"""F6 billing application services for baselines and progress measurement."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, QuerySet, Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.contracts.models import (
    Contract,
    ContractAmendmentStatus,
    ContractDirection,
    ContractItem,
    ContractStatus,
)
from apps.organizations.authorization import (
    get_active_membership,
    require_business_permission,
    scope_queryset,
)
from apps.organizations.models import (
    BusinessPermissionCode,
    MembershipStatus,
    Organization,
    OrganizationMembership,
)
from apps.payments.models import (
    Payment,
    PaymentAllocation,
    PaymentAllocationStatus,
    PaymentDirection,
    PaymentStatus,
)
from apps.projects.models import Activity, Project, WBSNode

from .models import (
    MONEY_QUANTUM,
    QUANTITY_QUANTUM,
    BaselineItem,
    BillingPolicy,
    ClaimAdjustment,
    ClaimAdjustmentType,
    ClaimNumberScope,
    ClaimPeriodBoundary,
    ClaimSettlementAllocation,
    ClaimSettlementAllocationStatus,
    ProgressClaim,
    ProgressClaimItem,
    ProgressClaimSource,
    ProgressRecord,
    ProgressRecordStatus,
    ProjectBaseline,
    ProjectBaselineStatus,
)


def _decimal_with_scale(
    value: Decimal | int | str,
    *,
    quantum: Decimal,
    label: str,
    positive: bool = False,
    nonnegative: bool = False,
) -> Decimal:
    if isinstance(value, (bool, float)):
        raise ValidationError(
            f"{label} باید Decimal باشد؛ مقدار اعشاری دودویی مجاز نیست."
        )
    try:
        normalized = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(f"{label} معتبر نیست.") from exc
    if normalized != normalized.quantize(quantum):
        places = abs(quantum.as_tuple().exponent)
        raise ValidationError(f"{label} حداکثر باید {places} رقم اعشار داشته باشد.")
    if positive and normalized <= 0:
        raise ValidationError(f"{label} باید بزرگ‌تر از صفر باشد.")
    if nonnegative and normalized < 0:
        raise ValidationError(f"{label} نمی‌تواند منفی باشد.")
    return normalized


def _require_permission(
    *,
    actor: User,
    organization: Organization,
    permission: BusinessPermissionCode,
    project: Project | None = None,
    allow_any_scope: bool = False,
) -> None:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        project=project,
        allow_any_scope=allow_any_scope,
        message="مجوز لازم برای مبنای تجاری این سازمان را ندارید.",
    )


def _locked_contract(*, organization: Organization, contract: Contract) -> Contract:
    try:
        locked = Contract.objects.select_for_update().get(
            pk=contract.pk, organization=organization
        )
    except Contract.DoesNotExist as exc:
        raise PermissionDenied("قرارداد متعلق به این سازمان نیست.") from exc
    if (
        locked.deleted_at is not None
        or locked.status != ContractStatus.ACTIVE
        or locked.direction != ContractDirection.RECEIVABLE
    ):
        raise ValidationError(
            "مبنا فقط برای قرارداد دریافتنیِ فعال ایجاد یا تأیید می‌شود."
        )
    return locked


def _validate_project_contract(
    *, organization: Organization, project: Project, contract: Contract
) -> None:
    if project.organization_id != organization.pk or project.deleted_at is not None:
        raise PermissionDenied("پروژه متعلق به سازمان فعال نیست.")
    if contract.project_id != project.pk:
        raise ValidationError("قرارداد باید متعلق به پروژه مبنا باشد.")


def _locked_baseline(
    *, organization: Organization, baseline: ProjectBaseline
) -> ProjectBaseline:
    try:
        return (
            ProjectBaseline.objects.select_for_update()
            .select_related("project", "contract")
            .get(pk=baseline.pk, organization=organization)
        )
    except ProjectBaseline.DoesNotExist as exc:
        raise PermissionDenied("مبنای تجاری متعلق به این سازمان نیست.") from exc


def _require_draft(baseline: ProjectBaseline) -> None:
    if baseline.status != ProjectBaselineStatus.DRAFT:
        raise ValidationError("فقط مبنای پیش‌نویس قابل ویرایش یا ارسال است.")


def _line_value(
    *, quantity: Decimal | int | str, rate: Decimal | int | str
) -> tuple[Decimal, Decimal, Decimal]:
    normalized_quantity = _decimal_with_scale(
        quantity,
        quantum=QUANTITY_QUANTUM,
        label="مقدار برنامه‌ریزی‌شده",
        positive=True,
    )
    normalized_rate = _decimal_with_scale(
        rate,
        quantum=MONEY_QUANTUM,
        label="نرخ واحد",
        nonnegative=True,
    )
    return (
        normalized_quantity,
        normalized_rate,
        (normalized_quantity * normalized_rate).quantize(
            MONEY_QUANTUM, rounding=ROUND_HALF_UP
        ),
    )


def _approved_amendment_total_locked(contract: Contract) -> Decimal:
    return sum(
        (
            amendment.value_change
            for amendment in contract.amendments.select_for_update().filter(
                status=ContractAmendmentStatus.APPROVED
            )
        ),
        Decimal("0.00"),
    ).quantize(MONEY_QUANTUM)


def _baseline_total_locked(baseline: ProjectBaseline) -> Decimal:
    return sum(
        (
            item.planned_value
            for item in BaselineItem.objects.select_for_update().filter(
                baseline=baseline, organization=baseline.organization
            )
        ),
        Decimal("0.00"),
    ).quantize(MONEY_QUANTUM)


def get_project_baselines(
    *, actor: User, organization: Organization
) -> QuerySet[ProjectBaseline]:
    """Return only the active tenant's commercial baselines."""

    _require_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.BASELINES_VIEW,
        allow_any_scope=True,
    )
    membership = get_active_membership(user=actor, organization=organization)
    return scope_queryset(
        queryset=ProjectBaseline.objects.filter(organization=organization),
        membership=membership,
        project_lookup="project_id",
    ).select_related("project", "contract", "approved_by", "created_by")


@transaction.atomic
def create_project_baseline(
    *,
    organization: Organization,
    actor: User,
    project: Project,
    contract: Contract,
    effective_date: date,
) -> ProjectBaseline:
    """Create the next draft version; pricing lines are added separately."""

    _require_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.BASELINES_MANAGE,
        project=project,
    )
    _validate_project_contract(
        organization=organization, project=project, contract=contract
    )
    locked_contract = _locked_contract(organization=organization, contract=contract)
    next_version = (
        ProjectBaseline.objects.filter(
            organization=organization, contract=locked_contract
        ).aggregate(value=Max("version"))["value"]
        or 0
    ) + 1
    baseline = ProjectBaseline.objects.create(
        organization=organization,
        project=project,
        contract=locked_contract,
        version=next_version,
        effective_date=effective_date,
        created_by=actor,
        updated_by=actor,
    )
    record_audit_event(
        action=AuditAction.PROJECT_BASELINE_CREATED,
        entity_type="billing.ProjectBaseline",
        entity_id=str(baseline.pk),
        organization=organization,
        actor=actor,
        metadata={
            "project_id": str(project.pk),
            "contract_id": str(locked_contract.pk),
            "version": baseline.version,
        },
    )
    return baseline


