from django.urls import path

from apps.safety import views

app_name = "safety"

urlpatterns = [
    path("", views.incident_list, name="list"),
    path("create/", views.incident_create, name="create"),
    path("<uuid:incident_id>/", views.incident_detail, name="detail"),
    path("<uuid:incident_id>/review/", views.incident_review, name="review"),
    path("<uuid:incident_id>/assign/", views.incident_assign, name="assign"),
    path(
        "<uuid:incident_id>/corrective-action/",
        views.corrective_action_start,
        name="corrective_action",
    ),
    path("<uuid:incident_id>/resolve/", views.incident_resolve, name="resolve"),
    path("<uuid:incident_id>/close/", views.incident_close, name="close"),
]
