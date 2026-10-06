from django.urls import path

from apps.inventory import p8_views, views

app_name = "inventory"

urlpatterns = [
    path("", views.warehouse_list, name="warehouse_list"),
    path("custody/", p8_views.custody_workbench, name="custody_workbench"),
    path("valuation/", p8_views.valuation_workbench, name="valuation_workbench"),
    path(
        "custody/reservations/new/",
        p8_views.reservation_create,
        name="reservation_create",
    ),
    path(
        "custody/reservations/<uuid:reservation_id>/release/",
        p8_views.reservation_release,
        name="reservation_release",
    ),
    path("custody/counts/new/", p8_views.count_create, name="count_create"),
    path("custody/counts/<uuid:count_id>/", p8_views.count_detail, name="count_detail"),
    path(
        "custody/counts/<uuid:count_id>/approve/",
        p8_views.count_approve,
        name="count_approve",
    ),
    path(
        "custody/counts/<uuid:count_id>/post/",
        p8_views.count_post,
        name="count_post",
    ),
    path("custody/transfers/new/", p8_views.transfer_create, name="transfer_create"),
    path(
        "custody/transfers/<uuid:transfer_id>/",
        p8_views.transfer_detail,
        name="transfer_detail",
    ),
    path(
        "custody/transfers/<uuid:transfer_id>/dispatch/",
        p8_views.transfer_dispatch,
        name="transfer_dispatch",
    ),
    path(
        "custody/transfers/<uuid:transfer_id>/in-transit/",
        p8_views.transfer_in_transit,
        name="transfer_in_transit",
    ),
    path(
        "custody/transfers/<uuid:transfer_id>/accept/",
        p8_views.transfer_accept,
        name="transfer_accept",
    ),
    path("create/", views.warehouse_create, name="warehouse_create"),
    path("<uuid:warehouse_id>/", views.warehouse_detail, name="warehouse_detail"),
    path(
        "<uuid:warehouse_id>/archive/",
        views.warehouse_archive,
        name="warehouse_archive",
    ),
    path("transactions/", views.transaction_list, name="transaction_list"),
    path("transactions/create/", views.transaction_create, name="transaction_create"),
    path(
        "transactions/<uuid:transaction_id>/",
        views.transaction_detail,
        name="transaction_detail",
    ),
    path(
        "transactions/<uuid:transaction_id>/post/",
        views.transaction_post,
        name="transaction_post",
    ),
    path(
        "transactions/<uuid:transaction_id>/request-posting/",
        views.transaction_request_posting,
        name="transaction_request_posting",
    ),
    path(
        "transactions/<uuid:transaction_id>/reverse/",
        views.transaction_reverse,
        name="transaction_reverse",
    ),
    path(
        "transactions/<uuid:transaction_id>/request-reversal/",
        views.transaction_request_reversal,
        name="transaction_request_reversal",
    ),
]
