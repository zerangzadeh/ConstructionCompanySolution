from django.urls import path

from apps.support import views

app_name = "support"
urlpatterns = [
    path("", views.workbench, name="workbench"),
    path("notifications/", views.workbench, name="notifications"),
    path(
        "notifications/<uuid:notification_id>/acknowledge/",
        views.acknowledge,
        name="acknowledge",
    ),
    path("calendar/", views.workbench, name="calendar"),
    path("cases/", views.workbench, name="cases"),
    path("cases/create/", views.case_create, name="case_create"),
    path("cases/<uuid:case_id>/", views.case_detail, name="case_detail"),
    path("cases/<uuid:case_id>/assign/", views.case_assign, name="case_assign"),
    path("cases/<uuid:case_id>/evidence/", views.case_evidence, name="case_evidence"),
    path(
        "cases/<uuid:case_id>/transition/",
        views.case_transition,
        name="case_transition",
    ),
    path("access/", views.workbench, name="access"),
    path("access/request/", views.access_request, name="access_request"),
    path("access/<uuid:request_id>/revoke/", views.access_revoke, name="access_revoke"),
    path(
        "access/<uuid:request_id>/confirm/", views.access_confirm, name="access_confirm"
    ),
    path(
        "access/<uuid:request_id>/approve/",
        views.access_confirm,
        {"platform": True},
        name="access_approve",
    ),
]
