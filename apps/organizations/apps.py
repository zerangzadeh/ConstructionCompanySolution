from django.apps import AppConfig
from django.db.models.signals import post_migrate


class OrganizationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.organizations"
    verbose_name = "سازمان‌ها"

    def ready(self) -> None:
        from apps.organizations.catalog_bootstrap import (
            synchronize_authorization_catalog,
        )

        post_migrate.connect(
            synchronize_authorization_catalog,
            sender=self,
            dispatch_uid="organizations.synchronize_authorization_catalog",
        )
