from django.contrib import admin

from .models import Tontine, TontineContribution, TontineMembership


@admin.register(Tontine)
class TontineAdmin(admin.ModelAdmin):
    list_display = ("name", "creator", "contribution_amount", "frequency", "max_members", "status", "current_round")
    list_filter = ("status", "frequency")


@admin.register(TontineMembership)
class TontineMembershipAdmin(admin.ModelAdmin):
    list_display = ("tontine", "member", "position", "has_received_pot")


@admin.register(TontineContribution)
class TontineContributionAdmin(admin.ModelAdmin):
    list_display = ("tontine", "member", "round_number", "amount", "paid", "paid_at")
    list_filter = ("paid",)
