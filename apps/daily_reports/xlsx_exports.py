"""Value projections from authorized Daily Reports; no progress calculation."""

from django.db.models import QuerySet

from core.xlsx import Column, Sheet, download

from .models import DailyReport
from .submission_snapshots import ENTRIES, frozen_entries

REPORT_COLUMNS = (
    Column("پروژه", "project_label"),
    Column("کارگاه", "site_label"),
    Column("فاز", "phase_label"),
    Column("تاریخ گزارش", "reporting_date"),
    Column("نسخه", "revision_number"),
    Column("وضعیت", "get_status_display"),
    Column("آب‌وهوا", "weather_conditions"),
    Column("تعداد نیرو", "labor_count"),
    Column("کارهای انجام‌شده", "work_performed", 60),
    Column("خلاصه پیشرفت", "progress_summary", 48),
    Column("مسائل و تأخیرها", "issues_and_delays", 48),
    Column("یادداشت ایمنی", "safety_notes", 40),
    Column("یادداشت کیفیت", "quality_notes", 40),
)
CHILD_CONTEXT = (
    Column("پروژه", "report.project_label"),
    Column("کارگاه", "report.site_label"),
    Column("فاز", "report.phase_label"),
    Column("تاریخ گزارش", "report.reporting_date"),
    Column("نسخه", "report.revision_number"),
)
CHILD_SPECS = (
    (
        "فعالیت‌ها",
        "daily_activities",
        (
            Column("فعالیت", "activity.name"),
            Column("شرح", "description", 48),
            Column("مقدار", "quantity"),
            Column("واحد", "unit_of_measure.name"),
            Column("درصد پیشرفت ثبت‌شده", "progress_percent"),
            Column("یادداشت", "notes", 40),
        ),
    ),
    (
        "نیروی انسانی",
        "labor_entries",
        (
            Column("گروه کاری", "team_name"),
            Column("تعداد نیرو", "worker_count"),
            Column("ساعات کارکرد", "hours_worked"),
            Column("یادداشت", "notes", 40),
        ),
    ),
    (
        "تجهیزات",
        "equipment_entries",
        (
            Column("تجهیز", "equipment_name"),
            Column("ساعات کارکرد", "hours_used"),
            Column("یادداشت", "notes", 40),
        ),
    ),
    (
        "مصالح",
        "material_entries",
        (
            Column(
                "مصالح",
                lambda row: row.material.name if row.material_id else row.material_name,
            ),
            Column("مقدار", "quantity"),
            Column(
                "واحد",
                lambda row: (
                    row.unit_of_measure.name if row.unit_of_measure_id else row.unit
                ),
            ),
            Column("یادداشت", "notes", 40),
        ),
    ),
    (
        "تأخیرها",
        "delay_events",
        (
            Column("فعالیت", "activity.name"),
            Column("تاریخ وقوع", "occurred_on"),
            Column("دسته", "category"),
            Column("علت", "cause", 48),
            Column("اثر", "impact", 40),
            Column("طرف مسئول", "responsible_party"),
            Column("مدت (ساعت)", "duration_hours"),
            Column("وضعیت", "get_status_display"),
        ),
    ),
)


def reports_download(records: QuerySet[DailyReport], *, timezone_name: str):
    records = list(
        records.prefetch_related(
            "daily_activities__activity",
            "daily_activities__unit_of_measure",
            "labor_entries",
            "equipment_entries",
            "material_entries__material",
            "material_entries__unit_of_measure",
            "delay_events__activity",
        )
    )
    sheets = [Sheet("گزارش‌های روزانه", REPORT_COLUMNS, records)]
    kinds = {spec.relation: kind for kind, spec in ENTRIES.items()}
    for title, relation, columns in CHILD_SPECS:
        children = [
            child
            for report in records
            for child in frozen_entries(report, kinds[relation])
            if child.organization_id == report.organization_id
        ]
        sheets.append(Sheet(title, CHILD_CONTEXT + columns, children))
    return download("گزارش‌های روزانه", sheets, timezone_name=timezone_name)
