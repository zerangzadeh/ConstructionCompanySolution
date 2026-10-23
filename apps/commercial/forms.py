from django import forms
from django.core.exceptions import PermissionDenied
from django.db.models import OuterRef, Subquery

from apps.commercial.models import TenderBidStatus
from apps.documents.models import (
    DocumentProcessingAssessment,
    DocumentProcessingVerdict,
    DocumentVersion,
)
from apps.documents.services import get_organization_documents
from apps.organizations.authorization import effective_scope_grants
from apps.organizations.form_scoping import scoped_projects_for_form
from apps.organizations.models import AuthorizationScopeType
from apps.projects.models import Project


class TenderBidCreateForm(forms.Form):
    project = forms.ModelChoiceField(
        queryset=Project.objects.none(), label="پروژه", required=False
    )
    opportunity_code = forms.CharField(label="شناسه فرصت", max_length=80)
    title = forms.CharField(label="عنوان", max_length=255)
    description = forms.CharField(label="شرح", required=False, widget=forms.Textarea)

    def __init__(self, *args, organization, membership, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = scoped_projects_for_form(
            organization=organization, membership=membership
        )
        self.fields["project"].required = (
            not effective_scope_grants(membership)
            .filter(scope_type=AuthorizationScopeType.ORGANIZATION)
            .exists()
        )


class TenderBidRevisionForm(forms.Form):
    title = forms.CharField(label="عنوان", max_length=255)
    description = forms.CharField(label="شرح", required=False, widget=forms.Textarea)
    submission_reference = forms.CharField(
        label="مرجع ارسال", max_length=160, required=False
    )
    result_reference = forms.CharField(
        label="مرجع نتیجه", max_length=160, required=False
    )
    bid_bond_reference = forms.CharField(
        label="مرجع ضمانت پیشنهاد", max_length=160, required=False
    )
    bid_cost_reference = forms.CharField(
        label="مرجع هزینه پیشنهاد", max_length=160, required=False
    )
    reason = forms.CharField(label="دلیل بازنگری", widget=forms.Textarea)


class TenderBidTransitionForm(forms.Form):
    target = forms.ChoiceField(label="وضعیت بعدی", choices=TenderBidStatus.choices)
    reason = forms.CharField(label="دلیل", widget=forms.Textarea)
    submission_reference = forms.CharField(
        label="مرجع ارسال", max_length=160, required=False
    )
    result_reference = forms.CharField(
        label="مرجع نتیجه", max_length=160, required=False
    )


class TenderBidEvidenceForm(forms.Form):
    document_version_id = forms.ModelChoiceField(
        queryset=DocumentVersion.objects.none(),
        label="نسخه آماده سند",
        help_text="فقط نسخه جاری، پاک و قابل مشاهده در مدیریت اسناد قابل انتخاب است.",
    )
    description = forms.CharField(label="شرح شاهد", max_length=255, required=False)

    def __init__(self, *args, organization, user, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            documents = get_organization_documents(user=user, organization=organization)
        except PermissionDenied:
            return
        verdict = (
            DocumentProcessingAssessment.objects.filter(
                version_id=OuterRef("pk"),
                organization=organization,
            )
            .order_by("-sequence")
            .values("verdict")[:1]
        )
        self.fields["document_version_id"].queryset = (
            DocumentVersion.objects.filter(
                organization=organization,
                pk__in=documents.values("current_version_id"),
            )
            .annotate(latest_verdict=Subquery(verdict))
            .filter(
                latest_verdict=DocumentProcessingVerdict.CLEAN,
            )
            .select_related("document")
        )
        self.fields["document_version_id"].label_from_instance = lambda version: (
            f"{version.document.document_number} — {version.document.title} · نسخه {version.version_number}"
        )
