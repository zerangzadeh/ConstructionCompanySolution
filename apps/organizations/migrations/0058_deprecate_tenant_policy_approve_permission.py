from django.db import migrations


LEGACY_PERMISSION_CODE = "tenant_policies.approve"
LEGACY_PERMISSION_LABEL = "منسوخ — تأیید انتخاب سیاست‌های Tenant (بدون مسیر اجرایی)"


def deprecate_legacy_permission(apps, schema_editor):
    del schema_editor
    apps.get_model("organizations", "BusinessPermission").objects.filter(
        code=LEGACY_PERMISSION_CODE
    ).update(
        name=LEGACY_PERMISSION_LABEL,
        description=(
            "این مجوز منسوخ و غیرفعال است. انتخاب و اعمال سیاست حسابداری فقط با "
            "tenant_policies.apply توسط Tenant Admin انجام می‌شود؛ مسیر تأیید جداگانه‌ای وجود ندارد."
        ),
        is_active=False,
    )


class Migration(migrations.Migration):
    dependencies = [("organizations", "0057_policy_source_reason")]

    operations = [migrations.RunPython(deprecate_legacy_permission, migrations.RunPython.noop)]
