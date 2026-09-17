from django.apps import AppConfig


class EquipmentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.equipment"
    verbose_name = "تجهیزات و ماشین‌آلات"

    def ready(self) -> None:
        from .workflow import register_maintenance_workflow

        register_maintenance_workflow()
