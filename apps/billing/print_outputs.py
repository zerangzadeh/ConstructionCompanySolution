"""Claim print projection: persisted revision results, never a recalculation."""

from datetime import date

from core.printing import Document, Table, day, moment, value

from .models import ClaimAdjustmentType, ProgressClaim


def claim_document(claim: ProgressClaim) -> Document:
    snapshot = claim.submission_snapshot
    saved = snapshot.get("claim", {})

    def field(name: str):
        return saved[name] if name in saved else getattr(claim, name)

    def saved_day(name: str):
        result = field(name)
        return day(date.fromisoformat(result) if isinstance(result, str) else result)

    items = list(
        claim.items.select_related("baseline_item").order_by(
            "baseline_item__sort_order", "pk"
        )
    )
    by_id = {str(item.pk): item for item in items}
    source_rows = snapshot.get("items")
    if source_rows is None:
        source_rows = [
            {
                name: getattr(item, name)
                for name in (
                    "previous_cumulative_quantity",
                    "current_quantity",
                    "new_cumulative_quantity",
                    "unit_rate_snapshot",
                    "current_amount",
                )
            }
            | {"id": str(item.pk)}
            for item in items
        ]
    rows = []
    for row in sorted(
        source_rows,
        key=lambda row: (by_id[row["id"]].baseline_item.sort_order, row["id"]),
    ):
        # Baseline descriptions/units belong to the pinned immutable baseline.
        item = by_id[row["id"]]
        rows.append(
            (
                value(item.baseline_item.description),
                value(item.baseline_item.unit),
                *(
                    value(row[key], number=True)
                    for key in (
                        "previous_cumulative_quantity",
                        "current_quantity",
                        "new_cumulative_quantity",
                        "unit_rate_snapshot",
                        "current_amount",
                    )
                ),
            )
        )
    adjustments = snapshot.get("adjustments")
    if adjustments is None:
        adjustments = [
            {
                key: getattr(row, key)
                for key in (
                    "adjustment_type",
                    "rate_snapshot",
                    "base_amount_snapshot",
                    "amount",
                )
            }
            for row in claim.adjustments.order_by("sequence", "pk")
        ]
    currency = field("currency_code")
    document = Document(
        "صورت‌وضعیت",
        str(field("claim_number")),
        metadata=[
            ("پروژه", value(claim.project.name)),
            ("شماره قرارداد", value(claim.contract.contract_number)),
            ("عنوان قرارداد", value(claim.contract.title)),
            (
                "طرف قرارداد",
                value(
                    saved.get("party_identity", {}).get(
                        "display_name", claim.party_identity_snapshot.display_name
                    )
                ),
            ),
            ("نسخه", value(field("revision_number"))),
            ("وضعیت", value(claim.get_status_display())),
            ("شروع دوره", saved_day("period_start")),
            ("پایان دوره", saved_day("period_end")),
            ("تاریخ نهایی اندازه‌گیری", saved_day("measurement_cutoff")),
            ("ارز", value(currency)),
        ],
        tables=[
            Table(
                "کارکرد و مقادیر تجمعی",
                (
                    "شرح",
                    "واحد",
                    "تجمعی قبلی",
                    "مقدار دوره",
                    "تجمعی جدید",
                    "نرخ ثبت‌شده",
                    "مبلغ دوره",
                ),
                rows,
                wide_first=True,
            ),
            Table(
                "کسور و تعدیلات",
                ("نوع", "نرخ ثبت‌شده (درصد)", "مبلغ مبنا", "مبلغ"),
                [
                    (
                        value(ClaimAdjustmentType(row["adjustment_type"]).label),
                        value(row["rate_snapshot"], number=True),
                        value(row["base_amount_snapshot"], number=True),
                        value(row["amount"], number=True),
                    )
                    for row in adjustments
                ],
            ),
        ],
        totals=[
            (label + f" ({currency})", value(field(key), number=True))
            for label, key in (
                ("ناخالص", "gross_amount"),
                ("کسور و تعدیلات", "adjustment_amount"),
                ("خالص صورت‌وضعیت", "net_amount"),
            )
        ],
    )
    if claim.approved_at:
        document.approvals.append(
            ("زمان تأیید", moment(claim.approved_at, claim.organization))
        )
        if claim.approved_by and claim.approved_by.get_full_name():
            document.approvals.append(
                ("تأییدکننده", value(claim.approved_by.get_full_name()))
            )
    return document
