from django.db.models import Q
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.transactions.services import InsufficientFunds

from .models import Guarantee, Loan
from .serializers import (
    GuaranteeCreateSerializer,
    GuaranteeSerializer,
    LoanCreateSerializer,
    LoanSerializer,
    RepaymentSerializer,
)
from .services import GuaranteeError, GuaranteeService, LoanError, LoanService, ReputationService


def _check_pin(user, pin):
    if not user.check_pin(pin):
        raise PermissionDenied("PIN incorrect.")


class LoanCreateView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "loan_create"

    def post(self, request):
        ser = LoanCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        _check_pin(request.user, ser.validated_data["pin"])
        try:
            loan = LoanService.create_loan(
                request.user,
                ser.validated_data["amount"],
                ser.validated_data["duration_days"],
            )
        except LoanError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(LoanSerializer(loan).data, status=201)


class MyLoansView(generics.ListAPIView):
    serializer_class = LoanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Loan.objects.filter(borrower=self.request.user)


class AvailableLoansView(generics.ListAPIView):
    """Loans still seeking a guarantor, excluding the caller's own."""
    serializer_class = LoanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Loan.objects.filter(status="waiting_guarantor").exclude(borrower=self.request.user)
        amount = self.request.query_params.get("max_amount")
        duration = self.request.query_params.get("duration")
        if amount:
            qs = qs.filter(amount__lte=amount)
        if duration:
            qs = qs.filter(duration_days=duration)
        return qs.order_by("-borrower__reputation_score", "-requested_at")


class LoanDetailView(generics.RetrieveAPIView):
    serializer_class = LoanSerializer
    permission_classes = [IsAuthenticated]
    queryset = Loan.objects.all()

    def get_queryset(self):
        u = self.request.user
        return Loan.objects.filter(
            Q(borrower=u) | Q(guarantees__guarantor=u) | Q(status="waiting_guarantor")
        ).distinct()


class LoanRepayView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        loan = Loan.objects.filter(pk=pk, borrower=request.user).first()
        if not loan:
            return Response({"detail": "Introuvable."}, status=404)
        ser = RepaymentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        _check_pin(request.user, ser.validated_data["pin"])
        try:
            rep = LoanService.repay(
                loan, ser.validated_data["amount"],
                payment_method=ser.validated_data["payment_method"],
                idempotency_key=ser.validated_data["idempotency_key"],
            )
        except (LoanError, InsufficientFunds) as exc:
            return Response({"detail": str(exc)}, status=400)
        loan.refresh_from_db()
        return Response(LoanSerializer(loan).data)


class LoanCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        loan = Loan.objects.filter(pk=pk, borrower=request.user).first()
        if not loan:
            return Response({"detail": "Introuvable."}, status=404)
        try:
            LoanService.cancel(loan)
        except LoanError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"cancelled": True})


class GuaranteeCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        loan = Loan.objects.filter(pk=pk).first()
        if not loan:
            return Response({"detail": "Introuvable."}, status=404)
        ser = GuaranteeCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        _check_pin(request.user, ser.validated_data["pin"])
        try:
            g = GuaranteeService.create_guarantee(
                request.user, loan, ser.validated_data["amount_blocked"],
            )
        except (GuaranteeError, InsufficientFunds) as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(GuaranteeSerializer(g).data, status=201)


class MyGuaranteesView(generics.ListAPIView):
    serializer_class = GuaranteeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Guarantee.objects.filter(guarantor=self.request.user).order_by("-blocked_at")


class LoanEligibilityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        ok, msg = user.can_borrow()
        max_amount, max_dur = ReputationService.max_loan_for(user)
        return Response({
            "eligible": ok and max_amount > 0,
            "reason": msg,
            "max_amount": str(max_amount),
            "max_duration_days": max_dur,
            "reputation_score": user.reputation_score,
        })
