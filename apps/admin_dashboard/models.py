import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class PlatformAccount(models.Model):
    TYPES = (
        ("commission", "commission"),
        ("reserve_fund", "reserve_fund"),
        ("investment_pool", "investment_pool"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=30, choices=TYPES, unique=True)
    balance = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"PlatformAccount<{self.type}={self.balance}>"

    @classmethod
    def get_or_create_account(cls, type_: str) -> "PlatformAccount":
        obj, _ = cls.objects.get_or_create(type=type_)
        return obj
