from decimal import Decimal, InvalidOperation

from django import template

from core.jalali import format_jalali

register = template.Library()
STATUS_LABELS = {
    "reported": "ثبت‌شده",
    "assigned": "تخصیص‌یافته",
    "under_review": "در حال بررسی",
    "in_progress": "در حال انجام",
    "action_in_progress": "اقدام اصلاحی در حال انجام",
    "awaiting_verification": "در انتظار راستی‌آزمایی",
    "resolved": "رفع‌شده",
    "verified": "راستی‌آزمایی‌شده",
    "closed": "بسته‌شده",
    "accepted": "پذیرفته‌شده",
    "paid": "پرداخت‌شده",
    "failed": "ناموفق",
    "rejected": "ردشده",
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
    "Material": "مصالح",
    "Subcontractor": "پیمانکار جزء",
    "Permit": "مجوز",
}

# Presentation families only; domain transitions and labels stay authoritative.
STATUS_FAMILIES = {
    **dict.fromkeys(
        (
            "active",
            "approved",
            "completed",
            "posted",
            "paid",
            "accepted",
            "verified",
            "closed",
            "resolved",
        ),
        "success",
    ),
    **dict.fromkeys(
        (
            "planning",
            "submitted",
            "revised",
            "in_progress",
            "under_review",
            "action_in_progress",
            "assigned",
        ),
        "info",
    ),
    **dict.fromkeys(
        (
            "pending",
            "on_hold",
            "delayed",
            "reported",
            "awaiting_verification",
            "returned",
        ),
        "warning",
    ),
    **dict.fromkeys(
        ("cancelled", "terminated", "void", "voided", "rejected", "failed"),
        "danger",
    ),
}


@register.filter
def status_family(value):
    return STATUS_FAMILIES.get(str(value), "neutral")


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
def rial(value):
    formatted = erp_number(value)
    return f"{formatted} ریال" if formatted not in (None, "") else formatted


@register.filter
def status_fa(value):
    return STATUS_LABELS.get(str(value), value)


@register.filter
def jalali_date(value):
    return format_jalali(value)


@register.filter
def jalali_datetime(value):
    return format_jalali(value, include_time=True)


@register.filter
def reconciliation_issue_fa(value):
    exact = {
        "missing_source_line": "ردیف منبع سند مشخص نشده است",
        "manual_identity_mismatch": "شناسه سند دستی با منبع یکسان نیست",
        "reversal_source_mismatch": "سند برگشت به منبع صحیح متصل نیست",
        "replacement_source_mismatch": "سند جایگزین به منبع صحیح متصل نیست",
        "opening_posting_missing": "سند قطعی افتتاحیه یافت نشد",
        "opening_line_mismatch": "ردیف افتتاحیه با سند حسابداری مغایرت دارد",
        "opening_line_count_mismatch": "تعداد ردیف‌های افتتاحیه و سند یکسان نیست",
    }
    if value in exact:
        return exact[value]
    for kind, title in (
        ("manual", "سند دستی"),
        ("opening", "افتتاحیه"),
        ("correction", "اصلاح سند"),
    ):
        for suffix, label in {
            "count_mismatch": "تعداد ردیف‌ها",
            "amount_mismatch": "مبلغ",
            "source_version_mismatch": "نسخه منبع",
            "exact_line_mismatch": "محتوای ردیف‌ها",
            "dimension_mismatch": "پروژه و سایر ابعاد",
            "correction_chain_mismatch": "زنجیره اصلاح",
        }.items():
            if value == f"{kind}_{suffix}":
                return f"{title}: مغایرت در {label}"
    return "مغایرت نیازمند بررسی؛ کد در جزئیات ردیابی"


