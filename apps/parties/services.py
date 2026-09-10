from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationStatus,
)
from apps.parties.models import (
    BusinessParty,
    ContactType,
    PartyContact,
    PartyKind,
    PartyRole,
    PartyRoleType,
)


def _can_manage_parties(user: User, organization: Organization) -> bool:
    return organization.memberships.filter(
        user=user,
        status=MembershipStatus.ACTIVE,
        role__in=[MembershipRole.OWNER, MembershipRole.ADMIN, MembershipRole.MANAGER],
    ).exists()


def _require_active_management_access(
    *, organization: Organization, actor: User
) -> None:
    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied("ورود به حساب کاربری الزامی است.")
    if organization.status != OrganizationStatus.ACTIVE or organization.deleted_at:
        raise PermissionDenied("سازمان فعال نیست.")
    if not _can_manage_parties(actor, organization):
        raise PermissionDenied("اجازه مدیریت طرف‌های تجاری این سازمان را ندارید.")


@transaction.atomic
def create_business_party(
    *,
    organization: Organization,
    actor: User,
    party_kind: str,
    display_name: str,
    legal_name: str = "",
    tax_identifier: str = "",
) -> BusinessParty:
    """Create an independently usable tenant-owned party."""

    _require_active_management_access(organization=organization, actor=actor)
    if party_kind not in PartyKind.values:
        raise ValueError("نوع طرف تجاری معتبر نیست.")
    party = BusinessParty(
        organization=organization,
        party_kind=party_kind,
        display_name=display_name.strip(),
        legal_name=legal_name.strip(),
        tax_identifier=tax_identifier.strip(),
        created_by=actor,
        updated_by=actor,
    )
    try:
        party.full_clean()
        party.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError("طرف تجاری با این شناسه مالیاتی از قبل وجود دارد.") from exc
    record_audit_event(
        action=AuditAction.BUSINESS_PARTY_CREATED,
        entity_type="business_party",
        entity_id=party.pk,
        organization=organization,
        actor=actor,
        metadata={"display_name": party.display_name, "party_kind": party.party_kind},
    )
    return party


@transaction.atomic
def update_business_party(
    *,
    organization: Organization,
    actor: User,
    party: BusinessParty,
    party_kind: str,
    display_name: str,
    legal_name: str = "",
    tax_identifier: str = "",
) -> BusinessParty:
    """Update an active tenant-owned party without changing its identity."""

    _require_active_management_access(organization=organization, actor=actor)
    locked_party = BusinessParty.objects.select_for_update().get(pk=party.pk)
    if locked_party.organization_id != organization.id:
        raise PermissionDenied("طرف تجاری متعلق به این سازمان نیست.")
    if locked_party.archived_at is not None:
        raise ValueError("طرف تجاری بایگانی‌شده قابل به‌روزرسانی نیست.")
    if party_kind not in PartyKind.values:
        raise ValueError("نوع طرف تجاری معتبر نیست.")
    locked_party.party_kind = party_kind
    locked_party.display_name = display_name.strip()
    locked_party.legal_name = legal_name.strip()
    locked_party.tax_identifier = tax_identifier.strip()
    locked_party.updated_by = actor
    try:
        locked_party.full_clean()
        locked_party.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError("طرف تجاری با این شناسه مالیاتی از قبل وجود دارد.") from exc
    record_audit_event(
        action=AuditAction.BUSINESS_PARTY_UPDATED,
        entity_type="business_party",
        entity_id=locked_party.pk,
        organization=organization,
        actor=actor,
        metadata={"display_name": locked_party.display_name},
    )
    return locked_party


def get_organization_parties(
    *, user: User, organization: Organization
) -> QuerySet[BusinessParty]:
    """List only active parties after checking the tenant membership."""

    if not organization.memberships.filter(
        user=user, status=MembershipStatus.ACTIVE
    ).exists():
        raise PermissionDenied("به این سازمان دسترسی ندارید.")
    return BusinessParty.objects.filter(
        organization=organization, archived_at__isnull=True
    ).prefetch_related("roles")


@transaction.atomic
def archive_business_party(
    *, organization: Organization, actor: User, party: BusinessParty
) -> BusinessParty:
    _require_active_management_access(organization=organization, actor=actor)
    locked_party = BusinessParty.objects.select_for_update().get(pk=party.pk)
    if locked_party.organization_id != organization.id:
        raise PermissionDenied("طرف تجاری متعلق به این سازمان نیست.")
    if locked_party.archived_at is not None:
        raise ValueError("طرف تجاری از قبل بایگانی شده است.")
    locked_party.archived_at = timezone.now()
    locked_party.updated_by = actor
    locked_party.save(update_fields=["archived_at", "updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.BUSINESS_PARTY_ARCHIVED,
        entity_type="business_party",
        entity_id=locked_party.pk,
        organization=organization,
        actor=actor,
        metadata={"display_name": locked_party.display_name},
    )
    return locked_party


@transaction.atomic
def assign_party_role(
    *, organization: Organization, actor: User, party: BusinessParty, role: str
) -> PartyRole:
    _require_active_management_access(organization=organization, actor=actor)
    if role not in PartyRoleType.values:
        raise ValueError("نقش طرف تجاری معتبر نیست.")
    locked_party = BusinessParty.objects.select_for_update().get(pk=party.pk)
    if locked_party.organization_id != organization.id:
        raise PermissionDenied("طرف تجاری متعلق به این سازمان نیست.")
    if locked_party.archived_at is not None:
        raise ValueError("برای طرف تجاری بایگانی‌شده نمی‌توان نقش تعیین کرد.")
    try:
        party_role = PartyRole.objects.create(
            organization=organization, party=locked_party, role=role
        )
    except (IntegrityError, ValidationError) as exc:
        raise ValueError("این نقش طرف تجاری از قبل وجود دارد.") from exc
    record_audit_event(
        action=AuditAction.PARTY_ROLE_ASSIGNED,
        entity_type="party_role",
        entity_id=party_role.pk,
        organization=organization,
        actor=actor,
        metadata={"role": role, "party_name": locked_party.display_name},
    )
    return party_role


@transaction.atomic
def add_party_contact(
    *,
    organization: Organization,
    actor: User,
    party: BusinessParty,
    contact_type: str,
    value: str,
    label: str = "",
    is_primary: bool = False,
) -> PartyContact:
    _require_active_management_access(organization=organization, actor=actor)
    if contact_type not in ContactType.values:
        raise ValueError("نوع راه ارتباطی معتبر نیست.")
    locked_party = BusinessParty.objects.select_for_update().get(pk=party.pk)
    if locked_party.organization_id != organization.id:
        raise PermissionDenied("طرف تجاری متعلق به این سازمان نیست.")
    if locked_party.archived_at is not None:
        raise ValueError("برای طرف تجاری بایگانی‌شده نمی‌توان راه ارتباطی افزود.")
    if is_primary:
        PartyContact.objects.filter(
            organization=organization,
            party=locked_party,
            is_primary=True,
            archived_at__isnull=True,
        ).update(is_primary=False)
    contact = PartyContact(
        organization=organization,
        party=locked_party,
        contact_type=contact_type,
        value=value.strip(),
        label=label.strip(),
        is_primary=is_primary,
    )
    try:
        contact.full_clean()
        contact.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError("این راه ارتباطی از قبل وجود دارد.") from exc
    record_audit_event(
        action=AuditAction.PARTY_CONTACT_ADDED,
        entity_type="party_contact",
        entity_id=contact.pk,
        organization=organization,
        actor=actor,
        metadata={
            "contact_type": contact.contact_type,
            "party_name": locked_party.display_name,
        },
    )
    return contact
