from django.urls import path

from .views import InvestmentListCreateView, InvestmentWithdrawView

urlpatterns = [
    path("", InvestmentListCreateView.as_view()),
    path("<uuid:pk>/withdraw", InvestmentWithdrawView.as_view()),
]
