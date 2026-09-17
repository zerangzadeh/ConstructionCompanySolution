from django.apps import AppConfig


class SafetyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.safety"
    verbose_name = "ایمنی"

    def ready(self) -> None:
        from .workflow import register_safety_workflow

        register_safety_workflow()
