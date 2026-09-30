from django.urls import path

from apps.accounting import views

app_name = "accounting"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("accounts/", views.account_list, name="account_list"),
    path("accounts/create/", views.account_create, name="account_create"),
    path("periods/", views.period_list, name="period_list"),
    path("periods/year/create/", views.fiscal_year_create, name="fiscal_year_create"),
    path("periods/create/", views.fiscal_period_create, name="fiscal_period_create"),
    path("periods/<uuid:period_id>/close/", views.period_close, name="period_close"),
    path("periods/<uuid:period_id>/reopen/", views.period_reopen, name="period_reopen"),
    path("journals/", views.journal_list, name="journal_list"),
    path("journals/create/", views.journal_create, name="journal_create"),
    path(
        "journals/adjustment/create/",
        views.controlled_adjustment_create,
        name="controlled_adjustment_create",
    ),
    path("journals/<uuid:journal_id>/", views.journal_detail, name="journal_detail"),
    path(
        "journals/<uuid:journal_id>/line/",
        views.journal_line_add,
        name="journal_line_add",
    ),
    path(
        "journals/<uuid:journal_id>/submit/",
        views.journal_submit,
        name="journal_submit",
    ),
    path("journals/<uuid:journal_id>/post/", views.journal_post, name="journal_post"),
    path(
        "journals/<uuid:journal_id>/reverse/",
        views.journal_reverse,
        name="journal_reverse",
    ),
    path(
        "journals/<uuid:journal_id>/replacement/",
        views.journal_replacement,
        name="journal_replacement",
    ),
    path(
        "journals/<uuid:journal_id>/source/",
        views.journal_source,
        name="journal_source",
    ),
    path("openings/", views.opening_list, name="opening_list"),
    path("openings/create/", views.opening_create, name="opening_create"),
    path("openings/<uuid:opening_id>/", views.opening_detail, name="opening_detail"),
    path(
        "openings/<uuid:opening_id>/line/",
        views.opening_line_add,
        name="opening_line_add",
    ),
    path(
        "openings/<uuid:opening_id>/submit/",
        views.opening_submit,
        name="opening_submit",
    ),
    path(
        "openings/<uuid:opening_id>/accept/",
        views.opening_accept,
        name="opening_accept",
    ),
    path("reconciliations/", views.reconciliation_list, name="reconciliation_list"),
    path("reconciliations/run/", views.reconciliation_run, name="reconciliation_run"),
    path(
        "reconciliations/<uuid:run_id>/",
        views.reconciliation_detail,
        name="reconciliation_detail",
    ),
    path(
        "reconciliations/exceptions/<uuid:exception_id>/dispose/",
        views.reconciliation_dispose,
        name="reconciliation_dispose",
    ),
    path(
        "reconciliations/<uuid:run_id>/sign-off/",
        views.reconciliation_sign_off,
        name="reconciliation_sign_off",
    ),
    path("statements/", views.statement_list, name="statement_list"),
    path("statements/run/", views.statement_run, name="statement_run"),
    path(
        "statements/<uuid:run_id>/",
        views.statement_detail,
        name="statement_detail",
    ),
    path(
        "statements/<uuid:run_id>/accounts/<uuid:line_id>/",
        views.statement_account_ledger,
        name="statement_account_ledger",
    ),
]
