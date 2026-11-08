from django.urls import path

from apps.accounts import platform_user_views
from apps.organizations import platform_console, platform_views, views
from apps.organizations.reference_personas import reference_persona_catalogue

app_name = "organizations"

urlpatterns = [
    path("platform/", platform_console.dashboard, name="platform_dashboard"),
    path("platform/users/", platform_user_views.directory, name="platform_users"),
    path(
        "platform/users/create/",
        platform_user_views.account_form,
        name="platform_user_create",
    ),
    path(
        "platform/users/<uuid:user_id>/",
        platform_user_views.detail,
        name="platform_user_detail",
    ),
    path(
        "platform/users/<uuid:user_id>/edit/",
        platform_user_views.account_form,
        name="platform_user_edit",
    ),
    path(
        "platform/users/<uuid:user_id>/status/",
        platform_user_views.change_status,
        name="platform_user_status",
    ),
    path(
        "platform/users/<uuid:user_id>/reset-password/",
        platform_user_views.reset_password,
        name="platform_user_reset",
    ),
    path(
        "platform/users/<uuid:user_id>/temporary-password/",
        platform_user_views.temporary_password,
        name="platform_user_temporary_password",
    ),
    path(
        "platform/administrators/",
        platform_console.administrators,
        name="platform_administrators",
    ),
    path(
        "platform/member-roles/",
        platform_console.member_roles,
        name="platform_member_roles",
    ),
    path(
        "platform/companies/<uuid:organization_id>/members/<uuid:membership_id>/roles/",
        platform_console.member_authorization,
        name="platform_member_authorization",
    ),
    path(
        "platform/settings/",
        platform_console.platform_settings,
        name="platform_settings",
    ),
    path("platform/activity/", platform_console.audit_log, name="platform_audit"),
    path("platform/status/", platform_console.system_status, name="platform_status"),
    path(
        "platform/companies/<uuid:organization_id>/onboarding/",
        platform_views.company_onboarding,
        name="platform_company_onboarding",
    ),
    path(
        "platform/companies/", platform_views.company_list, name="platform_company_list"
    ),
    path(
        "platform/companies/<uuid:organization_id>/",
        platform_views.company_detail,
        name="platform_company_detail",
    ),
    path(
        "platform/companies/<uuid:organization_id>/edit/",
        platform_views.company_edit,
        name="platform_company_edit",
    ),
    path(
        "platform/companies/<uuid:organization_id>/status/",
        platform_views.company_status,
        name="platform_company_status",
    ),
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
