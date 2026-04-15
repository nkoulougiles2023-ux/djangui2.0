from django.urls import path

from .views import (
    TontineContributeView,
    TontineDetailView,
    TontineJoinView,
    TontineListCreateView,
)

urlpatterns = [
    path("", TontineListCreateView.as_view()),
    path("<uuid:pk>", TontineDetailView.as_view()),
    path("<uuid:pk>/join", TontineJoinView.as_view()),
    path("<uuid:pk>/contribute", TontineContributeView.as_view()),
]
