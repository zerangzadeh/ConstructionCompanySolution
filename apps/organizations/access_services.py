from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import (
    effective_role_assignments,
    get_active_membership,
    is_platform_admin,
    membership_has_permission,
    membership_has_role,
    membership_has_scope,
    membership_permission_codes,
    require_business_permission,
)
from apps.organizations.models import (
    AuthorizationMigrationIssue,
    AuthorizationScopeType,
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    PlatformRoleAssignment,
    PlatformRoleCode,
    ProtectedOperation,
    ProtectedOperationCode,
)

PRIVILEGED_TENANT_ROLES = frozenset(
    {
        MembershipRole.TENANT_OWNER,
        MembershipRole.TENANT_ADMIN,
        MembershipRole.TENANT_MANAGER,
    }
)


def quarantine_membership_authorization(
    *, membership: OrganizationMembership, issue_code: str, detail: str
) -> None:
    """Switch a new/ambiguous row to deny-by-default until explicit controls finish."""

    now = timezone.now()
    membership.authorization_migrated_at = now
    membership.authorization_quarantined_at = now
    membership.save(
        update_fields=[
            "authorization_migrated_at",
            "authorization_quarantined_at",
            "updated_at",
        ]
    )
    AuthorizationMigrationIssue.objects.get_or_create(
        organization=membership.organization,
        membership=membership,
        issue_code=issue_code,
        defaults={"detail": detail},
    )


def _complete_quarantine_if_ready(membership: OrganizationMembership) -> None:
    if not membership.role_assignments.filter(revoked_at__isnull=True).exists():
        return
    if not membership.scope_grants.filter(revoked_at__isnull=True).exists():
        return
    now = timezone.now()
    membership.authorization_quarantined_at = None
    membership.save(update_fields=["authorization_quarantined_at", "updated_at"])
    membership.authorization_migration_issues.filter(resolved_at__isnull=True).update(
        resolved_at=now,
        resolution="Explicit role and scope established by P1.1 services.",
    )


def _active_membership_for_update(
    *, organization: Organization, membership_id: object
) -> OrganizationMembership:
    try:
        return (
            OrganizationMembership.objects.select_for_update(of=("self",))
            .select_related("user", "role_definition")
            .get(
                pk=membership_id,
                organization=organization,
                status=MembershipStatus.ACTIVE,
                user__is_active=True,
            )
        )
    except (ValueError, OrganizationMembership.DoesNotExist) as exc:
        raise PermissionDenied("عضویت فعال در این سازمان یافت نشد.") from exc


