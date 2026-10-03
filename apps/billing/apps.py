from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.billing"
    verbose_name = "صورت‌وضعیت و پیشرفت"

    def ready(self) -> None:
        from .commercial_workflow import register_commercial_control_workflows
        from .handoffs import register_progress_claim_financial_handoffs
        from .payable_handoffs import register_payable_certificate_financial_handoffs
        from .payable_workflow import register_payable_certificate_workflow
        from .workflow import (
            register_progress_claim_approval_workflow,
            register_progress_verification_workflow,
            register_project_baseline_workflow,
        )

        register_project_baseline_workflow()
        register_progress_verification_workflow()
        register_progress_claim_approval_workflow()
        register_progress_claim_financial_handoffs()
        register_payable_certificate_workflow()
        register_payable_certificate_financial_handoffs()
        register_commercial_control_workflows()
