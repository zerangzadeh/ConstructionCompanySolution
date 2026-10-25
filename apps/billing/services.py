"""F6 billing application services for baselines and progress measurement."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
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
    ContractTermVersion,
    ContractTermVersionStatus,
)
from apps.organizations.authorization import (
    get_active_membership,
    require_business_permission,
    scope_queryset,
)
from apps.organizations.models import (
    SUPPORTED_BASE_CURRENCY,
    BusinessPermissionCode,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationSettings,
    PlatformPolicyVersion,
    PolicyReviewDisposition,
    PolicySourceBasis,
    PolicyVersionStatus,
)
from apps.organizations.policy_services import (
    resolve_effective_platform_regulatory_policy,
)
from apps.organizations.policy_specs import (
    RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE,
    validate_policy_for_consumer,
)
from apps.parties.models import PartyIdentitySnapshot
from apps.projects.models import Activity, Project, WBSNode
from apps.subledgers.models import Obligation, ObligationDirection, SettlementAllocation
from apps.subledgers.services import allocate_settlement, reverse_settlement
from apps.treasury.models import TreasuryMovement

from .models import (
    MONEY_QUANTUM,
    QUANTITY_QUANTUM,
    BaselineItem,
    ClaimAdjustment,
    ClaimAdjustmentType,
    ClaimNumberScope,
    ClaimPeriodBoundary,
    ProgressClaim,
    ProgressClaimCorrectionKind,
    ProgressClaimItem,
    ProgressClaimSource,
    ProgressRecord,
    ProgressRecordStatus,
    ProjectBaseline,
    ProjectBaselineStatus,
    TenantBillingConfiguration,
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
    *,
    organization: Organization,
    baseline: ProjectBaseline,
    item: BaselineItem,
    allow_superseded: bool = False,
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
    allowed_statuses = {ProjectBaselineStatus.APPROVED}
    if allow_superseded:
        allowed_statuses.add(ProjectBaselineStatus.SUPERSEDED)
    if locked_baseline.status not in allowed_statuses:
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

    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.PROGRESS_VIEW,
        message="مجوز لازم برای مشاهده پیشرفت را ندارید.",
        allow_any_scope=True,
    )
    return scope_queryset(
        ProgressRecord.objects.filter(organization=organization),
        membership=membership,
        project_lookup="baseline__project_id",
    ).select_related(
        "baseline", "baseline_item", "created_by", "verified_by", "corrects"
    )


def get_progress_claims(
    *, actor: User, organization: Organization
) -> QuerySet[ProgressClaim]:
    """Return only claims visible in the caller's active organization."""

    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.CLAIMS_VIEW,
        message="مجوز لازم برای مشاهده صورت‌وضعیت را ندارید.",
        allow_any_scope=True,
    )
    return scope_queryset(
        ProgressClaim.objects.filter(organization=organization),
        membership=membership,
        project_lookup="project_id",
    ).select_related(
        "project",
        "contract",
        "baseline",
        "created_by",
        "submitted_by",
        "approved_by",
        "returned_revision",
        "corrects",
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
            baseline__contract=item.baseline.contract,
            baseline__effective_date__lte=item.baseline.effective_date,
            baseline_item__line_key=item.line_key,
            status=ProgressRecordStatus.VERIFIED,
        )
        .order_by("-measured_on", "-verified_at", "-created_at")
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
        organization=organization,
        baseline=locked.baseline,
        item=locked.baseline_item,
        allow_superseded=bool(locked.corrects_id),
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


def _billing_configuration_snapshot(
    configuration: TenantBillingConfiguration,
) -> dict[str, str | bool | int]:
    return {
        "claim_number_scope": configuration.claim_number_scope,
        "period_boundary": configuration.period_boundary,
        "allow_partial_periods": configuration.allow_partial_periods,
        "allow_late_measurements": configuration.allow_late_measurements,
        "currency_decimal_places": configuration.currency_decimal_places,
    }


@transaction.atomic
def update_billing_configuration(
    *, organization: Organization, actor: User, **values: object
) -> TenantBillingConfiguration:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.COMPANY_SETTINGS_CHANGE,
        message="اجازه تغییر سیاست تجاری این سازمان را ندارید.",
    )
    locked = Organization.objects.select_for_update().get(pk=organization.pk)
    configuration, _ = (
        TenantBillingConfiguration.objects.select_for_update().get_or_create(
            organization=locked
        )
    )
    allowed = set(_billing_configuration_snapshot(configuration))
    unknown = set(values) - allowed
    if unknown:
        raise ValidationError(
            f"تنظیمات تجاری ناشناخته‌اند: {', '.join(sorted(unknown))}"
        )
    for name, value in values.items():
        setattr(configuration, name, value)
    configuration.updated_by = actor
    configuration.full_clean()
    configuration.save()
    return configuration