@transaction.atomic
def update_project_baseline_effective_date(
    *,
    organization: Organization,
    actor: User,
    baseline: ProjectBaseline,
    effective_date: date,
) -> ProjectBaseline:
    locked = _locked_baseline(organization=organization, baseline=baseline)
    _require_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.BASELINES_MANAGE,
        project=locked.project,
    )
    _require_draft(locked)
    locked.effective_date = effective_date
    locked.updated_by = actor
    locked.save(update_fields=["effective_date", "updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.PROJECT_BASELINE_UPDATED,
        entity_type="billing.ProjectBaseline",
        entity_id=str(locked.pk),
        organization=organization,
        actor=actor,
        metadata={"changed_fields": ["effective_date"]},
    )
    return locked


def _validate_item_references(
    *,
    organization: Organization,
    baseline: ProjectBaseline,
    contract_item: ContractItem | None,
    wbs_node: WBSNode | None,
    activity: Activity | None,
) -> None:
    for reference, label in (
        (contract_item, "ردیف قرارداد"),
        (wbs_node, "گره ساختار شکست"),
        (activity, "فعالیت"),
    ):
        if reference and reference.organization_id != organization.pk:
            raise PermissionDenied(f"{label} متعلق به این سازمان نیست.")
    if contract_item and contract_item.contract_id != baseline.contract_id:
        raise ValidationError("ردیف قرارداد باید متعلق به قرارداد مبنا باشد.")
    if wbs_node and wbs_node.project_id != baseline.project_id:
        raise ValidationError("گره ساختار شکست باید متعلق به پروژه مبنا باشد.")
    if activity and activity.project_id != baseline.project_id:
        raise ValidationError("فعالیت باید متعلق به پروژه مبنا باشد.")
    if activity and wbs_node and activity.wbs_node_id != wbs_node.pk:
        raise ValidationError("فعالیت باید متعلق به گره ساختار شکست انتخابی باشد.")


@transaction.atomic
def add_baseline_item(
    *,
    organization: Organization,
    actor: User,
    baseline: ProjectBaseline,
    line_key: str,
    description: str,
    unit: str,
    planned_quantity: Decimal | int | str,
    unit_rate: Decimal | int | str,
    contract_item: ContractItem | None = None,
    wbs_node: WBSNode | None = None,
    activity: Activity | None = None,
    sort_order: int = 0,
) -> BaselineItem:
    locked = _locked_baseline(organization=organization, baseline=baseline)
    _require_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.BASELINES_MANAGE,
        project=locked.project,
    )
    _require_draft(locked)
    if not line_key.strip() or not description.strip() or not unit.strip():
        raise ValidationError("کلید، شرح و واحد ردیف الزامی است.")
    if sort_order < 0:
        raise ValidationError("ترتیب نمایش نمی‌تواند منفی باشد.")
    _validate_item_references(
        organization=organization,
        baseline=locked,
        contract_item=contract_item,
        wbs_node=wbs_node,
        activity=activity,
    )
    quantity, rate, value = _line_value(quantity=planned_quantity, rate=unit_rate)
    item = BaselineItem.objects.create(
        organization=organization,
        baseline=locked,
        line_key=line_key.strip(),
        description=description.strip(),
        unit=unit.strip(),
        planned_quantity=quantity,
        unit_rate=rate,
        planned_value=value,
        contract_item=contract_item,
        wbs_node=wbs_node,
        activity=activity,
        sort_order=sort_order,
    )
    record_audit_event(
        action=AuditAction.PROJECT_BASELINE_ITEM_ADDED,
        entity_type="billing.BaselineItem",
        entity_id=str(item.pk),
        organization=organization,
        actor=actor,
        metadata={"baseline_id": str(locked.pk), "line_key": item.line_key},
    )
    return item


@transaction.atomic
def update_baseline_item(
    *,
    organization: Organization,
    actor: User,
    item: BaselineItem,
    description: str,
    unit: str,
    planned_quantity: Decimal | int | str,
    unit_rate: Decimal | int | str,
    contract_item: ContractItem | None = None,
    wbs_node: WBSNode | None = None,
    activity: Activity | None = None,
    sort_order: int = 0,
) -> BaselineItem:
    try:
        locked_item = (
            BaselineItem.objects.select_for_update()
            .select_related("baseline")
            .get(pk=item.pk, organization=organization)
        )
    except BaselineItem.DoesNotExist as exc:
        raise PermissionDenied("ردیف مبنا متعلق به این سازمان نیست.") from exc
    locked = _locked_baseline(organization=organization, baseline=locked_item.baseline)
    _require_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.BASELINES_MANAGE,
        project=locked.project,
    )
    _require_draft(locked)
    if not description.strip() or not unit.strip() or sort_order < 0:
        raise ValidationError("شرح، واحد و ترتیب نمایش ردیف معتبر نیست.")
    _validate_item_references(
        organization=organization,
        baseline=locked,
        contract_item=contract_item,
        wbs_node=wbs_node,
        activity=activity,
    )
    quantity, rate, value = _line_value(quantity=planned_quantity, rate=unit_rate)
    locked_item.description = description.strip()
    locked_item.unit = unit.strip()
    locked_item.planned_quantity = quantity
    locked_item.unit_rate = rate
    locked_item.planned_value = value
    locked_item.contract_item = contract_item
    locked_item.wbs_node = wbs_node
    locked_item.activity = activity
    locked_item.sort_order = sort_order
    locked_item.save()
    record_audit_event(
        action=AuditAction.PROJECT_BASELINE_UPDATED,
        entity_type="billing.BaselineItem",
        entity_id=str(locked_item.pk),
        organization=organization,
        actor=actor,
        metadata={"baseline_id": str(locked.pk), "line_key": locked_item.line_key},
    )
    return locked_item


@transaction.atomic
def remove_baseline_item(
    *, organization: Organization, actor: User, item: BaselineItem
) -> None:
    try:
        locked_item = (
            BaselineItem.objects.select_for_update()
            .select_related("baseline")
            .get(pk=item.pk, organization=organization)
        )
    except BaselineItem.DoesNotExist as exc:
        raise PermissionDenied("ردیف مبنا متعلق به این سازمان نیست.") from exc
    locked = _locked_baseline(organization=organization, baseline=locked_item.baseline)
    _require_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.BASELINES_MANAGE,
        project=locked.project,
    )
    _require_draft(locked)
    line_key = locked_item.line_key
    locked_item.delete()
    record_audit_event(
        action=AuditAction.PROJECT_BASELINE_UPDATED,
        entity_type="billing.ProjectBaseline",
        entity_id=str(locked.pk),
        organization=organization,
        actor=actor,
        metadata={"removed_line_key": line_key},
    )


@transaction.atomic
def withdraw_project_baseline(
    *, organization: Organization, actor: User, baseline: ProjectBaseline, reason: str
) -> ProjectBaseline:
    locked = _locked_baseline(organization=organization, baseline=baseline)
    _require_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.BASELINES_MANAGE,
        project=locked.project,
    )
    if not reason.strip():
        raise ValidationError("دلیل استرداد الزامی است.")
    _require_draft(locked)
    locked.status = ProjectBaselineStatus.WITHDRAWN
    locked.withdrawn_by = actor
    locked.withdrawn_at = timezone.now()
    locked.withdrawal_reason = reason.strip()
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "status",
            "withdrawn_by",
            "withdrawn_at",
            "withdrawal_reason",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.PROJECT_BASELINE_WITHDRAWN,
        entity_type="billing.ProjectBaseline",
        entity_id=str(locked.pk),
        organization=organization,
        actor=actor,
        metadata={"reason": locked.withdrawal_reason},
    )
    return locked


