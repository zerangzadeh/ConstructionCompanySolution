from django.contrib import admin
from django.http import HttpRequest

from apps.projects.models import (
    Activity,
    Project,
    ProjectPhase,
    ProjectSite,
    ProjectSiteDocumentLink,
    WBSNode,
)


@admin.register(ProjectSiteDocumentLink)
class ProjectSiteDocumentLinkAdmin(admin.ModelAdmin):
    list_display = ("document", "project_site", "organization", "created_at")
    list_filter = ("organization",)
    readonly_fields = (
        "id",
        "organization",
        "document",
        "project_site",
        "created_by",
        "legacy_link_id",
        "created_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: ProjectSiteDocumentLink | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: ProjectSiteDocumentLink | None = None
    ) -> bool:
        return False


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "organization",
        "status",
        "estimated_budget",
        "actual_budget",
        "deleted_at",
    )
    list_filter = ("status", "organization")
    search_fields = ("code", "name", "organization__name")
    readonly_fields = ("id", "created_at", "updated_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: Project | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: Project | None = None
    ) -> bool:
        return False


@admin.register(ProjectSite)
class ProjectSiteAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "project", "organization", "is_active")
    list_filter = ("organization", "is_active")
    search_fields = ("code", "name", "project__name", "organization__name")
    readonly_fields = ("id", "created_at", "updated_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: ProjectSite | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: ProjectSite | None = None
    ) -> bool:
        return False


@admin.register(ProjectPhase)
class ProjectPhaseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "site", "organization", "status")
    list_filter = ("organization", "status")
    search_fields = ("code", "name", "site__name", "organization__name")
    readonly_fields = ("id", "created_at", "updated_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: ProjectPhase | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: ProjectPhase | None = None
    ) -> bool:
        return False


@admin.register(WBSNode)
class WBSNodeAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "project", "parent", "organization", "is_active")
    list_filter = ("organization", "project", "is_active")
    search_fields = ("code", "title", "project__name")
    readonly_fields = ("id", "created_at", "updated_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: WBSNode | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: WBSNode | None = None
    ) -> bool:
        return False


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "project", "wbs_node", "status", "organization")
    list_filter = ("organization", "project", "status", "is_active")
    search_fields = ("code", "name", "project__name")
    readonly_fields = ("id", "created_at", "updated_at")
    list_select_related = ("project", "wbs_node", "organization")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: Activity | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: Activity | None = None
    ) -> bool:
        return False
