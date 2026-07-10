from django.shortcuts import render
from django.http import Http404
from ads.models import *

cities = {'Presov': 'Пряшівові', 'Bratislava': 'Братіславі', 'Kosice': 'Кошиці'}

def rent(request, slug):

    if slug not in cities:
        raise Http404()

    neighbors = NeighborPost.objects.filter(caseType='rent').order_by('-created_at')[:4]

    return render(request, 'SEO/rent.html', {
        'city': cities[slug],
        'neighbor_favorites': neighbors,
    })

def things(request, slug):

    if slug not in cities:
        raise Http404()

    thing = ThingsPost.objects.filter(caseType='sell_category').order_by('-created_at')[:4]

    return render(request, 'SEO/things.html', {
        'city': cities[slug],
        'neighbor_favorites': thing,
    })