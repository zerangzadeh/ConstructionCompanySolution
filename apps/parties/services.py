from dataclasses import dataclass
from datetime import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max, Q, QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import (
    BusinessPermissionCode,
    Organization,
    OrganizationStatus,
)
from apps.parties.models import (
    BusinessParty,
    ContactType,
    PartyAlias,
    PartyAliasType,
    PartyClassification,
    PartyClassificationAssignment,
    PartyClassificationKind,
    PartyContact,
    PartyIdentitySnapshot,
    PartyKind,
    PartyRepresentative,
    PartyRepresentativeAuthority,
    PartyRestriction,
    PartyRestrictionEffect,
    PartyRestrictionScope,
    PartyRole,
    PartyRoleType,
)
from core.identifiers import (
    canonicalize_lower_identifier,
    canonicalize_party_identity_value,
)


@dataclass(frozen=True, slots=True)
class PartyDuplicateCandidate:
    party: BusinessParty
    matched_fields: tuple[str, ...]


def _require_active_management_access(
    *,
    organization: Organization,
    actor: User,
    permission: BusinessPermissionCode,
) -> None:
    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied("ورود به حساب کاربری الزامی است.")
    if organization.status != OrganizationStatus.ACTIVE or organization.deleted_at:
        raise PermissionDenied("سازمان فعال نیست.")
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        message="اجازه انجام این عملیات روی طرف‌های تجاری را ندارید.",
    )


def _identity_snapshot_values(party: BusinessParty) -> dict[str, str]:
    return {
        "party_kind": party.party_kind,
        "display_name": party.display_name,
        "legal_name": party.legal_name,
        "tax_identifier": party.tax_identifier,
        "normalized_display_name": party.normalized_display_name,
        "normalized_legal_name": party.normalized_legal_name,
        "normalized_tax_identifier": party.normalized_tax_identifier,
    }


def _record_identity_snapshot(
    *, party: BusinessParty, actor: User | None, reason: str
) -> PartyIdentitySnapshot:
    sequence = (
        PartyIdentitySnapshot.objects.filter(party=party).aggregate(Max("sequence"))[
            "sequence__max"
        ]
        or 0
    ) + 1
    return PartyIdentitySnapshot.objects.create(
        organization=party.organization,
        party=party,
        sequence=sequence,
        reason=reason,
        recorded_by=actor,
        **_identity_snapshot_values(party),
    )


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

    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PARTIES_CREATE,
    )
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
        party.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError("طرف تجاری با این شناسه مالیاتی از قبل وجود دارد.") from exc
    _record_identity_snapshot(party=party, actor=actor, reason="party_created")
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

    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PARTIES_CHANGE,
    )
    locked_party = BusinessParty.objects.select_for_update().get(pk=party.pk)
    if locked_party.organization_id != organization.id:
        raise PermissionDenied("طرف تجاری متعلق به این سازمان نیست.")
    if locked_party.archived_at is not None:
        raise ValueError("طرف تجاری بایگانی‌شده قابل به‌روزرسانی نیست.")
    if party_kind not in PartyKind.values:
        raise ValueError("نوع طرف تجاری معتبر نیست.")
    before = _identity_snapshot_values(locked_party)
    locked_party.party_kind = party_kind
    locked_party.display_name = display_name.strip()
    locked_party.legal_name = legal_name.strip()
    locked_party.tax_identifier = tax_identifier.strip()
    locked_party.updated_by = actor
    try:
        locked_party.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError("طرف تجاری با این شناسه مالیاتی از قبل وجود دارد.") from exc
    after = _identity_snapshot_values(locked_party)
    changed_fields = sorted(field for field in before if before[field] != after[field])
    if before != after:
        _record_identity_snapshot(
            party=locked_party, actor=actor, reason="identity_updated"
        )
    record_audit_event(
        action=AuditAction.BUSINESS_PARTY_UPDATED,
        entity_type="business_party",
        entity_id=locked_party.pk,
        organization=organization,
        actor=actor,
        metadata={"changed_fields": changed_fields},
    )
    return locked_party


