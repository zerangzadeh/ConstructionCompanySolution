"""Select the guarded Django Admin site for tenant-owned models."""

from django.contrib.admin.apps import AdminConfig


class TenantSafeAdminConfig(AdminConfig):
    default_site = "core.admin.TenantSafeAdminSite"
