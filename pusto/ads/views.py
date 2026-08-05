from django.shortcuts import render, get_object_or_404
from accounts.models import *
from django.views.generic import TemplateView, CreateView
from django.shortcuts import redirect
from .forms import *
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from payments.models import *
from django.db.models import OuterRef, Exists
from django.views.decorators.http import require_POST
from django.http import Http404
from telethon.tl.types import PhotoSize
from django.urls import reverse
from django.core.mail import send_mail
from .models import *
from django.http import JsonResponse
from support.forms import *
from django.db import OperationalError
from urllib.parse import urlencode
from django.views import View
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import F, Q, Value
from django.db.models.functions import Coalesce
from .search import *
from django.db.models import Case, Exists, F, IntegerField, OuterRef, Q, Value, When
from django.db.models import Prefetch
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib.admin.views.decorators import staff_member_required
import json
from urllib.parse import quote
from django.core.cache import cache
import requests
from interactions.forms import *

TG_SUPERGROUP_PREFIX = 1000000000000

chat_invite = {
    '1175233956': 'https://t.me/baraholka_presov_kosice',
    '1956832493': 'https://t.me/kosiceflats',
    '2091082928': 'https://t.me/arenda_nitra',
    '2101692521': 'https://t.me/baraholka_nitra',
    '1912835249': 'https://t.me/nitra_hack',
    '1386423654': 'https://t.me/tuke_hack',
    '1274583303': 'https://t.me/kosice_hack',
    '2240457831': 'https://t.me/DreamCityGroupSro',
    '1764112838': 'https://t.me/GoldKeyBratislava',
    '2766446415': 'https://t.me/NashaBratislava',
    '1840072195': 'https://t.me/rent_slovakia',
    '1974415585': 'https://t.me/GoldKeyKosice',
    '2149548602': 'https://t.me/prenajom_v_Kosice',
    '2013028399': 'https://t.me/rent_kosice',
    '1612101159': 't.me/realestateSlovensko',
}

class GlobalSearchView(View):
    def get(self, request, *args, **kwargs):
        q = request.GET.get('q', '').strip()
        q_normalized = normalize_search_text(q)

        print('RAW QUERY:', repr(q))
        print('NORMALIZED:', repr(q_normalized))

        if not q_normalized:
            return redirect('home')

        # --- MULTILANG SEARCH ---
        # всегда ищем и по основным полям, и по *_en
        things_qs = search_things_queryset(
            ThingsPost.objects.select_related(
                'category',
            ),
            q_normalized,

        )

        #jobs_qs = search_jobs_queryset(
        #    JobPost.objects.all(),
        #    q_normalized,
        #)

        neighbors_qs = search_neighbors_queryset(
            NeighborPost.objects.all(),
            q_normalized,

        )

        things_count = things_qs.count()
        #jobs_count = jobs_qs.count()
        neighbors_count = neighbors_qs.count()

        print('THINGS COUNT:', things_count)
        #print('JOBS COUNT:', jobs_count)
        print('NEIGHBORS COUNT:', neighbors_count)

        best_target = 'ads:things_all'
        best_count = things_count

        #if jobs_count > best_count:
        #    best_target = 'ads:jobs_all'
        #    best_count = jobs_count

        if neighbors_count > best_count:
            best_target = 'ads:neighbors_all'
            best_count = neighbors_count

        print('BEST TARGET:', best_target)

        target_url = reverse(best_target)
        query_string = urlencode({'search': q})   # или {'q': q}, см. ниже

        return redirect(f'{target_url}?{query_string}')

def candidate_chat_ids(chat_id: int) -> list[int]:
    cid = int(chat_id)
    if cid < 0:
        return [cid]  # уже telethon-формат (-100... или -...)
    # пробуем: супер/канал (-100...), потом обычная группа (-id)
    return [-(TG_SUPERGROUP_PREFIX + cid), -cid]

def _pick_thumb(photo):
    sizes = getattr(photo, "sizes", []) or []
    medium = [s for s in sizes if isinstance(s, PhotoSize) and 300 <= getattr(s, "w", 0) <= 700]
    small  = [s for s in sizes if isinstance(s, PhotoSize) and getattr(s, "w", 0) < 300]
    if medium:
        return max(medium, key=lambda x: x.w)
    if small:
        return max(small, key=lambda x: x.w)
    return None

