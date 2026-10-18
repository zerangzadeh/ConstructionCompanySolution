from django.apps import AppConfig


class WorkforceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.workforce"
    verbose_name = "منابع انسانی"

    def ready(self):
        from .personal_change_workflow import register_personal_change
        register_personal_change()
        from .certificate_workflow import register_certificate_workflow
        register_certificate_workflow()
