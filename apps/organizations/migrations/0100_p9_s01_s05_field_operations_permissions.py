from typing import ClassVar

from django.db import migrations


PERMISSIONS = (
    ("field_observations.view", "مشاهده مشاهدات میدانی"),
    ("field_observations.capture", "ثبت و ویرایش مشاهده میدانی"),
    ("field_observations.submit", "ارسال مشاهده میدانی"),
    ("field_observations.review", "بررسی مشاهده میدانی"),
    ("field_observations.location_view", "مشاهده مکان دقیق مشاهده"),
    ("field_proposals.prepare", "تهیه پیشنهاد تحویل مشاهده"),
    ("field_proposals.review", "بررسی پیشنهاد تحویل مشاهده"),
)


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
    view = {"field_observations.view"}
    capture = {
        "field_observations.capture",
        "field_observations.submit",
        "field_proposals.prepare",
    }
    review = {"field_observations.review", "field_proposals.review"}
    location = {"field_observations.location_view"}
    managers = {
        "tenant_owner",
        "tenant_admin",
        "tenant_manager",
        "company_owner",
        "company_manager",
        "operations_manager",
        "project_manager",
    }
    for role in role_model.objects.filter(organization__isnull=True):
        codes = set(view)
        if role.code in managers:
            codes |= capture | review | location
        elif role.code == "supervisor":
            codes |= capture
        elif role.code == "member":
            codes |= capture
        role.permissions.add(*(records[code] for code in codes))


def reverse(apps, schema_editor):
    del schema_editor
    apps.get_model("organizations", "BusinessPermission").objects.filter(
        code__in=[code for code, _ in PERMISSIONS]
    ).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [
        ("organizations", "0099_p8_s24_s27_cost_asset_permissions"),
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