def get_billing_configuration(
    *, organization: Organization
) -> TenantBillingConfiguration:
    return TenantBillingConfiguration.objects.get_or_create(organization=organization)[
        0
    ]


def _resolve_contract_term_version(
    *, organization: Organization, contract: Contract, on_date: date
) -> ContractTermVersion:
    version = (
        ContractTermVersion.objects.select_for_update()
        .filter(
            organization=organization,
            contract=contract,
            status__in=(
                ContractTermVersionStatus.APPROVED,
                ContractTermVersionStatus.SUPERSEDED,
            ),
            effective_from__lte=on_date,
        )
        .order_by("-effective_from", "-version")
        .first()
    )
    if version is None:
        raise ValidationError("نسخه تأییدشده شرایط قرارداد برای تاریخ قطع وجود ندارد.")
    return version


def _resolve_regulatory_rule_version(
    *,
    organization: Organization,
    on_date: date,
    term_version: ContractTermVersion | None = None,
) -> PlatformPolicyVersion:
    if term_version is None:
        raise ValidationError("نسخه شرایط قرارداد برای تعیین طبقه‌بندی بیمه الزامی است.")
    try:
        term_version = ContractTermVersion.objects.select_related(
            "insurance_classification"
        ).get(
            pk=term_version.pk,
            organization=organization,
            contract__organization=organization,
            status__in=[
                ContractTermVersionStatus.APPROVED,
                ContractTermVersionStatus.SUPERSEDED,
            ],
            effective_from__lte=on_date,
        )
    except ContractTermVersion.DoesNotExist as exc:
        raise PermissionDenied("نسخه شرایط قرارداد معتبر یا در دسترس نیست.") from exc
    if not organization.is_active:
        raise PermissionDenied("سازمان فعال نیست.")
    return resolve_effective_platform_regulatory_policy(
        code=RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE,
        consumer="billing.progress_claim.calculate",
        on_date=on_date,
        insurance_classification=term_version.insurance_classification,
    )