@transaction.atomic
def _approve_project_baseline_domain(
    *, organization: Organization, actor: User, baseline: ProjectBaseline, reason: str
) -> ProjectBaseline:
    """Certify the baseline inside the shared runtime transaction only."""

    locked = _locked_baseline(organization=organization, baseline=baseline)
    _require_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.BASELINES_APPROVE,
        project=locked.project,
    )
    if not reason.strip():
        raise ValidationError("دلیل تأیید مبنا الزامی است.")
    _require_draft(locked)
    locked_contract = _locked_contract(
        organization=organization, contract=locked.contract
    )
    _validate_project_contract(
        organization=organization, project=locked.project, contract=locked_contract
    )
    amendments_total = _approved_amendment_total_locked(locked_contract)
    effective_ceiling = (locked_contract.contract_value + amendments_total).quantize(
        MONEY_QUANTUM
    )
    if effective_ceiling < 0:
        raise ValidationError("سقف مؤثر قرارداد نمی‌تواند منفی باشد.")
    baseline_total = _baseline_total_locked(locked)
    if baseline_total != effective_ceiling:
        raise ValidationError(
            "جمع ارزش گرد‌شده ردیف‌های مبنا باید دقیقاً با سقف مؤثر قرارداد برابر باشد."
        )
    current = (
        ProjectBaseline.objects.select_for_update()
        .filter(
            organization=organization,
            contract=locked_contract,
            status=ProjectBaselineStatus.APPROVED,
        )
        .first()
    )
    now = timezone.now()
    # The conditional unique constraint permits only one approved baseline per
    # contract. Free it before approving the replacement, inside this same
    # transaction, so the database invariant holds at every statement.
    if current is not None:
        current.status = ProjectBaselineStatus.SUPERSEDED
        current.superseded_by = locked
        current.save(update_fields=["status", "superseded_by", "updated_at"])

    locked.contract_value_snapshot = locked_contract.contract_value
    locked.approved_amendments_snapshot = amendments_total
    locked.effective_ceiling = effective_ceiling
    locked.status = ProjectBaselineStatus.APPROVED
    locked.approved_by = actor
    locked.approved_at = now
    locked.approval_reason = reason.strip()
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "contract_value_snapshot",
            "approved_amendments_snapshot",
            "effective_ceiling",
            "status",
            "approved_by",
            "approved_at",
            "approval_reason",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.PROJECT_BASELINE_APPROVED,
        entity_type="billing.ProjectBaseline",
        entity_id=str(locked.pk),
        organization=organization,
        actor=actor,
        metadata={
            "contract_id": str(locked_contract.pk),
            "version": locked.version,
            "line_total": str(baseline_total),
            "effective_ceiling": str(effective_ceiling),
            "superseded_baseline_id": str(current.pk) if current else None,
            "reason": locked.approval_reason,
        },
    )
    return locked


def request_project_baseline_approval(
    *, organization: Organization, actor: User, baseline: ProjectBaseline
):
    """Request approval through the shared WorkflowInstance/WorkItem runtime."""

    from .workflow import request_project_baseline_approval_with_workflow

    return request_project_baseline_approval_with_workflow(
        organization=organization, actor=actor, baseline=baseline
    )


def approve_project_baseline(
    *,
    organization: Organization,
    actor: User,
    baseline: ProjectBaseline,
    reason: str,
) -> ProjectBaseline:
    """Approve only by completing the active shared work item."""

    from .workflow import approve_project_baseline_with_workflow

    return approve_project_baseline_with_workflow(
        organization=organization, actor=actor, baseline=baseline, reason=reason
    )


def _require_progress_permission(
    *, actor: User, organization: Organization, permission: BusinessPermissionCode
) -> None:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        message="مجوز لازم برای پیشرفت این سازمان را ندارید.",
    )


def _locked_progress_record(
    *, organization: Organization, record: ProgressRecord
) -> ProgressRecord:
    try:
        return (
            ProgressRecord.objects.select_for_update()
            .select_related("baseline", "baseline_item")
            .get(pk=record.pk, organization=organization)
        )
    except ProgressRecord.DoesNotExist as exc:
        raise PermissionDenied("رکورد پیشرفت متعلق به این سازمان نیست.") from exc


def _locked_progress_baseline_item(
    *, organization: Organization, baseline: ProjectBaseline, item: BaselineItem
) -> tuple[ProjectBaseline, BaselineItem]:
    locked_baseline = _locked_baseline(organization=organization, baseline=baseline)
    try:
        locked_item = BaselineItem.objects.select_for_update().get(
            pk=item.pk, organization=organization, baseline=locked_baseline
        )
    except BaselineItem.DoesNotExist as exc:
        raise PermissionDenied(
            "ردیف مبنا متعلق به این سازمان یا مبنای انتخابی نیست."
        ) from exc
    if locked_baseline.status != ProjectBaselineStatus.APPROVED:
        raise ValidationError("ثبت پیشرفت فقط بر مبنای تأییدشده مجاز است.")
    return locked_baseline, locked_item


def _progress_quantity(value: Decimal | int | str, *, label: str) -> Decimal:
    return _decimal_with_scale(
        value, quantum=QUANTITY_QUANTUM, label=label, nonnegative=True
    )


def _validate_measurement_fields(
    *,
    period_start: date,
    period_end: date,
    measured_on: date,
    source_type: str,
    source_reference: str,
) -> None:
    if period_end < period_start:
        raise ValidationError("پایان دوره نمی‌تواند پیش از شروع دوره باشد.")
    if not period_start <= measured_on <= period_end:
        raise ValidationError("تاریخ اندازه‌گیری باید در دوره اندازه‌گیری باشد.")
    if not source_type.strip() or not source_reference.strip():
        raise ValidationError("نوع و شناسه منبع اندازه‌گیری الزامی است.")


def get_progress_records(
    *, actor: User, organization: Organization
) -> QuerySet[ProgressRecord]:
    """Return progress sources from the caller's active organization only."""

    _require_progress_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.PROGRESS_VIEW,
    )
    return ProgressRecord.objects.filter(organization=organization).select_related(
        "baseline", "baseline_item", "created_by", "verified_by", "corrects"
    )


def get_progress_claims(
    *, actor: User, organization: Organization
) -> QuerySet[ProgressClaim]:
    """Return only claims visible in the caller's active organization."""

    _require_progress_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.CLAIMS_VIEW,
    )
    return ProgressClaim.objects.filter(organization=organization).select_related(
        "project",
        "contract",
        "baseline",
        "created_by",
        "submitted_by",
        "approved_by",
        "returned_revision",
    )


