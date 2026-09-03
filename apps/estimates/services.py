from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.contracts.models import Contract
from apps.estimates.models import Estimate, EstimateItem, EstimateStatus
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationStatus,
)
from apps.projects.models import Project, ProjectPhase


def _can_manage_estimates(user: User, organization: Organization) -> bool:
    return organization.memberships.filter(
        user=user,
        status=MembershipStatus.ACTIVE,
        role__in=[
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
            MembershipRole.MANAGER,
        ],
    ).exists()


def _can_approve_estimates(user: User, organization: Organization) -> bool:
    return organization.memberships.filter(
        user=user,
        status=MembershipStatus.ACTIVE,
        role__in=[MembershipRole.OWNER, MembershipRole.ADMIN],
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
    if not _can_manage_estimates(actor, organization):
        raise PermissionDenied("You cannot manage estimates in this organization.")
    if project.organization_id != organization.pk or project.deleted_at is not None:
        raise PermissionDenied("The project does not belong to this organization.")


def _validate_phase(
    *,
    organization: Organization,
    project: Project,
    phase: ProjectPhase,
) -> None:
    if phase.organization_id != organization.pk or phase.site.project_id != project.pk:
        raise PermissionDenied("The project phase does not belong to this project.")


@transaction.atomic
def create_estimate(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    estimate_number: str,
    title: str,
    contract: Contract | None = None,
    phase: ProjectPhase | None = None,
    status: str = EstimateStatus.DRAFT,
    notes: str = "",
) -> Estimate:
    """Create an estimate scoped to an active organization and project."""

    _validate_context(actor=actor, organization=organization, project=project)
    if contract and (
        contract.organization_id != organization.pk
        or contract.project_id != project.pk
        or contract.deleted_at is not None
    ):
        raise PermissionDenied("The contract does not belong to this project.")
    if phase is not None:
        _validate_phase(organization=organization, project=project, phase=phase)
    if not estimate_number.strip() or not title.strip():
        raise ValueError("Estimate number and title are required.")
    if status != EstimateStatus.DRAFT:
        raise ValueError("Estimates must be created as drafts.")
    normalized_number = estimate_number.strip()
    if Estimate.objects.filter(
        organization=organization,
        estimate_number=normalized_number,
    ).exists():
        raise ValueError("An estimate with this number already exists.")

    estimate = Estimate.objects.create(
        organization=organization,
        project=project,
        contract=contract,
        phase=phase,
        estimate_number=normalized_number,
        title=title.strip(),
        status=status,
        notes=notes.strip(),
        created_by=actor,
        updated_by=actor,
    )
    record_audit_event(
        action=AuditAction.ESTIMATE_CREATED,
        entity_type="estimate",
        entity_id=estimate.pk,
        organization=organization,
        actor=actor,
        metadata={
            "estimate_number": estimate.estimate_number,
            "project_id": str(project.pk),
            "phase_id": str(phase.pk) if phase else None,
        },
    )
    return estimate


@transaction.atomic
def add_estimate_item(
    *,
    estimate: Estimate,
    actor: User,
    description: str,
    quantity: Decimal,
    unit_price: Decimal,
    unit: str = "unit",
    sort_order: int = 0,
) -> EstimateItem:
    """Add a positive-quantity, non-negative-price item to an estimate."""

    locked_estimate = (
        Estimate.objects.select_for_update()
        .select_related("organization", "project")
        .get(pk=estimate.pk)
    )
    _validate_context(
        actor=actor,
        organization=locked_estimate.organization,
        project=locked_estimate.project,
    )
    if locked_estimate.deleted_at is not None:
        raise ValueError("Cannot add items to a deleted estimate.")
    if locked_estimate.status == EstimateStatus.APPROVED:
        raise ValueError("Cannot modify an approved estimate.")
    if not description.strip():
        raise ValueError("Item description is required.")
    if quantity <= Decimal("0.0000"):
        raise ValueError("Item quantity must be positive.")
    if unit_price < Decimal("0.00"):
        raise ValueError("Item unit price cannot be negative.")
    item = EstimateItem.objects.create(
        organization=locked_estimate.organization,
        estimate=locked_estimate,
        description=description.strip(),
        quantity=quantity,
        unit=unit.strip() or "unit",
        unit_price=unit_price,
        sort_order=sort_order,
    )
    record_audit_event(
        action=AuditAction.ESTIMATE_ITEM_ADDED,
        entity_type="estimate_item",
        entity_id=item.pk,
        organization=locked_estimate.organization,
        actor=actor,
        metadata={
            "estimate_id": str(locked_estimate.pk),
            "line_total": str(item.line_total),
        },
    )
    return item


@transaction.atomic
def approve_estimate(
    *,
    estimate: Estimate,
    actor: User,
) -> Estimate:
    """Approve a draft estimate and lock its line items."""

    locked_estimate = (
        Estimate.objects.select_for_update()
        .select_related("organization", "project")
        .get(pk=estimate.pk)
    )
    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied("Authentication is required.")
    if not _can_approve_estimates(actor, locked_estimate.organization):
        raise PermissionDenied("You cannot approve estimates in this organization.")
    if (
        locked_estimate.organization.status != OrganizationStatus.ACTIVE
        or locked_estimate.organization.deleted_at is not None
        or locked_estimate.project.organization_id != locked_estimate.organization_id
        or locked_estimate.project.deleted_at is not None
    ):
        raise PermissionDenied("The estimate context is not active.")
    if locked_estimate.deleted_at is not None:
        raise ValueError("Cannot approve a deleted estimate.")
    if locked_estimate.status != EstimateStatus.DRAFT:
        raise ValueError("Only draft estimates can be approved.")

    now = timezone.now()
    locked_estimate.status = EstimateStatus.APPROVED
    locked_estimate.approved_by = actor
    locked_estimate.approved_at = now
    locked_estimate.updated_by = actor
    locked_estimate.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.ESTIMATE_APPROVED,
        entity_type="estimate",
        entity_id=locked_estimate.pk,
        organization=locked_estimate.organization,
        actor=actor,
        metadata={"estimate_number": locked_estimate.estimate_number},
    )
    return locked_estimate


def get_organization_estimates(
    *,
    user: User,
    organization: Organization,
) -> QuerySet[Estimate]:
    """Return non-deleted estimates visible in the active organization."""

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
        Estimate.objects.filter(
            organization=organization,
            deleted_at__isnull=True,
            project__deleted_at__isnull=True,
        )
        .select_related(
            "project",
            "phase",
            "contract",
            "created_by",
            "updated_by",
        )
        .prefetch_related("items")
        .order_by("-created_at")
    )