async def fetch_cover_bytes(client, chat_id: int, msg_id: int):
    last_err = None

    for cid in candidate_chat_ids(chat_id):
        try:
            msg = await client.get_messages(cid, ids=int(msg_id))
            if msg and msg.photo:
                thumb = _pick_thumb(msg.photo)
                data = await client.download_media(msg.photo, file=bytes, thumb=thumb)
                if not data:
                    raise FileNotFoundError("Cannot download")

                content_type = "image/jpeg"
                if data[:8] == b"\x89PNG\r\n\x1a\n":
                    content_type = "image/png"
                return data, content_type

        except Exception as e:
            last_err = e
            continue

    raise FileNotFoundError(f"No photo (last_err={last_err!r})")

def mark_tg_deleted_everywhere(chat_id: int, msg_id: int):
    for model in (ThingsPost, JobPost, NeighborPost):
        model.objects.filter(
            chat_id=chat_id,
            photo_id=msg_id,
            tg_deleted=False,
        ).update(tg_deleted=True)

def is_db_locked_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return (
        "database is locked" in text
        or "database table is locked" in text
        or isinstance(exc, OperationalError)
        and "locked" in text
    )

# Create your views here.
def select(request):

    return render(request, 'ads/selectAds.html')

def get_slider_images(self):
    slides = []

    # Bazos
    if getattr(self.obj, "source", None) == "bazos" and getattr(self.obj, "img_bazos", None):
        slides.append({
            "src": self.obj.img_bazos,
            "is_preview": True,
        })
        return slides

    # Telegram / пользовательские изображения
    preview_src = self._resolve_image_src(getattr(self.obj, "preview_image", None))
    if preview_src:
        slides.append({
            "src": preview_src,
            "is_preview": True,
        })

    for image in self.obj.images.all():
        image_src = self._resolve_image_src(getattr(image, "image", None))
        if image_src:
            slides.append({
                "src": image_src,
                "is_preview": False,
            })

    if not slides:
        slides.append({
            "src": "/static/ads/images/stub.png",
            "is_preview": False,
            "is_stub": True,
        })

    return slides

def apply_common_filters(queryset, params):
    city = params.get('city')
    verified = params.get('verified')
    source = params.get('source')

    if city:
        queryset = queryset.filter(city__icontains=city)

    if verified == '1':
        queryset = queryset.filter(author__verification_status='1')

    if source:
        queryset = queryset.filter(source=source)

    return queryset

class BaseListMixin:
    paginate_by = 24

    def paginate_queryset(self, queryset):
        paginator = Paginator(queryset, self.paginate_by)
        page_number = self.request.GET.get("page")
        return paginator.get_page(page_number)

    def apply_sorting(self, queryset, sort, order, field_map):
        if sort in field_map:
            field = field_map[sort]
            return queryset.order_by(field if order == "asc" else f"-{field}")
        return queryset

