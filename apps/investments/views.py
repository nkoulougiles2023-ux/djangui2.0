from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Investment
from .serializers import (
    InvestmentCreateSerializer,
    InvestmentSerializer,
    InvestmentWithdrawSerializer,
)
from .services import InvestmentError, InvestmentService


def _check_pin(user, pin):
    if not user.check_pin(pin):
        raise PermissionDenied("PIN incorrect.")


class InvestmentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Investment.objects.filter(investor=request.user).order_by("-invested_at")
        return Response(InvestmentSerializer(qs, many=True).data)

    def post(self, request):
        ser = InvestmentCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        _check_pin(request.user, ser.validated_data["pin"])
        try:
            inv = InvestmentService.deposit(
                request.user, ser.validated_data["amount"],
                idempotency_key=ser.validated_data["idempotency_key"],
            )
        except InvestmentError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(InvestmentSerializer(inv).data, status=201)


class InvestmentWithdrawView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        inv = Investment.objects.filter(pk=pk, investor=request.user).first()
        if not inv:
            return Response({"detail": "Introuvable."}, status=404)
        ser = InvestmentWithdrawSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        _check_pin(request.user, ser.validated_data["pin"])
        try:
            InvestmentService.request_withdrawal(inv)
        except InvestmentError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(InvestmentSerializer(inv).data)
