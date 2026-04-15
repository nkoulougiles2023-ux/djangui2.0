from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


def landing(_request):
    return JsonResponse({
        "app": "DJANGUI 2.0",
        "status": "preview",
        "description": "Tontine, prêt instantané & investissement — Cameroun",
        "docs": "/api/docs/",
        "schema": "/api/schema/",
        "api_base": "/api/v1/",
    })


api_v1 = [
    path("auth/", include("apps.accounts.urls_auth")),
    path("users/", include("apps.accounts.urls_users")),
    path("wallet/", include("apps.transactions.urls")),
    path("loans/", include("apps.loans.urls")),
    path("guarantees/", include("apps.loans.urls_guarantees")),
    path("tontines/", include("apps.tontines.urls")),
    path("investments/", include("apps.investments.urls")),
    path("tchekele/", include("apps.rewards.urls_tchekele")),
    path("honor-board/", include("apps.rewards.urls_honor")),
    path("notifications/", include("apps.notifications.urls")),
    path("admin/", include("apps.admin_dashboard.urls")),
    path("webhooks/", include("apps.transactions.urls_webhooks")),
]

urlpatterns = [
    path("", landing, name="landing"),
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