class BaseAdsList(BaseListMixin, TemplateView):
    model = None
    template_name = None
    case_type_map = {}
    sort_map = {
        "date": "created_at",
        "price": "price",
    }
    filters = {}
    paginate_by = 24

    # Какие поля точно нужны в списке
    # На время оптимизации лучше оставить None.
    # only() часто вызывает скрытые догрузки полей.
    list_only_fields = None

    def get_base_queryset(self):
        params = self.request.GET
        slug = self.kwargs.get("slug", "all")

        if slug in self.case_type_map:
            case_type = self.case_type_map[slug]
            queryset = (
                self.model.objects.filter(caseType=case_type)
                if case_type is not None
                else self.model.objects.all()
            )
        else:
            queryset = self.model.objects.all()

        # ВАЖНО: только после if/else выше
        queryset = queryset.exclude(tg_deleted=True)

        if not self.request.user.is_staff:
            queryset = queryset.filter(status="active")

        queryset = apply_common_filters(queryset, params)

        for key, field in getattr(self, "filters", {}).items():
            value = params.get(key)
            if value not in (None, ""):
                queryset = queryset.filter(**{field: value})

        if self.list_only_fields:
            queryset = queryset.only(*self.list_only_fields)

        return queryset


    def get_queryset(self):
        qs = (
            self.get_base_queryset()
            .filter(status='active')
            .select_related(
                'category',
                'user',
            )
            .prefetch_related(
                Prefetch(
                    'images',
                    queryset=ThingsPostImage.objects.order_by('id'),
                    to_attr='prefetched_images'
                )
            )
        )

        search = self.request.GET.get('search', '').strip()
        if search:
            qs = search_things_queryset(qs, search)

        return qs

    def get_content_type_id(self):
        """
        Берём только id ContentType.
        """
        return ContentType.objects.get_for_model(self.model).id

    def get_active_top_ids(self):
        """
        Вместо annotate(is_top=Exists(...)) на каждую строку
        получаем список top object_id отдельным запросом.
        Это обычно дешевле, чем correlated subquery по всему queryset.
        """
        now = timezone.now()
        ct_id = self.get_content_type_id()

        return list(
            TopPromotion.objects.filter(
                content_type_id=ct_id,
                is_paid=True,
                is_active=True,
                starts_at__lte=now,
                ends_at__gte=now,
            ).values_list("object_id", flat=True)
        )

    def with_image_priority_annotation(self, queryset):
        rel = self.model._meta.get_field("images")
        image_model = rel.related_model
        fk_name = rel.field.name

        uploaded_images = image_model.objects.filter(**{fk_name: OuterRef("pk")})

        return queryset.annotate(
            has_any_image=Case(
                When(
                    Exists(uploaded_images),
                    then=Value(1),
                ),
                When(
                    has_photo=True,
                    then=Value(1),
                ),
                When(
                    Q(img_bazos__isnull=False) &
                    ~Q(img_bazos=""),
                    then=Value(1),
                ),
                default=Value(0),
                output_field=IntegerField(),
            )
        )

    def apply_default_ordering(self, queryset):
        queryset = self.with_image_priority_annotation(queryset)
        return queryset.order_by("-has_any_image", "-created_at", "-id")


    def apply_user_sorting(self, queryset, sort, order):
        queryset = self.with_image_priority_annotation(queryset)
        sort_field = self.sort_map[sort]

        if sort in ["price", "salary", "budget"]:
            if order == "asc":
                return queryset.order_by(
                    "-has_any_image",
                    F(sort_field).asc(nulls_last=True),
                    "id",
                )

            return queryset.order_by(
                "-has_any_image",
                F(sort_field).desc(nulls_last=True),
                "-id",
            )

        if order == "asc":
            return queryset.order_by("-has_any_image", sort_field, "id")

        return queryset.order_by("-has_any_image", f"-{sort_field}", "-id")

    def get_active_banners(self):
        now = timezone.now()
        return advertisingBanner.objects.filter(
            status='active'
        ).filter(
            Q(start_at__isnull=True) | Q(start_at__lte=now)
        ).filter(
            Q(end_at__isnull=True) | Q(end_at__gte=now)
        )

    def get_banners_for_page(self, request):
        banners = list(self.get_active_banners())
        if not banners:
            return []

        if len(banners) <= 2:
            advertisingBanner.objects.filter(
                id__in=[b.id for b in banners]
            ).update(impressions_count=F('impressions_count') + 1)
            return banners

        # вес обратно пропорционален числу показов:
        # чем меньше показов — тем выше шанс быть выбранным
        weights = [1 / (b.impressions_count + 1) for b in banners]

        chosen = []
        pool = banners[:]
        pool_weights = weights[:]

        for _ in range(min(2, len(pool))):
            picked = random.choices(pool, weights=pool_weights, k=1)[0]
            chosen.append(picked)
            idx = pool.index(picked)
            pool.pop(idx)
            pool_weights.pop(idx)

        advertisingBanner.objects.filter(
            id__in=[b.id for b in chosen]
        ).update(impressions_count=F('impressions_count') + 1)

        return chosen

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        params = self.request.GET
        slug = self.kwargs.get("slug", "all")
        sort = params.get("sort")
        order = params.get("order", "desc")
        search = params.get("search", "").strip()
        page = params.get("page")

        # определяем нужен ли noindex
        noindex = bool(
            search or
            sort or
            (page and page != "1")
        )

        queryset = self.get_queryset()

        if sort in self.sort_map:
            queryset = self.apply_user_sorting(queryset, sort, order)
        else:
            queryset = self.apply_default_ordering(queryset)

        page_obj = self.paginate_queryset(queryset)

        for obj in page_obj.object_list:
            prefetched = getattr(obj, "prefetched_images", None)
            obj.first_image = prefetched[0] if prefetched else None

        count = page_obj.paginator.count
        current = page_obj.number
        today = timezone.now().date()
        total = page_obj.paginator.num_pages

        start = max(current - 2, 1)
        end = min(current + 2, total)

        page_numbers = range(start, end + 1)

        context.update(
            {
                "base": page_obj,
                "count": count,
                "today": today,
                "page_obj": page_obj,
                "current_sort": sort,
                "current_order": order,
                "type_slug": slug,
                "slug": slug,
                "page_numbers": page_numbers,
                "noindex": noindex,  # ← добавили эту строку
                "admin_categories": Category.objects.filter(
                    is_active=True
                ),
                "advertising_banners": self.get_banners_for_page(self.request),

                **self.get_additional_context(params),
            }
        )

        return context

    def get_additional_context(self, params):
        return {}

