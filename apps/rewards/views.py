from datetime import datetime

from rest_framework import serializers as drf_serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import HonorBoard, Partner, TchekeleRedemption
from .services import TchekeleError, TchekeleService


class PartnerSerializer(drf_serializers.ModelSerializer):
    class Meta:
        model = Partner
        fields = ("id", "name", "type", "discount_description", "tchekele_cost", "city", "contact_phone")


class RedemptionSerializer(drf_serializers.ModelSerializer):
    class Meta:
        model = TchekeleRedemption
        fields = ("id", "partner", "points_spent", "code", "created_at")


class HonorSerializer(drf_serializers.ModelSerializer):
    class Meta:
        model = HonorBoard
        fields = ("id", "user", "period", "score", "rank", "is_visible")


class TchekeleSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        partners = Partner.objects.filter(is_active=True)
        history = TchekeleRedemption.objects.filter(user=u).order_by("-created_at")
        return Response({
            "balance": u.tchekele_points,
            "partners": PartnerSerializer(partners, many=True).data,
            "history": RedemptionSerializer(history, many=True).data,
        })


class TchekeleRedeemView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        partner_id = request.data.get("partner_id")
        if not partner_id:
            return Response({"detail": "partner_id requis."}, status=400)
        try:
            r = TchekeleService.redeem(request.user, partner_id)
        except TchekeleError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(RedemptionSerializer(r).data, status=201)


class HonorBoardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        period = request.query_params.get("period") or datetime.now().strftime("%Y-%m")
        qs = HonorBoard.objects.filter(period=period, is_visible=True).order_by("rank")[:50]
        return Response({
            "period": period,
            "ranking": HonorSerializer(qs, many=True).data,
        })
