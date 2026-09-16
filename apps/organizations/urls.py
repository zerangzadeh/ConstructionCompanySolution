from django.urls import path

from apps.organizations import views

app_name = "organizations"

urlpatterns = [
    path("", views.select_organization, name="select"),
    path("create/", views.create_organization, name="create"),
    path("members/", views.organization_members, name="members"),
    path(
        "members/accounts/create/",
        views.organization_account_create,
        name="account_create",
    ),
    path(
        "members/<uuid:membership_id>/edit/",
        views.update_member,
        name="member_update",
    ),
    path(
        "members/<uuid:membership_id>/reset-password/",
        views.reset_member_password,
        name="member_password_reset",
    ),
    path("settings/", views.organization_settings, name="settings"),
    path("switch/", views.switch_organization, name="switch"),
]
