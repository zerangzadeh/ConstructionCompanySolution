"""Current Expense records, also backing the MVP petty-cash navigation entry."""

from django.db.models import QuerySet
from django.http import FileResponse

from apps.organizations.models import Organization
from core.xlsx import Column as C
from core.xlsx import Sheet, download

from .models import Expense

EXPENSE_COLUMNS = (
    C("پروژه", "project.name"),
    C("کارگاه", "phase.site.name"),
    C("فاز", "phase.name"),
    C("تاریخ هزینه", "incurred_on"),
    C("گروه هزینه", "primary_group.name"),
    C("دسته هزینه", "expense_category.name"),
    C("شرح", "description", 48),
    C("فروشنده", "vendor_name"),
    C("طرف تجاری", "party.display_name"),
    C("ارز", "organization.settings.currency"),
    C("مبلغ", "amount", number_format="#,##0.00"),
    C("وضعیت", "get_status_display"),
    C("مرجع رسید", "receipt_reference"),
)


def expenses_download(
    records: QuerySet[Expense], *, organization: Organization
) -> FileResponse:
    records = records.select_related(
        "organization__settings",
        "phase__site",
        "primary_group",
        "expense_category",
        "party",
    )
    return download(
        "هزینه‌ها و تنخواه",
        (Sheet("هزینه‌ها و تنخواه", EXPENSE_COLUMNS, records.iterator()),),
        timezone_name=organization.settings.timezone,
    )
