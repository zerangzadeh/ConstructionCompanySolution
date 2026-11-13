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
from apps.projects.models import Project
from apps.treasury.models import TreasuryMovement
from core.forms import JalaliDateMixin
from core.product_surface import route_exposed

TARGET_FIELDS = (
    "project",
    "contract",
    "estimate",
    "expense",
    "treasury_movement",
    "daily_report",
    "field_observation",
)
TARGET_PERMISSIONS = {
    "project": BusinessPermissionCode.PROJECTS_VIEW,
    "contract": BusinessPermissionCode.CONTRACTS_VIEW,
    "estimate": BusinessPermissionCode.ESTIMATES_VIEW,
    "expense": BusinessPermissionCode.EXPENSES_VIEW,
    "treasury_movement": BusinessPermissionCode.TREASURY_VIEW,
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
    treasury_movement = forms.ModelChoiceField(
        label="حرکت خزانه‌داری", queryset=TreasuryMovement.objects.none(), required=False
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
        membership = None
        if user is not None and organization is not None:
            try:
                membership = get_active_membership(user=user, organization=organization)
            except PermissionDenied:
                pass
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
            "treasury_movement": TreasuryMovement.objects.filter(
                organization=organization, project__deleted_at__isnull=True
            ).order_by("-movement_date", "pk"),
            "daily_report": DailyReport.objects.filter(
                organization=organization, project__deleted_at__isnull=True
            ).order_by("-reporting_date"),
            "field_observation": FieldObservation.objects.filter(
                organization=organization, project__deleted_at__isnull=True
            ).order_by("-created_at"),
        }
        for field_name, queryset in querysets.items():
            if field_name == "treasury_movement" and not route_exposed(
                "treasury:movement_detail"
            ):
                self.fields.pop(field_name)
                continue
            if membership is None or not has_business_permission(
                user=user,
                organization=organization,
                permission=TARGET_PERMISSIONS[field_name],
                allow_any_scope=True,
            ):
                queryset = queryset.none()
            else:
                queryset = scope_queryset(
                    queryset,
                    membership=membership,
                    project_lookup="id" if field_name == "project" else "project_id",
                    site_lookup=(
                        "site_id"
                        if any(
                            field.name == "site"
                            for field in queryset.model._meta.fields
                        )
                        else None
                    ),
                    include_site_parent=field_name == "project",
                )
            if document is not None:
                link_lookup = (
                    (
                        "evidence_links__document"
                        if field_name == "field_observation"
                        else "typed_document_links__document"
                    )
                    if field_name in {"field_observation", "treasury_movement"}
                    else "document_links__document"
                )
                queryset = queryset.exclude(**{link_lookup: document})
            self.fields[field_name].queryset = queryset

        if user is not None and organization is not None:
            try:
                membership = get_active_membership(user=user, organization=organization)
            except PermissionDenied:
                self.fields[
                    "field_observation"
                ].queryset = FieldObservation.objects.none()
            else:
                if not has_business_permission(
                    user=user,
                    organization=organization,
                    permission=BusinessPermissionCode.FIELD_OBSERVATIONS_CAPTURE,
                    allow_any_scope=True,
                ):
                    self.fields[
                        "field_observation"
                    ].queryset = FieldObservation.objects.none()
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


class DocumentCreateForm(JalaliDateMixin, DocumentTargetForm):
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


class _ContextualIntentForm(forms.Form):
    """Bind a form to the server-resolved source, actor and tenant."""

    context_token = forms.CharField(widget=forms.HiddenInput)

    def bind_context(self, *, context, user, organization):
        from django.core import signing

        from core.business_choices import InheritedParentInput, inherit_business_parent

        self.association_context = context
        self.actor = user
        self.organization = organization
        kind = context.source.kind
        self.intent = {
            "kind": kind,
            "target": str(context.target.pk),
            "user": str(user.pk),
            "organization": str(organization.pk),
        }
        self.fields["context_token"].widget = InheritedParentInput(
            signing.dumps(self.intent, salt="documents.contextual-association.v1")
        )
        self.fields["context_token"].required = True
        self.fields["context_token"].error_messages["required"] = (
            "زمینه فرم معتبر نیست؛ صفحه را دوباره باز کنید."
        )
        from apps.documents.presentation import SOURCE_ROUTES

        inherit_business_parent(
            self, kind, context.target, detail_route=SOURCE_ROUTES[kind][0]
        )

    def clean(self):
        from django.core import signing

        cleaned = super().clean()
        kind = self.association_context.source.kind
        forbidden = set(TARGET_FIELDS) - {kind}
        forbidden |= {
            "payment",
            "project_site",
            "organization",
            "organization_id",
            "related_to",
            "related_id",
            "target_type",
            "target_id",
            "next",
            "return_url",
            "return_to",
        }
        if any(self.data.get(name) for name in forbidden) or any(
            len(self.data.getlist(name)) != 1
            for name in (kind, "context_token")
            if hasattr(self.data, "getlist")
        ):
            raise forms.ValidationError("زمینه ارسالی با این فرم هم‌خوان نیست.")
        try:
            intent = signing.loads(
                cleaned.get("context_token", ""),
                salt="documents.contextual-association.v1",
                max_age=3600,
            )
        except signing.BadSignature as exc:
            raise forms.ValidationError(
                "زمینه فرم معتبر نیست یا مهلت آن پایان یافته است؛ دوباره تلاش کنید."
            ) from exc
        if intent != self.intent:
            raise forms.ValidationError("زمینه ارسالی با این فرم هم‌خوان نیست.")
        return cleaned


class ContextualDocumentCreateForm(_ContextualIntentForm, DocumentCreateForm):
    def __init__(self, *args, context, user, organization, **kwargs):
        super().__init__(*args, user=user, organization=organization, **kwargs)
        for name in TARGET_FIELDS:
            if name != context.source.kind:
                self.fields.pop(name, None)
        self.bind_context(context=context, user=user, organization=organization)

    def clean_file(self):
        from apps.documents.services import _validate_uploaded_file

        upload = self.cleaned_data["file"]
        try:
            _validate_uploaded_file(upload)
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc
        return upload


class ContextualDocumentLinkForm(_ContextualIntentForm):
    document = forms.ModelChoiceField(
        label="سند موجود",
        queryset=None,
        error_messages={
            "invalid_choice": "سند انتخاب‌شده قابل پیوند نیست یا قبلاً پیوند خورده است.",
            "required": "یک سند را انتخاب کنید.",
        },
    )

    def __init__(self, *args, context, user, organization, **kwargs):
        from django.urls import reverse

        from apps.documents.association import (
            association_candidates,
            association_choices,
            document_choice_label,
        )
        from apps.documents.presentation import _sources
        from core.business_choices import SearchChoiceSelect

        super().__init__(*args, **kwargs)
        kind = context.source.kind
        self.fields[kind] = forms.ModelChoiceField(
            label=context.source.label,
            queryset=_sources(kind=kind, user=user, organization=organization),
        )
        self.bind_context(context=context, user=user, organization=organization)
        field = self.fields["document"]
        field.queryset = association_candidates(
            user=user, organization=organization, context=context
        )
        field.label_from_instance = document_choice_label
        rows, _ = association_choices(
            user=user, organization=organization, context=context
        )
        selected = self.data.get("document") if self.is_bound else None
        if selected and all(str(row.pk) != selected for row in rows):
            try:
                chosen = field.clean(selected)
                from apps.documents.association import authorized_association_document

                chosen = authorized_association_document(
                    user=user, organization=organization, identifier=chosen.pk
                )
            except (forms.ValidationError, PermissionDenied, ValueError):
                pass
            else:
                rows.insert(0, chosen)
        field.widget = SearchChoiceSelect(
            attrs={
                "data-options-url": reverse(
                    "documents:contextual-choices", args=[kind, context.target.pk]
                ),
                "data-business-choice": "document",
                "data-business-names-primary": "true",
                "data-placeholder": "جست‌وجو با عنوان یا شماره سند…",
                "dir": "rtl",
            },
            choices=[("", "انتخاب سند")]
            + [(str(row.pk), document_choice_label(row)) for row in rows],
        )

    def clean_document(self):
        from apps.documents.association import authorized_association_document

        document = self.cleaned_data["document"]
        try:
            return authorized_association_document(
                user=self.actor, organization=self.organization, identifier=document.pk
            )
        except PermissionDenied as exc:
            raise forms.ValidationError(
                self.fields["document"].error_messages["invalid_choice"]
            ) from exc
