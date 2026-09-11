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
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import (
    BusinessPermissionCode,
    InvitationRole,
    InvitationStatus,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
    OrganizationRole,
    OrganizationSettings,
    OrganizationStatus,
)
from core.identifiers import canonicalize_lower_identifier

ACTIVE_ORGANIZATION_SESSION_KEY = "active_organization_id"
INVITATION_LIFETIME = timedelta(days=7)


def _hash_invitation_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _resolve_active_role(role: OrganizationRole | str) -> OrganizationRole:
    if isinstance(role, OrganizationRole):
        role_definition = role
    else:
        try:
            role_definition = OrganizationRole.objects.get(code=role)
        except OrganizationRole.DoesNotExist as exc:
            raise ValueError("نقش انتخاب‌شده معتبر نیست.") from exc
    if not role_definition.is_active:
        raise ValueError("نقش انتخاب‌شده غیرفعال است.")
    return role_definition


def _validate_role_delegation(
    *,
    actor: User,
    actor_membership: OrganizationMembership | None,
    assigned_role: OrganizationRole,
    current_role: OrganizationRole | None = None,
) -> None:
    """Prevent membership managers from delegating privileges they do not hold."""

    if actor.is_superuser or (
        actor_membership is not None and actor_membership.role_definition.is_owner
    ):
        return
    if actor_membership is None:
        raise PermissionDenied("اجازه واگذاری این نقش را ندارید.")
    actor_permissions = set(
        actor_membership.role_definition.permissions.filter(is_active=True).values_list(
            "code", flat=True
        )
    )
    roles_to_compare = [assigned_role]
    if current_role is not None:
        roles_to_compare.append(current_role)
    for role_definition in roles_to_compare:
        role_permissions = set(
            role_definition.permissions.filter(is_active=True).values_list(
                "code", flat=True
            )
        )
        if not role_permissions.issubset(actor_permissions):
            raise PermissionDenied(
                "نمی‌توانید نقشی با اختیارات بیشتر از نقش خود واگذار یا مدیریت کنید."
            )


