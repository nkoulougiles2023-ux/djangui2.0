from django.db import transaction
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import (
    ChangePinSerializer,
    KYCSerializer,
    OTPVerifySerializer,
    PhoneSerializer,
    PinLoginSerializer,
    RegisterSerializer,
    UserSerializer,
)
from .services import (
    audit,
    clear_pin_failures,
    is_pin_locked,
    issue_otp,
    register_pin_failure,
    verify_otp,
)


def _tokens(user: User) -> dict:
    r = RefreshToken.for_user(user)
    return {"refresh": str(r), "access": str(r.access_token)}


class OTPSendView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_send"

    def post(self, request):
        data = PhoneSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        phone = data.validated_data["phone"]
        try:
            code = issue_otp(phone, ip=request.META.get("REMOTE_ADDR"))
        except RuntimeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        audit(request.user, "otp_send", request, phone=phone)
        payload = {"sent": True}
        # Only expose the code in DEBUG for local testing
        from django.conf import settings
        if settings.DEBUG:
            payload["dev_code"] = code
        return Response(payload)


class OTPVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = OTPVerifySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        phone = data.validated_data["phone"]
        if not verify_otp(phone, data.validated_data["code"]):
            return Response({"detail": "OTP invalide."}, status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.filter(phone=phone).first()
        if not user:
            return Response({"verified": True, "registered": False})
        audit(user, "otp_login", request)
        return Response({"verified": True, "registered": True, **_tokens(user)})


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = RegisterSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        if not verify_otp(v["phone"], v["otp"]):
            return Response({"detail": "OTP invalide."}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            user = User.objects.create_user(
                phone=v["phone"],
                first_name=v["first_name"],
                last_name=v["last_name"],
                date_of_birth=v["date_of_birth"],
                gender=v["gender"],
                address=v["address"],
                city=v["city"],
            )
            user.set_pin(v["pin"])
            user.save()
        audit(user, "register", request)
        return Response({"user": UserSerializer(user).data, **_tokens(user)}, status=201)


class PinLoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "pin_login"

    def post(self, request):
        data = PinLoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = User.objects.filter(phone=data.validated_data["phone"]).first()
        if not user:
            return Response({"detail": "Identifiants invalides."}, status=401)
        if is_pin_locked(user):
            return Response({"detail": "PIN bloqué temporairement."}, status=423)
        if not user.check_pin(data.validated_data["pin"]):
            register_pin_failure(user)
            audit(user, "pin_login_failed", request)
            return Response({"detail": "PIN incorrect."}, status=401)
        clear_pin_failures(user)
        audit(user, "pin_login", request)
        return Response({"user": UserSerializer(user).data, **_tokens(user)})


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class KYCView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Limit resubmissions: max 3 (simple counter on user)
        existing = request.user.cni_number or request.user.selfie_kyc
        ser = KYCSerializer(request.user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        audit(request.user, "kyc_submitted", request)
        return Response({"kyc_status": request.user.kyc_status})


class ChangePinView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        ser = ChangePinSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = request.user
        if not user.check_pin(ser.validated_data["old_pin"]):
            return Response({"detail": "PIN actuel incorrect."}, status=400)
        user.set_pin(ser.validated_data["new_pin"])
        user.save(update_fields=["pin_hash", "updated_at"])
        audit(user, "pin_changed", request)
        return Response({"changed": True})


class MyStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        loans = user.loans_as_borrower.all()
        repaid = loans.filter(status="repaid").count()
        defaulted = loans.filter(status="defaulted").count()
        active_guarantees = user.guarantees_given.filter(status="blocked").count()
        return Response({
            "loans_total": loans.count(),
            "loans_repaid": repaid,
            "loans_defaulted": defaulted,
            "active_guarantees": active_guarantees,
            "reputation_score": user.reputation_score,
            "tchekele_points": user.tchekele_points,
        })