def get_organization_parties(
    *, user: User, organization: Organization
) -> QuerySet[BusinessParty]:
    """List only active parties after checking the tenant membership."""

    require_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.PARTIES_VIEW,
        message="اجازه مشاهده طرف‌های تجاری این سازمان را ندارید.",
    )
    return BusinessParty.objects.filter(
        organization=organization,
        archived_at__isnull=True,
        merged_into__isnull=True,
    ).prefetch_related("roles")


def find_duplicate_candidates(
    *,
    user: User,
    organization: Organization,
    party: BusinessParty | None = None,
    display_name: str = "",
    legal_name: str = "",
    tax_identifier: str = "",
) -> list[PartyDuplicateCandidate]:
    """Return explainable Tenant-local candidates without changing identity."""

    require_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.PARTIES_VIEW,
        message="اجازه مشاهده طرف‌های تجاری این سازمان را ندارید.",
    )
    if party is not None:
        if party.organization_id != organization.pk:
            raise PermissionDenied("طرف تجاری متعلق به این سازمان نیست.")
        display_name = party.display_name
        legal_name = party.legal_name
        tax_identifier = party.tax_identifier
    normalized = {
        "display_name": canonicalize_party_identity_value(display_name),
        "legal_name": canonicalize_party_identity_value(legal_name),
        "tax_identifier": canonicalize_party_identity_value(tax_identifier),
    }
    predicate = Q()
    for field, value in normalized.items():
        if value:
            predicate |= Q(**{f"normalized_{field}": value})
    if not predicate:
        return []
    candidates = BusinessParty.objects.filter(
        predicate,
        organization=organization,
        archived_at__isnull=True,
        merged_into__isnull=True,
    )
    if party is not None:
        candidates = candidates.exclude(pk=party.pk)
    result: list[PartyDuplicateCandidate] = []
    for candidate in candidates.order_by("display_name", "pk"):
        matches = tuple(
            field
            for field, value in normalized.items()
            if value and getattr(candidate, f"normalized_{field}") == value
        )
        result.append(PartyDuplicateCandidate(candidate, matches))
    return result


def resolve_canonical_party(
    *, user: User, organization: Organization, party: BusinessParty
) -> BusinessParty:
    require_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.PARTIES_VIEW,
        message="اجازه مشاهده طرف‌های تجاری این سازمان را ندارید.",
    )
    try:
        current = BusinessParty.objects.select_related("merged_into").get(
            pk=party.pk, organization=organization
        )
    except BusinessParty.DoesNotExist as exc:
        raise PermissionDenied("طرف تجاری متعلق به این سازمان نیست.") from exc
    return current.merged_into or current


