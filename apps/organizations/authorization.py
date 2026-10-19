from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermissionCode,
    MembershipRole,
    MembershipScopeGrant,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    PlatformRoleAssignment,
    PlatformRoleCode,
)

MINIMAL_SITE_PARENT_FIELDS = (
    "id",
    "organization_id",
    "code",
    "name",
    "status",
)

OBJECT_SCOPED_PERMISSION_NAMESPACES = frozenset(
    {
        "projects",
        "project_sites",
        "project_phases",
        "project_controls",
        "project_cost",
        "wbs_nodes",
        "activities",
        "contracts",
        "contract_items",
        "contract_amendments",
        "baselines",
        "progress",
        "claims",
        "claim_settlements",
        "payable_measurements",
        "payable_certificates",
        "guarantees",
        "compliance_evidence",
        "retention_releases",
        "estimates",
        "estimate_items",
        "expenses",
        "documents",
        "daily_reports",
        "project_assignments",
        "workforce_skills",
        "workforce_qualifications",
        "workforce_performance",
        "workforce_labor_rates",
        "attendance",
        "leave_mission",
        "overtime",
        "timesheets",
        "payroll_results",
        "payslips",
        "payroll_inquiries",
        "payroll_ess",
        "purchase_requests",
        "purchase_request_items",
        "purchase_orders",
        "purchase_order_items",
        "goods_receipts",
        "goods_receipt_items",
        "warehouses",
        "stock_transactions",
        "stock_balances",
        "equipment_assignments",
        "maintenance_records",
        "safety_incidents",
        "quality_issues",
        "work_items",
        "rfqs",
        "tender_bids",
        "supplier_portal",
        "supplier_invoices",
        "invoice_matches",
        "reporting",
    }
)


def permission_supports_object_scope(permission: str | BusinessPermissionCode) -> bool:
    return str(permission).partition(".")[0] in OBJECT_SCOPED_PERMISSION_NAMESPACES


def _validate_access_context(*, user: User, organization: Organization) -> None:
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied("ورود با حساب کاربری فعال الزامی است.")
    if not organization.is_active:
        raise PermissionDenied("شرکت فعال نیست.")


def get_active_membership(
    *, user: User, organization: Organization
) -> OrganizationMembership:
    """Return the active membership; platform privilege is never a tenant bypass."""

    _validate_access_context(user=user, organization=organization)
    try:
        return (
            OrganizationMembership.objects.select_related("role_definition")
            .prefetch_related("role_assignments__role", "scope_grants")
            .get(
                user=user,
                organization=organization,
                status=MembershipStatus.ACTIVE,
            )
        )
    except OrganizationMembership.DoesNotExist as exc:
        raise PermissionDenied("به این شرکت دسترسی ندارید.") from exc


def is_platform_admin(user: User) -> bool:
    """Return platform-control authority without implying tenant-data authority."""

    if not user.is_authenticated or not user.is_active:
        return False
    now = timezone.now()
    return (
        PlatformRoleAssignment.objects.filter(
            user=user,
            role=PlatformRoleCode.PLATFORM_ADMIN,
            starts_at__lte=now,
            revoked_at__isnull=True,
        )
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
        .exists()
    )


def has_platform_role(user: User, role: str) -> bool:
    """Check one active platform duty without implying Tenant-data access."""

    if role not in PlatformRoleCode.values:
        return False
    if not user.is_authenticated or not user.is_active:
        return False
    now = timezone.now()
    return (
        PlatformRoleAssignment.objects.filter(
            user=user,
            role=role,
            starts_at__lte=now,
            revoked_at__isnull=True,
        )
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
        .exists()
    )


def is_platform_actor(user: User) -> bool:
    """Return whether an active user holds any current platform duty."""

    if not user.is_authenticated or not user.is_active:
        return False
    now = timezone.now()
    return (
        PlatformRoleAssignment.objects.filter(
            user=user,
            starts_at__lte=now,
            revoked_at__isnull=True,
        )
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
        .exists()
    )


def effective_role_assignments(membership: OrganizationMembership) -> QuerySet[Any]:
    now = timezone.now()
    return membership.role_assignments.filter(
        starts_at__lte=now,
        revoked_at__isnull=True,
        role__is_active=True,
    ).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))


