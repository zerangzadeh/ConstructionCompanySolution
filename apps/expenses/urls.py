from django.urls import path

from apps.expenses import views

app_name = "expenses"

urlpatterns = [
    path("", views.expense_list, name="list"),
    path("create/", views.expense_create, name="create"),
    path("draft/create/", views.expense_draft_create, name="draft_create"),
    path("categories/", views.expense_category_list, name="category_list"),
    path("categories/create/", views.expense_category_create, name="category_create"),
    path(
        "categories/<uuid:category_id>/",
        views.expense_category_detail,
        name="category_detail",
    ),
    path(
        "categories/<uuid:category_id>/archive/",
        views.expense_category_archive,
        name="category_archive",
    ),
    path(
        "platform-groups/",
        views.platform_expense_group_list,
        name="platform_group_list",
    ),
    path(
        "platform-groups/create/",
        views.platform_expense_group_create,
        name="platform_group_create",
    ),
    path(
        "platform-groups/<uuid:group_id>/",
        views.platform_expense_group_detail,
        name="platform_group_detail",
    ),
    path(
        "platform-groups/<uuid:group_id>/archive/",
        views.platform_expense_group_archive,
        name="platform_group_archive",
    ),
    path("recurrences/", views.recurrence_list, name="recurrences"),
    path(
        "recurrences/<uuid:template_id>/propose/",
        views.recurrence_propose,
        name="recurrence_propose",
    ),
    path("<uuid:expense_id>/", views.expense_detail, name="detail"),
    path("<uuid:expense_id>/allocate/", views.expense_allocate, name="allocate"),
    path("<uuid:expense_id>/submit/", views.expense_submit, name="submit"),
    path("<uuid:expense_id>/approve/", views.expense_approve, name="approve"),
    path("<uuid:expense_id>/return/", views.expense_return, name="return"),
    path("<uuid:expense_id>/void/", views.expense_void, name="void"),
]