def _lock_membership_authority(membership: OrganizationMembership) -> None:
    """Lock and invalidate cached authority before a privileged decision."""

    OrganizationMembership.objects.select_for_update().get(pk=membership.pk)
    list(
        MembershipRoleAssignment.objects.select_for_update()
        .filter(membership=membership, revoked_at__isnull=True)
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    list(
        MembershipScopeGrant.objects.select_for_update()
        .filter(membership=membership, revoked_at__isnull=True)
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    membership.refresh_from_db()
    membership._prefetched_objects_cache = {}


def _independent_approver(
    *,
    organization: Organization,
    actor_membership: OrganizationMembership,
    target_membership: OrganizationMembership,
    approver_membership_id: object,
    permission: BusinessPermissionCode,
    allow_any_scope: bool = False,
) -> OrganizationMembership:
    approver = _active_membership_for_update(
        organization=organization, membership_id=approver_membership_id
    )
    _lock_membership_authority(approver)
    if approver.pk in (actor_membership.pk, target_membership.pk):
        raise PermissionDenied("تأییدکننده باید مستقل از عامل و گیرنده باشد.")
    if not membership_has_permission(approver, permission) or not membership_has_scope(
        approver, allow_any_scope=allow_any_scope
    ):
        raise PermissionDenied("تأییدکننده اختیار مستقل لازم را ندارد.")
    return approver


def _role(
    role: OrganizationRole | str, *, organization: Organization | None = None
) -> OrganizationRole:
    if isinstance(role, OrganizationRole):
        resolved = role
    else:
        try:
            roles = OrganizationRole.objects.filter(code=role)
            if organization is not None:
                roles = roles.filter(
                    Q(organization__isnull=True) | Q(organization=organization)
                )
            resolved = roles.get()
        except OrganizationRole.DoesNotExist as exc:
            raise ValidationError("نقش معتبر نیست.") from exc
        except OrganizationRole.MultipleObjectsReturned as exc:
            raise ValidationError("نقش انتخاب‌شده مبهم است.") from exc
    if not resolved.is_active:
        raise ValidationError("نقش غیرفعال است.")
    if organization is not None and resolved.organization_id not in (
        None,
        organization.pk,
    ):
        raise ValidationError("نقش متعلق به شرکت دیگری است.")
    return resolved


def _role_catalog_manager(*, actor: User, organization: Organization | None) -> None:
    """Authorize platform-global or exact-tenant custom-role administration."""

    if is_platform_admin(actor):
        return
    if organization is None:
        raise PermissionDenied("فقط Platform Admin می‌تواند نقش سراسری را مدیریت کند.")
    membership = get_active_membership(user=actor, organization=organization)
    if not membership_has_role(membership, MembershipRole.TENANT_ADMIN):
        raise PermissionDenied(
            "فقط Tenant Admin می‌تواند نقش اختصاصی شرکت را مدیریت کند."
        )


def _permission_codes(permissions: Iterable[BusinessPermissionCode | str]) -> list[str]:
    codes = sorted({str(permission) for permission in permissions})
    available = set(
        BusinessPermission.objects.filter(code__in=codes, is_active=True).values_list(
            "code", flat=True
        )
    )
    if available != set(codes):
        raise ValidationError("همه مجوزهای نقش باید از کاتالوگ فعال سامانه باشند.")
    return codes


def _assert_tenant_admin_permission_subset(
    *, actor: User, organization: Organization | None, permission_codes: Iterable[str]
) -> None:
    if organization is None or is_platform_admin(actor):
        return
    membership = get_active_membership(user=actor, organization=organization)
    if not set(permission_codes).issubset(membership_permission_codes(membership)):
        raise PermissionDenied(
            "Tenant Admin نمی‌تواند مجوزی فراتر از اختیار خود به نقش متصل کند."
        )


@transaction.atomic
def create_organization_role(
    *,
    actor: User,
    organization: Organization | None,
    code: str,
    name: str,
    description: str,
    permissions: Iterable[BusinessPermissionCode | str],
    reason: str,
) -> OrganizationRole:
    """Create a custom global or exact-tenant role from catalogued permissions."""

    if not reason.strip() or not name.strip():
        raise ValidationError("نام و دلیل ایجاد نقش الزامی است.")
    if organization is not None:
        organization = Organization.objects.select_for_update().get(pk=organization.pk)
    _role_catalog_manager(actor=actor, organization=organization)
    permission_codes = _permission_codes(permissions)
    _assert_tenant_admin_permission_subset(
        actor=actor, organization=organization, permission_codes=permission_codes
    )
    role = OrganizationRole(
        organization=organization,
        code=code,
        name=name.strip(),
        description=description.strip(),
        is_system=False,
        is_owner=False,
        created_by=actor,
        updated_by=actor,
    )
    role.full_clean()
    role.save()
    role.permissions.set(BusinessPermission.objects.filter(code__in=permission_codes))
    record_audit_event(
        action=AuditAction.ROLE_CREATED,
        entity_type="organizations.OrganizationRole",
        entity_id=role.pk,
        organization=organization,
        actor=actor,
        allow_platform_actor=True,
        metadata={
            "role_code": role.code,
            "role_scope": "global" if organization is None else "tenant",
            "previous_permissions": [],
            "new_permissions": permission_codes,
            "reason": reason.strip(),
        },
    )
    return role


@transaction.atomic
def update_organization_role(
    *,
    actor: User,
    role_id: object,
    name: str,
    description: str,
    permissions: Iterable[BusinessPermissionCode | str],
    reason: str,
) -> OrganizationRole:
    """Update role presentation and catalogued permissions without changing identity."""

    if not reason.strip() or not name.strip():
        raise ValidationError("نام و دلیل ویرایش نقش الزامی است.")
    try:
        role = OrganizationRole.objects.select_for_update().get(pk=role_id)
    except (ValueError, OrganizationRole.DoesNotExist) as exc:
        raise PermissionDenied("نقش یافت نشد.") from exc
    _role_catalog_manager(actor=actor, organization=role.organization)
    if role.is_system and not is_platform_admin(actor):
        raise PermissionDenied("فقط Platform Admin می‌تواند نقش سیستمی را ویرایش کند.")
    if not role.is_active:
        raise ValidationError("نقش بایگانی‌شده قابل ویرایش نیست.")
    permission_codes = _permission_codes(permissions)
    _assert_tenant_admin_permission_subset(
        actor=actor, organization=role.organization, permission_codes=permission_codes
    )
    previous_permissions = sorted(role.permissions.values_list("code", flat=True))
    previous = {"name": role.name, "description": role.description}
    role.name = name.strip()
    role.description = description.strip()
    role.updated_by = actor
    role.full_clean()
    role.save(update_fields=["name", "description", "updated_by", "updated_at"])
    role.permissions.set(BusinessPermission.objects.filter(code__in=permission_codes))
    record_audit_event(
        action=AuditAction.ROLE_UPDATED,
        entity_type="organizations.OrganizationRole",
        entity_id=role.pk,
        organization=role.organization,
        actor=actor,
        allow_platform_actor=True,
        metadata={
            "role_code": role.code,
            "previous": previous,
            "current": {"name": role.name, "description": role.description},
            "previous_permissions": previous_permissions,
            "new_permissions": permission_codes,
            "reason": reason.strip(),
        },
    )
    return role


@transaction.atomic
def archive_organization_role(
    *, actor: User, role_id: object, reason: str
) -> OrganizationRole:
    """Archive a custom role while preserving members, assignments, and history."""

    if not reason.strip():
        raise ValidationError("دلیل بایگانی نقش الزامی است.")
    try:
        role = OrganizationRole.objects.select_for_update().get(pk=role_id)
    except (ValueError, OrganizationRole.DoesNotExist) as exc:
        raise PermissionDenied("نقش یافت نشد.") from exc
    _role_catalog_manager(actor=actor, organization=role.organization)
    if role.is_system:
        raise PermissionDenied("نقش سیستمی قابل حذف یا بایگانی نیست.")
    if not role.is_active:
        return role
    now = timezone.now()
    previous_permissions = sorted(role.permissions.values_list("code", flat=True))
    role.is_active = False
    role.archived_at = now
    role.archived_by = actor
    role.archive_reason = reason.strip()
    role.updated_by = actor
    role.save(
        update_fields=[
            "is_active",
            "archived_at",
            "archived_by",
            "archive_reason",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.ROLE_ARCHIVED,
        entity_type="organizations.OrganizationRole",
        entity_id=role.pk,
        organization=role.organization,
        actor=actor,
        allow_platform_actor=True,
        metadata={
            "role_code": role.code,
            "previous_permissions": previous_permissions,
            "new_permissions": previous_permissions,
            "reason": reason.strip(),
        },
    )
    return role


def _validate_interval(*, starts_at: datetime, ends_at: datetime | None) -> None:
    if ends_at is not None and ends_at <= starts_at:
        raise ValidationError("پایان اعتبار باید پس از شروع اعتبار باشد.")


def bootstrap_membership_authorization(
    *, membership: OrganizationMembership, actor: User | None, source: str
) -> tuple[MembershipRoleAssignment, MembershipScopeGrant]:
    """Create the explicit initial Tenant Owner role and governance scope."""

    if membership.status != MembershipStatus.ACTIVE:
        raise ValidationError("فقط عضویت فعال قابل راه‌اندازی است.")
    tenant_owner = OrganizationRole.objects.get(
        code=MembershipRole.TENANT_OWNER, is_active=True
    )
    role_assignment, _ = MembershipRoleAssignment.objects.get_or_create(
        organization=membership.organization,
        membership=membership,
        role=tenant_owner,
        revoked_at__isnull=True,
        defaults={
            "assigned_by": None,
            "approved_by": None,
            "reason": "Initial Tenant Owner bootstrap",
            "source": source,
        },
    )
    scope_grant, _ = MembershipScopeGrant.objects.get_or_create(
        organization=membership.organization,
        membership=membership,
        scope_type=AuthorizationScopeType.ORGANIZATION,
        project=None,
        site=None,
        revoked_at__isnull=True,
        defaults={
            "granted_by": None,
            "approved_by": None,
            "reason": "Initial ownership and governance scope",
            "source": source,
        },
    )
    now = timezone.now()
    membership.authorization_migrated_at = now
    membership.authorization_quarantined_at = None
    membership.save(
        update_fields=[
            "authorization_migrated_at",
            "authorization_quarantined_at",
            "updated_at",
        ]
    )
    if actor is not None:
        record_audit_event(
            action=AuditAction.MEMBERSHIP_ROLE_ASSIGNED,
            entity_type="organizations.MembershipRoleAssignment",
            entity_id=role_assignment.pk,
            organization=membership.organization,
            actor=actor,
            metadata={"role": tenant_owner.code, "source": source},
        )
        record_audit_event(
            action=AuditAction.MEMBERSHIP_SCOPE_GRANTED,
            entity_type="organizations.MembershipScopeGrant",
            entity_id=scope_grant.pk,
            organization=membership.organization,
            actor=actor,
            metadata={
                "scope_type": AuthorizationScopeType.ORGANIZATION,
                "source": source,
            },
        )
    return role_assignment, scope_grant


@transaction.atomic
def assign_membership_role(
    *,
    organization: Organization,
    actor: User,
    membership_id: object,
    role: OrganizationRole | str,
    approver_membership_id: object,
    reason: str,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
) -> MembershipRoleAssignment:
    """Assign one independent role with dual control and no privilege transfer."""

    if not reason.strip():
        raise ValidationError("دلیل تخصیص نقش الزامی است.")
    Organization.objects.select_for_update().get(pk=organization.pk)
    actor_membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.AUTHORIZATION_ROLES_ASSIGN,
        message="اجازه تخصیص نقش ندارید.",
    )
    _lock_membership_authority(actor_membership)
    if not membership_has_permission(
        actor_membership, BusinessPermissionCode.AUTHORIZATION_ROLES_ASSIGN
    ) or not membership_has_scope(actor_membership):
        raise PermissionDenied("اجازه تخصیص نقش ندارید.")
    target = _active_membership_for_update(
        organization=organization, membership_id=membership_id
    )
    if target.pk == actor_membership.pk:
        raise PermissionDenied("تخصیص نقش به خود یک عملیات حفاظت‌شده و ممنوع است.")
    assigned_role = _role(role, organization=organization)
    role_permissions = set(
        assigned_role.permissions.filter(is_active=True).values_list("code", flat=True)
    )
    if not role_permissions.issubset(membership_permission_codes(actor_membership)):
        raise PermissionDenied("انتقال مجوزی خارج از اختیار عامل ممنوع است.")
    approver = _independent_approver(
        organization=organization,
        actor_membership=actor_membership,
        target_membership=target,
        approver_membership_id=approver_membership_id,
        permission=BusinessPermissionCode.AUTHORIZATION_ROLES_ASSIGN,
    )
    start = starts_at or timezone.now()
    _validate_interval(starts_at=start, ends_at=ends_at)
    if MembershipRoleAssignment.objects.filter(
        membership=target, role=assigned_role, revoked_at__isnull=True
    ).exists():
        raise ValidationError("این نقش هنوز برای عضویت فعال یا زمان‌بندی‌شده است.")
    previous_permissions = sorted(membership_permission_codes(target))
    assignment = MembershipRoleAssignment.objects.create(
        organization=organization,
        membership=target,
        role=assigned_role,
        starts_at=start,
        ends_at=ends_at,
        assigned_by=actor_membership,
        approved_by=approver,
        reason=reason.strip(),
    )
    if target.authorization_migrated_at is None:
        target.authorization_migrated_at = timezone.now()
        target.save(update_fields=["authorization_migrated_at", "updated_at"])
    _complete_quarantine_if_ready(target)
    target._prefetched_objects_cache = {}
    new_permissions = sorted(membership_permission_codes(target))
    record_audit_event(
        action=AuditAction.MEMBERSHIP_ROLE_ASSIGNED,
        entity_type="organizations.MembershipRoleAssignment",
        entity_id=assignment.pk,
        organization=organization,
        actor=actor,
        metadata={
            "target_membership_id": str(target.pk),
            "role": assigned_role.code,
            "approver_membership_id": str(approver.pk),
            "starts_at": start.isoformat(),
            "ends_at": ends_at.isoformat() if ends_at else None,
            "previous_permissions": previous_permissions,
            "new_permissions": new_permissions,
            "reason": reason.strip(),
        },
    )
    return assignment


@transaction.atomic
def revoke_membership_role(
    *,
    organization: Organization,
    actor: User,
    assignment_id: object,
    approver_membership_id: object,
    reason: str,
) -> MembershipRoleAssignment:
    if not reason.strip():
        raise ValidationError("دلیل لغو نقش الزامی است.")
    actor_membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.AUTHORIZATION_ROLES_REVOKE,
        message="اجازه لغو نقش ندارید.",
    )
    _lock_membership_authority(actor_membership)
    if not membership_has_permission(
        actor_membership, BusinessPermissionCode.AUTHORIZATION_ROLES_REVOKE
    ) or not membership_has_scope(actor_membership):
        raise PermissionDenied("اجازه لغو نقش ندارید.")
    try:
        assignment = (
            MembershipRoleAssignment.objects.select_for_update()
            .select_related("membership", "role")
            .get(pk=assignment_id, organization=organization)
        )
    except (ValueError, MembershipRoleAssignment.DoesNotExist) as exc:
        raise PermissionDenied("تخصیص نقش در این سازمان یافت نشد.") from exc
    if assignment.revoked_at:
        return assignment
    if assignment.membership_id == actor_membership.pk:
        raise PermissionDenied("لغو نقش خود یک عملیات حفاظت‌شده و ممنوع است.")
    approver = _independent_approver(
        organization=organization,
        actor_membership=actor_membership,
        target_membership=assignment.membership,
        approver_membership_id=approver_membership_id,
        permission=BusinessPermissionCode.AUTHORIZATION_ROLES_REVOKE,
    )
    if assignment.role.code == MembershipRole.TENANT_OWNER:
        now = timezone.now()
        other_owner_exists = (
            MembershipRoleAssignment.objects.select_for_update()
            .filter(
                organization=organization,
                role__code=MembershipRole.TENANT_OWNER,
                starts_at__lte=now,
                revoked_at__isnull=True,
            )
            .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
            .exclude(pk=assignment.pk)
            .exists()
        )
        if not other_owner_exists:
            raise ValidationError("سازمان باید حداقل یک Tenant Owner فعال داشته باشد.")
    previous_permissions = sorted(membership_permission_codes(assignment.membership))
    assignment.revoked_at = timezone.now()
    assignment.revoked_by = actor_membership
    assignment.revocation_reason = reason.strip()
    assignment.save(
        update_fields=["revoked_at", "revoked_by", "revocation_reason", "updated_at"]
    )
    assignment.membership._prefetched_objects_cache = {}
    new_permissions = sorted(membership_permission_codes(assignment.membership))
    record_audit_event(
        action=AuditAction.MEMBERSHIP_ROLE_REVOKED,
        entity_type="organizations.MembershipRoleAssignment",
        entity_id=assignment.pk,
        organization=organization,
        actor=actor,
        metadata={
            "target_membership_id": str(assignment.membership_id),
            "role": assignment.role.code,
            "approver_membership_id": str(approver.pk),
            "previous_permissions": previous_permissions,
            "new_permissions": new_permissions,
            "reason": reason.strip(),
        },
    )
    return assignment


def _scope_target(
    *,
    organization: Organization,
    scope_type: str,
    project: Any | None,
    site: Any | None,
) -> tuple[Any | None, Any | None]:
    if scope_type not in AuthorizationScopeType.values:
        raise ValidationError("نوع دامنه معتبر نیست.")
    if scope_type == AuthorizationScopeType.ORGANIZATION:
        if project is not None or site is not None:
            raise ValidationError("دامنه سازمانی پروژه یا کارگاه ندارد.")
        return None, None
    if project is None or project.organization_id != organization.pk:
        raise PermissionDenied("پروژه متعلق به این سازمان نیست.")
    if scope_type == AuthorizationScopeType.PROJECT:
        if site is not None:
            raise ValidationError("دامنه پروژه‌ای کارگاه اختصاصی ندارد.")
        return project, None
    if (
        site is None
        or site.organization_id != organization.pk
        or site.project_id != project.pk
    ):
        raise PermissionDenied("کارگاه متعلق به پروژه و سازمان انتخاب‌شده نیست.")
    return project, site


@transaction.atomic
def grant_membership_scope(
    *,
    organization: Organization,
    actor: User,
    membership_id: object,
    scope_type: str,
    approver_membership_id: object,
    reason: str,
    project: Any | None = None,
    site: Any | None = None,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
) -> MembershipScopeGrant:
    if not reason.strip():
        raise ValidationError("دلیل اعطای دامنه الزامی است.")
    actor_membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.AUTHORIZATION_GRANTS_CREATE,
        message="اجازه اعطای دامنه دسترسی ندارید.",
        allow_any_scope=True,
    )
    _lock_membership_authority(actor_membership)
    if not membership_has_permission(
        actor_membership, BusinessPermissionCode.AUTHORIZATION_GRANTS_CREATE
    ) or not membership_has_scope(actor_membership, allow_any_scope=True):
        raise PermissionDenied("اجازه اعطای دامنه دسترسی ندارید.")
    target = _active_membership_for_update(
        organization=organization, membership_id=membership_id
    )
    if target.pk == actor_membership.pk:
        raise PermissionDenied("اعطای دامنه به خود یک عملیات حفاظت‌شده و ممنوع است.")
    project, site = _scope_target(
        organization=organization, scope_type=scope_type, project=project, site=site
    )
    if not membership_has_scope(actor_membership, project=project, site=site):
        raise PermissionDenied("دامنه پیشنهادی خارج از اختیار عامل است.")
    approver = _independent_approver(
        organization=organization,
        actor_membership=actor_membership,
        target_membership=target,
        approver_membership_id=approver_membership_id,
        permission=BusinessPermissionCode.AUTHORIZATION_GRANTS_CREATE,
        allow_any_scope=True,
    )
    if not membership_has_scope(approver, project=project, site=site):
        raise PermissionDenied("دامنه پیشنهادی خارج از اختیار تأییدکننده است.")
    start = starts_at or timezone.now()
    _validate_interval(starts_at=start, ends_at=ends_at)
    duplicate = MembershipScopeGrant.objects.filter(
        membership=target,
        scope_type=scope_type,
        project=project,
        site=site,
        revoked_at__isnull=True,
    ).exists()
    if duplicate:
        raise ValidationError("این دامنه هنوز فعال یا زمان‌بندی‌شده است.")
    grant = MembershipScopeGrant.objects.create(
        organization=organization,
        membership=target,
        scope_type=scope_type,
        project=project,
        site=site,
        starts_at=start,
        ends_at=ends_at,
        granted_by=actor_membership,
        approved_by=approver,
        reason=reason.strip(),
    )
    if target.authorization_migrated_at is None:
        target.authorization_migrated_at = timezone.now()
        target.save(update_fields=["authorization_migrated_at", "updated_at"])
    _complete_quarantine_if_ready(target)
    record_audit_event(
        action=AuditAction.MEMBERSHIP_SCOPE_GRANTED,
        entity_type="organizations.MembershipScopeGrant",
        entity_id=grant.pk,
        organization=organization,
        actor=actor,
        metadata={
            "target_membership_id": str(target.pk),
            "scope_type": scope_type,
            "project_id": str(project.pk) if project else None,
            "site_id": str(site.pk) if site else None,
            "approver_membership_id": str(approver.pk),
            "starts_at": start.isoformat(),
            "ends_at": ends_at.isoformat() if ends_at else None,
            "reason": reason.strip(),
        },
    )
    return grant


