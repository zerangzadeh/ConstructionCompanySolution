from django.urls import path

from apps.procurement import views

app_name = "procurement"

urlpatterns = [
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
