from django.urls import path

from apps.equipment import views

app_name = "equipment"

urlpatterns = [
    path("", views.equipment_list, name="list"),
    path("create/", views.equipment_create, name="create"),
    path("<uuid:equipment_id>/", views.equipment_detail, name="detail"),
    path(
        "<uuid:equipment_id>/status/",
        views.equipment_status_change,
        name="status_change",
    ),
    path("<uuid:equipment_id>/archive/", views.equipment_archive, name="archive"),
    path("assignments/", views.assignment_list, name="assignment_list"),
    path("assignments/create/", views.assignment_create, name="assignment_create"),
    path(
        "assignments/<uuid:assignment_id>/status/",
        views.assignment_status_change,
        name="assignment_status_change",
    ),
    path("maintenance/", views.maintenance_list, name="maintenance_list"),
    path("maintenance/create/", views.maintenance_create, name="maintenance_create"),
    path(
        "maintenance/<uuid:record_id>/status/",
        views.maintenance_status_change,
        name="maintenance_status_change",
    ),
]