# ===================== THINGS =====================

class things(BaseAdsList):
    template_name = 'ads/things.html'
    model = ThingsPost

    case_type_map = {
        'all': None,
        'sell': 'sell_category',
        'buy': 'buy_category',
    }

    sort_map = {
        'date': 'created_at',
        'price': 'price',
    }

    filters = {
        'price_from': 'price__gte',
        'price_to': 'price__lte',
        'category': 'category__slug',
        'condition': 'condition',
    }

    list_only_fields = [
        'id',
        'title',
        'slug_title',
        'created_at',
        'price',
        'city',
        'has_photo',
        'user',
        'category',
        'private_status',
        'source',
        'preview_image',
        'status',
    ]

    def get_queryset(self):
        qs = (
            self.get_base_queryset()
            .select_related(
                'category',
            )
            .prefetch_related(
                Prefetch(
                    'images',
                    queryset=ThingsPostImage.objects.order_by('id'),
                    to_attr='prefetched_images'
                )
            )
        )

        search = self.request.GET.get('search', '').strip()
        if search:
            qs = search_things_queryset(qs, search)

        return qs

    def get_additional_context(self, params):
        filter_category = params.get('category', '')

        categories = cache.get("things_categories")

        if categories is None:
            categories = list(
                Category.objects.filter(
                    is_active=True,
                    things__status=StatusAdv.ACTIVE,
                    things__tg_deleted=False,
                ).distinct()
            )
            cache.set("things_categories", categories, 600)

        return {
            'cities': ThingsPost.objects.values_list('city', flat=True).distinct(),

            'categories': categories,

            'filter_city': params.get('city', ''),
            'filter_search': params.get('search', ''),
            'filter_verified': params.get('verified', ''),
            'filter_price_from': params.get('price_from', ''),
            'filter_price_to': params.get('price_to', ''),

            'filter_category': filter_category,

            'filter_condition': params.get('condition', ''),
            'source': params.get('source', ''),
            'form': NotificationThingsForm,
        }

# ===================== JOBS =====================
class neighbors(BaseAdsList):
    template_name = 'ads/neighbors.html'
    model = NeighborPost

    case_type_map = {
        'all': None,
        'findNeighbor': 'findNeighbor',
        'rent': 'rent',
    }

    sort_map = {
        'date': 'created_at',
        'budget': 'budget',
    }

    filters = {
        'budget_from': 'budget__gte',
        'budget_to': 'budget__lte',
        'neighbor_gender': 'neighbor_gender',
        'housing_type': 'housing_type',
        'rent_period': 'rent_period',
        'rooms': 'rooms',
    }

    list_only_fields = [
        'id',
        'title',
        'slug_title',
        'created_at',
        'budget',
        'city',
        'has_photo',
        'user',
        'private_status',
        'source',
        'preview_image',
        'status',
        'neighbor_gender',
        'housing_type',
        'rent_period',
    ]

    def get_queryset(self):
        qs = (
            self.get_base_queryset()
            .select_related(
                'user',
            )
            .prefetch_related(
                Prefetch(
                    'images',
                    queryset=NeighborPostImage.objects.order_by('id'),
                    to_attr='prefetched_images'
                )
            )
        )

        search = self.request.GET.get('search', '').strip()
        if search:
            qs = search_neighbors_queryset(qs, search)

        return qs


    def get_additional_context(self, params):
        return {
            'cities': NeighborPost.objects.values_list('city', flat=True).distinct(),
            'rent_periods': RentPeriod.choices,
            'housing_types': HousingType.choices,
            'genders': Gender.choices,
            'filter_city': params.get('city', ''),
            'filter_search': params.get('search', ''),
            'filter_verified': params.get('verified', ''),
            'filter_budget_from': params.get('budget_from', ''),
            'filter_budget_to': params.get('budget_to', ''),
            'filter_neighbor_gender': params.get('neighbor_gender', ''),
            'filter_housing_type': params.get('housing_type', ''),
            'filter_rent_period': params.get('rent_period', ''),
            'source': params.get('source', ''),
            'form': NotificationNeighborForm,
        }

