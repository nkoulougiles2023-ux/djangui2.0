"""Atomic wallet and ledger operations. Every balance mutation MUST go through here."""
import logging
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.models import Wallet

from .models import Transaction

log = logging.getLogger("djangui.transactions")


class InsufficientFunds(Exception):
    pass


class DuplicateIdempotency(Exception):
    pass


class LimitExceeded(Exception):
    pass


def _get_or_reuse(idempotency_key: str) -> Transaction | None:
    return Transaction.objects.filter(idempotency_key=idempotency_key).first()


def _ensure_key(key: str | None) -> str:
    return key or uuid.uuid4().hex


class WalletService:
    """All operations are safe under concurrent access via select_for_update()."""

    # --- core primitives -------------------------------------------------

    @staticmethod
    @transaction.atomic
    def deposit(user, amount: Decimal, *, reference: str | None = None,
                idempotency_key: str | None = None, description: str = "") -> Transaction:
        amount = Decimal(amount)
        if amount <= 0:
            raise ValueError("amount must be positive")
        key = _ensure_key(idempotency_key)
        if existing := _get_or_reuse(key):
            return existing

        WalletService._check_daily_limit(user, amount, "deposit")

        wallet = Wallet.objects.select_for_update().get(user=user)
        wallet.available_balance += amount
        wallet.save(update_fields=["available_balance", "updated_at"])
        tx = Transaction.objects.create(
            type="deposit", amount=amount, receiver=user,
            status="completed", payment_reference=reference,
            idempotency_key=key, description=description,
        )
        log.info("deposit user=%s amount=%s", user.phone, amount)
        return tx

    @staticmethod
    @transaction.atomic
    def withdraw(user, amount: Decimal, *, reference: str | None = None,
                 idempotency_key: str | None = None, description: str = "") -> Transaction:
        amount = Decimal(amount)
        if amount <= 0:
            raise ValueError("amount must be positive")
        key = _ensure_key(idempotency_key)
        if existing := _get_or_reuse(key):
            return existing

        WalletService._check_daily_limit(user, amount, "withdrawal")

        wallet = Wallet.objects.select_for_update().get(user=user)
        if wallet.available_balance < amount:
            raise InsufficientFunds("Solde insuffisant")
        wallet.available_balance -= amount
        wallet.save(update_fields=["available_balance", "updated_at"])
        tx = Transaction.objects.create(
            type="withdrawal", amount=amount, sender=user,
            status="completed", payment_reference=reference,
            idempotency_key=key, description=description,
        )
        log.info("withdraw user=%s amount=%s", user.phone, amount)
        return tx

    @staticmethod
    @transaction.atomic
    def block(user, amount: Decimal, *, kind: str = "guarantee_block",
              loan=None, idempotency_key: str | None = None, description: str = "") -> Transaction:
        amount = Decimal(amount)
        key = _ensure_key(idempotency_key)
        if existing := _get_or_reuse(key):
            return existing

        wallet = Wallet.objects.select_for_update().get(user=user)
        cap = wallet.available_balance * Decimal(str(settings.DJANGUI["MAX_GUARANTEE_PCT_OF_WALLET"]))
        if amount > cap:
            raise InsufficientFunds("Blocage max 80% du solde disponible")
        if wallet.available_balance < amount:
            raise InsufficientFunds("Solde insuffisant")

        wallet.available_balance -= amount
        wallet.blocked_balance += amount
        wallet.save(update_fields=["available_balance", "blocked_balance", "updated_at"])
        tx = Transaction.objects.create(
            type=kind, amount=amount, sender=user, loan=loan,
            status="completed", idempotency_key=key, description=description,
        )
        return tx

    @staticmethod
    @transaction.atomic
    def unblock(user, amount: Decimal, *, kind: str = "guarantee_release",
                loan=None, idempotency_key: str | None = None,
                description: str = "") -> Transaction:
        amount = Decimal(amount)
        key = _ensure_key(idempotency_key)
        if existing := _get_or_reuse(key):
            return existing

        wallet = Wallet.objects.select_for_update().get(user=user)
        if wallet.blocked_balance < amount:
            raise InsufficientFunds("Solde bloqué insuffisant")
        wallet.blocked_balance -= amount
        wallet.available_balance += amount
        wallet.save(update_fields=["blocked_balance", "available_balance", "updated_at"])
        return Transaction.objects.create(
            type=kind, amount=amount, receiver=user, loan=loan,
            status="completed", idempotency_key=key, description=description,
        )

    @staticmethod
    @transaction.atomic
    def seize(user, amount: Decimal, *, loan=None, to_user=None,
              idempotency_key: str | None = None, description: str = "") -> Transaction:
        """Move blocked funds out of the guarantor wallet (to platform / lender)."""
        amount = Decimal(amount)
        key = _ensure_key(idempotency_key)
        if existing := _get_or_reuse(key):
            return existing

        wallet = Wallet.objects.select_for_update().get(user=user)
        if wallet.blocked_balance < amount:
            raise InsufficientFunds("Solde bloqué insuffisant")
        wallet.blocked_balance -= amount
        wallet.save(update_fields=["blocked_balance", "updated_at"])
        if to_user:
            target = Wallet.objects.select_for_update().get(user=to_user)
            target.available_balance += amount
            target.save(update_fields=["available_balance", "updated_at"])
        return Transaction.objects.create(
            type="guarantee_seize", amount=amount, sender=user, receiver=to_user,
            loan=loan, status="completed", idempotency_key=key, description=description,
        )

    @staticmethod
    @transaction.atomic
    def transfer(sender, receiver, amount: Decimal, *, kind: str,
                 loan=None, tontine=None, idempotency_key: str | None = None,
                 description: str = "") -> Transaction:
        amount = Decimal(amount)
        key = _ensure_key(idempotency_key)
        if existing := _get_or_reuse(key):
            return existing

        if sender is not None:
            sw = Wallet.objects.select_for_update().get(user=sender)
            if sw.available_balance < amount:
                raise InsufficientFunds("Solde insuffisant")
            sw.available_balance -= amount
            sw.save(update_fields=["available_balance", "updated_at"])
        if receiver is not None:
            rw = Wallet.objects.select_for_update().get(user=receiver)
            rw.available_balance += amount
            rw.save(update_fields=["available_balance", "updated_at"])

        return Transaction.objects.create(
            type=kind, amount=amount, sender=sender, receiver=receiver,
            loan=loan, tontine=tontine,
            status="completed", idempotency_key=key, description=description,
        )

    # --- helpers ---------------------------------------------------------

    @staticmethod
    def _check_daily_limit(user, amount: Decimal, kind: str):
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        limit_key = "DAILY_DEPOSIT_LIMIT" if kind == "deposit" else "DAILY_WITHDRAW_LIMIT"
        limit = Decimal(settings.DJANGUI[limit_key])
        field = "receiver" if kind == "deposit" else "sender"
        type_ = "deposit" if kind == "deposit" else "withdrawal"
        total = (
            Transaction.objects.filter(
                **{field: user}, type=type_, status="completed",
                created_at__gte=today_start,
            ).aggregate(s=Sum("amount"))["s"] or Decimal("0")
        )
        if total + amount > limit:
            raise LimitExceeded(f"Limite quotidienne dépassée ({limit} FCFA)")
