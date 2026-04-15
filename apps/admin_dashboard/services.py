from decimal import Decimal

from django.db import transaction
from django.db.models import F

from .models import PlatformAccount


class PlatformAccountError(Exception):
    pass


class PlatformAccountService:
    @staticmethod
    @transaction.atomic
    def credit(type_: str, amount: Decimal) -> PlatformAccount:
        if amount <= 0:
            raise PlatformAccountError("Montant invalide")
        acc = PlatformAccount.objects.select_for_update().filter(type=type_).first()
        if acc is None:
            acc = PlatformAccount.objects.create(type=type_, balance=Decimal("0"))
            acc = PlatformAccount.objects.select_for_update().get(pk=acc.pk)
        acc.balance = F("balance") + amount
        acc.save(update_fields=["balance", "updated_at"])
        acc.refresh_from_db()
        return acc

    @staticmethod
    @transaction.atomic
    def debit(type_: str, amount: Decimal) -> PlatformAccount:
        if amount <= 0:
            raise PlatformAccountError("Montant invalide")
        acc = PlatformAccount.objects.select_for_update().filter(type=type_).first()
        if acc is None or acc.balance < amount:
            raise PlatformAccountError("Solde plateforme insuffisant")
        acc.balance = F("balance") - amount
        acc.save(update_fields=["balance", "updated_at"])
        acc.refresh_from_db()
        return acc
