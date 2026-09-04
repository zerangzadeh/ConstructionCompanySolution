import django.db.models.deletion
import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("organizations", "0002_organizationsettings"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UnitOfMeasure",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=20)),
                ("name", models.CharField(max_length=100)),
                ("symbol", models.CharField(max_length=20)),
                ("category", models.CharField(choices=[("count", "Count"), ("length", "Length"), ("area", "Area"), ("volume", "Volume"), ("weight", "Weight"), ("time", "Time"), ("other", "Other")], max_length=20)),
                ("decimal_places", models.PositiveSmallIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="units_of_measure_created", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="units_of_measure", to="organizations.organization")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="units_of_measure_updated", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["name"],
                "indexes": [models.Index(fields=["organization", "is_active"], name="uom_org_active_idx")],
                "constraints": [models.UniqueConstraint(fields=("organization", "code"), name="unique_uom_code_per_organization"), models.UniqueConstraint(fields=("organization", "symbol"), name="unique_uom_symbol_per_organization")],
            },
        ),
    ]
