from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import QuerySet

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.expenses.models import Expense, ExpenseCategory, ExpenseStatus
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationStatus,
)
from apps.projects.models import Project


def _can_manage_expenses(user: User, organization: Organization) -> bool:
    return organization.memberships.filter(
        user=user,
        status=MembershipStatus.ACTIVE,
        role__in=[
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
            MembershipRole.MANAGER,
        ],
    ).exists()


def _validate_context(
    *,
    actor: User,
    organization: Organization,
    project: Project,
) -> None:
    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied("Authentication is required.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("The organization is not active.")
    if not _can_manage_expenses(actor, organization):
        raise PermissionDenied("You cannot manage expenses in this organization.")
    if project.organization_id != organization.pk or project.deleted_at is not None:
        raise PermissionDenied("The project does not belong to this organization.")


@transaction.atomic
def create_expense(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    description: str,
    amount: Decimal,
    incurred_on: date,
    category: str = ExpenseCategory.OTHER,
    vendor_name: str = "",
    status: str = ExpenseStatus.RECORDED,
    receipt_reference: str = "",
    notes: str = "",
) -> Expense:
    """Record a non-negative expense for a project."""

    _validate_context(actor=actor, organization=organization, project=project)
    if not description.strip():
        raise ValueError("Expense description is required.")
    if amount < Decimal("0.00"):
        raise ValueError("Expense amount cannot be negative.")
    if category not in ExpenseCategory.values:
        raise ValueError("Invalid expense category.")
    if status not in ExpenseStatus.values:
        raise ValueError("Invalid expense status.")

    expense = Expense.objects.create(
        organization=organization,
        project=project,
        category=category,
        description=description.strip(),
        vendor_name=vendor_name.strip(),
        amount=amount,
        incurred_on=incurred_on,
        status=status,
        receipt_reference=receipt_reference.strip(),
        notes=notes.strip(),
        created_by=actor,
        updated_by=actor,
    )
    record_audit_event(
        action=AuditAction.EXPENSE_RECORDED,
        entity_type="expense",
        entity_id=expense.pk,
        organization=organization,
        actor=actor,
        metadata={
            "project_id": str(project.pk),
            "amount": str(expense.amount),
            "category": expense.category,
        },
    )
    return expense


def get_organization_expenses(
    *,
    user: User,
    organization: Organization,
) -> QuerySet[Expense]:
    """Return non-deleted expenses visible in the active organization."""

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
    return (
        Expense.objects.filter(
            organization=organization,
            deleted_at__isnull=True,
            project__deleted_at__isnull=True,
        )
        .select_related("project", "created_by", "updated_by")
        .order_by("-incurred_on", "-created_at")
    )
