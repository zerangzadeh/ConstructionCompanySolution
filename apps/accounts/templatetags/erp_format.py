from decimal import Decimal, InvalidOperation
from django import template

register = template.Library()
STATUS_LABELS = {
    "draft": "پیش‌نویس",
    "active": "فعال",
    "completed": "تکمیل‌شده",
    "approved": "تأییدشده",
    "submitted": "ارسال‌شده",
    "revised": "بازنگری‌شده",
    "archived": "بایگانی‌شده",
    "terminated": "خاتمه‌یافته",
    "recorded": "ثبت‌شده",
    "posted": "ثبت‌شده",
    "void": "باطل‌شده",
    "voided": "باطل‌شده",
    "planning": "در حال برنامه‌ریزی",
    "on_hold": "متوقف‌شده",
    "cancelled": "لغوشده",
    "receipt": "دریافت",
    "disbursement": "پرداخت",
    "bank_transfer": "انتقال بانکی",
    "cash": "نقدی",
    "check": "چک",
    "other": "سایر",
    "materials": "مصالح",
    "labor": "نیروی انسانی",
    "equipment": "تجهیزات",
    "subcontractor": "پیمانکار جزء",
    "permit": "مجوز",
    "Draft": "پیش‌نویس",
    "Active": "فعال",
    "Completed": "تکمیل‌شده",
    "Approved": "تأییدشده",
    "Submitted": "ارسال‌شده",
    "Revised": "بازنگری‌شده",
    "Archived": "بایگانی‌شده",
    "Terminated": "خاتمه‌یافته",
    "Recorded": "ثبت‌شده",
    "Posted": "ثبت‌شده",
    "Void": "باطل‌شده",
    "Planning": "در حال برنامه‌ریزی",
    "On hold": "متوقف‌شده",
    "Cancelled": "لغوشده",
    "Receipt": "دریافت",
    "Disbursement": "پرداخت",
    "Bank transfer": "انتقال بانکی",
    "Cash": "نقدی",
    "Check": "چک",
    "Other": "سایر",
    "Materials": "مصالح",
    "Labor": "نیروی انسانی",
    "Equipment": "تجهیزات",
    "Subcontractor": "پیمانکار جزء",
    "Permit": "مجوز",
}

@register.filter
def erp_number(value):
    if value in (None, ""):
        return value
    try:
        text = format(Decimal(str(value)), ",f")
    except (InvalidOperation, TypeError, ValueError):
        return value
    return text.rstrip("0").rstrip(".") if "." in text else text

@register.filter
def status_fa(value):
    return STATUS_LABELS.get(str(value), value)
