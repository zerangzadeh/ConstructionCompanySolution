from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="auditevent",
            name="action",
            field=models.CharField(
                choices=[
                    ("organization.created", "Organization created"),
                    ("project.created", "Project created"),
                    ("project.archived", "Project archived"),
                    ("contract.created", "Contract created"),
                    ("estimate.created", "Estimate created"),
                    ("estimate.item_added", "Estimate item added"),
                    ("estimate.approved", "Estimate approved"),
                    ("expense.recorded", "Expense recorded"),
                    ("membership.invited", "Membership invited"),
                    ("membership.accepted", "Membership accepted"),
                ],
                max_length=64,
            ),
        ),
    ]
