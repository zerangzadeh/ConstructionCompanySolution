"""Read-only list presentation over the existing authorized report selector."""

from typing import Any

from django import forms
from django.db.models import Count, Q, QuerySet
from django.http import HttpRequest

from apps.projects.models import Project, ProjectPhase, ProjectSite
from core.forms import JalaliDateMixin, ParentChoiceSelect
from core.list_filters import (
    build_filter_bar,
    paginate_table,
    parse_user_date,
    table_pagination_query,
)

from .models import DailyReport, DailyReportStatus


class DailyReportListForm(JalaliDateMixin, forms.Form):
    q = forms.CharField(label="جست‌وجو", required=False, max_length=200)
    project_filter = forms.ModelChoiceField(
        label="پروژه",
        queryset=Project.objects.none(),
        required=False,
        empty_label="همه پروژه‌ها",
    )
    site_filter = forms.ModelChoiceField(
        label="کارگاه",
        queryset=ProjectSite.objects.none(),
        required=False,
        empty_label="همه کارگاه‌ها",
    )
    status = forms.ChoiceField(
        label="وضعیت",
        required=False,
        choices=[("", "همه وضعیت‌ها"), *DailyReportStatus.choices],
    )
    reporting_date_from = forms.DateField(label="تاریخ گزارش از", required=False)
    reporting_date_to = forms.DateField(label="تاریخ گزارش تا", required=False)
    phase_filter = forms.ModelChoiceField(
        label="فاز",
        queryset=ProjectPhase.objects.none(),
        required=False,
        empty_label="همه فازها",
    )
    author = forms.CharField(label="نویسنده", required=False, max_length=150)

    def __init__(self, data=None, *args, records, **kwargs):
        if data is not None:
            data = data.copy()
            for name in ("reporting_date_from", "reporting_date_to"):
                if parsed := parse_user_date(data.get(name, "")):
                    data[name] = parsed.isoformat()
        super().__init__(data, *args, **kwargs)
        # Choices come exclusively from the already authorized report queryset.
        for field, model, relation in (
            ("project_filter", Project, "project_id"),
            ("site_filter", ProjectSite, "site_id"),
            ("phase_filter", ProjectPhase, "phase_id"),
        ):
            self.fields[field].queryset = model.objects.filter(
                pk__in=records.values(relation)
            ).order_by("name", "pk")
            self.fields[field].label_from_instance = lambda row: row.name
        # Retain legacy text-filter URLs without confusing them with selectors.
        for name, label in (("project", "نام پروژه / کارگاه"), ("phase", "نام فاز")):
            if self.data.get(name):
                self.fields[name] = forms.CharField(label=label, required=False)
        self.fields["q"].widget = forms.TextInput(
            attrs={
                "type": "search",
                "placeholder": "جست‌وجوی پروژه، کارگاه یا شرح گزارش…",
            }
        )
        for field in self.fields.values():
            field.widget.attrs["class"] = "erp-input w-full"
            field.error_messages["invalid_choice"] = (
                "گزینه معتبر و مجاز را انتخاب کنید."
            )
        for child, parent, attribute in (
            ("site_filter", "project_filter", "project_id"),
            ("phase_filter", "site_filter", "site_id"),
        ):
            field = self.fields[child]
            field.widget = ParentChoiceSelect(
                parent_attribute=attribute,
                attrs={
                    **field.widget.attrs,
                    "data-daily-parent": self[parent].id_for_label,
                },
                choices=field.choices,
            )

    def clean(self):
        data = super().clean()
        start, end = data.get("reporting_date_from"), data.get("reporting_date_to")
        if start and end and start > end:
            raise forms.ValidationError(
                "تاریخ پایان باید برابر یا پس از تاریخ شروع باشد."
            )
        return data


def daily_report_list_context(
    request: HttpRequest, records: QuerySet[DailyReport]
) -> dict[str, Any]:
    summary = records.aggregate(
        total=Count("pk"),
        draft=Count("pk", filter=Q(status=DailyReportStatus.DRAFT)),
        submitted=Count("pk", filter=Q(status=DailyReportStatus.SUBMITTED)),
        approved=Count("pk", filter=Q(status=DailyReportStatus.APPROVED)),
    )
    form = DailyReportListForm(request.GET, records=records)
    if not form.is_valid():
        records = records.none()
    else:
        data = form.cleaned_data
        if query := data.get("q"):
            records = records.filter(
                Q(project__name__icontains=query)
                | Q(site__name__icontains=query)
                | Q(work_performed__icontains=query)
            )
        for parameter, lookup in (
            ("project_filter", "project"),
            ("site_filter", "site"),
            ("phase_filter", "phase"),
            ("status", "status"),
            ("reporting_date_from", "reporting_date__gte"),
            ("reporting_date_to", "reporting_date__lte"),
            ("author", "created_by__username__icontains"),
            ("phase", "phase__name__icontains"),
        ):
            if data.get(parameter):
                records = records.filter(**{lookup: data[parameter]})
        if project := data.get("project"):
            records = records.filter(
                Q(project__name__icontains=project) | Q(site__name__icontains=project)
            )
    sorts = (
        ("project", "پروژه / کارگاه", "project__name"),
        ("reporting_date", "تاریخ گزارش", "reporting_date"),
        ("phase", "فاز", "phase__name"),
        ("labor_count", "نیروی کار", "labor_count"),
        ("status", "وضعیت", "status"),
        ("author", "نویسنده", "created_by__username"),
    )
    page = paginate_table(
        records,
        request,
        sort_fields={key: (field, "pk") for key, _, field in sorts},
        default_ordering=("-reporting_date", "-created_at", "pk"),
    )
    secondary = ["reporting_date_from", "reporting_date_to", "phase_filter", "author"]
    secondary += [name for name in ("project", "phase") if name in form.fields]
    bar = build_filter_bar(
        request,
        form=form,
        quick_fields=("project_filter", "site_filter", "status"),
        secondary_fields=secondary,
        result_count=page.paginator.count,
        result_label="گزارش",
    )
    labels = {key: label for key, label, _ in sorts}
    key = request.GET.get("sort", "")
    return {
        "reports": page.object_list,
        "page_obj": page,
        "pagination_query": table_pagination_query(request),
        "pagination_rendered": True,
        "summary": summary,
        "filter_bar": bar,
        "list_ui": {
            "bar": bar,
            "sort": {
                "key": key if key in labels else "reporting_date",
                "label": labels.get(key, "جدیدترین گزارش"),
                "descending": request.GET.get("direction") == "desc"
                if key in labels
                else True,
            },
            "sorts": [{"key": key, "label": label} for key, label, _ in sorts],
        },
        "page_breadcrumbs": [
            {"label": "خانه", "url": "/"},
            {"label": "گزارش‌های روزانه"},
        ],
    }
