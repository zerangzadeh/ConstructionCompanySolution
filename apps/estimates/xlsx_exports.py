"""Current BOQ revision values and existing model-owned amounts only."""

from django.db.models import Prefetch, QuerySet

from core.xlsx import Column, Sheet, download

from .models import Estimate, EstimateItem

ESTIMATE_COLUMNS = (
    Column("شماره برآورد", "estimate_number"),
    Column("عنوان", "title", 48),
    Column("پروژه", "project.name"),
    Column("فاز", "phase.name"),
    Column("قرارداد", "contract.contract_number"),
    Column("بازنگری جاری", "current_revision.revision_number"),
    Column("وضعیت", "get_status_display"),
    Column("وضعیت بازنگری", "current_revision.get_status_display"),
    Column("مبلغ کل", "total_amount", number_format="#,##0.00"),
    Column("زمان تأیید", "approved_at"),
)
LINE_COLUMNS = (
    Column("شماره برآورد", "estimate.estimate_number"),
    Column("پروژه", "estimate.project.name"),
    Column("بازنگری", "revision.revision_number"),
    Column("شرح ردیف", "description", 60),
    Column(
        "واحد",
        lambda row: row.unit_of_measure.name if row.unit_of_measure_id else row.unit,
    ),
    Column("مقدار", "quantity"),
    Column("قیمت واحد", "unit_price", number_format="#,##0.00"),
    Column("مبلغ ردیف", "line_total", number_format="#,##0.00"),
)


def estimates_download(records: QuerySet[Estimate], *, timezone_name: str):
    records = list(
        records.prefetch_related(
            Prefetch(
                "items",
                queryset=EstimateItem.objects.select_related(
                    "unit_of_measure", "revision"
                ),
                to_attr="xlsx_items",
            ),
        )
    )
    # Match Estimate.total_amount: current revision, or legacy unversioned items.
    lines = [
        line
        for estimate in records
        for line in estimate.xlsx_items
        if line.organization_id == estimate.organization_id
        and (
            not estimate.current_revision_id
            or line.revision_id == estimate.current_revision_id
        )
    ]
    return download(
        "برآوردها",
        (
            Sheet("برآوردها", ESTIMATE_COLUMNS, records),
            Sheet("ردیف‌های برآورد", LINE_COLUMNS, lines),
        ),
        timezone_name=timezone_name,
    )
