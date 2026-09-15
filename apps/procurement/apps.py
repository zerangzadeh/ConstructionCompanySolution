from django.apps import AppConfig


class ProcurementConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.procurement"
    verbose_name = "تدارکات و خرید"

    def ready(self) -> None:
        from .workflow import register_purchase_request_workflow

        register_purchase_request_workflow()
