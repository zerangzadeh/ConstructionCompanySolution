"""Tenant-bound inputs for the existing immutable employment-record command."""

from django import forms

from apps.documents.models import DocumentVersion
from apps.documents.services import get_organization_documents
from core.forms import JalaliDateMixin

from .models import EmploymentRecord, WorkRelationship, WorkRelationshipDocumentLink


class EmploymentRecordForm(JalaliDateMixin, forms.Form):
    relationship = forms.ModelChoiceField(
        queryset=WorkRelationship.objects.none(), label="رابطه کاری"
    )
    record_key = forms.CharField(max_length=100, label="شناسه سابقه")
    kind = forms.ChoiceField(
        choices=EmploymentRecord._meta.get_field("kind").choices, label="نوع سابقه"
    )
    effective_from = forms.DateField(label="شروع اثر")
    effective_to = forms.DateField(required=False, label="پایان اثر")
    document_version = forms.ModelChoiceField(
        queryset=DocumentVersion.objects.none(), label="نسخه ایمن سند مرتبط"
    )
    supersedes = forms.ModelChoiceField(
        queryset=EmploymentRecord.objects.none(),
        required=False,
        label="جایگزینی سابقه پیشین",
    )
    reason = forms.CharField(max_length=2000, widget=forms.Textarea, label="دلیل ثبت")

    def __init__(self, *args, organization, actor, **kwargs):
        super().__init__(*args, **kwargs)
        relationships = WorkRelationship.objects.filter(
            organization=organization, person__organization=organization
        ).select_related("person")
        self.fields["relationship"].queryset = relationships
        self.fields["relationship"].label_from_instance = lambda item: (
            f"{item.person.first_name} {item.person.last_name} · "
            f"{item.employee_number} · {item.effective_start}"
        )
        value = (
            self.data.get("relationship")
            if self.is_bound
            else self.initial.get("relationship")
        )
        try:
            relationship = relationships.filter(pk=value).first() if value else None
        except (ValueError, forms.ValidationError):
            relationship = None
        if relationship is None:
            return
        documents = get_organization_documents(user=actor, organization=organization)
        links = WorkRelationshipDocumentLink.objects.filter(
            organization=organization,
            work_relationship=relationship,
            document__in=documents,
        ).values("document_id")
        versions = (
            DocumentVersion.objects.filter(
                organization=organization, document_id__in=links
            )
            .select_related("document")
            .order_by("document__title", "version_number")
        )
        self.fields["document_version"].queryset = versions.filter(
            pk__in=[v.pk for v in versions if v.is_available]
        )
        self.fields["document_version"].label_from_instance = lambda item: (
            f"{item.document.title} · {item.version_number}"
        )
        self.fields["supersedes"].queryset = EmploymentRecord.objects.filter(
            organization=organization,
            relationship=relationship,
            replacement__isnull=True,
            document_version__document__in=documents,
        )
        self.fields["supersedes"].label_from_instance = lambda item: (
            f"{item.record_key} · {item.version}"
        )