@transaction.atomic
def record_business_party_merge(
    *,
    organization: Organization,
    actor: User,
    source: BusinessParty,
    survivor: BusinessParty,
    reason: str,
) -> BusinessParty:
    """Record non-destructive merge lineage; never rewrite transaction FKs."""

    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PARTIES_MERGE,
    )
    if source.pk == survivor.pk:
        raise ValueError("طرف تجاری نمی‌تواند در خودش ادغام شود.")
    locked = {
        row.pk: row
        for row in BusinessParty.objects.select_for_update()
        .filter(organization=organization, pk__in=[source.pk, survivor.pk])
        .order_by("pk")
    }
    if len(locked) != 2:
        raise PermissionDenied("هر دو طرف تجاری باید متعلق به این سازمان باشند.")
    source_row = locked[source.pk]
    survivor_row = locked[survivor.pk]
    if source_row.archived_at or survivor_row.archived_at:
        raise ValueError("فقط طرف‌های تجاری فعال قابل ادغام هستند.")
    if source_row.merged_into_id or survivor_row.merged_into_id:
        raise ValueError("زنجیره ادغام طرف تجاری مجاز نیست.")
    if source_row.merged_sources.exists():
        raise ValueError("طرف تجاری مرجعِ ادغام قبلی قابل ادغام در مرجع دیگری نیست.")
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValueError("ثبت دلیل ادغام الزامی است.")
    merged_at = timezone.now()
    source_row.merged_into = survivor_row
    source_row.merged_at = merged_at
    source_row.merged_by = actor
    source_row.merge_reason = normalized_reason
    source_row.archived_at = merged_at
    source_row.updated_by = actor
    source_row.save(
        update_fields=[
            "merged_into",
            "merged_at",
            "merged_by",
            "merge_reason",
            "archived_at",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.BUSINESS_PARTY_MERGED,
        entity_type="business_party",
        entity_id=source_row.pk,
        organization=organization,
        actor=actor,
        metadata={
            "source_party_id": str(source_row.pk),
            "survivor_party_id": str(survivor_row.pk),
        },
    )
    return source_row


def get_effective_party_restrictions(
    *,
    user: User,
    organization: Organization,
    party: BusinessParty,
    at: datetime | None = None,
) -> QuerySet[PartyRestriction]:
    require_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.PARTIES_VIEW,
        message="اجازه مشاهده طرف‌های تجاری این سازمان را ندارید.",
    )
    if party.organization_id != organization.pk:
        raise PermissionDenied("طرف تجاری متعلق به این سازمان نیست.")
    effective_at = at or timezone.now()
    return PartyRestriction.objects.filter(
        organization=organization,
        party=party,
        effective_from__lte=effective_at,
        revoked_at__isnull=True,
    ).filter(Q(effective_until__isnull=True) | Q(effective_until__gt=effective_at))


@transaction.atomic
def create_tenant_party_restriction(
    *,
    organization: Organization,
    actor: User,
    party: BusinessParty,
    code: str,
    effect: str,
    reason: str,
    effective_from: datetime | None = None,
    effective_until: datetime | None = None,
) -> PartyRestriction:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PARTY_RESTRICTIONS_MANAGE,
    )
    try:
        locked_party = BusinessParty.objects.select_for_update().get(
            pk=party.pk, organization=organization
        )
    except BusinessParty.DoesNotExist as exc:
        raise PermissionDenied("طرف تجاری متعلق به این سازمان نیست.") from exc
    if locked_party.archived_at or locked_party.merged_into_id:
        raise ValueError("برای طرف تجاری غیرفعال نمی‌توان محدودیت ثبت کرد.")
    restriction = PartyRestriction(
        organization=organization,
        party=locked_party,
        scope=PartyRestrictionScope.TENANT,
        code=canonicalize_lower_identifier(code),
        effect=effect,
        reason=reason.strip(),
        effective_from=effective_from or timezone.now(),
        effective_until=effective_until,
        created_by=actor,
    )
    try:
        restriction.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError("اطلاعات محدودیت طرف تجاری معتبر نیست.") from exc
    record_audit_event(
        action=AuditAction.PARTY_RESTRICTION_CREATED,
        entity_type="party_restriction",
        entity_id=restriction.pk,
        organization=organization,
        actor=actor,
        metadata={
            "party_id": str(locked_party.pk),
            "scope": restriction.scope,
            "code": restriction.code,
            "effect": restriction.effect,
        },
    )
    return restriction


@transaction.atomic
def revoke_tenant_party_restriction(
    *,
    organization: Organization,
    actor: User,
    restriction: PartyRestriction,
    reason: str,
) -> PartyRestriction:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PARTY_RESTRICTIONS_MANAGE,
    )
    try:
        locked = PartyRestriction.objects.select_for_update().get(
            pk=restriction.pk, organization=organization
        )
    except PartyRestriction.DoesNotExist as exc:
        raise PermissionDenied("محدودیت متعلق به این سازمان نیست.") from exc
    if locked.scope != PartyRestrictionScope.TENANT:
        raise PermissionDenied("محدودیت پلتفرم توسط نقش Tenant قابل تغییر نیست.")
    if locked.revoked_at:
        raise ValueError("محدودیت از قبل لغو شده است.")
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValueError("ثبت دلیل لغو الزامی است.")
    locked.revoked_at = timezone.now()
    locked.revoked_by = actor
    locked.revocation_reason = normalized_reason
    locked.save(
        update_fields=[
            "revoked_at",
            "revoked_by",
            "revocation_reason",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.PARTY_RESTRICTION_REVOKED,
        entity_type="party_restriction",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"party_id": str(locked.party_id), "code": locked.code},
    )
    return locked


