from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AlertChannelViewSet, MonitorAlertViewSet

app_name = "notifications"

router = DefaultRouter()
router.register(r"alert-channels", AlertChannelViewSet, basename="alertchannel")
router.register(r"monitor-alerts", MonitorAlertViewSet, basename="monitoralert")

urlpatterns = [
    path("", include(router.urls)),
]
