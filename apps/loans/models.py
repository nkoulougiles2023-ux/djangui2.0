import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Loan(models.Model):
    STATUSES = (
        ("waiting_guarantor", "waiting_guarantor"),
        ("waiting_validation", "waiting_validation"),
        ("active", "active"),
        ("repaid", "repaid"),
        ("defaulted", "defaulted"),
        ("cancelled", "cancelled"),
    )
    DURATIONS = (7, 14, 30, 60, 90)
    DURATION_CHOICES = tuple((d, f"{d} jours") for d in DURATIONS)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    borrower = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="loans_as_borrower",
    )
    amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("1000"))],
    )
    commission_rate = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("10.00"))
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    total_to_repay = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    duration_days = models.IntegerField(choices=DURATION_CHOICES)

    status = models.CharField(max_length=20, choices=STATUSES, default="waiting_guarantor")

    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    amount_repaid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    grace_period_hours = models.IntegerField(default=72)

    class Meta:
        indexes = [
            models.Index(fields=["borrower", "status"]),
            models.Index(fields=["status", "due_date"]),
            models.Index(fields=["status", "requested_at"]),
        ]
        ordering = ("-requested_at",)

    def __str__(self):
        return f"Loan<{self.borrower.phone} {self.amount}XAF {self.status}>"

    # --- computed helpers ------------------------------------------------

    def compute_totals(self):
        self.commission_amount = (self.amount * self.commission_rate / Decimal("100")).quantize(Decimal("0.01"))
        self.total_to_repay = self.amount + self.commission_amount
        return self

    @property
    def remaining(self) -> Decimal:
        return max(self.total_to_repay - self.amount_repaid, Decimal("0"))

    @property
    def coverage(self) -> Decimal:
        return self.guarantees.filter(status="blocked").aggregate(
            s=models.Sum("amount_blocked")
        )["s"] or Decimal("0")

    @property
    def grace_deadline(self):
        if not self.due_date:
            return None
        from datetime import timedelta
        return self.due_date + timedelta(hours=self.grace_period_hours)

    @property
    def is_in_grace(self) -> bool:
        if self.status != "active" or not self.due_date:
            return False
        now = timezone.now()
        return self.due_date < now <= self.grace_deadline


class Guarantee(models.Model):
    STATUSES = (("blocked", "blocked"), ("released", "released"), ("seized", "seized"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="guarantees")
    guarantor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="guarantees_given",
    )
    amount_blocked = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUSES, default="blocked")
    commission_earned = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    blocked_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["guarantor", "status"]),
            models.Index(fields=["loan", "status"]),
        ]
        # Rule "guarantor != loan.borrower" is enforced in
        # GuaranteeService.create_guarantee; a CheckConstraint cannot traverse FKs.


class LoanRepayment(models.Model):
    PAYMENT_METHODS = (
        ("wallet", "wallet"),
        ("mtn_momo", "mtn_momo"),
        ("orange_money", "orange_money"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="repayments")
    amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("100"))],
    )
    paid_at = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    transaction = models.OneToOneField(
        "transactions.Transaction", on_delete=models.PROTECT,
        related_name="repayment",
    )

    class Meta:
        indexes = [models.Index(fields=["loan", "paid_at"])]
