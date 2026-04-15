from django.contrib import admin

from .models import AuditLog, OTPAttempt, User, Wallet


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("phone", "first_name", "last_name", "kyc_status", "reputation_score", "is_active", "is_banned")
    list_filter = ("kyc_status", "is_active", "is_banned", "gender")
    search_fields = ("phone", "first_name", "last_name", "cni_number")
    readonly_fields = ("id", "created_at", "updated_at", "pin_hash")


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "available_balance", "blocked_balance", "currency", "updated_at")
    search_fields = ("user__phone",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "ip")
    list_filter = ("action",)
    search_fields = ("action", "user__phone")
    readonly_fields = tuple(f.name for f in AuditLog._meta.fields)


admin.site.register(OTPAttempt)
