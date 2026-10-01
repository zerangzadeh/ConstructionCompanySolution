import uuid
from typing import ClassVar

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


LEGACY_GROUPS = (
    ("materials", "مصالح"),
    ("labor", "نیروی انسانی"),
    ("equipment", "تجهیزات"),
    ("subcontractor", "پیمانکار جزء"),
    ("permit", "مجوزها"),
    ("other", "سایر"),
)


def seed_and_link_groups(apps, schema_editor):
    del schema_editor
    Group = apps.get_model("expenses", "PlatformExpenseGroup")
    Category = apps.get_model("expenses", "ExpenseCategory")
    groups = {
        code: Group.objects.get_or_create(code=code, defaults={"name": name})[0]
        for code, name in LEGACY_GROUPS
    }
    for category in Category.objects.filter(primary_group__isnull=True):
        category.primary_group = groups.get(category.code, groups["other"])
        category.save(update_fields=["primary_group"])


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [
        ("expenses", "0005_p4_s26_s30_expense_controls"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations: ClassVar[list] = [
        migrations.CreateModel(
            name="PlatformExpenseGroup",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        verbose_name="شناسه",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True, verbose_name="زمان آخرین به‌روزرسانی"
                    ),
                ),
                (
                    "code",
                    models.CharField(max_length=30, unique=True, verbose_name="کد"),
                ),
                (
                    "name",
                    models.CharField(
                        max_length=100, unique=True, verbose_name="نام گروه اصلی هزینه"
                    ),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
                (
                    "archived_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="زمان بایگانی"
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="platform_expense_groups_created",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="ایجادکننده",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="platform_expense_groups_updated",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="آخرین ویرایش‌کننده",
                    ),
                ),
            ],
            options={
                "verbose_name": "گروه اصلی هزینه",
                "verbose_name_plural": "گروه‌های اصلی هزینه",
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="expensecategory",
            name="primary_group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="expense_categories",
                to="expenses.platformexpensegroup",
                verbose_name="گروه اصلی هزینه",
            ),
        ),
        migrations.RunPython(seed_and_link_groups, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="expensecategory",
            name="primary_group",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="expense_categories",
                to="expenses.platformexpensegroup",
                verbose_name="گروه اصلی هزینه",
            ),
        ),
    ]