#class jobs(BaseAdsList):
#    template_name = 'ads/jobs.html'
#    model = JobPost
#
#    case_type_map = {
#        'all': None,
#        'findJob': 'findJob',
#        'giveJob': 'giveJob',
#    }
#
#    sort_map = {
#        'date': 'created_at',
#        'salary': 'salary_to',
#    }
#
#    filters = {
#        'salary_from': 'salary_from__gte',
#        'salary_to': 'salary_to__lte',
#        'employment_type': 'employment_type',
#    }
#
#    list_only_fields = [
#        'id',
#        'title',
#        'slug_title',
#        'created_at',
#        'salary_from',
#        'salary_to',
#        'city',
#        'has_photo',
#        'user',
#        'private_status',
#        'source_telegram',
#        'preview_image',
#        'status',
#        'employment_type',
#    ]
#
#    def get_queryset(self):
#        qs = (
#            self.get_base_queryset()
#            .select_related(
#                'user',
#            )
#            .prefetch_related(
#                Prefetch(
#                    'images',
#                    queryset=JobPostImage.objects.order_by('id'),
#                    to_attr='JobPostImage'
#                )
#            )
#        )
#
#        search = self.request.GET.get('search', '').strip()
#        if search:
#            qs = search_jobs_queryset(qs, search)
#
#        return qs
#
#    def get_additional_context(self, params):
#        return {
#            'cities': JobPost.objects.values_list('city', flat=True).distinct(),
#            'employment_types': EmploymentType.choices,
#            'filter_city': params.get('city', ''),
#            'filter_search': params.get('search', ''),
#            'filter_verified': params.get('verified', ''),
#            'filter_salary_from': params.get('salary_from', ''),
#            'filter_salary_to': params.get('salary_to', ''),
#            'filter_employment_type': params.get('employment_type', ''),
#            'source_telegram': params.get('source_telegram', ''),
#        }