@transaction.atomic
def revoke_membership_scope(
    *,
    organization: Organization,
    actor: User,
    grant_id: object,
    approver_membership_id: object,
    reason: str,
) -> MembershipScopeGrant:
    if not reason.strip():
        raise ValidationError("دلیل لغو دامنه الزامی است.")
    actor_membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.AUTHORIZATION_GRANTS_REVOKE,
        message="اجازه لغو دامنه دسترسی ندارید.",
        allow_any_scope=True,
    )
    _lock_membership_authority(actor_membership)
    if not membership_has_permission(
        actor_membership, BusinessPermissionCode.AUTHORIZATION_GRANTS_REVOKE
    ) or not membership_has_scope(actor_membership, allow_any_scope=True):
        raise PermissionDenied("اجازه لغو دامنه دسترسی ندارید.")
    try:
        grant = (
            MembershipScopeGrant.objects.select_for_update(of=("self",))
            .select_related("membership", "project", "site")
            .get(pk=grant_id, organization=organization)
        )
    except (ValueError, MembershipScopeGrant.DoesNotExist) as exc:
        raise PermissionDenied("دامنه دسترسی در این سازمان یافت نشد.") from exc
    if grant.revoked_at:
        return grant
    if grant.membership_id == actor_membership.pk:
        raise PermissionDenied("لغو دامنه خود یک عملیات حفاظت‌شده و ممنوع است.")
    approver = _independent_approver(
        organization=organization,
        actor_membership=actor_membership,
        target_membership=grant.membership,
        approver_membership_id=approver_membership_id,
        permission=BusinessPermissionCode.AUTHORIZATION_GRANTS_REVOKE,
        allow_any_scope=True,
    )
    if not membership_has_scope(
        actor_membership, project=grant.project, site=grant.site
    ) or not membership_has_scope(approver, project=grant.project, site=grant.site):
        raise PermissionDenied("دامنه لغوشده خارج از اختیار عامل یا تأییدکننده است.")
    grant.revoked_at = timezone.now()
    grant.revoked_by = actor_membership
    grant.revocation_reason = reason.strip()
    grant.save(
        update_fields=["revoked_at", "revoked_by", "revocation_reason", "updated_at"]
    )
    record_audit_event(
        action=AuditAction.MEMBERSHIP_SCOPE_REVOKED,
        entity_type="organizations.MembershipScopeGrant",
        entity_id=grant.pk,
        organization=organization,
        actor=actor,
        metadata={
            "target_membership_id": str(grant.membership_id),
            "scope_type": grant.scope_type,
            "project_id": str(grant.project_id) if grant.project_id else None,
            "site_id": str(grant.site_id) if grant.site_id else None,
            "approver_membership_id": str(approver.pk),
            "reason": reason.strip(),
        },
    )
    return grant


