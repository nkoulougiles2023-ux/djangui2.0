import logging
import random
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User, Wallet
from apps.admin_dashboard.models import PlatformAccount
from apps.notifications.services import notify
from apps.transactions.services import InsufficientFunds, WalletService

from .models import Tontine, TontineContribution, TontineMembership

log = logging.getLogger("djangui.tontines")


class TontineError(Exception):
    pass


class TontineService:
    @staticmethod
    @transaction.atomic
    def create(creator: User, *, name: str, contribution_amount: Decimal,
               frequency: str, max_members: int, requires_guarantor: bool) -> Tontine:
        t = Tontine.objects.create(
            name=name, creator=creator,
            contribution_amount=Decimal(contribution_amount),
            frequency=frequency, max_members=max_members,
            requires_guarantor=requires_guarantor,
        )
        # Creator joins at position 1 (order is randomized when the tontine starts)
        TontineMembership.objects.create(tontine=t, member=creator, position=1)
        return t

    @staticmethod
    @transaction.atomic
    def join(user: User, tontine: Tontine, guarantor: User | None = None) -> TontineMembership:
        if tontine.status != "recruiting":
            raise TontineError("Tontine fermée au recrutement")
        if TontineMembership.objects.filter(tontine=tontine, member=user).exists():
            raise TontineError("Déjà membre")
        if user.kyc_status != "verified":
            raise TontineError("KYC requis")
        wallet = Wallet.objects.select_for_update().get(user=user)
        if wallet.available_balance < tontine.contribution_amount:
            raise TontineError("Solde insuffisant pour 1 cotisation")
        if tontine.requires_guarantor:
            if guarantor is None:
                raise TontineError("Avaliste requis")
            if guarantor.id == user.id:
                raise TontineError("Avaliste différent du membre requis")
            g_wallet = Wallet.objects.get(user=guarantor)
            if g_wallet.available_balance < tontine.contribution_amount:
                raise TontineError("Avaliste solde insuffisant")

        count = TontineMembership.objects.filter(tontine=tontine).count()
        m = TontineMembership.objects.create(
            tontine=tontine, member=user, guarantor=guarantor, position=count + 1,
        )
        # Start when full — randomize positions, open round 1 contributions
        if count + 1 >= tontine.max_members:
            TontineService._start(tontine)
        return m

    @staticmethod
    @transaction.atomic
    def _start(tontine: Tontine) -> None:
        memberships = list(tontine.memberships.all())
        random.shuffle(memberships)
        for i, m in enumerate(memberships, start=1):
            m.position = i
        TontineMembership.objects.bulk_update(memberships, ["position"])
        tontine.status = "active"
        tontine.start_date = date.today()
        tontine.save(update_fields=["status", "start_date"])
        TontineService._open_round(tontine, 1)

    @staticmethod
    def _open_round(tontine: Tontine, round_number: int) -> None:
        for m in tontine.memberships.all():
            TontineContribution.objects.get_or_create(
                tontine=tontine, member=m.member, round_number=round_number,
                defaults={"amount": tontine.contribution_amount},
            )
        notify_all(tontine, "tontine_reminder", "Nouveau tour",
                   f"Tour {round_number} ouvert — cotisez {tontine.contribution_amount} FCFA")

    @staticmethod
    @transaction.atomic
    def contribute(user: User, tontine: Tontine, *, idempotency_key: str | None = None) -> TontineContribution:
        if tontine.status != "active":
            raise TontineError("Tontine inactive")
        contrib = TontineContribution.objects.select_for_update().filter(
            tontine=tontine, member=user, round_number=tontine.current_round,
        ).first()
        if not contrib or contrib.paid:
            raise TontineError("Aucune cotisation due")
        try:
            tx = WalletService.transfer(
                sender=user, receiver=None, amount=contrib.amount,
                kind="tontine_contribution", tontine=tontine,
                idempotency_key=idempotency_key,
                description=f"Cotisation {tontine.name} tour {contrib.round_number}",
            )
        except InsufficientFunds as exc:
            raise TontineError(str(exc))
        contrib.paid = True
        contrib.paid_at = timezone.now()
        contrib.transaction = tx
        contrib.save(update_fields=["paid", "paid_at", "transaction"])

        # If all paid → payout
        outstanding = TontineContribution.objects.filter(
            tontine=tontine, round_number=tontine.current_round, paid=False,
        ).count()
        if outstanding == 0:
            TontineService._payout(tontine)
        return contrib

    @staticmethod
    @transaction.atomic
    def _payout(tontine: Tontine) -> None:
        beneficiary_m = tontine.memberships.filter(position=tontine.current_round).first()
        if not beneficiary_m:
            return
        # 2% platform commission
        commission = tontine.commission
        net = tontine.net_payout

        WalletService.transfer(
            sender=None, receiver=beneficiary_m.member, amount=net,
            kind="tontine_payout", tontine=tontine,
            description=f"Cagnotte tour {tontine.current_round} — {tontine.name}",
        )
        platform_acc, _ = PlatformAccount.objects.select_for_update().get_or_create(type="commission")
        platform_acc.balance += commission
        platform_acc.save(update_fields=["balance", "updated_at"])

        beneficiary_m.has_received_pot = True
        beneficiary_m.save(update_fields=["has_received_pot"])
        notify(beneficiary_m.member, "tontine_turn", "Cagnotte reçue",
               f"Vous avez reçu {net} FCFA de la tontine {tontine.name}.")

        # Advance round
        if tontine.current_round >= tontine.max_members:
            tontine.status = "completed"
            tontine.save(update_fields=["status"])
        else:
            tontine.current_round += 1
            tontine.save(update_fields=["current_round"])
            TontineService._open_round(tontine, tontine.current_round)


def notify_all(tontine: Tontine, type_: str, title: str, body: str) -> None:
    for m in tontine.memberships.all():
        notify(m.member, type_, title, body)
