from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.expenses.models import (
    Expense,
    ExpenseCategory,
    ExpenseStatus,
    LegacyExpenseCategory,
)
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationStatus,
)
from apps.parties.models import BusinessParty
from apps.projects.models import Project, ProjectPhase


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
        raise PermissionDenied("ورود به حساب کاربری الزامی است.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("سازمان فعال نیست.")
    if not _can_manage_expenses(actor, organization):
        raise PermissionDenied("اجازه مدیریت هزینه‌های این سازمان را ندارید.")
    if project.organization_id != organization.pk or project.deleted_at is not None:
        raise PermissionDenied("پروژه متعلق به این سازمان نیست.")


def _validate_phase(
    *,
    organization: Organization,
    project: Project,
    phase: ProjectPhase,
) -> None:
    if phase.organization_id != organization.pk or phase.site.project_id != project.pk:
        raise PermissionDenied("فاز پروژه متعلق به این پروژه نیست.")


@transaction.atomic
def create_expense(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    description: str,
    amount: Decimal,
    incurred_on: date,
    phase: ProjectPhase | None = None,
    category: str = LegacyExpenseCategory.OTHER,
    vendor_name: str = "",
    party: BusinessParty | None = None,
    expense_category: ExpenseCategory | None = None,
    status: str = ExpenseStatus.RECORDED,
    receipt_reference: str = "",
    notes: str = "",
) -> Expense:
    """Record a non-negative expense for a project."""

    _validate_context(actor=actor, organization=organization, project=project)
    if phase is not None:
        _validate_phase(organization=organization, project=project, phase=phase)
    if not description.strip():
        raise ValueError("وارد کردن شرح هزینه الزامی است.")
    if amount < Decimal("0.00"):
        raise ValueError("مبلغ هزینه نمی‌تواند منفی باشد.")
    if category not in LegacyExpenseCategory.values:
        raise ValueError("دسته هزینه معتبر نیست.")
    if status not in ExpenseStatus.values:
        raise ValueError("وضعیت هزینه معتبر نیست.")
    if status != ExpenseStatus.RECORDED:
        raise ValueError("هزینه باید با وضعیت ثبت‌شده ایجاد شود.")
    if party and (party.organization_id != organization.pk or party.archived_at):
        raise PermissionDenied("طرف تجاری متعلق به این سازمان نیست.")
    if expense_category and (
        expense_category.organization_id != organization.pk
        or expense_category.archived_at
        or not expense_category.is_active
    ):
        raise PermissionDenied(
            "دسته هزینه متعلق به این سازمان نیست."
        )
    expense = Expense.objects.create(
        organization=organization,
        project=project,
        phase=phase,
        category=category,
        description=description.strip(),
        vendor_name=vendor_name.strip() or (party.display_name if party else ""),
        party=party,
        expense_category=expense_category,
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
            "phase_id": str(phase.pk) if phase else None,
            "amount": str(expense.amount),
            "category": expense.category,
            "party_id": str(party.pk) if party else None,
            "expense_category_id": str(expense_category.pk)
            if expense_category
            else None,
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
        raise PermissionDenied("ورود به حساب کاربری الزامی است.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("سازمان فعال نیست.")
    if not organization.memberships.filter(
        user=user,
        status=MembershipStatus.ACTIVE,
    ).exists():
        raise PermissionDenied("به این سازمان دسترسی ندارید.")
    return (
        Expense.objects.filter(
            organization=organization,
            deleted_at__isnull=True,
            project__deleted_at__isnull=True,
        )
        .select_related(
            "project",
            "phase",
            "party",
            "expense_category",
            "created_by",
            "updated_by",
            "voided_by",
        )
        .order_by("-incurred_on", "-created_at")
    )


@transaction.atomic
def void_expense(*, expense: Expense, actor: User, reason: str) -> Expense:
    """Void a recorded expense without changing its original financial amount."""

    locked_expense = Expense.objects.select_for_update().get(pk=expense.pk)
    _validate_context(
        actor=actor,
        organization=locked_expense.organization,
        project=locked_expense.project,
    )
    if locked_expense.status != ExpenseStatus.RECORDED:
        raise ValueError("فقط هزینه ثبت‌شده قابل ابطال است.")
    if not reason.strip():
        raise ValueError("وارد کردن دلیل ابطال هزینه الزامی است.")

    locked_expense.status = ExpenseStatus.VOID
    locked_expense.void_reason = reason.strip()
    locked_expense.voided_at = timezone.now()
    locked_expense.voided_by = actor
    locked_expense.updated_by = actor
    locked_expense.save(
        update_fields=[
            "status",
            "void_reason",
            "voided_at",
            "voided_by",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.EXPENSE_VOIDED,
        entity_type="expense",
        entity_id=locked_expense.pk,
        organization=locked_expense.organization,
        actor=actor,
        metadata={"reason": locked_expense.void_reason},
    )
    return locked_expense


@transaction.atomic
def create_expense_category(
    *, organization: Organization, actor: User, code: str, name: str
) -> ExpenseCategory:
    _validate_category_management(organization=organization, actor=actor)
    category = ExpenseCategory(
        organization=organization,
        code=code,
        name=name,
        created_by=actor,
        updated_by=actor,
    )
    try:
        category.save()
    except ValidationError as exc:
        raise ValueError("اطلاعات دسته هزینه معتبر نیست.") from exc
    record_audit_event(
        action=AuditAction.EXPENSE_CATEGORY_CREATED,
        entity_type="expense_category",
        entity_id=category.pk,
        organization=organization,
        actor=actor,
        metadata={"code": category.code},
    )
    return category


def _validate_category_management(*, organization: Organization, actor: User) -> None:
    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied("ورود به حساب کاربری الزامی است.")
    if organization.status != OrganizationStatus.ACTIVE or organization.deleted_at:
        raise PermissionDenied("سازمان فعال نیست.")
    if not _can_manage_expenses(actor, organization):
        raise PermissionDenied("اجازه مدیریت هزینه‌های این سازمان را ندارید.")


@transaction.atomic
def archive_expense_category(
    *, organization: Organization, actor: User, category: ExpenseCategory
) -> ExpenseCategory:
    _validate_category_management(organization=organization, actor=actor)
    locked_category = ExpenseCategory.objects.select_for_update().get(pk=category.pk)
    if locked_category.organization_id != organization.pk:
        raise PermissionDenied(
            "دسته هزینه متعلق به این سازمان نیست."
        )
    if locked_category.archived_at is not None:
        raise ValueError("دسته هزینه از قبل بایگانی شده است.")
    locked_category.is_active = False
    locked_category.archived_at = timezone.now()
    locked_category.updated_by = actor
    locked_category.save(
        update_fields=["is_active", "archived_at", "updated_by", "updated_at"]
    )
    record_audit_event(
        action=AuditAction.EXPENSE_CATEGORY_ARCHIVED,
        entity_type="expense_category",
        entity_id=locked_category.pk,
        organization=organization,
        actor=actor,
        metadata={"code": locked_category.code},
    )
    return locked_category
