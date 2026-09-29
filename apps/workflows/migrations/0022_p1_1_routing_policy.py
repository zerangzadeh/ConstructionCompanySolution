from django.db import migrations


def remove_privileged_owner_routes(apps, schema_editor):
    WorkflowTemplate = apps.get_model("workflows", "WorkflowTemplate")
    for template in WorkflowTemplate.objects.all().iterator():
        configuration = dict(template.configuration or {})
        steps = [dict(step) for step in configuration.get("steps", [])]
        transitions = configuration.get("transitions", [])
        permission_by_source = {
            transition.get("source"): transition.get("required_permission")
            for transition in transitions
            if transition.get("required_permission")
        }
        changed = False
        for step in steps:
            routes = step.get("routing")
            if not isinstance(routes, list):
                continue
            retained = [
                route
                for route in routes
                if route.get("resolver_type") != "organization_owner"
            ]
            if len(retained) == len(routes):
                continue
            changed = True
            if not retained:
                permission = step.get("required_permission") or permission_by_source.get(
                    step.get("key")
                )
                if permission:
                    retained = [
                        {
                            "resolver_type": "business_permission",
                            "configuration": {"permission": permission},
                        }
                    ]
            step["routing"] = retained
        if changed:
            configuration["steps"] = steps
            WorkflowTemplate.objects.filter(pk=template.pk).update(
                configuration=configuration
            )


class Migration(migrations.Migration):
    dependencies = [("workflows", "0021_p1_1_unresolved_work")]  # noqa: RUF012

    operations = [  # noqa: RUF012
        migrations.RunPython(
            remove_privileged_owner_routes,
            reverse_code=migrations.RunPython.noop,
        )
    ]
