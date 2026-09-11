from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import QuerySet

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
    ContractType,
)
from apps.materials.models import UnitOfMeasure
from apps.organizations.authorization import has_business_permission
from apps.organizations.models import (
    BusinessPermissionCode,
    MembershipStatus,
    Organization,
    OrganizationStatus,
)
from apps.parties.models import BusinessParty
from apps.projects.models import Project, WBSNode
from core.identifiers import canonicalize_upper_identifier


def _can_manage_contracts(user: User, organization: Organization) -> bool:
    return has_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.CONTRACTS_MANAGE,
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
    if not _can_manage_contracts(actor, organization):
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
    if (
        not (user.is_superuser and user.is_active)
        and not organization.memberships.filter(
            user=user,
            status=MembershipStatus.ACTIVE,
            role_definition__is_active=True,
        ).exists()
    ):
        raise PermissionDenied("به این سازمان دسترسی ندارید.")
    return (
        Contract.objects.filter(
            organization=organization,
            deleted_at__isnull=True,
            project__deleted_at__isnull=True,
        )
        .select_related("project", "party", "created_by", "updated_by")
        .order_by("-created_at")
    )


def _get_locked_contract(*, contract: Contract, organization: Organization) -> Contract:
    locked = Contract.objects.select_for_update().get(pk=contract.pk)
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
    if not _can_manage_contracts(actor, organization):
        raise PermissionDenied("اجازه مدیریت قراردادهای این سازمان را ندارید.")
    locked = _get_locked_contract(contract=contract, organization=organization)
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
    if not _can_manage_contracts(actor, organization):
        raise PermissionDenied("اجازه مدیریت قراردادهای این سازمان را ندارید.")
    locked = _get_locked_contract(contract=contract, organization=organization)
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
    if not _can_manage_contracts(actor, organization):
        raise PermissionDenied("اجازه مدیریت قراردادهای این سازمان را ندارید.")
    locked = _get_locked_contract(contract=contract, organization=organization)
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
def approve_contract_amendment(
    *, organization: Organization, actor: User, amendment: ContractAmendment
) -> ContractAmendment:
    """Approve a single immutable amendment without changing the legacy header value."""
    if not _can_manage_contracts(actor, organization):
        raise PermissionDenied("اجازه مدیریت قراردادهای این سازمان را ندارید.")
    locked = ContractAmendment.objects.select_for_update().get(pk=amendment.pk)
    if locked.organization_id != organization.pk:
        raise PermissionDenied("الحاقیه متعلق به این سازمان نیست.")
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
