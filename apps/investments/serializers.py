from rest_framework import serializers

from .models import Investment


class InvestmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Investment
        fields = (
            "id", "amount", "status", "return_rate", "total_returns_earned",
            "invested_at", "withdrawn_at", "notice_period_days",
        )
        read_only_fields = fields


class InvestmentCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=5000)
    pin = serializers.RegexField(regex=r"^\d{4}$")
    idempotency_key = serializers.CharField(max_length=64)


class InvestmentWithdrawSerializer(serializers.Serializer):
    pin = serializers.RegexField(regex=r"^\d{4}$")
