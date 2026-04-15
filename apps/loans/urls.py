from django.urls import path

from .views import (
    AvailableLoansView,
    GuaranteeCreateView,
    LoanCancelView,
    LoanCreateView,
    LoanDetailView,
    LoanEligibilityView,
    LoanRepayView,
    MyLoansView,
)

urlpatterns = [
    path("", LoanCreateView.as_view()),
    path("mine", MyLoansView.as_view()),
    path("available", AvailableLoansView.as_view()),
    path("eligibility", LoanEligibilityView.as_view()),
    path("<uuid:pk>", LoanDetailView.as_view()),
    path("<uuid:pk>/repay", LoanRepayView.as_view()),
    path("<uuid:pk>/cancel", LoanCancelView.as_view()),
    path("<uuid:pk>/guarantee", GuaranteeCreateView.as_view()),
]
