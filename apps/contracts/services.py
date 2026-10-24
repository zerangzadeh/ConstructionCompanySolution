from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, QuerySet

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.contracts.models import (
    Contract,
    ContractAmendment,
    ContractAmendmentStatus,
    ContractDirection,
    ContractItem,
    ContractStatus,
    ContractTermVersion,
    ContractTermVersionStatus,
    ContractType,
    RetentionReleaseRequirement,
)
from apps.materials.models import UnitOfMeasure
from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
    require_business_permission,
    scope_queryset,
)
from apps.organizations.models import (
    BusinessPermissionCode,
    InsuranceClassification,
    Organization,
    OrganizationStatus,
)
from apps.parties.models import BusinessParty
from apps.projects.models import Project, WBSNode
from core.identifiers import canonicalize_upper_identifier


def can_view_contracts(user: User, organization: Organization) -> bool:
    """Return whether the active tenant role can read contract data."""

    return has_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.CONTRACTS_VIEW,
        allow_any_scope=True,
    )


def can_manage_contracts(user: User, organization: Organization) -> bool:
    return has_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.CONTRACTS_CREATE,
        allow_any_scope=True,
    )


@transaction.atomic
def create_contract_term_version(
    *,
    organization: Organization,
    actor: User,
    contract: Contract,
    effective_from: date,
    reason: str,
    payment_due_days: int = 0,
    retention_rate: Decimal = Decimal(0),
    retention_cap: Decimal = Decimal(0),
    advance_recovery_rate: Decimal = Decimal(0),
    advance_recovery_cap: Decimal = Decimal(0),
    contractual_insurance_rate: Decimal = Decimal(0),
    contractual_insurance_cap: Decimal = Decimal(0),
    retention_release_requirement: str = RetentionReleaseRequirement.UNCONFIGURED,
    retention_release_cap: Decimal = Decimal(0),
    insurance_classification: InsuranceClassification | None = None,
) -> ContractTermVersion:
    try:
        locked_contract = (
            Contract.objects.select_for_update()
            .select_related("project")
            .get(pk=contract.pk, organization=organization)
        )
    except Contract.DoesNotExist as exc:
        raise PermissionDenied("قرارداد متعلق به این سازمان نیست.") from exc
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.CONTRACT_TERMS_MANAGE,
        project=locked_contract.project,
        message="اجازه تهیه نسخه شرایط این قرارداد را ندارید.",
    )
    if locked_contract.direction not in {
        ContractDirection.RECEIVABLE,
        ContractDirection.PAYABLE,
    }:
        raise ValidationError("جهت قرارداد برای شرایط تجاری باید مشخص باشد.")
    if (
        locked_contract.direction == ContractDirection.PAYABLE
        and locked_contract.contract_type != ContractType.SUBCONTRACT
    ):
        raise ValidationError("شرایط پرداختنی فقط برای پیمان جزء مجاز است.")
    version = (
        ContractTermVersion.objects.filter(contract=locked_contract).aggregate(
            value=Max("version")
        )["value"]
        or 0
    ) + 1
    term = ContractTermVersion(
        organization=organization,
        contract=locked_contract,
        version=version,
        effective_from=effective_from,
        payment_due_days=payment_due_days,
        insurance_classification=insurance_classification,
        insurance_classification_selected_by=actor
        if insurance_classification
        else None,
        retention_rate=retention_rate,
        retention_cap=retention_cap,
        advance_recovery_rate=advance_recovery_rate,
        advance_recovery_cap=advance_recovery_cap,
        contractual_insurance_rate=contractual_insurance_rate,
        contractual_insurance_cap=contractual_insurance_cap,
        retention_release_requirement=retention_release_requirement,
        retention_release_cap=retention_release_cap,
        reason=reason.strip(),
        created_by=actor,
    )
    if insurance_classification is not None:
        _validate_term_insurance_classification(term)
    term.save()
    record_audit_event(
        action=AuditAction.CONTRACT_TERM_VERSION_CREATED,
        entity_type="contracts.ContractTermVersion",
        entity_id=term.pk,
        organization=organization,
        actor=actor,
        metadata={
            "contract_id": str(locked_contract.pk),
            "version": version,
            "insurance_classification_id": str(term.insurance_classification_id)
            if term.insurance_classification_id
            else None,
        },
    )
    return term


