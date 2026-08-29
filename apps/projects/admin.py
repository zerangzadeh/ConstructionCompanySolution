from django.contrib import admin

from apps.projects.models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "organization", "status", "budget", "deleted_at")
    list_filter = ("status", "organization")
    search_fields = ("code", "name", "organization__name")
    readonly_fields = ("id", "created_at", "updated_at")
