from django.urls import path

from apps.treasury import operational_views, views

app_name = "treasury"

urlpatterns = [
    path(
        "operations/records/<str:resource>/<uuid:object_id>/",
        operational_views.detail,
        name="operational_detail",
    ),
    path("operations/", operational_views.workspace, name="operations"),
    path("operations/<str:operation>/", operational_views.operation, name="operation"),
    path(
        "operations/<str:operation>/<uuid:object_id>/",
        operational_views.operation,
        name="object_operation",
    ),
    path("movements/new/", views.movement_create, name="movement_create"),
    path(
        "movements/<uuid:movement_id>/", views.movement_detail, name="movement_detail"
    ),
    path(
        "movements/<uuid:movement_id>/submit/",
        views.movement_submit,
        name="movement_submit",
    ),
    path(
        "movements/<uuid:movement_id>/post/", views.movement_post, name="movement_post"
    ),
    path(
        "movements/<uuid:movement_id>/reverse/",
        views.movement_reverse,
        name="movement_reverse",
    ),
    path("", views.workbench, name="workbench"),
    path("statements/", views.statement_workbench, name="statement_workbench"),
    path(
        "statements/lines/<uuid:line_id>/suggest/",
        views.suggest_match,
        name="suggest_match",
    ),
    path(
        "statements/proposals/<uuid:proposal_id>/confirm/",
        views.confirm_match,
        name="confirm_match",
    ),
    path(
        "statements/proposals/<uuid:proposal_id>/reject/",
        views.reject_match,
        name="reject_match",
    ),
    path(
        "statements/clearings/<uuid:clearing_id>/reverse/",
        views.reverse_clearing,
        name="reverse_clearing",
    ),
    path(
        "statements/imports/<uuid:import_id>/reconcile/",
        views.bank_reconcile,
        name="bank_reconcile",
    ),
    path(
        "reconciliations/<uuid:run_id>/review/",
        views.review_gl_reconciliation,
        name="review_gl_reconciliation",
    ),
]
