from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch

from apps.accounts.models import User
from apps.contracts.models import Contract
from apps.estimates.models import Estimate, EstimateStatus
from apps.expenses.models import Expense, ExpenseStatus
from apps.organizations.models import MembershipStatus, Organization, OrganizationStatus
from apps.projects.models import Project

ZERO = Decimal("0.00")


@dataclass(frozen=True)
class ProjectFinancialReport:
    project: Project
    approved_estimate_total: Decimal
    recorded_expense_total: Decimal
    variance: Decimal
    approved_estimate_count: int
    recorded_expense_count: int


@dataclass(frozen=True)
class OrganizationDashboard:
    project_count: int
    contract_count: int
    estimate_count: int
    approved_estimate_total: Decimal
    recorded_expense_total: Decimal
    variance: Decimal


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _validate_view_context(user: User, organization: Organization) -> None:
    if not user.is_authenticated:
        raise PermissionDenied("Authentication is required.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("The organization is not active.")
    if not organization.memberships.filter(
        user=user,
        status=MembershipStatus.ACTIVE,
    ).exists():
        raise PermissionDenied("You do not have access to this organization.")


def _build_report(project: Project) -> ProjectFinancialReport:
    approved_estimates = list(project.estimates.all())
    recorded_expenses = list(project.expenses.all())
    estimate_total = _money(
        sum((estimate.total_amount for estimate in approved_estimates), ZERO)
    )
    expense_total = _money(sum((expense.amount for expense in recorded_expenses), ZERO))
    return ProjectFinancialReport(
        project=project,
        approved_estimate_total=estimate_total,
        recorded_expense_total=expense_total,
        variance=_money(estimate_total - expense_total),
        approved_estimate_count=len(approved_estimates),
        recorded_expense_count=len(recorded_expenses),
    )


def get_project_financial_report(
    *,
    user: User,
    organization: Organization,
    project_id: str,
) -> ProjectFinancialReport:
    """Build one tenant-scoped financial report for a project."""

    _validate_view_context(user, organization)
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
                    status=ExpenseStatus.RECORDED,
                    deleted_at__isnull=True,
                ),
            ),
        )
        .first()
    )
    if project is None:
        raise PermissionDenied("Project not found in this organization.")
    return _build_report(project)


def get_organization_financial_reports(
    *,
    user: User,
    organization: Organization,
) -> list[ProjectFinancialReport]:
    """Build tenant-scoped financial reports for all active projects."""

    _validate_view_context(user, organization)
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
                    status=ExpenseStatus.RECORDED,
                    deleted_at__isnull=True,
                ),
            ),
        )
        .order_by("name")
    )
    return [_build_report(project) for project in projects]


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
    )
