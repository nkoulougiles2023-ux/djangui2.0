import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Investment(models.Model):
    STATUSES = (
        ("active", "active"),
        ("pending_withdrawal", "pending_withdrawal"),
        ("withdrawn", "withdrawn"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    investor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="investments",
    )
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("5000"))],
    )
    status = models.CharField(max_length=20, choices=STATUSES, default="active")
    return_rate = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("3.00"))
    total_returns_earned = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    invested_at = models.DateTimeField(auto_now_add=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    withdrawal_requested_at = models.DateTimeField(null=True, blank=True)
    notice_period_days = models.IntegerField(default=7)

    class Meta:
        indexes = [models.Index(fields=["investor", "status"])]
