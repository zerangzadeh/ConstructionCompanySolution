from django.apps import AppConfig


class ContractsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.contracts"
    verbose_name = "قراردادها"

    def ready(self) -> None:
        from .contractual_workflow import register_contractual_record_workflow
        from .workflow import register_contract_amendment_workflow

        register_contract_amendment_workflow()
        register_contractual_record_workflow()
