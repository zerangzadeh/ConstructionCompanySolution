"""Reuse source-separated authorized history before its independent pagination."""

from django.db.models import Prefetch

from core.xlsx import Column, Sheet, download

from .models import TimesheetEntry

PERSON_CONTEXT = (
    Column(
        "نیروی کار", lambda row: f"{row.employee.first_name} {row.employee.last_name}"
    ),
    Column("پروژه", "project.name"),
    Column("کارگاه", "site.name"),
)
ATTENDANCE_COLUMNS = PERSON_CONTEXT + (
    Column("تاریخ", "work_date"),
    Column("ورود", "check_in_at"),
    Column("خروج", "check_out_at"),
    Column("وضعیت", "get_state_display"),
)
OVERTIME_COLUMNS = PERSON_CONTEXT + (
    Column("شروع", "starts_at"),
    Column("پایان", "ends_at"),
    Column("دلیل", "reason", 48),
    Column("وضعیت", "get_state_display"),
)
TIMESHEET_COLUMNS = (
    Column(
        "نیروی کار", lambda row: f"{row.employee.first_name} {row.employee.last_name}"
    ),
    Column("شروع دوره", "period_start"),
    Column("پایان دوره", "period_end"),
    Column("بازنگری", "revision"),
    Column("زمان اظهارشده (دقیقه)", "declared_minutes"),
    Column("وضعیت", "get_state_display"),
)
ENTRY_COLUMNS = (
    Column(
        "نیروی کار",
        lambda row: (
            f"{row.timesheet.employee.first_name} {row.timesheet.employee.last_name}"
        ),
    ),
    Column("شروع دوره", "timesheet.period_start"),
    Column("پایان دوره", "timesheet.period_end"),
    Column("بازنگری", "timesheet.revision"),
    Column("تاریخ", "work_date"),
    Column("پروژه", "project.name"),
    Column("کارگاه", "site.name"),
    Column("فعالیت", "activity.name"),
    Column("کارکرد (دقیقه)", "minutes"),
    Column("یادداشت", "note", 48),
)


def history_download(data: dict, *, timezone_name: str):
    def records(key):
        return data[key]["page"].paginator.object_list

    sheets = list(
        records("timesheet_page").prefetch_related(
            Prefetch(
                "entries",
                queryset=TimesheetEntry.objects.select_related(
                    "project", "site", "activity"
                ).order_by("work_date", "pk"),
            )
        )
    )
    entries = [
        entry
        for sheet in sheets
        for entry in sheet.entries.all()
        if entry.organization_id == sheet.organization_id
    ]
    return download(
        "حضور و کارکرد",
        (
            Sheet("حضور", ATTENDANCE_COLUMNS, records("attendance_page")),
            Sheet("کارکرد", TIMESHEET_COLUMNS, sheets),
            Sheet("توزیع زمان", ENTRY_COLUMNS, entries),
            Sheet("اضافه‌کاری", OVERTIME_COLUMNS, records("overtime_page")),
        ),
        timezone_name=timezone_name,
    )