@transaction.atomic
def assign_platform_admin(
    *,
    actor: User,
    approver: User,
    target: User,
    reason: str,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
) -> PlatformRoleAssignment:
    """Assign platform control by an active Superuser, never tenant access."""

    if not reason.strip():
        raise ValidationError("دلیل تخصیص نقش پلتفرمی الزامی است.")
    if not actor.is_active or not actor.is_superuser:
        raise PermissionDenied("فقط Superuser می‌تواند نقش پلتفرمی تخصیص دهد.")
    if not approver.is_active or not approver.is_superuser:
        raise PermissionDenied("تأییدکننده نقش پلتفرمی باید Superuser فعال باشد.")
    if target.pk in (actor.pk, approver.pk):
        raise PermissionDenied("تخصیص یا تأیید نقش پلتفرمی خود ممنوع است.")
    if not target.is_active:
        raise ValidationError("نقش پلتفرمی فقط به کاربر فعال تخصیص می‌یابد.")
    start = starts_at or timezone.now()
    _validate_interval(starts_at=start, ends_at=ends_at)
    assignment = PlatformRoleAssignment.objects.create(
        user=target,
        role=PlatformRoleCode.PLATFORM_ADMIN,
        starts_at=start,
        ends_at=ends_at,
        assigned_by=actor,
        approved_by=approver,
        reason=reason.strip(),
    )
    record_audit_event(
        action=AuditAction.PLATFORM_ROLE_ASSIGNED,
        entity_type="organizations.PlatformRoleAssignment",
        entity_id=assignment.pk,
        actor=actor,
        metadata={
            "target_user_id": str(target.pk),
            "role": PlatformRoleCode.PLATFORM_ADMIN,
            "approver_user_id": str(approver.pk),
            "reason": reason.strip(),
        },
    )
    return assignment


