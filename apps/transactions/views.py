from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.serializers import WalletSerializer

from .models import Transaction
from .serializers import DepositSerializer, TransactionSerializer, WithdrawSerializer
from .services import InsufficientFunds, LimitExceeded, WalletService


class WalletView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(WalletSerializer(request.user.wallet).data)


class DepositView(APIView):
    """Initiates a Mobile Money collection. In production, the wallet is credited
    by the provider webhook — not here. For dev we credit immediately."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = DepositSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data
        try:
            tx = WalletService.deposit(
                request.user, v["amount"],
                reference=f"{v['payment_method']}:{v['msisdn']}",
                idempotency_key=v["idempotency_key"],
                description=f"Dépôt {v['payment_method']}",
            )
        except LimitExceeded as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TransactionSerializer(tx).data, status=201)


class WithdrawView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = WithdrawSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data
        if not request.user.check_pin(v["pin"]):
            return Response({"detail": "PIN incorrect."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            tx = WalletService.withdraw(
                request.user, v["amount"],
                reference=f"{v['payment_method']}:{v['msisdn']}",
                idempotency_key=v["idempotency_key"],
                description=f"Retrait {v['payment_method']}",
            )
        except (InsufficientFunds, LimitExceeded) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TransactionSerializer(tx).data, status=201)


class TransactionHistoryView(generics.ListAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        u = self.request.user
        return Transaction.objects.filter(status="completed").filter(
            sender=u,
        ).union(Transaction.objects.filter(status="completed", receiver=u)).order_by("-created_at")


class MoMoWebhookView(APIView):
    """Stub — in production, verify HMAC and credit wallet here."""
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "webhook"

    def post(self, request):
        # TODO: verify signature (HMAC) or source IP whitelist
        # Expected payload: reference, status, amount, user_phone
        return Response({"ok": True})
