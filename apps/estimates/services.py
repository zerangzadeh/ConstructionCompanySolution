from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.contracts.models import Contract
from apps.estimates.models import (
    Estimate,
    EstimateItem,
    EstimateRevision,
    EstimateRevisionStatus,
    EstimateStatus,
)
from apps.materials.models import UnitOfMeasure
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationStatus,
)
from apps.projects.models import Project, ProjectPhase
from core.identifiers import canonicalize_upper_identifier


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
    normalized_number = canonicalize_upper_identifier(estimate_number)
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
    revision = EstimateRevision.objects.create(
        organization=organization,
        estimate=estimate,
        revision_number=1,
        notes=estimate.notes,
        created_by=actor,
        updated_by=actor,
    )
    estimate.current_revision = revision
    estimate.save(update_fields=["current_revision", "updated_at"])
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
            "revision_number": revision.revision_number,
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
    unit_of_measure: UnitOfMeasure | None = None,
    sort_order: int = 0,
) -> EstimateItem:
    """Add a positive-quantity, non-negative-price item to an estimate."""

    locked_estimate = Estimate.objects.select_for_update().get(pk=estimate.pk)
    _validate_context(
        actor=actor,
        organization=locked_estimate.organization,
        project=locked_estimate.project,
    )
    if locked_estimate.deleted_at is not None:
        raise ValueError("Cannot add items to a deleted estimate.")
    if locked_estimate.status != EstimateStatus.DRAFT:
        raise ValueError("Cannot modify an approved estimate.")
    revision = locked_estimate.current_revision
    if revision is None or revision.status != EstimateRevisionStatus.DRAFT:
        raise ValueError("Cannot modify a finalized estimate revision.")
    if not description.strip():
        raise ValueError("Item description is required.")
    if quantity <= Decimal("0.0000"):
        raise ValueError("Item quantity must be positive.")
    if unit_price < Decimal("0.00"):
        raise ValueError("Item unit price cannot be negative.")
    item = EstimateItem.objects.create(
        organization=locked_estimate.organization,
        estimate=locked_estimate,
        revision=revision,
        description=description.strip(),
        quantity=quantity,
        unit=unit.strip() or "unit",
        unit_of_measure=unit_of_measure,
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

    locked_estimate = Estimate.objects.select_for_update().get(pk=estimate.pk)
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

    revision = locked_estimate.current_revision
    if revision is None:
        revision = EstimateRevision.objects.create(
            organization=locked_estimate.organization,
            estimate=locked_estimate,
            revision_number=1,
            notes=locked_estimate.notes,
            created_by=locked_estimate.created_by,
            updated_by=actor,
        )
        EstimateItem.objects.filter(
            estimate=locked_estimate,
            revision__isnull=True,
        ).update(revision=revision)
        locked_estimate.current_revision = revision
    if revision.status != EstimateRevisionStatus.DRAFT:
        raise ValueError("Only draft estimate revisions can be approved.")
    now = timezone.now()
    EstimateRevision.objects.filter(
        estimate=locked_estimate, status=EstimateRevisionStatus.APPROVED
    ).exclude(pk=revision.pk).update(status=EstimateRevisionStatus.SUPERSEDED)
    revision.status, revision.approved_by, revision.approved_at = (
        EstimateRevisionStatus.APPROVED,
        actor,
        now,
    )
    revision.updated_by = actor
    revision.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "updated_by",
            "updated_at",
        ]
    )
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
            "current_revision",
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
    record_audit_event(
        action=AuditAction.ESTIMATE_REVISION_APPROVED,
        entity_type="estimate_revision",
        entity_id=revision.pk,
        organization=locked_estimate.organization,
        actor=actor,
        metadata={
            "estimate_id": str(locked_estimate.pk),
            "revision_number": revision.revision_number,
        },
    )
    return locked_estimate


@transaction.atomic
def create_estimate_revision(
    *, estimate: Estimate, actor: User, notes: str = ""
) -> EstimateRevision:
    """Copy the current approved revision into the next editable draft revision."""
    locked_estimate = Estimate.objects.select_for_update().get(pk=estimate.pk)
    _validate_context(
        actor=actor,
        organization=locked_estimate.organization,
        project=locked_estimate.project,
    )
    source = locked_estimate.current_revision
    if source is None or source.status != EstimateRevisionStatus.APPROVED:
        raise ValueError("Only an approved current revision can be revised.")
    revision = EstimateRevision.objects.create(
        organization=locked_estimate.organization,
        estimate=locked_estimate,
        revision_number=source.revision_number + 1,
        notes=notes.strip() or source.notes,
        created_by=actor,
        updated_by=actor,
    )
    for item in source.items.all():
        EstimateItem.objects.create(
            organization=locked_estimate.organization,
            estimate=locked_estimate,
            revision=revision,
            description=item.description,
            quantity=item.quantity,
            unit=item.unit,
            unit_of_measure=item.unit_of_measure,
            unit_price=item.unit_price,
            sort_order=item.sort_order,
        )
    (
        locked_estimate.current_revision,
        locked_estimate.status,
        locked_estimate.updated_by,
    ) = revision, EstimateStatus.DRAFT, actor
    locked_estimate.save(
        update_fields=["current_revision", "status", "updated_by", "updated_at"]
    )
    record_audit_event(
        action=AuditAction.ESTIMATE_REVISION_CREATED,
        entity_type="estimate_revision",
        entity_id=revision.pk,
        organization=locked_estimate.organization,
        actor=actor,
        metadata={
            "estimate_id": str(locked_estimate.pk),
            "revision_number": revision.revision_number,
        },
    )
    return revision


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
            "current_revision",
            "created_by",
            "updated_by",
        )
        .prefetch_related("items", "current_revision__items")
        .order_by("-created_at")
    )
