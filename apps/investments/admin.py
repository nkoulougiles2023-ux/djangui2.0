from django.contrib import admin

from .models import Investment


@admin.register(Investment)
class InvestmentAdmin(admin.ModelAdmin):
    list_display = ("investor", "amount", "status", "return_rate", "total_returns_earned", "invested_at")
    list_filter = ("status",)
