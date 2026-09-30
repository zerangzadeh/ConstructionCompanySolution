from typing import ClassVar

from django.db import migrations
from django.utils import timezone


PERMISSIONS = (
    ("documents.retention_manage", "مدیریت پیش‌نویس سیاست نگهداری اسناد"),
    ("documents.retention_approve", "تأیید سیاست نگهداری اسناد"),
    ("documents.holds_place", "ثبت نگهداری حقوقی سند"),
    ("documents.holds_release", "آزادسازی نگهداری حقوقی سند"),
    ("documents.disposals_request", "درخواست قصد امحای سند"),
    ("documents.disposals_approve", "تأیید قصد امحای سند"),
    ("documents.export", "خروجی کنترل‌شده اسناد"),
)
PROTECTED_OPERATIONS = (
    (
        "documents.hold_release",
        "Document hold release",
        "Requires an authorized Tenant membership distinct from the hold placer.",
    ),
    (
        "documents.disposal_approval",
        "Document disposal intent approval",
        "Requires an authorized Tenant membership distinct from the requester; destructive execution remains disabled.",
    ),
)


def register_document_lifecycle_authority(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    ProtectedOperation = apps.get_model("organizations", "ProtectedOperation")

    permissions = {}
    for code, name in PERMISSIONS:
        permissions[code] = Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": name, "is_active": True},
        )[0]

    owner_codes = ("tenant_owner", "company_owner")
    admin_codes = (*owner_codes, "tenant_admin")
    for role in Role.objects.filter(
        code__in=admin_codes, organization__isnull=True
    ):
        allowed = list(permissions.values())
        if role.code == "tenant_admin":
            allowed = [
                permission
                for code, permission in permissions.items()
                if code != "documents.retention_approve"
            ]
        role.permissions.add(*allowed)

    for code, name, description in PROTECTED_OPERATIONS:
        ProtectedOperation.objects.get_or_create(
            code=code,
            version=1,
            defaults={
                "name": name,
                "description": description,
                "effective_at": timezone.now(),
                "reason": "P1-S22 Product Owner D19-07/A1 decision",
            },
        )


def unregister_document_lifecycle_authority(apps, schema_editor):
    del schema_editor
    apps.get_model("organizations", "ProtectedOperation").objects.filter(
        code__in=[item[0] for item in PROTECTED_OPERATIONS], version=1
    ).delete()
    apps.get_model("organizations", "BusinessPermission").objects.filter(
        code__in=[item[0] for item in PERMISSIONS]
    ).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0042_alter_protectedoperation_code"),
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RunPython(
            register_document_lifecycle_authority,
            unregister_document_lifecycle_authority,
        )
    ]
