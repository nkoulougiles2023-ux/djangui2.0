from django.contrib import admin

from .models import HonorBoard, Partner, TchekeleRedemption


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "tchekele_cost", "city", "is_active")
    list_filter = ("type", "is_active", "city")


@admin.register(HonorBoard)
class HonorBoardAdmin(admin.ModelAdmin):
    list_display = ("period", "rank", "user", "score")
    list_filter = ("period",)


admin.site.register(TchekeleRedemption)
