from support.forms import SupportTicketForm
from django.conf import settings

def support_form(request):
    return {
        'support_form': SupportTicketForm(),
        "TURNSTILE_SITE_KEY": settings.TURNSTILE_SITE_KEY,
    }