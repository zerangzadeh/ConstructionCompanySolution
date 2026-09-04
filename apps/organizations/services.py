import hashlib
import secrets
import uuid
from collections.abc import MutableMapping
from datetime import timedelta
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.models import (
    InvitationRole,
    InvitationStatus,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
    OrganizationSettings,
    OrganizationStatus,
)
from core.identifiers import canonicalize_lower_identifier

ACTIVE_ORGANIZATION_SESSION_KEY = "active_organization_id"
INVITATION_LIFETIME = timedelta(days=7)


def _hash_invitation_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _can_manage_memberships(user: User, organization: Organization) -> bool:
    return OrganizationMembership.objects.filter(
        user=user,
        organization=organization,
        status=MembershipStatus.ACTIVE,
        role__in=[MembershipRole.OWNER, MembershipRole.ADMIN],
    ).exists()


def get_organization_settings(*, organization: Organization) -> OrganizationSettings:
    """Return settings, safely restoring a missing compatibility row if needed."""

    settings_record, _ = OrganizationSettings.objects.get_or_create(
        organization=organization,
        defaults={
            "timezone": organization.timezone,
            "currency": organization.currency,
        },
    )
    return settings_record


@transaction.atomic
def update_organization_settings(
    *,
    organization: Organization,
    updated_by: User,
    timezone_name: str,
    currency: str,
    fiscal_year_start_month: int,
) -> OrganizationSettings:
    """Update tenant settings for an active owner or administrator only."""

    locked_organization = Organization.objects.select_for_update().get(
        pk=organization.pk
    )
    if (
        locked_organization.status != OrganizationStatus.ACTIVE
        or locked_organization.deleted_at is not None
    ):
        raise PermissionDenied("The organization is not active.")
    if not _can_manage_memberships(updated_by, locked_organization):
        raise PermissionDenied("You cannot update settings for this organization.")

    settings_record = get_organization_settings(organization=locked_organization)
    settings_record.timezone = timezone_name
    settings_record.currency = currency
    settings_record.fiscal_year_start_month = fiscal_year_start_month
    settings_record.full_clean()
    settings_record.save(
        update_fields=[
            "timezone",
            "currency",
            "fiscal_year_start_month",
            "updated_at",
        ]
    )
    locked_organization.timezone = settings_record.timezone
    locked_organization.currency = settings_record.currency
    locked_organization.updated_by = updated_by
    locked_organization.save(
        update_fields=["timezone", "currency", "updated_by", "updated_at"]
    )
    record_audit_event(
        action=AuditAction.ORGANIZATION_SETTINGS_UPDATED,
        entity_type="organization_settings",
        entity_id=settings_record.pk,
        organization=locked_organization,
        actor=updated_by,
        metadata={
            "timezone": settings_record.timezone,
            "currency": settings_record.currency,
            "fiscal_year_start_month": settings_record.fiscal_year_start_month,
        },
    )
    return settings_record


@transaction.atomic
def create_organization_invitation(
    *,
    organization: Organization,
    invited_by: User,
    invitee: User,
    role: str = InvitationRole.MEMBER,
    expires_in: timedelta = INVITATION_LIFETIME,
) -> tuple[OrganizationInvitation, str]:
    """Create a hashed-token invitation for an existing user."""

    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("The organization is not active.")
    if not _can_manage_memberships(invited_by, organization):
        raise PermissionDenied("You cannot invite members to this organization.")
    if invited_by == invitee:
        raise ValueError("You cannot invite yourself.")
    if role not in InvitationRole.values:
        raise ValueError("Invalid invitation role.")

    existing_membership = OrganizationMembership.objects.filter(
        organization=organization,
        user=invitee,
    ).first()
    if existing_membership and existing_membership.status == MembershipStatus.ACTIVE:
        raise ValueError("The user is already an active member.")

    now = timezone.now()
    OrganizationInvitation.objects.filter(
        organization=organization,
        invitee=invitee,
        status=InvitationStatus.PENDING,
        expires_at__lte=now,
    ).update(status=InvitationStatus.EXPIRED)

    if OrganizationInvitation.objects.filter(
        organization=organization,
        invitee=invitee,
        status=InvitationStatus.PENDING,
    ).exists():
        raise ValueError("A pending invitation already exists.")

    raw_token = secrets.token_urlsafe(32)
    invitation = OrganizationInvitation.objects.create(
        organization=organization,
        invitee=invitee,
        invited_by=invited_by,
        role=role,
        token_hash=_hash_invitation_token(raw_token),
        expires_at=now + expires_in,
    )
    record_audit_event(
        action=AuditAction.MEMBERSHIP_INVITED,
        entity_type="organization_invitation",
        entity_id=invitation.pk,
        organization=organization,
        actor=invited_by,
        metadata={"invitee_username": invitee.username, "role": role},
    )
    return invitation, raw_token


