import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User, Wallet
from apps.admin_dashboard.models import PlatformAccount
from apps.transactions.services import InsufficientFunds, WalletService

from .models import Investment

log = logging.getLogger("djangui.investments")


class InvestmentError(Exception):
    pass


class InvestmentService:
    @staticmethod
    @transaction.atomic
    def deposit(user: User, amount: Decimal, *, idempotency_key: str) -> Investment:
        amount = Decimal(amount)
        if amount < settings.DJANGUI["INVESTMENT_MIN"]:
            raise InvestmentError(f"Minimum {settings.DJANGUI['INVESTMENT_MIN']} FCFA")
        if user.kyc_status != "verified":
            raise InvestmentError("KYC requis")
        try:
            WalletService.transfer(
                sender=user, receiver=None, amount=amount,
                kind="investment_deposit",
                idempotency_key=idempotency_key,
                description="Dépôt investissement",
            )
        except InsufficientFunds as exc:
            raise InvestmentError(str(exc))
        inv = Investment.objects.create(investor=user, amount=amount)
        pool, _ = PlatformAccount.objects.select_for_update().get_or_create(type="investment_pool")
        pool.balance += amount
        pool.save(update_fields=["balance", "updated_at"])
        return inv

    @staticmethod
    @transaction.atomic
    def request_withdrawal(inv: Investment) -> Investment:
        if inv.status != "active":
            raise InvestmentError("Investissement non actif")
        inv.status = "pending_withdrawal"
        inv.withdrawal_requested_at = timezone.now()
        inv.save(update_fields=["status", "withdrawal_requested_at"])
        return inv

    @staticmethod
    @transaction.atomic
    def finalize_withdrawal(inv: Investment) -> Investment:
        if inv.status != "pending_withdrawal":
            raise InvestmentError("Retrait non demandé")
        WalletService.transfer(
            sender=None, receiver=inv.investor, amount=inv.amount,
            kind="investment_withdrawal",
            description=f"Retrait investissement {inv.id}",
        )
        pool, _ = PlatformAccount.objects.select_for_update().get_or_create(type="investment_pool")
        pool.balance -= inv.amount
        pool.save(update_fields=["balance", "updated_at"])
        inv.status = "withdrawn"
        inv.withdrawn_at = timezone.now()
        inv.save(update_fields=["status", "withdrawn_at"])
        return inv
