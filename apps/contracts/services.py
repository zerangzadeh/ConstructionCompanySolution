from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import QuerySet

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.contracts.models import Contract, ContractStatus
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationStatus,
)
from apps.projects.models import Project


def _can_manage_contracts(user: User, organization: Organization) -> bool:
    return organization.memberships.filter(
        user=user,
        status=MembershipStatus.ACTIVE,
        role__in=[
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
            MembershipRole.MANAGER,
        ],
    ).exists()


@transaction.atomic
def create_contract(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    contract_number: str,
    title: str,
    counterparty_name: str,
    status: str = ContractStatus.DRAFT,
    contract_value: Decimal = Decimal("0.00"),
    signed_at: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    notes: str = "",
) -> Contract:
    """Create a contract with organization and project scope validation."""

    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied("Authentication is required.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("The organization is not active.")
    if not _can_manage_contracts(actor, organization):
        raise PermissionDenied("You cannot create contracts in this organization.")
    if project.organization_id != organization.pk or project.deleted_at is not None:
        raise PermissionDenied("The project does not belong to this organization.")
    if (
        not contract_number.strip()
        or not title.strip()
        or not counterparty_name.strip()
    ):
        raise ValueError("Contract number, title, and counterparty are required.")
    if status not in ContractStatus.values:
        raise ValueError("Invalid contract status.")
    if contract_value < Decimal("0.00"):
        raise ValueError("Contract value cannot be negative.")
    if start_date and end_date and end_date < start_date:
        raise ValueError("Contract end date cannot be before start date.")
    normalized_contract_number = contract_number.strip()
    if Contract.objects.filter(
        organization=organization,
        contract_number=normalized_contract_number,
    ).exists():
        raise ValueError("A contract with this contract number already exists.")

    contract = Contract.objects.create(
        organization=organization,
        project=project,
        contract_number=normalized_contract_number,
        title=title.strip(),
        counterparty_name=counterparty_name.strip(),
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
        Contract.objects.filter(
            organization=organization,
            deleted_at__isnull=True,
            project__deleted_at__isnull=True,
        )
        .select_related("project", "created_by", "updated_by")
        .order_by("-created_at")
    )