@transaction.atomic
def create_progress_record(
    *,
    organization: Organization,
    actor: User,
    baseline: ProjectBaseline,
    baseline_item: BaselineItem,
    period_start: date,
    period_end: date,
    measured_on: date,
    source_type: str,
    source_reference: str,
    period_quantity: Decimal | int | str,
    cumulative_quantity: Decimal | int | str,
    evidence: str = "",
) -> ProgressRecord:
    """Create a draft measurement. Verification computes the durable ledger link."""

    _require_progress_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.PROGRESS_RECORD,
    )
    locked_baseline, locked_item = _locked_progress_baseline_item(
        organization=organization, baseline=baseline, item=baseline_item
    )
    _validate_measurement_fields(
        period_start=period_start,
        period_end=period_end,
        measured_on=measured_on,
        source_type=source_type,
        source_reference=source_reference,
    )
    normalized_period = _progress_quantity(period_quantity, label="مقدار دوره")
    normalized_cumulative = _progress_quantity(cumulative_quantity, label="مقدار تجمعی")
    if normalized_cumulative > locked_item.planned_quantity:
        raise ValidationError(
            "مقدار تجمعی نمی‌تواند از مقدار مبنای تأییدشده بیشتر باشد."
        )
    if normalized_period > normalized_cumulative:
        raise ValidationError("مقدار دوره نمی‌تواند از مقدار تجمعی بیشتر باشد.")
    if ProgressRecord.objects.filter(
        organization=organization,
        baseline_item=locked_item,
        source_type=source_type.strip(),
        source_reference=source_reference.strip(),
    ).exists():
        raise ValidationError("این منبع اندازه‌گیری قبلاً برای ردیف مبنا ثبت شده است.")
    record = ProgressRecord.objects.create(
        organization=organization,
        baseline=locked_baseline,
        baseline_item=locked_item,
        period_start=period_start,
        period_end=period_end,
        measured_on=measured_on,
        source_type=source_type.strip(),
        source_reference=source_reference.strip(),
        evidence=evidence.strip(),
        period_quantity=normalized_period,
        cumulative_quantity=normalized_cumulative,
        created_by=actor,
        updated_by=actor,
    )
    record_audit_event(
        action=AuditAction.PROGRESS_RECORDED,
        entity_type="billing.ProgressRecord",
        entity_id=str(record.pk),
        organization=organization,
        actor=actor,
        metadata={
            "baseline_id": str(locked_baseline.pk),
            "baseline_item_id": str(locked_item.pk),
            "source": f"{record.source_type}:{record.source_reference}",
            "cumulative_quantity": str(record.cumulative_quantity),
        },
    )
    return record


@transaction.atomic
def create_progress_correction(
    *,
    organization: Organization,
    actor: User,
    record: ProgressRecord,
    source_type: str,
    source_reference: str,
    period_quantity: Decimal | int | str,
    cumulative_quantity: Decimal | int | str,
    evidence: str,
) -> ProgressRecord:
    """Append a replacement source; finalized measurements are never overwritten."""

    _require_progress_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.PROGRESS_RECORD,
    )
    corrected = _locked_progress_record(organization=organization, record=record)
    if corrected.status != ProgressRecordStatus.VERIFIED:
        raise ValidationError(
            "فقط رکورد راستی‌آزمایی‌شده از مسیر اصلاح قابل جایگزینی است."
        )
    if ProgressRecord.objects.filter(corrects=corrected).exists():
        raise ValidationError("برای این رکورد قبلاً یک اصلاح پیوندخورده ثبت شده است.")
    _validate_measurement_fields(
        period_start=corrected.period_start,
        period_end=corrected.period_end,
        measured_on=corrected.measured_on,
        source_type=source_type,
        source_reference=source_reference,
    )
    normalized_period = _progress_quantity(period_quantity, label="مقدار دوره اصلاحی")
    normalized_cumulative = _progress_quantity(
        cumulative_quantity, label="مقدار تجمعی اصلاحی"
    )
    if normalized_cumulative > corrected.baseline_item.planned_quantity:
        raise ValidationError("مقدار تجمعی اصلاحی از مقدار مبنای تأییدشده بیشتر است.")
    if normalized_period > normalized_cumulative:
        raise ValidationError("مقدار دوره اصلاحی نمی‌تواند از تجمعی بیشتر باشد.")
    replacement = ProgressRecord.objects.create(
        organization=organization,
        baseline=corrected.baseline,
        baseline_item=corrected.baseline_item,
        period_start=corrected.period_start,
        period_end=corrected.period_end,
        measured_on=corrected.measured_on,
        source_type=source_type.strip(),
        source_reference=source_reference.strip(),
        evidence=evidence.strip(),
        period_quantity=normalized_period,
        cumulative_quantity=normalized_cumulative,
        corrects=corrected,
        created_by=actor,
        updated_by=actor,
    )
    record_audit_event(
        action=AuditAction.PROGRESS_CORRECTION_RECORDED,
        entity_type="billing.ProgressRecord",
        entity_id=str(replacement.pk),
        organization=organization,
        actor=actor,
        metadata={"corrects_id": str(corrected.pk)},
    )
    return replacement


def _latest_verified_progress_locked(
    *, organization: Organization, item: BaselineItem
) -> ProgressRecord | None:
    return (
        ProgressRecord.objects.select_for_update()
        .filter(
            organization=organization,
            baseline_item=item,
            status=ProgressRecordStatus.VERIFIED,
        )
        .order_by("-verified_at", "-created_at")
        .first()
    )


@transaction.atomic
def _verify_progress_record_domain(
    *, organization: Organization, actor: User, record: ProgressRecord, reason: str
) -> ProgressRecord:
    _require_progress_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.PROGRESS_VERIFY,
    )
    if not reason.strip():
        raise ValidationError("دلیل راستی‌آزمایی الزامی است.")
    locked = _locked_progress_record(organization=organization, record=record)
    if locked.status != ProgressRecordStatus.SUBMITTED:
        raise ValidationError("فقط رکورد ارسال‌شده قابل راستی‌آزمایی است.")
    _, item = _locked_progress_baseline_item(
        organization=organization, baseline=locked.baseline, item=locked.baseline_item
    )
    latest = _latest_verified_progress_locked(organization=organization, item=item)
    if locked.corrects_id:
        if latest is None or latest.pk != locked.corrects_id:
            raise ValidationError(
                "اصلاح فقط آخرین رکورد راستی‌آزمایی‌شده را جایگزین می‌کند."
            )
        previous_cumulative = latest.previous_cumulative_quantity
    else:
        previous_cumulative = (
            latest.cumulative_quantity if latest is not None else Decimal("0.0000")
        )
        if latest is not None and locked.measured_on < latest.measured_on:
            raise ValidationError(
                "اندازه‌گیری عادی نمی‌تواند از آخرین منبع تأییدشده قدیمی‌تر باشد."
            )
    if locked.cumulative_quantity < previous_cumulative:
        raise ValidationError("مقدار تجمعی نمی‌تواند از تجمعی تأییدشده پیشین کمتر باشد.")
    if locked.cumulative_quantity > item.planned_quantity:
        raise ValidationError("مقدار تجمعی از مقدار مبنای تأییدشده بیشتر است.")
    period_quantity = (locked.cumulative_quantity - previous_cumulative).quantize(
        QUANTITY_QUANTUM
    )
    if locked.period_quantity != period_quantity:
        raise ValidationError("مقدار دوره باید با اختلاف تجمعی منبع پیشین برابر باشد.")
    locked.previous_cumulative_quantity = previous_cumulative
    locked.status = ProgressRecordStatus.VERIFIED
    locked.verified_by = actor
    locked.verified_at = timezone.now()
    locked.verification_reason = reason.strip()
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "previous_cumulative_quantity",
            "status",
            "verified_by",
            "verified_at",
            "verification_reason",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.PROGRESS_VERIFIED,
        entity_type="billing.ProgressRecord",
        entity_id=str(locked.pk),
        organization=organization,
        actor=actor,
        metadata={
            "previous_cumulative_quantity": str(previous_cumulative),
            "period_quantity": str(period_quantity),
            "cumulative_quantity": str(locked.cumulative_quantity),
            "corrects_id": str(locked.corrects_id) if locked.corrects_id else None,
            "reason": locked.verification_reason,
        },
    )
    return locked


