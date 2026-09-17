from django.apps import AppConfig


class DailyReportsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.daily_reports"
    verbose_name = "گزارش‌های روزانه"

    def ready(self) -> None:
        from .workflow import register_daily_report_workflow

        register_daily_report_workflow()
