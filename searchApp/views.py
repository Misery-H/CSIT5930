import json
import os
import time
from collections import defaultdict
from urllib.parse import urlparse

import numpy as np
from django.core.cache import caches
from django.core.paginator import Paginator
from django.db.models import Avg
from django.http import JsonResponse
from django.http import StreamingHttpResponse
from django.shortcuts import render
from django.utils.html import escape
from django.views.decorators.http import require_GET
from lemminflect import getAllLemmas, getInflection

from searchApp.utils import *
from .models import Document, UrlLinkage, InvertedIndex, Term

# Cache instances
search_results_cache = caches['search_results']
search_suggestions_cache = caches['search_suggestions']
term_expansion_cache = caches['term_expansion']


# Generate display url
def process_url(url):
    parsed = urlparse(url)
    domain = parsed.netloc
    path = parsed.path.lstrip('/')
    parts = path.split('/')
    if parts:
        last_part = parts[-1]
        filename, ext = os.path.splitext(last_part)
        parts[-1] = filename

    result = f"{parsed.scheme}://{domain} > " + ' > '.join(parts)
    return result


def expand_query_term(term):
    expanded_terms = set()
    expanded_terms.add(term.lower())

    lemmas = getAllLemmas(term)

    for pos in lemmas:
        for lemma in lemmas[pos]:
            if pos == 'NOUN':
                plural = getInflection(lemma, 'NNS')
                if plural:
                    expanded_terms.add(plural[0].lower())

            elif pos == 'VERB':
                forms = getInflection(lemma, 'VBG')  # Gerund (filming)
                if forms: expanded_terms.update([f.lower() for f in forms])

                forms = getInflection(lemma, 'VBD')  # Past tense (filmed)
                if forms: expanded_terms.update([f.lower() for f in forms])

                forms = getInflection(lemma, 'VBN')  # Past participle (filmed)
                if forms: expanded_terms.update([f.lower() for f in forms])

                forms = getInflection(lemma, 'VBZ')  # 3rd person singular (films)
                if forms: expanded_terms.update([f.lower() for f in forms])

    return list(expanded_terms)


def process_query(query):
    terms = query.strip().split()
    if not terms:
        return []

    lower_terms = [term.lower() for term in terms]

    all_expanded_terms = set()
    for term in lower_terms:
        expanded_terms = expand_query_term(term)
        all_expanded_terms.update(expanded_terms)

    existing_terms = Term.objects.filter(term__in=list(all_expanded_terms))

    return list(existing_terms)


def search_page(request):
    return render(request, 'search_index.html')


@require_GET
def search_suggestions(request):
    query = request.GET.get('q', '').strip().lower()

    # Try to get suggestions from cache
    cache_key = f'suggestions_{query}'
    cached_suggestions = search_suggestions_cache.get(cache_key)

    if cached_suggestions is not None:
        return JsonResponse({'suggestions': cached_suggestions})

    suggestions = []
    if query:
        suggestions = Term.objects.filter(
            term__startswith=query
        ).annotate(
            avg_pr=Avg('invertedindex__document__pr_score')
        ).order_by(
            '-df',
            '-avg_pr'
        )[:6]

        suggestions = [term.term for term in suggestions]

    for i, suggestion in enumerate(suggestions):
        suggestions[i] = escape(suggestion)

    # cache the suggestion
    search_suggestions_cache.set(cache_key, suggestions, timeout=60 * 60)

    return JsonResponse({'suggestions': suggestions})


