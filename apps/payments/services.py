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
from apps.payments.models import Payment, PaymentDirection, PaymentMethod, PaymentStatus
from apps.projects.models import Project, ProjectPhase


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
        raise PermissionDenied("Authentication is required.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("The organization is not active.")
    if not _can_manage_payments(actor, organization):
        raise PermissionDenied("You cannot manage payments in this organization.")
    if project.organization_id != organization.pk or project.deleted_at is not None:
        raise PermissionDenied("The project does not belong to this organization.")


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
        raise PermissionDenied("The contract does not belong to this project.")


def _validate_phase(
    *,
    organization: Organization,
    project: Project,
    phase: ProjectPhase,
) -> None:
    if phase.organization_id != organization.pk or phase.site.project_id != project.pk:
        raise PermissionDenied("The project phase does not belong to this project.")


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
    if not payment_number.strip() or not counterparty_name.strip():
        raise ValueError("Payment number and counterparty are required.")
    if amount <= Decimal("0.00"):
        raise ValueError("Payment amount must be positive.")
    if direction not in PaymentDirection.values:
        raise ValueError("Invalid payment direction.")
    if method not in PaymentMethod.values:
        raise ValueError("Invalid payment method.")

    normalized_number = payment_number.strip()
    if Payment.objects.filter(
        organization=organization,
        payment_number=normalized_number,
    ).exists():
        raise ValueError("A payment with this number already exists.")

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
        counterparty_name=counterparty_name.strip(),
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
        },
    )
    return payment


@transaction.atomic
def void_payment(*, payment: Payment, actor: User, reason: str) -> Payment:
    """Void a posted payment without deleting or changing the original amount."""

    locked_payment = (
        Payment.objects.select_for_update()
        .select_related("organization", "project")
        .get(pk=payment.pk)
    )
    _validate_context(
        actor=actor,
        organization=locked_payment.organization,
        project=locked_payment.project,
    )
    if locked_payment.status != PaymentStatus.POSTED:
        raise ValueError("Only posted payments can be voided.")
    if not reason.strip():
        raise ValueError("A void reason is required.")

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


def get_organization_payments(
    *,
    user: User,
    organization: Organization,
) -> QuerySet[Payment]:
    """Return payments visible to an active member of the active organization."""

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
        Payment.objects.filter(
            organization=organization,
            project__deleted_at__isnull=True,
        )
        .select_related("project", "contract", "phase", "created_by", "voided_by")
        .order_by("-paid_on", "-created_at")
    )