@transaction.atomic
def approve_contract_term_version(
    *,
    organization: Organization,
    actor: User,
    term_version: ContractTermVersion,
    reason: str,
) -> ContractTermVersion:
    from django.utils import timezone

    from apps.organizations.authorization import require_business_permission

    try:
        locked = (
            ContractTermVersion.objects.select_for_update()
            .select_related("contract__project")
            .get(pk=term_version.pk, organization=organization)
        )
    except ContractTermVersion.DoesNotExist as exc:
        raise PermissionDenied("نسخه شرایط متعلق به این سازمان نیست.") from exc
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.CONTRACT_TERMS_APPROVE,
        project=locked.contract.project,
        message="اجازه تأیید نسخه شرایط این قرارداد را ندارید.",
    )
    if locked.status != ContractTermVersionStatus.DRAFT:
        raise ValidationError("فقط نسخه پیش‌نویس شرایط قابل تأیید است.")
    if actor.pk in {
        locked.created_by_id,
        locked.insurance_classification_selected_by_id,
    }:
        raise PermissionDenied("تهیه‌کننده نمی‌تواند همان نسخه شرایط را تأیید کند.")
    if not reason.strip():
        raise ValidationError("دلیل تأیید نسخه شرایط الزامی است.")
    if (
        ContractTermVersion.objects.filter(
            contract=locked.contract,
            effective_from=locked.effective_from,
            status__in=(
                ContractTermVersionStatus.APPROVED,
                ContractTermVersionStatus.SUPERSEDED,
            ),
        )
        .exclude(pk=locked.pk)
        .exists()
    ):
        raise ValidationError("برای این تاریخ اثر قبلاً نسخه شرایط تأیید شده است.")
    if locked.insurance_classification_id:
        _validate_term_insurance_classification(locked)
    previous = list(
        ContractTermVersion.objects.select_for_update().filter(
            contract=locked.contract,
            status=ContractTermVersionStatus.APPROVED,
            effective_from__lt=locked.effective_from,
        )
    )
    locked.status = ContractTermVersionStatus.APPROVED
    locked.approved_by = actor
    locked.approved_at = timezone.now()
    locked.approval_reason = reason.strip()
    locked.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "approval_reason",
            "updated_at",
        ]
    )
    for old in previous:
        old.status = ContractTermVersionStatus.SUPERSEDED
        old.superseded_by = locked
        old.save(update_fields=["status", "superseded_by", "updated_at"])
    record_audit_event(
        action=AuditAction.CONTRACT_TERM_VERSION_APPROVED,
        entity_type="contracts.ContractTermVersion",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={
            "contract_id": str(locked.contract_id),
            "version": locked.version,
            "reason": locked.approval_reason,
        },
    )
    return locked


