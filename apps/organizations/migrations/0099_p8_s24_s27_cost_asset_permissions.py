from typing import ClassVar

from django.db import migrations

EQUIPMENT_COST = (
    ("equipment_cost_policy.view", "مشاهده سیاست هزینه تجهیز"),
    ("equipment_cost_policy.manage", "تهیه سیاست هزینه تجهیز"),
    ("equipment_cost_policy.publish", "انتشار سیاست هزینه تجهیز"),
    ("equipment_cost_allocation.view", "مشاهده تخصیص هزینه تجهیز"),
    ("equipment_cost_allocation.prepare", "تهیه تخصیص هزینه تجهیز"),
    ("equipment_cost_allocation.review", "بررسی تخصیص هزینه تجهیز"),
    ("equipment_cost_allocation.reverse", "برگشت تخصیص هزینه تجهیز"),
    ("equipment_cost_handoff.prepare", "تهیه پیشنهاد هزینه تجهیز"),
    ("equipment_cost_handoff.review", "بررسی پیشنهاد هزینه تجهیز"),
    ("equipment_cost_handoff.reconcile", "تطبیق پیشنهاد هزینه تجهیز"),
)
FIXED_ASSETS = (
    ("fixed_assets.view", "مشاهده دارایی‌های ثابت"),
    ("fixed_assets.candidate_prepare", "تهیه نامزد دارایی ثابت"),
    ("fixed_assets.candidate_review", "بررسی نامزد دارایی ثابت"),
    ("fixed_assets.manage", "مدیریت دارایی ثابت"),
    ("fixed_assets.class_policy_manage", "تهیه طبقه و سیاست دارایی"),
    ("fixed_assets.class_policy_publish", "انتشار طبقه و سیاست دارایی"),
    ("fixed_assets.capitalize", "سرمایه‌ای‌کردن دارایی"),
    ("fixed_assets.transaction_prepare", "تهیه رویداد دارایی"),
    ("fixed_assets.transaction_review", "بررسی رویداد دارایی"),
    ("fixed_assets.transaction_reverse", "برگشت رویداد دارایی"),
    ("fixed_assets.depreciation_preview", "پیش‌نمایش استهلاک"),
    ("fixed_assets.depreciation_finalize", "نهایی‌سازی استهلاک"),
    ("fixed_assets.depreciation_reverse", "برگشت استهلاک"),
    ("fixed_assets.transfer", "انتقال دارایی ثابت"),
    ("fixed_assets.impair", "کاهش ارزش دارایی ثابت"),
    ("fixed_assets.dispose", "واگذاری یا خروج دارایی ثابت"),
    ("fixed_assets.handoff_prepare", "تهیه پیشنهاد دارایی ثابت"),
    ("fixed_assets.handoff_review", "بررسی پیشنهاد دارایی ثابت"),
    ("fixed_assets.handoff_reconcile", "تطبیق پیشنهاد دارایی ثابت"),
    ("fixed_assets.audit_view", "مشاهده ممیزی دارایی ثابت"),
)
PERMISSIONS = EQUIPMENT_COST + FIXED_ASSETS


def forward(apps, schema_editor):
    del schema_editor
    permission_model = apps.get_model("organizations", "BusinessPermission")
    role_model = apps.get_model("organizations", "OrganizationRole")
    records = {
        code: permission_model.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": name, "is_active": True},
        )[0]
        for code, name in PERMISSIONS
    }
    cost_view = {"equipment_cost_policy.view", "equipment_cost_allocation.view"}
    cost_prepare = {
        "equipment_cost_policy.manage",
        "equipment_cost_allocation.prepare",
        "equipment_cost_handoff.prepare",
    }
    all_cost = {code for code, _ in EQUIPMENT_COST}
    all_assets = {code for code, _ in FIXED_ASSETS}
    for role in role_model.objects.filter(organization__isnull=True):
        codes = set()
        if role.code in {"tenant_owner", "company_owner", "tenant_admin", "accountant"}:
            codes |= all_cost | all_assets
        elif role.code in {"tenant_manager", "company_manager"}:
            codes |= all_cost | {"fixed_assets.view"}
        elif role.code in {"project_manager", "operations_manager"}:
            codes |= cost_view | cost_prepare | {"fixed_assets.view"}
        role.permissions.add(*(records[code] for code in codes))


def reverse(apps, schema_editor):
    del schema_editor
    apps.get_model("organizations", "BusinessPermission").objects.filter(
        code__in=[code for code, _ in PERMISSIONS]
    ).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [
        ("organizations", "0098_p8_s18_s23_equipment_operations_permissions")
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
