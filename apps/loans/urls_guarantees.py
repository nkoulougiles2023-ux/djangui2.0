from django.urls import path

from .views import MyGuaranteesView

urlpatterns = [
    path("mine", MyGuaranteesView.as_view()),
]
