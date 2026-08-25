"""Public API URLs (no auth required)."""

from django.urls import path

from .public_views import PublicStatusAPIView

app_name = "monitors-public"

urlpatterns = [
    path("status/<slug:slug>/", PublicStatusAPIView.as_view(), name="status-api"),
]
