from django.urls import path

from apps.fixed_assets import views

app_name = "fixed_assets"

urlpatterns = [
    path(
        "transactions/<uuid:transaction_id>/",
        views.transaction_detail,
        name="transaction_detail",
    ),
    path("", views.workbench, name="workbench"),
    path("audit/", views.audit_evidence, name="audit_evidence"),
    path("assets/create/", views.asset_create, name="asset_create"),
    path("assets/<uuid:asset_id>/", views.asset_detail, name="asset_detail"),
    path("classes/create/", views.class_create, name="class_create"),
    path("books/create/", views.book_create, name="book_create"),
    path(
        "policies/<uuid:policy_id>/<str:kind>/<str:action>/",
        views.policy_transition,
        name="policy_transition",
    ),
    path(
        "assets/<uuid:asset_id>/sources/create/",
        views.source_create,
        name="source_create",
    ),
    path("sources/<uuid:source_id>/review/", views.source_review, name="source_review"),
    path(
        "assets/<uuid:asset_id>/capitalize/",
        views.asset_capitalize,
        name="asset_capitalize",
    ),
    path(
        "depreciation/preview/", views.depreciation_preview, name="depreciation_preview"
    ),
    path(
        "depreciation/<uuid:run_id>/finalize/",
        views.depreciation_finalize,
        name="depreciation_finalize",
    ),
    path(
        "depreciation/<uuid:run_id>/reverse/",
        views.depreciation_reverse,
        name="depreciation_reverse",
    ),
    path("transactions/create/", views.transaction_create, name="transaction_create"),
    path(
        "transactions/<uuid:transaction_id>/finalize/",
        views.transaction_finalize,
        name="transaction_finalize",
    ),
    path(
        "transactions/<uuid:transaction_id>/reverse/",
        views.transaction_reverse,
        name="transaction_reverse",
    ),
    path("handoffs/create/", views.handoff_create, name="handoff_create"),
    path(
        "handoffs/<uuid:envelope_id>/review/",
        views.handoff_review,
        name="handoff_review",
    ),
    path(
        "handoffs/<uuid:envelope_id>/reconcile/",
        views.handoff_reconcile,
        name="handoff_reconcile",
    ),
]
