"""Paginated, source-separated histories; filtering has no domain effects."""

from zoneinfo import ZoneInfo

from django import forms
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Q
from django.db.models.functions import TruncDate

from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
    scope_queryset,
)
from apps.workforce.field_forms import FieldFilterForm, searchable_choices
from apps.workforce.field_selectors import context_employees, scoped_employees
from apps.workforce.models import Employee

from .models import (
    AttendanceCorrectionRequest,
    AttendanceRecord,
    LeaveMissionRequest,
    OvertimeRequest,
    Timesheet,
    TimesheetEntry,
)


def fully_scoped_timesheets(queryset, membership):
    """A sheet's totals and entries are visible only within its complete scope."""
    entries = TimesheetEntry.objects.filter(organization=membership.organization)
    allowed = scope_queryset(
        entries,
        membership=membership,
        project_lookup="project_id",
        site_lookup="site_id",
    )
    outside = entries.filter(timesheet_id=OuterRef("pk")).exclude(
        pk__in=allowed.values("pk")
    )
    return queryset.alias(has_outside_entries=Exists(outside)).filter(
        has_outside_entries=False
    )


class HistoryFilterForm(FieldFilterForm):
    employee = forms.ModelChoiceField(
        label="نیروی کار", queryset=Employee.objects.none(), required=False
    )
    date_from = forms.DateField(label="از تاریخ", required=False)
    date_to = forms.DateField(label="تا تاریخ", required=False)

    def __init__(self, *args, organization, user, context, **kwargs):
        super().__init__(*args, organization=organization, user=user, **kwargs)
        self.fields.pop("q")
        self.fields.pop("status")
        self.fields["employee"].queryset = context_employees(
            scoped_employees(organization=organization, user=user), context
        )
        self.fields["employee"].widget.attrs["data-depends-on"] = "project site"
        searchable_choices(self, "employee", "employee", query=context.query)

    def clean(self):
        cleaned = super().clean()
        if (
            cleaned.get("date_from")
            and cleaned.get("date_to")
            and cleaned["date_from"] > cleaned["date_to"]
        ):
            self.add_error("date_to", "پایان بازه نباید پیش از آغاز باشد.")
        return cleaned


def history_context(request, context):
    organization, user = request.organization, request.user
    membership = get_active_membership(user=user, organization=organization)
    form = HistoryFilterForm(
        request.GET or None, organization=organization, user=user, context=context
    )
    valid = form.is_valid()
    cleaned = form.cleaned_data if valid else {}

    def allowed(permission):
        return has_business_permission(
            user=user,
            organization=organization,
            permission=permission,
            allow_any_scope=True,
        )

    def filtered(
        queryset,
        *,
        project="project",
        site="site",
        employee="employee",
        date_field="work_date",
        end_field=None,
    ):
        queryset = scope_queryset(
            queryset.filter(organization=organization),
            membership=membership,
            project_lookup=f"{project}_id",
            site_lookup=f"{site}_id",
        )
        if request.GET and not valid:
            return queryset.none()
        if context.project:
            queryset = queryset.filter(**{project: context.project})
        if context.site:
            queryset = queryset.filter(**{site: context.site})
        if context.employee:
            queryset = queryset.filter(**{employee: context.employee})
        if cleaned.get("date_from"):
            queryset = queryset.filter(
                **{f"{end_field or date_field}__gte": cleaned["date_from"]}
            )
        if cleaned.get("date_to"):
            queryset = queryset.filter(**{f"{date_field}__lte": cleaned["date_to"]})
        return queryset.distinct()

    attendance = filtered(
        AttendanceRecord.objects.select_related("employee", "project", "site")
    )
    tenant_tz = ZoneInfo(organization.settings.timezone)

    def dated(queryset):
        return queryset.alias(
            local_start=TruncDate("starts_at", tzinfo=tenant_tz),
            local_end=TruncDate("ends_at", tzinfo=tenant_tz),
        )

    leave = filtered(
        dated(
            LeaveMissionRequest.objects.select_related("employee", "project", "site")
        ),
        date_field="local_start",
        end_field="local_end",
    )
    overtime = filtered(
        dated(OvertimeRequest.objects.select_related("employee", "project", "site")),
        date_field="local_start",
        end_field="local_end",
    )
    corrections = filtered(
        AttendanceCorrectionRequest.objects.filter(status="pending").select_related(
            "attendance__employee", "requested_by"
        ),
        project="attendance__project",
        site="attendance__site",
        employee="attendance__employee",
        date_field="attendance__work_date",
    )
    sheets = fully_scoped_timesheets(
        filtered(
            Timesheet.objects.filter(entries__isnull=False).select_related("employee"),
            project="entries__project",
            site="entries__site",
            date_field="period_start",
            end_field="period_end",
        ),
        membership,
    )
    # Own empty drafts remain addressable without fabricating project allocations.
    if not context.project and not context.site:
        own = Timesheet.objects.filter(
            organization=organization,
            prepared_by=user,
            state="draft",
            entries__isnull=True,
        )
        if context.employee:
            own = own.filter(employee=context.employee)
        if cleaned.get("date_from"):
            own = own.filter(period_end__gte=cleaned["date_from"])
        if cleaned.get("date_to"):
            own = own.filter(period_start__lte=cleaned["date_to"])
        if not request.GET or valid:
            sheets = Timesheet.objects.filter(
                Q(pk__in=sheets.values("pk")) | Q(pk__in=own.values("pk"))
            ).select_related("employee")

    result = {"history_form": form, "field_context": context}
    specs = (
        ("attendance_records", "attendance_page", attendance, "-work_date"),
        (
            "leave_mission_requests",
            "leave_page",
            leave if allowed("leave_mission.view") else leave.none(),
            "-starts_at",
        ),
        (
            "overtime_requests",
            "overtime_page",
            overtime if allowed("overtime.view") else overtime.none(),
            "-starts_at",
        ),
        (
            "correction_requests",
            "correction_page",
            corrections if allowed("attendance.correct") else corrections.none(),
            "-created_at",
        ),
        (
            "timesheets",
            "timesheet_page",
            sheets if allowed("timesheets.view") else sheets.none(),
            "-period_start",
        ),
    )
    for name, page_key, queryset, ordering in specs:
        page = Paginator(queryset.order_by(ordering, "-pk"), 25).get_page(
            request.GET.get(page_key)
        )
        result[name] = page.object_list
        query = request.GET.copy()
        query.pop(page_key, None)
        result[page_key] = {
            "page": page,
            "key": page_key,
            "prefix": f"?{query.urlencode()}&" if query else "?",
        }
    return result
