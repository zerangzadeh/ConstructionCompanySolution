"""Private year-end service context; never exposed as a user bypass flag."""

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date

from django.core.exceptions import ValidationError
from django.db.models import F, Q, QuerySet, Subquery

_YEAR_END = ContextVar("accounting_year_end", default=False)


@contextmanager
def _year_end_operation():
    token = _YEAR_END.set(True)
    try:
        yield
    finally:
        _YEAR_END.reset(token)


def require_ordinary_year(period: object) -> None:
    if not _YEAR_END.get() and period.fiscal_year.status != "active":
        raise ValidationError("سال مالی برای ثبت یا بازگشایی عادی باز نیست.")


def require_ordinary_journal(journal: object) -> None:
    if _YEAR_END.get():
        return
    from django.db.models import Q

    from .closing_models import FiscalYearClosing

    protected = (
        journal.kind == "closing"
        or journal.source_key.startswith("YEAR-END:")
        or FiscalYearClosing.objects.filter(organization_id=journal.organization_id)
        .filter(
            Q(closing_journal_id=journal.pk)
            | Q(opening_journal_id=journal.pk)
            | Q(closing_reversal_id=journal.pk)
            | Q(opening_reversal_id=journal.pk)
        )
        .exists()
    )
    if not _YEAR_END.get() and protected:
        raise ValidationError(
            "این سند فقط از فرایند بستن یا بازگشایی سال قابل اقدام است."
        )


def require_unreserved_opening(*, organization: object, year_id: object) -> None:
    from .closing_models import FiscalYearClosing

    if (
        not _YEAR_END.get()
        and FiscalYearClosing.objects.filter(
            organization=organization, target_year_id=year_id
        )
        .exclude(status__in=["reversed", "cancelled"])
        .exists()
    ):
        raise ValidationError("افتتاحیه این سال به فرایند انتقال سال قبل اختصاص دارد.")


def ledger_window(
    queryset: QuerySet, *, organization: object, ends_on: date, starts_on: date | None
) -> QuerySet:
    """Use one opening as a book boundary; suppress later duplicate seeds.

    Ranges crossing several years retain movements and closing entries; later
    generated opening seeds are not a second economic event. Reversed executions
    remain paired with their inverses and contribute zero.
    """
    from .closing_models import FiscalYearClosing

    anchor = starts_on or ends_on
    boundary = (
        FiscalYearClosing.objects.filter(
            organization=organization,
            status="rolled_forward",
            target_year__starts_on__lte=anchor,
        )
        .order_by("-target_year__starts_on")
        .values("target_year__starts_on")[:1]
    )
    # Boundary selection and ledger lines execute in the SAME SQL snapshot. A
    # roll-forward commit between separate reads cannot duplicate the opening.
    return (
        queryset.annotate(_ledger_boundary=Subquery(boundary))
        .filter(
            Q(_ledger_boundary__isnull=True)
            | Q(journal__accounting_date__gte=F("_ledger_boundary"))
        )
        .exclude(
            journal__fiscal_opening__organization=organization,
            journal__fiscal_opening__status="rolled_forward",
            journal__fiscal_opening__target_year__starts_on__gt=anchor,
        )
    )