@transaction.atomic
def revoke_platform_role(
    *,
    actor: User,
    approver: User,
    assignment_id: object,
    reason: str,
) -> PlatformRoleAssignment:
    if not reason.strip():
        raise ValidationError("دلیل لغو نقش پلتفرمی الزامی است.")
    if not actor.is_active or not actor.is_superuser:
        raise PermissionDenied("فقط Superuser می‌تواند نقش پلتفرمی را لغو کند.")
    if not approver.is_active or not approver.is_superuser or approver.pk == actor.pk:
        raise PermissionDenied("تأیید مستقل Superuser الزامی است.")
    try:
        assignment = PlatformRoleAssignment.objects.select_for_update().get(
            pk=assignment_id
        )
    except (ValueError, PlatformRoleAssignment.DoesNotExist) as exc:
        raise PermissionDenied("تخصیص نقش پلتفرمی یافت نشد.") from exc
    if assignment.revoked_at:
        return assignment
    if assignment.user_id in (actor.pk, approver.pk):
        raise PermissionDenied("لغو یا تأیید نقش پلتفرمی خود ممنوع است.")
    assignment.revoked_at = timezone.now()
    assignment.revoked_by = actor
    assignment.revocation_reason = reason.strip()
    assignment.save(
        update_fields=["revoked_at", "revoked_by", "revocation_reason", "updated_at"]
    )
    record_audit_event(
        action=AuditAction.PLATFORM_ROLE_REVOKED,
        entity_type="organizations.PlatformRoleAssignment",
        entity_id=assignment.pk,
        actor=actor,
        metadata={
            "target_user_id": str(assignment.user_id),
            "role": assignment.role,
            "approver_user_id": str(approver.pk),
            "reason": reason.strip(),
        },
    )
    return assignment


