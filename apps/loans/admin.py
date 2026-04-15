from django.contrib import admin

from .models import Guarantee, Loan, LoanRepayment


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ("borrower", "amount", "status", "duration_days", "due_date", "amount_repaid")
    list_filter = ("status", "duration_days")
    search_fields = ("borrower__phone",)


@admin.register(Guarantee)
class GuaranteeAdmin(admin.ModelAdmin):
    list_display = ("loan", "guarantor", "amount_blocked", "status", "commission_earned")
    list_filter = ("status",)


@admin.register(LoanRepayment)
class LoanRepaymentAdmin(admin.ModelAdmin):
    list_display = ("loan", "amount", "payment_method", "paid_at")
