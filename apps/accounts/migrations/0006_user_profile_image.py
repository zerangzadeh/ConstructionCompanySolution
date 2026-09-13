import apps.accounts.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_loginpagesettings"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="profile_image",
            field=models.FileField(
                blank=True,
                help_text="فرمت PNG، JPEG یا WebP با حداکثر حجم ۲ مگابایت.",
                max_length=255,
                upload_to=apps.accounts.models.profile_image_upload_path,
                validators=[apps.accounts.models.validate_profile_image],
                verbose_name="تصویر پروفایل",
            ),
        ),
    ]
