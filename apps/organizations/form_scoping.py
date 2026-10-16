from __future__ import annotations

import uuid
from typing import Any

from django.db.models import QuerySet

from apps.organizations.authorization import scope_queryset
from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.models import Project


def normalized_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def scoped_projects_for_form(
    *, organization: Organization, membership: OrganizationMembership
) -> QuerySet[Project]:
    """Authorized Project choices; UI context does not add any grant."""

    return scope_queryset(
        Project.objects.filter(
            organization=organization,
            deleted_at__isnull=True,
        ),
        membership=membership,
        project_lookup="pk",
        include_site_parent=True,
    ).order_by("name")


def scope_project_related_choices(
    queryset: QuerySet[Any],
    *,
    membership: OrganizationMembership,
    project_lookup: str,
    project: Project | None,
    site_lookup: str | None = None,
) -> QuerySet[Any]:
    """Intersect dependent choices with Tenant/object scope and selected parent."""

    queryset = scope_queryset(
        queryset,
        membership=membership,
        project_lookup=project_lookup,
        site_lookup=site_lookup,
    )
    if project is None:
        return queryset.none()
    return queryset.filter(**{project_lookup: project.pk})


def selected_form_project(
    *,
    data: Any,
    field_name: str,
    projects: QuerySet[Project],
    active_project: Project | None,
) -> Project | None:
    """Resolve a bound parent safely, falling back to persisted valid context."""

    selected_id = normalized_uuid(data.get(field_name)) if data else None
    if selected_id is not None:
        return projects.filter(pk=selected_id).first()
    if active_project is not None:
        return projects.filter(pk=active_project.pk).first()
    return None