@transaction.atomic
def create_protected_operation_version(
    *,
    actor: User,
    code: str,
    name: str,
    description: str,
    reason: str,
) -> ProtectedOperation:
    """Append one classification version under Platform Admin ownership."""

    if code not in ProtectedOperationCode.values:
        raise ValidationError("کد عملیات حفاظت‌شده ثبت نشده است.")
    if not name.strip() or not description.strip() or not reason.strip():
        raise ValidationError("نام، شرح و دلیل طبقه‌بندی الزامی است.")
    if not is_platform_admin(actor):
        raise PermissionDenied("فقط Platform Admin می‌تواند طبقه‌بندی را تغییر دهد.")
    previous = (
        ProtectedOperation.objects.select_for_update()
        .filter(code=code)
        .order_by("-version")
        .first()
    )
    item = ProtectedOperation.objects.create(
        code=code,
        version=(previous.version + 1 if previous else 1),
        name=name.strip(),
        description=description.strip(),
        supersedes=previous,
        created_by=actor,
        reason=reason.strip(),
    )
    record_audit_event(
        action=AuditAction.PROTECTED_OPERATION_CLASSIFIED,
        entity_type="organizations.ProtectedOperation",
        entity_id=item.pk,
        actor=actor,
        metadata={
            "code": code,
            "version": item.version,
            "control_mode": "platform_admin_single_actor",
            "reason": reason.strip(),
        },
    )
    return item


