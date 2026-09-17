from django.urls import path

from apps.inventory import views

app_name = "inventory"

urlpatterns = [
    path("", views.warehouse_list, name="warehouse_list"),
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