class BaseCreatePostView(CreateView):
    template_name = 'ads/create.html'
    section = None
    image_formset_class = None
    image_formset_prefix = 'images'

    post_case_map = {}
    section_map = {}
    
    def get_image_formset(self):
        if not self.image_formset_class:
            return None

        data = self.request.POST if self.request.method == 'POST' else None
        files = self.request.FILES if self.request.method == 'POST' else None

        return self.image_formset_class(
            data,
            files,
            instance=getattr(self, 'object', None),
            prefix=self.image_formset_prefix
        )

    def set_extra_fields_for_get(self):
        slug = self.kwargs.get('slug')
        self.section = self.section_map.get(slug, self.model.__name__.lower())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user

        if not getattr(self, 'object', None):
            self.object = None
            self.set_extra_fields_for_get()

        return kwargs

    def get_context_data(self, **kwargs):
        self.set_extra_fields_for_get()
        context = super().get_context_data(**kwargs)

        slug = self.kwargs.get("slug")

        if slug == "rent":
            context["formType"] = "rent"
        else:
            context["formType"] = self.formType

        context["formset"] = self.get_image_formset()
        context["slug"] = slug
        context["section"] = self.section
        context["is_auth"] = self.request.user.is_authenticated

        return context

    def set_extra_fields(self, form):
        slug = self.kwargs.get('slug')
        if slug in self.post_case_map:
            self.object.caseType = self.post_case_map[slug]
        self.section = self.section_map.get(slug, self.section)

    def check_daily_limit(self):
        today = timezone.now().date()
        limit = getattr(settings, 'DAILY_LIMITS', {}).get(self.model.__name__.lower(), 0)

        if limit == 0:
            return True

        qs = self.model.objects.filter(created_at__date=today)

        if self.request.user.is_authenticated:
            qs = qs.filter(user=self.request.user)
        else:
            ip = self.request.META.get('REMOTE_ADDR')
            qs = qs.filter(created_ip=ip)

        return qs.count() < limit

    def form_valid(self, form):
        print("POST CREATED")
        # if not self.check_daily_limit():
        #     messages.error(self.request, "Вы достигли лимита на сегодня.")
        #     return self.form_invalid(form)

        self.object = form.save(commit=False)
        self.object.created_ip = self.request.META.get('REMOTE_ADDR')
        self.object.source = 'pusto.sk'

        # AUTH
        if self.request.user.is_authenticated:
            self.object.user = self.request.user
            self.object.email = self.request.user.email

            self.set_extra_fields(form)
            self.object.status = StatusAdv.ACTIVE
            self.object.email_confirmed = True
            self.object.email_token = None
            self.object.save()

            formset = self.get_image_formset()
            if formset:
                if formset.is_valid():
                    formset.instance = self.object
                    formset.save()
                else:
                    return self.render_to_response(
                        self.get_context_data(form=form, formset=formset)
                    )

            messages.success(self.request, "Объявление опубликовано!")
            return redirect(self.get_success_url())
        else:
            # ANON
            if not self.object.email:
                form.add_error('email', 'Email обязателен для публикации объявления.')
                return self.form_invalid(form)

            self.set_extra_fields(form)
            self.object.status = StatusAdv.PENDING

            self.object.email_confirmed = False
            self.object.email_token = str(uuid.uuid4())
            self.object.withoutRegister = True
            self.object.save()


            formset = self.get_image_formset()
            if formset:
                if formset.is_valid():
                    formset.instance = self.object
                    formset.save()
                else:
                    return self.render_to_response(
                        self.get_context_data(form=form, formset=formset)
                    )

            verify_url = self.request.build_absolute_uri(
                reverse('ads:verify_post_email', args=[self.object.email_token])
            )

            send_mail(
                'Подтвердите Email для публикации объявления',
                f'Перейдите по ссылке, чтобы опубликовать объявление: {verify_url}',
                settings.DEFAULT_FROM_EMAIL,
                [self.object.email],
                fail_silently=False,
            )

            return render(
                self.request,
                'accounts/email_verified_adv.html',

            )

class ThingsCreateView(BaseCreatePostView):
    model = ThingsPost
    form_class = ThingsPostForm
    image_formset_class = ThingsPostImageFormSet
    success_url = '/things/all/'
    formType = 'things'

    post_case_map = {
        'sell': CaseTypeThing.SELL,
        'buy': CaseTypeThing.BUY,
    }
    section_map = {
        'sell': 'sell',
        'buy': 'buy',
    }

class JobCreateView(BaseCreatePostView):
    model = JobPost
    form_class = JobPostForm
    image_formset_class = JobPostImageFormSet
    success_url = '/jobs/all/'
    formType = 'jobs'

    post_case_map = {
        'findJob': CaseTypeJob.FIND,
        'giveJob': CaseTypeJob.GIVE,
    }
    section_map = {
        'findJob': 'findJob',
        'giveJob': 'giveJob',
    }

class NeighborCreateView(BaseCreatePostView):
    model = NeighborPost
    form_class = NeighborPostForm
    image_formset_class = NeighborPostImageFormSet
    success_url = '/neighbors/all/'
    formType = 'neighbors'

    post_case_map = {
        'findNeighbor': CaseTypeNeighbor.FIND_ROOMMATE,
        'rent': CaseTypeNeighbor.RENT,
    }
    section_map = {
        'findNeighbor': 'findNeighbor',
        'rent': 'rent',
    }


from django.conf import settings