def assert_party_transaction_allowed(
    *, organization: Organization, party: BusinessParty, at: datetime | None = None
) -> None:
    """Fail closed only for explicit effective transaction-block restrictions."""

    if party.organization_id != organization.pk:
        raise PermissionDenied("طرف تجاری متعلق به این سازمان نیست.")
    if party.archived_at or party.merged_into_id:
        raise PermissionDenied("طرف تجاری برای تراکنش جدید فعال نیست.")
    effective_at = at or timezone.now()
    if (
        PartyRestriction.objects.filter(
            organization=organization,
            party=party,
            effect=PartyRestrictionEffect.BLOCK_NEW_TRANSACTIONS,
            effective_from__lte=effective_at,
            revoked_at__isnull=True,
        )
        .filter(Q(effective_until__isnull=True) | Q(effective_until__gt=effective_at))
        .exists()
    ):
        raise PermissionDenied("محدودیت صریح، ایجاد تراکنش جدید را مسدود کرده است.")


@transaction.atomic
def archive_business_party(
    *, organization: Organization, actor: User, party: BusinessParty
) -> BusinessParty:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PARTIES_ARCHIVE,
    )
    locked_party = BusinessParty.objects.select_for_update().get(pk=party.pk)
    if locked_party.organization_id != organization.id:
        raise PermissionDenied("طرف تجاری متعلق به این سازمان نیست.")
    if locked_party.archived_at is not None:
        raise ValueError("طرف تجاری از قبل بایگانی شده است.")
    if locked_party.merged_sources.exists():
        raise ValueError("طرف تجاری مرجع ادغام قابل بایگانی نیست.")
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
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PARTY_ROLES_ASSIGN,
    )
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
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PARTY_CONTACTS_ADD,
    )
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


@transaction.atomic
def record_party_alias(
    *,
    organization: Organization,
    actor: User,
    party: BusinessParty,
    alias_type: str,
    value: str,
    reason: str,
) -> PartyAlias:
    """Record immutable alternate identity evidence without changing the party."""

    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PARTY_GOVERNANCE_MANAGE,
    )
    if alias_type not in PartyAliasType.values:
        raise ValueError("نوع نام مستعار معتبر نیست.")
    try:
        locked_party = BusinessParty.objects.select_for_update().get(
            pk=party.pk, organization=organization
        )
    except BusinessParty.DoesNotExist as exc:
        raise PermissionDenied("طرف تجاری متعلق به این سازمان نیست.") from exc
    if locked_party.archived_at or locked_party.merged_into_id:
        raise ValueError("برای طرف تجاری غیرفعال نمی‌توان نام مستعار ثبت کرد.")
    alias = PartyAlias(
        organization=organization,
        party=locked_party,
        alias_type=alias_type,
        value=value,
        reason=reason,
        recorded_by=actor,
    )
    try:
        alias.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError(
            "این سابقه نام مستعار از قبل وجود دارد یا معتبر نیست."
        ) from exc
    record_audit_event(
        action=AuditAction.PARTY_ALIAS_RECORDED,
        entity_type="party_alias",
        entity_id=alias.pk,
        organization=organization,
        actor=actor,
        metadata={"party_id": str(locked_party.pk), "alias_type": alias.alias_type},
    )
    return alias


