from rest_framework import serializers

from apps.accounts.serializers import UserSerializer

from .models import Guarantee, Loan, LoanRepayment


class LoanSerializer(serializers.ModelSerializer):
    borrower = UserSerializer(read_only=True)
    coverage = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    remaining = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Loan
        fields = (
            "id", "borrower", "amount", "commission_rate", "commission_amount",
            "total_to_repay", "duration_days", "status",
            "requested_at", "approved_at", "due_date", "completed_at",
            "amount_repaid", "grace_period_hours",
            "coverage", "remaining",
        )
        read_only_fields = fields


class LoanCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=1000)
    duration_days = serializers.ChoiceField(choices=(7, 14, 30, 60, 90))
    pin = serializers.RegexField(regex=r"^\d{4}$")


class GuaranteeCreateSerializer(serializers.Serializer):
    amount_blocked = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=100)
    pin = serializers.RegexField(regex=r"^\d{4}$")


class GuaranteeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guarantee
        fields = (
            "id", "loan", "guarantor", "amount_blocked", "status",
            "commission_earned", "blocked_at", "released_at",
        )
        read_only_fields = fields


class RepaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=100)
    payment_method = serializers.ChoiceField(choices=("wallet", "mtn_momo", "orange_money"), default="wallet")
    pin = serializers.RegexField(regex=r"^\d{4}$")
    idempotency_key = serializers.CharField(max_length=64)


class RepaymentReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanRepayment
        fields = ("id", "loan", "amount", "paid_at", "payment_method")
        read_only_fields = fields
