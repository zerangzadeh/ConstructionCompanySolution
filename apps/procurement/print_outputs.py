"""Read-only PO/version and GRN projections. No stock or finance semantics."""

from core.printing import Document, Table, day, moment, value

from .models import GoodsReceipt, PurchaseOrder


def order_document(order: PurchaseOrder) -> Document:
    version = order.current_version if order.status != "draft" else None
    lines = (
        version.lines.select_related(
            "material", "unit_of_measure", "source_item"
        ).order_by("sort_order", "created_at")
        if version
        else order.items.all()
    )
    document = Document(
        "سفارش خرید",
        order.order_number,
        metadata=[
            ("پروژه", value(order.project.name)),
            ("تأمین‌کننده", value(order.supplier.display_name)),
            ("تاریخ سفارش", day(order.order_date)),
            ("تحویل موردانتظار", day(order.expected_delivery_date)),
            ("وضعیت", value(order.get_status_display())),
            ("نسخه سفارش", value(version.version_number if version else None)),
        ],
        tables=[
            Table(
                "اقلام سفارش خرید",
                ("شرح / مصالح", "واحد", "مقدار", "قیمت واحد", "مبلغ ردیف"),
                [
                    (
                        value(
                            f"{line.material.name} — {line.description}"
                            if line.description
                            else line.material.name
                        ),
                        value(line.unit_of_measure.name),
                        value(line.quantity),
                        value(line.unit_price),
                        # Version 1's immutable source lines own the existing
                        # rounded amounts summed by PurchaseOrder.total_amount.
                        # Later amendments own their version-line amount only.
                        value(
                            line.source_item.line_total
                            if version and version.version_number == 1
                            else line.line_total
                        ),
                    )
                    for line in lines
                ],
                wide_first=True,
            )
        ],
        notes=[("یادداشت‌ها", order.notes)],
    )
    if order.purchase_request_id:
        document.metadata.append(
            ("درخواست خرید مبنا", value(order.purchase_request.request_number))
        )
    award = version.source_award if version else order.source_award
    if award:
        source = award.comparison.commercial_scope.rfq_version
        document.metadata.extend(
            [
                ("استعلام مبنا", value(source.rfq.rfq_number)),
                ("نسخه استعلام", value(source.version_number)),
            ]
        )
    # The existing total property covers base items, not later amended versions.
    # Match the source detail's rule rather than manufacture a version total.
    if version is None or version.version_number == 1:
        document.totals.append(("جمع مبلغ سفارش", value(order.total_amount)))
    return document


def receipt_document(receipt: GoodsReceipt) -> Document:
    version = receipt.purchase_order_version
    descriptions = (
        {line.source_item_id: line.description for line in version.lines.all()}
        if version
        else {}
    )
    document = Document(
        "رسید کالا",
        receipt.receipt_number,
        metadata=[
            ("پروژه", value(receipt.project.name)),
            ("سفارش خرید مبنا", value(receipt.purchase_order.order_number)),
            ("نسخه سفارش مبنا", value(version.version_number if version else None)),
            ("تأمین‌کننده", value(receipt.purchase_order.supplier.display_name)),
            ("زمان دریافت", moment(receipt.received_at, receipt.organization)),
            ("وضعیت رسید", value(receipt.get_status_display())),
        ],
        tables=[
            Table(
                "اقلام دریافت‌شده",
                ("مصالح / شرح سفارش مبنا", "واحد", "مقدار دریافت‌شده", "یادداشت ردیف"),
                [
                    (
                        value(
                            " — ".join(
                                filter(
                                    None,
                                    (
                                        line.material.name,
                                        descriptions.get(
                                            line.purchase_order_item_id, ""
                                        ),
                                    ),
                                )
                            )
                        ),
                        value(line.unit_of_measure.name),
                        value(line.quantity),
                        value(line.notes),
                    )
                    for line in receipt.items.select_related(
                        "material", "unit_of_measure"
                    )
                ],
                wide_first=True,
            )
        ],
        notes=[("یادداشت‌ها", receipt.notes)],
    )
    return document
