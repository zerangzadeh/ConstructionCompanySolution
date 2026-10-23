"""Bounded Platform Initial Grant; ordinary Tenant delegation stays unchanged."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.access_services import (
    _active_membership_for_update,
    _complete_quarantine_if_ready,
    _role,
    _scope_target,
)
from apps.organizations.authorization import (
    effective_scope_grants,
    is_platform_admin,
    membership_has_permission,
    membership_has_scope,
    membership_permission_codes,
)
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermissionCode,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    PlatformRoleAssignment,
    PlatformRoleCode,
)
from apps.organizations.permission_registry import registered_permission_codes
from apps.projects.models import Project, ProjectSite

INITIAL_GRANT_SOURCE = "platform_initial_grant"


def lock_platform_admin(actor: User) -> User:
    """Re-read identity and lock its current Platform Admin authority in a tx."""
    if not actor.is_authenticated or actor._state.adding:
        raise PermissionDenied("Active Platform Admin authority is required.")
    actor = User.objects.select_for_update().get(pk=actor.pk)
    now = timezone.now()
    duties = list(
        PlatformRoleAssignment.objects.select_for_update()
        .filter(
            user=actor,
            role=PlatformRoleCode.PLATFORM_ADMIN,
            starts_at__lte=now,
            revoked_at__isnull=True,
        )
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
    )
    if not duties or not is_platform_admin(actor):
        raise PermissionDenied("Active Platform Admin authority is required.")
    return actor


def _lawful_delegator_exists(
    *,
    organization: Organization,
    target: OrganizationMembership,
    permission_codes: set[str],
) -> bool:
    """Mirror assign_membership_role's actor/subset/independent-approver checks.

    Lock effective authority before deciding absence. A missing holder alone is
    not the test: both an authorized delegator and an independent approver must
    exist. The receiver cannot be either actor in ordinary delegation.
    """
    members = list(
        OrganizationMembership.objects.select_for_update(of=("self",))
        .select_related("role_definition")
        .filter(
            organization=organization,
            status=MembershipStatus.ACTIVE,
            user__is_active=True,
        )
        .exclude(pk=target.pk)
        .order_by("pk")
    )
    list(
        MembershipRoleAssignment.objects.select_for_update()
        .filter(organization=organization, revoked_at__isnull=True)
        .order_by("pk")
    )
    list(
        MembershipScopeGrant.objects.select_for_update()
        .filter(organization=organization, revoked_at__isnull=True)
        .order_by("pk")
    )
    role_ids = set(
        MembershipRoleAssignment.objects.filter(
            organization=organization, revoked_at__isnull=True
        ).values_list("role_id", flat=True)
    ) | {m.role_definition_id for m in members if m.role_definition_id}
    roles = list(
        OrganizationRole.objects.select_for_update()
        .filter(pk__in=role_ids)
        .order_by("pk")
    )
    for candidate_role in roles:
        list(candidate_role.permissions.select_for_update().order_by("pk"))
    authorized = [
        m
        for m in members
        if membership_has_permission(
            m, BusinessPermissionCode.AUTHORIZATION_ROLES_ASSIGN
        )
        and membership_has_scope(m)
    ]
    return len(authorized) >= 2 and any(
        permission_codes.issubset(membership_permission_codes(m)) for m in authorized
    )


@transaction.atomic
def platform_initial_grant(
    *,
    organization: Organization,
    actor: User,
    membership_id: object,
    role: OrganizationRole | str,
    scope_type: str,
    reason: str,
    project: Project | None = None,
    site: ProjectSite | None = None,
) -> tuple[MembershipRoleAssignment, MembershipScopeGrant]:
    """Grant an existing role plus explicit scope when no lawful delegator exists.

    Requires a separately assigned Platform Admin; superuser/staff status is not
    sufficient. No tenant membership is created for the actor. Existing union-of-
    roles/scope semantics apply, so broader or unrelated receiver scopes fail
    closed instead of silently expanding the supplied grant scope.
    """
    if not reason.strip():
        raise ValidationError("An Initial Grant reason is required.")
    actor = lock_platform_admin(actor)
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    if not organization.is_active:
        raise PermissionDenied("Initial Grant requires an active Tenant.")
    target = _active_membership_for_update(
        organization=organization, membership_id=membership_id
    )
    if target.user_id == actor.pk:
        raise PermissionDenied("Platform Admin cannot Initial Grant to itself.")
    if not User.objects.select_for_update().get(pk=target.user_id).is_active:
        raise PermissionDenied("Initial Grant requires an active receiver identity.")
    resolved = _role(role, organization=organization)
    resolved = OrganizationRole.objects.select_for_update().get(pk=resolved.pk)
    # Revalidate even when the caller passed a stale model instance.
    resolved = _role(resolved, organization=organization)
    permissions = list(resolved.permissions.select_for_update().order_by("code"))
    if not permissions or any(not p.is_active for p in permissions):
        raise ValidationError("An active, nonempty approved role is required.")
    permission_codes = {p.code for p in permissions}
    if not permission_codes.issubset(registered_permission_codes()):
        raise ValidationError(
            "Every permission must belong to the registered catalogue."
        )
    try:
        if project is not None:
            project = Project.objects.select_for_update().get(
                pk=project.pk, organization=organization
            )
        if site is not None:
            site = ProjectSite.objects.select_for_update().get(
                pk=site.pk, organization=organization
            )
    except (Project.DoesNotExist, ProjectSite.DoesNotExist) as exc:
        raise PermissionDenied("Scope target does not belong to this Tenant.") from exc
    project, site = _scope_target(
        organization=organization, scope_type=scope_type, project=project, site=site
    )
    now = timezone.now()
    pending_scopes = list(
        target.scope_grants.select_for_update()
        .filter(revoked_at__isnull=True)
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
    )
    for grant in pending_scopes:
        contained = scope_type == AuthorizationScopeType.ORGANIZATION or (
            grant.project_id == project.pk
            and grant.scope_type != AuthorizationScopeType.ORGANIZATION
            and (
                scope_type == AuthorizationScopeType.PROJECT
                or (
                    grant.scope_type == AuthorizationScopeType.SITE
                    and grant.site_id == site.pk
                )
            )
        )
        if not contained:
            raise PermissionDenied(
                "Existing receiver scopes exceed the explicit scope."
            )
    if MembershipRoleAssignment.objects.filter(
        membership=target, role=resolved, revoked_at__isnull=True
    ).exists():
        raise ValidationError("This role is already assigned or scheduled.")
    if _lawful_delegator_exists(
        organization=organization, target=target, permission_codes=permission_codes
    ):
        raise PermissionDenied("A lawful Tenant delegation path exists; use it.")
    previous_permissions = sorted(membership_permission_codes(target))
    previous_scopes = list(effective_scope_grants(target).values_list("pk", flat=True))
    assignment = MembershipRoleAssignment.objects.create(
        organization=organization,
        membership=target,
        role=resolved,
        starts_at=now,
        reason=reason.strip(),
        source=INITIAL_GRANT_SOURCE,
    )
    # Reuse an identical indefinite scope; never silently edit an existing grant.
    grant = next(
        (
            g
            for g in pending_scopes
            if g.scope_type == scope_type
            and g.project_id == (project.pk if project else None)
            and g.site_id == (site.pk if site else None)
            and g.starts_at <= now
            and g.ends_at is None
        ),
        None,
    )
    scope_created = grant is None
    if grant is None:
        grant = MembershipScopeGrant.objects.create(
            organization=organization,
            membership=target,
            scope_type=scope_type,
            project=project,
            site=site,
            starts_at=now,
            reason=reason.strip(),
            source=INITIAL_GRANT_SOURCE,
        )
    target.authorization_migrated_at = now
    target.save(update_fields=["authorization_migrated_at", "updated_at"])
    _complete_quarantine_if_ready(target)
    target._prefetched_objects_cache = {}
    metadata: dict[str, Any] = {
        "source": INITIAL_GRANT_SOURCE,
        "target_membership_id": str(target.pk),
        "target_user_id": str(target.user_id),
        "role_id": str(resolved.pk),
        "role": resolved.code,
        "role_permissions": sorted(permission_codes),
        "scope_grant_id": str(grant.pk),
        "scope_created": scope_created,
        "scope_type": scope_type,
        "project_id": str(project.pk) if project else None,
        "site_id": str(site.pk) if site else None,
        "starts_at": now.isoformat(),
        "ends_at": None,
        "previous_permissions": previous_permissions,
        "new_permissions": sorted(membership_permission_codes(target)),
        "previous_scope_ids": [str(pk) for pk in previous_scopes],
        "new_scope_ids": [
            str(pk)
            for pk in effective_scope_grants(target).values_list("pk", flat=True)
        ],
        "lawful_tenant_delegator_exists": False,
        "reason": reason.strip(),
    }
    correlation_id = uuid4()
    record_audit_event(
        action=AuditAction.MEMBERSHIP_ROLE_ASSIGNED,
        entity_type="organizations.MembershipRoleAssignment",
        entity_id=assignment.pk,
        organization=organization,
        actor=actor,
        allow_platform_actor=True,
        correlation_id=correlation_id,
        metadata=metadata,
    )
    if scope_created:
        record_audit_event(
            action=AuditAction.MEMBERSHIP_SCOPE_GRANTED,
            entity_type="organizations.MembershipScopeGrant",
            entity_id=grant.pk,
            organization=organization,
            actor=actor,
            allow_platform_actor=True,
            correlation_id=correlation_id,
            metadata=metadata,
        )
    return assignment, grant