def _prefetched_effective_roles(
    membership: OrganizationMembership,
) -> list[Any] | None:
    cache = getattr(membership, "_prefetched_objects_cache", {})
    if "role_assignments" not in cache:
        return None
    now = timezone.now()
    return [
        assignment
        for assignment in cache["role_assignments"]
        if assignment.revoked_at is None
        and assignment.starts_at <= now
        and (assignment.ends_at is None or assignment.ends_at > now)
        and assignment.role.is_active
    ]


def membership_permission_codes(membership: OrganizationMembership) -> frozenset[str]:
    """Union permissions from every active applicable membership role."""

    if membership.status != MembershipStatus.ACTIVE:
        return frozenset()
    prefetched = _prefetched_effective_roles(membership)
    cache = getattr(membership, "_prefetched_objects_cache", {})
    has_assignments = (
        bool(cache["role_assignments"])
        if "role_assignments" in cache
        else membership.role_assignments.exists()
    )
    if has_assignments:
        if prefetched is not None:
            return frozenset(
                permission.code
                for assignment in prefetched
                for permission in assignment.role.permissions.all()
                if permission.is_active
            )
        assignments = effective_role_assignments(membership)
        return frozenset(
            assignments.filter(role__permissions__is_active=True).values_list(
                "role__permissions__code", flat=True
            )
        )
    # Reversible read compatibility for rows not yet switched by the migration.
    if membership.authorization_migrated_at is not None:
        return frozenset()
    role = membership.role_definition
    if role is None or not role.is_active:
        return frozenset()
    return frozenset(
        role.permissions.filter(is_active=True).values_list("code", flat=True)
    )


def membership_has_permission(
    membership: OrganizationMembership,
    permission: str | BusinessPermissionCode,
) -> bool:
    return str(permission) in membership_permission_codes(membership)


def membership_is_tenant_owner(membership: OrganizationMembership) -> bool:
    if membership.status != MembershipStatus.ACTIVE:
        return False
    if membership.role_assignments.exists():
        return (
            effective_role_assignments(membership)
            .filter(role__code=MembershipRole.TENANT_OWNER)
            .exists()
        )
    return bool(
        membership.role_definition_id
        and membership.role_definition.is_active
        and membership.role_definition.is_owner
    )


def membership_has_role(membership: OrganizationMembership, role_code: str) -> bool:
    """Check one effective role while honoring prefetched routing data."""

    if membership.status != MembershipStatus.ACTIVE:
        return False
    prefetched = _prefetched_effective_roles(membership)
    if prefetched is not None:
        if getattr(membership, "_prefetched_objects_cache", {}).get("role_assignments"):
            return any(item.role.code == role_code for item in prefetched)
    elif membership.role_assignments.exists():
        return (
            effective_role_assignments(membership).filter(role__code=role_code).exists()
        )
    return bool(
        membership.authorization_migrated_at is None
        and membership.role_definition_id
        and membership.role_definition.is_active
        and membership.role_definition.code == role_code
    )


def effective_scope_grants(
    membership: OrganizationMembership,
) -> QuerySet[MembershipScopeGrant]:
    now = timezone.now()
    return membership.scope_grants.filter(
        organization_id=membership.organization_id,
        starts_at__lte=now,
        revoked_at__isnull=True,
    ).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))


def _prefetched_effective_scopes(
    membership: OrganizationMembership,
) -> list[MembershipScopeGrant] | None:
    cache = getattr(membership, "_prefetched_objects_cache", {})
    if "scope_grants" not in cache:
        return None
    now = timezone.now()
    return [
        grant
        for grant in cache["scope_grants"]
        if grant.organization_id == membership.organization_id
        and grant.revoked_at is None
        and grant.starts_at <= now
        and (grant.ends_at is None or grant.ends_at > now)
    ]


