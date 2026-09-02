from django.contrib import admin

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
