from django.urls import path

from apps.subledgers import views

app_name = "subledgers"

urlpatterns = [
    path(
        "obligations/<uuid:obligation_id>/",
        views.obligation_detail,
        name="obligation_detail",
    ),
    path("", views.workbench, name="workbench"),
    path(
        "supplier-invoice-matches/",
        views.supplier_invoice_match_review,
        name="supplier_invoice_match_review",
    ),
    path(
        "supplier-invoice-matches/<uuid:match_id>/",
        views.supplier_invoice_match_review,
        name="supplier_invoice_match_detail",
    ),
    path("obligations/<uuid:obligation_id>/allocate/", views.allocate, name="allocate"),
    path(
        "allocations/<uuid:allocation_id>/reverse/",
        views.reverse_allocation,
        name="reverse_allocation",
    ),
    path(
        "obligations/<uuid:obligation_id>/write-off/",
        views.propose_writeoff,
        name="propose_writeoff",
    ),
    path("aging/", views.aging, name="aging"),
    path("reconciliations/", views.reconcile, name="reconcile"),
    path(
        "reconciliations/<uuid:run_id>/review/",
        views.review_reconciliation,
        name="review_reconciliation",
    ),
]