def search_results(request):
    query = request.GET.get('q', '')
    start = time.perf_counter()
    vague_search = False
    pages = []

    # try to get result from cache
    cache_key = f'search_results_{query}'
    cached_results = search_results_cache.get(cache_key)

    if cached_results is not None:
        context = json.loads(cached_results)
        context['time_consumption'] = f"{time.perf_counter() - start:.4f}"
        context['cache_hit'] = True
        return render(request, 'search_results.html', context)

    search_query = process_query(query)

    expanded_query = []
    if len(search_query) == 0:

        # try to get expanded terms from cache
        term_cache_key = f'term_expansion_{query}'
        cached_expanded_terms = term_expansion_cache.get(term_cache_key)

        if cached_expanded_terms is not None:
            existing_expanded_terms = cached_expanded_terms
        else:
            existing_expanded_terms = Term.objects.filter(term__in=vague_searcher.expand_terms(query))
            # Cache the expanded terms
            term_expansion_cache.set(term_cache_key, existing_expanded_terms, timeout=60 * 60)

        vague_search = True
        search_query = list(set(search_query + list(existing_expanded_terms)))
        expanded_query = [q.term for q in search_query]

    raw_docs = Document.objects.filter(invertedindex__term__in=search_query).distinct()

    # Relevance score calculation (core)
    # Calculate query term vector
    # Magic number: 1.0 for terms from origin query, 0.8 for terms from expansion
    original_query_term_strs = set([term.lower() for term in query.strip().split()])
    term_id_to_weight = {
        term.id: (1.0 if term.term in original_query_term_strs else 0.8)
        for term in search_query
    }

    query_term_ids = list(term_id_to_weight.keys())
    query_vector = np.array([term_id_to_weight[tid] for tid in query_term_ids])
    query_norm = np.linalg.norm(query_vector)

    # Collect terms idf vector
    total_docs = Document.objects.count()
    term_dfs = {term.id: term.df for term in search_query}
    idf_vector = np.array([
        np.log((total_docs + 1) / (term_dfs[tid] + 1)) + 1  # smooth
        for tid in query_term_ids
    ])

    # Collect tf for all doc-term pairs
    inv_indexes = InvertedIndex.objects.filter(
        term_id__in=query_term_ids, document__in=raw_docs
    ).values('document_id', 'term_id', 'tf')

    # Map doc_id to vector
    doc_vectors = defaultdict(lambda: np.zeros(len(query_term_ids)))

    term_index = {tid: i for i, tid in enumerate(query_term_ids)}

    for entry in inv_indexes:
        doc_id = entry['document_id']
        tid = entry['term_id']
        tf = entry['tf']
        idx = term_index[tid]
        doc_vectors[doc_id][idx] = tf

    # Calculate ranking score
    # Magic number: compute final ranking score as 0.7 * tf/idf + 0.2 * pagerank + 0.1 * HITS
    # TODO: Fine-tune Weight Params
    scores = {}
    relevance_scores = {}
    hits_scores = {}
    for doc in raw_docs:
        doc_vec_raw = doc_vectors[doc.id]
        doc_tfidf_vec = doc_vec_raw * idf_vector
        doc_norm = np.linalg.norm(doc_tfidf_vec)

        tfidf_score = np.dot(doc_tfidf_vec, query_vector) / (doc_norm * query_norm) if doc_norm != 0 else 0.0
        hits_score = (doc.authority_score + doc.hub_score) / 2.0

        final_score = (
                0.7 * tfidf_score +
                0.2 * doc.pr_score +
                0.1 * hits_score
        )

        hits_scores[doc.id] = hits_score
        relevance_scores[doc.id] = tfidf_score
        scores[doc.id] = final_score

    # Document ranking
    doc_list = sorted(raw_docs, key=lambda d: scores.get(d.id, 0), reverse=True)

    # Show docs
    for doc in doc_list:
        links = UrlLinkage.objects.filter(to_document_id=doc.id).select_related('from_document')
        from_docs = []
        for link in links:
            from_docs.append({
                'url': link.from_document.url,
                'title': link.from_document.title,
            })

        links = UrlLinkage.objects.filter(from_document_id=doc.id).select_related('to_document')
        to_docs = []
        for link in links:
            to_docs.append({
                'url': link.to_document.url,
                'title': link.to_document.title,
            })

        keywords_db = InvertedIndex.objects.filter(document_id=doc.id).select_related('term').order_by(
            '-tf').values_list(
            'term__term', flat=True)[:5]

        keywords = [keyword for keyword in keywords_db]

        # GENAI label judgement
        description_ai = False
        description = doc.description
        if description.split("`")[-1] == "AIDESC":
            description_ai = True
            description = "`".join(description.split("`")[:-1])

        # Compose a row (page)
        pages.append({
            'id': doc.id,
            'title': doc.title,
            'display_url': process_url(doc.url),
            'url': doc.url,
            'snippet': description,
            'desc_ai': description_ai,
            'last_modify': str(doc.last_modify),
            'size': doc.page_size,
            'keywords': keywords,
            'from_docs': from_docs,
            'to_docs': to_docs,
            'relevance_score': f"R: {round(relevance_scores.get(doc.id, 0), 4)}",
            'hits_score': f"H: {round(hits_scores.get(doc.id, 0), 4)}",
            'pr_score': f"P: {round(doc.pr_score, 4)}",
            'final_score': f"Score: {round(scores.get(doc.id, 0), 4)}",
        })

    end = time.perf_counter()

    context = {
        'query': query,
        'vague_search': vague_search,
        'expanded_query': expanded_query,
        'time_consumption': f"{end - start:.4f}",
        'pages': pages,
        'cache_hit': False,
    }

    save_context = {
        'query': query,
        'pages': pages,
    }
    # print(save_context)

    # Cache the search results
    search_results_cache.set(cache_key, json.dumps(save_context), timeout=60 * 60)

    return render(request, 'search_results.html', context)


