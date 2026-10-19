from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch
from django.utils import timezone

from apps.accounts.models import User
from apps.contracts.models import Contract
from apps.estimates.models import Estimate, EstimateStatus
from apps.expenses.models import Expense, ExpenseStatus
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import (
    BusinessPermissionCode,
    Organization,
    OrganizationStatus,
)
from apps.projects.models import Project
from apps.treasury.models import (
    TreasuryMovement,
    TreasuryMovementKind,
    TreasuryMovementStatus,
)

ZERO = Decimal("0.00")


@dataclass(frozen=True)
class ProjectFinancialReport:
    project: Project
    approved_estimate_total: Decimal
    recorded_expense_total: Decimal
    variance: Decimal
    approved_estimate_count: int
    recorded_expense_count: int
    receipt_total: Decimal
    disbursement_total: Decimal
    net_cash_flow: Decimal
    posted_movement_count: int
    cash_source_references: tuple[tuple[str, int, str], ...]
    cash_cutoff: datetime


@dataclass(frozen=True)
class OrganizationDashboard:
    project_count: int
    contract_count: int
    estimate_count: int
    approved_estimate_total: Decimal
    recorded_expense_total: Decimal
    variance: Decimal
    receipt_total: Decimal
    disbursement_total: Decimal
    net_cash_flow: Decimal
    posted_movement_count: int
    cash_cutoff: datetime


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _validate_view_context(user: User, organization: Organization) -> None:
    if not user.is_authenticated:
        raise PermissionDenied("ورود به حساب کاربری الزامی است.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("سازمان فعال نیست.")
    require_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.FINANCIALS_VIEW,
        message="اجازه مشاهده گزارش‌های مالی این سازمان را ندارید.",
    )
    require_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_VIEW,
        message="مشاهده جریان نقد به مجوز خزانه‌داری همین سازمان نیاز دارد.",
    )


def _build_report(project: Project, *, cash_cutoff: datetime) -> ProjectFinancialReport:
    approved_estimates = list(project.estimates.all())
    recorded_expenses = list(project.expenses.all())
    posted_movements = project.cash_movements
    estimate_total = _money(
        sum((estimate.total_amount for estimate in approved_estimates), ZERO)
    )
    expense_total = _money(sum((expense.amount for expense in recorded_expenses), ZERO))
    # Project already-approved cash amounts exactly; presentation cannot choose
    # a second monetary precision or rounding policy for Treasury.
    receipt_total = sum(
        (
            movement.amount
            for movement in posted_movements
            if movement.kind == TreasuryMovementKind.RECEIPT
        ),
        ZERO,
    )
    disbursement_total = sum(
        (
            movement.amount
            for movement in posted_movements
            if movement.kind == TreasuryMovementKind.DISBURSEMENT
        ),
        ZERO,
    )
    return ProjectFinancialReport(
        project=project,
        approved_estimate_total=estimate_total,
        recorded_expense_total=expense_total,
        variance=_money(estimate_total - expense_total),
        approved_estimate_count=len(approved_estimates),
        recorded_expense_count=len(recorded_expenses),
        receipt_total=receipt_total,
        disbursement_total=disbursement_total,
        net_cash_flow=receipt_total - disbursement_total,
        posted_movement_count=len(posted_movements),
        cash_source_references=tuple(
            (str(m.pk), m.version, str(m.journal_id)) for m in posted_movements
        ),
        cash_cutoff=cash_cutoff,
    )


