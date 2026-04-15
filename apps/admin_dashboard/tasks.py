import logging
from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.loans.models import Loan
from apps.transactions.models import Transaction

log = logging.getLogger("djangui.admin_dashboard")


@shared_task
def daily_platform_snapshot() -> dict:
    """Lightweight daily metrics roll-up for ops alerts (Telegram/Sentry)."""
    now = timezone.now()
    yesterday = now - timedelta(days=1)

    suspicious = Transaction.objects.filter(
        created_at__gte=yesterday, amount__gte=Decimal("200000"),
    ).count()

    loans = Loan.objects.filter(requested_at__gte=yesterday).aggregate(
        n=Count("id"),
        volume=Sum("amount"),
        defaulted=Count("id", filter=Q(status="defaulted")),
    )
    users = User.objects.filter(created_at__gte=yesterday).count()

    payload = {
        "new_users_24h": users,
        "loans_24h": loans["n"] or 0,
        "loan_volume_24h": str(loans["volume"] or Decimal("0")),
        "defaults_24h": loans["defaulted"] or 0,
        "high_value_txns_24h": suspicious,
        "snapshot_at": now.isoformat(),
    }
    log.info("daily_platform_snapshot %s", payload)
    return payload
