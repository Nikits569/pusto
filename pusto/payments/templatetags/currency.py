from django import template

register = template.Library()

@register.filter
def euro(value):
    try:
        return "{:.2f}".format(int(value) / 100)
    except:
        return "—"