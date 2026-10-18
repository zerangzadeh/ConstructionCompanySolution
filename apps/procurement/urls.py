from django.urls import path

from apps.procurement import rfq_actions, rfq_workspace, views

app_name = "procurement"

urlpatterns = [
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
    path("orders/", views.purchase_order_list, name="order_list"),
    path("orders/create/", views.purchase_order_create, name="order_create"),
    path("orders/<uuid:order_id>/", views.purchase_order_detail, name="order_detail"),
    path(
        "orders/<uuid:order_id>/items/",
        views.purchase_order_item_add,
        name="order_item_add",
    ),
    path(
        "orders/<uuid:order_id>/issue/", views.purchase_order_issue, name="order_issue"
    ),
    path(
        "orders/<uuid:order_id>/cancel/",
        views.purchase_order_cancel,
        name="order_cancel",
    ),
    path("receipts/", views.goods_receipt_list, name="receipt_list"),
    path("receipts/create/", views.goods_receipt_create, name="receipt_create"),
    path(
        "receipts/<uuid:receipt_id>/", views.goods_receipt_detail, name="receipt_detail"
    ),
    path(
        "receipts/<uuid:receipt_id>/items/",
        views.goods_receipt_item_add,
        name="receipt_item_add",
    ),
    path(
        "receipts/<uuid:receipt_id>/post/",
        views.goods_receipt_post,
        name="receipt_post",
    ),
    path(
        "receipts/<uuid:receipt_id>/void/",
        views.goods_receipt_void,
        name="receipt_void",
    ),
]
