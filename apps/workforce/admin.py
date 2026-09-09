from django.contrib import admin
from django.http import HttpRequest

from apps.workforce.models import (
    Department,
    Employee,
    EmployeeProjectAssignment,
    Position,
    WorkTeam,
)


class ReadOnlyWorkforceAdmin(admin.ModelAdmin):
    readonly_fields = ("id", "created_at", "updated_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:
        return False


@admin.register(Department)
class DepartmentAdmin(ReadOnlyWorkforceAdmin):
    list_display = ("code", "name", "parent", "organization", "is_active")
    list_filter = ("organization", "is_active")
    search_fields = ("code", "name", "organization__name")
    list_select_related = ("parent", "organization")


@admin.register(Position)
class PositionAdmin(ReadOnlyWorkforceAdmin):
    list_display = ("code", "title", "department", "organization", "is_active")
    list_filter = ("organization", "department", "is_active")
    search_fields = ("code", "title", "organization__name")
    list_select_related = ("department", "organization")


@admin.register(WorkTeam)
class WorkTeamAdmin(ReadOnlyWorkforceAdmin):
    list_display = ("code", "name", "department", "lead", "organization", "is_active")
    list_filter = ("organization", "department", "is_active")
    search_fields = ("code", "name", "lead__employee_number")
    list_select_related = ("department", "lead", "organization")


@admin.register(Employee)
class EmployeeAdmin(ReadOnlyWorkforceAdmin):
    list_display = (
        "employee_number",
        "first_name",
        "last_name",
        "department",
        "position",
        "work_team",
        "status",
        "organization",
    )
    list_filter = ("organization", "status", "department", "position", "work_team")
    search_fields = ("employee_number", "first_name", "last_name", "user__username")
    list_select_related = (
        "user",
        "department",
        "position",
        "work_team",
        "organization",
    )


@admin.register(EmployeeProjectAssignment)
class EmployeeProjectAssignmentAdmin(ReadOnlyWorkforceAdmin):
    list_display = (
        "employee",
        "project",
        "site",
        "role_title",
        "start_date",
        "end_date",
        "status",
        "organization",
    )
    list_filter = ("organization", "project", "site", "status")
    search_fields = (
        "employee__employee_number",
        "employee__first_name",
        "employee__last_name",
        "project__code",
    )
    list_select_related = ("employee", "project", "site", "organization")