def _party_identity_snapshot(contract: Contract) -> PartyIdentitySnapshot:
    if contract.party_id is None:
        raise ValidationError("قرارداد دریافتنی باید طرف تجاری مرجع داشته باشد.")
    snapshot = contract.party.identity_snapshots.order_by("-sequence").first()
    if snapshot is None:
        raise ValidationError("طرف قرارداد تصویر هویت قابل استناد ندارد.")
    return snapshot


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
    configuration = get_billing_configuration(organization=organization)
    if (
        period_end < period_start
        or not period_start <= measurement_cutoff <= period_end
    ):
        raise ValidationError("دوره و تاریخ قطع اندازه‌گیری معتبر نیست.")
    if locked.effective_date > measurement_cutoff:
        raise ValidationError("تاریخ اثر مبنا نمی‌تواند پس از تاریخ قطع باشد.")
    if ProgressClaim.objects.filter(
        organization=organization,
        contract=locked.contract,
        revision_number=1,
        period_start__lte=period_end,
        period_end__gte=period_start,
    ).exists():
        raise ValidationError("دوره صورت‌وضعیت پیش‌نویس با دوره موجود هم‌پوشانی دارد.")
    if configuration.period_boundary == ClaimPeriodBoundary.CALENDAR and (
        period_start.day != 1
        or period_end.month == period_start.month
        and period_end.day < 28
    ):
        raise ValidationError("سیاست سازمان دوره تقویمی کامل را الزامی می‌کند.")
    scope = (
        {"organization": organization}
        if configuration.claim_number_scope == ClaimNumberScope.ORGANIZATION
        else {"organization": organization, "contract": locked.contract}
    )
    number = (
        ProgressClaim.objects.filter(**scope).aggregate(value=Max("claim_number"))[
            "value"
        ]
        or 0
    ) + 1
    term_version = _resolve_contract_term_version(
        organization=organization,
        contract=locked.contract,
        on_date=measurement_cutoff,
    )
    regulatory_version = _resolve_regulatory_rule_version(
        term_version=term_version,
        organization=organization,
        on_date=measurement_cutoff,
    )
    identity_snapshot = _party_identity_snapshot(locked.contract)
    organization_settings, _ = OrganizationSettings.objects.get_or_create(
        organization=organization,
        defaults={"currency": SUPPORTED_BASE_CURRENCY},
    )
    claim = ProgressClaim.objects.create(
        organization=organization,
        project=locked.project,
        contract=locked.contract,
        baseline=locked,
        claim_number=number,
        period_start=period_start,
        period_end=period_end,
        measurement_cutoff=measurement_cutoff,
        billing_configuration_snapshot=_billing_configuration_snapshot(configuration),
        contract_term_version=term_version,
        regulatory_rule_version=regulatory_version,
        party_identity_snapshot=identity_snapshot,
        currency_code=organization_settings.currency,
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
            .select_related(
                "baseline",
                "contract_term_version",
                "regulatory_rule_version",
            )
            .get(pk=claim.pk, organization=organization)
        )
    except ProgressClaim.DoesNotExist as exc:
        raise PermissionDenied("صورت‌وضعیت متعلق به این سازمان نیست.") from exc
    if locked.status != "draft":
        raise ValidationError("فقط صورت‌وضعیت پیش‌نویس قابل محاسبه مجدد است.")
    configuration = locked.billing_configuration_snapshot
    places = int(configuration["currency_decimal_places"])
    term = locked.contract_term_version
    regulatory = locked.regulatory_rule_version
    if (
        term.organization_id != organization.pk
        or term.contract_id != locked.contract_id
        or term.status
        not in {
            ContractTermVersionStatus.APPROVED,
            ContractTermVersionStatus.SUPERSEDED,
        }
        or term.effective_from > locked.measurement_cutoff
    ):
        raise ValidationError("نسخه شرایط پین‌شده برای این صورت‌وضعیت معتبر نیست.")
    if (
        regulatory.status
        not in {PolicyVersionStatus.PUBLISHED, PolicyVersionStatus.RETIRED}
        or regulatory.effective_from > locked.measurement_cutoff
        or (
            regulatory.effective_to is not None
            and regulatory.effective_to <= locked.measurement_cutoff
        )
    ):
        raise ValidationError("نسخه مقرراتی پین‌شده برای این صورت‌وضعیت معتبر نیست.")
    if (
        not term.insurance_classification_id
        or regulatory.insurance_classification_id != term.insurance_classification_id
    ):
        raise ValidationError(
            "قاعده مقرراتی با طبقه‌بندی بیمه شرایط قرارداد هم‌خوان نیست."
        )
    if not term.insurance_classification.is_active or not regulatory.policy.is_active:
        raise ValidationError("طبقه‌بندی بیمه یا سیاست غیرفعال است.")
    validate_policy_for_consumer(
        policy_version=regulatory,
        consumer="billing.progress_claim.calculate",
        expected_policy_code=RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE,
    )
    if (
        regulatory.source_basis != PolicySourceBasis.EXTERNAL_AUTHORITY
        or not regulatory.source_links.exists()
        or not regulatory.review_evidence.filter(
            disposition=PolicyReviewDisposition.ACCEPTED
        ).exists()
    ):
        raise ValidationError("نسخه مقرراتی پین‌شده شواهد معتبر ندارد.")
    regulatory_parameters = regulatory.parameters
    ProgressClaimSource.objects.filter(claim_item__claim=locked).delete()
    ProgressClaimItem.objects.filter(claim=locked).delete()
    ClaimAdjustment.objects.filter(claim=locked).delete()

    prior_claims = list(
        ProgressClaim.objects.select_for_update()
        .filter(
            organization=organization,
            contract=locked.contract,
            status="approved",
        )
        .exclude(claim_number=locked.claim_number)
        .order_by("claim_number", "revision_number")
    )
    prior_claim_ids = [item.pk for item in prior_claims]
    prior_gross = sum((item.gross_amount for item in prior_claims), Decimal(0))
    prior_net = sum((item.net_amount for item in prior_claims), Decimal(0))
    remaining_ceiling = locked.baseline.effective_ceiling - prior_gross
    if remaining_ceiling < 0:
        raise ValidationError("سوابق تأییدشده از سقف مؤثر مبنای فعلی بیشتر است.")
    prior_by_line = {
        row["baseline_item__line_key"]: {
            "quantity": row["quantity"] or Decimal(0),
            "amount": row["amount"] or Decimal(0),
        }
        for row in ProgressClaimItem.objects.filter(claim_id__in=prior_claim_ids)
        .values("baseline_item__line_key")
        .annotate(quantity=Sum("current_quantity"), amount=Sum("current_amount"))
    }

    if locked.correction_kind == ProgressClaimCorrectionKind.CANCELLATION:
        cancellation_snapshot = {
            "calculation_order": ["linked_cancellation", "zero_final_amount"],
            "correction_kind": locked.correction_kind,
            "corrects_claim_id": str(locked.corrects_id),
            "currency": locked.currency_code,
            "currency_decimal_places": places,
            "prior_active_approved_claim_ids": [str(item.pk) for item in prior_claims],
            "prior_approved_gross": str(prior_gross),
            "prior_approved_net": str(prior_net),
            "gross_final": "0",
            "adjustment_final": "0",
            "net_final": "0",
        }
        locked.gross_amount = Decimal(0)
        locked.adjustment_amount = Decimal(0)
        locked.net_amount = Decimal(0)
        locked.calculation_snapshot = cancellation_snapshot
        locked.updated_by = actor
        locked.save(
            update_fields=[
                "gross_amount",
                "adjustment_amount",
                "net_amount",
                "calculation_snapshot",
                "updated_by",
                "updated_at",
            ]
        )
        return locked

    records = (
        ProgressRecord.objects.select_related("baseline", "baseline_item")
        .filter(
            organization=organization,
            baseline__contract=locked.contract,
            baseline__effective_date__lte=locked.measurement_cutoff,
            status=ProgressRecordStatus.VERIFIED,
            measured_on__lte=locked.measurement_cutoff,
        )
        .order_by("baseline_item__line_key", "measured_on", "verified_at", "created_at")
    )
    latest: dict[str, ProgressRecord] = {}
    for record in records:
        latest[record.baseline_item.line_key] = record
    gross_intermediate = Decimal(0)
    line_calculations: list[dict[str, str]] = []
    for baseline_item in locked.baseline.items.order_by("sort_order", "created_at"):
        record = latest.get(baseline_item.line_key)
        if record is None:
            continue
        previous = prior_by_line.get(baseline_item.line_key, {}).get(
            "quantity", Decimal(0)
        )
        if record.cumulative_quantity < previous:
            raise ValidationError(
                "مقدار تجمعی منبع از مقدار تجمعی قبلاً تأییدشده کمتر است."
            )
        if record.cumulative_quantity > baseline_item.planned_quantity:
            raise ValidationError("مقدار تجمعی از مقدار مبنای فعلی بیشتر است.")
        current = record.cumulative_quantity - previous
        if current == 0:
            continue
        amount = (current * baseline_item.unit_rate).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        item = ProgressClaimItem.objects.create(
            claim=locked,
            baseline_item=baseline_item,
            previous_cumulative_quantity=previous,
            current_quantity=current,
            new_cumulative_quantity=record.cumulative_quantity,
            unit_rate_snapshot=baseline_item.unit_rate,
            current_amount=amount,
        )
        ProgressClaimSource.objects.create(claim_item=item, progress_record=record)
        gross_intermediate += amount
        line_calculations.append(
            {
                "line_key": baseline_item.line_key,
                "baseline_item_id": str(baseline_item.pk),
                "progress_record_id": str(record.pk),
                "previous_certified_quantity": str(previous),
                "current_quantity": str(current),
                "new_cumulative_quantity": str(record.cumulative_quantity),
                "unit_rate": str(baseline_item.unit_rate),
                "current_amount": str(amount),
                "prior_certified_amount": str(
                    prior_by_line.get(baseline_item.line_key, {}).get(
                        "amount", Decimal(0)
                    )
                ),
            }
        )

    def remaining_cap(adjustment_type: str, cap: Decimal) -> Decimal:
        consumed = ClaimAdjustment.objects.filter(
            claim__organization=organization,
            claim__contract=locked.contract,
            claim__status="approved",
            adjustment_type=adjustment_type,
        ).exclude(claim__claim_number=locked.claim_number).aggregate(
            total=Sum("amount")
        )["total"] or Decimal(0)
        return max(cap - abs(consumed), Decimal(0))

    adjustments: list[ClaimAdjustment] = []

    def add_adjustment(
        *,
        adjustment_type: str,
        description: str,
        rate: Decimal,
        base: Decimal,
        sign: int,
        cap: Decimal | None = None,
    ) -> None:
        amount = base * rate / Decimal(100)
        if cap is not None:
            amount = min(amount, remaining_cap(adjustment_type, cap))
        amount = amount.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        if amount:
            adjustments.append(
                ClaimAdjustment(
                    claim=locked,
                    adjustment_type=adjustment_type,
                    description=description,
                    sequence=len(adjustments) + 1,
                    rate_snapshot=rate,
                    base_amount_snapshot=base.quantize(
                        Decimal("0.0001"), rounding=ROUND_HALF_UP
                    ),
                    amount=amount * sign,
                )
            )

    add_adjustment(
        adjustment_type=ClaimAdjustmentType.RETENTION,
        description="contract_term.retention",
        rate=term.retention_rate,
        base=gross_intermediate,
        sign=-1,
        cap=term.retention_cap,
    )
    add_adjustment(
        adjustment_type=ClaimAdjustmentType.ADVANCE_RECOVERY,
        description="contract_term.advance_recovery",
        rate=term.advance_recovery_rate,
        base=gross_intermediate,
        sign=-1,
        cap=term.advance_recovery_cap,
    )
    add_adjustment(
        adjustment_type=ClaimAdjustmentType.CONTRACTUAL_INSURANCE,
        description="contract_term.insurance",
        rate=term.contractual_insurance_rate,
        base=gross_intermediate,
        sign=-1,
        cap=term.contractual_insurance_cap,
    )
    contractual_total = sum((item.amount for item in adjustments), Decimal(0))
    after_contractual = gross_intermediate + contractual_total
    tax_base = (
        gross_intermediate
        if regulatory_parameters["tax_basis"] == "gross"
        else after_contractual
    )
    insurance_base = (
        gross_intermediate
        if regulatory_parameters["insurance_basis"] == "gross"
        else after_contractual
    )
    add_adjustment(
        adjustment_type=ClaimAdjustmentType.TAX,
        description="regulatory.tax",
        rate=Decimal(regulatory_parameters["tax_rate"]),
        base=tax_base,
        sign=1,
    )
    add_adjustment(
        adjustment_type=ClaimAdjustmentType.STATUTORY_INSURANCE,
        description="regulatory.insurance",
        rate=Decimal(regulatory_parameters["insurance_rate"]),
        base=insurance_base,
        sign=-1,
    )
    ClaimAdjustment.objects.bulk_create(adjustments)
    total_adjustments_intermediate = sum(
        (item.amount for item in adjustments), Decimal(0)
    )
    net_intermediate = gross_intermediate + total_adjustments_intermediate
    if net_intermediate < 0:
        raise ValidationError("صورت‌وضعیت عادی با مبلغ خالص منفی مجاز نیست.")
    if gross_intermediate > remaining_ceiling:
        raise ValidationError("جمع تجمعی تأییدشده از سقف مؤثر قرارداد بیشتر است.")
    gross = _money(gross_intermediate, places)
    net = _money(net_intermediate, places)
    total_adjustments = net - gross
    calculation_snapshot = {
        "calculation_order": [
            "gross",
            "contractual_deductions",
            "statutory_adjustments",
            "final_monetary_rounding",
        ],
        "currency": locked.currency_code,
        "currency_decimal_places": places,
        "correction_kind": locked.correction_kind,
        "corrects_claim_id": str(locked.corrects_id) if locked.corrects_id else None,
        "baseline_id": str(locked.baseline_id),
        "baseline_version": locked.baseline.version,
        "contract_value_snapshot": str(locked.baseline.contract_value_snapshot),
        "approved_amendments_snapshot": str(
            locked.baseline.approved_amendments_snapshot
        ),
        "effective_ceiling": str(locked.baseline.effective_ceiling),
        "prior_active_approved_claim_ids": [str(item.pk) for item in prior_claims],
        "prior_approved_gross": str(prior_gross),
        "prior_approved_net": str(prior_net),
        "remaining_ceiling_before_claim": str(remaining_ceiling),
        "contract_term_version_id": str(term.pk),
        "contract_term_version": term.version,
        "payment_due_days": term.payment_due_days,
        "regulatory_rule_version_id": str(regulatory.pk),
        "regulatory_rule_version": regulatory.version,
        "gross_intermediate": str(gross_intermediate),
        "contractual_adjustments_intermediate": str(contractual_total),
        "statutory_adjustments_intermediate": str(
            total_adjustments_intermediate - contractual_total
        ),
        "net_intermediate": str(net_intermediate),
        "gross_final": str(gross),
        "adjustment_final": str(total_adjustments),
        "net_final": str(net),
        "line_calculations": line_calculations,
    }
    (
        locked.gross_amount,
        locked.adjustment_amount,
        locked.net_amount,
        locked.calculation_snapshot,
        locked.updated_by,
    ) = gross, total_adjustments, net, calculation_snapshot, actor
    locked.save(
        update_fields=[
            "gross_amount",
            "adjustment_amount",
            "net_amount",
            "calculation_snapshot",
            "updated_by",
            "updated_at",
        ]
    )
    return locked


