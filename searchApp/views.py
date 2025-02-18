import time

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from searchApp.utils import *
from django.http import StreamingHttpResponse
from django.utils.html import escape


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