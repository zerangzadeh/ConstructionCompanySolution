from django.apps import AppConfig
from django.db.models.signals import post_migrate


class ReportingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reporting"
    verbose_name = "گزارش‌گیری و شاخص‌های حاکم‌شده"

    def ready(self) -> None:
        from apps.reporting.catalog_bootstrap import synchronize_metric_catalogue

        post_migrate.connect(
            synchronize_metric_catalogue,
            sender=self,
            dispatch_uid="reporting.synchronize_metric_catalogue",
        )