def _has_contract_permission(
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


@transaction.atomic
def create_contract(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    contract_number: str,
    title: str,
    counterparty_name: str,
    party: BusinessParty | None = None,
    direction: str | None = None,
    contract_type: str | None = None,
    status: str = ContractStatus.DRAFT,
    contract_value: Decimal = Decimal("0.00"),
    signed_at: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    notes: str = "",
) -> Contract:
    """Create a contract with organization and project scope validation."""

    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied("ورود به حساب کاربری الزامی است.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("سازمان فعال نیست.")
    if not _has_contract_permission(
        actor,
        organization,
        BusinessPermissionCode.CONTRACTS_CREATE,
        project=project,
    ):
        raise PermissionDenied("اجازه ایجاد قرارداد در این سازمان را ندارید.")
    if project.organization_id != organization.pk or project.deleted_at is not None:
        raise PermissionDenied("پروژه متعلق به این سازمان نیست.")
    if (
        not contract_number.strip()
        or not title.strip()
        or not counterparty_name.strip()
    ):
        raise ValueError("وارد کردن شماره، عنوان و طرف قرارداد الزامی است.")
    if party and (party.organization_id != organization.pk or party.archived_at):
        raise PermissionDenied("طرف تجاری متعلق به این سازمان نیست.")
    if direction is not None and direction not in ContractDirection.values:
        raise ValueError("جهت قرارداد معتبر نیست.")
    if contract_type is not None and contract_type not in ContractType.values:
        raise ValueError("نوع قرارداد معتبر نیست.")
    if status not in ContractStatus.values:
        raise ValueError("وضعیت قرارداد معتبر نیست.")
    if contract_value < Decimal("0.00"):
        raise ValueError("مبلغ قرارداد نمی‌تواند منفی باشد.")
    if start_date and end_date and end_date < start_date:
        raise ValueError("تاریخ پایان قرارداد نمی‌تواند پیش از تاریخ شروع باشد.")
    normalized_contract_number = canonicalize_upper_identifier(contract_number)
    if Contract.objects.filter(
        organization=organization,
        contract_number=normalized_contract_number,
    ).exists():
        raise ValueError("قراردادی با این شماره از قبل وجود دارد.")

    contract = Contract.objects.create(
        organization=organization,
        project=project,
        contract_number=normalized_contract_number,
        title=title.strip(),
        counterparty_name=counterparty_name.strip(),
        party=party,
        direction=direction,
        contract_type=contract_type,
        status=status,
        contract_value=contract_value,
        signed_at=signed_at,
        start_date=start_date,
        end_date=end_date,
        notes=notes.strip(),
        created_by=actor,
        updated_by=actor,
    )
    record_audit_event(
        action=AuditAction.CONTRACT_CREATED,
        entity_type="contract",
        entity_id=contract.pk,
        organization=organization,
        actor=actor,
        metadata={
            "contract_number": contract.contract_number,
            "project_id": str(project.pk),
            "party_id": str(party.pk) if party else None,
            "direction": direction,
        },
    )
    return contract


def get_organization_contracts(
    *,
    user: User,
    organization: Organization,
) -> QuerySet[Contract]:
    """Return non-deleted contracts in the user's active organization."""

    if not user.is_authenticated:
        raise PermissionDenied("ورود به حساب کاربری الزامی است.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("سازمان فعال نیست.")
    if not can_view_contracts(user, organization):
        raise PermissionDenied("اجازه مشاهده قراردادهای این سازمان را ندارید.")
    membership = get_active_membership(user=user, organization=organization)
    return (
        scope_queryset(
            Contract.objects.filter(
                organization=organization,
                deleted_at__isnull=True,
                project__deleted_at__isnull=True,
            ),
            membership=membership,
            project_lookup="project_id",
        )
        .select_related("project", "party", "created_by", "updated_by")
        .order_by("-created_at")
    )


def _get_locked_contract(*, contract: Contract, organization: Organization) -> Contract:
    locked = (
        Contract.objects.select_for_update()
        .select_related("project")
        .get(pk=contract.pk)
    )
    if locked.organization_id != organization.pk:
        raise PermissionDenied("قرارداد متعلق به این سازمان نیست.")
    return locked


@transaction.atomic
def update_draft_contract(
    *,
    organization: Organization,
    actor: User,
    contract: Contract,
    title: str,
    counterparty_name: str,
    party: BusinessParty | None,
    direction: str | None,
    contract_type: str | None,
    contract_value: Decimal,
    notes: str = "",
) -> Contract:
    """Edit only a draft contract; finalized commercial terms use amendments."""
    locked = _get_locked_contract(contract=contract, organization=organization)
    if not _has_contract_permission(
        actor,
        organization,
        BusinessPermissionCode.CONTRACTS_CHANGE,
        project=locked.project,
    ):
        raise PermissionDenied("اجازه مدیریت قراردادهای این سازمان را ندارید.")
    if locked.status != ContractStatus.DRAFT:
        raise ValueError("فقط قراردادهای پیش‌نویس قابل ویرایش هستند.")
    if (
        not title.strip()
        or not counterparty_name.strip()
        or contract_value < Decimal("0.00")
    ):
        raise ValueError("اطلاعات قرارداد پیش‌نویس معتبر نیست.")
    if party and (party.organization_id != organization.pk or party.archived_at):
        raise PermissionDenied("طرف تجاری متعلق به این سازمان نیست.")
    if direction is not None and direction not in ContractDirection.values:
        raise ValueError("جهت قرارداد معتبر نیست.")
    if contract_type is not None and contract_type not in ContractType.values:
        raise ValueError("نوع قرارداد معتبر نیست.")
    locked.title, locked.counterparty_name, locked.party = (
        title.strip(),
        counterparty_name.strip(),
        party,
    )
    locked.direction, locked.contract_type, locked.contract_value = (
        direction,
        contract_type,
        contract_value,
    )
    locked.notes, locked.updated_by = notes.strip(), actor
    locked.save()
    record_audit_event(
        action=AuditAction.CONTRACT_UPDATED,
        entity_type="contract",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"contract_number": locked.contract_number},
    )
    return locked


@transaction.atomic
def transition_contract_status(
    *, organization: Organization, actor: User, contract: Contract, status: str
) -> Contract:
    """Apply the deliberately narrow contract lifecycle under a row lock."""
    locked = _get_locked_contract(contract=contract, organization=organization)
    if not _has_contract_permission(
        actor,
        organization,
        BusinessPermissionCode.CONTRACTS_TRANSITION,
        project=locked.project,
    ):
        raise PermissionDenied("اجازه مدیریت قراردادهای این سازمان را ندارید.")
    allowed = {
        ContractStatus.DRAFT: {ContractStatus.ACTIVE, ContractStatus.TERMINATED},
        ContractStatus.ACTIVE: {ContractStatus.COMPLETED, ContractStatus.TERMINATED},
    }
    if status not in allowed.get(locked.status, set()):
        raise ValueError("تغییر وضعیت قرارداد مجاز نیست.")
    previous_status = locked.status
    locked.status, locked.updated_by = status, actor
    locked.save(update_fields=["status", "updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.CONTRACT_STATUS_CHANGED,
        entity_type="contract",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"previous_status": previous_status, "status": status},
    )
    return locked


@transaction.atomic
def add_contract_item(
    *,
    organization: Organization,
    actor: User,
    contract: Contract,
    description: str,
    quantity: Decimal,
    unit_price: Decimal,
    unit: str = "unit",
    unit_of_measure: UnitOfMeasure | None = None,
    wbs_node: WBSNode | None = None,
    sort_order: int = 0,
) -> ContractItem:
    locked = _get_locked_contract(contract=contract, organization=organization)
    if not _has_contract_permission(
        actor,
        organization,
        BusinessPermissionCode.CONTRACT_ITEMS_ADD,
        project=locked.project,
    ):
        raise PermissionDenied("اجازه مدیریت قراردادهای این سازمان را ندارید.")
    if locked.status != ContractStatus.DRAFT:
        raise ValueError("فقط ردیف‌های قرارداد پیش‌نویس قابل تغییر هستند.")
    if not description.strip() or quantity <= Decimal(0) or unit_price < Decimal(0):
        raise ValueError("اطلاعات ردیف قرارداد معتبر نیست.")
    item = ContractItem.objects.create(
        organization=organization,
        contract=locked,
        description=description.strip(),
        quantity=quantity,
        unit=unit.strip() or "unit",
        unit_price=unit_price,
        unit_of_measure=unit_of_measure,
        wbs_node=wbs_node,
        sort_order=sort_order,
    )
    record_audit_event(
        action=AuditAction.CONTRACT_ITEM_ADDED,
        entity_type="contract_item",
        entity_id=item.pk,
        organization=organization,
        actor=actor,
        metadata={"contract_id": str(locked.pk), "line_total": str(item.line_total)},
    )
    return item


@transaction.atomic
def _approve_contract_amendment_domain(
    *, organization: Organization, actor: User, amendment: ContractAmendment
) -> ContractAmendment:
    """Approve a single immutable amendment without changing the legacy header value."""
    locked = (
        ContractAmendment.objects.select_for_update()
        .select_related("contract__project")
        .get(pk=amendment.pk)
    )
    if locked.organization_id != organization.pk:
        raise PermissionDenied("الحاقیه متعلق به این سازمان نیست.")
    if not _has_contract_permission(
        actor,
        organization,
        BusinessPermissionCode.CONTRACT_AMENDMENTS_APPROVE,
        project=locked.contract.project,
    ):
        raise PermissionDenied("اجازه مدیریت قراردادهای این سازمان را ندارید.")
    if locked.contract.status not in {ContractStatus.ACTIVE, ContractStatus.COMPLETED}:
        raise ValueError("فقط قراردادهای نهایی‌شده می‌توانند الحاقیه داشته باشند.")
    if locked.status != ContractAmendmentStatus.DRAFT:
        raise ValueError("فقط الحاقیه‌های پیش‌نویس قابل تأیید هستند.")
    from django.utils import timezone

    locked.status, locked.approved_by, locked.approved_at = (
        ContractAmendmentStatus.APPROVED,
        actor,
        timezone.now(),
    )
    locked.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    record_audit_event(
        action=AuditAction.CONTRACT_AMENDMENT_APPROVED,
        entity_type="contract_amendment",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={
            "contract_id": str(locked.contract_id),
            "value_change": str(locked.value_change),
        },
    )
    return locked


def approve_contract_amendment(
    *, organization: Organization, actor: User, amendment: ContractAmendment
) -> ContractAmendment:
    """Approve through W5.4 when the amendment has an active work item."""
    from .workflow import approve_contract_amendment_with_workflow

    return approve_contract_amendment_with_workflow(
        organization=organization, actor=actor, amendment=amendment
    )


def _validate_term_insurance_classification(term: ContractTermVersion) -> None:
    from apps.organizations.policy_services import (
        resolve_effective_platform_regulatory_policy,
    )
    from apps.organizations.policy_specs import RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE

    resolve_effective_platform_regulatory_policy(
        code=RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE,
        consumer="billing.progress_claim.calculate",
        on_date=term.effective_from,
        insurance_classification=term.insurance_classification,
    )


@transaction.atomic
def select_contract_insurance_classification(
    *,
    organization: Organization,
    actor: User,
    term_version: ContractTermVersion,
    insurance_classification: InsuranceClassification,
    reason: str,
) -> ContractTermVersion:
    try:
        locked = (
            ContractTermVersion.objects.select_for_update()
            .select_related("contract__project")
            .get(
                pk=term_version.pk,
                organization=organization,
                contract__organization=organization,
            )
        )
    except ContractTermVersion.DoesNotExist as exc:
        raise PermissionDenied("نسخه شرایط متعلق به این سازمان نیست.") from exc
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.CONTRACT_TERMS_MANAGE,
        project=locked.contract.project,
        message="اجازه انتخاب طبقه‌بندی بیمه را ندارید.",
    )
    if locked.status != ContractTermVersionStatus.DRAFT or not reason.strip():
        raise ValidationError(
            "انتخاب طبقه‌بندی فقط برای نسخه پیش‌نویس و با دلیل مجاز است."
        )
    before = locked.insurance_classification_id
    locked.insurance_classification = insurance_classification
    locked.insurance_classification_selected_by = actor
    _validate_term_insurance_classification(locked)
    locked.save(
        update_fields=[
            "insurance_classification",
            "insurance_classification_selected_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.CONTRACT_UPDATED,
        entity_type="contracts.ContractTermVersion",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={
            "before": {"insurance_classification_id": str(before) if before else None},
            "after": {
                "insurance_classification_id": str(locked.insurance_classification_id)
            },
            "reason": reason.strip(),
        },
    )
    return locked
