from django.contrib import admin

from apps.contracts.models import Contract


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = (
        "contract_number",
        "title",
        "organization",
        "project",
        "status",
        "contract_value",
    )
    list_filter = ("status", "organization")
    search_fields = (
        "contract_number",
        "title",
        "counterparty_name",
        "project__name",
        "organization__name",
    )
    readonly_fields = ("id", "created_at", "updated_at")