@transaction.atomic
def update_organization_membership(
    *,
    organization: Organization,
    actor: User,
    membership: OrganizationMembership,
    role: OrganizationRole | str,
    status: str,
) -> OrganizationMembership:
    """Update tenant membership access with authorization and audit evidence."""

    locked_organization = Organization.objects.select_for_update().get(
        pk=organization.pk
    )
    if (
        locked_organization.status != OrganizationStatus.ACTIVE
        or locked_organization.deleted_at is not None
    ):
        raise PermissionDenied("سازمان فعال نیست.")

    actor_membership = require_business_permission(
        user=actor,
        organization=locked_organization,
        permission=BusinessPermissionCode.MEMBERSHIP_MANAGE,
        message="اجازه مدیریت عضویت‌های این شرکت را ندارید.",
    )
    role_definition = _resolve_active_role(role)
    if status not in MembershipStatus.values:
        raise ValueError("وضعیت عضویت معتبر نیست.")

    locked_membership = (
        OrganizationMembership.objects.select_for_update()
        .select_related("user", "role_definition")
        .get(pk=membership.pk)
    )
    if locked_membership.organization_id != locked_organization.pk:
        raise PermissionDenied("عضویت متعلق به این سازمان نیست.")
    actor_is_owner = bool(
        actor_membership and actor_membership.role_definition.is_owner
    )
    if (
        not actor.is_superuser
        and not actor_is_owner
        and (locked_membership.role_definition.is_owner or role_definition.is_owner)
    ):
        raise PermissionDenied("فقط مالک می‌تواند نقش مالک را مدیریت کند.")
    _validate_role_delegation(
        actor=actor,
        actor_membership=actor_membership,
        assigned_role=role_definition,
        current_role=locked_membership.role_definition,
    )

    owner_access_removed = (
        locked_membership.role_definition.is_owner
        and locked_membership.status == MembershipStatus.ACTIVE
        and (not role_definition.is_owner or status != MembershipStatus.ACTIVE)
    )
    if (
        owner_access_removed
        and not OrganizationMembership.objects.filter(
            organization=locked_organization,
            role_definition__is_owner=True,
            status=MembershipStatus.ACTIVE,
        )
        .exclude(pk=locked_membership.pk)
        .exists()
    ):
        raise ValueError("سازمان باید حداقل یک مالک فعال داشته باشد.")

    previous_role = locked_membership.role_definition.code
    previous_status = locked_membership.status
    now = timezone.now()
    if previous_role != role_definition.code:
        record_audit_event(
            action=AuditAction.MEMBERSHIP_ROLE_CHANGED,
            entity_type="organization_membership",
            entity_id=locked_membership.pk,
            organization=locked_organization,
            actor=actor,
            metadata={
                "target_user_id": str(locked_membership.user_id),
                "target_username": locked_membership.user.username,
                "previous_role": previous_role,
                "new_role": role_definition.code,
            },
        )
    if previous_status != status:
        record_audit_event(
            action=AuditAction.MEMBERSHIP_STATUS_CHANGED,
            entity_type="organization_membership",
            entity_id=locked_membership.pk,
            organization=locked_organization,
            actor=actor,
            metadata={
                "target_user_id": str(locked_membership.user_id),
                "target_username": locked_membership.user.username,
                "previous_status": previous_status,
                "new_status": status,
            },
        )

    locked_membership.role_definition = role_definition
    locked_membership.role = role_definition.code
    locked_membership.status = status
    if status == MembershipStatus.ACTIVE and locked_membership.joined_at is None:
        locked_membership.joined_at = now
    update_fields = ["role", "role_definition", "status", "updated_at"]
    if status == MembershipStatus.ACTIVE and locked_membership.joined_at == now:
        update_fields.append("joined_at")
    locked_membership.save(update_fields=update_fields)
    return locked_membership


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
        raise PermissionDenied("سازمان فعال نیست.")
    require_business_permission(
        user=updated_by,
        organization=locked_organization,
        permission=BusinessPermissionCode.COMPANY_SETTINGS_MANAGE,
        message="اجازه به‌روزرسانی تنظیمات این شرکت را ندارید.",
    )

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
    role: OrganizationRole | str = InvitationRole.MEMBER,
    expires_in: timedelta = INVITATION_LIFETIME,
) -> tuple[OrganizationInvitation, str]:
    """Create a hashed-token invitation for an existing user."""

    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("سازمان فعال نیست.")
    inviter_membership = require_business_permission(
        user=invited_by,
        organization=organization,
        permission=BusinessPermissionCode.MEMBERSHIP_MANAGE,
        message="اجازه دعوت عضو به این سازمان را ندارید.",
    )
    if invited_by == invitee:
        raise ValueError("نمی‌توانید خودتان را دعوت کنید.")
    role_definition = _resolve_active_role(role)
    if role_definition.is_owner:
        raise ValueError("نقش مالک شرکت از طریق دعوت‌نامه قابل تخصیص نیست.")
    _validate_role_delegation(
        actor=invited_by,
        actor_membership=inviter_membership,
        assigned_role=role_definition,
    )

    existing_membership = OrganizationMembership.objects.filter(
        organization=organization,
        user=invitee,
    ).first()
    if existing_membership and existing_membership.status == MembershipStatus.ACTIVE:
        raise ValueError("کاربر از قبل عضو فعال سازمان است.")

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
        raise ValueError("یک دعوت‌نامه در انتظار از قبل وجود دارد.")

    raw_token = secrets.token_urlsafe(32)
    invitation = OrganizationInvitation.objects.create(
        organization=organization,
        invitee=invitee,
        invited_by=invited_by,
        role=role_definition.code,
        role_definition=role_definition,
        token_hash=_hash_invitation_token(raw_token),
        expires_at=now + expires_in,
    )
    record_audit_event(
        action=AuditAction.MEMBERSHIP_INVITED,
        entity_type="organization_invitation",
        entity_id=invitation.pk,
        organization=organization,
        actor=invited_by,
        metadata={
            "invitee_username": invitee.username,
            "role": role_definition.code,
        },
    )
    return invitation, raw_token