def find_parties_by_alias(
    *,
    user: User,
    organization: Organization,
    alias_type: str,
    value: str,
) -> list[BusinessParty]:
    """Resolve exact Tenant-local aliases; ambiguity remains visible to callers."""

    require_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.PARTIES_VIEW,
        message="اجازه مشاهده طرف‌های تجاری این سازمان را ندارید.",
    )
    if alias_type not in PartyAliasType.values:
        raise ValueError("نوع نام مستعار معتبر نیست.")
    normalized = canonicalize_party_identity_value(value)
    if not normalized:
        return []
    aliases = PartyAlias.objects.filter(
        organization=organization,
        alias_type=alias_type,
        normalized_value=normalized,
    ).select_related("party", "party__merged_into")
    resolved: dict[object, BusinessParty] = {}
    for alias in aliases:
        canonical = alias.party.merged_into or alias.party
        if canonical.archived_at is None:
            resolved[canonical.pk] = canonical
    return sorted(resolved.values(), key=lambda item: (item.display_name, str(item.pk)))


@transaction.atomic
def create_party_classification(
    *,
    organization: Organization,
    actor: User,
    kind: str,
    code: str,
    name: str,
    description: str = "",
) -> PartyClassification:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PARTY_GOVERNANCE_MANAGE,
    )
    if kind not in PartyClassificationKind.values:
        raise ValueError("نوع دسته‌بندی معتبر نیست.")
    classification = PartyClassification(
        organization=organization,
        kind=kind,
        code=code,
        name=name,
        description=description.strip(),
        created_by=actor,
    )
    try:
        classification.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError("کد یا اطلاعات دسته‌بندی معتبر نیست.") from exc
    record_audit_event(
        action=AuditAction.PARTY_CLASSIFICATION_CREATED,
        entity_type="party_classification",
        entity_id=classification.pk,
        organization=organization,
        actor=actor,
        metadata={"kind": classification.kind, "code": classification.code},
    )
    return classification


@transaction.atomic
def assign_party_classification(
    *,
    organization: Organization,
    actor: User,
    party: BusinessParty,
    classification: PartyClassification,
) -> PartyClassificationAssignment:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PARTY_GOVERNANCE_MANAGE,
    )
    try:
        locked_party = BusinessParty.objects.select_for_update().get(
            pk=party.pk, organization=organization
        )
        locked_classification = PartyClassification.objects.select_for_update().get(
            pk=classification.pk, organization=organization
        )
    except (BusinessParty.DoesNotExist, PartyClassification.DoesNotExist) as exc:
        raise PermissionDenied(
            "طرف تجاری و دسته باید متعلق به این سازمان باشند."
        ) from exc
    if locked_party.archived_at or locked_party.merged_into_id:
        raise ValueError("طرف تجاری برای دسته‌بندی فعال نیست.")
    if locked_classification.archived_at:
        raise ValueError("دسته یا برچسب بایگانی‌شده قابل تخصیص نیست.")
    try:
        assignment = PartyClassificationAssignment.objects.create(
            organization=organization,
            party=locked_party,
            classification=locked_classification,
            assigned_at=timezone.now(),
            assigned_by=actor,
        )
    except (IntegrityError, ValidationError) as exc:
        raise ValueError("این دسته یا برچسب اکنون به طرف تجاری تخصیص دارد.") from exc
    record_audit_event(
        action=AuditAction.PARTY_CLASSIFICATION_ASSIGNED,
        entity_type="party_classification_assignment",
        entity_id=assignment.pk,
        organization=organization,
        actor=actor,
        metadata={
            "party_id": str(locked_party.pk),
            "classification_id": str(locked_classification.pk),
        },
    )
    return assignment


@transaction.atomic
def revoke_party_classification(
    *,
    organization: Organization,
    actor: User,
    assignment: PartyClassificationAssignment,
    reason: str,
) -> PartyClassificationAssignment:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PARTY_GOVERNANCE_MANAGE,
    )
    try:
        locked = PartyClassificationAssignment.objects.select_for_update().get(
            pk=assignment.pk, organization=organization
        )
    except PartyClassificationAssignment.DoesNotExist as exc:
        raise PermissionDenied("انتساب متعلق به این سازمان نیست.") from exc
    if locked.revoked_at:
        raise ValueError("انتساب از قبل لغو شده است.")
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValueError("دلیل لغو الزامی است.")
    locked.revoked_at = timezone.now()
    locked.revoked_by = actor
    locked.revocation_reason = normalized_reason
    locked.save(
        update_fields=["revoked_at", "revoked_by", "revocation_reason", "updated_at"]
    )
    record_audit_event(
        action=AuditAction.PARTY_CLASSIFICATION_REVOKED,
        entity_type="party_classification_assignment",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"party_id": str(locked.party_id)},
    )
    return locked


