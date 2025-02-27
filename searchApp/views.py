import os
import time
from urllib.parse import urlparse

from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from searchApp.utils import *
from django.http import StreamingHttpResponse
from django.utils.html import escape
from .models import Document, UrlLinkage


def search_page(request):
    return render(request, 'search_index.html')


@require_GET
def search_suggestions(request):
    query = request.GET.get('q', '')
    suggestions = []
    if query:
        # TODO: Make suggestions

        suggestions = [
            f"WIP: suggestion for {query} 1",
            f"WIP: suggestion for {query} 2",
            f"WIP: suggestion for {query} 3",
            f"WIP: suggestion for {query} 4",
            f"WIP: suggestion for {query} 5",
        ]

    for i, suggestion in enumerate(suggestions):
        suggestions[i] = escape(suggestion)

    return JsonResponse({'suggestions': suggestions})


def search_results(request):
    query = request.GET.get('q', '')
    # Add your actual search logic here

    start = time.perf_counter()

    results = []  # Replace with actual search results
    # TODO: REMOVE THIS SLEEP AFTER FORMAL IMPLEMENTATION OF SEARCHING!
    time.sleep(1)

    end = time.perf_counter()

    context = {
        'query': query,
        'time_consumption': f"{end - start:.4f}",
        'results': [
            {
                'title': "Example Result 1",
                'url': "#",
                'display_url': "www.example.com › example-page",
                'snippet': "This is an example search result snippet text that shows relevant content from the page."
            },
            # Add more result objects
        ]
    }
    return render(request, 'search_results.html', context)


def ai_analysis(request):
    query = request.GET.get('q', '')

    return StreamingHttpResponse(aliyun_helper.chat_complete(query))


def pages(request, page_number=1):
    # LWT: this slide should be processed in SQL layer, instead of loading all records into memory.
    # Please monitor for performance degradation
    paginator = Paginator(Document.objects.all(), 50)
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
        keywords = ["keywords1", "keywords2", "keywords3", "keywords4", "keywords5"]

        pages.append({
            'id': doc.id,
            'title': doc.title,
            'display_url': process_url(doc.url),
            'url': doc.url,
            'snippet': doc.description,
            'last_modify': doc.last_modify,
            'size': "121KB",  # TODO
            'keywords': keywords,
            'from_docs': from_docs,
            'to_docs': to_docs,
            'score': "114514"  # TODO
        })

    context = {
        'pages_count': pages_count,
        'page_number': page_number,
        'page_range': page_range,
        'pages': pages,
    }

    return render(request, 'pages.html', context)
