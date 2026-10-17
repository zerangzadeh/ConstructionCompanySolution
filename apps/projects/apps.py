from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.projects"
    verbose_name = "پروژه‌ها"

    def ready(self) -> None:
        from .forecast_governance import register_forecast_workflow

        register_forecast_workflow()
