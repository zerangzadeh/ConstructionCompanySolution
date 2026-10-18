from django.apps import AppConfig


class PayrollConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payroll"
    verbose_name = "حقوق و دستمزد"

    def ready(self) -> None:
        from .inquiry_workflow import register_inquiry_workflow
        register_inquiry_workflow()
