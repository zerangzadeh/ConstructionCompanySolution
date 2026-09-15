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


def jalali_to_gregorian(year: int, month: int, day: int) -> tuple[int, int, int]:
    """Convert a Jalali date to Gregorian without accepting impossible days."""
    if month < 1 or month > 12 or day < 1 or day > 31:
        raise ValueError("invalid Jalali date")
    year_offset = year + 1595
    days = (
        -355668
        + (365 * year_offset)
        + ((year_offset // 33) * 8)
        + (((year_offset % 33) + 3) // 4)
        + day
        + ((month - 1) * 31 if month < 7 else ((month - 7) * 30) + 186)
    )
    gregorian_year = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        gregorian_year += 100 * ((days - 1) // 36524)
        days = (days - 1) % 36524
        if days >= 365:
            days += 1
    gregorian_year += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gregorian_year += (days - 1) // 365
        days = (days - 1) % 365
    gregorian_day_of_year = days + 1
    leap = (
        gregorian_year % 4 == 0 and gregorian_year % 100 != 0
    ) or gregorian_year % 400 == 0
    month_lengths = (0, 31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    gregorian_month = 1
    while (
        gregorian_month <= 12 and gregorian_day_of_year > month_lengths[gregorian_month]
    ):
        gregorian_day_of_year -= month_lengths[gregorian_month]
        gregorian_month += 1
    if gregorian_month > 12:
        raise ValueError("invalid Jalali date")
    return gregorian_year, gregorian_month, gregorian_day_of_year


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