def accept_organization_invitation(
    *,
    token: str,
    user: User,
) -> OrganizationMembership:
    """Accept a valid invitation for its intended user."""

    if not user.is_authenticated:
        raise PermissionDenied("ورود به حساب کاربری الزامی است.")

    expired = False
    with transaction.atomic():
        invitation = (
            OrganizationInvitation.objects.select_for_update()
            .select_related("organization", "invitee", "role_definition")
            .filter(token_hash=_hash_invitation_token(token))
            .first()
        )
        if invitation is None:
            raise ValueError("دعوت‌نامه معتبر نیست.")
        if invitation.invitee_id != user.id:
            raise PermissionDenied("این دعوت‌نامه متعلق به کاربر دیگری است.")
        if invitation.status != InvitationStatus.PENDING:
            raise ValueError("دعوت‌نامه دیگر در وضعیت انتظار نیست.")

        now = timezone.now()
        if invitation.expires_at <= now:
            invitation.status = InvitationStatus.EXPIRED
            invitation.save(update_fields=["status", "updated_at"])
            expired = True
        else:
            if invitation.organization.status != OrganizationStatus.ACTIVE:
                raise ValueError("سازمان فعال نیست.")

            membership, _ = OrganizationMembership.objects.get_or_create(
                organization=invitation.organization,
                user=user,
                defaults={
                    "role": invitation.role,
                    "role_definition": invitation.role_definition,
                    "status": MembershipStatus.ACTIVE,
                    "joined_at": now,
                    "invited_by": invitation.invited_by,
                },
            )
            if membership.status != MembershipStatus.ACTIVE:
                membership.role = invitation.role
                membership.role_definition = invitation.role_definition
                membership.status = MembershipStatus.ACTIVE
                membership.joined_at = now
                membership.invited_by = invitation.invited_by
                membership.save(
                    update_fields=[
                        "role",
                        "role_definition",
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
                metadata={"role": membership.role_definition.code},
            )
            return membership

    if expired:
        raise ValueError("دعوت‌نامه منقضی شده است.")
    raise ValueError("پذیرش دعوت‌نامه ممکن نشد.")


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
        raise ValueError("کاربر واردشده به سامانه الزامی است.")

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
    owner_role = OrganizationRole.objects.get(
        code=MembershipRole.COMPANY_OWNER,
        is_active=True,
        is_owner=True,
    )
    OrganizationMembership.objects.create(
        organization=organization,
        user=owner,
        role=MembershipRole.COMPANY_OWNER,
        role_definition=owner_role,
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


def create_organization_by_system_admin(
    *,
    actor: User,
    owner: User,
    name: str,
    slug: str,
    legal_name: str = "",
    timezone_name: str = "UTC",
    currency: str = "USD",
) -> Organization:
    """Create a tenant only when requested by the global system administrator."""

    if (
        not actor.is_authenticated
        or actor._state.adding
        or not actor.is_active
        or not actor.is_superuser
    ):
        raise PermissionDenied("فقط ادمین سامانه می‌تواند شرکت جدید ایجاد کند.")

    return create_organization_with_owner(
        owner=owner,
        name=name,
        slug=slug,
        legal_name=legal_name,
        timezone_name=timezone_name,
        currency=currency,
    )


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
            role_definition__is_active=True,
        )
        .select_related("organization", "role_definition")
        .order_by("organization__name")
    )


def get_organization_members(
    *,
    user: User,
    organization: Organization,
    include_inactive: bool = False,
) -> QuerySet[OrganizationMembership]:
    """Return active members only after validating active tenant access."""

    has_access = get_valid_memberships(user).filter(organization=organization).exists()
    if not has_access:
        raise PermissionDenied("به این سازمان دسترسی ندارید.")
    memberships = OrganizationMembership.objects.filter(organization=organization)
    if not include_inactive:
        memberships = memberships.filter(status=MembershipStatus.ACTIVE)
    return memberships.select_related("user", "role_definition").order_by(
        "user__username"
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
