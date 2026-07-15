from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils.translation import check_for_language


def custom_set_language(request):
    next_url = request.POST.get('next') or '/'
    lang_code = request.POST.get('language')

    if lang_code and check_for_language(lang_code):
        parts = next_url.split('/', 2)  # ['', 'uk', 'rest/of/path']
        rest = parts[2] if len(parts) > 2 else ''
        next_url = f'/{lang_code}/{rest}'

        response = HttpResponseRedirect(next_url)
        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang_code)
        return response

    return HttpResponseRedirect(next_url)