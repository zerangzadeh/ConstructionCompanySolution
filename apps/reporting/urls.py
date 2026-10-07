from django.urls import path

from apps.reporting import views

app_name = "reporting"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("refresh/<slug:metric_code>/", views.refresh, name="refresh"),
    path("results/<uuid:result_id>/sources/", views.drillthrough, name="drillthrough"),
    path("export/", views.export_csv, name="export"),
    path(
        "reconciliations/",
        views.reconciliation_workbench,
        name="reconciliation_workbench",
    ),
    path(
        "reconciliations/run/<slug:pair_code>/",
        views.reconciliation_execute,
        name="reconciliation_execute",
    ),
    path(
        "reconciliations/<uuid:run_id>/",
        views.reconciliation_detail,
        name="reconciliation_detail",
    ),
    path(
        "reconciliations/<uuid:run_id>/replay/",
        views.reconciliation_replay,
        name="reconciliation_replay",
    ),
    path(
        "reconciliation-exceptions/<uuid:exception_id>/<slug:action>/",
        views.reconciliation_exception_action,
        name="reconciliation_exception_action",
    ),
    path(
        "project-closeout/",
        views.project_closeout_workbench,
        name="project_closeout_workbench",
    ),
    path(
        "project-closeout/create/",
        views.project_closeout_create,
        name="project_closeout_create",
    ),
    path(
        "project-closeout/<uuid:case_id>/",
        views.project_closeout_detail,
        name="project_closeout_detail",
    ),
    path(
        "project-closeout/<uuid:case_id>/assess/",
        views.project_closeout_assess,
        name="project_closeout_assess",
    ),
    path(
        "project-closeout/<uuid:case_id>/coordinate/",
        views.project_closeout_coordinate,
        name="project_closeout_coordinate",
    ),
    path(
        "project-closeout/<uuid:case_id>/decide/<slug:decision>/",
        views.project_closeout_decide,
        name="project_closeout_decide",
    ),
    path(
        "project-closeout/<uuid:case_id>/reopen/",
        views.project_closeout_reopen,
        name="project_closeout_reopen",
    ),
    path(
        "project-closeout/<uuid:case_id>/evidence/",
        views.project_closeout_evidence,
        name="project_closeout_evidence",
    ),
    path(
        "project-closeout/<uuid:case_id>/export/",
        views.project_closeout_export,
        name="project_closeout_export",
    ),
]
