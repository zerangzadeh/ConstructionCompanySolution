from django.db import migrations


NATIONAL_CODES = (
    "receivable-claim-regulatory",
    "taxpayer-invoice-regulatory",
    "contractor-compliance-regulatory",
)


def forward(apps, schema_editor):
    del schema_editor
    PlatformPolicy = apps.get_model("organizations", "PlatformPolicy")
    BusinessPermission = apps.get_model("organizations", "BusinessPermission")
    PlatformPolicy.objects.filter(code__in=NATIONAL_CODES).update(tenant_selectable=False)
    BusinessPermission.objects.filter(code="tenant_policies.approve").delete()


class Migration(migrations.Migration):
    dependencies = [("organizations", "0087_p6_s26_s32_statutory_permissions")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
