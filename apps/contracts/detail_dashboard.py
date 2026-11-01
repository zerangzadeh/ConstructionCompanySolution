"""Read-only presentation of an already authorized contract and related querysets.

No posting, settlement, progress measurement or lifecycle authority lives here.
Gross period amounts follow billing's active-claim convention; drafts, returned,
superseded and cancelled revisions do not contribute. Zero physical progress is
an explicit empty state only when the scoped measurement selector proves absence;
existing measurements still require a governed contract-wide rollup.
"""

from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q, QuerySet, Sum
from django.http import HttpRequest
from django.urls import reverse

from core.business_choices import contextual_url
from core.product_surface import route_exposed

from .models import Contract


def contract_dashboard(
    request: HttpRequest,
    contract: Contract,
    *,
    claims: QuerySet | None,
    baselines: QuerySet | None,
    estimates: QuerySet | None,
    certificates: QuerySet | None = None,
    physical_empty: bool = False,
) -> dict[str, object]:
    """Compose exact values from the view's tenant/project/permission scoped reads."""
    try:
        currency = request.organization.settings.currency
    except ObjectDoesNotExist:
        currency = None
    currency_label = "ریال" if currency == "IRR" else currency
    amendments = sum(
        (
            row.value_change
            for row in contract.amendments.all()
            if row.organization_id == request.organization.pk
            and row.status == "approved"
        ),
        Decimal(0),
    )
    effective = contract.contract_value + amendments
    payable = contract.direction == "payable"
    detail_route = (
        "billing:payable_certificate_detail" if payable else "billing:claim_detail"
    )
    source = certificates if payable else claims
    number_field = "certificate_number" if payable else "claim_number"
    record_label = "گواهی پرداخت" if payable else "صورت‌وضعیت"
    records = (
        source.filter(
            organization=request.organization,
            contract=contract,
            project=contract.project,
        ).select_related(None)
        if source is not None and route_exposed(detail_route)
        else None
    )
    unavailable = "صورت‌وضعیت قابل مشاهده‌ای ثبت نشده است."
    if records is None:
        unavailable = "اطلاعات صورت‌وضعیت در این نما در دسترس نیست."
    active = (
        records.filter(status__in=("approved", "submitted"))
        if records is not None
        else None
    )
    has_active = active is not None and active.exists()
    comparable = (
        bool(currency and records is not None)
        and not active.exclude(
            currency_code=currency, correction_kind="ordinary"
        ).exists()
    )
    if has_active and not comparable:
        unavailable = "سوابق ارزی یا اصلاحی برای این مقایسه قابل تجمیع نیستند."
    approved = pending = issued = remaining = percentage = None
    segments = []
    if comparable:
        totals = active.aggregate(
            approved=Sum(
                "gross_amount", filter=Q(status="approved"), default=Decimal(0)
            ),
            pending=Sum(
                "gross_amount", filter=Q(status="submitted"), default=Decimal(0)
            ),
        )
        approved, pending = totals["approved"], totals["pending"]
        issued = approved + pending
        if effective >= 0 and Decimal(0) <= issued <= effective:
            remaining = effective - issued
            percentage = (
                (approved / effective * 100).quantize(Decimal("0.1"))
                if effective > 0
                else Decimal(0)
            )
            segments = [
                {"label": "تأییدشده", "value": approved, "tone": "approved"},
                {"label": "در حال بررسی", "value": pending, "tone": "pending"},
                {
                    "label": "مانده قابل صورت‌وضعیت",
                    "value": remaining,
                    "tone": "remaining",
                },
            ]
            for segment in segments:
                segment["percent"] = (
                    (segment["value"] / effective * 100).quantize(Decimal("0.1"))
                    if effective > 0
                    else Decimal(0)
                )
        else:
            unavailable = "مبلغ مؤثر و صورت‌وضعیت‌ها برای نمایش نسبت قابل مقایسه نیستند."
    kpis = [
        {
            "label": "مبلغ مؤثر قرارداد",
            "value": effective,
            "unit": currency_label or "",
            "tone": "value",
            "icon": "coins",
            "note": "مبلغ اولیه + الحاقیه‌های تأییدشده",
        },
        {
            "label": "مانده قابل صورت‌وضعیت",
            "value": remaining,
            "unit": currency_label or "",
            "tone": "remaining",
            "icon": "document",
            "note": "پس از مبالغ ناخالص ارسال و تأییدشده",
        },
        {
            "label": "مبلغ تأییدشده",
            "value": approved,
            "unit": currency_label or "",
            "tone": "approved",
            "icon": "check",
            "note": "ناخالص گواهی‌های پرداخت تأییدشده"
            if payable
            else "ناخالص صورت‌وضعیت‌های تأییدشده",
        },
        {
            "label": "مبلغ صورت‌وضعیت‌شده",
            "value": issued,
            "unit": currency_label or "",
            "tone": "issued",
            "icon": "layers",
            "note": "ناخالص ارسال و تأییدشده؛ بدون پیش‌نویس",
        },
        {
            "label": "پیشرفت فیزیکی",
            "value": Decimal(0) if physical_empty else None,
            "unit": "٪" if physical_empty else "",
            "tone": "physical",
            "icon": "target",
            "note": "اندازه‌گیری پیشرفت ثبت نشده"
            if physical_empty
            else "پیشرفت تجمیعی قابل اتکا در دسترس نیست",
        },
    ]
    recent = []
    if records is not None:
        for field, label in (
            ("created_at", "ثبت صورت‌وضعیت"),
            ("submitted_at", "ارسال صورت‌وضعیت"),
            ("approved_at", "تأیید صورت‌وضعیت"),
            ("returned_at", "بازگشت صورت‌وضعیت"),
        ):
            for row in records.filter(**{f"{field}__isnull": False}).order_by(
                f"-{field}", "-pk"
            )[:3]:
                recent.append(
                    {
                        "title": f"{label.replace('صورت‌وضعیت', record_label)} شماره {getattr(row, number_field)} · نسخه {row.revision_number}",
                        "date": getattr(row, field),
                        "url": reverse(detail_route, args=[row.pk]),
                        "icon": "document",
                    }
                )
    recent.append(
        {
            "title": "ثبت قرارداد",
            "date": contract.created_at,
            "url": "#information",
            "icon": "document",
        }
    )
    chart_rows = [
        {
            "label": row["label"],
            "value": str(row["value"]),
            "percent": str(row["percent"]),
            "formatted": f"{row['value']:,f} {currency_label} · {row['percent']}٪",
        }
        for row in segments
    ]
    billing_records = (
        [
            {
                "number": getattr(row, number_field),
                "revision_number": row.revision_number,
                "period_end": row.period_end,
                "gross_amount": row.gross_amount,
                "currency_code": row.currency_code,
                "status": row.status,
                "status_label": row.get_status_display(),
                "url": reverse(detail_route, args=[row.pk]),
            }
            for row in records.order_by("-created_at", "-pk")[:3]
        ]
        if records is not None
        else None
    )
    return {
        "kpis": kpis,
        "currency": currency or "واحد پول تنظیم نشده",
        "currency_label": currency_label or "واحد پول تنظیم نشده",
        "effective": effective,
        "amendments": amendments,
        "segments": segments,
        "chart_rows": chart_rows,
        "financial_percent": percentage,
        "physical_percent": Decimal(0) if physical_empty else None,
        "unavailable": unavailable,
        "billing_records": billing_records,
        "billing_heading": "آخرین صورت‌وضعیت‌های پرداختنی"
        if payable
        else "آخرین صورت‌وضعیت‌ها",
        "billing_nav_label": "صورت‌وضعیت‌های پرداختنی" if payable else "صورت‌وضعیت‌ها",
        "billing_nav_url": "#billing-records"
        if payable
        else contextual_url("billing:claim_list", contract=contract),
        "billing_list_label": "فهرست گواهی‌های پرداخت"
        if payable
        else "مشاهده همه صورت‌وضعیت‌ها",
        "billing_list_url": reverse("billing:payable_certificate_list")
        if payable
        else contextual_url("billing:claim_list", contract=contract),
        "recent": sorted(recent, key=lambda r: r["date"], reverse=True)[:3],
        "show_baselines": baselines is not None
        and route_exposed("billing:baseline_list"),
        "show_billing": records is not None,
        "show_estimates": estimates is not None and route_exposed("estimates:list"),
    }
