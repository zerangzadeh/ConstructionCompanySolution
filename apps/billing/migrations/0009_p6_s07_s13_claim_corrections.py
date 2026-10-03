import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0008_p6_s01_s06_seed_reset_and_required_snapshots"),
    ]

    operations = [
        migrations.AddField(
            model_name="progressclaim",
            name="correction_kind",
            field=models.CharField(
                choices=[
                    ("ordinary", "عادی"),
                    ("replacement", "اصلاح جایگزین"),
                    ("cancellation", "ابطال"),
                ],
                default="ordinary",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="progressclaim",
            name="correction_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="progressclaim",
            name="corrects",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="correction_claim",
                to="billing.progressclaim",
            ),
        ),
        migrations.AlterField(
            model_name="progressclaim",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "پیش‌نویس"),
                    ("submitted", "ارسال‌شده برای تأیید"),
                    ("approved", "تأییدشده"),
                    ("returned", "بازگردانده‌شده برای اصلاح"),
                    ("superseded", "جایگزین‌شده با اصلاح"),
                    ("cancelled", "باطل‌شده با سند پیوندخورده"),
                ],
                db_index=True,
                default="draft",
                max_length=20,
            ),
        ),
    ]
