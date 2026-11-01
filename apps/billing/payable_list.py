"""Read-only list presentation over the existing authorized certificate selector."""

from typing import Any

from django import forms
from django.db.models import Q, QuerySet
from django.http import HttpRequest
from django.urls import reverse

from apps.contracts.models import Contract
from apps.organizations.authorization import (
    has_business_permission,
    permission_supports_object_scope,
)
from apps.organizations.models import BusinessPermissionCode
from core.jalali import format_jalali
from core.list_filters import build_filter_bar, paginate_table, table_pagination_query

from .models import PayableCertificate, PayableCertificateStatus


class PayableCertificateListForm(forms.Form):
    q = forms.CharField(label="جست‌وجوی گواهی", required=False, max_length=200)
    status = forms.ChoiceField(
        label="وضعیت",
        required=False,
        choices=[("", "همه وضعیت‌ها"), *PayableCertificateStatus.choices],
    )
    contract = forms.ModelChoiceField(
        label="پیمان جزء",
        required=False,
        queryset=Contract.objects.none(),
        empty_label="همه پیمان‌ها",
    )
    period = forms.ChoiceField(label="دوره", required=False)
    number = forms.IntegerField(
        label="شماره گواهی", required=False, min_value=1, max_value=2147483647
    )
    counterparty = forms.CharField(label="طرف قرارداد", required=False, max_length=200)

    def __init__(self, *args, certificates, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contract"].queryset = Contract.objects.filter(
            pk__in=certificates.values("contract_id")
        ).order_by("contract_number", "pk")
        self.fields["contract"].label_from_instance = lambda row: row.contract_number
        self.fields["period"].choices = [("", "همه دوره‌ها")] + [
            (f"{start}/{end}", f"{format_jalali(start)} — {format_jalali(end)}")
            for start, end in certificates.order_by("-period_start", "-period_end")
            .values_list("period_start", "period_end")
            .distinct()
        ]
        for field in self.fields.values():
            field.widget.attrs["class"] = "erp-input w-full"
            field.error_messages["invalid_choice"] = (
                "گزینه معتبر و مجاز را انتخاب کنید."
            )
            field.error_messages["max_length"] = "عبارت جست‌وجو بیش از حد طولانی است."
        self.fields["q"].widget.attrs.update(
            {"type": "search", "placeholder": "شماره گواهی، پیمان یا طرف قرارداد…"}
        )


def payable_list_context(
    request: HttpRequest, certificates: QuerySet[PayableCertificate]
) -> dict[str, Any]:
    """Narrow the supplied scope only; never resolve authority from GET state."""
    scoped_has_records = certificates.exists()
    form = PayableCertificateListForm(request.GET, certificates=certificates)
    if not form.is_valid():
        certificates = certificates.none()
    else:
        data = form.cleaned_data
        if query := data["q"]:
            match = Q(contract__contract_number__icontains=query) | Q(
                party_identity_snapshot__display_name__icontains=query
            )
            if query.isdecimal() and len(query) <= 9:
                match |= Q(certificate_number=int(query))
            certificates = certificates.filter(match)
        if data["status"]:
            certificates = certificates.filter(status=data["status"])
        if data["contract"]:
            certificates = certificates.filter(contract=data["contract"])
        if data["period"]:
            start, end = data["period"].split("/")
            certificates = certificates.filter(period_start=start, period_end=end)
        if data["number"]:
            certificates = certificates.filter(certificate_number=data["number"])
        if data["counterparty"]:
            certificates = certificates.filter(
                party_identity_snapshot__display_name__icontains=data["counterparty"]
            )
    sort_fields = {
        "number": ("certificate_number", "revision_number", "pk"),
        "contract": ("contract__contract_number", "pk"),
        "counterparty": ("party_identity_snapshot__display_name", "pk"),
        "period": ("period_start", "period_end", "pk"),
        "gross": ("gross_amount", "pk"),
        "adjustment": ("adjustment_amount", "pk"),
        "net": ("net_amount", "pk"),
        "status": ("status", "pk"),
        "date": ("created_at", "pk"),
    }
    labels = dict(
        zip(
            sort_fields,
            (
                "شماره / ویرایش",
                "پیمان جزء",
                "طرف قرارداد",
                "دوره",
                "مبلغ ناخالص",
                "کسورات",
                "خالص قابل پرداخت",
                "وضعیت",
                "تاریخ ثبت",
            ),
        )
    )
    page = paginate_table(certificates, request, sort_fields=sort_fields)
    bar = build_filter_bar(
        request,
        form=form,
        quick_fields=("status", "contract", "period"),
        secondary_fields=("number", "counterparty"),
        result_count=page.paginator.count,
        result_label="گواهی پرداخت",
    )
    key = request.GET.get("sort", "").strip()
    return {
        "certificates": page.object_list,
        "scoped_has_records": scoped_has_records,
        "filter_bar": bar,
        "clear_filters_url": bar["clear_url"],
        "page_obj": page,
        "pagination_query": table_pagination_query(request),
        "sort_options": [{"key": key, "label": label} for key, label in labels.items()],
        "list_sort": {
            "label": labels.get(key, "ترتیب پیمان و شماره گواهی"),
            "descending": key in labels
            and request.GET.get("direction", "asc").strip().lower() == "desc",
        },
        "create_url": reverse("billing:payable_certificate_create")
        if has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=BusinessPermissionCode.PAYABLE_CERTIFICATES_CREATE,
            allow_any_scope=permission_supports_object_scope(
                BusinessPermissionCode.PAYABLE_CERTIFICATES_CREATE
            ),
        )
        else None,
        "can_view_measurements": has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=BusinessPermissionCode.PAYABLE_MEASUREMENTS_VIEW,
            allow_any_scope=permission_supports_object_scope(
                BusinessPermissionCode.PAYABLE_MEASUREMENTS_VIEW
            ),
        ),
    }
