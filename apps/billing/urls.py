from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("baselines/", views.baseline_list, name="baseline_list"),
    path(
        "baselines/<uuid:baseline_id>/", views.baseline_detail, name="baseline_detail"
    ),
    path("progress/", views.progress_list, name="progress_list"),
    path("progress/<uuid:record_id>/", views.progress_detail, name="progress_detail"),
    path(
        "progress/<uuid:record_id>/submit/",
        views.progress_submit,
        name="progress_submit",
    ),
    path(
        "progress/<uuid:record_id>/verify/",
        views.progress_verify,
        name="progress_verify",
    ),
    path(
        "progress/<uuid:record_id>/reject/",
        views.progress_reject,
        name="progress_reject",
    ),
    path("claims/", views.claim_list, name="claim_list"),
    path("claims/recovery/", views.recovery_guidance, name="recovery_guidance"),
    path("claims/<uuid:claim_id>/", views.claim_detail, name="claim_detail"),
    path(
        "claims/<uuid:claim_id>/settlements/",
        views.claim_settlement_allocate,
        name="claim_settlement_allocate",
    ),
]
