from django.urls import path

from .views import CheckResultListView

app_name = "checks"

urlpatterns = [
    path(
        "monitors/<int:monitor_id>/checks/",
        CheckResultListView.as_view(),
        name="check-list",
    ),
]
