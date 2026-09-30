from typing import ClassVar

from django.db import migrations, models
from django.utils import timezone

PERMISSION_CODE = "accounting.reconciliations_sign_off"
PROTECTED_OPERATION_CODE = "accounting.reconciliation_sign_off"


def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    ProtectedOperation = apps.get_model("organizations", "ProtectedOperation")
    permission, _ = Permission.objects.update_or_create(
        code=PERMISSION_CODE,
        defaults={
            "name": "بررسی و تأیید مستقل تطبیق حسابداری",
            "description": "بررسی و تأیید مستقل تطبیق حسابداری",
            "is_active": True,
        },
    )
    for role in Role.objects.filter(
        code__in=("tenant_owner", "company_owner", "tenant_admin", "accountant"),
        organization__isnull=True,
    ):
        role.permissions.add(permission)
    ProtectedOperation.objects.get_or_create(
        code=PROTECTED_OPERATION_CODE,
        version=1,
        defaults={
            "name": "Accounting reconciliation sign-off",
            "description": "Requires a dedicated permission, reason, immutable evidence and an independent reviewer.",
            "effective_at": timezone.now(),
            "reason": "P2-S19 protected independent reconciliation review",
        },
    )


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0053_p2_reconciliation_disposition_permission")
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.AlterField(
            model_name="protectedoperation",
            name="code",
            field=models.CharField(
                choices=[
                    ("authorization.self_grant", "افزایش دسترسی خود"),
                    (
                        "authorization.own_privileged_role",
                        "تخصیص یا تأیید نقش ممتاز خود",
                    ),
                    (
                        "authorization.own_support_access",
                        "دسترسی پشتیبانی یا اضطراری خود",
                    ),
                    ("authorization.policy_weaken", "تضعیف سیاست امنیت یا مجوز"),
                    (
                        "authorization.audit_control_weaken",
                        "تضعیف کنترل ممیزی یا امنیت",
                    ),
                    (
                        "authorization.protected_classification_change",
                        "تغییر طبقه‌بندی عملیات حفاظت‌شده",
                    ),
                    ("documents.hold_release", "آزادسازی نگهداری حقوقی سند"),
                    ("documents.disposal_approval", "تأیید قصد امحای سند"),
                    ("accounting.journal_post", "ثبت قطعی سند حسابداری"),
                    ("accounting.opening_accept", "پذیرش مانده افتتاحیه"),
                    ("accounting.journal_reverse", "برگشت سند حسابداری"),
                    ("accounting.period_close", "بستن دوره مالی"),
                    ("accounting.period_reopen", "بازگشایی دوره مالی"),
                    (
                        "accounting.reconciliation_sign_off",
                        "تأیید نهایی تطبیق حسابداری",
                    ),
                ],
                max_length=100,
            ),
        ),
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