@transaction.atomic
def _reject_progress_record_domain(
    *, organization: Organization, actor: User, record: ProgressRecord, reason: str
) -> ProgressRecord:
    _require_progress_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.PROGRESS_VERIFY,
    )
    if not reason.strip():
        raise ValidationError("دلیل رد الزامی است.")
    locked = _locked_progress_record(organization=organization, record=record)
    if locked.status != ProgressRecordStatus.SUBMITTED:
        raise ValidationError("فقط رکورد ارسال‌شده قابل رد است.")
    locked.status = ProgressRecordStatus.REJECTED
    locked.rejected_by = actor
    locked.rejected_at = timezone.now()
    locked.rejection_reason = reason.strip()
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "status",
            "rejected_by",
            "rejected_at",
            "rejection_reason",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.PROGRESS_REJECTED,
        entity_type="billing.ProgressRecord",
        entity_id=str(locked.pk),
        organization=organization,
        actor=actor,
        metadata={"reason": locked.rejection_reason},
    )
    return locked


def request_progress_verification(
    *, organization: Organization, actor: User, record: ProgressRecord
):
    from .workflow import request_progress_verification_with_workflow

    return request_progress_verification_with_workflow(
        organization=organization, actor=actor, record=record
    )


def verify_progress_record(
    *, organization: Organization, actor: User, record: ProgressRecord, reason: str
) -> ProgressRecord:
    from .workflow import verify_progress_record_with_workflow

    return verify_progress_record_with_workflow(
        organization=organization, actor=actor, record=record, reason=reason
    )


def reject_progress_record(
    *, organization: Organization, actor: User, record: ProgressRecord, reason: str
) -> ProgressRecord:
    from .workflow import reject_progress_record_with_workflow

    return reject_progress_record_with_workflow(
        organization=organization, actor=actor, record=record, reason=reason
    )


def _policy_snapshot(policy: BillingPolicy) -> dict[str, str | bool | int]:
    return {
        "claim_number_scope": policy.claim_number_scope,
        "period_boundary": policy.period_boundary,
        "allow_partial_periods": policy.allow_partial_periods,
        "allow_late_measurements": policy.allow_late_measurements,
        "money_decimal_places": policy.money_decimal_places,
        "tax_rate": str(policy.tax_rate),
        "tax_basis": policy.tax_basis,
        "insurance_rate": str(policy.insurance_rate),
        "insurance_basis": policy.insurance_basis,
        "retention_rate": str(policy.retention_rate),
        "retention_cap": str(policy.retention_cap),
        "advance_recovery_rate": str(policy.advance_recovery_rate),
        "advance_recovery_cap": str(policy.advance_recovery_cap),
        "allow_negative_corrective_claims": policy.allow_negative_corrective_claims,
    }


@transaction.atomic
def update_billing_policy(
    *, organization: Organization, actor: User, **values: object
) -> BillingPolicy:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.COMPANY_SETTINGS_CHANGE,
        message="اجازه تغییر سیاست تجاری این سازمان را ندارید.",
    )
    locked = Organization.objects.select_for_update().get(pk=organization.pk)
    policy, _ = BillingPolicy.objects.select_for_update().get_or_create(
        organization=locked
    )
    allowed = set(_policy_snapshot(policy))
    unknown = set(values) - allowed
    if unknown:
        raise ValidationError(
            f"تنظیمات تجاری ناشناخته‌اند: {', '.join(sorted(unknown))}"
        )
    for name, value in values.items():
        setattr(policy, name, value)
    policy.updated_by = actor
    policy.full_clean()
    policy.save()
    return policy


def get_billing_policy(*, organization: Organization) -> BillingPolicy:
    return BillingPolicy.objects.get_or_create(organization=organization)[0]


def _money(value: Decimal, places: int) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


@transaction.atomic
def create_progress_claim(
    *,
    organization: Organization,
    actor: User,
    baseline: ProjectBaseline,
    period_start: date,
    period_end: date,
    measurement_cutoff: date,
) -> ProgressClaim:
    _require_progress_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.CLAIMS_CREATE,
    )
    locked = _locked_baseline(organization=organization, baseline=baseline)
    if locked.status != ProjectBaselineStatus.APPROVED:
        raise ValidationError("صورت‌وضعیت فقط بر مبنای تأییدشده ساخته می‌شود.")
    policy = get_billing_policy(organization=organization)
    if (
        period_end < period_start
        or not period_start <= measurement_cutoff <= period_end
    ):
        raise ValidationError("دوره و تاریخ قطع اندازه‌گیری معتبر نیست.")
    if ProgressClaim.objects.filter(
        organization=organization,
        contract=locked.contract,
        baseline=locked,
        revision_number=1,
        period_start__lte=period_end,
        period_end__gte=period_start,
    ).exists():
        raise ValidationError("دوره صورت‌وضعیت پیش‌نویس با دوره موجود هم‌پوشانی دارد.")
    if policy.period_boundary == ClaimPeriodBoundary.CALENDAR and (
        period_start.day != 1
        or period_end.month == period_start.month
        and period_end.day < 28
    ):
        raise ValidationError("سیاست سازمان دوره تقویمی کامل را الزامی می‌کند.")
    scope = (
        {"organization": organization}
        if policy.claim_number_scope == ClaimNumberScope.ORGANIZATION
        else {"organization": organization, "contract": locked.contract}
    )
    number = (
        ProgressClaim.objects.filter(**scope).aggregate(value=Max("claim_number"))[
            "value"
        ]
        or 0
    ) + 1
    claim = ProgressClaim.objects.create(
        organization=organization,
        project=locked.project,
        contract=locked.contract,
        baseline=locked,
        claim_number=number,
        period_start=period_start,
        period_end=period_end,
        measurement_cutoff=measurement_cutoff,
        policy_snapshot=_policy_snapshot(policy),
        created_by=actor,
        updated_by=actor,
    )
    return recalculate_progress_claim(
        organization=organization, actor=actor, claim=claim
    )


