from django.urls import path

from apps.organizations import views

app_name = "organizations"

urlpatterns = [
    path("", views.select_organization, name="select"),
    path("create/", views.create_organization, name="create"),
    path("invite/", views.invite_member, name="invite"),
    path("accept-invitation/", views.accept_invitation, name="accept_invitation"),
    path("members/", views.organization_members, name="members"),
    path(
        "members/<uuid:membership_id>/edit/",
        views.update_member,
        name="member_update",
    ),
    path("settings/", views.organization_settings, name="settings"),
    path("switch/", views.switch_organization, name="switch"),
]
