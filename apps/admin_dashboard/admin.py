from django.contrib import admin

from .models import PlatformAccount


@admin.register(PlatformAccount)
class PlatformAccountAdmin(admin.ModelAdmin):
    list_display = ("type", "balance", "updated_at")
    readonly_fields = ("updated_at",)
