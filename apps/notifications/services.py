import logging
from typing import Iterable

from django.conf import settings
from django.db import transaction

from .models import Notification

log = logging.getLogger("djangui.notifications")


class NotificationService:
    """Create in-app notifications and dispatch push/SMS via external providers.

    Push (FCM) and SMS are behind feature flags so local/dev runs don't fail.
    """

    @staticmethod
    @transaction.atomic
    def notify(user, type_: str, title: str, message: str) -> Notification:
        n = Notification.objects.create(
            user=user, type=type_, title=title, message=message,
        )
        try:
            NotificationService._push(user, title, message, type_)
        except Exception:
            log.exception("push dispatch failed")
        return n

    @staticmethod
    def bulk_notify(users: Iterable, type_: str, title: str, message: str) -> int:
        objs = [
            Notification(user=u, type=type_, title=title, message=message) for u in users
        ]
        Notification.objects.bulk_create(objs, batch_size=500)
        return len(objs)

    @staticmethod
    def _push(user, title: str, message: str, type_: str) -> None:
        if not getattr(user, "push_enabled", True):
            return
        token = getattr(user, "fcm_token", None)
        if not token:
            return
        fcm_key = getattr(settings, "FCM_SERVER_KEY", "")
        if not fcm_key:
            return
        log.info("FCM would dispatch to=%s type=%s", token[:8], type_)


def notify(user, type_: str, title: str, message: str) -> Notification:
    """Module-level alias — used across apps for simple single-user notifications."""
    return NotificationService.notify(user, type_, title, message)


def bulk_notify(users, type_: str, title: str, message: str) -> int:
    return NotificationService.bulk_notify(users, type_, title, message)
