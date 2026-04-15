import logging
import secrets
from django.db import transaction

from apps.accounts.models import User

from .models import Partner, TchekeleRedemption

log = logging.getLogger("djangui.rewards")


class TchekeleError(Exception):
    pass


class TchekeleService:
    @staticmethod
    @transaction.atomic
    def redeem(user: User, partner_id: str) -> TchekeleRedemption:
        partner = Partner.objects.filter(pk=partner_id, is_active=True).first()
        if not partner:
            raise TchekeleError("Partenaire introuvable")
        u = User.objects.select_for_update().get(pk=user.pk)
        if u.tchekele_points < partner.tchekele_cost:
            raise TchekeleError("Points Tchekele insuffisants")
        u.tchekele_points -= partner.tchekele_cost
        u.save(update_fields=["tchekele_points", "updated_at"])
        code = secrets.token_urlsafe(8)
        return TchekeleRedemption.objects.create(
            user=user, partner=partner, points_spent=partner.tchekele_cost, code=code,
        )