@transaction.atomic
def recalculate_progress_claim(
    *, organization: Organization, actor: User, claim: ProgressClaim
) -> ProgressClaim:
    _require_progress_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.CLAIMS_REVISE,
    )
    try:
        locked = (
            ProgressClaim.objects.select_for_update()
            .select_related("baseline", "contract")
            .get(pk=claim.pk, organization=organization)
        )
    except ProgressClaim.DoesNotExist as exc:
        raise PermissionDenied("صورت‌وضعیت متعلق به این سازمان نیست.") from exc
    if locked.status != "draft":
        raise ValidationError("فقط صورت‌وضعیت پیش‌نویس قابل محاسبه مجدد است.")
    policy = locked.policy_snapshot
    places = int(policy["money_decimal_places"])
    ProgressClaimSource.objects.filter(claim_item__claim=locked).delete()
    ProgressClaimItem.objects.filter(claim=locked).delete()
    records = (
        ProgressRecord.objects.select_related("baseline_item")
        .filter(
            organization=organization,
            baseline=locked.baseline,
            status=ProgressRecordStatus.VERIFIED,
            measured_on__gte=locked.period_start,
            measured_on__lte=locked.measurement_cutoff,
        )
        .order_by("baseline_item_id", "verified_at")
    )
    latest: dict[object, ProgressRecord] = {}
    for record in records:
        latest[record.baseline_item_id] = record
    gross = Decimal(0)
    for item_id, record in latest.items():
        previous = record.previous_cumulative_quantity
        current = record.cumulative_quantity - previous
        amount = _money(current * record.baseline_item.unit_rate, places)
        item = ProgressClaimItem.objects.create(
            claim=locked,
            baseline_item_id=item_id,
            previous_cumulative_quantity=previous,
            current_quantity=current,
            new_cumulative_quantity=record.cumulative_quantity,
            unit_rate_snapshot=record.baseline_item.unit_rate,
            current_amount=amount,
        )
        ProgressClaimSource.objects.create(claim_item=item, progress_record=record)
        gross += amount
    gross = _money(gross, places)
    adjustments = []
    for adjustment_type, rate_key, cap_key, sign in (
        (ClaimAdjustmentType.RETENTION, "retention_rate", "retention_cap", -1),
        (ClaimAdjustmentType.TAX, "tax_rate", None, 1),
        (ClaimAdjustmentType.INSURANCE, "insurance_rate", None, -1),
        (
            ClaimAdjustmentType.ADVANCE_RECOVERY,
            "advance_recovery_rate",
            "advance_recovery_cap",
            -1,
        ),
    ):
        rate = Decimal(str(policy[rate_key]))
        amount = _money(gross * rate / Decimal(100), places)
        if cap_key:
            amount = min(amount, Decimal(str(policy[cap_key])))
        if amount:
            adjustments.append(
                ClaimAdjustment(
                    claim=locked,
                    adjustment_type=adjustment_type,
                    description=adjustment_type,
                    sequence=len(adjustments) + 1,
                    rate_snapshot=rate,
                    base_amount_snapshot=gross,
                    amount=amount * sign,
                )
            )
    ClaimAdjustment.objects.filter(claim=locked).delete()
    ClaimAdjustment.objects.bulk_create(adjustments)
    total_adjustments = sum((item.amount for item in adjustments), Decimal(0))
    net = _money(gross + total_adjustments, places)
    if net < 0 and not policy["allow_negative_corrective_claims"]:
        raise ValidationError("سیاست سازمان صورت‌وضعیت خالص منفی را مجاز نمی‌داند.")
    if gross > locked.baseline.effective_ceiling:
        raise ValidationError("جمع ناخالص از سقف مبنای تأییدشده بیشتر است.")
    (
        locked.gross_amount,
        locked.adjustment_amount,
        locked.net_amount,
        locked.updated_by,
    ) = gross, total_adjustments, net, actor
    locked.save(
        update_fields=[
            "gross_amount",
            "adjustment_amount",
            "net_amount",
            "updated_by",
            "updated_at",
        ]
    )
    return locked


@transaction.atomic
def create_progress_claim_revision(
    *, organization: Organization, actor: User, claim: ProgressClaim
) -> ProgressClaim:
    _require_progress_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.CLAIMS_REVISE,
    )
    original = ProgressClaim.objects.select_for_update().get(
        pk=claim.pk, organization=organization
    )
    revision = (
        ProgressClaim.objects.filter(
            organization=organization,
            contract=original.contract,
            claim_number=original.claim_number,
        ).aggregate(value=Max("revision_number"))["value"]
        or 0
    ) + 1
    clone = ProgressClaim.objects.create(
        organization=organization,
        project=original.project,
        contract=original.contract,
        baseline=original.baseline,
        claim_number=original.claim_number,
        revision_number=revision,
        period_start=original.period_start,
        period_end=original.period_end,
        measurement_cutoff=original.measurement_cutoff,
        policy_snapshot=original.policy_snapshot,
        created_by=actor,
        updated_by=actor,
    )
    return recalculate_progress_claim(
        organization=organization, actor=actor, claim=clone
    )


@transaction.atomic
def _approve_progress_claim_domain(
    *, organization: Organization, actor: User, claim: ProgressClaim, reason: str
) -> ProgressClaim:
    _require_progress_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.CLAIMS_APPROVE,
    )
    if not reason.strip():
        raise ValidationError("دلیل تأیید صورت‌وضعیت الزامی است.")
    try:
        locked = (
            ProgressClaim.objects.select_for_update()
            .select_related("contract", "baseline")
            .get(pk=claim.pk, organization=organization)
        )
    except ProgressClaim.DoesNotExist as exc:
        raise PermissionDenied("صورت‌وضعیت متعلق به این سازمان نیست.") from exc
    if locked.status != "submitted" or not locked.submission_snapshot:
        raise ValidationError("فقط صورت‌وضعیت ارسال‌شده با تصویر ثابت قابل تأیید است.")
    if (
        locked.submitted_by_id == actor.pk
        and OrganizationMembership.objects.filter(
            organization=organization,
            status=MembershipStatus.ACTIVE,
            role_definition__is_active=True,
            user__is_active=True,
            role_definition__permissions__code=BusinessPermissionCode.CLAIMS_APPROVE,
            role_definition__permissions__is_active=True,
        )
        .exclude(user=actor)
        .exists()
    ):
        raise PermissionDenied(
            "با وجود تأییدکننده واجدشرایط دیگر، تهیه‌کننده نمی‌تواند صورت‌وضعیت خود را تأیید کند."
        )
    _locked_contract(organization=organization, contract=locked.contract)
    baseline = _locked_baseline(organization=organization, baseline=locked.baseline)
    if baseline.status != ProjectBaselineStatus.APPROVED:
        raise ValidationError("مبنای صورت‌وضعیت در زمان تأیید باید تأییدشده باشد.")
    list(
        ProgressClaim.objects.select_for_update().filter(
            organization=organization,
            contract=locked.contract,
            claim_number=locked.claim_number,
        )
    )
    if (
        ProgressClaim.objects.filter(
            organization=organization,
            contract=locked.contract,
            claim_number=locked.claim_number,
            status="approved",
        )
        .exclude(pk=locked.pk)
        .exists()
    ):
        raise ValidationError(
            "برای این شماره صورت‌وضعیت یک revision تأییدشده وجود دارد."
        )
    locked.status = "approved"
    locked.approved_by = actor
    locked.approved_at = timezone.now()
    locked.approval_reason = reason.strip()
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "approval_reason",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.PROGRESS_CLAIM_APPROVED,
        entity_type="billing.ProgressClaim",
        entity_id=str(locked.pk),
        organization=organization,
        actor=actor,
        metadata={
            "claim_number": locked.claim_number,
            "revision": locked.revision_number,
            "reason": locked.approval_reason,
        },
    )
    return locked


