from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET


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

    return JsonResponse({'suggestions': suggestions})


def search_results(request):
    query = request.GET.get('q', '')

    # TODO: Generate search results

    context = {
        'query': query,
        'results': []
    }
    return render(request, 'results.html', context)
