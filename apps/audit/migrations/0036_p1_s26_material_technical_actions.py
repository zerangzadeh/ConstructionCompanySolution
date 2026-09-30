from django.db import migrations, models

from apps.audit.models import AuditAction


class Migration(migrations.Migration):
    dependencies = [("audit", "0035_p1_s25_material_attribute_actions")]
    operations = [migrations.AlterField(model_name="auditevent", name="action", field=models.CharField(choices=AuditAction.choices, max_length=64, verbose_name="عملیات"))]
