from django.contrib import admin

from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("created_at", "type", "amount", "status", "sender", "receiver", "loan")
    list_filter = ("type", "status")
    search_fields = ("idempotency_key", "payment_reference", "sender__phone", "receiver__phone")
    readonly_fields = tuple(f.name for f in Transaction._meta.fields)

    def has_delete_permission(self, request, obj=None):
        return False
