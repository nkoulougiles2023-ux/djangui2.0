from django.urls import path

from .views import (
    AdminDashboardView,
    AdminLoanListView,
    AdminUserDetailView,
    AdminUserListView,
    KYCPendingListView,
    KYCValidateView,
    PlatformAccountListView,
)

urlpatterns = [
    path("dashboard", AdminDashboardView.as_view(), name="admin-dashboard"),
    path("kyc/pending", KYCPendingListView.as_view(), name="admin-kyc-pending"),
    path("kyc/<uuid:pk>/validate", KYCValidateView.as_view(), name="admin-kyc-validate"),
    path("loans", AdminLoanListView.as_view(), name="admin-loans"),
    path("users", AdminUserListView.as_view(), name="admin-users"),
    path("users/<uuid:pk>", AdminUserDetailView.as_view(), name="admin-user-detail"),
    path("platform-accounts", PlatformAccountListView.as_view(), name="admin-platform-accounts"),
]