@transaction.atomic
def record_party_representative(
    *,
    organization: Organization,
    actor: User,
    party: BusinessParty,
    authority: str,
    full_name: str,
    evidence_reference: str,
    effective_from: datetime | None = None,
    effective_until: datetime | None = None,
    title: str = "",
) -> PartyRepresentative:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PARTY_GOVERNANCE_MANAGE,
    )
    if authority not in PartyRepresentativeAuthority.values:
        raise ValueError("نوع اختیار نماینده معتبر نیست.")
    try:
        locked_party = BusinessParty.objects.select_for_update().get(
            pk=party.pk, organization=organization
        )
    except BusinessParty.DoesNotExist as exc:
        raise PermissionDenied("طرف تجاری متعلق به این سازمان نیست.") from exc
    if locked_party.archived_at or locked_party.merged_into_id:
        raise ValueError("برای طرف تجاری غیرفعال نمی‌توان نماینده ثبت کرد.")
    representative = PartyRepresentative(
        organization=organization,
        party=locked_party,
        authority=authority,
        full_name=full_name,
        title=title,
        evidence_reference=evidence_reference,
        effective_from=effective_from or timezone.now(),
        effective_until=effective_until,
        recorded_by=actor,
    )
    try:
        representative.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError("اطلاعات نماینده یا بازه اعتبار معتبر نیست.") from exc
    record_audit_event(
        action=AuditAction.PARTY_REPRESENTATIVE_RECORDED,
        entity_type="party_representative",
        entity_id=representative.pk,
        organization=organization,
        actor=actor,
        metadata={"party_id": str(locked_party.pk), "authority": authority},
    )
    return representative


@transaction.atomic
def revoke_party_representative(
    *,
    organization: Organization,
    actor: User,
    representative: PartyRepresentative,
    reason: str,
) -> PartyRepresentative:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PARTY_GOVERNANCE_MANAGE,
    )
    try:
        locked = PartyRepresentative.objects.select_for_update().get(
            pk=representative.pk, organization=organization
        )
    except PartyRepresentative.DoesNotExist as exc:
        raise PermissionDenied("نماینده متعلق به این سازمان نیست.") from exc
    if locked.revoked_at:
        raise ValueError("نماینده از قبل لغو شده است.")
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValueError("دلیل لغو الزامی است.")
    locked.revoked_at = timezone.now()
    locked.revoked_by = actor
    locked.revocation_reason = normalized_reason
    locked.save(
        update_fields=["revoked_at", "revoked_by", "revocation_reason", "updated_at"]
    )
    record_audit_event(
        action=AuditAction.PARTY_REPRESENTATIVE_REVOKED,
        entity_type="party_representative",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"party_id": str(locked.party_id), "authority": locked.authority},
    )
    return locked


def get_effective_party_representatives(
    *,
    user: User,
    organization: Organization,
    party: BusinessParty,
    at: datetime | None = None,
) -> QuerySet[PartyRepresentative]:
    require_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.PARTIES_VIEW,
        message="اجازه مشاهده طرف‌های تجاری این سازمان را ندارید.",
    )
    if party.organization_id != organization.pk:
        raise PermissionDenied("طرف تجاری متعلق به این سازمان نیست.")
    effective_at = at or timezone.now()
    return PartyRepresentative.objects.filter(
        organization=organization,
        party=party,
        effective_from__lte=effective_at,
        revoked_at__isnull=True,
    ).filter(Q(effective_until__isnull=True) | Q(effective_until__gt=effective_at))
