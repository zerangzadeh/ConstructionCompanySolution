from typing import ClassVar

from django.db import migrations

WORKFORCE_GENERAL_CODES = {
    "workforce_skills.view",
    "workforce_skills.manage",
    "workforce_qualifications.view",
    "workforce_qualifications.manage",
    "workforce_qualifications.revoke",
}
TIME_VIEW_CODES = {
    "time_calendars.view",
    "attendance.view",
    "leave_mission.view",
    "overtime.view",
    "timesheets.view",
}
TIME_PREPARE_CODES = {
    "attendance.capture",
    "leave_mission.request",
    "overtime.request",
    "timesheets.prepare",
}
TIME_REVIEW_CODES = {
    "attendance.review",
    "leave_mission.review",
    "overtime.review",
    "timesheets.review",
    "timesheets.preview",
}
WORKFORCE_MANAGEMENT_ROLES = {
    "tenant_owner",
    "company_owner",
    "tenant_admin",
    "tenant_manager",
    "project_manager",
    "company_manager",
    "operations_manager",
}
TIME_GRANTS = {
    "tenant_owner": TIME_VIEW_CODES
    | TIME_PREPARE_CODES
    | TIME_REVIEW_CODES
    | {"time_calendars.manage", "attendance.correct", "attendance.import"},
    "company_owner": TIME_VIEW_CODES
    | TIME_PREPARE_CODES
    | TIME_REVIEW_CODES
    | {"time_calendars.manage", "attendance.correct", "attendance.import"},
    "tenant_admin": TIME_VIEW_CODES
    | TIME_PREPARE_CODES
    | TIME_REVIEW_CODES
    | {"time_calendars.manage", "attendance.correct", "attendance.import"},
    "tenant_manager": TIME_VIEW_CODES | TIME_PREPARE_CODES | TIME_REVIEW_CODES,
    "project_manager": TIME_VIEW_CODES | TIME_PREPARE_CODES | TIME_REVIEW_CODES,
    "company_manager": TIME_VIEW_CODES | TIME_PREPARE_CODES | TIME_REVIEW_CODES,
    "operations_manager": TIME_VIEW_CODES | TIME_PREPARE_CODES | TIME_REVIEW_CODES,
    "supervisor": TIME_VIEW_CODES | TIME_PREPARE_CODES,
    "member": TIME_VIEW_CODES,
    "viewer": TIME_VIEW_CODES,
}


def forward(apps, schema_editor):
    """Reconcile pre-existing global roles after the P7 permission rollout.

    The P7 sensitive Payroll and statutory catalog entries are deliberately not
    included: they still require an explicit tenant-specific role assignment.
    """

    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    permission_codes = WORKFORCE_GENERAL_CODES | set().union(*TIME_GRANTS.values())
    permissions = {
        permission.code: permission
        for permission in Permission.objects.filter(
            code__in=permission_codes,
            is_active=True,
        )
    }
    for role in Role.objects.filter(organization__isnull=True):
        grant_codes = set()
        if role.code in WORKFORCE_MANAGEMENT_ROLES:
            grant_codes |= WORKFORCE_GENERAL_CODES
        grant_codes |= TIME_GRANTS.get(role.code, set())
        role.permissions.add(*(permissions[code] for code in grant_codes))


def reverse(apps, schema_editor):
    del apps, schema_editor
    # This is a forward-only reconciliation. Removing grants could discard
    # intentional tenant administration decisions made after the rollout.


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [
        ("organizations", "0094_p7_s29_s32_payroll_handoff_permissions"),
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
