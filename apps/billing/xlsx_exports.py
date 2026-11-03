"""Export persisted Billing results without recalculation or state changes."""

from django.db.models import Prefetch, QuerySet
from django.http import FileResponse

from apps.organizations.models import Organization
from core.xlsx import Column as C
from core.xlsx import Sheet, download

from .models import ClaimAdjustment, ProgressClaim, ProgressClaimItem

CLAIM_COLUMNS = (
    C("پروژه", "project.name"),
    C("شماره قرارداد", "contract.contract_number"),
    C("عنوان قرارداد", "contract.title", 36),
    C("شماره صورت‌وضعیت", lambda r: str(r.claim_number)),
    C("نسخه", "revision_number"),
    C("وضعیت", "get_status_display"),
    C("شروع دوره", "period_start"),
    C("پایان دوره", "period_end"),
    C("تاریخ قطع اندازه‌گیری", "measurement_cutoff"),
    C("ارز", "currency_code"),
    C("مبلغ ناخالص", "gross_amount", number_format="#,##0.0000"),
    C("کسورات و اضافات", "adjustment_amount", number_format="#,##0.0000"),
    C("مبلغ خالص", "net_amount", number_format="#,##0.0000"),
)
LINE_COLUMNS = (
    C("شماره قرارداد", "claim.contract.contract_number"),
    C("شماره صورت‌وضعیت", lambda r: str(r.claim.claim_number)),
    C("نسخه", "claim.revision_number"),
    C("شرح ردیف", "baseline_item.description", 48),
    C("واحد", "baseline_item.unit"),
    C("مقدار تجمعی قبلی", "previous_cumulative_quantity"),
    C("مقدار دوره", "current_quantity"),
    C("مقدار تجمعی جدید", "new_cumulative_quantity"),
    C("نرخ واحد ثبت‌شده", "unit_rate_snapshot"),
    C("مبلغ دوره", "current_amount"),
)
ADJUSTMENT_COLUMNS = (
    C("شماره قرارداد", "claim.contract.contract_number"),
    C("شماره صورت‌وضعیت", lambda r: str(r.claim.claim_number)),
    C("نسخه", "claim.revision_number"),
    C("نوع", "get_adjustment_type_display"),
    C("شرح", "description", 48),
    C("نرخ ثبت‌شده", "rate_snapshot"),
    C("مبلغ مبنا", "base_amount_snapshot"),
    C("مبلغ", "amount"),
)


def claims_download(
    records: QuerySet[ProgressClaim], *, organization: Organization
) -> FileResponse:
    records = list(
        records.prefetch_related(
            Prefetch(
                "items",
                queryset=ProgressClaimItem.objects.select_related(
                    "baseline_item"
                ).order_by("baseline_item__sort_order", "pk"),
            ),
            Prefetch(
                "adjustments",
                queryset=ClaimAdjustment.objects.order_by("sequence", "pk"),
            ),
        )
    )
    return download(
        "صورت‌وضعیت‌ها",
        (
            Sheet("صورت‌وضعیت‌ها", CLAIM_COLUMNS, records),
            Sheet(
                "ردیف‌های کارکرد",
                LINE_COLUMNS,
                (i for r in records for i in r.items.all()),
            ),
            Sheet(
                "کسورات و اضافات",
                ADJUSTMENT_COLUMNS,
                (i for r in records for i in r.adjustments.all()),
            ),
        ),
        timezone_name=organization.settings.timezone,
    )
