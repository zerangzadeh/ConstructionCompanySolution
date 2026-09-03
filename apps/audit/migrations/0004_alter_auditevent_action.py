from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("audit", "0003_alter_auditevent_action")]
    operations = [
        migrations.AlterField(
            model_name="auditevent",
            name="action",
            field=models.CharField(
                choices=[
                    ("organization.created", "Organization created"), ("project.created", "Project created"), ("project.archived", "Project archived"), ("project_site.created", "Project site created"), ("project_phase.created", "Project phase created"), ("project_phase.status_changed", "Project phase status changed"), ("contract.created", "Contract created"), ("estimate.created", "Estimate created"), ("estimate.item_added", "Estimate item added"), ("estimate.approved", "Estimate approved"), ("expense.recorded", "Expense recorded"), ("expense.voided", "Expense voided"), ("payment.recorded", "Payment recorded"), ("payment.voided", "Payment voided"), ("document.uploaded", "Document uploaded"), ("document.downloaded", "Document downloaded"), ("document.archived", "Document archived"), ("daily_report.created", "Daily report created"), ("daily_report.submitted", "Daily report submitted"), ("daily_report.approved", "Daily report approved"), ("daily_report.labor_added", "Daily report labor added"), ("daily_report.equipment_added", "Daily report equipment added"), ("daily_report.material_added", "Daily report material added"), ("membership.invited", "Membership invited"), ("membership.accepted", "Membership accepted"),
                ], max_length=64,
            ),
        )
    ]
