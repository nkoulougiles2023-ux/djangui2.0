from django.urls import path

from .views import ChangePinView, KYCView, MeView, MyStatsView

urlpatterns = [
    path("me", MeView.as_view()),
    path("me/kyc", KYCView.as_view()),
    path("me/pin", ChangePinView.as_view()),
    path("me/stats", MyStatsView.as_view()),
]
