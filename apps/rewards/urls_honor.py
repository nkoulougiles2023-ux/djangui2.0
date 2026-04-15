from django.urls import path

from .views import HonorBoardView

urlpatterns = [path("", HonorBoardView.as_view())]
