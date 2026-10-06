from typing import ClassVar

from django import forms

from apps.accounts.models import User
from apps.documents.models import Document, DocumentVersion
from apps.organizations.models import MembershipStatus, Organization


class CaseAssignmentForm(forms.Form):
    assignee = forms.ModelChoiceField(
        queryset=User.objects.none(), label="مسئول رسیدگی"
    )
    expected_status = forms.CharField(widget=forms.HiddenInput)

    def __init__(
        self, *args, organization: Organization, current_status: str, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.fields["expected_status"].initial = current_status
        self.fields["assignee"].queryset = (
            User.objects.filter(
                organization_memberships__organization=organization,
                organization_memberships__status=MembershipStatus.ACTIVE,
                is_active=True,
            )
            .distinct()
            .order_by("first_name", "last_name", "username")
        )


class CaseTransitionForm(forms.Form):
    to_status = forms.ChoiceField(label="اقدام")
    comment = forms.CharField(
        label="توضیح", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
    expected_status = forms.CharField(widget=forms.HiddenInput)

    TRANSITIONS: ClassVar[dict[str, tuple[tuple[str, str], ...]]] = {
        "open": (("triaged", "بررسی اولیه"),),
        "triaged": (("in_progress", "شروع رسیدگی"), ("closed", "بستن")),
        "in_progress": (
            ("resolved", "حل‌شده"),
            ("awaiting_requester", "در انتظار درخواست‌کننده"),
        ),
        "awaiting_requester": (("in_progress", "ادامه رسیدگی"), ("resolved", "حل‌شده")),
        "resolved": (("closed", "بستن"), ("open", "بازگشایی / اصلاح")),
        "closed": (("open", "بازگشایی / اصلاح"),),
    }

    def __init__(self, *args, current_status: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["expected_status"].initial = current_status
        self.fields["to_status"].choices = self.TRANSITIONS.get(current_status, ())


class SupportEvidenceForm(forms.Form):
    document = forms.ModelChoiceField(queryset=Document.objects.none(), label="سند")
    document_version = forms.ModelChoiceField(
        queryset=DocumentVersion.objects.none(), label="نسخه دقیق سند"
    )

    def __init__(
        self,
        *args,
        organization: Organization,
        can_view_sensitive: bool = False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        documents = Document.objects.filter(organization=organization)
        versions = DocumentVersion.objects.filter(organization=organization)
        if not can_view_sensitive:
            documents = documents.filter(confidentiality="internal")
            versions = versions.filter(document__confidentiality="internal")
        self.fields["document"].queryset = documents.order_by("title")
        self.fields["document_version"].queryset = versions.select_related(
            "document"
        ).order_by("document__title", "-version_number")

    def clean(self):
        cleaned = super().clean()
        document = cleaned.get("document")
        version = cleaned.get("document_version")
        if document and version and version.document_id != document.pk:
            raise forms.ValidationError("نسخه انتخاب‌شده متعلق به سند انتخاب‌شده نیست.")
        return cleaned
