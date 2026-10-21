from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from .views import DemoLoginView, LogoutView, MeView, RegisterView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", obtain_auth_token, name="login"),
    path("demo/", DemoLoginView.as_view(), name="demo-login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
]
