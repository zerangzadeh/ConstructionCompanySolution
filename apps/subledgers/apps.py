from django.apps import AppConfig


class SubledgersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.subledgers"

    def ready(self) -> None:
        from .supplier_invoice_handoffs import register_supplier_invoice_handoff

        register_supplier_invoice_handoff()