class page(TemplateView):
    template_name = "ads/page.html"

    MODEL_MAP = {
        "things": ThingsPost,
        "jobs": JobPost,
        "neighbors": NeighborPost,
    }

    def dispatch(self, request, *args, **kwargs):
        self.section = kwargs.get("section")
        self.title = kwargs.get("title")
        self.post_id = kwargs.get("id")

        model = self.MODEL_MAP.get(self.section)
        if not model:
            raise Http404("Unknown section")

        self.obj = get_object_or_404(
            model.objects.prefetch_related("images"),
            id=self.post_id,
        )

        if self.title != self.obj.slug_title:
            return redirect(
                "ads:page",
                self.section,
                self.obj.slug_title,
                self.obj.id,
                permanent=True,
            )

        return super().dispatch(request, *args, **kwargs)

    def _resolve_image_src(self, value):
        if not value:
            return None

        try:
            return value.url
        except AttributeError:
            pass

        value = str(value).strip()
        if not value:
            return None

        if value.startswith(("http://", "https://", "/")):
            return value

        return f"{settings.MEDIA_URL.rstrip('/')}/{value.lstrip('/')}"

    def _get_remote_photos(self, folder, max_photos=5):
        """Проверяет по HEAD-запросу, сколько фото реально существует."""
        slides = []
        for i in range(1, max_photos + 1):
            url = f'https://pusto.sk/photos/{folder}/{self.obj.ad_id}/{i}.jpg'
            try:
                resp = requests.head(url, timeout=2)
            except requests.RequestException:
                break
            if resp.status_code != 200:
                break
            slides.append({"src": url})
        return slides

    def get_slider_images(self):
        slides = []
        source = getattr(self.obj, "source", None)

        if source == "reality.sk":
            slides.extend(self._get_remote_photos("reality"))

        elif source == "topreality":
            slides.extend(self._get_remote_photos("topreality"))
        elif source == 'telegram':
            for i in range(1, 4):
                url = f'https://pusto.sk/media/telegram_previews/{self.obj.chat_id}_{self.obj.message_id}/{i}.jpg'
                try:
                    resp = requests.head(url, timeout=2)
                except requests.RequestException:
                    break
                if resp.status_code != 200:
                    break
                slides.append({"src": url})
        elif source == "bazos" and getattr(self.obj, "img_bazos", None):
            slides.append({
                "src": self.obj.img_bazos,
                "is_preview": True,
            })
            return slides

        if slides:
            return slides

        # Telegram / пользовательские изображения
        preview_src = self._resolve_image_src(getattr(self.obj, "preview_image", None))
        if preview_src:
            slides.append({
                "src": preview_src,
                "is_preview": True,
            })

        for image in self.obj.images.all():
            image_src = self._resolve_image_src(getattr(image, "image", None))
            if image_src:
                slides.append({
                    "src": image_src,
                    "is_preview": False,
                })

        if not slides:
            slides.append({
                "src": "/static/ads/images/stub.png",
                "is_preview": False,
                "is_stub": True,
            })

        return slides

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        chat_id = getattr(self.obj, "chat_id", None)
        chat_invite_link = chat_invite.get(str(chat_id)) if chat_id else None

        context.update({
            "obj": self.obj,
            "slug": self.section,
            "claim_app_label": self.obj._meta.app_label,
            "claim_model_name": self.obj._meta.model_name,
            "slider_images": self.get_slider_images(),
            "chat_invite_link": chat_invite_link,
        })

        return context

def typeThings(request):
    return render(request, 'ads/typeThings.html')

def typeJob(request):
    return render(request, 'ads/typeJob.html')

def relog(request):
    return render(request, 'pusto/relog.html')

def verify_post_email(request, token):
    token = str(token).strip()
    post = ThingsPost.objects.filter(email_token=token).first()
    if not post:
        post = JobPost.objects.filter(email_token=token).first()
    if not post:
        post = NeighborPost.objects.filter(email_token=token).first()

    if not post:
        return render(
            request,
            'accounts/email_verified.html',
            {'msg': 'Ссылка недействительна или устарела.'},
            status=404
        )

    post.email_confirmed = True
    post.status = StatusAdv.ACTIVE
    post.email_token = None  # одноразовая ссылка
    post.save(update_fields=['email_confirmed', 'status', 'email_token'])

    section = "things" if isinstance(post, ThingsPost) else "jobs" if isinstance(post, JobPost) else "neighbors"
    return redirect('ads:page', section, post.slug_title, post.id)
