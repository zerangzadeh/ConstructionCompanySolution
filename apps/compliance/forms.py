# ruff: noqa: RUF012
from __future__ import annotations

import uuid

from django import forms

from apps.accounts.models import User
from apps.compliance.models import (
    CapaAction,
    EvidencePurpose,
    Inspection,
    InspectionFinding,
    InspectionTemplate,
    InspectionTemplateVersion,
    Nonconformance,
    Permit,
    QualityTest,
)
from apps.documents.models import DocumentVersion
from apps.organizations.models import MembershipStatus, Organization
from apps.projects.models import Project, ProjectSite
from core.forms import JalaliDateMixin, attach_parent_choice_ui


class StyledForm(JalaliDateMixin):
    def style(self) -> None:
        css = "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
        for field in self.fields.values():
            field.widget.attrs["class"] = css


class ScopedModelForm(StyledForm, forms.ModelForm):
    def __init__(
        self, *args: object, organization: Organization, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        if "project" in self.fields:
            self.fields["project"].queryset = Project.objects.filter(
                organization=organization, deleted_at__isnull=True
            )
        if "site" in self.fields:
            self.fields["site"].queryset = ProjectSite.objects.filter(
                organization=organization, is_active=True
            )
            self.fields["site"].required = False
        if "project" in self.fields and "site" in self.fields:
            attach_parent_choice_ui(self, "site", "project", "project_id")
        self.style()


class TemplateForm(StyledForm, forms.ModelForm):
    class Meta:
        model = InspectionTemplate
        fields = ["profile", "code", "title"]

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.style()


class TemplatePublishForm(StyledForm, forms.Form):
    checklist = forms.JSONField(
        label="اقلام چک‌لیست", widget=forms.Textarea(attrs={"rows": 8}), initial=list
    )
    required_evidence = forms.JSONField(
        label="شواهد الزامی", widget=forms.Textarea(attrs={"rows": 4}), initial=list
    )
    outcome_rules = forms.JSONField(
        label="قواعد نتیجه", widget=forms.Textarea(attrs={"rows": 4}), initial=dict
    )
    source_references = forms.JSONField(
        label="مراجع منبع", widget=forms.Textarea(attrs={"rows": 4}), initial=list
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.style()


class InspectionForm(ScopedModelForm):
    class Meta:
        model = Inspection
        fields = [
            "profile",
            "project",
            "site",
            "number",
            "template_version",
            "title",
            "inspector",
            "scheduled_for",
            "replaces",
        ]
        widgets = {
            "scheduled_for": forms.DateTimeInput(attrs={"type": "datetime-local"})
        }

    def __init__(
        self, *args: object, organization: Organization, **kwargs: object
    ) -> None:
        super().__init__(*args, organization=organization, **kwargs)
        self.fields[
            "template_version"
        ].queryset = InspectionTemplateVersion.objects.filter(
            organization=organization, template__status="published"
        )
        self.fields["inspector"].queryset = User.objects.filter(
            organization_memberships__organization=organization,
            organization_memberships__status=MembershipStatus.ACTIVE,
            is_active=True,
        ).distinct()
        self.fields["replaces"].queryset = Inspection.objects.filter(
            organization=organization, status__in=["passed", "conditional", "failed"]
        )
        self.fields["replaces"].required = False


class PermitForm(ScopedModelForm):
    class Meta:
        model = Permit
        fields = [
            "project",
            "site",
            "number",
            "permit_type",
            "rule_source",
            "rule_version",
            "issuer_name",
            "scope_description",
            "valid_from",
            "valid_until",
        ]
        widgets = {
            "valid_from": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "valid_until": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "scope_description": forms.Textarea(attrs={"rows": 3}),
        }


class QualityTestForm(ScopedModelForm):
    class Meta:
        model = QualityTest
        fields = [
            "project",
            "site",
            "number",
            "title",
            "method_reference",
            "method_version",
            "acceptance_criteria",
            "specimen_id",
            "replaces",
        ]
        widgets = {"acceptance_criteria": forms.Textarea(attrs={"rows": 5})}

    def __init__(
        self, *args: object, organization: Organization, **kwargs: object
    ) -> None:
        super().__init__(*args, organization=organization, **kwargs)
        self.fields["replaces"].queryset = QualityTest.objects.filter(
            organization=organization,
            status__in=["accepted", "rejected", "invalidated"],
        )
        self.fields["replaces"].required = False


class FindingForm(ScopedModelForm):
    class Meta:
        model = InspectionFinding
        fields = ["inspection", "source_test", "number", "title", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(
        self, *args: object, organization: Organization, **kwargs: object
    ) -> None:
        super().__init__(*args, organization=organization, **kwargs)
        self.fields["inspection"].queryset = Inspection.objects.filter(
            organization=organization
        )
        self.fields["source_test"].queryset = QualityTest.objects.filter(
            organization=organization
        )
        self.fields["inspection"].required = False
        self.fields["source_test"].required = False


class NcrForm(StyledForm, forms.Form):
    finding = forms.ModelChoiceField(
        label="یافته QA/QC", queryset=InspectionFinding.objects.none()
    )
    number = forms.CharField(label="شماره NCR", max_length=50)
    description = forms.CharField(
        label="شرح عدم انطباق", widget=forms.Textarea(attrs={"rows": 4})
    )

    def __init__(
        self, *args: object, organization: Organization, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["finding"].queryset = InspectionFinding.objects.filter(
            organization=organization,
            profile="qa_qc",
            status__in=["triaged", "assigned"],
        )
        self.style()


class CapaForm(ScopedModelForm):
    class Meta:
        model = CapaAction
        fields = [
            "finding",
            "nonconformance",
            "number",
            "action_type",
            "problem_or_risk",
            "cause_or_rationale",
            "implementation_plan",
            "verification_criteria",
            "effectiveness_criteria",
            "target_date",
            "distinct_closer_required",
        ]
        widgets = {
            field: forms.Textarea(attrs={"rows": 3})
            for field in (
                "problem_or_risk",
                "cause_or_rationale",
                "implementation_plan",
                "verification_criteria",
                "effectiveness_criteria",
            )
        }

    def __init__(
        self, *args: object, organization: Organization, **kwargs: object
    ) -> None:
        super().__init__(*args, organization=organization, **kwargs)
        self.fields["finding"].queryset = InspectionFinding.objects.filter(
            organization=organization
        )
        self.fields["nonconformance"].queryset = Nonconformance.objects.filter(
            organization=organization
        )
        self.fields["finding"].required = False
        self.fields["nonconformance"].required = False


class TransitionForm(StyledForm, forms.Form):
    expected_status = forms.CharField(widget=forms.HiddenInput())
    to_status = forms.CharField(widget=forms.HiddenInput())
    operation_key = forms.UUIDField(widget=forms.HiddenInput(), initial=uuid.uuid4)
    reason = forms.CharField(
        label="دلیل / توضیح", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
    updates = forms.JSONField(
        label="جزئیات تکمیلی",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        initial=dict,
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.style()


class EvidenceForm(StyledForm, forms.Form):
    document_version = forms.ModelChoiceField(
        label="نسخه دقیق سند", queryset=DocumentVersion.objects.none()
    )
    purpose = forms.ChoiceField(label="کاربرد شاهد", choices=EvidencePurpose.choices)
    operation_key = forms.UUIDField(widget=forms.HiddenInput(), initial=uuid.uuid4)

    def __init__(
        self, *args: object, organization: Organization, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["document_version"].queryset = DocumentVersion.objects.filter(
            organization=organization
        ).select_related("document")
        self.style()
