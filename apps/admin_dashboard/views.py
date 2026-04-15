from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import filters, generics
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.loans.models import Guarantee, Loan
from apps.notifications.services import NotificationService
from apps.transactions.models import Transaction

from .models import PlatformAccount
from .serializers import (
    AdminLoanSerializer,
    AdminUserSerializer,
    AdminUserUpdateSerializer,
    KYCDecisionSerializer,
    KYCPendingSerializer,
    PlatformAccountSerializer,
)


class KYCPendingListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = KYCPendingSerializer

    def get_queryset(self):
        return User.objects.filter(kyc_status="pending").order_by("created_at")


class KYCValidateView(APIView):
    permission_classes = [IsAdminUser]

    def put(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        payload = KYCDecisionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        decision = payload.validated_data["decision"]
        reason = payload.validated_data.get("reason", "")

        user.kyc_status = decision
        user.save(update_fields=["kyc_status", "updated_at"])

        if decision == "verified":
            user.reputation_score = min(100, user.reputation_score + 5)
            user.save(update_fields=["reputation_score", "updated_at"])
            NotificationService.notify(
                user, "system", "KYC validé",
                "Votre identité a été vérifiée. Vous pouvez désormais emprunter.",
            )
        else:
            NotificationService.notify(
                user, "system", "KYC rejeté",
                f"Votre vérification a été rejetée. Motif: {reason or 'non précisé'}",
            )
        return Response(KYCPendingSerializer(user).data)


class AdminLoanListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminLoanSerializer
    filter_backends = [filters.OrderingFilter]
    ordering = ["-requested_at"]

    def get_queryset(self):
        qs = Loan.objects.select_related("borrower")
        status_ = self.request.query_params.get("status")
        if status_:
            qs = qs.filter(status=status_)
        return qs


class AdminUserListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminUserSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["phone", "first_name", "last_name", "city"]
    ordering_fields = ["created_at", "reputation_score"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return User.objects.select_related("wallet")


class AdminUserDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        user = get_object_or_404(User.objects.select_related("wallet"), pk=pk)
        return Response(AdminUserSerializer(user).data)

    def put(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        s = AdminUserUpdateSerializer(user, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(AdminUserSerializer(user).data)


class AdminDashboardView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        loan_stats = Loan.objects.aggregate(
            total=Count("id"),
            active=Count("id", filter=Q(status="active")),
            repaid=Count("id", filter=Q(status="repaid")),
            defaulted=Count("id", filter=Q(status="defaulted")),
            volume_month=Sum("amount", filter=Q(requested_at__gte=month_start)),
        )

        txn_stats = Transaction.objects.aggregate(
            total=Count("id"),
            month=Count("id", filter=Q(created_at__gte=month_start)),
        )

        user_stats = User.objects.aggregate(
            total=Count("id"),
            verified=Count("id", filter=Q(kyc_status="verified")),
            pending=Count("id", filter=Q(kyc_status="pending")),
            banned=Count("id", filter=Q(is_banned=True)),
        )

        guarantee_stats = Guarantee.objects.aggregate(
            blocked=Sum("amount_blocked", filter=Q(status="blocked")),
            seized=Sum("amount_blocked", filter=Q(status="seized")),
        )

        platform = {
            p.type: str(p.balance)
            for p in PlatformAccount.objects.all()
        }

        return Response({
            "as_of": now.isoformat(),
            "users": {
                **user_stats,
                "banned": user_stats["banned"] or 0,
            },
            "loans": {
                **loan_stats,
                "volume_month": str(loan_stats["volume_month"] or Decimal("0")),
            },
            "transactions": txn_stats,
            "guarantees": {
                "blocked": str(guarantee_stats["blocked"] or Decimal("0")),
                "seized": str(guarantee_stats["seized"] or Decimal("0")),
            },
            "platform_accounts": platform,
        })


class PlatformAccountListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = PlatformAccountSerializer
    queryset = PlatformAccount.objects.all().order_by("type")
