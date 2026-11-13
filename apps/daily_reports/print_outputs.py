"""Existing site report fields and entries; no derived progress/productivity."""

from core.printing import Document, Table, day, moment, value

from .models import DailyReport
from .submission_snapshots import frozen_entries


def daily_document(report: DailyReport) -> Document:
    document = Document(
        "گزارش روزانه",
        metadata=[
            ("پروژه", value(report.project_label)),
            ("کارگاه", value(report.site_label)),
            ("فاز", value(report.phase_label)),
            ("نسخه", value(report.revision_number)),
            ("تاریخ گزارش", day(report.reporting_date)),
            ("وضعیت", value(report.get_status_display())),
            ("آب‌وهوا", value(report.weather_conditions)),
            ("تعداد نیروی انسانی", value(report.labor_count)),
        ],
        introduction=[
            (label, getattr(report, name))
            for label, name in (
                ("کارهای انجام‌شده", "work_performed"),
                ("خلاصه پیشرفت", "progress_summary"),
                ("مسائل و تأخیرها", "issues_and_delays"),
                ("یادداشت‌های ایمنی", "safety_notes"),
                ("یادداشت‌های کیفیت", "quality_notes"),
            )
        ],
    )
    document.tables = [
        Table(
            "فعالیت‌های روزانه",
            ("شرح", "مقدار", "واحد", "پیشرفت ثبت‌شده (درصد)", "یادداشت"),
            [
                (
                    value(row.description),
                    value(row.quantity),
                    value(row.unit_of_measure.name if row.unit_of_measure else None),
                    value(row.progress_percent),
                    value(row.notes),
                )
                for row in frozen_entries(report, "activities")
            ],
            wide_first=True,
        ),
        Table(
            "نیروی انسانی",
            ("گروه کاری", "تعداد نیرو", "ساعات کارکرد", "یادداشت"),
            [
                (
                    value(row.team_name),
                    value(row.worker_count),
                    value(row.hours_worked),
                    value(row.notes),
                )
                for row in frozen_entries(report, "labor")
            ],
        ),
        Table(
            "تجهیزات",
            ("نام تجهیز", "ساعات کارکرد", "یادداشت"),
            [
                (value(row.equipment_name), value(row.hours_used), value(row.notes))
                for row in frozen_entries(report, "equipment")
            ],
        ),
        Table(
            "مصالح مصرفی",
            ("مصالح ثبت‌شده", "مقدار", "واحد ثبت‌شده", "یادداشت"),
            [
                (
                    value(row.material_name),
                    value(row.quantity),
                    value(row.unit),
                    value(row.notes),
                )
                for row in frozen_entries(report, "materials")
            ],
        ),
        Table(
            "رویدادهای تأخیر",
            ("تاریخ", "دسته / علت / اثر", "طرف مسئول", "مدت (ساعت)", "وضعیت"),
            [
                (
                    day(row.occurred_on),
                    value(
                        " — ".join(filter(None, (row.category, row.cause, row.impact)))
                    ),
                    value(row.responsible_party),
                    value(row.duration_hours),
                    value(row.get_status_display()),
                )
                for row in frozen_entries(report, "delays")
            ],
            wide_first=False,
        ),
    ]
    document.tables = [table for table in document.tables if table.rows]
    if report.approved_at:
        document.approvals.append(
            ("زمان تأیید", moment(report.approved_at, report.organization))
        )
        if report.approved_by and report.approved_by.get_full_name():
            document.approvals.append(
                ("تأییدکننده", value(report.approved_by.get_full_name()))
            )
    return document
