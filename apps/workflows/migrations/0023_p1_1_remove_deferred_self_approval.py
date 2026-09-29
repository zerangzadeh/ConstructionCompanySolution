from django.db import migrations


def remove_deferred_self_approval_flags(apps, schema_editor):
    WorkflowTemplate = apps.get_model("workflows", "WorkflowTemplate")
    for template in WorkflowTemplate.objects.all().iterator():
        configuration = dict(template.configuration or {})
        steps = [dict(step) for step in configuration.get("steps", [])]
        changed = False
        for step in steps:
            step_configuration = dict(step.get("configuration") or {})
            if "allow_submitter_if_no_other_candidate" not in step_configuration:
                continue
            step_configuration.pop("allow_submitter_if_no_other_candidate")
            step["configuration"] = step_configuration
            changed = True
        if changed:
            configuration["steps"] = steps
            WorkflowTemplate.objects.filter(pk=template.pk).update(
                configuration=configuration
            )


class Migration(migrations.Migration):
    dependencies = [("workflows", "0022_p1_1_routing_policy")]  # noqa: RUF012

    operations = [  # noqa: RUF012
        migrations.RunPython(
            remove_deferred_self_approval_flags,
            reverse_code=migrations.RunPython.noop,
        )
    ]