def get_project_financial_report(
    *,
    user: User,
    organization: Organization,
    project_id: str,
) -> ProjectFinancialReport:
    """Build one tenant-scoped financial report for a project."""

    _validate_view_context(user, organization)
    cash_cutoff = timezone.now()
    project = (
        Project.objects.filter(
            pk=project_id,
            organization=organization,
            deleted_at__isnull=True,
        )
        .prefetch_related(
            Prefetch(
                "estimates",
                queryset=Estimate.objects.filter(
                    status=EstimateStatus.APPROVED,
                    deleted_at__isnull=True,
                ).prefetch_related("items"),
            ),
            Prefetch(
                "expenses",
                queryset=Expense.objects.filter(
                    status__in=(ExpenseStatus.RECORDED, ExpenseStatus.APPROVED),
                    deleted_at__isnull=True,
                ),
            ),
            Prefetch(
                "treasurymovement_set",
                queryset=TreasuryMovement.objects.filter(
                    organization=organization,
                    status=TreasuryMovementStatus.POSTED,
                    posted_at__lte=cash_cutoff,
                    kind__in=(
                        TreasuryMovementKind.RECEIPT,
                        TreasuryMovementKind.DISBURSEMENT,
                    ),
                    reverses__isnull=True,
                    reversal_movement__isnull=True,
                ),
                to_attr="cash_movements",
            ),
        )
        .first()
    )
    if project is None:
        raise PermissionDenied("پروژه در این سازمان یافت نشد.")
    return _build_report(project, cash_cutoff=cash_cutoff)


def get_organization_financial_reports(
    *,
    user: User,
    organization: Organization,
) -> list[ProjectFinancialReport]:
    """Build tenant-scoped financial reports for all active projects."""

    _validate_view_context(user, organization)
    cash_cutoff = timezone.now()
    projects = (
        Project.objects.filter(
            organization=organization,
            deleted_at__isnull=True,
        )
        .prefetch_related(
            Prefetch(
                "estimates",
                queryset=Estimate.objects.filter(
                    status=EstimateStatus.APPROVED,
                    deleted_at__isnull=True,
                ).prefetch_related("items"),
            ),
            Prefetch(
                "expenses",
                queryset=Expense.objects.filter(
                    status__in=(ExpenseStatus.RECORDED, ExpenseStatus.APPROVED),
                    deleted_at__isnull=True,
                ),
            ),
            Prefetch(
                "treasurymovement_set",
                queryset=TreasuryMovement.objects.filter(
                    organization=organization,
                    status=TreasuryMovementStatus.POSTED,
                    posted_at__lte=cash_cutoff,
                    kind__in=(
                        TreasuryMovementKind.RECEIPT,
                        TreasuryMovementKind.DISBURSEMENT,
                    ),
                    reverses__isnull=True,
                    reversal_movement__isnull=True,
                ),
                to_attr="cash_movements",
            ),
        )
        .order_by("name")
    )
    return [_build_report(project, cash_cutoff=cash_cutoff) for project in projects]


def get_organization_dashboard(
    *,
    user: User,
    organization: Organization,
) -> OrganizationDashboard:
    """Build tenant-scoped dashboard metrics for an active organization."""

    _validate_view_context(user, organization)
    reports = get_organization_financial_reports(
        user=user,
        organization=organization,
    )
    approved_estimate_total = _money(
        sum((report.approved_estimate_total for report in reports), ZERO)
    )
    recorded_expense_total = _money(
        sum((report.recorded_expense_total for report in reports), ZERO)
    )
    receipt_total = sum((report.receipt_total for report in reports), ZERO)
    disbursement_total = sum((report.disbursement_total for report in reports), ZERO)
    return OrganizationDashboard(
        project_count=len(reports),
        contract_count=Contract.objects.filter(
            organization=organization,
            deleted_at__isnull=True,
            project__deleted_at__isnull=True,
        ).count(),
        estimate_count=Estimate.objects.filter(
            organization=organization,
            deleted_at__isnull=True,
            project__deleted_at__isnull=True,
        ).count(),
        approved_estimate_total=approved_estimate_total,
        recorded_expense_total=recorded_expense_total,
        variance=_money(approved_estimate_total - recorded_expense_total),
        receipt_total=receipt_total,
        disbursement_total=disbursement_total,
        net_cash_flow=receipt_total - disbursement_total,
        posted_movement_count=sum(report.posted_movement_count for report in reports),
        cash_cutoff=reports[0].cash_cutoff if reports else timezone.now(),
    )
