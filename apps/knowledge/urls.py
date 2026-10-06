from django.urls import path

from . import views

app_name = "knowledge"
urlpatterns = [
    path("", views.catalogue, name="catalogue"),
    path("candidates/", views.candidates, name="candidates"),
    path("candidates/create/", views.candidate_create, name="candidate_create"),
    path(
        "candidates/<uuid:candidate_id>/",
        views.candidate_detail,
        name="candidate_detail",
    ),
    path(
        "candidates/<uuid:candidate_id>/submit/",
        views.candidate_submit,
        name="candidate_submit",
    ),
    path(
        "candidates/<uuid:candidate_id>/review/",
        views.candidate_review,
        name="candidate_review",
    ),
    path(
        "candidates/<uuid:candidate_id>/approve/",
        views.candidate_approve,
        name="candidate_approve",
    ),
    path(
        "candidates/<uuid:candidate_id>/publish/",
        views.candidate_publish,
        name="candidate_publish",
    ),
    path(
        "publications/<uuid:version_id>/",
        views.publication_detail,
        name="publication_detail",
    ),
    path(
        "publications/<uuid:version_id>/withdraw/",
        views.publication_withdraw,
        name="publication_withdraw",
    ),
    path(
        "publications/<uuid:version_id>/correct/",
        views.publication_correct,
        name="publication_correct",
    ),
    path(
        "publications/<uuid:version_id>/history/",
        views.publication_history,
        name="publication_history",
    ),
    path(
        "publications/<uuid:version_id>/promote/",
        views.publication_promote,
        name="publication_promote",
    ),
    path("recurrence/", views.recurrence, name="recurrence"),
    path("recurrence/record/", views.recurrence_record, name="recurrence_record"),
    path(
        "recurrence/<uuid:recurrence_id>/correct/",
        views.recurrence_correct,
        name="recurrence_correct",
    ),
    path("reuse/", views.reuse, name="reuse"),
    path("reuse/record/", views.reuse_record, name="reuse_record"),
    path(
        "reuse/<uuid:reuse_id>/correct/",
        views.reuse_correct,
        name="reuse_correct",
    ),
    path("platform/promotions/", views.platform_promotions, name="platform_promotions"),
    path(
        "platform/promotions/<uuid:promotion_id>/review/",
        views.platform_promotion_review,
        name="platform_promotion_review",
    ),
    path(
        "platform/promotions/<uuid:promotion_id>/approve/",
        views.platform_promotion_approve,
        name="platform_promotion_approve",
    ),
    path(
        "platform/promotions/<uuid:promotion_id>/publish/",
        views.platform_promotion_publish,
        name="platform_promotion_publish",
    ),
]
