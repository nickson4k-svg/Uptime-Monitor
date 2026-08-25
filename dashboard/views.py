"""Dashboard HTML view — serves the SPA shell."""

from django.shortcuts import render
from django.views import View


class DashboardView(View):
    """Serves the dashboard HTML shell. Auth handled client-side via JWT."""

    def get(self, request):
        return render(request, "dashboard/dashboard.html")


class LoginView(View):
    def get(self, request):
        return render(request, "accounts/login.html")


class RegisterView(View):
    def get(self, request):
        return render(request, "accounts/register.html")
