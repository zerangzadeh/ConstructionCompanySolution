from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.contracts.models import Contract
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationStatus,
)
from apps.parties.models import BusinessParty
from apps.payments.models import (
    Payment,
    PaymentAllocation,
    PaymentAllocationStatus,
    PaymentDirection,
    PaymentMethod,
    PaymentStatus,
)
from apps.projects.models import Project, ProjectPhase
from core.identifiers import canonicalize_upper_identifier


def _can_manage_payments(user: User, organization: Organization) -> bool:
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
    if not _can_manage_payments(actor, organization):
        raise PermissionDenied("اجازه مدیریت پرداخت‌های این سازمان را ندارید.")
    if project.organization_id != organization.pk or project.deleted_at is not None:
        raise PermissionDenied("پروژه متعلق به این سازمان نیست.")


def _validate_contract(
    *,
    organization: Organization,
    project: Project,
    contract: Contract,
) -> None:
    if (
        contract.organization_id != organization.pk
        or contract.project_id != project.pk
        or contract.deleted_at is not None
    ):
        raise PermissionDenied("قرارداد متعلق به این پروژه نیست.")


def _validate_phase(
    *,
    organization: Organization,
    project: Project,
    phase: ProjectPhase,
) -> None:
    if phase.organization_id != organization.pk or phase.site.project_id != project.pk:
        raise PermissionDenied("فاز پروژه متعلق به این پروژه نیست.")


@transaction.atomic
def create_payment(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    payment_number: str,
    direction: str,
    amount: Decimal,
    paid_on: date,
    counterparty_name: str,
    party: BusinessParty | None = None,
    contract: Contract | None = None,
    phase: ProjectPhase | None = None,
    method: str = PaymentMethod.BANK_TRANSFER,
    reference: str = "",
    notes: str = "",
) -> Payment:
    """Post an immutable cash transaction scoped to one tenant and project."""

    _validate_context(actor=actor, organization=organization, project=project)
    if contract is not None:
        _validate_contract(
            organization=organization,
            project=project,
            contract=contract,
        )
    if phase is not None:
        _validate_phase(organization=organization, project=project, phase=phase)
    if not payment_number.strip() or (not counterparty_name.strip() and party is None):
        raise ValueError("وارد کردن شماره پرداخت و طرف حساب الزامی است.")
    if amount <= Decimal("0.00"):
        raise ValueError("مبلغ پرداخت باید مثبت باشد.")
    if direction not in PaymentDirection.values:
        raise ValueError("جهت پرداخت معتبر نیست.")
    if method not in PaymentMethod.values:
        raise ValueError("روش پرداخت معتبر نیست.")
    if party and (party.organization_id != organization.pk or party.archived_at):
        raise PermissionDenied("طرف تجاری متعلق به این سازمان نیست.")

    normalized_number = canonicalize_upper_identifier(payment_number)
    if Payment.objects.filter(
        organization=organization,
        payment_number=normalized_number,
    ).exists():
        raise ValueError("پرداختی با این شماره از قبل وجود دارد.")

    payment = Payment.objects.create(
        organization=organization,
        project=project,
        contract=contract,
        phase=phase,
        payment_number=normalized_number,
        direction=direction,
        amount=amount,
        paid_on=paid_on,
        method=method,
        counterparty_name=counterparty_name.strip() or party.display_name,
        party=party,
        reference=reference.strip(),
        notes=notes.strip(),
        created_by=actor,
        updated_by=actor,
    )
    record_audit_event(
        action=AuditAction.PAYMENT_RECORDED,
        entity_type="payment",
        entity_id=payment.pk,
        organization=organization,
        actor=actor,
        metadata={
            "payment_number": payment.payment_number,
            "project_id": str(project.pk),
            "contract_id": str(contract.pk) if contract else None,
            "phase_id": str(phase.pk) if phase else None,
            "direction": payment.direction,
            "amount": str(payment.amount),
            "party_id": str(party.pk) if party else None,
        },
    )
    return payment


