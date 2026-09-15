from __future__ import annotations

from datetime import date, datetime

from django.utils import timezone


def gregorian_to_jalali(year: int, month: int, day: int) -> tuple[int, int, int]:
    """Convert a Gregorian date to its Jalali calendar equivalent."""
    month_days = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)
    adjusted_year = year + 1 if month > 2 else year
    days = (
        355666
        + (365 * year)
        + ((adjusted_year + 3) // 4)
        - ((adjusted_year + 99) // 100)
        + ((adjusted_year + 399) // 400)
        + day
        + month_days[month - 1]
    )
    jalali_year = -1595 + (33 * (days // 12053))
    days %= 12053
    jalali_year += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jalali_year += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jalali_month = 1 + (days // 31)
        jalali_day = 1 + (days % 31)
    else:
        jalali_month = 7 + ((days - 186) // 30)
        jalali_day = 1 + ((days - 186) % 30)
    return jalali_year, jalali_month, jalali_day


def format_jalali(value: date | datetime | None, *, include_time: bool = False) -> str:
    """Format a date/datetime for the Persian UI without changing storage values."""
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        date_value = value.date()
    elif isinstance(value, date):
        date_value = value
    else:
        return str(value)
    year, month, day = gregorian_to_jalali(
        date_value.year, date_value.month, date_value.day
    )
    result = f"{year:04d}/{month:02d}/{day:02d}"
    if include_time and isinstance(value, datetime):
        result = f"{result} {value:%H:%M}"
    return result
