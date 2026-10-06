from django.urls import path

from apps.daily_reports import field_views, views

app_name = "daily_reports"

urlpatterns = [
    path("field/", field_views.field_observation_list, name="field_observation_list"),
    path("field/create/", field_views.field_observation_create, name="field_observation_create"),
    path("field/<uuid:observation_id>/", field_views.field_observation_detail, name="field_observation_detail"),
    path("field/<uuid:observation_id>/save/", field_views.field_observation_save, name="field_observation_save"),
    path("field/<uuid:observation_id>/evidence/", field_views.field_observation_evidence_add, name="field_observation_evidence_add"),
    path("field/<uuid:observation_id>/submit/", field_views.field_observation_submit, name="field_observation_submit"),
    path("field/<uuid:observation_id>/review/start/", field_views.field_observation_review_start, name="field_observation_review_start"),
    path("field/<uuid:observation_id>/review/<str:accepted>/", field_views.field_observation_review_decide, name="field_observation_review_decide"),
    path("field/<uuid:observation_id>/proposals/create/", field_views.field_proposal_create, name="field_proposal_create"),
    path("field/<uuid:observation_id>/proposals/<uuid:proposal_id>/submit/", field_views.field_proposal_submit, name="field_proposal_submit"),
    path("field/<uuid:observation_id>/proposals/<uuid:proposal_id>/review/<str:accepted>/", field_views.field_proposal_review, name="field_proposal_review"),
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
