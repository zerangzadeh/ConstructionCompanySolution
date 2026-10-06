from __future__ import annotations

import json
import uuid

from django import forms
from django.core.exceptions import PermissionDenied

from apps.daily_reports.field_models import (
    FieldObservation,
    FieldProposalFamily,
)
from apps.organizations.authorization import get_active_membership, scope_queryset
from apps.projects.models import (
    Activity,
    Project,
    ProjectPhase,
    ProjectPhaseStatus,
    ProjectSite,
)


class FieldObservationForm(forms.ModelForm):
    project = forms.ModelChoiceField(label="پروژه", queryset=Project.objects.none())
    site = forms.ModelChoiceField(label="کارگاه", queryset=ProjectSite.objects.none(), required=False)
    phase = forms.ModelChoiceField(label="فاز", queryset=ProjectPhase.objects.none(), required=False)
    activity = forms.ModelChoiceField(label="فعالیت", queryset=Activity.objects.none(), required=False)
    structured_payload_text = forms.CharField(
        label="داده ساختاریافته (JSON)", required=False, widget=forms.Textarea(attrs={"rows": 4, "dir": "ltr"})
    )
    operation_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)

    class Meta:
        model = FieldObservation
        fields = [  # noqa: RUF012
            "project", "site", "phase", "activity", "kind", "title", "summary",
            "structured_payload_text", "manual_context", "captured_at", "effective_at",
            "location_permission", "latitude", "longitude", "horizontal_accuracy_meters",
            "location_captured_at", "location_mismatch_note", "operation_key",
        ]
        widgets = {  # noqa: RUF012
            "captured_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "effective_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "location_captured_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "summary": forms.Textarea(attrs={"rows": 3}),
            "manual_context": forms.Textarea(attrs={"rows": 2}),
            "kind": forms.Select(),
            "location_permission": forms.Select(),
            "latitude": forms.NumberInput(attrs={"step": "0.000001"}),
            "longitude": forms.NumberInput(attrs={"step": "0.000001"}),
            "horizontal_accuracy_meters": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }

    def __init__(self, *args, organization=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = Project.objects.filter(
            organization=organization, deleted_at__isnull=True
        ).order_by("name")
        self.fields["site"].queryset = ProjectSite.objects.filter(
            organization=organization, is_active=True, project__deleted_at__isnull=True
        ).select_related("project").order_by("project__name", "name")
        self.fields["phase"].queryset = ProjectPhase.objects.filter(
            organization=organization, status=ProjectPhaseStatus.ACTIVE, site__is_active=True,
            site__project__deleted_at__isnull=True,
        ).select_related("site", "site__project").order_by("site__project__name", "name")
        self.fields["activity"].queryset = Activity.objects.filter(
            organization=organization, project__deleted_at__isnull=True
        ).select_related("project").order_by("project__name", "code")
        if user is None or organization is None:
            for field_name in ("project", "site", "phase", "activity"):
                self.fields[field_name].queryset = self.fields[field_name].queryset.none()
        else:
            try:
                membership = get_active_membership(user=user, organization=organization)
            except PermissionDenied:
                for field_name in ("project", "site", "phase", "activity"):
                    self.fields[field_name].queryset = self.fields[field_name].queryset.none()
            else:
                self.fields["project"].queryset = scope_queryset(
                    self.fields["project"].queryset,
                    membership=membership,
                    project_lookup="id",
                    include_site_parent=True,
                )
                self.fields["site"].queryset = scope_queryset(
                    self.fields["site"].queryset,
                    membership=membership,
                    project_lookup="project_id",
                    site_lookup="id",
                )
                self.fields["phase"].queryset = scope_queryset(
                    self.fields["phase"].queryset,
                    membership=membership,
                    project_lookup="site__project_id",
                    site_lookup="site_id",
                )
                self.fields["activity"].queryset = scope_queryset(
                    self.fields["activity"].queryset,
                    membership=membership,
                    project_lookup="project_id",
                    include_site_parent=True,
                )
        style = (
            "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 "
            "text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
        )
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", style)
        self.fields["operation_key"].widget.attrs.pop("class", None)
        if self.instance and self.instance.pk:
            self.initial["structured_payload_text"] = json.dumps(
                self.instance.structured_payload, ensure_ascii=False, indent=2
            )

    def clean_structured_payload_text(self):
        value = self.cleaned_data.get("structured_payload_text", "").strip()
        if not value:
            return {}
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("JSON داده ساختاریافته معتبر نیست.") from exc
        if not isinstance(parsed, dict):
            raise forms.ValidationError("داده ساختاریافته باید یک شیء JSON باشد.")
        return parsed

    def clean(self):
        cleaned = super().clean()
        project, site, phase, activity = (
            cleaned.get("project"), cleaned.get("site"), cleaned.get("phase"), cleaned.get("activity")
        )
        if project and site and site.project_id != project.pk:
            self.add_error("site", "کارگاه متعلق به پروژه انتخاب‌شده نیست.")
        if phase and site and phase.site_id != site.pk:
            self.add_error("phase", "فاز متعلق به کارگاه انتخاب‌شده نیست.")
        if activity and project and activity.project_id != project.pk:
            self.add_error("activity", "فعالیت متعلق به پروژه انتخاب‌شده نیست.")
        return cleaned


class FieldObservationEvidenceForm(forms.Form):
    document_version_id = forms.UUIDField(label="شناسه نسخه DMS")
    operation_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)


class FieldReviewForm(forms.Form):
    reason = forms.CharField(label="دلیل / توضیح", widget=forms.Textarea(attrs={"rows": 3}), required=False)
    operation_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)


class FieldProposalForm(forms.Form):
    family = forms.ChoiceField(label="خانواده پیشنهاد", choices=FieldProposalFamily.choices)
    lines_text = forms.CharField(label="سطرهای پیشنهاد (JSON)", widget=forms.Textarea(attrs={"rows": 5, "dir": "ltr"}))
    effective_at = forms.DateTimeField(label="زمان اثر", required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    operation_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)

    def clean_lines_text(self):
        value = self.cleaned_data["lines_text"].strip()
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("JSON سطرهای پیشنهاد معتبر نیست.") from exc
        if not isinstance(parsed, list) or not parsed or not all(isinstance(item, dict) for item in parsed):
            raise forms.ValidationError("سطرها باید آرایه‌ای غیرخالی از اشیای JSON باشند.")
        return parsed
