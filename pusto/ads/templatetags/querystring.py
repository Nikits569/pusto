from django import template

register = template.Library()

@register.simple_tag
def query_transform(request, **kwargs):
    updated = request.GET.copy()
    for k, v in kwargs.items():
        if v is None:
            updated.pop(k, None)
        else:
            updated[k] = v
    return updated.urlencode()