def membership_has_scope(
    membership: OrganizationMembership,
    *,
    project: Any | None = None,
    site: Any | None = None,
    allow_any_scope: bool = False,
    allow_site_parent: bool = False,
) -> bool:
    """Intersect explicit organization/project/site grants with the object."""

    if membership.status != MembershipStatus.ACTIVE:
        return False
    if project is not None and project.organization_id != membership.organization_id:
        return False
    if site is not None:
        if site.organization_id != membership.organization_id:
            return False
        if project is not None and site.project_id != project.pk:
            return False
        project = site.project

    prefetched = _prefetched_effective_scopes(membership)
    if prefetched is not None:
        if allow_any_scope:
            return bool(prefetched)
        if project is None and site is None:
            return any(
                grant.scope_type == AuthorizationScopeType.ORGANIZATION
                for grant in prefetched
            )
        return any(
            grant.scope_type == AuthorizationScopeType.ORGANIZATION
            or (
                grant.scope_type == AuthorizationScopeType.PROJECT
                and grant.project_id == project.pk
            )
            or (
                site is not None
                and grant.scope_type == AuthorizationScopeType.SITE
                and grant.project_id == project.pk
                and grant.site_id == site.pk
            )
            or (
                site is None
                and allow_site_parent
                and grant.scope_type == AuthorizationScopeType.SITE
                and grant.project_id == project.pk
            )
            for grant in prefetched
        )
    grants = effective_scope_grants(membership)
    if allow_any_scope:
        return grants.exists()
    if project is None and site is None:
        return grants.filter(scope_type=AuthorizationScopeType.ORGANIZATION).exists()
    query = Q(scope_type=AuthorizationScopeType.ORGANIZATION) | Q(
        scope_type=AuthorizationScopeType.PROJECT,
        project_id=project.pk,
    )
    if site is not None:
        query |= Q(
            scope_type=AuthorizationScopeType.SITE,
            project_id=project.pk,
            site_id=site.pk,
        )
    elif allow_site_parent:
        query |= Q(
            scope_type=AuthorizationScopeType.SITE,
            project_id=project.pk,
        )
    return grants.filter(query).exists()


def has_business_permission(
    *,
    user: User,
    organization: Organization,
    permission: str | BusinessPermissionCode,
    project: Any | None = None,
    site: Any | None = None,
    allow_any_scope: bool = False,
    allow_site_parent: bool = False,
) -> bool:
    """Check active membership, role-union permission, and explicit object scope."""

    try:
        membership = get_active_membership(user=user, organization=organization)
    except PermissionDenied:
        return False
    return membership_has_permission(membership, permission) and membership_has_scope(
        membership,
        project=project,
        site=site,
        allow_any_scope=allow_any_scope,
        allow_site_parent=allow_site_parent,
    )


def require_business_permission(
    *,
    user: User,
    organization: Organization,
    permission: str | BusinessPermissionCode,
    message: str,
    project: Any | None = None,
    site: Any | None = None,
    allow_any_scope: bool = False,
    allow_site_parent: bool = False,
) -> OrganizationMembership:
    """Deny by default and return the checked membership for scoped workflows."""

    membership = get_active_membership(user=user, organization=organization)
    if not membership_has_permission(
        membership, permission
    ) or not membership_has_scope(
        membership,
        project=project,
        site=site,
        allow_any_scope=allow_any_scope,
        allow_site_parent=allow_site_parent,
    ):
        raise PermissionDenied(message)
    return membership


def scope_queryset(
    queryset: QuerySet[Any],
    *,
    membership: OrganizationMembership,
    project_lookup: str,
    site_lookup: str | None = None,
    include_site_parent: bool = False,
) -> QuerySet[Any]:
    """Intersect a queryset with the tenant and currently effective grants."""

    if (
        membership.status != MembershipStatus.ACTIVE
        or not membership.organization.is_active
        or not membership.user.is_active
    ):
        return queryset.none()
    queryset = queryset.filter(organization_id=membership.organization_id)
    grants = effective_scope_grants(membership)
    if grants.filter(scope_type=AuthorizationScopeType.ORGANIZATION).exists():
        return queryset
    project_ids = grants.filter(scope_type=AuthorizationScopeType.PROJECT).values_list(
        "project_id", flat=True
    )
    condition = Q(**{f"{project_lookup}__in": project_ids})
    if site_lookup:
        site_ids = grants.filter(scope_type=AuthorizationScopeType.SITE).values_list(
            "site_id", flat=True
        )
        condition |= Q(**{f"{site_lookup}__in": site_ids})
    elif include_site_parent:
        parent_project_ids = grants.filter(
            scope_type=AuthorizationScopeType.SITE
        ).values_list("project_id", flat=True)
        condition |= Q(**{f"{project_lookup}__in": parent_project_ids})
    return queryset.filter(condition).distinct()


def memberships_with_permission(
    *, organization: Organization, permission: str | BusinessPermissionCode
) -> Iterable[OrganizationMembership]:
    """Resolve multi-role candidates without treating positions as grants."""

    memberships = OrganizationMembership.objects.filter(
        organization=organization,
        status=MembershipStatus.ACTIVE,
        user__is_active=True,
    ).prefetch_related(
        "role_assignments__role__permissions", "role_definition__permissions"
    )
    return [
        membership
        for membership in memberships
        if membership_has_permission(membership, permission)
    ]
