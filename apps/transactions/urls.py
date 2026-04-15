from django.urls import path

from .views import DepositView, TransactionHistoryView, WalletView, WithdrawView

urlpatterns = [
    path("", WalletView.as_view()),
    path("deposit", DepositView.as_view()),
    path("withdraw", WithdrawView.as_view()),
    path("transactions", TransactionHistoryView.as_view()),
]
