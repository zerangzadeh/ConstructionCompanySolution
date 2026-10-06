from typing import Any

from django import forms
from django.core.exceptions import PermissionDenied

from apps.contracts.models import Contract
from apps.daily_reports.field_models import FieldObservation, FieldObservationStatus
from apps.daily_reports.models import DailyReport
from apps.documents.models import (
    DocumentCategory,
    DocumentConfidentiality,
    DocumentType,
)
from apps.estimates.models import Estimate
from apps.expenses.models import Expense
from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
    scope_queryset,
)
from apps.organizations.models import BusinessPermissionCode
from apps.payments.models import Payment
from apps.projects.models import Project

TARGET_FIELDS = (
    "project",
    "contract",
    "estimate",
    "expense",
    "payment",
    "daily_report",
    "field_observation",
)
TARGET_PERMISSIONS = {
    "project": BusinessPermissionCode.PROJECTS_VIEW,
    "contract": BusinessPermissionCode.CONTRACTS_VIEW,
    "estimate": BusinessPermissionCode.ESTIMATES_VIEW,
    "expense": BusinessPermissionCode.EXPENSES_VIEW,
    "payment": BusinessPermissionCode.PAYMENTS_VIEW,
    "daily_report": BusinessPermissionCode.DAILY_REPORTS_VIEW,
    "field_observation": BusinessPermissionCode.FIELD_OBSERVATIONS_VIEW,
}


class DocumentTargetForm(forms.Form):
    project = forms.ModelChoiceField(
        label="پروژه", queryset=Project.objects.none(), required=False
    )
    contract = forms.ModelChoiceField(
        label="قرارداد", queryset=Contract.objects.none(), required=False
    )
    estimate = forms.ModelChoiceField(
        label="برآورد", queryset=Estimate.objects.none(), required=False
    )
    expense = forms.ModelChoiceField(
        label="هزینه", queryset=Expense.objects.none(), required=False
    )
    payment = forms.ModelChoiceField(
        label="پرداخت", queryset=Payment.objects.none(), required=False
    )
    daily_report = forms.ModelChoiceField(
        label="گزارش روزانه", queryset=DailyReport.objects.none(), required=False
    )
    field_observation = forms.ModelChoiceField(
        label="مشاهده میدانی", queryset=FieldObservation.objects.none(), required=False
    )

    def __init__(
        self,
        *args: Any,
        organization: Any = None,
        user: Any = None,
        document: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        querysets = {
            "project": Project.objects.filter(
                organization=organization, deleted_at__isnull=True
            ).order_by("name"),
            "contract": Contract.objects.filter(
                organization=organization, project__deleted_at__isnull=True
            ).order_by("contract_number"),
            "estimate": Estimate.objects.filter(
                organization=organization, project__deleted_at__isnull=True
            ).order_by("estimate_number"),
            "expense": Expense.objects.filter(
                organization=organization, project__deleted_at__isnull=True
            ).order_by("-incurred_on"),
            "payment": Payment.objects.filter(
                organization=organization, project__deleted_at__isnull=True
            ).order_by("-paid_on", "payment_number"),
            "daily_report": DailyReport.objects.filter(
                organization=organization, project__deleted_at__isnull=True
            ).order_by("-reporting_date"),
            "field_observation": FieldObservation.objects.filter(
                organization=organization, project__deleted_at__isnull=True
            ).order_by("-created_at"),
        }
        for field_name, queryset in querysets.items():
            if user is None or not has_business_permission(
                user=user,
                organization=organization,
                permission=TARGET_PERMISSIONS[field_name],
            ):
                queryset = queryset.none()
            if document is not None:
                link_lookup = (
                    "evidence_links__document"
                    if field_name == "field_observation"
                    else "document_links__document"
                )
                queryset = queryset.exclude(**{link_lookup: document})
            self.fields[field_name].queryset = queryset

        if user is not None and organization is not None:
            try:
                membership = get_active_membership(user=user, organization=organization)
            except PermissionDenied:
                self.fields["field_observation"].queryset = FieldObservation.objects.none()
            else:
                if not has_business_permission(
                    user=user,
                    organization=organization,
                    permission=BusinessPermissionCode.FIELD_OBSERVATIONS_CAPTURE,
                    allow_any_scope=True,
                ):
                    self.fields["field_observation"].queryset = FieldObservation.objects.none()
                else:
                    self.fields["field_observation"].queryset = scope_queryset(
                        self.fields["field_observation"].queryset.filter(
                            status=FieldObservationStatus.DRAFT
                        ),
                        membership=membership,
                        project_lookup="project_id",
                        site_lookup="site_id",
                    )

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        selected = [
            cleaned_data.get(field_name)
            for field_name in TARGET_FIELDS
            if cleaned_data.get(field_name) is not None
        ]
        if len(selected) != 1:
            raise forms.ValidationError("دقیقاً یک موجودیت مرتبط برای سند انتخاب کنید.")
        return cleaned_data

    def selected_target(self) -> Any:
        for field_name in TARGET_FIELDS:
            target = self.cleaned_data.get(field_name)
            if target is not None:
                return target
        raise ValueError("موجودیت مرتبط انتخاب نشده است.")


class DocumentCreateForm(DocumentTargetForm):
    document_type = forms.ChoiceField(label="نوع سند", choices=DocumentType.choices)
    title = forms.CharField(label="عنوان سند", max_length=255)
    category = forms.ModelChoiceField(
        label="دسته‌بندی", queryset=DocumentCategory.objects.none(), required=False
    )
    confidentiality = forms.ChoiceField(
        label="سطح محرمانگی",
        choices=DocumentConfidentiality.choices,
        required=False,
        initial=DocumentConfidentiality.INTERNAL,
    )
    access_expires_at = forms.DateTimeField(
        label="پایان دسترسی",
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    reference = forms.CharField(label="شماره مرجع", max_length=120, required=False)
    description = forms.CharField(
        label="توضیحات", widget=forms.Textarea, required=False
    )
    file = forms.FileField(label="فایل نسخه اول")

    def __init__(self, *args: Any, organization: Any = None, **kwargs: Any) -> None:
        super().__init__(*args, organization=organization, **kwargs)
        self.fields["category"].queryset = DocumentCategory.objects.filter(
            organization=organization, archived_at__isnull=True
        ).order_by("name")


class DocumentVersionForm(forms.Form):
    file = forms.FileField(label="فایل نسخه جدید")


class DocumentLinkForm(DocumentTargetForm):
    pass


class DocumentArchiveForm(forms.Form):
    reason = forms.CharField(
        label="دلیل بایگانی", widget=forms.Textarea, max_length=1000
    )
