from django.urls import path

from apps.treasury import views

app_name = "treasury"

urlpatterns = [
    path("", views.workbench, name="workbench"),
    path("statements/", views.statement_workbench, name="statement_workbench"),
    path("statements/lines/<uuid:line_id>/suggest/", views.suggest_match, name="suggest_match"),
    path("statements/proposals/<uuid:proposal_id>/confirm/", views.confirm_match, name="confirm_match"),
    path("statements/proposals/<uuid:proposal_id>/reject/", views.reject_match, name="reject_match"),
    path("statements/clearings/<uuid:clearing_id>/reverse/", views.reverse_clearing, name="reverse_clearing"),
    path("statements/imports/<uuid:import_id>/reconcile/", views.bank_reconcile, name="bank_reconcile"),
    path(
        "reconciliations/<uuid:run_id>/review/",
        views.review_gl_reconciliation,
        name="review_gl_reconciliation",
    ),
]
