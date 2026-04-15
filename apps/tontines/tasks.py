import logging
from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.utils import timezone

from apps.notifications.services import notify

from .models import TontineContribution

log = logging.getLogger("djangui.tontines")


@shared_task
def check_tontine_contributions():
    """Remind late contributors. After 48h, trigger guarantor or penalty (stub)."""
    cutoff = timezone.now() - timedelta(hours=24)
    pending = TontineContribution.objects.filter(paid=False, tontine__status="active")
    reminded = 0
    for c in pending:
        notify(c.member, "tontine_reminder", "Cotisation en attente",
               f"Cotisez {c.amount} FCFA pour le tour {c.round_number}.")
        reminded += 1
    return reminded
