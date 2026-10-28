"""Bounded, authorization-safe global search read model for CEP-019."""

from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.urls import reverse

from apps.accounts.models import User
from apps.materials.services import search_organization_materials
from apps.organizations.authorization import has_business_permission
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.projects.services import get_organization_projects
from core.product_surface import route_exposed

MINIMUM_QUERY_LENGTH = 2
MAXIMUM_QUERY_LENGTH = 100
RESULT_LIMIT_PER_FAMILY = 10


@dataclass(frozen=True, slots=True)
class SearchResult:
    """A safe display projection, never a source-domain authority."""

    family: str
    family_label: str
    title: str
    reference: str
    url: str


@dataclass(frozen=True, slots=True)
class SearchResponse:
    query: str
    results: tuple[SearchResult, ...]
    validation_message: str


def _normalized_query(value: str) -> tuple[str, str]:
    query = value.strip()
    if not query:
        return "", ""
    if len(query) < MINIMUM_QUERY_LENGTH:
        return "", "برای جستجو دست‌کم دو نویسه وارد کنید."
    if len(query) > MAXIMUM_QUERY_LENGTH:
        return "", "عبارت جستجو بیش از حد طولانی است."
    return query, ""


def search_active_organization(
    *, actor: User, organization: Organization, query: str
) -> SearchResponse:
    """Search only the explicit safe-family allowlist under existing source guards."""

    normalized, validation_message = _normalized_query(query)
    if not normalized:
        return SearchResponse(
            query=query.strip()[:MAXIMUM_QUERY_LENGTH],
            results=(),
            validation_message=validation_message,
        )

    results: list[SearchResult] = []
    if has_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.PROJECTS_VIEW,
        allow_any_scope=True,
    ) and route_exposed("projects:detail"):
        projects = get_organization_projects(user=actor, organization=organization)
        projects = projects.filter(code__icontains=normalized) | projects.filter(
            name__icontains=normalized
        )
        for project in projects.distinct().order_by("name", "pk")[
            :RESULT_LIMIT_PER_FAMILY
        ]:
            results.append(
                SearchResult(
                    family="project",
                    family_label="پروژه",
                    title=project.name,
                    reference=project.code,
                    url=reverse("projects:detail", args=[project.pk]),
                )
            )

    if has_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.MATERIALS_VIEW,
    ) and route_exposed("materials:material_detail"):
        try:
            materials = search_organization_materials(
                user=actor, organization=organization, term=normalized
            )
        except PermissionDenied:
            materials = ()
        for material in materials[:RESULT_LIMIT_PER_FAMILY]:
            results.append(
                SearchResult(
                    family="material",
                    family_label="مصالح",
                    title=material.name,
                    reference=material.code,
                    url=reverse("materials:material_detail", args=[material.pk]),
                )
            )

    return SearchResponse(
        query=normalized,
        results=tuple(results),
        validation_message="",
    )