@transaction.atomic
def retire_protected_operation(
    *, actor: User, code: str, reason: str
) -> ProtectedOperation:
    """Retire the current version without deleting its immutable audit history."""

    if code not in ProtectedOperationCode.values:
        raise ValidationError("کد عملیات حفاظت‌شده ثبت نشده است.")
    if not reason.strip():
        raise ValidationError("دلیل بازنشستگی الزامی است.")
    if not is_platform_admin(actor):
        raise PermissionDenied("فقط Platform Admin می‌تواند طبقه‌بندی را بازنشسته کند.")
    try:
        item = (
            ProtectedOperation.objects.select_for_update()
            .filter(code=code, retired_at__isnull=True)
            .order_by("-version")
            .first()
        )
    except ValueError as exc:
        raise ValidationError("کد عملیات حفاظت‌شده نامعتبر است.") from exc
    if item is None:
        raise ValidationError("نسخه فعالی برای بازنشستگی یافت نشد.")
    retired_at = timezone.now()
    ProtectedOperation.objects.filter(pk=item.pk).update(
        retired_at=retired_at,
        retired_by=actor,
        retirement_reason=reason.strip(),
        updated_at=retired_at,
    )
    item.refresh_from_db()
    record_audit_event(
        action=AuditAction.PROTECTED_OPERATION_RETIRED,
        entity_type="organizations.ProtectedOperation",
        entity_id=item.pk,
        actor=actor,
        metadata={
            "code": code,
            "version": item.version,
            "control_mode": "platform_admin_single_actor",
            "reason": reason.strip(),
        },
    )
    return item


