import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Tontine(models.Model):
    STATUSES = (
        ("recruiting", "recruiting"),
        ("active", "active"),
        ("completed", "completed"),
        ("cancelled", "cancelled"),
    )
    FREQUENCIES = (("weekly", "weekly"), ("biweekly", "biweekly"), ("monthly", "monthly"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tontines_created",
    )
    contribution_amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("500"))],
    )
    frequency = models.CharField(max_length=20, choices=FREQUENCIES)
    max_members = models.IntegerField(validators=[MinValueValidator(2), MaxValueValidator(50)])
    current_round = models.IntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUSES, default="recruiting")
    requires_guarantor = models.BooleanField(default=True)
    start_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return f"Tontine<{self.name} {self.status}>"

    @property
    def pot(self) -> Decimal:
        return self.contribution_amount * self.max_members

    @property
    def commission(self) -> Decimal:
        rate = Decimal(str(settings.DJANGUI["TONTINE_COMMISSION_RATE"]))
        return (self.pot * rate).quantize(Decimal("0.01"))

    @property
    def net_payout(self) -> Decimal:
        return self.pot - self.commission


class TontineMembership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tontine = models.ForeignKey(Tontine, on_delete=models.CASCADE, related_name="memberships")
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="tontine_memberships",
    )
    guarantor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="tontine_guarantees", null=True, blank=True,
    )
    position = models.IntegerField()
    has_received_pot = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("tontine", "member"), name="unique_tontine_member"),
            models.UniqueConstraint(fields=("tontine", "position"), name="unique_tontine_position"),
        ]


class TontineContribution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tontine = models.ForeignKey(Tontine, on_delete=models.CASCADE, related_name="contributions")
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="tontine_contributions",
    )
    round_number = models.IntegerField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    transaction = models.ForeignKey(
        "transactions.Transaction", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="tontine_contributions",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("tontine", "member", "round_number"),
                name="unique_tontine_member_round",
            ),
        ]
        indexes = [models.Index(fields=["tontine", "round_number"])]
