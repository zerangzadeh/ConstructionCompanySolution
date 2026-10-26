from django.urls import path

from apps.organizations import views
from apps.organizations.reference_personas import reference_persona_catalogue

app_name = "organizations"

urlpatterns = [
    path(
        "platform/reference-personas/",
        reference_persona_catalogue,
        name="reference_personas",
    ),
    path("members/<uuid:membership_id>/", views.member_detail, name="member_detail"),
    path("", views.select_organization, name="select"),
    path("create/", views.create_organization, name="create"),
    path("members/", views.organization_members, name="members"),
    path("roles/", views.role_catalog, name="role_catalog"),
    path("platform/roles/", views.platform_role_catalog, name="platform_role_catalog"),
    path(
        "platform/protected-operations/",
        views.protected_operation_catalog,
        name="protected_operation_catalog",
    ),
    path(
        "platform/accounting-policies/",
        views.platform_policy_catalog,
        name="platform_policy_catalog",
    ),
    path(
        "policies/",
        views.tenant_policy_configuration,
        name="tenant_policy_configuration",
    ),
    path(
        "configuration-profiles/",
        views.configuration_profiles,
        name="configuration_profiles",
    ),
    path(
        "members/<uuid:membership_id>/profile-image/",
        views.member_profile_image,
        name="member_profile_image",
    ),
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
        "members/<uuid:membership_id>/authorization/",
        views.member_authorization,
        name="member_authorization",
    ),
    path(
        "members/<uuid:membership_id>/reset-password/",
        views.reset_member_password,
        name="member_password_reset",
    ),
    path("settings/", views.organization_settings, name="settings"),
    path("switch/", views.switch_organization, name="switch"),
    path("context/", views.update_context, name="update_context"),
    path(
        "context/form-options/",
        views.form_context_options,
        name="form_context_options",
    ),
]