@require_POST
def resend_post_verification(request):
    post_id = request.POST.get('post_id')
    post_type = request.POST.get('post_type')  # "things" / "jobs" / "neighbors"

    MODEL_MAP = {
        "things": ThingsPost,
        "jobs": JobPost,
        "neighbors": NeighborPost,
    }

    model = MODEL_MAP.get(post_type)
    if not model:
        return redirect('ads:select')

    post = model.objects.filter(id=post_id).first()

    # если не найден или уже активен — ничего не делаем
    if not post or post.status == StatusAdv.ACTIVE:
        return redirect('ads:select')

    # если токена нет — создаём новый (строкой)
    if not post.email_token:
        post.email_token = str(uuid.uuid4())
        post.save(update_fields=['email_token'])

    verify_url = request.build_absolute_uri(
        reverse('ads:verify_post_email', args=[str(post.email_token).strip()])

    )

    send_mail(
        'Подтвердите Email для публикации объявления',
        f'Перейдите по ссылке, чтобы опубликовать объявление: {verify_url}',
        settings.DEFAULT_FROM_EMAIL,
        [post.email],
        fail_silently=False,
    )

    return render(
        request,
        'accounts/email_verified.html',
        {'msg': 'Письмо отправлено повторно. Проверьте почту.'}
    )



def send_message(request, post_id):
    if request.method != "POST":
        return redirect("/")

    obj = get_object_or_404(ThingsPost, id=post_id)

    if request.user.is_authenticated:
        sender_email = request.user.email
    else:
        sender_email = request.POST.get("email", "").strip()

    message = request.POST.get("message", "").strip()

    # нет владельца у объявления

    # у владельца нет email
    if not obj.email:
        messages.error(request, "У власника оголошення немає email для зв’язку.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    # у гостя не введён email
    if not sender_email:
        messages.error(request, "Вкажіть ваш email.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    # пустое сообщение
    if not message:
        messages.error(request, "Введіть повідомлення.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    send_mail(
        subject=f"Message about: {obj.title}",
        message=f"Від: {sender_email}\n\n{message}",
        from_email=None,
        recipient_list=[obj.email],
    )

    messages.success(request, "Повідомлення відправлено.")
    return redirect(request.META.get("HTTP_REFERER", "/"))

# documents

def privacy(request):
    return render(request, 'pusto/privacy.html')

def terms(request):
    return render(request, 'pusto/terms.html')

def cookies(request):
    return render(request, 'pusto/cookies.html')

def impressum(request):
    return render(request, 'pusto/impressum.html')

def community(request):
    return render(request, 'pusto/community.html')

def paid_features(request):
    return render(request, 'pusto/paid_features.html')

def takedown(request):
    return render(request, 'pusto/takedown.html')

MODEL_MAP = {
    "things": ThingsPost,
    "jobs": JobPost,
    "neighbors": NeighborPost,
}

@method_decorator(staff_member_required, name='dispatch')
class UpdateAdStatusView(View):
    def post(self, request, ad_type, pk):
        print("STATUS UPDATE HIT:", ad_type, pk, request.body)

        data = json.loads(request.body)
        status = data.get("status")

        print("NEW STATUS:", status)

        if status not in ["active", "closed"]:
            return JsonResponse({"error": "Invalid status"}, status=400)

        model = MODEL_MAP.get(ad_type)
        if not model:
            return JsonResponse({"error": "Invalid type"}, status=400)

        obj = model.objects.filter(pk=pk).first()
        if not obj:
            return JsonResponse({"error": "Not found"}, status=404)

        obj.status = status
        obj.save(update_fields=["status"])

        return JsonResponse({
            "success": True,
            "id": obj.id,
            "status": obj.status,
        })

STOP_WORDS = [
    "prodam", "prodaju", "prodat",
    "kuplju", "kupit",
    "srochno",
    "novyi", "novaya", "novoe",
    "bu", "b-u", "used",
]


def similar(request, section, slug):
    # разбиваем slug
    words = slug.lower().split("-")

    # убираем стоп-слова
    words = [w for w in words if w not in STOP_WORDS]

    # ограничиваем длину
    words = words[:3]

    # собираем обратно
    query = " ".join(words)

    # fallback если всё удалилось
    if not query:
        query = slug.replace("-", " ")

    url = f"/{section}/?search={quote(query)}&section={section}"

    return redirect(url)

def banner_click(request, banner_id):
    banner = get_object_or_404(advertisingBanner, id=banner_id)
    advertisingBanner.objects.filter(id=banner.id).update(
        clicks_count=F('clicks_count') + 1
    )
    return redirect(banner.url)