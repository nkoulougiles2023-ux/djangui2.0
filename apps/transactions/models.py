import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Transaction(models.Model):
    TYPES = (
        ("deposit", "deposit"),
        ("withdrawal", "withdrawal"),
        ("loan_disbursement", "loan_disbursement"),
        ("loan_repayment", "loan_repayment"),
        ("guarantee_block", "guarantee_block"),
        ("guarantee_release", "guarantee_release"),
        ("guarantee_seize", "guarantee_seize"),
        ("commission_platform", "commission_platform"),
        ("commission_guarantor", "commission_guarantor"),
        ("commission_investor", "commission_investor"),
        ("tontine_contribution", "tontine_contribution"),
        ("tontine_payout", "tontine_payout"),
        ("investment_deposit", "investment_deposit"),
        ("investment_withdrawal", "investment_withdrawal"),
        ("investment_return", "investment_return"),
        ("tchekele_reward", "tchekele_reward"),
    )
    STATUSES = (("pending", "pending"), ("completed", "completed"), ("failed", "failed"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=30, choices=TYPES)
    amount = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="transactions_sent",
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="transactions_received",
    )
    loan = models.ForeignKey(
        "loans.Loan", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="transactions",
    )
    tontine = models.ForeignKey(
        "tontines.Tontine", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="transactions",
    )
    status = models.CharField(max_length=20, choices=STATUSES, default="pending")
    payment_reference = models.CharField(max_length=100, null=True, blank=True)
    idempotency_key = models.CharField(max_length=64, unique=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["sender", "created_at"]),
            models.Index(fields=["receiver", "created_at"]),
            models.Index(fields=["idempotency_key"]),
            models.Index(fields=["type", "status"]),
        ]
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.type} {self.amount} [{self.status}]"

    def save(self, *args, **kwargs):
        # Transactions are immutable once persisted with completed/failed status.
        if self.pk:
            existing = Transaction.objects.filter(pk=self.pk).first()
            if existing and existing.status in ("completed", "failed"):
                raise RuntimeError("Transaction is immutable once finalized")
        super().save(*args, **kwargs)