@transaction.atomic
def void_payment(*, payment: Payment, actor: User, reason: str) -> Payment:
    """Void a posted payment without deleting or changing the original amount."""

    locked_payment = Payment.objects.select_for_update().get(pk=payment.pk)
    _validate_context(
        actor=actor,
        organization=locked_payment.organization,
        project=locked_payment.project,
    )
    if locked_payment.status != PaymentStatus.POSTED:
        raise ValueError("فقط پرداخت ثبت‌شده قابل ابطال است.")
    if not reason.strip():
        raise ValueError("وارد کردن دلیل ابطال الزامی است.")

    locked_payment.status = PaymentStatus.VOID
    locked_payment.void_reason = reason.strip()
    locked_payment.voided_at = timezone.now()
    locked_payment.voided_by = actor
    locked_payment.updated_by = actor
    locked_payment.save(
        update_fields=[
            "status",
            "void_reason",
            "voided_at",
            "voided_by",
            "updated_by",
            "updated_at",
        ]
    )
    _reverse_active_allocations(payment=locked_payment, actor=actor)
    record_audit_event(
        action=AuditAction.PAYMENT_VOIDED,
        entity_type="payment",
        entity_id=locked_payment.pk,
        organization=locked_payment.organization,
        actor=actor,
        metadata={
            "payment_number": locked_payment.payment_number,
            "reason": locked_payment.void_reason,
        },
    )
    return locked_payment


def _reverse_active_allocations(*, payment: Payment, actor: User) -> None:
    """Keep allocation history while excluding it when its payment is voided."""
    for allocation in PaymentAllocation.objects.filter(
        payment=payment, status=PaymentAllocationStatus.ACTIVE
    ):
        allocation.status = PaymentAllocationStatus.REVERSED
        allocation.reversed_at = timezone.now()
        allocation.reversed_by = actor
        allocation.save(
            update_fields=["status", "reversed_at", "reversed_by", "updated_at"]
        )
        record_audit_event(
            action=AuditAction.PAYMENT_ALLOCATION_REVERSED,
            entity_type="payment_allocation",
            entity_id=allocation.pk,
            organization=payment.organization,
            actor=actor,
            metadata={"payment_id": str(payment.pk), "amount": str(allocation.amount)},
        )


@transaction.atomic
def allocate_payment(
    *, payment: Payment, contract: Contract, actor: User, amount: Decimal
) -> PaymentAllocation:
    """Allocate part of a posted payment without exceeding its original amount."""
    locked_payment = Payment.objects.select_for_update().get(pk=payment.pk)
    _validate_context(
        actor=actor,
        organization=locked_payment.organization,
        project=locked_payment.project,
    )
    _validate_contract(
        organization=locked_payment.organization,
        project=locked_payment.project,
        contract=contract,
    )
    if locked_payment.status != PaymentStatus.POSTED:
        raise ValueError("فقط پرداخت ثبت‌شده قابل تخصیص است.")
    if amount <= Decimal("0.00"):
        raise ValueError("مبلغ تخصیص باید مثبت باشد.")
    allocated = sum(
        (
            allocation.amount
            for allocation in locked_payment.allocations.filter(
                status=PaymentAllocationStatus.ACTIVE
            )
        ),
        Decimal("0.00"),
    )
    if allocated + amount > locked_payment.amount:
        raise ValueError("مجموع تخصیص‌ها نمی‌تواند از مبلغ پرداخت بیشتر باشد.")
    allocation = PaymentAllocation.objects.create(
        organization=locked_payment.organization,
        payment=locked_payment,
        contract=contract,
        amount=amount,
        created_by=actor,
    )
    record_audit_event(
        action=AuditAction.PAYMENT_ALLOCATION_CREATED,
        entity_type="payment_allocation",
        entity_id=allocation.pk,
        organization=locked_payment.organization,
        actor=actor,
        metadata={
            "payment_id": str(locked_payment.pk),
            "contract_id": str(contract.pk),
            "amount": str(amount),
        },
    )
    return allocation


def get_organization_payments(
    *,
    user: User,
    organization: Organization,
) -> QuerySet[Payment]:
    """Return payments visible to an active member of the active organization."""

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
        Payment.objects.filter(
            organization=organization,
            project__deleted_at__isnull=True,
        )
        .select_related(
            "project", "contract", "phase", "party", "created_by", "voided_by"
        )
        .order_by("-paid_on", "-created_at")
    )
