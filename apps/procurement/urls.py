from django.urls import path

from apps.procurement import (
    commercial_scope_views,
    order_workspace,
    receipt_workspace,
    request_ui,
    rfq_actions,
    rfq_ui,
    rfq_workspace,
    views,
)

app_name = "procurement"

urlpatterns = [
    path(
        "rfqs/<uuid:rfq_id>/scope/",
        commercial_scope_views.scope_define,
        name="rfq_scope_define",
    ),
    path(
        "rfqs/<uuid:rfq_id>/addendum/",
        commercial_scope_views.rfq_addendum,
        name="rfq_addendum",
    ),
    path(
        "requests/choices/<slug:field>/",
        request_ui.request_choices,
        name="request_choices",
    ),
    path("rfqs/choices/<slug:field>/", rfq_ui.rfq_choices, name="rfq_choices"),
    path("rfqs/", rfq_workspace.rfq_list, name="rfq_list"),
    path("rfqs/create/", rfq_workspace.rfq_create, name="rfq_create"),
    path("rfqs/<uuid:rfq_id>/", rfq_workspace.rfq_detail, name="rfq_detail"),
    path(
        "rfqs/<uuid:rfq_id>/buyer/",
        rfq_actions.buyer_workspace,
        name="rfq_buyer_workspace",
    ),
    path(
        "rfqs/<uuid:rfq_id>/buyer/<slug:action>/",
        rfq_actions.buyer_action,
        name="rfq_buyer_action",
    ),
    path(
        "rfqs/<uuid:rfq_id>/buyer/documents/<uuid:evidence_id>/",
        rfq_actions.buyer_document,
        name="rfq_buyer_document",
    ),
    path("rfqs/<uuid:rfq_id>/lines/", rfq_workspace.rfq_line_add, name="rfq_line_add"),
    path("rfqs/<uuid:rfq_id>/submit/", rfq_workspace.rfq_submit, name="rfq_submit"),
    path("rfqs/<uuid:rfq_id>/issue/", rfq_workspace.rfq_issue, name="rfq_issue"),
    path("rfqs/<uuid:rfq_id>/close/", rfq_workspace.rfq_close, name="rfq_close"),
    path("rfqs/<uuid:rfq_id>/cancel/", rfq_workspace.rfq_cancel, name="rfq_cancel"),
    path("portal/accept/", views.supplier_portal_accept, name="portal_accept"),
    path(
        "portal/grants/<uuid:grant_id>/",
        views.supplier_portal_context,
        name="portal_context",
    ),
    path(
        "portal/grants/<uuid:grant_id>/submit/",
        views.supplier_portal_submit,
        name="portal_submit",
    ),
    path(
        "portal/receipts/<uuid:receipt_id>/",
        views.supplier_portal_receipt,
        name="portal_receipt",
    ),
    path(
        "rfq-invitations/<uuid:invitation_id>/portal/",
        views.portal_invitation_manage,
        name="portal_invitation_manage",
    ),
    path(
        "rfq-invitations/<uuid:invitation_id>/portal/revoke/<uuid:grant_id>/",
        views.portal_grant_revoke,
        name="portal_grant_revoke",
    ),
    path(
        "quote-revisions/<uuid:revision_id>/sealed-evidence/",
        views.sealed_evidence_custody,
        name="sealed_evidence_custody",
    ),
    path("", views.purchase_request_list, name="request_list"),
    path("requests/create/", views.purchase_request_create, name="request_create"),
    path(
        "requests/<uuid:request_id>/",
        views.purchase_request_detail,
        name="request_detail",
    ),
    path(
        "requests/<uuid:request_id>/items/",
        views.purchase_request_item_add,
        name="request_item_add",
    ),
    path(
        "requests/<uuid:request_id>/submit/",
        views.purchase_request_submit,
        name="request_submit",
    ),
    path(
        "requests/<uuid:request_id>/approve/",
        views.purchase_request_approve,
        name="request_approve",
    ),
    path(
        "requests/<uuid:request_id>/reject/",
        views.purchase_request_reject,
        name="request_reject",
    ),
    path(
        "requests/<uuid:request_id>/cancel/",
        views.purchase_request_cancel,
        name="request_cancel",
    ),
    path(
        "orders/choices/<slug:purpose>/<slug:field>/",
        order_workspace.order_choices,
        name="order_choices",
    ),
    path(
        "orders/from-award/<uuid:award_id>/",
        order_workspace.order_from_award,
        name="order_from_award",
    ),
    path("orders/", order_workspace.order_list, name="order_list"),
    path("orders/create/", views.purchase_order_create, name="order_create"),
    path("orders/<uuid:order_id>/", order_workspace.order_detail, name="order_detail"),
    path(
        "orders/<uuid:order_id>/items/",
        order_workspace.order_item_add,
        name="order_item_add",
    ),
    path(
        "orders/<uuid:order_id>/issue/", order_workspace.order_issue, name="order_issue"
    ),
    path(
        "orders/<uuid:order_id>/cancel/",
        order_workspace.order_cancel,
        name="order_cancel",
    ),
    path(
        "receipts/choices/<slug:purpose>/<slug:field>/",
        receipt_workspace.receipt_choices,
        name="receipt_choices",
    ),
    path("receipts/", receipt_workspace.receipt_list, name="receipt_list"),
    path("receipts/create/", receipt_workspace.receipt_create, name="receipt_create"),
    path(
        "receipts/<uuid:receipt_id>/",
        receipt_workspace.receipt_detail,
        name="receipt_detail",
    ),
    path(
        "receipts/<uuid:receipt_id>/items/",
        receipt_workspace.receipt_item_add,
        name="receipt_item_add",
    ),
    path(
        "receipts/<uuid:receipt_id>/post/",
        receipt_workspace.receipt_post,
        name="receipt_post",
    ),
    path(
        "receipts/<uuid:receipt_id>/void/",
        receipt_workspace.receipt_void,
        name="receipt_void",
    ),
]
