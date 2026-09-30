from django.contrib import admin
from django.http import HttpRequest

from apps.accounting.models import (
    Account,
    FinancialStatementLineSnapshot,
    FinancialStatementRun,
    FiscalPeriod,
    FiscalPeriodControlEvent,
    FiscalYear,
    JournalEntry,
    JournalLine,
    OpeningBalanceImport,
    OpeningBalanceImportLine,
    ReconciliationExceptionDisposition,
    ReconciliationExceptionSnapshot,
    ReconciliationReview,
    ReconciliationRun,
    ReconciliationTieOutSnapshot,
)
from apps.organizations.authorization import has_business_permission
from apps.organizations.models import BusinessPermissionCode


class TenantReadOnlyAccountingAdmin(admin.ModelAdmin):
    """Admin inspection only: all accounting mutations use audited services/UI."""

    readonly_fields: tuple[str, ...] = ()

    def get_queryset(self, request: HttpRequest):
        queryset = super().get_queryset(request)
        organization = getattr(request, "organization", None)
        if organization is None or not has_business_permission(
            user=request.user,
            organization=organization,
            permission=BusinessPermissionCode.ACCOUNTING_VIEW,
        ):
            return queryset.none()
        return queryset.filter(organization=organization)

    def has_module_permission(self, request: HttpRequest) -> bool:
        organization = getattr(request, "organization", None)
        return bool(organization) and has_business_permission(
            user=request.user,
            organization=organization,
            permission=BusinessPermissionCode.ACCOUNTING_VIEW,
        )

    def has_view_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:
        organization = getattr(request, "organization", None)
        return (
            bool(organization)
            and has_business_permission(
                user=request.user,
                organization=organization,
                permission=BusinessPermissionCode.ACCOUNTING_VIEW,
            )
            and (
                obj is None or getattr(obj, "organization_id", None) == organization.pk
            )
        )

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


def _readonly_fields(model: object) -> tuple[str, ...]:
    return tuple(field.name for field in model._meta.fields)  # type: ignore[attr-defined]


@admin.register(Account)
class AccountAdmin(TenantReadOnlyAccountingAdmin):
    list_display = ("code", "name", "account_type", "is_posting", "organization")
    list_filter = ("account_type", "is_posting", "organization")
    search_fields = ("code", "name", "organization__name")
    readonly_fields = _readonly_fields(Account)


@admin.register(FiscalYear)
class FiscalYearAdmin(TenantReadOnlyAccountingAdmin):
    list_display = ("code", "name", "starts_on", "ends_on", "status", "organization")
    list_filter = ("status", "organization")
    readonly_fields = _readonly_fields(FiscalYear)


@admin.register(FiscalPeriod)
class FiscalPeriodAdmin(TenantReadOnlyAccountingAdmin):
    list_display = (
        "fiscal_year",
        "number",
        "name",
        "starts_on",
        "ends_on",
        "status",
        "organization",
    )
    list_filter = ("status", "organization")
    readonly_fields = _readonly_fields(FiscalPeriod)


@admin.register(JournalEntry)
class JournalEntryAdmin(TenantReadOnlyAccountingAdmin):
    list_display = (
        "number",
        "kind",
        "status",
        "accounting_date",
        "period",
        "organization",
    )
    list_filter = ("kind", "status", "organization")
    search_fields = ("source_key", "description", "organization__name")
    readonly_fields = _readonly_fields(JournalEntry)


for model in (
    JournalLine,
    OpeningBalanceImport,
    OpeningBalanceImportLine,
    ReconciliationRun,
    ReconciliationExceptionSnapshot,
    ReconciliationTieOutSnapshot,
    ReconciliationExceptionDisposition,
    ReconciliationReview,
    FinancialStatementRun,
    FinancialStatementLineSnapshot,
    FiscalPeriodControlEvent,
):
    admin.site.register(
        model,
        type(
            f"{model.__name__}Admin",
            (TenantReadOnlyAccountingAdmin,),
            {"readonly_fields": _readonly_fields(model)},
        ),
    )
