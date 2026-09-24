from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.billing"
    verbose_name = "صورت‌وضعیت و پیشرفت"

    def ready(self) -> None:
        from .workflow import (
            register_progress_claim_approval_workflow,
            register_progress_verification_workflow,
            register_project_baseline_workflow,
        )

        register_project_baseline_workflow()
        register_progress_verification_workflow()
        register_progress_claim_approval_workflow()
