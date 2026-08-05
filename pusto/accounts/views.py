from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.urls import reverse
from .forms import *
from django.shortcuts import get_object_or_404
from .models import *
from django.core.mail import send_mail
from django.conf import settings
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from .models import Profile
import hashlib
import hmac
from django.core.mail import send_mail
from .utils import check_support_rate_limit

def register_view(request):
    if request.user.is_authenticated:
        return redirect('/select')

    blocked = check_support_rate_limit(request)
    if blocked:
        return blocked

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.email_verification_token = uuid.uuid4()
            user.verification_email = False

            user.ip_address = request.META.get("HTTP_CF_CONNECTING_IP")
            user.user_agent = request.META.get("HTTP_USER_AGENT", "")

            user.save()

            verify_url = request.build_absolute_uri(
                reverse('verify_email', args=[str(user.email_verification_token)])
            )

            from_email = settings.EMAIL_HOST_USER
            send_mail(
                'Підтвердження Email',
                f'Привіт, {user.first_name}!\nПерейдіть за посиланням для підтвердження: {verify_url}',
                from_email,
                [user.email],
                fail_silently=False
            )

            return render(request, 'accounts/email_verified.html', {
                'msg': 'Ми надіслали лист для підтвердження email. Перейдіть за посиланням, яке прийшло вам на пошту.'
            })
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form, "TURNSTILE_SITE_KEY": settings.TURNSTILE_SITE_KEY})


def login_view(request):

    if request.user.is_authenticated: return redirect('/')
    msg = ''
    show_resend = False
    user_obj = None

    if request.method == 'POST':
        form = LoginForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            try: user_obj = Profile.objects.get(email=email)
            except Profile.DoesNotExist: user_obj = None

            if user_obj:
                if not user_obj.is_active:
                    msg = f'Аккаунт не подтверждён. Проверьте почту: { email }'
                    show_resend = True

                else:
                    user = authenticate(request, email=email, password=password)
                    if user:
                        login(request, user)
                        return redirect('/login')
                    else: msg = 'Неверный пароль'
            else: msg = 'Неверный email'

    else: form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form, 'msg': msg, 'show_resend': show_resend, 'user_obj': user_obj})

def logout_view(request):
    logout(request)
    return redirect('ads:select')

def verify_email(request, token):
    user = get_object_or_404(Profile, email_verification_token=token)

    if user.verification_email:
        msg = 'електронну адресу вже підтверджено.'

    else:
        user.is_active = True
        user.verification_email = True
        user.save(update_fields=['is_active', 'verification_email'])
        msg = 'електронну адресу підтверджено. '


    return render(request, 'accounts/email_verified.html', {'msg': msg})

def verify_post_email(request, token):
    # ищем токен в трёх таблицах
    post = ThingsPost.objects.filter(email_verification_token=token).first()
    if not post:
        post = JobPost.objects.filter(email_verification_token=token).first()
    if not post:
        post = NeighborPost.objects.filter(email_verification_token=token).first()

    if not post:
        return render(request, 'accounts/email_verified.html', {'msg': 'Ссылка недействительна или устарела.'}, status=404)

    # уже активировано
    if post.status == Status.ACTIVE and post.email_confirmed:
        # можно вести на страницу объявления
        return redirect(post.get_absolute_url() if hasattr(post, "get_absolute_url") else '/')

    post.email_confirmed = True
    post.status = Status.ACTIVE
    post.email_verification_token = None  # одноразовая ссылка
    post.save(update_fields=['email_confirmed', 'status', 'email_verification_token'])

    # редирект на объявление
    return redirect(post.get_absolute_url() if hasattr(post, "get_absolute_url") else '/')

@require_POST
def resend_verification(request):
    user_id = request.POST.get('user_id')

    try:
        user = Profile.objects.get(id=user_id)

        if not user.is_active and not user.verification_email:
            verify_url = request.build_absolute_uri(
                reverse('verify_email', args=[str(user.email_verification_token)])
            )

            send_mail(
                'Підтвердіть email',
                f'Перейдіть за посиланням для підтвердження: {verify_url}',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )

    except Profile.DoesNotExist:
        pass

    return redirect('login')

