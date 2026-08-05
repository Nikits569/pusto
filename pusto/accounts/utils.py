from datetime import timedelta
from django.shortcuts import redirect
from django.http import HttpResponse
from django.utils import timezone
from django.contrib import messages
from .models import Profile


def check_support_rate_limit(request):
    ip = request.META.get("HTTP_CF_CONNECTING_IP")

    if not ip:
        return None

    hour_ago = timezone.now() - timedelta(hours=1)

    count = Profile.objects.filter(
        ip_address=ip,
        created_at__gte=hour_ago
    ).count()

    if count >= 3:
        messages.error(
            request,
            "Ви надіслали надто багато звернень. Спробуйте пізніше."
        )
        return redirect("/")
    return None