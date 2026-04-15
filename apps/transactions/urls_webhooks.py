from django.urls import path

from .views import MoMoWebhookView

urlpatterns = [
    path("mtn-momo", MoMoWebhookView.as_view()),
    path("orange-money", MoMoWebhookView.as_view()),
]
