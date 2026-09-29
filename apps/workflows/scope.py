from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db.models import Q, QuerySet

from apps.organizations.authorization import (
    effective_scope_grants,
    membership_has_scope,
)
from apps.organizations.models import (
    AuthorizationScopeType,
    OrganizationMembership,
)
from apps.projects.models import Project, ProjectSite

from .models import WorkflowInstance


def workflow_scope_objects(
    instance: WorkflowInstance,
) -> tuple[Project | None, ProjectSite | None]:
    """Resolve registered project/site context without trusting cross-tenant ids."""

    project_id = instance.subject_context.get("project_id")
    site_id = instance.subject_context.get("site_id")
    project = None
    site = None
    if project_id:
        try:
            project = Project.objects.filter(
                pk=project_id,
                organization_id=instance.organization_id,
                deleted_at__isnull=True,
            ).first()
        except (ValueError, ValidationError):
            project = None
    if site_id:
        try:
            site = (
                ProjectSite.objects.select_related("project")
                .filter(
                    pk=site_id,
                    organization_id=instance.organization_id,
                    project_id=project_id,
                    is_active=True,
                )
                .first()
            )
        except (ValueError, ValidationError):
            site = None
        if site is not None:
            project = site.project
    return project, site


def membership_has_workflow_scope(
    *,
    membership: OrganizationMembership,
    instance: WorkflowInstance,
    resolved_scope: tuple[Project | None, ProjectSite | None] | None = None,
) -> bool:
    project, site = resolved_scope or workflow_scope_objects(instance)
    if instance.subject_context.get("site_id") and site is None:
        return False
    if instance.subject_context.get("project_id") and project is None:
        return False
    return membership_has_scope(membership, project=project, site=site)


def delegation_scope_is_bounded(
    *, scope: dict[str, Any], instance: WorkflowInstance
) -> bool:
    """Require a delegation to state project/site bounds when the subject has them."""

    for key in ("project_id", "site_id"):
        value = instance.subject_context.get(key)
        if value is not None and str(scope.get(key, "")) != str(value):
            return False
    return True


def scope_work_item_queryset(
    queryset: QuerySet[Any], *, membership: OrganizationMembership
) -> QuerySet[Any]:
    grants = effective_scope_grants(membership)
    if membership.authorization_migrated_at is None and not grants.exists():
        return queryset
    if grants.filter(scope_type=AuthorizationScopeType.ORGANIZATION).exists():
        return queryset
    project_ids = [
        str(value)
        for value in grants.filter(
            scope_type=AuthorizationScopeType.PROJECT
        ).values_list("project_id", flat=True)
    ]
    site_pairs = [
        (str(project_id), str(site_id))
        for project_id, site_id in grants.filter(
            scope_type=AuthorizationScopeType.SITE
        ).values_list("project_id", "site_id")
    ]
    condition = Q(instance__subject_context__project_id__in=project_ids)
    for project_id, site_id in site_pairs:
        condition |= Q(
            instance__subject_context__project_id=project_id,
            instance__subject_context__site_id=site_id,
        )
    return queryset.filter(condition)
