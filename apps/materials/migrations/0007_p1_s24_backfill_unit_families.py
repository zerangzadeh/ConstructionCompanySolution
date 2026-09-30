from django.db import migrations


DIMENSION_BY_CATEGORY = {
    "count": "count",
    "length": "length",
    "area": "area",
    "volume": "volume",
    "weight": "weight",
    "time": "time",
}


def backfill_isolated_families(apps, schema_editor):
    del schema_editor
    UnitOfMeasure = apps.get_model("materials", "UnitOfMeasure")
    UnitFamily = apps.get_model("materials", "UnitFamily")
    for unit in UnitOfMeasure.objects.filter(family__isnull=True).iterator():
        family = UnitFamily.objects.create(
            organization_id=unit.organization_id,
            code=f"ISO-{unit.pk.hex[:12].upper()}",
            name=f"{unit.name} isolated",
            dimension=DIMENSION_BY_CATEGORY.get(unit.category, "isolated"),
            base_unit_id=unit.pk,
            created_by_id=unit.created_by_id,
        )
        UnitOfMeasure.objects.filter(pk=unit.pk, family__isnull=True).update(
            family_id=family.pk
        )


class Migration(migrations.Migration):
    dependencies = [
        ("materials", "0006_alter_unitfamily_created_by"),
    ]
    operations = [migrations.RunPython(backfill_isolated_families, migrations.RunPython.noop)]
