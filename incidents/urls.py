from django.urls import path

from .views import IncidentListView

app_name = "incidents"

urlpatterns = [
    path(
        "monitors/<int:monitor_id>/incidents/",
        IncidentListView.as_view(),
        name="incident-list",
    ),
]
