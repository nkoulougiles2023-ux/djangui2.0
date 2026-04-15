import uuid

from django.conf import settings
from django.db import models


class Notification(models.Model):
    TYPES = (
        ("loan_reminder", "loan_reminder"),
        ("loan_approved", "loan_approved"),
        ("loan_defaulted", "loan_defaulted"),
        ("guarantee_request", "guarantee_request"),
        ("guarantee_seized", "guarantee_seized"),
        ("tontine_turn", "tontine_turn"),
        ("tontine_reminder", "tontine_reminder"),
        ("tchekele_earned", "tchekele_earned"),
        ("system", "system"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    type = models.CharField(max_length=30, choices=TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["user", "-created_at"]),
        ]
        ordering = ("-created_at",)
