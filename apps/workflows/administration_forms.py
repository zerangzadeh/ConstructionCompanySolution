"""Bounded presentation of the existing declarative workflow service inputs."""

import json

from django import forms
from django.apps import apps
from django.core.exceptions import ValidationError

from .models import WorkflowDefinition, WorkflowTemplate, WorkflowType
from .registry import registry
from .validators import validate_configuration_payload


class DefinitionForm(forms.Form):
    workflow_type = forms.ModelChoiceField(
        label="نوع گردش‌کار", queryset=WorkflowType.objects.none()
    )
    code = forms.SlugField(label="کد", max_length=100)
    name = forms.CharField(label="عنوان", max_length=255)
    description = forms.CharField(
        label="توضیحات", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
    scope = forms.JSONField(
        label="محدودهٔ انتخاب گردش‌کار",
        required=False,
        initial=dict,
        widget=forms.Textarea(attrs={"rows": 3, "dir": "ltr"}),
        help_text="فقط فیلدهای محدودهٔ ثبت‌شده برای نوع انتخابی؛ {} یعنی محدودهٔ عمومی شرکت.",
    )

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.fields["workflow_type"].queryset = WorkflowType.objects.filter(
            is_active=True, code__in=registry.workflow_types
        )

    def clean(self):
        data = super().clean()
        workflow_type = data.get("workflow_type")
        scope = data.get("scope")
        if scope is None:
            scope = {}
        if not workflow_type:
            return data
        definition = WorkflowDefinition(
            organization=self.organization, workflow_type=workflow_type, scope=scope
        )
        definition.clean()
        # IDs are configuration inputs, never tenant authority. Resolve each
        # registered relationship within the active tenant without existence hints.
        lookups = {
            "project_id": ("projects", "Project"),
            "site_id": ("projects", "ProjectSite"),
            "phase_id": ("projects", "ProjectPhase"),
            "contract_id": ("contracts", "Contract"),
            "baseline_id": ("billing", "ProjectBaseline"),
        }
        resolved = {}
        for key, (app_label, model_name) in lookups.items():
            if key not in scope:
                continue
            model = apps.get_model(app_label, model_name)
            try:
                target = model.objects.filter(
                    organization=self.organization, pk=scope[key]
                ).first()
            except (ValueError, TypeError, ValidationError):
                target = None
            if target is None:
                raise ValidationError("محدودهٔ انتخاب‌شده در این شرکت معتبر نیست.")
            resolved[key] = target
        project = resolved.get("project_id")
        project_ids = {project.pk} if project else set()
        for key, target in resolved.items():
            if key == "project_id":
                continue
            target_project_id = (
                target.site.project_id if key == "phase_id" else target.project_id
            )
            project_ids.add(target_project_id)
            if project and target_project_id != project.pk:
                raise ValidationError("اجزای محدوده به یک پروژه تعلق ندارند.")
        if len(project_ids) > 1:
            raise ValidationError("اجزای محدوده به یک پروژه تعلق ندارند.")
        if (
            "phase_id" in resolved
            and "site_id" in resolved
            and resolved["phase_id"].site_id != resolved["site_id"].pk
        ):
            raise ValidationError("فاز به کارگاه انتخاب‌شده تعلق ندارد.")
        data["scope"] = scope
        return data


class DeclarativeJSONField(forms.JSONField):
    def prepare_value(self, value):
        prepared = super().prepare_value(value)
        try:
            return json.dumps(json.loads(prepared), ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return prepared


class DraftForm(forms.Form):
    change_summary = forms.CharField(
        label="خلاصه تغییر", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
    template = forms.ModelChoiceField(
        label="جایگزینی پیکربندی با الگوی ثبت‌شده",
        queryset=WorkflowTemplate.objects.none(),
        required=False,
        help_text="انتخاب الگو، پیکربندی پیش‌نویس را با همان الگو جایگزین می‌کند؛ انتشار جداگانه است.",
    )
    configuration = DeclarativeJSONField(
        label="پیکربندی ثبت‌شدهٔ گام‌ها و انتقال‌ها",
        required=False,
        widget=forms.Textarea(attrs={"rows": 24, "dir": "ltr", "spellcheck": "false"}),
        help_text="ساختار اعلانی گام‌ها، انتقال‌ها و مسیریابی؛ فقط گزینه‌های کاتالوگ مجاز است.",
    )

    def __init__(self, *args, workflow_type_code, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.workflow_type_code = workflow_type_code
        self.organization = organization
        self.fields["template"].queryset = WorkflowTemplate.objects.filter(
            workflow_type__code=workflow_type_code, is_active=True
        )

    def clean(self):
        data = super().clean()
        if "configuration" not in data:
            return data
        template = data.get("template")
        value = template.configuration if template else data["configuration"]
        validate_configuration_payload(
            value, workflow_type_code=self.workflow_type_code
        )
        for step in value.get("steps", []):
            for rule in step.get("routing", []):
                target = {
                    "explicit_membership": (
                        "organizations",
                        "OrganizationMembership",
                        "membership_id",
                    ),
                    "position": ("workforce", "Position", "position_id"),
                    "work_team": ("workforce", "WorkTeam", "work_team_id"),
                }.get(rule["resolver_type"])
                if target is None:
                    continue
                app_label, model_name, key = target
                model = apps.get_model(app_label, model_name)
                try:
                    valid = model.objects.filter(
                        organization=self.organization, pk=rule["configuration"][key]
                    ).exists()
                except (ValueError, TypeError, ValidationError):
                    valid = False
                if not valid:
                    raise ValidationError("هدف مسیریابی در این شرکت معتبر نیست.")
        data["configuration"] = value
        return data


class LifecycleForm(forms.Form):
    reason = forms.CharField(
        label="دلیل / خلاصه تغییر",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, needs_reason=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reason"].required = needs_reason
