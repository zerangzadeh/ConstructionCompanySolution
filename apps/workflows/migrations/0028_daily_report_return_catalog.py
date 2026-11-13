"""Add the Daily Report Return template without changing the legacy template."""
from django.db import migrations

CONFIGURATION = {'steps': [{'key': 'start', 'name': 'شروع', 'step_type': 'start', 'is_start': True},
           {'key': 'legacy_approval',
            'name': 'تأیید گزارش روزانه',
            'step_type': 'approval',
            'configuration': {'decision_policy': 'any',
                              'exclude_creator': True,
                              'exclude_submitter': True},
            'routing': [{'resolver_type': 'business_permission',
                         'configuration': {'permission': 'daily_reports.approve'}}]},
           {'key': 'approved', 'name': 'تأییدشده', 'step_type': 'end', 'is_terminal': True},
           {'key': 'compatibility_approval',
            'name': 'تأیید گزارش روزانه',
            'step_type': 'approval',
            'configuration': {'decision_policy': 'any'},
            'routing': [{'resolver_type': 'business_permission',
                         'configuration': {'permission': 'daily_reports.approve'}}]},
           {'key': 'returned',
            'name': 'بازگشت برای اصلاح',
            'step_type': 'end',
            'is_terminal': True}],
 'transitions': [{'source': 'start',
                  'target': 'legacy_approval',
                  'outcome': 'submitted_for_independent_review',
                  'is_default': False,
                  'conditions': [{'condition_type': 'subject_attribute_equals',
                                  'configuration': {'attribute': 'return_enabled',
                                                    'value': True}}]},
                 {'source': 'legacy_approval',
                  'target': 'approved',
                  'outcome': 'approved',
                  'domain_command': 'daily_reports.daily_report.approve',
                  'required_permission': 'daily_reports.approve'},
                 {'source': 'start',
                  'target': 'compatibility_approval',
                  'outcome': 'submitted',
                  'is_default': True},
                 {'source': 'compatibility_approval',
                  'target': 'approved',
                  'outcome': 'approved',
                  'domain_command': 'daily_reports.daily_report.approve',
                  'required_permission': 'daily_reports.approve'},
                 {'source': 'legacy_approval',
                  'target': 'returned',
                  'outcome': 'returned',
                  'domain_command': 'daily_reports.daily_report.return_for_correction',
                  'required_permission': 'daily_reports.approve'}]}


def seed(apps, schema_editor):
    template = apps.get_model("workflows", "WorkflowTemplate")
    template.objects.using(schema_editor.connection.alias).get_or_create(
        workflow_type__code="daily_reports.daily_report_approval",
        code="daily_report_return_v1",
        defaults={
            "workflow_type_id": apps.get_model("workflows", "WorkflowType").objects.using(
                schema_editor.connection.alias
            ).get(code="daily_reports.daily_report_approval").pk,
            "name": "بررسی مستقل و اصلاح گزارش روزانه",
            "description": "بازگشت مستدل و ارسال نسخه اصلاحی گزارش روزانه.",
            "configuration": CONFIGURATION,
            "is_active": True,
        },
    )


def unseed(apps, schema_editor):
    apps.get_model("workflows", "WorkflowTemplate").objects.using(
        schema_editor.connection.alias
    ).filter(code="daily_report_return_v1").update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [("workflows", "0027_p6_s33_s38_contractual_record_catalog")]
    operations = [migrations.RunPython(seed, unseed)]
