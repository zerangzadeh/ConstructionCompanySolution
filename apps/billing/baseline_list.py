"""Read-only presentation over the existing authorized baseline selector."""

from typing import Any

from django import forms
from django.db.models import Q, QuerySet
from django.http import Http404, HttpRequest

from apps.contracts.models import Contract
from apps.projects.models import Project
from core.list_filters import build_filter_bar, paginate_table, table_pagination_query

from .journey_views import breadcrumb_contract, journey_breadcrumbs
from .models import ProjectBaseline, ProjectBaselineStatus

TITLE = "مبنای متره و صورت‌وضعیت"


class BaselineListForm(forms.Form):
    q = forms.CharField(label="جست‌وجو", required=False, max_length=200)
    contract_filter = forms.ModelChoiceField(
        label="قرارداد",
        required=False,
        queryset=Contract.objects.none(),
        empty_label="همه قراردادها",
    )
    project = forms.ModelChoiceField(
        label="پروژه",
        required=False,
        queryset=Project.objects.none(),
        empty_label="همه پروژه‌ها",
    )
    status = forms.ChoiceField(
        label="وضعیت",
        required=False,
        choices=[("", "همه وضعیت‌ها"), *ProjectBaselineStatus.choices],
    )

    def __init__(self, *args, records, scoped=False, **kwargs):
        super().__init__(*args, **kwargs)
        if scoped:
            for name in ("q", "contract_filter", "project", "status"):
                self.fields.pop(name)
        else:
            self.fields["contract_filter"].queryset = Contract.objects.filter(
                pk__in=records.values("contract_id")
            ).order_by("contract_number")
            self.fields["contract_filter"].label_from_instance = lambda row: (
                row.contract_number
            )
            self.fields["project"].queryset = Project.objects.filter(
                pk__in=records.values("project_id")
            ).order_by("name")
            self.fields["q"].widget.attrs.update(
                {"type": "search", "placeholder": "جست‌وجوی قرارداد یا پروژه…"}
            )
        for field in self.fields.values():
            field.widget.attrs["class"] = "erp-input w-full"
            field.error_messages["invalid_choice"] = (
                "گزینه معتبر و مجاز را انتخاب کنید."
            )


def baseline_list_context(
    request: HttpRequest, records: QuerySet[ProjectBaseline]
) -> dict[str, Any]:
    contract = None
    if "contract" in request.GET:
        contract = breadcrumb_contract(request)
        if contract is None and len(request.GET.getlist("contract")) == 1:
            from apps.organizations.form_scoping import normalized_uuid

            identifier = normalized_uuid(request.GET["contract"])
            authorized_row = (
                records.filter(contract_id=identifier).first() if identifier else None
            )
            contract = authorized_row.contract if authorized_row else None
        if contract is None or contract.direction != "receivable":
            raise Http404("قرارداد یافت نشد.")
        records = records.filter(contract=contract)
    count = records.count()
    single = records.first() if contract and count == 1 else None
    # Do not redirect filtered results or hide historical versions behind current.
    redirect_id = (
        single.pk
        if single
        and single.status == ProjectBaselineStatus.APPROVED
        and not any(key != "contract" for key in request.GET)
        else None
    )
    form = BaselineListForm(request.GET, records=records, scoped=bool(contract))
    if not form.is_valid():
        records = records.none()
    else:
        data = form.cleaned_data
        if query := data.get("q"):
            records = records.filter(
                Q(contract__title__icontains=query)
                | Q(contract__contract_number__icontains=query)
                | Q(project__name__icontains=query)
            )
        for parameter, lookup in (
            ("contract_filter", "contract"),
            ("project", "project"),
            ("status", "status"),
        ):
            if data.get(parameter):
                records = records.filter(**{lookup: data[parameter]})
    fields = {
        "contract": "contract__contract_number",
        "project": "project__name",
        "version": "version",
        "date": "effective_date",
        "ceiling": "effective_ceiling",
        "status": "status",
    }
    labels = dict(
        zip(fields, ("قرارداد", "پروژه", "نسخه", "تاریخ اثر", "سقف مؤثر", "وضعیت"))
    )
    page = paginate_table(
        records,
        request,
        sort_fields={key: (value, "pk") for key, value in fields.items()},
        default_ordering=("-version", "pk") if contract else ("-created_at", "pk"),
    )
    if contract:
        # Scoped mode intentionally offers no contract/project search controls.
        bar = None
    else:
        bar = build_filter_bar(
            request,
            form=form,
            quick_fields=("contract_filter", "project", "status"),
            result_count=page.paginator.count,
            result_label="مبنا",
        )
    return {
        "selected_contract": contract,
        "baselines": page.object_list,
        "page_obj": page,
        "scoped_has_records": count > 0,
        "filter_bar": bar,
        "pagination_query": table_pagination_query(request),
        "pagination_rendered": True,
        "redirect_baseline_id": redirect_id,
        "list_sort": {
            "key": request.GET.get("sort", ""),
            "label": labels.get(
                request.GET.get("sort"),
                "جدیدترین نسخه" if contract else "جدیدترین مبنا",
            ),
            "descending": request.GET.get("direction") == "desc",
        },
        "sort_options": [
            {"key": key, "label": label}
            for key, label in labels.items()
            if not contract or key not in ("contract", "project")
        ],
        "page_breadcrumbs": journey_breadcrumbs(request, TITLE, contract),
    }
