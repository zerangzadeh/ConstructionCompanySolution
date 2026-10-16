from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import PermissionDenied

from apps.organizations.authorization import (
    get_active_membership,
    membership_permission_codes,
    permission_supports_object_scope,
    scope_queryset,
)
from apps.organizations.models import Organization
from apps.projects.models import Project, ProjectSite

ACTIVE_PROJECT_SESSION_KEY = "active_project_id"
ACTIVE_SITE_SESSION_KEY = "active_site_id"


@dataclass(frozen=True)
class EffectiveContext:
    project: Project | None
    site: ProjectSite | None


def scoped_context_projects(*, user: Any, organization: Organization):
    """Return Projects that are inside the member's effective object grants."""

    membership = get_active_membership(user=user, organization=organization)
    if not any(
        permission_supports_object_scope(code)
        for code in membership_permission_codes(membership)
    ):
        return Project.objects.none()
    return (
        scope_queryset(
            Project.objects.filter(
                organization=organization,
                deleted_at__isnull=True,
            ),
            membership=membership,
            project_lookup="pk",
            include_site_parent=True,
        )
        .only("id", "organization_id", "code", "name")
        .order_by("name")
    )


def scoped_context_sites(*, user: Any, organization: Organization, project: Project):
    """Return active Sites the member may use beneath one authorized Project."""

    membership = get_active_membership(user=user, organization=organization)
    return (
        scope_queryset(
            ProjectSite.objects.filter(
                organization=organization,
                project=project,
                is_active=True,
            ),
            membership=membership,
            project_lookup="project_id",
            site_lookup="pk",
        )
        .only("id", "organization_id", "project_id", "code", "name")
        .order_by("name")
    )


def clear_effective_context(session: MutableMapping[str, Any]) -> None:
    session.pop(ACTIVE_PROJECT_SESSION_KEY, None)
    session.pop(ACTIVE_SITE_SESSION_KEY, None)


def resolve_session_context(
    *, user: Any, organization: Organization, session: MutableMapping[str, Any]
) -> EffectiveContext:
    """Resolve session context against current Tenant membership and object scope."""

    project_id = session.get(ACTIVE_PROJECT_SESSION_KEY)
    if not project_id:
        session.pop(ACTIVE_SITE_SESSION_KEY, None)
        return EffectiveContext(project=None, site=None)

    try:
        project = scoped_context_projects(user=user, organization=organization).get(
            pk=project_id
        )
    except (Project.DoesNotExist, ValueError, TypeError, PermissionDenied):
        clear_effective_context(session)
        return EffectiveContext(project=None, site=None)

    site_id = session.get(ACTIVE_SITE_SESSION_KEY)
    if not site_id:
        return EffectiveContext(project=project, site=None)
    try:
        site = scoped_context_sites(
            user=user,
            organization=organization,
            project=project,
        ).get(pk=site_id)
    except (ProjectSite.DoesNotExist, ValueError, TypeError, PermissionDenied):
        session.pop(ACTIVE_SITE_SESSION_KEY, None)
        site = None
    return EffectiveContext(project=project, site=site)


def set_effective_context(
    *,
    user: Any,
    organization: Organization,
    session: MutableMapping[str, Any],
    project_id: str | None,
    site_id: str | None,
) -> EffectiveContext:
    """Persist only a currently authorized Project/Site pair."""

    if not project_id:
        clear_effective_context(session)
        return EffectiveContext(project=None, site=None)

    try:
        project = scoped_context_projects(user=user, organization=organization).get(
            pk=project_id
        )
    except (Project.DoesNotExist, ValueError, TypeError) as exc:
        raise PermissionDenied("پروژه انتخاب‌شده در دامنه مجاز شما نیست.") from exc

    site = None
    if site_id:
        try:
            site = scoped_context_sites(
                user=user,
                organization=organization,
                project=project,
            ).get(pk=site_id)
        except (ProjectSite.DoesNotExist, ValueError, TypeError) as exc:
            raise PermissionDenied(
                "کارگاه انتخاب‌شده در دامنه مجاز پروژه نیست."
            ) from exc

    session[ACTIVE_PROJECT_SESSION_KEY] = str(project.pk)
    if site is None:
        session.pop(ACTIVE_SITE_SESSION_KEY, None)
    else:
        session[ACTIVE_SITE_SESSION_KEY] = str(site.pk)
    return EffectiveContext(project=project, site=site)
