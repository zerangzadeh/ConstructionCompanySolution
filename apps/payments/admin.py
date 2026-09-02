from django.contrib import admin

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