def _copy_returned_claim_revision(
    *, original: ProgressClaim, actor: User
) -> ProgressClaim:
    revision = (
        ProgressClaim.objects.filter(
            organization=original.organization,
            contract=original.contract,
            claim_number=original.claim_number,
        ).aggregate(value=Max("revision_number"))["value"]
        or 0
    ) + 1
    clone = ProgressClaim.objects.create(
        organization=original.organization,
        project=original.project,
        contract=original.contract,
        baseline=original.baseline,
        claim_number=original.claim_number,
        revision_number=revision,
        period_start=original.period_start,
        period_end=original.period_end,
        measurement_cutoff=original.measurement_cutoff,
        policy_snapshot=original.policy_snapshot,
        gross_amount=original.gross_amount,
        adjustment_amount=original.adjustment_amount,
        net_amount=original.net_amount,
        created_by=original.submitted_by or original.created_by,
        updated_by=original.submitted_by or original.created_by or actor,
    )
    for item in original.items.prefetch_related("sources").order_by("pk"):
        copied_item = ProgressClaimItem.objects.create(
            claim=clone,
            baseline_item=item.baseline_item,
            previous_cumulative_quantity=item.previous_cumulative_quantity,
            current_quantity=item.current_quantity,
            new_cumulative_quantity=item.new_cumulative_quantity,
            unit_rate_snapshot=item.unit_rate_snapshot,
            current_amount=item.current_amount,
        )
        for source in item.sources.all():
            ProgressClaimSource.objects.create(
                claim_item=copied_item,
                progress_record=source.progress_record,
            )
    for adjustment in original.adjustments.order_by("sequence", "pk"):
        ClaimAdjustment.objects.create(
            claim=clone,
            adjustment_type=adjustment.adjustment_type,
            description=adjustment.description,
            sequence=adjustment.sequence,
            rate_snapshot=adjustment.rate_snapshot,
            base_amount_snapshot=adjustment.base_amount_snapshot,
            amount=adjustment.amount,
            evidence=adjustment.evidence,
        )
    return clone


@transaction.atomic
def _return_progress_claim_domain(
    *, organization: Organization, actor: User, claim: ProgressClaim, reason: str
) -> ProgressClaim:
    _require_progress_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.CLAIMS_APPROVE,
    )
    if not reason.strip():
        raise ValidationError("دلیل بازگردانی صورت‌وضعیت الزامی است.")
    try:
        locked = (
            ProgressClaim.objects.select_for_update()
            .select_related("contract", "baseline")
            .get(pk=claim.pk, organization=organization)
        )
    except ProgressClaim.DoesNotExist as exc:
        raise PermissionDenied("صورت‌وضعیت متعلق به این سازمان نیست.") from exc
    if locked.status != "submitted" or not locked.submission_snapshot:
        raise ValidationError(
            "فقط صورت‌وضعیت ارسال‌شده با تصویر ثابت قابل بازگردانی است."
        )
    revision = _copy_returned_claim_revision(original=locked, actor=actor)
    locked.status = "returned"
    locked.returned_by = actor
    locked.returned_at = timezone.now()
    locked.return_reason = reason.strip()
    locked.returned_revision = revision
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "status",
            "returned_by",
            "returned_at",
            "return_reason",
            "returned_revision",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.PROGRESS_CLAIM_RETURNED,
        entity_type="billing.ProgressClaim",
        entity_id=str(locked.pk),
        organization=organization,
        actor=actor,
        metadata={
            "claim_number": locked.claim_number,
            "revision": locked.revision_number,
            "new_revision_id": str(revision.pk),
            "reason": locked.return_reason,
        },
    )
    record_audit_event(
        action=AuditAction.PROGRESS_CLAIM_REVISION_CREATED,
        entity_type="billing.ProgressClaim",
        entity_id=str(revision.pk),
        organization=organization,
        actor=actor,
        metadata={"returned_from_id": str(locked.pk)},
    )
    return locked


def submit_progress_claim(
    *, organization: Organization, actor: User, claim: ProgressClaim
):
    from .workflow import submit_progress_claim_with_workflow

    return submit_progress_claim_with_workflow(
        organization=organization, actor=actor, claim=claim
    )


def approve_progress_claim(
    *, organization: Organization, actor: User, claim: ProgressClaim, reason: str
) -> ProgressClaim:
    from .workflow import approve_progress_claim_with_workflow

    return approve_progress_claim_with_workflow(
        organization=organization, actor=actor, claim=claim, reason=reason
    )


def return_progress_claim(
    *, organization: Organization, actor: User, claim: ProgressClaim, reason: str
) -> ProgressClaim:
    from .workflow import return_progress_claim_with_workflow

    return return_progress_claim_with_workflow(
        organization=organization, actor=actor, claim=claim, reason=reason
    )


@dataclass(frozen=True)
class ProgressClaimSettlementSummary:
    """Read-only reconciliation of one approved claim against posted receipts."""

    claim_id: object
    approved_net_amount: Decimal
    settled_amount: Decimal
    outstanding_amount: Decimal


def _require_claim_settlement_permission(
    *, actor: User, organization: Organization, permission: BusinessPermissionCode
) -> None:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        message="مجوز لازم برای تسویه صورت‌وضعیت این سازمان را ندارید.",
    )


def _locked_settlement_claim(
    *, organization: Organization, claim: ProgressClaim
) -> ProgressClaim:
    try:
        return (
            ProgressClaim.objects.select_for_update()
            .select_related("project", "contract")
            .get(pk=claim.pk, organization=organization)
        )
    except ProgressClaim.DoesNotExist as exc:
        raise PermissionDenied("صورت‌وضعیت متعلق به این سازمان نیست.") from exc


def _locked_payment_allocation_for_settlement(
    *, organization: Organization, payment_allocation: PaymentAllocation
) -> tuple[Payment, PaymentAllocation]:
    """Lock cash, its contract allocation, then the claim in one global order."""

    try:
        preliminary = PaymentAllocation.objects.select_related("payment").get(
            pk=payment_allocation.pk,
            organization=organization,
        )
    except PaymentAllocation.DoesNotExist as exc:
        raise PermissionDenied("تخصیص پرداخت متعلق به این سازمان نیست.") from exc
    payment = Payment.objects.select_for_update().get(pk=preliminary.payment_id)
    allocation = (
        PaymentAllocation.objects.select_for_update(of=("self",))
        .select_related("contract", "payment__party")
        .get(pk=preliminary.pk, organization=organization)
    )
    return payment, allocation


