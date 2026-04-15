import logging
from decimal import Decimal

from celery import shared_task
from django.db.models import Sum

from apps.accounts.models import Wallet

from .models import Transaction

log = logging.getLogger("djangui.transactions")


@shared_task
def reconcile_wallets():
    """Verify each wallet against the immutable ledger. Freezes on mismatch."""
    mismatches = 0
    for w in Wallet.objects.select_related("user"):
        credits = Transaction.objects.filter(
            receiver=w.user, status="completed",
        ).aggregate(s=Sum("amount"))["s"] or Decimal("0")
        debits = Transaction.objects.filter(
            sender=w.user, status="completed",
        ).aggregate(s=Sum("amount"))["s"] or Decimal("0")
        # Blocked funds move from available→blocked, not out of the user.
        # So expected total = credits − debits − permanently-seized amounts.
        seized = Transaction.objects.filter(
            sender=w.user, type="guarantee_seize", status="completed",
        ).aggregate(s=Sum("amount"))["s"] or Decimal("0")
        expected_total = credits - debits - seized
        actual_total = w.available_balance + w.blocked_balance
        if abs(expected_total - actual_total) > Decimal("0.01"):
            log.error(
                "wallet_mismatch user=%s expected=%s actual=%s",
                w.user.phone, expected_total, actual_total,
            )
            mismatches += 1
    return mismatches
