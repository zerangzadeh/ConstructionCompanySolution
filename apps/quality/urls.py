from django.urls import path

from apps.quality import views

app_name = "quality"

urlpatterns = [
    path("", views.issue_list, name="list"),
    path("create/", views.issue_create, name="create"),
    path("<uuid:issue_id>/", views.issue_detail, name="detail"),
    path("<uuid:issue_id>/review/", views.issue_review, name="review"),
    path("<uuid:issue_id>/assign/", views.issue_assign, name="assign"),
    path(
        "<uuid:issue_id>/corrective-action/",
        views.corrective_action_start,
        name="corrective_action",
    ),
    path(
        "<uuid:issue_id>/submit-for-verification/",
        views.issue_submit_for_verification,
        name="submit_for_verification",
    ),
    path("<uuid:issue_id>/verify/", views.issue_verify, name="verify"),
    path("<uuid:issue_id>/close/", views.issue_close, name="close"),
]
