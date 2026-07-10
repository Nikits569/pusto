import re

from django.db.models import Q, Case, When, Value, IntegerField
from .search_config import SEARCH_SYNONYMS


def normalize_search_text(text: str) -> str:
    text = (text or '').strip().lower()
    text = re.sub(r'\s+', ' ', text)
    return text


def expand_search_terms(text: str) -> list[str]:
    terms = text.split()
    expanded = list(terms)

    for term in terms:
        if term in SEARCH_SYNONYMS:
            expanded.extend(SEARCH_SYNONYMS[term])

    seen = set()
    result = []
    for item in expanded:
        item = item.strip().lower()
        if item and item not in seen:
            seen.add(item)
            result.append(item)

    return result


def build_or_query(fields, terms):
    query = Q()

    for field in fields:
        field_query = Q()

        for term in terms:
            field_query |= Q(**{f"{field}__icontains": term})

        query |= field_query

    return query


def build_relevance_case(priority_rules: list[tuple[str, int]], terms: list[str]):
    whens = []

    for field, weight in priority_rules:
        for term in terms:
            whens.append(
                When(**{f"{field}__icontains": term}, then=Value(weight))
            )

    return Case(
        *whens,
        default=Value(0),
        output_field=IntegerField(),
    )


def apply_smart_search_mysql(
    qs,
    search_text: str,
    *,
    search_fields: list[str],
    priority_rules: list[tuple[str, int]],
):
    normalized = normalize_search_text(search_text)
    if not normalized:
        return qs.none()

    terms = expand_search_terms(normalized)

    if not terms:
        return qs.none()

    query = build_or_query(search_fields, terms)
    relevance = build_relevance_case(priority_rules, terms)

    return (
        qs.filter(query)
        .annotate(relevance=relevance)
        .order_by('-relevance', '-created_at')
    )


def search_things_queryset(qs, search_text: str):
    return apply_smart_search_mysql(
        qs,
        search_text,
        search_fields=[
            'title',
            'title_en',
            'text',
            'text_en',
            'city',
            # 'subcategory__title_sk',
            #'subcategory__title_uk',
            #'subcategory__title_en',
            #'subcategory__category__title_sk',
            #'subcategory__category__title_uk',
            #'subcategory__category__title_en',
        ],
        priority_rules=[
            ('title', 100),
            ('title_en', 100),
            # ('subcategory__title_sk', 90),
            #('subcategory__title_uk', 90),
            #('subcategory__title_en', 90),
            #('subcategory__category__title_sk', 80),
            #('subcategory__category__title_uk', 80),
            #('subcategory__category__title_en', 80),
            ('text', 50),
            ('text_en', 50),
            ('city', 30),
        ],
    )


#def search_jobs_queryset(qs, search_text: str):
#    return apply_smart_search_mysql(
#        qs,
#        search_text,
#        search_fields=[
#            'title',
#            'company_name',
#            'text',
#            'city',
#        ],
#        priority_rules=[
#            ('title', 100),
#            ('company_name', 90),
#            ('text', 50),
#            ('city', 30),
#        ],
#    )


def search_neighbors_queryset(qs, search_text: str):
    return apply_smart_search_mysql(
        qs,
        search_text,
        search_fields=[
            'title',
            'title_en',
            'text',
            'text_en',
            'city',
        ],
        priority_rules=[
            ('title', 100),
            ('title_en', 100),
            ('city', 80),
            ('text', 50),
            ('text_en', 50),
        ],
    )