from ads.models import *
from accounts.models import *
from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404, redirect, render
from .forms import *
from django.utils import timezone
from django.contrib import messages
from django.db.models import F
from django.contrib.contenttypes.models import ContentType
from .models import TrackedLink
from django.http import HttpResponseRedirect

def support_submit(request):
    if request.method == 'POST':
        form = SupportTicketForm(request.POST)
        if form.is_valid():
            form.save()

    return redirect('success')

def support_create(request):
    if request.method == 'POST':
        form = SupportTicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.user = request.user
            ticket.save()
            return redirect('success')
    else:
        form = SupportTicketForm()
    return render(request, 'support/support.html', {'form': form})

def success(request):
    user = request.user
    return render(request, 'support/success.html', {'user': user})

def confirmationView(request):
    return render(request, 'support/confirmation.html')



def create_claim(request, app_label, model_name, object_id):
    # Получаем объект, на который подается жалоба
    user = request.user
    if not request.user.is_authenticated:
        messages.error(request, f"Для начала нужно войти или зарегестрировать аккаунт.")
        return redirect('ads:select')

    content_type = get_object_or_404(ContentType, app_label=app_label, model=model_name.lower())
    target_object = get_object_or_404(content_type.model_class(), pk=object_id)

    # 🔹 Проверка, подал ли уже пользователь жалобу на этот объект
    if ClaimRequest.objects.filter(user=request.user, content_type=content_type, object_id=object_id).exists():
        messages.error(request, "Вы уже подали жалобу на этот объект.")
        return redirect('ads:select')

    if request.method == 'POST':
        form = ClaimRequestForm(request.POST)

        if form.is_valid():
            # 🔹 Проверка лимита на сегодня
            today = timezone.now().date()
            limit = getattr(settings, 'DAILY_LIMITS', {}).get('claim', 5)  # по умолчанию 5 жалоб в день
            count_today = ClaimRequest.objects.filter(user=user, created_at__date=today).count()

            if limit > 0 and count_today >= limit:
                messages.error(request, f"Вы достигли лимита подачи жалоб на сегодня ({limit}).")
                return redirect(request.path)

            # Создаем жалобу
            claim = form.save(commit=False)
            claim.user = request.user
            claim.content_type = content_type
            claim.object_id = object_id
            claim.save()

            messages.success(request, "Жалоба успешно отправлена.")
            return render(request, 'support/success.html', {'claim': claim})
    else:
        form = ClaimRequestForm()

    return render(request, 'support/create_claim.html', {
        'form': form,
        'target': target_object,
    })



def tracked_redirect(request, slug):
    link = get_object_or_404(TrackedLink, slug=slug)

    TrackedLink.objects.filter(pk=link.pk).update(
        clicks=F('clicks') + 1
    )

    url = link.original_url.strip()

    if not url.startswith(("http://", "https://", "/")):
        url = "https://" + url

    return HttpResponseRedirect(url)