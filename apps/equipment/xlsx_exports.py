"""Operational Equipment projections; no costs or invented usage metrics."""

from core.xlsx import Column

EQUIPMENT_COLUMNS = (
    Column("کد تجهیز", "code"),
    Column("تجهیز", "name"),
    Column("دسته", "category"),
    Column("مالکیت", "get_ownership_type_display"),
    Column("وضعیت", "get_status_display"),
    Column("سازنده", "manufacturer"),
    Column("مدل", "model"),
    Column("شماره سریال", "serial_number"),
    Column("شماره پلاک", "registration_number"),
    Column("تاریخ تملک یا شروع اجاره", "acquired_on"),
    Column("یادداشت", "notes", 48),
)
ASSIGNMENT_COLUMNS = (
    Column("کد تجهیز", "equipment.code"),
    Column("تجهیز", "equipment.name"),
    Column("پروژه", "project.name"),
    Column("کارگاه", "site.name"),
    Column("شروع تخصیص", "start_date"),
    Column("پایان تخصیص", "end_date"),
    Column("وضعیت", "get_status_display"),
    Column("هدف تخصیص", "purpose", 40),
    Column("یادداشت", "notes", 48),
)
USAGE_COLUMNS = (
    Column("کد تجهیز", "equipment.code"),
    Column("تجهیز", "equipment.name"),
    Column("پروژه", "deployment.project.name"),
    Column("کارگاه", "deployment.site.name"),
    Column("شروع", "started_at"),
    Column("پایان", "ended_at"),
    Column("کارکرد ثبت‌شده (ساعت)", "runtime_hours"),
    Column(
        "اپراتور",
        lambda row: (
            f"{row.operator.first_name} {row.operator.last_name}"
            if row.operator_id
            else None
        ),
    ),
    Column("دلیل اصلاح", "correction_reason", 48),
)
