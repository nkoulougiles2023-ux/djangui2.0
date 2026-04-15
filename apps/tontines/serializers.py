from rest_framework import serializers

from .models import Tontine, TontineContribution, TontineMembership


class TontineSerializer(serializers.ModelSerializer):
    members_count = serializers.SerializerMethodField()
    pot = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    commission = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    net_payout = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Tontine
        fields = (
            "id", "name", "creator", "contribution_amount", "frequency",
            "max_members", "members_count", "current_round", "status",
            "requires_guarantor", "start_date", "created_at",
            "pot", "commission", "net_payout",
        )
        read_only_fields = (
            "id", "creator", "current_round", "status", "start_date",
            "created_at", "pot", "commission", "net_payout",
        )

    def get_members_count(self, obj):
        return obj.memberships.count()


class TontineCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    contribution_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=500)
    frequency = serializers.ChoiceField(choices=("weekly", "biweekly", "monthly"))
    max_members = serializers.IntegerField(min_value=2, max_value=50)
    requires_guarantor = serializers.BooleanField(default=True)


class JoinSerializer(serializers.Serializer):
    guarantor_phone = serializers.RegexField(regex=r"^\+237[0-9]{9}$", required=False)
    pin = serializers.RegexField(regex=r"^\d{4}$")


class ContributeSerializer(serializers.Serializer):
    pin = serializers.RegexField(regex=r"^\d{4}$")
    idempotency_key = serializers.CharField(max_length=64)


class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = TontineMembership
        fields = ("id", "tontine", "member", "guarantor", "position", "has_received_pot", "joined_at")
        read_only_fields = fields


class ContributionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TontineContribution
        fields = ("id", "tontine", "member", "round_number", "amount", "paid", "paid_at")
        read_only_fields = fields
