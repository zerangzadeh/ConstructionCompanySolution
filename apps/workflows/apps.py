from django.apps import AppConfig
from django.db.models.signals import post_migrate


class WorkflowsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.workflows"
    verbose_name = "گردش‌کار و مدیریت کار"

    def ready(self) -> None:
        from apps.workflows.catalog_bootstrap import synchronize_workflow_catalog

        post_migrate.connect(
            synchronize_workflow_catalog,
            sender=self,
            dispatch_uid="workflows.synchronize_workflow_catalog",
        )
