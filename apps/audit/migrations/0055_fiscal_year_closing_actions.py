from django.db import migrations, models
from apps.audit.models import AuditAction


class Migration(migrations.Migration):
    dependencies = [("audit", "0054_cep005_integration_attempt_action")]
    operations = [migrations.AlterField(model_name="auditevent", name="action", field=models.CharField("عملیات", max_length=64, choices=AuditAction.choices))]
