from support.forms import SupportTicketForm

def support_form(request):
    return {
        'support_form': SupportTicketForm()
    }