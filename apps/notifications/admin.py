from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "type", "title", "is_read")
    list_filter = ("type", "is_read")
    search_fields = ("user__phone", "title", "message")
    readonly_fields = ("created_at",)
