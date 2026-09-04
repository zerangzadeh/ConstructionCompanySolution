from django.urls import path

from apps.daily_reports import views

app_name = "daily_reports"

urlpatterns = [
    path("", views.daily_report_list, name="list"),
    path("create/", views.daily_report_create, name="create"),
    path("<uuid:report_id>/labor/", views.daily_report_labor_add, name="labor_add"),
    path(
        "<uuid:report_id>/equipment/",
        views.daily_report_equipment_add,
        name="equipment_add",
    ),
    path(
        "<uuid:report_id>/materials/",
        views.daily_report_material_add,
        name="material_add",
    ),
    path("<uuid:report_id>/activities/", views.daily_activity_add, name="activity_add"),
    path("<uuid:report_id>/delays/", views.delay_event_add, name="delay_add"),
    path("<uuid:report_id>/", views.daily_report_detail, name="detail"),
    path("<uuid:report_id>/submit/", views.daily_report_submit, name="submit"),
    path("<uuid:report_id>/approve/", views.daily_report_approve, name="approve"),
]
