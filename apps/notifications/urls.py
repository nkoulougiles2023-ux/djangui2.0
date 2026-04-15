from django.urls import path

from .views import (
    NotificationListView,
    NotificationMarkAllReadView,
    NotificationMarkReadView,
)

urlpatterns = [
    path("", NotificationListView.as_view(), name="notification-list"),
    path("read-all", NotificationMarkAllReadView.as_view(), name="notification-read-all"),
    path("<uuid:pk>/read", NotificationMarkReadView.as_view(), name="notification-read"),
]
