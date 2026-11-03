"""Filtered Expense data; the MVP petty-cash entry owns no cash ledger."""

from django.db.models import QuerySet

from apps.organizations.models import Organization
from core.printing import Document, Table, day, value

from .models import Expense


def expense_document(
    records: QuerySet[Expense],
    *,
    organization: Organization,
    filters: list[tuple[str, str]],
) -> Document:
    rows = records.select_related(
        "phase__site", "project", "primary_group", "expense_category", "party"
    )
    currency = organization.settings.currency
    return Document(
        "خلاصه هزینه‌ها و تنخواه",
        metadata=[
            ("ارز", value(currency)),
            *((label, value(text)) for label, text in filters),
        ],
        tables=[
            Table(
                "هزینه‌های ثبت‌شده",
                (
                    "شرح / پروژه و کارگاه",
                    "تاریخ / گروه و دسته",
                    "فروشنده / طرف تجاری",
                    f"مبلغ ({currency})",
                    "وضعیت / مرجع رسید",
                ),
                [
                    (
                        value(
                            " — ".join(
                                filter(
                                    None,
                                    (
                                        row.description,
                                        row.project.name,
                                        row.phase.site.name if row.phase else "",
                                        row.phase.name if row.phase else "",
                                    ),
                                )
                            )
                        ),
                        value(
                            " — ".join(
                                filter(
                                    None,
                                    (
                                        day(row.incurred_on).text,
                                        row.primary_group.name
                                        if row.primary_group
                                        else row.get_category_display(),
                                        row.expense_category.name
                                        if row.expense_category
                                        else "",
                                    ),
                                )
                            )
                        ),
                        value(
                            " — ".join(
                                filter(
                                    None,
                                    (
                                        row.vendor_name,
                                        row.party.display_name if row.party else "",
                                    ),
                                )
                            )
                        ),
                        value(row.amount),
                        value(
                            " — ".join(
                                filter(
                                    None,
                                    (row.get_status_display(), row.receipt_reference),
                                )
                            )
                        ),
                    )
                    for row in rows
                ],
                wide_first=True,
            )
        ],
    )
