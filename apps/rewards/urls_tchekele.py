from django.urls import path

from .views import TchekeleRedeemView, TchekeleSummaryView

urlpatterns = [
    path("", TchekeleSummaryView.as_view()),
    path("redeem", TchekeleRedeemView.as_view()),
]
