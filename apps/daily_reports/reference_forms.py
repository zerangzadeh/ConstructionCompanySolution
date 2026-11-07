"""Existing shared selectors and DMS upload fields for Daily Report Create."""

from copy import deepcopy
from itertools import islice
from typing import ClassVar

from django import forms
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from apps.daily_reports.forms import DailyReportForm
from apps.daily_reports.references import (
    authorized_options,
    reference_label,
    reference_queryset,
    reference_scope,
)
from apps.documents.forms import DocumentCreateForm
from apps.documents.models import Document
from apps.documents.services import _validate_uploaded_file
from apps.quality.models import QualityIssue
from apps.safety.models import SafetyIncident
from core.business_choices import SearchChoiceSelect


class ReferenceMultipleSelect(SearchChoiceSelect, forms.SelectMultiple):
    """The existing Tom Select widget already supports multiple selected values."""

    template_name = "daily_reports/widgets/reference_select.html"

    class Media:
        css: ClassVar = {"all": ("daily_reports/reference_choices.css",)}


class DailyReportCreateForm(DailyReportForm):
    linked_safety_incidents = forms.ModelMultipleChoiceField(
        label="رکوردهای ایمنی مرتبط",
        queryset=SafetyIncident.objects.none(),
        required=False,
    )
    linked_quality_issues = forms.ModelMultipleChoiceField(
        label="رکوردهای کیفیت مرتبط",
        queryset=QualityIssue.objects.none(),
        required=False,
    )
    linked_documents = forms.ModelMultipleChoiceField(
        label="اسناد موجود مرتبط", queryset=Document.objects.none(), required=False
    )

    reference_fields: ClassVar = {
        "linked_safety_incidents": "safety",
        "linked_quality_issues": "quality",
        "linked_documents": "documents",
    }

    def __init__(self, *args, organization=None, membership=None, **kwargs):
        super().__init__(
            *args, organization=organization, membership=membership, **kwargs
        )
        self.forbidden_reference_fields = []
        if membership is None or membership.organization_id != getattr(
            organization, "pk", None
        ):
            return
        values = self.data if self.is_bound else self.initial
        try:
            scope = reference_scope(
                actor=membership.user,
                organization=organization,
                project_id=values.get("project"),
                site_id=values.get("site"),
                phase_id=values.get("phase"),
            )
        except PermissionDenied:
            scope = None
        for name, kind in self.reference_fields.items():
            try:
                records = reference_queryset(
                    actor=membership.user,
                    organization=organization,
                    kind=kind,
                    scope=scope,
                )
            except PermissionDenied:
                self.fields.pop(name)
                self.forbidden_reference_fields.append(name)
                continue
            field = self.fields[name]
            field.queryset = records
            field.error_messages["invalid_choice"] = (
                "گزینه انتخاب‌شده قابل دسترسی نیست یا با محدوده گزارش هم‌خوان نیست."
            )
            field.help_text = (
                "ارجاع به سابقه موجود؛ رکورد اصلی تغییر نمی‌کند. پروژه، کارگاه و فاز باید با گزارش یکسان باشد."
                if kind != "documents"
                else "اسنادی که اجازه مشاهده و پیوند آن‌ها را دارید؛ فایل اصلی در مدیریت اسناد نگهداری می‌شود."
            )
            field.label_from_instance = lambda record, k=kind: reference_label(
                record, k
            )
            selected = (
                self.data.getlist(name)
                if self.is_bound and hasattr(self.data, "getlist")
                else values.get(name, [])
            )
            try:
                selected_records = list(
                    authorized_options(
                        actor=membership.user,
                        organization=organization,
                        kind=kind,
                        records=records.filter(pk__in=selected),
                    )
                )
            except (ValueError, forms.ValidationError):
                selected_records = []
            options = {
                str(record.pk): reference_label(record, kind)
                for record in selected_records
            }
            for record in islice(
                authorized_options(
                    actor=membership.user,
                    organization=organization,
                    kind=kind,
                    records=records,
                ),
                40,
            ):
                options[str(record.pk)] = reference_label(record, kind)
            field.widget = ReferenceMultipleSelect(
                attrs={
                    "data-options-url": reverse(
                        "daily_reports:reference_choices", args=[kind]
                    ),
                    "data-business-choice": name,
                    "data-business-names-primary": "true",
                    "data-placeholder": f"جست‌وجو و انتخاب {field.label}…",
                    "data-choice-parents": "project site phase",
                    "data-depends-on": "site project phase",
                    "data-requires-parent": "true",
                    "dir": "rtl",
                },
                choices=list(options.items()),
            )

    def clean(self):
        cleaned = super().clean()
        if any(self.data.get(name) for name in self.forbidden_reference_fields):
            raise forms.ValidationError("اجازه پیوند رکورد انتخاب‌شده را ندارید.")
        return cleaned


class DailyReportUploadForm(forms.Form):
    # Reuse the canonical DMS field types, labels and file validator.
    title = deepcopy(DocumentCreateForm.base_fields["title"])
    document_type = deepcopy(DocumentCreateForm.base_fields["document_type"])
    file = deepcopy(DocumentCreateForm.base_fields["file"])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False
            field.widget.attrs["class"] = "erp-input w-full"
        self.fields[
            "file"
        ].help_text = "اختیاری؛ برای بارگذاری، عنوان و نوع سند را نیز وارد کنید. پس از خطای فرم، فایل را دوباره انتخاب کنید."

    def clean_file(self):
        upload = self.cleaned_data.get("file")
        if upload:
            try:
                _validate_uploaded_file(upload)
            except ValueError as exc:
                raise forms.ValidationError(str(exc)) from exc
        return upload

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("file") or cleaned.get("title"):
            for name in self.fields:
                if not cleaned.get(name) and name not in self.errors:
                    self.add_error(name, "این فیلد برای بارگذاری سند الزامی است.")
        return cleaned
