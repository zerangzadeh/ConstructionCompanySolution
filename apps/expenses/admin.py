from django.contrib import admin
from django.http import HttpRequest

from apps.expenses.models import Expense


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        "description",
        "organization",
        "project",
        "phase",
        "category",
        "amount",
        "incurred_on",
        "status",
    )
    list_filter = ("category", "status", "organization")
    search_fields = (
        "description",
        "vendor_name",
        "receipt_reference",
        "project__name",
        "phase__name",
        "organization__name",
    )
    readonly_fields = ("id", "created_at", "updated_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Expenses must be recorded through the audited service workflow."""

        return False

    def has_change_permission(
        self, request: HttpRequest, obj: Expense | None = None
    ) -> bool:
        """Recorded expenses cannot be edited in the admin interface."""

        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: Expense | None = None
    ) -> bool:
        """Expense corrections use the audited void workflow, never deletion."""

        return False
