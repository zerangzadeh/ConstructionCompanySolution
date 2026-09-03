from django.contrib import admin
from django.http import HttpRequest

from apps.payments.models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "payment_number",
        "organization",
        "project",
        "direction",
        "amount",
        "paid_on",
        "status",
    )
    list_filter = ("direction", "method", "status", "organization")
    search_fields = (
        "payment_number",
        "counterparty_name",
        "reference",
        "project__name",
        "contract__contract_number",
        "organization__name",
    )
    readonly_fields = ("id", "created_at", "updated_at", "voided_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Payments must be created through the audited service workflow."""

        return False

    def has_change_permission(
        self, request: HttpRequest, obj: Payment | None = None
    ) -> bool:
        """Posted financial records cannot be edited in the admin interface."""

        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: Payment | None = None
    ) -> bool:
        """Financial corrections use the audited void workflow, never deletion."""

        return False
