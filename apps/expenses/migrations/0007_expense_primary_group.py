from typing import ClassVar

import django.db.models.deletion
from django.db import migrations, models


def backfill_expense_primary_groups(apps, schema_editor):
    del schema_editor
    Group = apps.get_model("expenses", "PlatformExpenseGroup")
    Expense = apps.get_model("expenses", "Expense")
    groups = {group.code: group for group in Group.objects.all()}
    fallback = groups["other"]
    for expense in Expense.objects.filter(primary_group__isnull=True):
        expense.primary_group = groups.get(expense.category, fallback)
        expense.save(update_fields=["primary_group"])


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("expenses", "0006_platformexpensegroup_expensecategory_primary_group")
    ]
    operations: ClassVar[list] = [
        migrations.AddField(
            model_name="expense",
            name="primary_group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="expenses",
                to="expenses.platformexpensegroup",
                verbose_name="گروه اصلی هزینه",
            ),
        ),
        migrations.RunPython(backfill_expense_primary_groups, migrations.RunPython.noop),
    ]
