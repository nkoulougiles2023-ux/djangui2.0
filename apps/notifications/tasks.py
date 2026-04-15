import logging

from celery import shared_task

from .models import Notification
from .services import NotificationService

log = logging.getLogger("djangui.notifications")


@shared_task
def send_notification(user_id: str, type_: str, title: str, message: str) -> str:
    from apps.accounts.models import User

    u = User.objects.filter(pk=user_id).first()
    if not u:
        return "user_not_found"
    n = NotificationService.notify(u, type_, title, message)
    return str(n.id)


@shared_task
def purge_old_notifications(days: int = 90) -> int:
    from datetime import timedelta

    from django.utils import timezone

    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = Notification.objects.filter(
        is_read=True, created_at__lt=cutoff,
    ).delete()
    return deleted
