"""Private monitors API URLs."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MonitorViewSet

app_name = "monitors"

router = DefaultRouter()
router.register(r"monitors", MonitorViewSet, basename="monitor")

urlpatterns = [
    path("", include(router.urls)),
]
