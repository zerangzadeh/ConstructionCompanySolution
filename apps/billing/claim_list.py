"""Read-only Claims list presentation; supplied queryset owns all authorization."""

from typing import Any

from django import forms
from django.db.models import Count, Q, QuerySet
from django.http import HttpRequest

from apps.contracts.models import Contract
from apps.projects.models import Project
from core.jalali import format_jalali
from core.list_filters import build_filter_bar, paginate_table, table_pagination_query

from .models import ProgressClaim


class ClaimListForm(forms.Form):
    q = forms.CharField(label="جست‌وجو", required=False, max_length=200)
    status = forms.ChoiceField(
        label="وضعیت",
        required=False,
        choices=[("", "همه وضعیت‌ها"), *ProgressClaim._meta.get_field("status").choices],
    )
    project = forms.ModelChoiceField(
        label="پروژه",
        required=False,
        queryset=Project.objects.none(),
        empty_label="همه پروژه‌ها",
    )
    claim_contract = forms.ModelChoiceField(
        label="قرارداد",
        required=False,
        queryset=Contract.objects.none(),
        empty_label="همه قراردادها",
    )
    period = forms.ChoiceField(label="دوره", required=False)

    def __init__(self, *args, claims, contract_scoped, project_scoped, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = Project.objects.filter(
            pk__in=claims.values("project_id")
        ).order_by("name", "pk")
        self.fields["claim_contract"].queryset = Contract.objects.filter(
            pk__in=claims.values("contract_id")
        ).order_by("contract_number", "pk")
        self.fields["claim_contract"].label_from_instance = lambda row: (
            f"{row.contract_number} · {row.title}"
        )
        self.fields["period"].choices = [("", "همه دوره‌ها")] + [
            (f"{start}/{end}", f"{format_jalali(start)} — {format_jalali(end)}")
            for start, end in claims.order_by("-period_start", "-period_end")
            .values_list("period_start", "period_end")
            .distinct()
        ]
        if contract_scoped:
            del self.fields["project"]
            del self.fields["claim_contract"]
        elif project_scoped:
            del self.fields["project"]
        for field in self.fields.values():
            field.widget.attrs["class"] = "erp-input w-full"
            field.error_messages["invalid_choice"] = (
                "گزینه معتبر و مجاز را انتخاب کنید."
            )
        self.fields["q"].widget.attrs.update(
            type="search",
            placeholder="شماره صورت‌وضعیت…"
            if contract_scoped
            else "قرارداد، پروژه یا شماره صورت‌وضعیت…",
        )


def claim_list_context(
    request: HttpRequest, claims: QuerySet[ProgressClaim], *, contract_scoped: bool
) -> dict[str, Any]:
    """Filters only narrow the existing receivable, tenant and project scope."""
    has_records = claims.exists()
    form = ClaimListForm(
        request.GET,
        claims=claims,
        contract_scoped=contract_scoped,
        project_scoped="project_id" in request.GET,
    )
    if not form.is_valid():
        claims = claims.none()
    else:
        data = form.cleaned_data
        if query := data["q"]:
            match = (
                Q(contract__title__icontains=query)
                | Q(contract__contract_number__icontains=query)
                | Q(project__name__icontains=query)
            )
            if query.isdecimal() and len(query) <= 10:
                match |= Q(claim_number=int(query))
            claims = claims.filter(match)
        if data["status"]:
            claims = claims.filter(status=data["status"])
        if data.get("project"):
            claims = claims.filter(project=data["project"])
        if data.get("claim_contract"):
            claims = claims.filter(contract=data["claim_contract"])
        if data["period"]:
            start, end = data["period"].split("/")
            claims = claims.filter(period_start=start, period_end=end)
    counts = dict(claims.order_by().values_list("status").annotate(total=Count("pk")))
    fields = {
        "number": ("claim_number", "revision_number", "pk"),
        "contract": ("contract__title", "pk"),
        "period": ("period_start", "period_end", "pk"),
        "gross": ("gross_amount", "pk"),
        "deductions": ("adjustment_amount", "pk"),
        "amount": ("net_amount", "pk"),
        "status": ("status", "pk"),
        "date": ("created_at", "pk"),
    }
    labels = dict(
        zip(
            fields,
            (
                "شماره / نسخه",
                "قرارداد / پروژه",
                "دوره",
                "مبلغ ناخالص",
                "کسورات و اضافات",
                "خالص صورت‌وضعیت",
                "وضعیت",
                "تاریخ ایجاد",
            ),
        )
    )
    page = paginate_table(
        claims, request, sort_fields=fields, default_ordering=("-created_at", "pk")
    )
    bar = build_filter_bar(
        request,
        form=form,
        quick_fields=("status", "period"),
        secondary_fields=tuple(
            name for name in ("project", "claim_contract") if name in form.fields
        ),
        context={
            key: request.GET[key]
            for key in ("contract", "project_id")
            if key in request.GET
        },
        result_count=page.paginator.count,
        result_label="صورت‌وضعیت",
    )
    key = request.GET.get("sort", "").strip()
    return {
        "claims": page.object_list,
        "page_obj": page,
        "filter_bar": bar,
        "clear_filters_url": bar["clear_url"],
        "scoped_has_records": has_records,
        "pagination_query": table_pagination_query(request),
        "sort_options": [{"key": key, "label": label} for key, label in labels.items()],
        "list_sort": {
            "label": labels.get(key, "تاریخ ایجاد · جدیدترین"),
            "descending": key not in labels
            or request.GET.get("direction", "asc").lower() == "desc",
        },
        "status_summary": [
            {"status": value, "label": label, "count": counts.get(value, 0)}
            for value, label in ProgressClaim._meta.get_field("status").choices
            if value in ("draft", "submitted", "returned", "approved")
            or counts.get(value)
        ],
    }
