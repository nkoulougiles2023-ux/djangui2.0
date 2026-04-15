from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import OTPSendView, OTPVerifyView, PinLoginView, RegisterView

urlpatterns = [
    path("register", RegisterView.as_view()),
    path("otp/send", OTPSendView.as_view()),
    path("otp/verify", OTPVerifyView.as_view()),
    path("login/pin", PinLoginView.as_view()),
    path("token/refresh", TokenRefreshView.as_view()),
]
