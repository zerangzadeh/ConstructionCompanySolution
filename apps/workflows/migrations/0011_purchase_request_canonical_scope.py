from django.db import migrations


def restrict_purchase_request_scope(apps, schema_editor):
    del schema_editor
    WorkflowType = apps.get_model("workflows", "WorkflowType")
    WorkflowType.objects.filter(code="procurement.purchase_request_approval").update(
        allowed_scope_fields=["project_id"]
    )


class Migration(migrations.Migration):
    dependencies = [("workflows", "0010_procurement_pilot_compatibility")]

    operations = [
        migrations.RunPython(restrict_purchase_request_scope, migrations.RunPython.noop)
    ]
