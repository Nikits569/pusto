from django.shortcuts import render
from django.http import Http404
from ads.models import *
from django.utils.translation import get_language

cities = {'Presov': 'Пряшівові', 'Bratislava': 'Братіславі', 'Kosice': 'Кошиці'}

def rent(request, slug):

    if slug not in cities:
        raise Http404()

    neighbors = NeighborPost.objects.filter(caseType='rent', city=slug).order_by('-created_at')[:4]

    if get_language() == 'uk':
        city = cities[slug]
    else:
        city = slug

    return render(request, 'SEO/rent.html', {
        'city': city,
        'neighbor_favorites': neighbors,
    })

def things(request, slug):

    if slug not in cities:
        raise Http404()

    thing = ThingsPost.objects.filter(caseType='sell_category', city=slug).order_by('-created_at')[:4]

    if get_language() == 'uk':
        city = cities[slug]
    else:
        city = slug

    return render(request, 'SEO/things.html', {
        'city': city,
        'neighbor_favorites': thing,
    })