"""Fail-closed tenant inspection at the Django Admin registration boundary."""

from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.core.exceptions import FieldDoesNotExist, PermissionDenied
from django.db.models.base import ModelBase
from django.http import HttpRequest

from apps.organizations.authorization import (
    get_active_membership,
    membership_has_permission,
    membership_has_scope,
    permission_supports_object_scope,
    scope_queryset,
)
from apps.organizations.models import BusinessPermissionCode

# Only these company/project/site inspection surfaces have an approved Admin
# permission and object-scope contract. Other tenant models remain hidden here;
# their service-backed workspaces retain their existing authorization paths.
ADMIN_READ_SCOPES: dict[str, tuple[str, str | None, str | None]] = {
    "organizations.Organization": (
        BusinessPermissionCode.COMPANY_SETTINGS_VIEW,
        None,
        None,
    ),
    "projects.Project": (BusinessPermissionCode.PROJECTS_VIEW, "pk", None),
    "projects.ProjectSite": (
        BusinessPermissionCode.PROJECT_SITES_VIEW,
        "project_id",
        "pk",
    ),
    "projects.ProjectPhase": (
        BusinessPermissionCode.PROJECT_PHASES_VIEW,
        "site__project_id",
        "site_id",
    ),
    "projects.WBSNode": (BusinessPermissionCode.WBS_NODES_VIEW, "project_id", None),
    "projects.Activity": (
        BusinessPermissionCode.ACTIVITIES_VIEW,
        "project_id",
        "site_id",
    ),
    "projects.ProjectSiteDocumentLink": (
        BusinessPermissionCode.DOCUMENTS_VIEW,
        "project_site__project_id",
        "project_site_id",
    ),
}


class TenantScopedAdminMixin:
    """Require tenant authority for list, search, direct detail and navigation."""

    def _access(self, request: HttpRequest) -> tuple[Any, Any] | None:
        organization = getattr(request, "organization", None)
        policy = ADMIN_READ_SCOPES.get(self.model._meta.label)
        if organization is None or policy is None:
            return None
        try:
            membership = get_active_membership(
                user=request.user, organization=organization
            )
        except PermissionDenied:
            return None
        permission = policy[0]
        if not membership_has_permission(
            membership, permission
        ) or not membership_has_scope(
            membership,
            allow_any_scope=permission_supports_object_scope(permission),
        ):
            return None
        return organization, membership

    def get_queryset(self, request: HttpRequest):
        queryset = super().get_queryset(request)
        access = self._access(request)
        if access is None:
            return queryset.none()
        organization, membership = access
        _, project_lookup, site_lookup = ADMIN_READ_SCOPES[self.model._meta.label]
        if project_lookup is None:
            return queryset.filter(pk=organization.pk)
        return scope_queryset(
            queryset,
            membership=membership,
            project_lookup=project_lookup,
            site_lookup=site_lookup,
        )

    def has_module_permission(self, request: HttpRequest) -> bool:
        return self._access(request) is not None and super().has_module_permission(
            request
        )

    def has_view_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:
        access = self._access(request)
        if access is None or not super().has_view_permission(request, obj):
            return False
        if obj is None:
            return True
        organization, membership = access
        if self.model._meta.label == "organizations.Organization":
            return obj.pk == organization.pk
        if getattr(obj, "organization_id", None) != organization.pk:
            return False
        if self.model._meta.label == "projects.Project":
            return membership_has_scope(membership, project=obj)
        site = None
        project = None
        if self.model._meta.label == "projects.ProjectSite":
            site = obj
        elif self.model._meta.label == "projects.ProjectPhase":
            site = obj.site
        elif self.model._meta.label == "projects.ProjectSiteDocumentLink":
            site = obj.project_site
        else:
            project = obj.project
            if self.model._meta.label == "projects.Activity":
                site = obj.site
        return membership_has_scope(membership, project=project, site=site)

    def get_list_filter(self, request: HttpRequest):
        # Related-field filters enumerate values outside the scoped queryset.
        filters = []
        for item in super().get_list_filter(request):
            if not isinstance(item, str):
                continue
            try:
                field = self.model._meta.get_field(item.partition("__")[0])
            except FieldDoesNotExist:
                continue
            if not field.is_relation:
                filters.append(item)
        return filters

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:
        return False


class TenantSafeAdminSite(admin.AdminSite):
    """Wrap tenant-owned registrations, including future ones, by default."""

    def register(self, model_or_iterable, admin_class=None, **options):
        if not isinstance(model_or_iterable, ModelBase):
            for model in model_or_iterable:
                self.register(model, admin_class, **options)
            return
        model = model_or_iterable
        try:
            organization_field = model._meta.get_field("organization")
        except FieldDoesNotExist:
            organization_field = None
        if model._meta.label == "organizations.Organization" or (
            organization_field is not None and not organization_field.null
        ):
            admin_class = type(
                f"TenantScoped{(admin_class or admin.ModelAdmin).__name__}",
                (TenantScopedAdminMixin, admin_class or admin.ModelAdmin),
                {"__module__": __name__},
            )
        super().register(model, admin_class, **options)
