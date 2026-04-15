import uuid

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models


class HonorBoard(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="honor_entries",
    )
    period = models.CharField(
        max_length=7,
        validators=[RegexValidator(r"^\d{4}-\d{2}$", "format YYYY-MM")],
    )
    score = models.IntegerField(default=0)
    rank = models.IntegerField(default=0)
    is_visible = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("user", "period"), name="unique_honor_user_period"),
        ]
        indexes = [models.Index(fields=["period", "rank"])]


class Partner(models.Model):
    TYPES = (
        ("bayam_sellam", "bayam_sellam"),
        ("market", "market"),
        ("training", "training"),
        ("lottery", "lottery"),
        ("other", "other"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=30, choices=TYPES)
    discount_description = models.TextField()
    tchekele_cost = models.IntegerField()
    is_active = models.BooleanField(default=True)
    contact_phone = models.CharField(max_length=15, null=True, blank=True)
    city = models.CharField(max_length=100)


class TchekeleRedemption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tchekele_redemptions",
    )
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT, related_name="redemptions")
    points_spent = models.IntegerField()
    code = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)
