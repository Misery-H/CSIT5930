import os
import time
from urllib.parse import urlparse

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

    return JsonResponse({'suggestions': suggestions})


def search_results(request):
    query = request.GET.get('q', '')
    start = time.perf_counter()
    vague_search = False
    pages = []

    search_query = process_query(query)

    expanded_query = []
    if len(search_query) == 0:
        existing_expanded_terms = Term.objects.filter(term__in=vague_searcher.expand_terms(query))
        vague_search = True
        search_query = list(set(search_query + list(existing_expanded_terms)))
        expanded_query = [q.term for q in search_query]

    raw_docs = Document.objects.filter(invertedindex__term__in=search_query).distinct()
    print(search_query)

    # TODO: doc ranking
    doc_list = raw_docs

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

        # TODO: fetch keywords
        keywords = InvertedIndex.objects.filter(document_id=doc.id).select_related('term').order_by('-tf').values_list(
            'term__term', flat=True)[:5]

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
            'last_modify': doc.last_modify,
            'size': doc.page_size,
            'keywords': keywords,
            'from_docs': from_docs,
            'to_docs': to_docs,
            'score': f"Pagerank: {round(doc.pr_score, 4)}"
        })

    end = time.perf_counter()

    context = {
        'query': query,
        'vague_search': vague_search,
        'expanded_query': expanded_query,
        'time_consumption': f"{end - start:.4f}",
        'pages': pages,
    }

    return render(request, 'search_results.html', context)


def ai_analysis(request):
    query = request.GET.get('q', '')

    return StreamingHttpResponse(aliyun_helper.chat_complete_stream(query))


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