def ai_analysis(request):
    query = request.GET.get('q', '')

    # try to get result from cache
    cache_key = f'search_results_{query}'
    cached_results = search_results_cache.get(cache_key)

    # Try 3 times
    attempt_times = 5

    while cached_results is None and attempt_times > 0:
        time.sleep(1)
        print(f"Try {6 - attempt_times} to fetch search result from redis with key = {cache_key}")
        cached_results = search_results_cache.get(cache_key)
        attempt_times -= 1

    documents = ""
    if cached_results is not None:
        # Use top 5 results
        top_docs = 5

        context = json.loads(cached_results)
        pages = context["pages"]

        for index, doc in enumerate(pages):
            if top_docs <= 0:
                break
            document = Document.objects.get(id=doc["id"]).content
            documents += f"Document {index}: {document}\n"
            top_docs -= 1

    prompt = f"""
    {aliyun_helper.PROMPT_TEMPLATE}
    Query: {query}
    Documents: {documents}
    """

    return StreamingHttpResponse(aliyun_helper.chat_complete_stream(prompt))


def pages(request, page_number=1):
    # LWT: this slide should be processed in SQL layer, instead of loading all records into memory.
    # Please monitor for performance degradation
    doc_count = Document.objects.all().count()
    paginator = Paginator(Document.objects.all().order_by("-pr_score"), 50, )
    pages_count = paginator.num_pages
    page_obj = paginator.get_page(page_number)

    # 生成智能页码范围（前后各显示2页）
    page_range = []
    for num in page_obj.paginator.page_range:
        if num <= 2 or \
                num >= page_obj.paginator.num_pages - 1 or \
                abs(num - page_obj.number) <= 2:
            page_range.append(num)
        elif page_range[-1] != '...':
            page_range.append('...')

    doc_list = paginator.page(page_number)
    pages = []

    for doc in doc_list:

        links = UrlLinkage.objects.filter(to_document_id=doc.id).select_related('from_document')
        from_docs = []
        for link in links:
            from_docs.append({
                'url': link.from_document.url,
                'title': link.from_document.title,
            })

        links = UrlLinkage.objects.filter(from_document_id=doc.id).select_related('to_document')
        to_docs = []
        for link in links:
            to_docs.append({
                'url': link.to_document.url,
                'title': link.to_document.title,
            })

        keywords = InvertedIndex.objects.filter(document_id=doc.id).select_related('term').order_by('-tf').values_list(
            'term__term', flat=True)[:5]

        description_ai = False
        description = doc.description
        if description.split("`")[-1] == "AIDESC":
            description_ai = True
            description = "`".join(description.split("`")[:-1])

        pages.append({
            'id': doc.id,
            'title': doc.title,
            'display_url': process_url(doc.url),
            'url': doc.url,
            'snippet': description,
            'desc_ai': description_ai,
            'last_modify': doc.last_modify,
            'size': doc.page_size,
            'keywords': keywords,
            'from_docs': from_docs,
            'to_docs': to_docs,
            'score': f"Pagerank: {round(doc.pr_score, 4)}"
        })

    context = {
        'doc_count': doc_count,
        'pages_count': pages_count,
        'page_number': page_number,
        'page_range': page_range,
        'pages': pages,
    }

    return render(request, 'pages.html', context)

def about(request):

    context = {
    }

    return render(request, 'about.html', context)
