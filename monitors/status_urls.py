"""Public status page HTML URLs — /status/<slug>/."""

from django.urls import path

from .status_views import PublicStatusPageView

app_name = "status"

urlpatterns = [
    path("<slug:slug>/", PublicStatusPageView.as_view(), name="public-page"),
]
