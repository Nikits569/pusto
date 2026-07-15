import datetime

from django.utils import timezone

from ads.models import ThingsPost, JobPost, NeighborPost, PrivateStatus

POST_MODEL_MAP = {
    "things": ThingsPost,
    "job": JobPost,
    "neighbor": NeighborPost,
}


def apply_promotion(order) -> bool:
    """
    Поднимает объявление после подтверждённой оплаты (любым способом).
    Возвращает True, если что-то реально применили.
    """
    if not order.post_type or not order.post_id:
        return False

    PostModel = POST_MODEL_MAP.get(order.post_type)
    if PostModel is None:
        return False

    post = PostModel.objects.filter(id=order.post_id).first()
    if post is None:
        return False

    duration = order.duration_days or 0
    post.private_status = PrivateStatus.TOP
    post.promoted_until = timezone.now() + datetime.timedelta(days=duration)
    post.save(update_fields=["private_status", "promoted_until"])
    return True