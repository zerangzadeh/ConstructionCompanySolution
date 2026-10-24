"""Presentation of existing closeout snapshots and authorized DMS references."""

from django import forms
from django.core.exceptions import PermissionDenied

from apps.documents.models import DocumentVersion
from apps.documents.services import get_organization_documents

from .project_closeout_catalog import PROJECT_CLOSEOUT_FAMILIES


class CloseoutEvidenceForm(forms.Form):
    document_version_id = forms.ModelChoiceField(
        queryset=DocumentVersion.objects.none(), label="سند و نسخه دقیق"
    )
    purpose = forms.ChoiceField(
        choices=(
            ("closeout_support", "شاهد پشتیبان اختتام"),
            ("custom", "هدف سفارشی موجود"),
        ),
        initial="closeout_support",
        required=False,
        label="هدف شاهد",
    )
    evidence_role = forms.CharField(required=False, max_length=80, label="هدف سفارشی")

    def __init__(self, *args, organization, actor, **kwargs):
        super().__init__(*args, **kwargs)
        documents = get_organization_documents(user=actor, organization=organization)
        versions = (
            DocumentVersion.objects.filter(
                organization=organization, document__in=documents
            )
            .select_related("document")
            .prefetch_related("processing_assessments")
        )
        available_ids = [version.pk for version in versions if version.is_available]
        self.fields["document_version_id"].queryset = versions.filter(
            pk__in=available_ids
        )
        self.fields["document_version_id"].label_from_instance = lambda version: (
            f"{version.document.title} — نسخه {version.version_number} — {version.original_file_name}"
        )

    def clean(self):
        data = super().clean()
        purpose = data.pop("purpose", "")
        if purpose == "custom" and not data.get("evidence_role"):
            self.add_error("evidence_role", "هدف سفارشی موجود را وارد کنید.")
        elif purpose == "closeout_support" or not data.get("evidence_role"):
            data["evidence_role"] = "closeout_support"
        return data


AUTHORITY_LABELS = {
    "Projects and Project Controls": "پروژه‌ها و کنترل پروژه",
    "Contracts": "قراردادها",
    "Billing, AP/AR, Treasury and Accounting": "صورت‌وضعیت، پرداختنی‌ها، دریافتنی‌ها، خزانه‌داری و حسابداری",
    "Reporting/Reconciliation and native source domains": "گزارش‌گیری، تطبیق و دامنه‌های منبع",
    "DMS and each source domain": "مدیریت اسناد و هر دامنه منبع",
    "Inventory": "انبار",
    "Equipment and Fixed Assets": "تجهیزات و دارایی‌های ثابت",
    "Field Operations, HSE and Quality": "عملیات میدانی، ایمنی و کیفیت",
    "Knowledge": "دانش",
}


def closeout_presentation(*, case, actor):
    rows = []
    for item in case.current_assessment.items.all() if case.current_assessment else ():
        spec = PROJECT_CLOSEOUT_FAMILIES.get(item.family_code, {})
        rows.append(
            {
                "item": item,
                "name": spec.get("persian_name", "خانواده منبع"),
                "authority": AUTHORITY_LABELS.get(
                    item.authority_domain, item.authority_domain
                ),
            }
        )
    actions = {
        "coordinate": "ثبت هماهنگی",
        "accept": "پذیرش ارزیابی",
        "reject": "رد ارزیابی",
        "reopen": "بازگشایی",
        "cancel": "لغو",
        "assess": "ارزیابی منابع",
    }
    events = [
        {"event": event, "label": actions.get(event.action, "ثبت رویداد پرونده")}
        for event in case.events.all()
    ]
    try:
        documents = get_organization_documents(
            user=actor, organization=case.organization
        )
        evidence = case.evidence_links.filter(
            document_version__document__in=documents
        ).select_related("document_version__document")
        form = CloseoutEvidenceForm(organization=case.organization, actor=actor)
    except PermissionDenied:
        evidence, form = (), None
    return {
        "closeout_rows": rows,
        "closeout_events": events,
        "closeout_evidence": evidence,
        "evidence_form": form,
    }
