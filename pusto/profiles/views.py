from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from accounts.models import *
from ads.models import *
from .forms import *
from itertools import chain
from django.contrib import messages
from django.core.mail import send_mail
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import redirect
from django.contrib import messages
from django.db.models import Q
from accounts.models import *
from django.urls import reverse
from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)

@login_required
def MyProfileEdit(request):
    if not request.user.is_authenticated: return redirect('/index')
    user = request.user  # текущий пользователь
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            return redirect('profiles:MyProfile')  # перенаправление на страницу профиля
    else:
        form = ProfileForm(instance=user)

    return render(request, 'profiles/edit_profile.html', {'form': form})

from itertools import chain

from django.shortcuts import redirect, render, get_object_or_404
from django.utils import timezone
from django.db.models import Prefetch

# imports моделей оставь свои
# from .models import Profile, TgLinkCode
# from ads.models import NeighborPost, ThingsPost, JobPost
# from .forms import ProfileForm


def _prepare_profile_posts(user):
    neighbor_posts = list(
        NeighborPost.objects.filter(user=user).prefetch_related(
            Prefetch('images', to_attr='prefetched_images')
        )
    )
    things_posts = list(
        ThingsPost.objects.filter(user=user).prefetch_related(
            Prefetch('images', to_attr='prefetched_images')
        )
    )
    job_posts = list(
        JobPost.objects.filter(user=user).prefetch_related(
            Prefetch('images', to_attr='prefetched_images')
        )
    )

    all_posts = sorted(
        chain(neighbor_posts, job_posts, things_posts),
        key=lambda post: post.created_at,
        reverse=True
    )

    for post in all_posts:
        post.type_name = post.__class__.__name__

        if isinstance(post, ThingsPost):
            post.type_key = 'things'
        elif isinstance(post, JobPost):
            post.type_key = 'jobs'
        elif isinstance(post, NeighborPost):
            post.type_key = 'neighbors'

        prefetched = getattr(post, 'prefetched_images', None)
        post.first_image = prefetched[0] if prefetched else None

    return all_posts


