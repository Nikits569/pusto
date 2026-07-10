import json
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from ads.models import ThingsPost, NeighborPost, JobPost
from django.views.decorators.csrf import ensure_csrf_cookie

@ensure_csrf_cookie
def favorites(request):
    return render(request, "interactions/favorites.html")


@require_POST
def resolve_favorites(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "bad_json"}, status=400)

    ids_by_type = payload.get("items", {})
    if not isinstance(ids_by_type, dict):
        return JsonResponse({"ok": False, "error": "bad_items"}, status=400)

    def preview_image_path_for(post):
        try:
            preview_image = getattr(post, "preview_image", None)
            if preview_image:
                return str(preview_image)
        except Exception:
            pass
        return None

    def first_image_url_for(post):
        try:
            images_rel = getattr(post, "images", None)
            if images_rel is not None:
                first = images_rel.first()
                if first and getattr(first, "image", None):
                    return first.image.url
        except Exception:
            pass
        return None

    def page_url_for(ctype, post):
        kind = {
            "ThingsPost": "things",
            "NeighborPost": "neighbors",
            "JobPost": "jobs",
        }[ctype]
        return reverse("ads:page", args=[kind, post.slug_title, post.id])

    def format_created_at(post):
        created = getattr(post, "created_at", None)
        if not created:
            return ""
        try:
            return created.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return str(created)

    def get_price_data(ctype, post):
        if ctype == "ThingsPost":
            value = getattr(post, "price", None)
            return {
                "price": value,
                "budget": None,
                "salary_from": None,
                "salary_to": None,
            }

        if ctype == "NeighborPost":
            value = getattr(post, "budget", None)
            return {
                "price": None,
                "budget": value,
                "salary_from": None,
                "salary_to": None,
            }

        if ctype == "JobPost":
            return {
                "price": None,
                "budget": None,
                "salary_from": getattr(post, "salary_from", None),
                "salary_to": getattr(post, "salary_to", None),
            }

        return {
            "price": None,
            "budget": None,
            "salary_from": None,
            "salary_to": None,
        }

    def get_user_badges(post):
        user = getattr(post, "user", None)
        if not user:
            return {
                "verification_user": False,
                "verification_student": False,
                "verification_employer": False,
            }

        return {
            "verification_user": bool(getattr(user, "verification_user", False)),
            "verification_student": bool(getattr(user, "verification_student", False)),
            "verification_employer": bool(getattr(user, "verification_employer", False)),
        }

    def get_cards(ctype, model, ids):
        normalized_ids = []
        for i in ids:
            try:
                normalized_ids.append(int(i))
            except (TypeError, ValueError):
                continue

        ids = normalized_ids[:200]
        if not ids:
            return []

        qs = (
            model.objects
            .select_related("user")
            .filter(id__in=ids)
        )

        cards = []
        for o in qs:
            price_data = get_price_data(ctype, o)

            cards.append({
                "id": o.id,
                "slug": getattr(o, "slug_title", ""),
                "title": getattr(o, "text", "") or getattr(o, "title", ""),
                "text": getattr(o, "text", "") or getattr(o, "title", ""),
                "preview_image_path": preview_image_path_for(o),
                "first_image_url": first_image_url_for(o),
                "page_url": page_url_for(ctype, o),
                "city": getattr(o, "city", ""),
                "created_at": format_created_at(o),
                "source_telegram": bool(getattr(o, "source_telegram", False)),
                "user": get_user_badges(o),
                "price": price_data["price"],
                "budget": price_data["budget"],
                "salary_from": price_data["salary_from"],
                "salary_to": price_data["salary_to"],
            })

        order = {oid: idx for idx, oid in enumerate(ids)}
        cards.sort(key=lambda x: order.get(x["id"], 10**9))
        return cards

    try:
        out = {
            "ThingsPost": get_cards("ThingsPost", ThingsPost, ids_by_type.get("ThingsPost", [])),
            "NeighborPost": get_cards("NeighborPost", NeighborPost, ids_by_type.get("NeighborPost", [])),
            "JobPost": get_cards("JobPost", JobPost, ids_by_type.get("JobPost", [])),
        }
        return JsonResponse({"ok": True, "data": out})
    except Exception as e:
        print("[favorites] resolve_favorites fatal error:", e)
        return JsonResponse({"ok": False, "error": "server_error"}, status=500)

def promotion(request):
    return render(request, "interactions/promotion.html")