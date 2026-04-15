from rest_framework import serializers

from apps.accounts.models import User
from apps.loans.models import Loan

from .models import PlatformAccount


class PlatformAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformAccount
        fields = ("id", "type", "balance", "updated_at")
        read_only_fields = fields


class KYCPendingSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id", "phone", "first_name", "last_name",
            "date_of_birth", "city", "cni_number",
            "cni_front_image", "cni_back_image", "selfie_kyc",
            "kyc_status", "created_at",
        )
        read_only_fields = fields


class KYCDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=("verified", "rejected"))
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


class AdminUserSerializer(serializers.ModelSerializer):
    wallet_balance = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id", "phone", "first_name", "last_name", "city",
            "kyc_status", "is_active", "is_banned",
            "reputation_score", "tchekele_points",
            "wallet_balance", "created_at",
        )
        read_only_fields = (
            "id", "phone", "wallet_balance", "created_at",
            "reputation_score", "tchekele_points",
        )

    def get_wallet_balance(self, obj):
        w = getattr(obj, "wallet", None)
        return str(w.available_balance) if w else "0.00"


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("is_active", "is_banned", "kyc_status")


class AdminLoanSerializer(serializers.ModelSerializer):
    borrower_phone = serializers.CharField(source="borrower.phone", read_only=True)

    class Meta:
        model = Loan
        fields = (
            "id", "borrower", "borrower_phone", "amount",
            "total_to_repay", "amount_repaid", "duration_days",
            "status", "requested_at", "approved_at", "due_date", "completed_at",
        )
        read_only_fields = fields
