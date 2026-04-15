from django.db.models import Q
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User

from .models import Tontine
from .serializers import (
    ContributeSerializer,
    JoinSerializer,
    TontineCreateSerializer,
    TontineSerializer,
)
from .services import TontineError, TontineService


def _check_pin(user, pin):
    if not user.check_pin(pin):
        raise PermissionDenied("PIN incorrect.")


class TontineListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        scope = request.query_params.get("scope", "all")
        user = request.user
        if scope == "mine":
            qs = Tontine.objects.filter(
                Q(creator=user) | Q(memberships__member=user)
            ).distinct()
        elif scope == "recruiting":
            qs = Tontine.objects.filter(status="recruiting")
        else:
            qs = Tontine.objects.all()
        return Response(TontineSerializer(qs, many=True).data)

    def post(self, request):
        ser = TontineCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        t = TontineService.create(request.user, **ser.validated_data)
        return Response(TontineSerializer(t).data, status=201)


class TontineDetailView(generics.RetrieveAPIView):
    serializer_class = TontineSerializer
    permission_classes = [IsAuthenticated]
    queryset = Tontine.objects.all()


class TontineJoinView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        tontine = Tontine.objects.filter(pk=pk).first()
        if not tontine:
            return Response({"detail": "Introuvable."}, status=404)
        ser = JoinSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        _check_pin(request.user, ser.validated_data["pin"])
        guarantor = None
        if "guarantor_phone" in ser.validated_data:
            guarantor = User.objects.filter(phone=ser.validated_data["guarantor_phone"]).first()
            if not guarantor:
                return Response({"detail": "Avaliste introuvable."}, status=400)
        try:
            TontineService.join(request.user, tontine, guarantor=guarantor)
        except TontineError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(TontineSerializer(tontine).data)


class TontineContributeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        tontine = Tontine.objects.filter(pk=pk).first()
        if not tontine:
            return Response({"detail": "Introuvable."}, status=404)
        ser = ContributeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        _check_pin(request.user, ser.validated_data["pin"])
        try:
            TontineService.contribute(
                request.user, tontine,
                idempotency_key=ser.validated_data["idempotency_key"],
            )
        except TontineError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"ok": True})
