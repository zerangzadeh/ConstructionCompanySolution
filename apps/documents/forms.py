from django import forms

from apps.documents.models import ProjectDocument
from apps.payments.models import Payment
from apps.projects.models import Project


class ProjectDocumentForm(forms.ModelForm):
    """Private document upload form scoped to the active organization."""

    project = forms.ModelChoiceField(label="پروژه", queryset=Project.objects.none())
    payment = forms.ModelChoiceField(
        label="پرداخت",
        queryset=Payment.objects.none(),
        required=False,
        empty_label="بدون پرداخت مرتبط",
    )

    class Meta:
        model = ProjectDocument
        fields = [  # noqa: RUF012
            "project",
            "payment",
            "document_type",
            "title",
            "file",
        ]

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = Project.objects.filter(
            organization=organization,
            deleted_at__isnull=True,
        ).order_by("name")
        self.fields["payment"].queryset = (
            Payment.objects.filter(
                organization=organization,
                project__deleted_at__isnull=True,
            )
            .select_related("project")
            .order_by("-paid_on", "payment_number")
        )

    def clean(self):
        cleaned_data = super().clean()
        project = cleaned_data.get("project")
        payment = cleaned_data.get("payment")
        if payment and project and payment.project_id != project.pk:
            self.add_error(
                "payment", "پرداخت انتخاب‌شده متعلق به این پروژه نیست."
            )
        return cleaned_data


class DocumentArchiveForm(forms.Form):
    """Requires a retained reason when a document is removed from active use."""

    reason = forms.CharField(label="دلیل بایگانی", widget=forms.Textarea, max_length=1000)
