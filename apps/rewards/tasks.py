import logging
from datetime import date, timedelta
from decimal import Decimal

from celery import shared_task
from django.db import transaction
from django.db.models import Count, Q, Sum

from apps.accounts.models import User
from apps.loans.models import Loan

from .models import HonorBoard

log = logging.getLogger("djangui.rewards")


@shared_task
def update_honor_board():
    """Recompute monthly ranking: repaid loans + reputation + Tchekele."""
    period = (date.today().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    start = date.today().replace(day=1) - timedelta(days=1)
    month_start = start.replace(day=1)
    qs = User.objects.annotate(
        repaid=Count("loans_as_borrower", filter=Q(
            loans_as_borrower__status="repaid",
            loans_as_borrower__completed_at__gte=month_start,
        )),
        repaid_amount=Sum("loans_as_borrower__amount", filter=Q(
            loans_as_borrower__status="repaid",
            loans_as_borrower__completed_at__gte=month_start,
        )),
    ).filter(repaid__gt=0)

    scored = []
    for u in qs:
        score = int((u.repaid or 0) * 10 + (u.repaid_amount or Decimal("0")) / 1000 + u.reputation_score)
        scored.append((u, score))
    scored.sort(key=lambda x: -x[1])

    with transaction.atomic():
        HonorBoard.objects.filter(period=period).delete()
        for rank, (u, score) in enumerate(scored, start=1):
            HonorBoard.objects.create(user=u, period=period, score=score, rank=rank)
    return len(scored)
