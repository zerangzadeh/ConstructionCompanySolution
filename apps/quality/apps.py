from django.apps import AppConfig


class QualityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.quality"
    verbose_name = "کیفیت"

    def ready(self) -> None:
        from .workflow import register_quality_workflow

        register_quality_workflow()
