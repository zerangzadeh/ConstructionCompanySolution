from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("documents", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="projectdocument",
            name="archive_reason",
            field=models.TextField(blank=True),
        ),
    ]
