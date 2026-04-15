import logging
from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.admin_dashboard.models import PlatformAccount
from apps.transactions.services import WalletService

from .models import Investment
from .services import InvestmentService

log = logging.getLogger("djangui.investments")


@shared_task
def calculate_monthly_returns():
    """Distribute the investor commission pool proportionally to active investments."""
    with transaction.atomic():
        pool = PlatformAccount.objects.select_for_update().filter(type="investment_pool").first()
        if not pool or pool.balance <= 0:
            return 0
        # Only the portion that represents actual commission, not the capital.
        # In this MVP we track the capital separately via Investment rows.
        capital = Investment.objects.filter(status="active").aggregate(s=Sum("amount"))["s"] or Decimal("0")
        distributable = pool.balance - capital
        if distributable <= 0:
            return 0

        investments = list(Investment.objects.filter(status="active").select_related("investor"))
        total_weight = sum((i.amount for i in investments), start=Decimal("0"))
        if total_weight <= 0:
            return 0

        distributed = Decimal("0")
        for inv in investments:
            share = (distributable * inv.amount / total_weight).quantize(Decimal("0.01"))
            if share <= 0:
                continue
            WalletService.transfer(
                sender=None, receiver=inv.investor, amount=share,
                kind="investment_return",
                description="Rendement mensuel investissement",
            )
            inv.total_returns_earned += share
            inv.save(update_fields=["total_returns_earned"])
            distributed += share

        pool.balance -= distributed
        pool.save(update_fields=["balance", "updated_at"])
        return int(distributed)


@shared_task
def process_pending_withdrawals():
    """Finalize investor withdrawals whose notice period has elapsed."""
    now = timezone.now()
    count = 0
    for inv in Investment.objects.filter(status="pending_withdrawal"):
        if not inv.withdrawal_requested_at:
            continue
        ready = inv.withdrawal_requested_at + timedelta(days=inv.notice_period_days)
        if now >= ready:
            try:
                InvestmentService.finalize_withdrawal(inv)
                count += 1
            except Exception:
                log.exception("failed to finalize investment %s", inv.pk)
    return count
