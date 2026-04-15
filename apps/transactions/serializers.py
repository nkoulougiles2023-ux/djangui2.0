from rest_framework import serializers

from .models import Transaction


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = (
            "id", "type", "amount", "status", "payment_reference",
            "description", "loan", "tontine", "created_at",
        )
        read_only_fields = fields


class DepositSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=500)
    payment_method = serializers.ChoiceField(choices=("mtn_momo", "orange_money"))
    msisdn = serializers.RegexField(regex=r"^\+237[0-9]{9}$")
    idempotency_key = serializers.CharField(max_length=64)


class WithdrawSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=500)
    payment_method = serializers.ChoiceField(choices=("mtn_momo", "orange_money"))
    msisdn = serializers.RegexField(regex=r"^\+237[0-9]{9}$")
    pin = serializers.RegexField(regex=r"^\d{4}$")
    idempotency_key = serializers.CharField(max_length=64)