def _assert_claim_correction_downstream_clear(
    *, organization: Organization, claim: ProgressClaim
) -> None:
    if (
        claim_settlements_queryset(organization=organization, claim=claim)
        .filter(reversal__isnull=True)
        .exists()
    ):
        raise ValidationError("صورت‌وضعیت دارای تسویه فعال ابتدا باید تسویه معکوس شود.")

    from apps.billing.handoffs import PROGRESS_CLAIM_SOURCE_KIND
    from apps.subledgers.models import Obligation

    if Obligation.objects.filter(
        organization=organization,
        source_kind=PROGRESS_CLAIM_SOURCE_KIND,
        source_uuid=claim.pk,
        source_version=claim.revision_number,
    ).exists():
        raise ValidationError(
            "تعهد AR شناسایی‌شده باید پیش از اصلاح از مسیر کنترل‌شده تعیین تکلیف شود."
        )


@transaction.atomic
def create_progress_claim_correction(
    *,
    organization: Organization,
    actor: User,
    claim: ProgressClaim,
    correction_kind: str,
    reason: str,
) -> ProgressClaim:
    """Create a linked full replacement or zero-value cancellation draft."""

    _require_progress_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.CLAIMS_REVISE,
    )
    if correction_kind not in {
        ProgressClaimCorrectionKind.REPLACEMENT,
        ProgressClaimCorrectionKind.CANCELLATION,
    }:
        raise ValidationError("نوع اصلاح صورت‌وضعیت معتبر نیست.")
    if not reason.strip():
        raise ValidationError("دلیل اصلاح یا ابطال الزامی است.")
    try:
        original = (
            ProgressClaim.objects.select_for_update()
            .select_related("contract", "baseline", "contract_term_version")
            .get(pk=claim.pk, organization=organization)
        )
    except ProgressClaim.DoesNotExist as exc:
        raise PermissionDenied("صورت‌وضعیت متعلق به این سازمان نیست.") from exc
    if original.status != "approved":
        raise ValidationError("فقط صورت‌وضعیت تأییدشده فعال قابل اصلاح یا ابطال است.")
    if original.correction_kind == ProgressClaimCorrectionKind.CANCELLATION:
        raise ValidationError("سند ابطال تأییدشده از این مسیر قابل بازگردانی نیست.")
    if ProgressClaim.objects.filter(corrects=original).exists():
        raise ValidationError("برای این صورت‌وضعیت قبلاً سند اصلاحی ایجاد شده است.")
    _assert_claim_correction_downstream_clear(organization=organization, claim=original)
    revision = (
        ProgressClaim.objects.filter(
            organization=organization,
            contract=original.contract,
            claim_number=original.claim_number,
        ).aggregate(value=Max("revision_number"))["value"]
        or 0
    ) + 1
    correction = ProgressClaim.objects.create(
        organization=organization,
        project=original.project,
        contract=original.contract,
        baseline=original.baseline,
        claim_number=original.claim_number,
        revision_number=revision,
        correction_kind=correction_kind,
        corrects=original,
        correction_reason=reason.strip(),
        period_start=original.period_start,
        period_end=original.period_end,
        measurement_cutoff=original.measurement_cutoff,
        billing_configuration_snapshot=original.billing_configuration_snapshot,
        contract_term_version=original.contract_term_version,
        regulatory_rule_version=original.regulatory_rule_version,
        party_identity_snapshot=original.party_identity_snapshot,
        currency_code=original.currency_code,
        created_by=actor,
        updated_by=actor,
    )
    correction = recalculate_progress_claim(
        organization=organization, actor=actor, claim=correction
    )
    record_audit_event(
        action=AuditAction.PROGRESS_CLAIM_CORRECTION_CREATED,
        entity_type="billing.ProgressClaim",
        entity_id=str(correction.pk),
        organization=organization,
        actor=actor,
        metadata={
            "corrects_id": str(original.pk),
            "correction_kind": correction_kind,
            "reason": correction.correction_reason,
        },
    )
    return correction


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
    if original.status not in {"draft", "returned"}:
        raise ValidationError(
            "سند ارسال‌شده یا تأییدشده فقط از مسیر بازگشت یا اصلاح پیوندخورده تغییر می‌کند."
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
        correction_kind=original.correction_kind,
        corrects=original.corrects,
        correction_reason=original.correction_reason,
        period_start=original.period_start,
        period_end=original.period_end,
        measurement_cutoff=original.measurement_cutoff,
        billing_configuration_snapshot=original.billing_configuration_snapshot,
        calculation_snapshot=original.calculation_snapshot,
        contract_term_version=original.contract_term_version,
        regulatory_rule_version=original.regulatory_rule_version,
        party_identity_snapshot=original.party_identity_snapshot,
        currency_code=original.currency_code,
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
            .select_related("contract", "baseline", "contract_term_version")
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
    permitted_baseline_statuses = {ProjectBaselineStatus.APPROVED}
    if locked.corrects_id:
        permitted_baseline_statuses.add(ProjectBaselineStatus.SUPERSEDED)
    if baseline.status not in permitted_baseline_statuses:
        raise ValidationError("مبنای صورت‌وضعیت در زمان تأیید باید تأییدشده باشد.")
    corrected_claim: ProgressClaim | None = None
    if locked.corrects_id:
        corrected_claim = ProgressClaim.objects.select_for_update().get(
            pk=locked.corrects_id,
            organization=organization,
            contract=locked.contract,
        )
        if corrected_claim.status != "approved":
            raise ValidationError("فقط صورت‌وضعیت تأییدشده فعال قابل جایگزینی است.")
        if locked.correction_kind not in {
            ProgressClaimCorrectionKind.REPLACEMENT,
            ProgressClaimCorrectionKind.CANCELLATION,
        }:
            raise ValidationError("نوع سند اصلاحی معتبر نیست.")
        _assert_claim_correction_downstream_clear(
            organization=organization, claim=corrected_claim
        )
    elif locked.correction_kind != ProgressClaimCorrectionKind.ORDINARY:
        raise ValidationError("سند اصلاحی باید به صورت‌وضعیت پیشین متصل باشد.")
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
        .exclude(pk__in=[locked.pk, locked.corrects_id])
        .exists()
    ):
        raise ValidationError(
            "برای این شماره صورت‌وضعیت یک revision تأییدشده وجود دارد."
        )
    if corrected_claim is not None:
        disposition = (
            "cancelled"
            if locked.correction_kind == ProgressClaimCorrectionKind.CANCELLATION
            else "superseded"
        )
        ProgressClaim.objects.filter(pk=corrected_claim.pk, status="approved").update(
            status=disposition, updated_by=actor, updated_at=timezone.now()
        )
    locked.status = "approved"
    locked.approved_by = actor
    locked.approved_at = timezone.now()
    locked.due_date = timezone.localdate(locked.approved_at) + timedelta(
        days=locked.contract_term_version.payment_due_days
    )
    locked.approval_reason = reason.strip()
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "due_date",
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
    if corrected_claim is not None:
        record_audit_event(
            action=(
                AuditAction.PROGRESS_CLAIM_CANCELLED
                if locked.correction_kind == ProgressClaimCorrectionKind.CANCELLATION
                else AuditAction.PROGRESS_CLAIM_SUPERSEDED
            ),
            entity_type="billing.ProgressClaim",
            entity_id=str(corrected_claim.pk),
            organization=organization,
            actor=actor,
            metadata={
                "successor_id": str(locked.pk),
                "correction_kind": locked.correction_kind,
                "reason": locked.correction_reason,
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
        correction_kind=original.correction_kind,
        corrects=original.corrects,
        correction_reason=original.correction_reason,
        period_start=original.period_start,
        period_end=original.period_end,
        measurement_cutoff=original.measurement_cutoff,
        billing_configuration_snapshot=original.billing_configuration_snapshot,
        calculation_snapshot=original.calculation_snapshot,
        contract_term_version=original.contract_term_version,
        regulatory_rule_version=original.regulatory_rule_version,
        party_identity_snapshot=original.party_identity_snapshot,
        currency_code=original.currency_code,
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


def claim_settlements_queryset(*, organization: Organization, claim: ProgressClaim):
    """Project only exact AR source/version allocations; never read Legacy Payment."""
    from .handoffs import PROGRESS_CLAIM_SOURCE_KIND

    return SettlementAllocation.objects.filter(
        organization=organization,
        obligation__organization=organization,
        obligation__source_kind=PROGRESS_CLAIM_SOURCE_KIND,
        obligation__source_uuid=claim.pk,
        obligation__source_version=claim.revision_number,
        obligation__direction=ObligationDirection.RECEIVABLE,
        obligation__project_id=claim.project_id,
        obligation__contract_id=claim.contract_id,
    )


def _active_settlement_total(*, claim: ProgressClaim) -> Decimal:
    return claim_settlements_queryset(
        organization=claim.organization, claim=claim
    ).filter(reversal__isnull=True).aggregate(total=Sum("amount"))["total"] or Decimal(
        "0.00"
    )


@transaction.atomic
def allocate_progress_claim_settlement(
    *,
    organization: Organization,
    actor: User,
    claim: ProgressClaim,
    movement: TreasuryMovement,
    amount: Decimal | int | str,
    effective_date: date,
    reason: str,
    idempotency_key: str,
) -> SettlementAllocation:
    """Use an explicitly recognized AR obligation and the existing settlement owner."""
    from .handoffs import PROGRESS_CLAIM_SOURCE_KIND

    Organization.objects.select_for_update().get(pk=organization.pk)
    locked_claim = _locked_settlement_claim(organization=organization, claim=claim)
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.CLAIM_SETTLEMENTS_ALLOCATE,
        message="مجوز تخصیص تسویه صورت‌وضعیت را ندارید.",
        project=locked_claim.project,
    )
    if locked_claim.status != "approved":
        raise ValidationError("فقط صورت‌وضعیت تأییدشده قابل تسویه است.")
    try:
        obligation = Obligation.objects.get(
            organization=organization,
            source_kind=PROGRESS_CLAIM_SOURCE_KIND,
            source_uuid=locked_claim.pk,
            source_version=locked_claim.revision_number,
            direction=ObligationDirection.RECEIVABLE,
            source_line_key="",
            project_id=locked_claim.project_id,
            contract_id=locked_claim.contract_id,
        )
    except Obligation.DoesNotExist as exc:
        raise ValidationError(
            "ابتدا تعهد دریافتنی صورت‌وضعیت را از خدمت مجاز AR شناسایی کنید."
        ) from exc
    return allocate_settlement(
        organization=organization,
        actor=actor,
        obligation=obligation,
        movement=movement,
        amount=_decimal_with_scale(
            amount, quantum=MONEY_QUANTUM, label="مبلغ تسویه", positive=True
        ),
        effective_date=effective_date,
        reason=reason,
        idempotency_key=idempotency_key,
    )


@transaction.atomic
def reverse_progress_claim_settlement(
    *,
    organization: Organization,
    actor: User,
    settlement: SettlementAllocation,
    effective_date: date,
    reason: str,
    idempotency_key: str,
):
    """Reverse through Subledger authority, retaining its append-only lineage."""
    from .handoffs import PROGRESS_CLAIM_SOURCE_KIND

    Organization.objects.select_for_update().get(pk=organization.pk)
    try:
        allocation = SettlementAllocation.objects.select_related(
            "obligation__project"
        ).get(
            pk=settlement.pk,
            organization=organization,
            obligation__source_kind=PROGRESS_CLAIM_SOURCE_KIND,
        )
    except SettlementAllocation.DoesNotExist as exc:
        raise PermissionDenied("تخصیص صورت‌وضعیت متعلق به این سازمان نیست.") from exc
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.CLAIM_SETTLEMENTS_REVERSE,
        message="مجوز برگشت تسویه صورت‌وضعیت را ندارید.",
        project=allocation.obligation.project,
    )
    return reverse_settlement(
        organization=organization,
        actor=actor,
        allocation=allocation,
        effective_date=effective_date,
        reason=reason,
        idempotency_key=idempotency_key,
    )


def get_progress_claim_settlement_summary(
    *, organization: Organization, actor: User, claim: ProgressClaim
) -> ProgressClaimSettlementSummary:
    scoped_claim = _locked_free_scoped_claim(organization=organization, claim=claim)
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.CLAIM_SETTLEMENTS_VIEW,
        message="مجوز مشاهده تسویه صورت‌وضعیت را ندارید.",
        project=scoped_claim.project,
    )
    settled = _active_settlement_total(claim=scoped_claim)
    return ProgressClaimSettlementSummary(
        claim_id=scoped_claim.pk,
        approved_net_amount=scoped_claim.net_amount,
        settled_amount=settled,
        outstanding_amount=scoped_claim.net_amount - settled,
    )


def _locked_free_scoped_claim(*, organization: Organization, claim: ProgressClaim):
    try:
        return ProgressClaim.objects.select_related("project").get(
            pk=claim.pk, organization=organization
        )
    except ProgressClaim.DoesNotExist as exc:
        raise PermissionDenied("صورت‌وضعیت متعلق به این سازمان نیست.") from exc
