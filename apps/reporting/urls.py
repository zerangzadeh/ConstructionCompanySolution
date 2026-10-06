from django.urls import path

from apps.reporting import views

app_name = "reporting"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("refresh/<slug:metric_code>/", views.refresh, name="refresh"),
    path("results/<uuid:result_id>/sources/", views.drillthrough, name="drillthrough"),
    path("export/", views.export_csv, name="export"),
]
