"""Shared version selection within existing source-owned operations."""

from __future__ import annotations

from uuid import uuid4

from django import forms
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from apps.documents.evidence import (
    EvidenceSource,
    choice_page,
    eligible_versions,
    picker_source,
    version_label,
)
from apps.documents.models import DocumentVersion
from core.business_choices import InheritedParentInput, SearchChoiceSelect


def configure_version_picker(form, name, *, user, organization, kind, identifier=None):
    """Keep native queryset validation and the existing searchable widget."""
    field = form.fields[name]
    versions = DocumentVersion.objects.none()
    if user is not None:
        try:
            source = picker_source(
                user=user, organization=organization, kind=kind, identifier=identifier
            )
            versions = eligible_versions(
                user=user, organization=organization, kind=kind, source=source
            )
        except PermissionDenied:
            pass
    field.queryset = versions
    field.label_from_instance = version_label
    field.error_messages.update(
        invalid_choice="نسخه انتخاب‌شده در دسترس نیست یا برای این عملیات مجاز نیست."
    )
    rows, _ = choice_page(versions)
    selected = (
        form.data.getlist(name)
        if form.is_bound and hasattr(form.data, "getlist")
        else []
    )
    if form.is_bound and not selected and form.data.get(name):
        selected = [form.data[name]]
    for value in selected:
        try:
            chosen = versions.filter(pk=value).first()
        except (ValueError, forms.ValidationError):
            continue
        if chosen is not None and all(chosen.pk != row.pk for row in rows):
            rows.insert(0, chosen)
    route = (
        "documents:evidence-choices"
        if identifier
        else "documents:commercial-evidence-choices"
    )
    args = [kind, identifier] if identifier else [kind]
    field.widget = SearchChoiceSelect(
        attrs={
            "data-options-url": reverse(route, args=args),
            "data-business-choice": name,
            "data-business-names-primary": "true",
            "data-placeholder": "جست‌وجوی عنوان یا شماره سند و انتخاب نسخه شاهد…",
            "dir": "rtl",
        },
        choices=[("", "انتخاب نسخه شاهد")]
        + [(str(row.pk), version_label(row)) for row in rows],
    )
    if isinstance(field, forms.ModelMultipleChoiceField):
        field.widget.allow_multiple_selected = True
    field.help_text = "عنوان سند و شماره نسخه انتخاب‌شده در همین کادر نمایش داده می‌شود؛ نسخه جاری به‌طور خودکار جایگزین شاهد نمی‌شود."


class EvidenceRegistrationForm(forms.Form):
    versions = forms.ModelMultipleChoiceField(
        label="نسخه‌های شاهد بررسی",
        queryset=DocumentVersion.objects.none(),
        required=False,
    )
    version = forms.ModelChoiceField(
        label="نسخه شاهد", queryset=DocumentVersion.objects.none()
    )
    label = forms.CharField(label="عنوان شاهد", max_length=255)
    reason = forms.CharField(
        label="دلیل ارسال رکورد", widget=forms.Textarea(attrs={"rows": 3})
    )
    operation_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid4)
    context_token = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, source: EvidenceSource, user, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.intent = {
            "kind": source.kind,
            "source": str(source.target.pk),
            "user": str(user.pk),
            "organization": str(organization.pk),
        }
        self.fields["context_token"].widget = InheritedParentInput(
            signing.dumps(self.intent, salt="documents.evidence-registration.v1")
        )
        if source.kind in {"safety", "quality"}:
            for name in ("version", "label", "operation_key"):
                self.fields.pop(name)
            name = "versions"
        else:
            self.fields.pop("versions")
            self.fields.pop("reason")
            if source.kind in {"contractual", "material"}:
                self.fields.pop("operation_key")
            if source.kind != "contractual":
                self.fields.pop("label")
            name = "version"
        configure_version_picker(
            self,
            name,
            user=user,
            organization=organization,
            kind=source.kind,
            identifier=source.target.pk,
        )
        if source.kind == "material":
            self.fields[
                "version"
            ].help_text = "فقط نسخه جاری سند قابل ثبت است. شماره نسخه انتخاب‌شده پیش از ثبت بررسی می‌شود؛ تغییر هم‌زمان نسخه، نیازمند انتخاب دوباره است."

    def clean(self):
        cleaned = super().clean()
        try:
            signed = signing.loads(
                cleaned.get("context_token", ""),
                salt="documents.evidence-registration.v1",
                max_age=3600,
            )
        except signing.BadSignature as exc:
            raise forms.ValidationError(
                "مهلت فرم پایان یافته یا زمینه معتبر نیست؛ دوباره تلاش کنید."
            ) from exc
        if signed != self.intent or any(
            self.data.get(name)
            for name in (
                "next",
                "return_url",
                "organization",
                "organization_id",
                "target_id",
                "target_type",
            )
        ):
            raise forms.ValidationError("زمینه ارسالی با این فرم هم‌خوان نیست.")
        return cleaned