@transaction.atomic
def prepare_membership_authorization_rollback(
    *, organization: Organization, actor: User, membership_id: object, reason: str
) -> OrganizationMembership:
    """Restore the compatibility role read while retaining explicit scope restrictions."""

    if not reason.strip():
        raise ValidationError("دلیل بازگشت مجوزدهی الزامی است.")
    actor_membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.AUTHORIZATION_ROLES_ASSIGN,
        message="اجازه آماده‌سازی بازگشت مجوزدهی ندارید.",
    )
    target = _active_membership_for_update(
        organization=organization, membership_id=membership_id
    )
    assignments = effective_role_assignments(target).order_by(
        "-role__is_owner", "starts_at", "pk"
    )
    selected = assignments.first()
    if selected is None:
        raise ValidationError("نقش فعالی برای بازگشت سازگار وجود ندارد.")
    target.role_definition = selected.role
    target.role = selected.role.code
    # authorization_migrated_at intentionally remains set: rollback never restores
    # broad scope after an explicit restriction was applied.
    target.save(update_fields=["role", "role_definition", "updated_at"])
    record_audit_event(
        action=AuditAction.AUTHORIZATION_MIGRATION_ROLLED_BACK,
        entity_type="organizations.OrganizationMembership",
        entity_id=target.pk,
        organization=organization,
        actor=actor,
        metadata={
            "compatibility_role": selected.role.code,
            "scope_restrictions_retained": True,
            "actor_membership_id": str(actor_membership.pk),
            "reason": reason.strip(),
        },
    )
    return target
