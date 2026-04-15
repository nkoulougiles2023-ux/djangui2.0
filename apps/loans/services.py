"""Loan, Guarantee, Commission, and Reputation business logic."""
import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.accounts.models import User, Wallet
from apps.admin_dashboard.models import PlatformAccount
from apps.notifications.services import notify
from apps.transactions.services import InsufficientFunds, WalletService

from .models import Guarantee, Loan, LoanRepayment

log = logging.getLogger("djangui.loans")


# ---------------------------------------------------------------------------
# Reputation
# ---------------------------------------------------------------------------

class ReputationService:
    GAINS = {
        "loan_repaid_early": 10,
        "loan_repaid_on_time": 5,
        "loan_repaid_in_grace": 2,
        "tontine_on_time": 3,
        "kyc_validated": 5,
        "streak_5_loans": 15,
        "guarantor_success": 2,
    }
    LOSSES = {
        "loan_defaulted": -20,
        "tontine_late": -5,
        "tontine_unpaid": -15,
        "loan_cancelled_after_guarantor": -3,
        "reported_abuse": -10,
    }

    @staticmethod
    def apply(user: User, event: str) -> int:
        """Adjust the user's reputation score per event, clamped to [0, 100]."""
        delta = ReputationService.GAINS.get(event) or ReputationService.LOSSES.get(event, 0)
        if not delta:
            return user.reputation_score
        with transaction.atomic():
            u = User.objects.select_for_update().get(pk=user.pk)
            u.reputation_score = max(0, min(100, u.reputation_score + delta))
            u.save(update_fields=["reputation_score", "updated_at"])
        log.info("reputation user=%s event=%s delta=%+d score=%s",
                 user.phone, event, delta, u.reputation_score)
        return u.reputation_score

    @staticmethod
    def max_loan_for(user: User) -> tuple[Decimal, int]:
        """Return (max_amount, max_duration_days) based on the score grid."""
        for lo, hi, amt, dur in settings.REPUTATION_GRID:
            if lo <= user.reputation_score <= hi:
                is_first = not user.loans_as_borrower.filter(
                    status__in=("active", "repaid", "defaulted"),
                ).exists()
                if is_first:
                    amt = min(amt, settings.DJANGUI["FIRST_LOAN_CAP"])
                return Decimal(amt), dur
        return Decimal("0"), 0


# ---------------------------------------------------------------------------
# Commissions
# ---------------------------------------------------------------------------

class CommissionService:
    @staticmethod
    @transaction.atomic
    def distribute_on_repayment(loan: Loan) -> None:
        """Splits 10% commission: 4% platform, 3% investors, 3% guarantors."""
        commission = loan.commission_amount
        if commission <= 0:
            return
        platform_share = (commission * Decimal(str(settings.DJANGUI["PLATFORM_SHARE"]))).quantize(Decimal("0.01"))
        investor_share = (commission * Decimal(str(settings.DJANGUI["INVESTOR_SHARE"]))).quantize(Decimal("0.01"))
        guarantor_share = commission - platform_share - investor_share

        # Platform account
        platform_acc, _ = PlatformAccount.objects.select_for_update().get_or_create(type="commission")
        platform_acc.balance += platform_share
        platform_acc.save(update_fields=["balance", "updated_at"])

        # Investor pool account
        inv_pool, _ = PlatformAccount.objects.select_for_update().get_or_create(type="investment_pool")
        inv_pool.balance += investor_share
        inv_pool.save(update_fields=["balance", "updated_at"])

        # Guarantors: split proportionally to amount_blocked
        guarantees = list(loan.guarantees.filter(status="blocked").select_related("guarantor"))
        total_blocked = sum((g.amount_blocked for g in guarantees), start=Decimal("0"))
        for g in guarantees:
            share = (
                (guarantor_share * g.amount_blocked / total_blocked).quantize(Decimal("0.01"))
                if total_blocked > 0 else Decimal("0")
            )
            g.commission_earned = share
            g.save(update_fields=["commission_earned"])
            if share > 0:
                WalletService.transfer(
                    sender=None, receiver=g.guarantor, amount=share,
                    kind="commission_guarantor", loan=loan,
                    description="Commission avaliste 3%",
                )
                ReputationService.apply(g.guarantor, "guarantor_success")

        # Record the platform / investor-pool commissions as transactions
        WalletService.transfer(
            sender=None, receiver=None, amount=platform_share,
            kind="commission_platform", loan=loan,
            description="Commission plateforme 4%",
        )
        WalletService.transfer(
            sender=None, receiver=None, amount=investor_share,
            kind="commission_investor", loan=loan,
            description="Commission pool investisseurs 3%",
        )


