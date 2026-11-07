"""Register platform-only company capabilities with no tenant default grants."""

from django.db import migrations

PERMISSIONS = {
    "platform_companies.view": "مشاهده شرکت‌های پلتفرم",
    "platform_companies.configure": "تنظیم شرکت‌های پلتفرم",
    "platform_companies.change_status": "تغییر وضعیت شرکت‌های پلتفرم",
    "platform_companies.audit_view": "مشاهده فعالیت شرکت‌های پلتفرم",
}


def forward(apps, schema_editor):
    permissions = apps.get_model("organizations", "BusinessPermission").objects.using(
        schema_editor.connection.alias
    )
    for code, label in PERMISSIONS.items():
        permissions.update_or_create(
            code=code,
            defaults={
                "name": label,
                "description": "نیازمند نقش فعال مستقل Platform Admin.",
                "is_active": True,
            },
        )


def backward(apps, schema_editor):
    apps.get_model("organizations", "BusinessPermission").objects.using(
        schema_editor.connection.alias
    ).filter(code__in=PERMISSIONS).update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [("organizations", "0126_daily_report_record_reference_permission")]  # noqa: RUF012
    operations = [migrations.RunPython(forward, backward)]  # noqa: RUF012