@login_required
def regenerate_tg_code(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    user = request.user

    # Можно старые неиспользованные коды пометить как used=True,
    # если хочешь, чтобы был только один активный код.
    TgLinkCode.objects.filter(
        user=user,
        used=False,
        expires_at__gt=timezone.now()
    ).update(used=True)

    code = TgLinkCode.create_code(user)

    return JsonResponse({
        'code': code.code,
        'expires_at': code.expires_at.isoformat(),
    })

def MyProfile(request):
    if not request.user.is_authenticated:
        return redirect('/index')

    user = request.user

    code = TgLinkCode.objects.filter(
        user=user,
        used=False,
        expires_at__gt=timezone.now()
    ).first()

    if not code:
        code = TgLinkCode.create_code(user)

    all_posts = _prepare_profile_posts(user)

    if request.method == 'POST' and 'edit_profile' in request.POST:
        form = ProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            return redirect('profiles:MyProfile')
    else:
        form = ProfileForm(instance=user)

    return render(
        request,
        'profiles/myprofile.html',
        {
            'all_posts': all_posts,
            'user': user,
            'tg_code': code.code,
            'tg_code_expires': code.expires_at,
            'form': form,
        }
    )


def otherProfile(request, idProfile):
    myuser = request.user
    user = get_object_or_404(Profile, id=idProfile)

    code = TgLinkCode.objects.filter(
        user=user,
        used=False,
        expires_at__gt=timezone.now()
    ).first()

    if not code:
        code = TgLinkCode.create_code(user)

    all_posts = _prepare_profile_posts(user)

    return render(
        request,
        'profiles/otherprofile.html',
        {
            'user': user,
            'myuser': myuser,
            'all_posts': all_posts,
            'tg_code': code.code,
            'tg_code_expires': code.expires_at,
        }
    )
@login_required
def delete_post(request, post_type, post_id):

    """
    post_type: 'things', 'job', 'neighbor'
    post_id: id конкретного объявления
    """
    model_map = {
        'things': ThingsPost,
        'job': JobPost,
        'neighbor': NeighborPost
    }

    model = model_map.get(post_type)
    
    if not model:
        logger.info("Not Model")
        return redirect('profiles:MyProfile')  # если неверный тип поста

    post = get_object_or_404(model, id=post_id)

    if post.user and post.user != request.user:
        return redirect('profiles:MyProfile')

    post.delete()
    #post = get_object_or_404(model, id=post_id, user=request.user)
    #post.delete()

    return redirect('profiles:MyProfile')

@login_required
def edit_post(request, post_type, post_id):
    post_map = {
        'jobs': {
            'model': JobPost,
            'form': JobPostEditForm,
            'image_model': JobPostImage,
        },
        'things': {
            'model': ThingsPost,
            'form': ThingsPostEditForm,
            'image_model': ThingsPostImage,
        },
        'neighbors': {
            'model': NeighborPost,
            'form': NeighborPostEditForm,
            'image_model': NeighborPostImage,
        },
    }

    config = post_map.get(post_type)
    if not config:
        print('Eror config  ------------------------------')
        return redirect('profiles:MyProfile')

    PostModel = config['model']
    FormClass = config['form']
    ImageModel = config['image_model']

    post = get_object_or_404(PostModel, id=post_id, user=request.user)

    if request.method == 'POST':
        form = FormClass(request.POST, instance=post)
        if form.is_valid():
            form.save()

            # удаление изображений
            delete_images = request.POST.getlist('delete_images')
            if delete_images:
                ImageModel.objects.filter(
                    id__in=delete_images,
                    post=post
                ).delete()

            # добавление новых изображений
            for img in request.FILES.getlist('images'):
                ImageModel.objects.create(
                    post=post,
                    image=img
                )

            return redirect('profiles:MyProfile')
    else:
        form = FormClass(instance=post)

    return render(request, 'profiles/edit_post.html', {
        'form': form,
        'post': post,
        'images': post.images.all(),
        'post_type': post_type,
    })

def EmployerVerificationView(request):
    if not request.user.is_authenticated:
        return redirect('select')

    user = request.user

    # 1. Якщо email не підтверджений — надіслати лист повторно
    if not user.verification_email:
        verify_url = request.build_absolute_uri(
            reverse('verify_email', args=[str(user.email_verification_token)])
        )

        send_mail(
            'Підтвердіть Email',
            f'Перейдіть за посиланням для підтвердження: {verify_url}',
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )

        messages.error(
            request,
            'Ваш email не підтверджений. Ми надіслали вам новий лист для підтвердження.'
        )
        return redirect('profiles:MyProfile')

    # 2. Перевірка існуючої заявки
    existing = Employer.objects.filter(user=user).first()
    if existing:
        if existing.status == 'verified':
            messages.error(
                request,
                'Ви вже пройшли верифікацію роботодавця.'
            )
        else:
            messages.info(
                request,
                f'Ви вже надсилали заявку. Статус: {existing.get_status_display()}'
            )
        return redirect('profiles:MyProfile')

    # 3. POST — обробка форми
    if request.method == 'POST':
        form = EmployerVerificationForm(request.POST)


        if form.is_valid():
            employer_verif = form.save(commit=False)
            employer_verif.user = user
            employer_verif.save()

            message = (
                f'Вітаємо, {user.first_name}!\n\n'
                'Вашу заявку на верифікацію роботодавця успішно отримано та передано на розгляд.\n\n'
                'Наразі дані проходять перевірку.\n\n'
                'Після завершення перевірки ви отримаєте окреме повідомлення з результатом.\n\n'
                'З повагою,\n'
                'Команда сервісу'
            )

            send_mail(
                subject='Верифікація роботодавця',
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )

            messages.success(
                request,
                f'Заявку надіслано. Статус: {employer_verif.get_status_display()}'
            )
            return redirect('profiles:MyProfile')
    else:
        form = EmployerVerificationForm()

    return render(request, 'profiles/employerVerification.html', {'form': form})

def StudentVerificationView(request):
    if not request.user.is_authenticated:
        return redirect('select')

    user = request.user

    # 1. Если email не подтвержден — шлем письмо повторно
    if not user.verification_email:
        verify_url = request.build_absolute_uri(
            reverse('verify_email', args=[str(user.email_verification_token)])
        )

        send_mail(
            'Підтвердіть Email',
            f'Перейдіть за посиланням для підтвердження: {verify_url}',
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )

        messages.error(
            request,
            'Ваш email не підтверджений. Ми надіслали вам новий лист для підтвердження.'
        )
        return redirect('profiles:MyProfile')

    # 2. Проверка существующей заявки
    existing = Student.objects.filter(user=user).first()
    if existing:
        if existing.status == 'verified':
            messages.error(
                request,
                'Ви вже пройшли студентську верифікацію.'
            )
        else:
            messages.info(
                request,
                f'Ви вже надсилали заявку. Статус: {existing.get_status_display()}'
            )
        return redirect('profiles:MyProfile')

    # 3. Обработка POST
    if request.method == 'POST':

        message = (
            f'Вітаємо, {user.first_name}!\n\n'
            'Для проходження студентської верифікації, будь ласка, відповідайте на цей лист '
            'та додайте підтвердження статусу студента.\n\n'
            'Ви можете надати один із наступних документів:\n'
            '- довідку з навчального закладу або\n'
            '- студентський квиток\n\n'
            'Зверніть увагу:\n'
            '- дозволяється приховати номер документа, штрих-код та інші чутливі дані;\n'
            '- достатньо, щоб було видно ваше ім’я та факт навчання;\n'
            '- не надсилайте документи, що містять надлишкові персональні дані.\n\n'
            'Надані матеріали використовуються виключно для перевірки та '
            'видаляються після завершення верифікації.\n\n'
            'Після перевірки ви отримаєте окреме повідомлення з результатом.\n\n'
            'З повагою,\n'
            'Команда сервісу'
        )

        send_mail(
            subject='Студентська верифікація',
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        new_request = Student.objects.create(user=user)

        messages.success(
            request,
            f'Заявку надіслано. Статус: {new_request.get_status_display()}'
        )
        return redirect('profiles:MyProfile')

    return render(request, 'profiles/studentVerification.html')

def UserVerificationView(request):
    if not request.user.is_authenticated:
        return redirect('select')

    user = request.user

    # 1. Якщо email НЕ підтверджений → відправити повторно
    if not user.verification_email:

        verify_url = request.build_absolute_uri(
            reverse('verify_email', args=[str(user.email_verification_token)])
        )

        send_mail(
            'Підтвердіть Email',
            f'Перейдіть за посиланням для підтвердження: {verify_url}',
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )

        messages.error(
            request,
            'Ваш email не підтверджений. Ми надіслали вам новий лист для підтвердження.'
        )
        return redirect('profiles:MyProfile')

    # 2. Перевірка заявки
    existing = CommonUser.objects.filter(user=user).first()
    if existing:
        if existing.status == 'verified':
            messages.error(
                request,
                'Ви вже пройшли верифікацію користувача.'
            )
        else:
            messages.info(
                request,
                f'Ви вже надсилали заявку. Статус: {existing.get_status_display()}'
            )
        return redirect('profiles:MyProfile')

    # 3. Перевірка оголошень
    has_post = (
        NeighborPost.objects.filter(user=user).exists() or
        ThingsPost.objects.filter(user=user).exists() or
        JobPost.objects.filter(user=user).exists()
    )

    if not has_post:
        messages.error(
            request,
            'Для проходження верифікації потрібно мати хоча б одне опубліковане оголошення.'
        )
        return redirect('profiles:MyProfile')

    # 4. POST
    if request.method == 'POST':
        if request.POST.get('human_check') != 'yes':
            messages.error(request, 'Підтвердьте, що ви не робот.')
            return redirect('profiles:verification')

        message = (
            f'Вітаємо, {user.first_name}!\n\n'
            'Ваш запит на верифікацію акаунта успішно отримано та передано на розгляд.\n\n'
            'Наразі ваш акаунт проходить перевірку.\n\n'
            'Дякуємо за використання нашого сервісу.'
        )

        send_mail(
            subject='Верифікація користувача',
            message=message,
            from_email='verify@yourapp.com',
            recipient_list=[user.email],
            fail_silently=False,
        )

        new_request = CommonUser.objects.create(user=user)

        messages.success(
            request,
            f'Заявку надіслано. Статус: {new_request.get_status_display()}'
        )
        return redirect('profiles:MyProfile')

    return render(request, 'profiles/userVerification.html')

@login_required
@require_POST
def claim_posts_by_email(request):
    user = request.user
    email = (user.email or "").strip().lower()

    if not email:
        messages.error(request, "У аккаунта нет email.")
        return redirect('profile')  # поменяй на свой url профиля

    # Берём только "ничейные" объявления по email
    things_qs = ThingsPost.objects.filter(user__isnull=True, email__iexact=email)
    jobs_qs = JobPost.objects.filter(user__isnull=True, email__iexact=email)
    neigh_qs = NeighborPost.objects.filter(user__isnull=True, email__iexact=email)

    # При желании — только подтверждённые email объявления
    things_qs = things_qs.filter(email_confirmed=True)
    jobs_qs = jobs_qs.filter(email_confirmed=True)
    neigh_qs = neigh_qs.filter(email_confirmed=True)

    # При желании — только активные
    # things_qs = things_qs.filter(status=Status.ACTIVE)
    # jobs_qs = jobs_qs.filter(status=Status.ACTIVE)
    # neigh_qs = neigh_qs.filter(status=Status.ACTIVE)

    updated_things = things_qs.update(user=user)
    updated_jobs = jobs_qs.update(user=user)
    updated_neigh = neigh_qs.update(user=user)

    total = updated_things + updated_jobs + updated_neigh

    if total == 0:
        messages.info(request, "Не найдено объявлений для привязки по вашему email.")
    else:
        messages.success(request, f"Готово! Привязано объявлений: {total}")

    return redirect('profiles:MyProfile')  # поменяй на свою страницу аккаунта/профиля