@register.filter
def source_authority_fa(value):
    return {
        "Timekeeping / Attendance": "حضور کارکنان",
        "Timekeeping / Timesheet": "کارکرد کارکنان",
        "Estimation": "برآورد",
        "Project Controls / Budget": "بودجه پروژه",
        "Procurement or Contracts": "خرید یا قراردادها",
        "Project Controls": "کنترل هزینه پروژه",
        "Procurement": "خرید و تدارکات",
        "AP/Finance and Matching": "پرداختنی‌ها و تطبیق مالی",
        "Inventory Custody": "مقدار موجودی انبار",
        "Inventory Valuation": "ارزش موجودی انبار",
        "Billing": "صورت‌وضعیت و صورتحساب",
        "Treasury and AP/AR": "خزانه و دریافتنی‌ها و پرداختنی‌ها",
        "AP/AR": "دریافتنی‌ها و پرداختنی‌ها",
        "Accounting / GL": "دفتر کل حسابداری",
        "Treasury": "خزانه‌داری",
        "Treasury Bank Reconciliation": "تطبیق صورت‌حساب بانکی",
        "Payroll": "حقوق و دستمزد",
        "Payroll Statutory": "مالیات و بیمه کارکنان",
        "Fixed Assets": "دارایی‌های ثابت",
        "Accounting or Project Controls": "حسابداری یا کنترل هزینه پروژه",
        "Contracts / Compliance": "قراردادها و انطباق",
        "Contract, AP or Accounting Consumer": "قرارداد، پرداختنی یا حسابداری",
        "Registered Source Domains": "گزارش‌های منابع ثبت‌شده",
        "Named Downstream Domain": "بخش دریافت‌کننده مشخص‌شده",
    }.get(str(value), "منبع ثبت‌شده؛ عنوان در جزئیات تطبیق")


@register.filter
def audit_entity_label(value):
    from django.apps import apps

    try:
        model = apps.get_model(str(value))
    except (LookupError, ValueError):
        model = None
    if model is not None:
        label = str(model._meta.verbose_name)
        if any("\u0600" <= char <= "\u06ff" for char in label):
            return label
    domain = str(value).partition(".")[0]
    return {
        "projects": "سابقه پروژه",
        "treasury": "سابقه خزانه‌داری",
        "accounting": "سابقه حسابداری",
        "procurement": "سابقه خرید و تدارکات",
        "inventory": "سابقه انبار",
        "equipment": "سابقه تجهیز",
        "fixed_assets": "سابقه دارایی ثابت",
        "knowledge": "سابقه دانش",
        "reporting": "سابقه گزارش",
        "payroll": "سابقه حقوق و دستمزد",
        "workforce": "سابقه منابع انسانی",
        "organizations": "سابقه عضویت و تنظیمات شرکت",
        "documents": "سابقه سند",
        "contracts": "سابقه قرارداد",
        "commercial": "سابقه مناقصه",
        "parties": "سابقه طرف تجاری",
        "materials": "سابقه مصالح",
        "support": "سابقه پشتیبانی",
        "daily_reports": "سابقه عملیات کارگاه",
        "safety": "سابقه ایمنی",
        "quality": "سابقه کیفیت",
        "compliance": "سابقه بازرسی و انطباق",
        "timekeeping": "سابقه حضور و کارکرد",
        "billing": "سابقه صورت‌وضعیت",
        "estimates": "سابقه برآورد",
        "workflows": "سابقه گردش‌کار",
    }.get(domain, "رکورد ثبت‌شده")


@register.filter
def audit_business_reference(event):
    # These existing producer fields identify a business record, never a secret,
    # employee identity, storage key, free-text reason, or live cross-domain object.
    reference_keys = (
        "project_code",
        "document_number",
        "request_number",
        "order_number",
        "invoice_number",
        "claim_number",
        "asset_number",
        "incident_number",
        "issue_number",
        "reservation_number",
        "count_number",
        "transfer_number",
    )
    metadata = event.metadata if isinstance(event.metadata, dict) else {}
    if str(event.entity_type) in {
        "projects.Project",
        "projects.ProjectSite",
        "projects.ProjectPhase",
        "materials.Material",
    }:
        reference_keys = ("code", *reference_keys)
    for key in reference_keys:
        value = metadata.get(key)
        if (
            isinstance(value, (str, int))
            and not isinstance(value, bool)
            and str(value).strip()
        ):
            return str(value)[:255]
    return "مرجع تجاری در این رویداد ثبت نشده است."


@register.filter
def reconciliation_readiness_fa(value):
    return {
        "ready": "آماده مقایسه",
        "unknown": "نامشخص",
        "uncomparable": "غیرقابل مقایسه",
        "gated_not_activated": "هنوز فعال نشده",
    }.get(str(value), "وضعیت ثبت‌شده؛ جزئیات را بررسی کنید")
