import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.notifications.services import notify

from .models import Loan
from .services import LoanService

log = logging.getLogger("djangui.loans")


@shared_task
def check_loan_expiry():
    """Cancel waiting_guarantor loans older than 48h."""
    cutoff = timezone.now() - timedelta(hours=48)
    qs = Loan.objects.filter(status="waiting_guarantor", requested_at__lt=cutoff)
    count = 0
    for loan in qs:
        try:
            LoanService.cancel(loan, by_system=True)
            count += 1
        except Exception:
            log.exception("failed to cancel expired loan %s", loan.pk)
    return count


@shared_task
def check_loan_default():
    """Trigger default after grace period."""
    now = timezone.now()
    count = 0
    for loan in Loan.objects.filter(status="active", due_date__lt=now):
        deadline = loan.due_date + timedelta(hours=loan.grace_period_hours)
        if now >= deadline:
            try:
                LoanService.handle_default(loan)
                count += 1
            except Exception:
                log.exception("failed to default loan %s", loan.pk)
        else:
            # Still in grace — remind every 24h
            notify(loan.borrower, "loan_reminder", "Rappel de remboursement",
                   "Période de grâce active — pensez à rembourser.")
    return count


@shared_task
def send_loan_reminders():
    """Daily J-3, J-1, J-0 reminders."""
    now = timezone.now()
    reminders = 0
    for delta in (3, 1, 0):
        target = (now + timedelta(days=delta)).date()
        for loan in Loan.objects.filter(status="active", due_date__date=target):
            notify(loan.borrower, "loan_reminder",
                   f"Échéance J-{delta}",
                   f"Reste à payer : {loan.remaining} FCFA")
            reminders += 1
    return reminders