# ---------------------------------------------------------------------------
# Guarantees
# ---------------------------------------------------------------------------

class GuaranteeError(Exception):
    pass


class GuaranteeService:
    @staticmethod
    @transaction.atomic
    def create_guarantee(user: User, loan: Loan, amount: Decimal) -> Guarantee:
        amount = Decimal(amount)
        if loan.borrower_id == user.id:
            raise GuaranteeError("Impossible de garantir son propre prêt")
        ok, msg = user.can_guarantee()
        if not ok:
            raise GuaranteeError(msg)

        # Max 3 active guarantees
        active_cnt = Guarantee.objects.filter(guarantor=user, status="blocked").count()
        if active_cnt >= settings.DJANGUI["MAX_ACTIVE_GUARANTEES"]:
            raise GuaranteeError("Max 3 garanties actives")

        # Anti-collusion: ≤ 2 consecutive loans from same guarantor for the same borrower
        recent = Guarantee.objects.filter(
            guarantor=user, loan__borrower=loan.borrower,
        ).exclude(loan=loan).order_by("-blocked_at")[:2]
        if len(recent) >= 2:
            raise GuaranteeError("Trop de prêts consécutifs garantis pour cet emprunteur")

        # Status must accept new coverage
        if loan.status != "waiting_guarantor":
            raise GuaranteeError("Prêt n'accepte plus de garanties")

        needed = loan.amount - loan.coverage
        if amount > needed:
            amount = needed

        # Block funds (also enforces the 80% wallet cap)
        WalletService.block(
            user, amount, kind="guarantee_block", loan=loan,
            description=f"Garantie prêt {loan.id}",
        )

        g = Guarantee.objects.create(loan=loan, guarantor=user, amount_blocked=amount)

        # If fully covered, activate the loan
        if loan.coverage >= loan.amount:
            LoanService.activate(loan)

        notify(
            loan.borrower, "guarantee_request", "Avaliste trouvé",
            f"{user.first_name} a garanti votre prêt.",
        )
        return g

    @staticmethod
    @transaction.atomic
    def release_all(loan: Loan) -> None:
        for g in loan.guarantees.select_for_update().filter(status="blocked"):
            WalletService.unblock(
                g.guarantor, g.amount_blocked, kind="guarantee_release",
                loan=loan, description=f"Libération garantie {loan.id}",
            )
            g.status = "released"
            g.released_at = timezone.now()
            g.save(update_fields=["status", "released_at"])

    @staticmethod
    @transaction.atomic
    def seize_all(loan: Loan) -> Decimal:
        """Seize blocked funds to cover the remaining debt. Returns amount seized."""
        remaining = loan.remaining
        seized_total = Decimal("0")
        for g in loan.guarantees.select_for_update().filter(status="blocked"):
            if remaining <= 0:
                # Leftover: release back to guarantor
                WalletService.unblock(
                    g.guarantor, g.amount_blocked, kind="guarantee_release", loan=loan,
                    description="Libération solde après saisie",
                )
                g.status = "released"
                g.released_at = timezone.now()
                g.save(update_fields=["status", "released_at"])
                continue
            take = min(g.amount_blocked, remaining)
            WalletService.seize(
                g.guarantor, take, loan=loan, to_user=None,
                description=f"Saisie garantie {loan.id}",
            )
            g.status = "seized"
            g.released_at = timezone.now()
            g.commission_earned = Decimal("0")
            g.save(update_fields=["status", "released_at", "commission_earned"])
            remaining -= take
            seized_total += take
            # If only part of the block was needed, return the rest
            leftover = g.amount_blocked - take
            if leftover > 0:
                WalletService.unblock(
                    g.guarantor, leftover, kind="guarantee_release", loan=loan,
                    description="Reliquat de garantie non saisi",
                )
        return seized_total