def accept_organization_invitation(
    *,
    token: str,
    user: User,
) -> OrganizationMembership:
    """Accept a valid invitation for its intended user."""

    if not user.is_authenticated:
        raise PermissionDenied("Authentication is required.")

    expired = False
    with transaction.atomic():
        invitation = (
            OrganizationInvitation.objects.select_for_update()
            .select_related("organization", "invitee")
            .filter(token_hash=_hash_invitation_token(token))
            .first()
        )
        if invitation is None:
            raise ValueError("Invitation is invalid.")
        if invitation.invitee_id != user.id:
            raise PermissionDenied("This invitation belongs to another user.")
        if invitation.status != InvitationStatus.PENDING:
            raise ValueError("Invitation is no longer pending.")

        now = timezone.now()
        if invitation.expires_at <= now:
            invitation.status = InvitationStatus.EXPIRED
            invitation.save(update_fields=["status", "updated_at"])
            expired = True
        else:
            if invitation.organization.status != OrganizationStatus.ACTIVE:
                raise ValueError("Organization is not active.")

            membership, _ = OrganizationMembership.objects.get_or_create(
                organization=invitation.organization,
                user=user,
                defaults={
                    "role": invitation.role,
                    "status": MembershipStatus.ACTIVE,
                    "joined_at": now,
                    "invited_by": invitation.invited_by,
                },
            )
            if membership.status != MembershipStatus.ACTIVE:
                membership.role = invitation.role
                membership.status = MembershipStatus.ACTIVE
                membership.joined_at = now
                membership.invited_by = invitation.invited_by
                membership.save(
                    update_fields=[
                        "role",
                        "status",
                        "joined_at",
                        "invited_by",
                        "updated_at",
                    ]
                )

            invitation.status = InvitationStatus.ACCEPTED
            invitation.accepted_at = now
            invitation.save(update_fields=["status", "accepted_at", "updated_at"])
            record_audit_event(
                action=AuditAction.MEMBERSHIP_ACCEPTED,
                entity_type="organization_membership",
                entity_id=membership.pk,
                organization=invitation.organization,
                actor=user,
                metadata={"role": membership.role},
            )
            return membership

    if expired:
        raise ValueError("Invitation has expired.")
    raise ValueError("Invitation could not be accepted.")


@transaction.atomic
def create_organization_with_owner(
    *,
    owner: User,
    name: str,
    slug: str,
    legal_name: str = "",
    timezone_name: str = "UTC",
    currency: str = "USD",
) -> Organization:
    """Create an organization and its active owner membership atomically."""

    if not owner.is_authenticated or owner._state.adding or not owner.is_active:
        raise ValueError("An authenticated user is required.")

    organization = Organization.objects.create(
        name=name,
        legal_name=legal_name,
        slug=canonicalize_lower_identifier(slug),
        timezone=timezone_name,
        currency=currency,
        created_by=owner,
        updated_by=owner,
    )
    OrganizationSettings.objects.create(
        organization=organization,
        timezone=timezone_name,
        currency=currency,
    )
    OrganizationMembership.objects.create(
        organization=organization,
        user=owner,
        role=MembershipRole.OWNER,
        status=MembershipStatus.ACTIVE,
        joined_at=timezone.now(),
        invited_by=None,
    )
    record_audit_event(
        action=AuditAction.ORGANIZATION_CREATED,
        entity_type="organization",
        entity_id=organization.pk,
        organization=organization,
        actor=owner,
        metadata={"name": organization.name},
    )
    return organization


def get_valid_memberships(user: Any) -> QuerySet[OrganizationMembership]:
    """Return active memberships for active, non-deleted organizations."""
    if not getattr(user, "is_authenticated", False):
        return OrganizationMembership.objects.none()
    return (
        OrganizationMembership.objects.filter(
            user=user,
            status=MembershipStatus.ACTIVE,
            organization__status=OrganizationStatus.ACTIVE,
            organization__deleted_at__isnull=True,
        )
        .select_related("organization")
        .order_by("organization__name")
    )


def get_organization_members(
    *,
    user: User,
    organization: Organization,
) -> QuerySet[OrganizationMembership]:
    """Return active members only after validating active tenant access."""

    has_access = get_valid_memberships(user).filter(organization=organization).exists()
    if not has_access:
        raise PermissionDenied("You do not have access to this organization.")
    return (
        OrganizationMembership.objects.filter(
            organization=organization,
            status=MembershipStatus.ACTIVE,
        )
        .select_related("user")
        .order_by("user__username")
    )


def resolve_active_organization(
    user: Any,
    organization_id: str | uuid.UUID | None = None,
) -> Organization | None:
    """Resolve an organization the user is allowed to access."""
    memberships = get_valid_memberships(user)
    if organization_id is not None:
        try:
            normalized_id = uuid.UUID(str(organization_id))
        except (TypeError, ValueError, AttributeError):
            return None
        membership = memberships.filter(organization_id=normalized_id).first()
        return membership.organization if membership else None
    if memberships.count() != 1:
        return None
    membership = memberships.first()
    return membership.organization if membership else None


def resolve_session_organization(
    user: Any,
    session: MutableMapping[str, Any],
) -> Organization | None:
    """Resolve and validate the organization stored in the current session."""

    organization_id = session.get(ACTIVE_ORGANIZATION_SESSION_KEY)
    organization = resolve_active_organization(user, organization_id)
    if organization is None and organization_id is not None:
        clear_active_organization(session)
    return organization


def set_active_organization(
    session: MutableMapping[str, Any],
    organization: Organization,
) -> None:
    """Store a validated organization identifier in the current session."""
    session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(organization.pk)


def clear_active_organization(session: MutableMapping[str, Any]) -> None:
    """Remove the active organization from the current session."""
    session.pop(ACTIVE_ORGANIZATION_SESSION_KEY, None)