def _active_settlement_total(*, claim: ProgressClaim) -> Decimal:
    return ClaimSettlementAllocation.objects.filter(
        claim=claim,
        status=ClaimSettlementAllocationStatus.ACTIVE,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")


def _active_payment_allocation_settlement_total(
    *, payment_allocation: PaymentAllocation
) -> Decimal:
    return ClaimSettlementAllocation.objects.filter(
        payment_allocation=payment_allocation,
        status=ClaimSettlementAllocationStatus.ACTIVE,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")


def _validate_settlement_context(
    *, claim: ProgressClaim, payment: Payment, payment_allocation: PaymentAllocation
) -> None:
    if claim.status != "approved":
        raise ValidationError("فقط صورت‌وضعیت تأییدشده قابل تسویه است.")
    if payment.status != PaymentStatus.POSTED:
        raise ValidationError("فقط دریافت ثبت‌شده و باطل‌نشده قابل تسویه است.")
    if payment.direction != PaymentDirection.RECEIPT:
        raise ValidationError("فقط دریافت قابل اتصال به صورت‌وضعیت است.")
    if payment_allocation.status != PaymentAllocationStatus.ACTIVE:
        raise ValidationError("فقط تخصیص پرداخت فعال قابل تسویه است.")
    if (
        payment.organization_id != claim.organization_id
        or payment_allocation.organization_id != claim.organization_id
        or payment.project_id != claim.project_id
        or payment_allocation.contract_id != claim.contract_id
        or (
            payment.contract_id is not None and payment.contract_id != claim.contract_id
        )
    ):
        raise ValidationError(
            "دریافت و تخصیص آن باید با سازمان، پروژه و قرارداد صورت‌وضعیت یکسان باشد."
        )
    if (
        not payment.party_id
        or not claim.contract.party_id
        or payment.party_id != claim.contract.party_id
    ):
        raise ValidationError(
            "طرف‌حساب دریافت و قرارداد باید با شناسه طرف تجاری یکسان و کامل باشد."
        )


@transaction.atomic
def allocate_progress_claim_settlement(
    *,
    organization: Organization,
    actor: User,
    claim: ProgressClaim,
    payment_allocation: PaymentAllocation,
    amount: Decimal | int | str,
    reason: str,
) -> ClaimSettlementAllocation:
    """Link an approved claim to an existing receipt allocation without cash mutation."""

    _require_claim_settlement_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.CLAIM_SETTLEMENTS_ALLOCATE,
    )
    normalized_amount = _decimal_with_scale(
        amount,
        quantum=MONEY_QUANTUM,
        label="مبلغ تسویه",
        positive=True,
    )
    if not reason.strip():
        raise ValidationError("دلیل تسویه الزامی است.")

    payment, locked_payment_allocation = _locked_payment_allocation_for_settlement(
        organization=organization,
        payment_allocation=payment_allocation,
    )
    locked_claim = _locked_settlement_claim(organization=organization, claim=claim)
    _validate_settlement_context(
        claim=locked_claim,
        payment=payment,
        payment_allocation=locked_payment_allocation,
    )
    allocation_remaining = (
        locked_payment_allocation.amount
        - _active_payment_allocation_settlement_total(
            payment_allocation=locked_payment_allocation
        )
    )
    claim_outstanding = locked_claim.net_amount - _active_settlement_total(
        claim=locked_claim
    )
    if normalized_amount > allocation_remaining:
        raise ValidationError("مبلغ تسویه از مانده تخصیص پرداخت بیشتر است.")
    if normalized_amount > claim_outstanding:
        raise ValidationError("مبلغ تسویه از مانده طلب صورت‌وضعیت بیشتر است.")

    settlement = ClaimSettlementAllocation.objects.create(
        organization=organization,
        claim=locked_claim,
        payment_allocation=locked_payment_allocation,
        amount=normalized_amount,
        reason=reason.strip(),
        created_by=actor,
    )
    record_audit_event(
        action=AuditAction.CLAIM_SETTLEMENT_ALLOCATED,
        entity_type="billing.ClaimSettlementAllocation",
        entity_id=str(settlement.pk),
        organization=organization,
        actor=actor,
        metadata={
            "claim_id": str(locked_claim.pk),
            "payment_allocation_id": str(locked_payment_allocation.pk),
            "payment_id": str(payment.pk),
            "amount": str(settlement.amount),
            "reason": settlement.reason,
        },
    )
    return settlement


def _reverse_locked_claim_settlement(
    *, settlement: ClaimSettlementAllocation, actor: User, reason: str
) -> ClaimSettlementAllocation:
    if settlement.status != ClaimSettlementAllocationStatus.ACTIVE:
        raise ValidationError("فقط تسویه فعال قابل برگشت است.")
    if not reason.strip():
        raise ValidationError("دلیل برگشت تسویه الزامی است.")
    settlement.status = ClaimSettlementAllocationStatus.REVERSED
    settlement.reversed_at = timezone.now()
    settlement.reversed_by = actor
    settlement.reversal_reason = reason.strip()
    settlement.save(
        update_fields=[
            "status",
            "reversed_at",
            "reversed_by",
            "reversal_reason",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.CLAIM_SETTLEMENT_REVERSED,
        entity_type="billing.ClaimSettlementAllocation",
        entity_id=str(settlement.pk),
        organization=settlement.organization,
        actor=actor,
        metadata={
            "claim_id": str(settlement.claim_id),
            "payment_allocation_id": str(settlement.payment_allocation_id),
            "amount": str(settlement.amount),
            "reason": settlement.reversal_reason,
        },
    )
    return settlement


@transaction.atomic
def reverse_progress_claim_settlement(
    *,
    organization: Organization,
    actor: User,
    settlement: ClaimSettlementAllocation,
    reason: str,
) -> ClaimSettlementAllocation:
    """Reverse a settlement append-only, retaining its payment allocation history."""

    _require_claim_settlement_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.CLAIM_SETTLEMENTS_REVERSE,
    )
    try:
        preliminary = ClaimSettlementAllocation.objects.select_related(
            "payment_allocation__payment"
        ).get(pk=settlement.pk, organization=organization)
    except ClaimSettlementAllocation.DoesNotExist as exc:
        raise PermissionDenied("تخصیص تسویه متعلق به این سازمان نیست.") from exc
    payment = Payment.objects.select_for_update().get(
        pk=preliminary.payment_allocation.payment_id
    )
    payment_allocation = PaymentAllocation.objects.select_for_update().get(
        pk=preliminary.payment_allocation_id,
        organization=organization,
    )
    locked_claim = _locked_settlement_claim(
        organization=organization,
        claim=preliminary.claim,
    )
    locked_settlement = ClaimSettlementAllocation.objects.select_for_update().get(
        pk=preliminary.pk,
        organization=organization,
        claim=locked_claim,
        payment_allocation=payment_allocation,
    )
    if payment.organization_id != organization.pk:
        raise PermissionDenied("پرداخت متعلق به این سازمان نیست.")
    return _reverse_locked_claim_settlement(
        settlement=locked_settlement,
        actor=actor,
        reason=reason,
    )


def reverse_claim_settlements_for_payment_allocation(
    *, payment_allocation: PaymentAllocation, actor: User, reason: str
) -> None:
    """Causally reverse claim settlements when their source allocation is reversed."""

    for settlement in (
        ClaimSettlementAllocation.objects.select_for_update()
        .filter(
            payment_allocation=payment_allocation,
            status=ClaimSettlementAllocationStatus.ACTIVE,
        )
        .order_by("pk")
    ):
        _reverse_locked_claim_settlement(
            settlement=settlement,
            actor=actor,
            reason=reason,
        )


def get_progress_claim_settlement_summary(
    *, organization: Organization, actor: User, claim: ProgressClaim
) -> ProgressClaimSettlementSummary:
    """Return the tenant-scoped outstanding receivable without changing cash state."""

    _require_claim_settlement_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.CLAIM_SETTLEMENTS_VIEW,
    )
    try:
        scoped_claim = ProgressClaim.objects.get(pk=claim.pk, organization=organization)
    except ProgressClaim.DoesNotExist as exc:
        raise PermissionDenied("صورت‌وضعیت متعلق به این سازمان نیست.") from exc
    settled_amount = _active_settlement_total(claim=scoped_claim)
    return ProgressClaimSettlementSummary(
        claim_id=scoped_claim.pk,
        approved_net_amount=scoped_claim.net_amount,
        settled_amount=settled_amount,
        outstanding_amount=scoped_claim.net_amount - settled_amount,
    )