# ---------------------------------------------------------------------------
# Loans
# ---------------------------------------------------------------------------

class LoanError(Exception):
    pass


class LoanService:
    @staticmethod
    @transaction.atomic
    def create_loan(borrower: User, amount: Decimal, duration_days: int) -> Loan:
        amount = Decimal(amount)
        if duration_days not in Loan.DURATIONS:
            raise LoanError("Durée invalide")

        ok, msg = borrower.can_borrow()
        if not ok:
            raise LoanError(msg)

        # Must not have an active loan
        if Loan.objects.filter(
            borrower=borrower,
            status__in=("waiting_guarantor", "waiting_validation", "active"),
        ).exists():
            raise LoanError("Vous avez déjà un prêt en cours")

        # Cooldown
        cooldown = timedelta(hours=settings.DJANGUI["LOAN_COOLDOWN_HOURS"])
        last = Loan.objects.filter(
            borrower=borrower, status__in=("repaid", "defaulted"),
        ).order_by("-completed_at").first()
        if last and last.completed_at and timezone.now() - last.completed_at < cooldown:
            raise LoanError("Cooldown de 24h entre deux prêts")

        max_amount, max_dur = ReputationService.max_loan_for(borrower)
        if max_amount <= 0:
            raise LoanError("Score insuffisant")
        if amount < settings.DJANGUI["LOAN_MIN_AMOUNT"]:
            raise LoanError(f"Montant min {settings.DJANGUI['LOAN_MIN_AMOUNT']} FCFA")
        if amount > max_amount:
            raise LoanError(f"Montant max {max_amount} FCFA selon votre score")
        if duration_days > max_dur:
            raise LoanError(f"Durée max {max_dur} jours selon votre score")

        loan = Loan(
            borrower=borrower, amount=amount,
            duration_days=duration_days,
            commission_rate=Decimal(str(settings.DJANGUI["COMMISSION_RATE"])),
        )
        loan.compute_totals()
        loan.save()
        notify(
            borrower, "loan_created", "Demande enregistrée",
            "Votre demande est en attente d'un avaliste.",
        )
        return loan

    @staticmethod
    @transaction.atomic
    def cancel(loan: Loan, *, by_system: bool = False) -> None:
        if loan.status not in ("waiting_guarantor", "waiting_validation"):
            raise LoanError("Prêt non annulable dans cet état")
        # Release any partial guarantees first
        GuaranteeService.release_all(loan)
        had_guarantor = loan.guarantees.exists()
        loan.status = "cancelled"
        loan.completed_at = timezone.now()
        loan.save(update_fields=["status", "completed_at"])
        if had_guarantor and not by_system:
            ReputationService.apply(loan.borrower, "loan_cancelled_after_guarantor")
        notify(loan.borrower, "loan_cancelled", "Prêt annulé", "Votre demande a été annulée.")

    @staticmethod
    @transaction.atomic
    def activate(loan: Loan) -> None:
        """Activate once 100% covered — disburses funds to borrower."""
        if loan.status != "waiting_guarantor":
            return
        if loan.coverage < loan.amount:
            return
        loan.status = "active"
        loan.approved_at = timezone.now()
        loan.due_date = loan.approved_at + timedelta(days=loan.duration_days)
        loan.save(update_fields=["status", "approved_at", "due_date"])
        WalletService.transfer(
            sender=None, receiver=loan.borrower, amount=loan.amount,
            kind="loan_disbursement", loan=loan,
            description=f"Versement prêt {loan.id}",
        )
        notify(loan.borrower, "loan_approved", "Prêt accordé",
               f"Votre prêt de {loan.amount} FCFA a été versé.")

    @staticmethod
    @transaction.atomic
    def repay(loan: Loan, amount: Decimal, *, payment_method: str = "wallet",
              idempotency_key: str | None = None) -> LoanRepayment:
        amount = Decimal(amount)
        if loan.status != "active":
            raise LoanError("Prêt non actif")
        remaining = loan.remaining
        if amount <= 0:
            raise LoanError("Montant invalide")
        if amount > remaining:
            amount = remaining

        # For this MVP we only handle wallet-sourced repayments atomically.
        if payment_method != "wallet":
            raise LoanError("Seul le paiement wallet est implémenté (MoMo via webhook)")

        tx = WalletService.transfer(
            sender=loan.borrower, receiver=None, amount=amount,
            kind="loan_repayment", loan=loan,
            idempotency_key=idempotency_key,
            description=f"Remboursement prêt {loan.id}",
        )
        rep = LoanRepayment.objects.create(
            loan=loan, amount=amount, payment_method=payment_method, transaction=tx,
        )
        loan.amount_repaid += amount
        loan.save(update_fields=["amount_repaid"])

        if loan.amount_repaid >= loan.total_to_repay:
            LoanService._close_as_repaid(loan)
        return rep

    @staticmethod
    def _close_as_repaid(loan: Loan) -> None:
        loan.status = "repaid"
        loan.completed_at = timezone.now()
        loan.save(update_fields=["status", "completed_at"])
        CommissionService.distribute_on_repayment(loan)
        GuaranteeService.release_all(loan)

        # Rewards — reputation & Tchekele
        now = timezone.now()
        if loan.due_date and now < loan.due_date:
            ReputationService.apply(loan.borrower, "loan_repaid_early")
            _add_tchekele(loan.borrower, 20)
        elif loan.due_date and now <= loan.due_date + timedelta(hours=loan.grace_period_hours):
            if now <= loan.due_date:
                ReputationService.apply(loan.borrower, "loan_repaid_on_time")
                _add_tchekele(loan.borrower, 10)
            else:
                ReputationService.apply(loan.borrower, "loan_repaid_in_grace")

        # Streak bonus: 5 consecutive on-time repayments
        last5 = list(loan.borrower.loans_as_borrower.filter(
            status="repaid",
        ).order_by("-completed_at")[:5])
        if len(last5) == 5 and all(l.completed_at <= (l.due_date + timedelta(hours=l.grace_period_hours))
                                   for l in last5):
            ReputationService.apply(loan.borrower, "streak_5_loans")
            _add_tchekele(loan.borrower, 50)

        notify(loan.borrower, "loan_repaid", "Prêt remboursé",
               "Bravo, votre prêt est soldé !")

    @staticmethod
    @transaction.atomic
    def handle_default(loan: Loan) -> None:
        """Grace period expired: seize guarantors, distribute platform/investor
        commissions (guarantor share = 0)."""
        if loan.status != "active":
            return
        GuaranteeService.seize_all(loan)
        loan.status = "defaulted"
        loan.completed_at = timezone.now()
        loan.save(update_fields=["status", "completed_at"])

        # Platform + investor commissions still paid from the seized pool
        commission = loan.commission_amount
        platform_share = (commission * Decimal(str(settings.DJANGUI["PLATFORM_SHARE"]))).quantize(Decimal("0.01"))
        investor_share = (commission * Decimal(str(settings.DJANGUI["INVESTOR_SHARE"]))).quantize(Decimal("0.01"))

        platform_acc, _ = PlatformAccount.objects.select_for_update().get_or_create(type="commission")
        platform_acc.balance += platform_share
        platform_acc.save(update_fields=["balance", "updated_at"])
        inv_pool, _ = PlatformAccount.objects.select_for_update().get_or_create(type="investment_pool")
        inv_pool.balance += investor_share
        inv_pool.save(update_fields=["balance", "updated_at"])

        WalletService.transfer(sender=None, receiver=None, amount=platform_share,
                               kind="commission_platform", loan=loan,
                               description="Commission plateforme (défaut)")
        WalletService.transfer(sender=None, receiver=None, amount=investor_share,
                               kind="commission_investor", loan=loan,
                               description="Commission investisseurs (défaut)")

        ReputationService.apply(loan.borrower, "loan_defaulted")
        notify(loan.borrower, "loan_defaulted", "Prêt en défaut",
               "Votre prêt a été déclaré en défaut.")
        for g in loan.guarantees.filter(status="seized"):
            notify(g.guarantor, "guarantee_seized", "Garantie saisie",
                   f"Votre garantie de {g.amount_blocked} FCFA a été saisie.")


def _add_tchekele(user: User, points: int) -> None:
    with transaction.atomic():
        u = User.objects.select_for_update().get(pk=user.pk)
        u.tchekele_points += points
        u.save(update_fields=["tchekele_points", "updated_at"])
