import hashlib
from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import QuerySet, Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.expenses.models import (
    Expense,
    ExpenseAllocation,
    ExpenseBudgetAssessment,
    ExpenseCategory,
    ExpenseClassification,
    ExpenseRecurrenceFrequency,
    ExpenseStatus,
    LegacyExpenseCategory,
    PlatformExpenseGroup,
    RecurringExpenseTemplate,
)
from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
    is_platform_admin,
    scope_queryset,
)
from apps.organizations.models import (
    BusinessPermissionCode,
    Organization,
    OrganizationStatus,
)
from apps.parties.models import BusinessParty
from apps.projects.models import (
    Activity,
    BudgetAllocation,
    BudgetVersionStatus,
    CBSNode,
    CostCenter,
    Project,
    ProjectBudgetControl,
    ProjectPhase,
    WBSNode,
)
from apps.workforce.models import Employee


def _has_expense_permission(
    user: User,
    organization: Organization,
    permission: BusinessPermissionCode,
    *,
    project: Project | None = None,
    allow_any_scope: bool = False,
) -> bool:
    return has_business_permission(
        user=user,
        organization=organization,
        permission=permission,
        project=project,
        allow_any_scope=allow_any_scope,
    )


def _validate_context(
    *,
    actor: User,
    organization: Organization,
    project: Project,
    permission: BusinessPermissionCode,
) -> None:
    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied("ورود به حساب کاربری الزامی است.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("سازمان فعال نیست.")
    if not _has_expense_permission(actor, organization, permission, project=project):
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

    _validate_context(
        actor=actor,
        organization=organization,
        project=project,
        permission=BusinessPermissionCode.EXPENSES_CREATE,
    )
    if phase is not None:
        _validate_phase(organization=organization, project=project, phase=phase)
    if not description.strip():
        raise ValueError("وارد کردن شرح هزینه الزامی است.")
    if amount < Decimal("0.00"):
        raise ValueError("مبلغ هزینه نمی‌تواند منفی باشد.")
    if not PlatformExpenseGroup.objects.filter(
        code=category, is_active=True, archived_at__isnull=True
    ).exists():
        raise ValueError("گروه اصلی هزینه معتبر نیست.")
    primary_group = PlatformExpenseGroup.objects.get(code=category)
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
        raise PermissionDenied("دسته هزینه متعلق به این سازمان نیست.")
    expense = Expense.objects.create(
        organization=organization,
        project=project,
        phase=phase,
        category=category,
        primary_group=primary_group,
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


def _expense_fingerprint(
    *, source_reference: str, amount: Decimal, incurred_on: date, vendor_name: str
) -> str:
    payload = "|".join(
        (
            source_reference.strip().casefold(),
            str(amount.quantize(Decimal("0.01"))),
            incurred_on.isoformat(),
            vendor_name.strip().casefold(),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _same_expense_draft_request(
    expense: Expense,
    *,
    project: Project,
    phase: ProjectPhase | None,
    category: str,
    description: str,
    vendor_name: str,
    party: BusinessParty | None,
    expense_category: ExpenseCategory | None,
    amount: Decimal,
    incurred_on: date,
    classification: str,
    source_reference: str,
    source_fingerprint: str,
    receipt_reference: str,
    notes: str,
    recurrence_template: RecurringExpenseTemplate | None,
    recurrence_occurrence_on: date | None,
    reimbursement_employee: Employee | None,
    replaces: Expense | None,
) -> bool:
    """Require an idempotency retry to reproduce the complete immutable payload."""

    return (
        expense.project_id == project.pk
        and expense.phase_id == getattr(phase, "pk", None)
        and expense.category == category
        and expense.description == description.strip()
        and expense.vendor_name == vendor_name
        and expense.party_id == getattr(party, "pk", None)
        and expense.expense_category_id == getattr(expense_category, "pk", None)
        and expense.amount == amount
        and expense.incurred_on == incurred_on
        and expense.classification == classification
        and expense.source_reference == source_reference.strip()
        and expense.source_fingerprint == source_fingerprint
        and expense.receipt_reference == receipt_reference.strip()
        and expense.notes == notes.strip()
        and expense.recurrence_template_id == getattr(recurrence_template, "pk", None)
        and expense.recurrence_occurrence_on == recurrence_occurrence_on
        and expense.reimbursement_employee_id == getattr(reimbursement_employee, "pk", None)
        and expense.replaces_id == getattr(replaces, "pk", None)
    )


@transaction.atomic
def create_expense_draft(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    description: str,
    amount: Decimal,
    incurred_on: date,
    source_reference: str,
    idempotency_key: str,
    phase: ProjectPhase | None = None,
    category: str = LegacyExpenseCategory.OTHER,
    vendor_name: str = "",
    party: BusinessParty | None = None,
    expense_category: ExpenseCategory | None = None,
    classification: str = ExpenseClassification.DIRECT,
    receipt_reference: str = "",
    notes: str = "",
    recurrence_template: RecurringExpenseTemplate | None = None,
    recurrence_occurrence_on: date | None = None,
    reimbursement_employee: Employee | None = None,
    replaces: Expense | None = None,
) -> Expense:
    """Create a reviewable draft; no payable, posting, cash, or cost fact is made."""

    _validate_context(
        actor=actor,
        organization=organization,
        project=project,
        permission=BusinessPermissionCode.EXPENSES_CREATE,
    )
    normalized_key = idempotency_key.strip()
    if not normalized_key:
        raise ValueError("An idempotency key is required.")
    if phase is not None:
        _validate_phase(organization=organization, project=project, phase=phase)
    if not description.strip() or not source_reference.strip():
        raise ValueError("Description and retained source reference are required.")
    if amount <= Decimal("0.00"):
        raise ValueError("Expense amount must be positive.")
    if not PlatformExpenseGroup.objects.filter(
        code=category, is_active=True, archived_at__isnull=True
    ).exists():
        raise ValueError("Invalid primary expense group.")
    primary_group = PlatformExpenseGroup.objects.get(code=category)
    if classification not in ExpenseClassification.values:
        raise ValueError("Invalid direct/indirect classification.")
    if reimbursement_employee and (
        reimbursement_employee.organization_id != organization.pk
        or classification != ExpenseClassification.DIRECT
    ):
        raise PermissionDenied("Reimbursement beneficiary must belong to this tenant and a direct expense.")
    if replaces is not None:
        replaces = Expense.objects.select_for_update().filter(
            pk=replaces.pk, organization=organization,
        ).first()
        if replaces is None:
            raise ValueError("Replacement source does not belong to this tenant.")
    if replaces and (
        replaces.organization_id != organization.pk
        or replaces.project_id != project.pk
        or replaces.status != ExpenseStatus.VOID
        or replaces.reimbursement_employee_id != getattr(reimbursement_employee, "pk", None)
    ):
        raise ValueError("Replacement requires a voided expense in the same context.")
    if party and (party.organization_id != organization.pk or party.archived_at):
        raise PermissionDenied("Business party does not belong to this organization.")
    if expense_category and (
        expense_category.organization_id != organization.pk
        or expense_category.archived_at
        or not expense_category.is_active
    ):
        raise PermissionDenied("Expense category does not belong to this organization.")
    if recurrence_template and (
        recurrence_template.organization_id != organization.pk
        or recurrence_template.project_id != project.pk
    ):
        raise PermissionDenied("Recurrence template does not belong to this context.")
    normalized_vendor = vendor_name.strip() or (party.display_name if party else "")
    source_fingerprint = _expense_fingerprint(
        source_reference=source_reference,
        amount=amount,
        incurred_on=incurred_on,
        vendor_name=normalized_vendor,
    )
    request_matches = {
        "project": project,
        "phase": phase,
        "category": category,
        "description": description,
        "vendor_name": normalized_vendor,
        "party": party,
        "expense_category": expense_category,
        "amount": amount,
        "incurred_on": incurred_on,
        "classification": classification,
        "source_reference": source_reference,
        "source_fingerprint": source_fingerprint,
        "receipt_reference": receipt_reference,
        "notes": notes,
        "recurrence_template": recurrence_template,
        "recurrence_occurrence_on": recurrence_occurrence_on,
        "reimbursement_employee": reimbursement_employee,
        "replaces": replaces,
    }
    existing = Expense.objects.filter(
        organization=organization, idempotency_key=normalized_key
    ).first()
    if existing:
        if _same_expense_draft_request(existing, **request_matches):
            return existing
        raise ValueError("The idempotency key already exists with a different payload.")
    if (
        Expense.objects.filter(
            organization=organization,
            source_fingerprint=source_fingerprint,
        )
        .exclude(status=ExpenseStatus.VOID)
        .exists()
    ):
        raise ValueError("Duplicate active expense source evidence.")
    try:
        with transaction.atomic():
            expense = Expense.objects.create(
                organization=organization,
                project=project,
                phase=phase,
                category=category,
                primary_group=primary_group,
                description=description.strip(),
                vendor_name=normalized_vendor,
                party=party,
                expense_category=expense_category,
                amount=amount,
                incurred_on=incurred_on,
                status=ExpenseStatus.DRAFT,
                classification=classification,
                source_reference=source_reference.strip(),
                source_fingerprint=source_fingerprint,
                idempotency_key=normalized_key,
                receipt_reference=receipt_reference.strip(),
                notes=notes.strip(),
                recurrence_template=recurrence_template,
                recurrence_occurrence_on=recurrence_occurrence_on,
                reimbursement_employee=reimbursement_employee,
                replaces=replaces,
                source_version=replaces.source_version + 1 if replaces else 1,
                created_by=actor,
                updated_by=actor,
            )
    except (IntegrityError, ValidationError) as exc:
        retry = Expense.objects.filter(
            organization=organization, idempotency_key=normalized_key
        ).first()
        if retry and _same_expense_draft_request(retry, **request_matches):
            return retry
        if retry:
            raise ValueError(
                "The idempotency key already exists with a different payload."
            ) from exc
        if isinstance(exc, ValidationError):
            raise
        raise ValueError("Duplicate active expense source evidence.") from exc
    record_audit_event(
        action=AuditAction.EXPENSE_DRAFT_CREATED,
        entity_type="expense",
        entity_id=expense.pk,
        organization=organization,
        actor=actor,
        metadata={
            "project_id": str(project.pk),
            "amount": str(expense.amount),
            "classification": classification,
            "source_fingerprint": source_fingerprint,
        },
    )
    return expense


@transaction.atomic
def add_expense_allocation(
    *,
    expense: Expense,
    actor: User,
    project: Project,
    wbs_node: WBSNode,
    cbs_node: CBSNode,
    amount: Decimal,
    allocation_basis_reference: str,
    activity: Activity | None = None,
    cost_center: CostCenter | None = None,
) -> ExpenseAllocation:
    locked = Expense.objects.select_for_update().get(pk=expense.pk)
    _validate_context(
        actor=actor,
        organization=locked.organization,
        project=project,
        permission=BusinessPermissionCode.EXPENSES_ALLOCATE,
    )
    if locked.status not in (ExpenseStatus.DRAFT, ExpenseStatus.RETURNED):
        raise ValueError("Only draft or returned expenses can be allocated.")
    control = (
        ProjectBudgetControl.objects.select_for_update(of=("self",))
        .select_related("governing_budget__structure_version")
        .filter(organization=locked.organization, project=project)
        .first()
    )
    if (
        not control
        or not control.governing_budget_id
        or control.governing_budget.status != BudgetVersionStatus.ACCEPTED
    ):
        raise ValueError("An accepted governing budget is required for expense coding.")
    if not cbs_node.is_leaf:
        raise ValueError("Expense coding requires a leaf CBS node.")
    if control.governing_budget.cost_center_required and cost_center is None:
        raise ValueError("The governing budget requires an explicit cost center.")
    allocated = locked.allocations.aggregate(total=Sum("amount"))["total"] or Decimal(
        "0.00"
    )
    if amount <= Decimal("0.00") or allocated + amount > locked.amount:
        raise ValueError(
            "Allocation must be positive and cannot exceed the expense amount."
        )
    allocation = ExpenseAllocation.objects.create(
        organization=locked.organization,
        expense=locked,
        sequence=locked.allocations.count() + 1,
        project=project,
        wbs_node=wbs_node,
        activity=activity,
        cbs_node=cbs_node,
        cost_center=cost_center,
        governing_budget=control.governing_budget,
        amount=amount,
        allocation_basis_reference=allocation_basis_reference.strip(),
        created_by=actor,
    )
    record_audit_event(
        action=AuditAction.EXPENSE_ALLOCATION_ADDED,
        entity_type="expense",
        entity_id=locked.pk,
        organization=locked.organization,
        actor=actor,
        metadata={
            "allocation_id": str(allocation.pk),
            "project_id": str(project.pk),
            "budget_id": str(control.governing_budget_id),
            "amount": str(amount),
        },
    )
    return allocation


def _assess_allocation(allocation: ExpenseAllocation) -> ExpenseBudgetAssessment:
    budget_amount = BudgetAllocation.objects.filter(
        organization=allocation.organization,
        manifest_line__manifest__budget=allocation.governing_budget,
        wbs_node=allocation.wbs_node,
        cbs_node=allocation.cbs_node,
        cost_center=allocation.cost_center,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    if budget_amount <= Decimal("0.00"):
        raise ValueError("The accepted budget contains no matching coded allocation.")
    prior = ExpenseAllocation.objects.filter(
        organization=allocation.organization,
        project=allocation.project,
        wbs_node=allocation.wbs_node,
        cbs_node=allocation.cbs_node,
        cost_center=allocation.cost_center,
        governing_budget=allocation.governing_budget,
        expense__status__in=(ExpenseStatus.APPROVED, ExpenseStatus.RECORDED),
    ).exclude(expense=allocation.expense).aggregate(total=Sum("amount"))[
        "total"
    ] or Decimal("0.00")
    remaining = budget_amount - prior - allocation.amount
    return ExpenseBudgetAssessment.objects.create(
        organization=allocation.organization,
        expense=allocation.expense,
        allocation=allocation,
        governing_budget=allocation.governing_budget,
        accepted_budget_amount=budget_amount,
        prior_approved_expense_amount=prior,
        proposed_amount=allocation.amount,
        remaining_after_proposal=remaining,
        is_overrun=remaining < Decimal("0.00"),
        control_mode="advisory_only",
        assessed_at=timezone.now(),
    )


def _lock_budget_controls(
    *, organization: Organization, project_ids: set[object]
) -> dict[object, ProjectBudgetControl]:
    """Lock all touched project controls in one deterministic order."""

    controls = tuple(
        ProjectBudgetControl.objects.select_for_update()
        .filter(organization=organization, project_id__in=project_ids)
        .order_by("project_id")
    )
    return {control.project_id: control for control in controls}


@transaction.atomic
def submit_expense(*, expense: Expense, actor: User) -> Expense:
    locked = Expense.objects.select_for_update().get(pk=expense.pk)
    _validate_context(
        actor=actor,
        organization=locked.organization,
        project=locked.project,
        permission=BusinessPermissionCode.EXPENSES_SUBMIT,
    )
    if locked.status not in (ExpenseStatus.DRAFT, ExpenseStatus.RETURNED):
        raise ValueError("Only a draft or returned expense can be submitted.")
    if not locked.source_reference or not locked.source_fingerprint:
        raise ValueError("Retained source evidence is required before submission.")
    allocations = sorted(
        locked.allocations.select_related(
            "project",
            "wbs_node",
            "activity",
            "cbs_node",
            "cost_center",
            "governing_budget",
        ),
        key=lambda item: (str(item.project_id), item.sequence),
    )
    if (
        not allocations
        or sum((item.amount for item in allocations), Decimal("0.00")) != locked.amount
    ):
        raise ValueError(
            "Expense allocations must exactly conserve the expense amount."
        )
    controls = _lock_budget_controls(
        organization=locked.organization,
        project_ids={allocation.project_id for allocation in allocations},
    )
    for allocation in allocations:
        control = controls.get(allocation.project_id)
        if control is None:
            raise ValueError("An accepted governing budget is required.")
        if control.governing_budget_id != allocation.governing_budget_id:
            raise ValueError(
                "The governing accepted budget changed; recoding is required."
            )
        _assess_allocation(allocation)
    locked.status = ExpenseStatus.SUBMITTED
    locked.submitted_by = actor
    locked.submitted_at = timezone.now()
    locked.return_reason = ""
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "status",
            "submitted_by",
            "submitted_at",
            "return_reason",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.EXPENSE_SUBMITTED,
        entity_type="expense",
        entity_id=locked.pk,
        organization=locked.organization,
        actor=actor,
        metadata={"allocation_count": len(allocations)},
    )
    return locked


@transaction.atomic
def approve_expense(*, expense: Expense, actor: User) -> Expense:
    locked = Expense.objects.select_for_update().get(pk=expense.pk)
    _validate_context(
        actor=actor,
        organization=locked.organization,
        project=locked.project,
        permission=BusinessPermissionCode.EXPENSES_APPROVE,
    )
    if locked.status != ExpenseStatus.SUBMITTED:
        raise ValueError("Only a submitted expense can be approved.")
    if locked.created_by_id == actor.pk or locked.submitted_by_id == actor.pk:
        raise PermissionDenied("Expense maker/submitting actor cannot approve it.")
    if locked.allocations.aggregate(total=Sum("amount"))["total"] != locked.amount:
        raise ValueError("Expense allocations no longer conserve the amount.")
    allocations = tuple(locked.allocations.order_by("project_id", "sequence"))
    controls = _lock_budget_controls(
        organization=locked.organization,
        project_ids={allocation.project_id for allocation in allocations},
    )
    for allocation in allocations:
        control = controls.get(allocation.project_id)
        if control is None:
            raise ValueError("An accepted governing budget is required.")
        if control.governing_budget_id != allocation.governing_budget_id:
            raise ValueError("The governing accepted budget changed after submission.")
    locked.status = ExpenseStatus.APPROVED
    locked.approved_by = actor
    locked.approved_at = timezone.now()
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.EXPENSE_APPROVED,
        entity_type="expense",
        entity_id=locked.pk,
        organization=locked.organization,
        actor=actor,
        metadata={"financial_handoff": "none"},
    )
    return locked


@transaction.atomic
def return_expense(*, expense: Expense, actor: User, reason: str) -> Expense:
    locked = Expense.objects.select_for_update().get(pk=expense.pk)
    _validate_context(
        actor=actor,
        organization=locked.organization,
        project=locked.project,
        permission=BusinessPermissionCode.EXPENSES_RETURN,
    )
    if locked.status != ExpenseStatus.SUBMITTED or not reason.strip():
        raise ValueError("A submitted expense and return reason are required.")
    locked.status = ExpenseStatus.RETURNED
    locked.returned_by = actor
    locked.returned_at = timezone.now()
    locked.return_reason = reason.strip()
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "status",
            "returned_by",
            "returned_at",
            "return_reason",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.EXPENSE_RETURNED,
        entity_type="expense",
        entity_id=locked.pk,
        organization=locked.organization,
        actor=actor,
        metadata={"reason": locked.return_reason},
    )
    return locked


@transaction.atomic
def create_recurring_expense_template(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    description: str,
    amount: Decimal,
    classification: str,
    frequency: str,
    starts_on: date,
    source_reference_prefix: str,
    ends_on: date | None = None,
) -> RecurringExpenseTemplate:
    _validate_context(
        actor=actor,
        organization=organization,
        project=project,
        permission=BusinessPermissionCode.EXPENSE_RECURRENCES_MANAGE,
    )
    if frequency not in ExpenseRecurrenceFrequency.values:
        raise ValueError("Invalid recurrence frequency.")
    template = RecurringExpenseTemplate.objects.create(
        organization=organization,
        project=project,
        description=description,
        amount=amount,
        classification=classification,
        frequency=frequency,
        starts_on=starts_on,
        ends_on=ends_on,
        source_reference_prefix=source_reference_prefix,
        created_by=actor,
    )
    return template


@transaction.atomic
def propose_recurring_expense(
    *, template: RecurringExpenseTemplate, occurrence_on: date, actor: User
) -> Expense:
    locked = RecurringExpenseTemplate.objects.select_for_update().get(pk=template.pk)
    _validate_context(
        actor=actor,
        organization=locked.organization,
        project=locked.project,
        permission=BusinessPermissionCode.EXPENSE_RECURRENCES_MANAGE,
    )
    if (
        not locked.is_active
        or occurrence_on < locked.starts_on
        or (locked.ends_on and occurrence_on > locked.ends_on)
    ):
        raise ValueError("Occurrence is outside the active recurrence window.")
    expected_weekday = locked.starts_on.weekday()
    if (
        locked.frequency == ExpenseRecurrenceFrequency.WEEKLY
        and occurrence_on.weekday() != expected_weekday
    ):
        raise ValueError("Weekly occurrence does not match the template weekday.")
    if (
        locked.frequency == ExpenseRecurrenceFrequency.MONTHLY
        and occurrence_on.day != locked.starts_on.day
    ):
        raise ValueError("Monthly occurrence does not match the template day.")
    existing = Expense.objects.filter(
        recurrence_template=locked, recurrence_occurrence_on=occurrence_on
    ).first()
    if existing:
        return existing
    proposal = create_expense_draft(
        organization=locked.organization,
        project=locked.project,
        actor=actor,
        description=locked.description,
        amount=locked.amount,
        incurred_on=occurrence_on,
        source_reference=f"{locked.source_reference_prefix}:{occurrence_on.isoformat()}",
        idempotency_key=f"recurrence:{locked.pk}:{occurrence_on.isoformat()}",
        classification=locked.classification,
        recurrence_template=locked,
        recurrence_occurrence_on=occurrence_on,
    )
    record_audit_event(
        action=AuditAction.EXPENSE_RECURRENCE_PROPOSED,
        entity_type="expense",
        entity_id=proposal.pk,
        organization=locked.organization,
        actor=actor,
        metadata={
            "template_id": str(locked.pk),
            "occurrence_on": occurrence_on.isoformat(),
        },
    )
    return proposal


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
    if not _has_expense_permission(
        user,
        organization,
        BusinessPermissionCode.EXPENSES_VIEW,
        allow_any_scope=True,
    ):
        raise PermissionDenied("اجازه مشاهده هزینه‌های این سازمان را ندارید.")
    membership = get_active_membership(user=user, organization=organization)
    return (
        scope_queryset(
            Expense.objects.filter(
                organization=organization,
                deleted_at__isnull=True,
                project__deleted_at__isnull=True,
            ),
            membership=membership,
            project_lookup="project_id",
        )
        .select_related(
            "project",
            "phase",
            "party",
            "expense_category",
            "primary_group",
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
        permission=BusinessPermissionCode.EXPENSES_VOID,
    )
    if locked_expense.status not in (
        ExpenseStatus.DRAFT,
        ExpenseStatus.SUBMITTED,
        ExpenseStatus.APPROVED,
        ExpenseStatus.RETURNED,
        ExpenseStatus.RECORDED,
    ):
        raise ValueError("این هزینه قابل ابطال نیست.")
    if not reason.strip():
        raise ValueError("وارد کردن دلیل ابطال هزینه الزامی است.")
    if locked_expense.reimbursement_employee_id:
        from apps.treasury.models import PaymentRequest, PaymentRequestStatus

        if PaymentRequest.objects.filter(
            source_expense=locked_expense,
            status__in=(
                PaymentRequestStatus.DRAFT,
                PaymentRequestStatus.SUBMITTED,
                PaymentRequestStatus.APPROVED,
                PaymentRequestStatus.RELEASED,
            ),
        ).exists():
            raise ValueError("An active or settled reimbursement request prevents voiding.")

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
    *,
    organization: Organization,
    actor: User,
    code: str,
    name: str,
    primary_group: PlatformExpenseGroup | None = None,
) -> ExpenseCategory:
    _validate_category_permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EXPENSE_CATEGORIES_CREATE,
    )
    primary_group = primary_group or PlatformExpenseGroup.objects.get(
        code=LegacyExpenseCategory.OTHER
    )
    if primary_group.archived_at is not None or not primary_group.is_active:
        raise ValueError("گروه اصلی هزینه باید فعال باشد.")
    category = ExpenseCategory(
        organization=organization,
        code=code,
        name=name,
        primary_group=primary_group,
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


@transaction.atomic
def update_expense_category(
    *,
    organization: Organization,
    actor: User,
    category: ExpenseCategory,
    code: str,
    name: str,
    primary_group: PlatformExpenseGroup,
) -> ExpenseCategory:
    _validate_category_permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EXPENSE_CATEGORIES_CHANGE,
    )
    locked_category = ExpenseCategory.objects.select_for_update().get(pk=category.pk)
    if locked_category.organization_id != organization.pk:
        raise PermissionDenied("دسته هزینه متعلق به این سازمان نیست.")
    if locked_category.archived_at is not None:
        raise ValueError("دسته هزینه بایگانی‌شده قابل ویرایش نیست.")
    if primary_group.archived_at is not None or not primary_group.is_active:
        raise ValueError("گروه اصلی هزینه باید فعال باشد.")
    locked_category.code = code
    locked_category.name = name
    locked_category.primary_group = primary_group
    locked_category.updated_by = actor
    try:
        locked_category.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError("اطلاعات دسته هزینه معتبر نیست.") from exc
    record_audit_event(
        action=AuditAction.EXPENSE_CATEGORY_UPDATED,
        entity_type="expense_category",
        entity_id=locked_category.pk,
        organization=organization,
        actor=actor,
        metadata={"code": locked_category.code, "primary_group": primary_group.code},
    )
    return locked_category


def get_platform_expense_groups(
    *, active_only: bool = False
) -> QuerySet[PlatformExpenseGroup]:
    queryset = PlatformExpenseGroup.objects.order_by("name")
    if active_only:
        queryset = queryset.filter(is_active=True, archived_at__isnull=True)
    return queryset


def _require_platform_expense_group_access(*, actor: User) -> None:
    if not is_platform_admin(actor):
        raise PermissionDenied(
            "فقط مدیر پلتفرم می‌تواند گروه‌های اصلی هزینه را مدیریت کند."
        )


@transaction.atomic
def create_platform_expense_group(
    *, actor: User, code: str, name: str
) -> PlatformExpenseGroup:
    _require_platform_expense_group_access(actor=actor)
    group = PlatformExpenseGroup(
        code=code, name=name, created_by=actor, updated_by=actor
    )
    try:
        group.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError("اطلاعات گروه اصلی هزینه معتبر نیست.") from exc
    record_audit_event(
        action=AuditAction.PLATFORM_EXPENSE_GROUP_CREATED,
        entity_type="platform_expense_group",
        entity_id=group.pk,
        organization=None,
        actor=actor,
        metadata={"code": group.code},
    )
    return group


@transaction.atomic
def update_platform_expense_group(
    *, actor: User, group: PlatformExpenseGroup, code: str, name: str
) -> PlatformExpenseGroup:
    _require_platform_expense_group_access(actor=actor)
    locked_group = PlatformExpenseGroup.objects.select_for_update().get(pk=group.pk)
    if locked_group.archived_at is not None:
        raise ValueError("گروه اصلی هزینه بایگانی‌شده قابل ویرایش نیست.")
    if code.strip().lower() != locked_group.code and (
        locked_group.expense_categories.exists()
        or Expense.objects.filter(category=locked_group.code).exists()
    ):
        raise ValueError(
            "کد گروه اصلی هزینهٔ دارای سابقه قابل تغییر نیست؛ فقط نام آن را ویرایش کنید."
        )
    locked_group.code = code
    locked_group.name = name
    locked_group.updated_by = actor
    try:
        locked_group.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError("اطلاعات گروه اصلی هزینه معتبر نیست.") from exc
    record_audit_event(
        action=AuditAction.PLATFORM_EXPENSE_GROUP_UPDATED,
        entity_type="platform_expense_group",
        entity_id=locked_group.pk,
        organization=None,
        actor=actor,
        metadata={"code": locked_group.code},
    )
    return locked_group


@transaction.atomic
def archive_platform_expense_group(
    *, actor: User, group: PlatformExpenseGroup
) -> PlatformExpenseGroup:
    _require_platform_expense_group_access(actor=actor)
    locked_group = PlatformExpenseGroup.objects.select_for_update().get(pk=group.pk)
    if locked_group.archived_at is not None:
        raise ValueError("گروه اصلی هزینه از قبل بایگانی شده است.")
    if locked_group.expense_categories.filter(archived_at__isnull=True).exists():
        raise ValueError("گروه دارای دسته هزینهٔ فعال قابل بایگانی نیست.")
    locked_group.is_active = False
    locked_group.archived_at = timezone.now()
    locked_group.updated_by = actor
    locked_group.save(
        update_fields=["is_active", "archived_at", "updated_by", "updated_at"]
    )
    record_audit_event(
        action=AuditAction.PLATFORM_EXPENSE_GROUP_ARCHIVED,
        entity_type="platform_expense_group",
        entity_id=locked_group.pk,
        organization=None,
        actor=actor,
        metadata={"code": locked_group.code},
    )
    return locked_group


def _validate_category_permission(
    *,
    organization: Organization,
    actor: User,
    permission: BusinessPermissionCode,
) -> None:
    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied("ورود به حساب کاربری الزامی است.")
    if organization.status != OrganizationStatus.ACTIVE or organization.deleted_at:
        raise PermissionDenied("سازمان فعال نیست.")
    if not _has_expense_permission(actor, organization, permission):
        raise PermissionDenied("اجازه دسترسی به دسته‌های هزینه این سازمان را ندارید.")


def get_organization_expense_categories(
    *, user: User, organization: Organization, active_only: bool = False
) -> QuerySet[ExpenseCategory]:
    """Return expense categories after enforcing tenant-aware view access."""

    _validate_category_permission(
        organization=organization,
        actor=user,
        permission=BusinessPermissionCode.EXPENSE_CATEGORIES_VIEW,
    )
    queryset = ExpenseCategory.objects.filter(organization=organization).order_by(
        "name"
    )
    if active_only:
        queryset = queryset.filter(is_active=True, archived_at__isnull=True)
    return queryset


@transaction.atomic
def archive_expense_category(
    *, organization: Organization, actor: User, category: ExpenseCategory
) -> ExpenseCategory:
    _validate_category_permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EXPENSE_CATEGORIES_ARCHIVE,
    )
    locked_category = ExpenseCategory.objects.select_for_update().get(pk=category.pk)
    if locked_category.organization_id != organization.pk:
        raise PermissionDenied("دسته هزینه متعلق به این سازمان نیست.")
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
