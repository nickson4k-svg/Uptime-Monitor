from django.urls import path

from .views import DashboardView, LoginView, RegisterView

app_name = "dashboard"

urlpatterns = [
    path("", DashboardView.as_view(), name="home"),
    path("login/", LoginView.as_view(), name="login"),
    path("register/", RegisterView.as_view(), name="register"),
]
