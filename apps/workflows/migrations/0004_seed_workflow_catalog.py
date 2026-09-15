from django.db import migrations


WORKFLOW_TYPE_CODE = "procurement.purchase_request_approval"
TEMPLATE_CODE = "small_tenant_owner_approval"


def seed_catalog(apps, schema_editor):
    workflow_type_model = apps.get_model("workflows", "WorkflowType")
    template_model = apps.get_model("workflows", "WorkflowTemplate")
    workflow_type, _ = workflow_type_model.objects.update_or_create(
        code=WORKFLOW_TYPE_CODE,
        defaults={
            "name": "تأیید درخواست خرید",
            "description": "نوع ثبت‌شده برای پایلوت آینده خرید؛ بدون اتصال runtime در W1.",
            "subject_type": "procurement.purchase_request",
            "subject_adapter": "procurement.purchase_request",
            "allowed_scope_fields": ["amount_band", "classification", "project_id"],
            "is_active": True,
        },
    )
    template_model.objects.update_or_create(
        workflow_type=workflow_type,
        code=TEMPLATE_CODE,
        defaults={
            "name": "تصمیم مالک برای شرکت کوچک",
            "description": "الگوی declarative؛ تبدیل آن به تعریف tenant در W2/W3 انجام می‌شود.",
            "is_active": True,
            "configuration": {
                "steps": [
                    {
                        "key": "start",
                        "name": "شروع",
                        "step_type": "start",
                        "is_start": True,
                    },
                    {
                        "key": "owner_decision",
                        "name": "تصمیم مالک",
                        "step_type": "approval",
                        "configuration": {"decision_policy": "any"},
                        "routing": [
                            {
                                "resolver_type": "organization_owner",
                                "configuration": {},
                            }
                        ],
                    },
                    {
                        "key": "approved",
                        "name": "تأییدشده",
                        "step_type": "end",
                        "is_terminal": True,
                    },
                    {
                        "key": "rejected",
                        "name": "ردشده",
                        "step_type": "end",
                        "is_terminal": True,
                    },
                ],
                "transitions": [
                    {
                        "source": "start",
                        "target": "owner_decision",
                        "outcome": "submitted",
                        "is_default": True,
                    },
                    {
                        "source": "owner_decision",
                        "target": "approved",
                        "outcome": "approved",
                        "domain_command": "procurement.purchase_request.approve",
                        "required_permission": "purchase_requests.approve",
                    },
                    {
                        "source": "owner_decision",
                        "target": "rejected",
                        "outcome": "rejected",
                        "domain_command": "procurement.purchase_request.reject",
                        "required_permission": "purchase_requests.reject",
                    },
                ],
            },
        },
    )


def remove_catalog(apps, schema_editor):
    template_model = apps.get_model("workflows", "WorkflowTemplate")
    workflow_type_model = apps.get_model("workflows", "WorkflowType")
    template_model.objects.filter(
        workflow_type__code=WORKFLOW_TYPE_CODE, code=TEMPLATE_CODE
    ).delete()
    workflow_type_model.objects.filter(code=WORKFLOW_TYPE_CODE).delete()


class Migration(migrations.Migration):
    dependencies = [  # noqa: RUF012
        ("organizations", "0022_workflow_foundation_permissions"),
        ("workflows", "0003_workflowtransitiondefinition_required_permission"),
    ]

    operations = [  # noqa: RUF012
        migrations.RunPython(seed_catalog, remove_catalog),
    ]

