"""Governed annual closing. All mutations serialize on the tenant book authority."""

from __future__ import annotations

import hashlib
import json
import logging
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from functools import wraps

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import (
    BusinessPermissionCode,
    Organization,
    OrganizationMembership,
)

from .closing_guards import _year_end_operation, ledger_window
from .closing_models import (
    ClosingStatus,
    FiscalClosingConfiguration,
    FiscalYearClosing,
    FiscalYearClosingEvent,
)
from .models import (
    Account,
    AccountType,
    FiscalPeriod,
    FiscalPeriodStatus,
    FiscalYear,
    FiscalYearStatus,
    JournalEntry,
    JournalKind,
    JournalLine,
    JournalStatus,
    OpeningBalanceImport,
)
from .posting_registry import get_posting_contract
from .reconciliation import verify_signed_reconciliation_run
from .services import (
    _journal_payload_hash,
    _require_reason,
    _validate_independent_requester,
    add_journal_line,
    create_journal,
    post_journal,
    reopen_period,
    reverse_journal,
    submit_journal,
)

ZERO = Decimal(0)
PERMANENT = frozenset({AccountType.ASSET, AccountType.LIABILITY, AccountType.EQUITY})
TEMPORARY = frozenset({AccountType.INCOME, AccountType.EXPENSE})
DIMENSIONS = ("project", "site", "wbs_node", "party")


def _failure_evidence(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception:
            # Outside the business transaction: no accounting payload or exception
            # text is logged. HTTP request logs separately retain request correlation.
            logging.getLogger(__name__).warning(
                "accounting.year_end_failed stage=%s", function.__name__
            )
            raise

    return wrapped


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _permission(organization, actor, permission):
    return require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        message="اختیار انجام این مرحله بستن سال را ندارید.",
    )


def _year(organization, year):
    # Re-read instead of trusting a caller-provided tenant/status/configuration.
    try:
        return FiscalYear.objects.get(organization=organization, pk=year.pk)
    except FiscalYear.DoesNotExist as exc:
        raise PermissionDenied("سال مالی در دسترس نیست.") from exc


def _key(row):
    return tuple(row.get(name) for name in ("account", "currency", *DIMENSIONS))


def _balances(rows):
    return {_key(row): Decimal(row["net"]) for row in rows if Decimal(row["net"])}


def _snapshot(organization, year):
    """Exact posted inputs plus balances at full existing ledger dimensional grain."""
    lines = ledger_window(
        JournalLine.objects.filter(
            journal__organization=organization,
            journal__status=JournalStatus.POSTED,
            journal__accounting_date__lte=year.ends_on,
        ),
        organization=organization,
        ends_on=year.ends_on,
        starts_on=None,
    )
    lines = list(
        lines.select_related(
            "journal__period__fiscal_year",
            "account",
            "project",
            "site",
            "wbs_node",
            "party",
        ).order_by("journal__accounting_date", "journal__number", "line_number", "pk")
    )
    totals = defaultdict(lambda: ZERO)
    rows = {}
    evidence = []
    journals = {}
    prior_nominal = defaultdict(lambda: ZERO)
    for line in lines:
        journal = line.journal
        if any(
            obj.organization_id != organization.pk
            for obj in (line, line.account, journal.period, journal.period.fiscal_year)
        ):
            raise ValidationError("ارتباط حسابداری خارج از شرکت شناسایی شد.")
        for name in DIMENSIONS:
            obj = getattr(line, name)
            if obj is not None and obj.organization_id != organization.pk:
                raise ValidationError("ابعاد حسابداری با شرکت سازگار نیست.")
        if (
            line.site_id
            and (not line.project_id or line.site.project_id != line.project_id)
        ) or (
            line.wbs_node_id
            and (not line.project_id or line.wbs_node.project_id != line.project_id)
        ):
            raise ValidationError("پروژه و ابعاد ردیف حسابداری سازگار نیستند.")
        if (
            journal.currency != "IRR"
            or not journal.period.starts_on
            <= journal.accounting_date
            <= journal.period.ends_on
        ):
            raise ValidationError("ارز یا تاریخ سند قطعی معتبر نیست.")
        if line.account.account_type not in PERMANENT | TEMPORARY:
            raise ValidationError("طبقه‌بندی معتبر برای حساب وجود ندارد.")
        if not line.account_snapshot or any(
            line.account_snapshot.get(k) != v
            for k, v in {
                "id": str(line.account_id),
                "code": line.account.code,
                "type": line.account.account_type,
            }.items()
        ):
            raise ValidationError("تصویر قطعی حساب ناقص یا ناسازگار است.")
        expected_dimensions = {
            "wbs" if name == "wbs_node" else name: str(getattr(line, f"{name}_id"))
            for name in DIMENSIONS
            if getattr(line, f"{name}_id")
        }
        if set(line.dimension_snapshot) != set(expected_dimensions) or any(
            line.dimension_snapshot[name].get("id") != value
            for name, value in expected_dimensions.items()
        ):
            raise ValidationError("تصویر قطعی ابعاد ناقص یا ناسازگار است.")
        if (
            not line.debit.is_finite()
            or not line.credit.is_finite()
            or not (
                (line.debit > 0 and line.credit == 0)
                or (line.credit > 0 and line.debit == 0)
            )
        ):
            raise ValidationError("مبلغ ردیف قطعی معتبر نیست.")
        if journal.pk not in journals:
            journal.clean()
            contract = get_posting_contract(
                source_kind=journal.source_kind, event_kind=journal.event_kind
            )
            if (
                journal.posting_rule_code != contract.rule_code
                or journal.posting_rule_version != contract.rule_version
                or not journal.source_key.strip()
            ):
                raise ValidationError("قرارداد ثبت سند قطعی معتبر نیست.")
            if (
                not journal.payload_hash
                or journal.payload_hash != _journal_payload_hash(journal)
            ):
                raise ValidationError("محتوای سند قطعی با شواهد آن ناسازگار است.")
            journals[journal.pk] = [ZERO, ZERO]
        journals[journal.pk][0] += line.debit
        journals[journal.pk][1] += line.credit
        row = {
            "account": str(line.account_id),
            "type": line.account.account_type,
            "currency": journal.currency,
            **{
                name: str(getattr(line, f"{name}_id"))
                if getattr(line, f"{name}_id")
                else None
                for name in DIMENSIONS
            },
        }
        key = _key(row)
        rows[key] = row
        totals[key] += line.debit - line.credit
        if journal.accounting_date < year.starts_on and row["type"] in TEMPORARY:
            prior_nominal[key] += line.debit - line.credit
        evidence.append(
            {
                "journal": str(journal.pk),
                "payload_hash": journal.payload_hash,
                "line": str(line.pk),
                "source_line": str(line.source_line_uuid),
                "account_snapshot": line.account_snapshot,
                "dimension_snapshot": line.dimension_snapshot,
                "accounting_date": journal.accounting_date.isoformat(),
                "debit": str(line.debit),
                "credit": str(line.credit),
            }
        )
    if any(debit != credit for debit, credit in journals.values()):
        raise ValidationError("حداقل یک سند قطعی نامتوازن است.")
    if JournalEntry.objects.filter(
        organization=organization,
        status=JournalStatus.POSTED,
        accounting_date__lte=year.ends_on,
        lines__isnull=True,
    ).exists():
        raise ValidationError("سند قطعی بدون ردیف شناسایی شد.")
    balances = [
        {**rows[key], "net": str(totals[key])}
        for key in sorted(rows, key=str)
        if totals[key]
    ]
    payload = {
        "organization": str(organization.pk),
        "year": str(year.pk),
        "cutoff": year.ends_on.isoformat(),
        "lines": evidence,
        "balances": balances,
        "nominal_balance_count": sum(row["type"] in TEMPORARY for row in balances),
        "prior_nominal_nonzero": any(prior_nominal.values()),
    }
    return {**payload, "hash": _hash(payload)}


def _target_checks(organization, source, target):
    if target.starts_on != source.ends_on + timedelta(days=1) or target.pk == source.pk:
        raise ValidationError("سال مقصد باید بلافاصله پس از سال مبدأ آغاز شود.")
    if target.status != FiscalYearStatus.ACTIVE:
        raise ValidationError("سال مقصد برای افتتاحیه باز نیست.")
    first = (
        FiscalPeriod.objects.filter(organization=organization, fiscal_year=target)
        .order_by("starts_on")
        .first()
    )
    if (
        first is None
        or first.starts_on != target.starts_on
        or first.status != FiscalPeriodStatus.OPEN
    ):
        raise ValidationError(
            "سال مقصد باید دوره افتتاحیه باز در ابتدای سال داشته باشد."
        )
    historical = FiscalYearClosing.objects.filter(
        organization=organization, target_year=target, opening_journal__isnull=False
    ).values_list("opening_journal_id", flat=True)
    if (
        JournalEntry.objects.filter(
            organization=organization,
            period__fiscal_year=target,
            kind=JournalKind.OPENING,
        )
        .exclude(status__in=[JournalStatus.CANCELLED, JournalStatus.REJECTED])
        .exclude(pk__in=historical)
        .exists()
    ):
        raise ValidationError("سال مقصد دارای سند افتتاحیه متعارض است.")
    if (
        OpeningBalanceImport.objects.filter(
            organization=organization, fiscal_year=target
        )
        .exclude(status="rejected")
        .exists()
    ):
        raise ValidationError("سال مقصد دارای ورودی افتتاحیه متعارض است.")
    return first


def _verify_period_close(organization: Organization, event) -> None:
    event.clean()
    review = verify_signed_reconciliation_run(
        organization=organization, run=event.reconciliation_run
    )
    payload = {
        "period": str(event.period_id),
        "sequence": event.sequence,
        "action": "close",
        "requested_by": str(event.requested_by_id),
        "acted_by": str(event.acted_by_id),
        "reason": event.reason,
        "reconciliation": str(event.reconciliation_run_id),
        "reconciliation_evidence": event.reconciliation_run.result_hash,
        "reconciliation_sign_off": review.signed_evidence_hash,
        "trial_balance_input": event.trial_balance_run.input_hash,
        "trial_balance_result": event.trial_balance_run.result_hash,
        "balance_sheet_input": event.balance_sheet_run.input_hash,
        "balance_sheet_result": event.balance_sheet_run.result_hash,
        "profit_loss_input": event.profit_loss_run.input_hash,
        "profit_loss_result": event.profit_loss_run.result_hash,
    }
    if (
        event.requested_by_id == event.acted_by_id
        or _hash(payload) != event.evidence_hash
        or not AuditEvent.objects.filter(
            organization=organization,
            action=AuditAction.ACCOUNTING_PERIOD_CLOSED,
            entity_id=str(event.period_id),
            actor_id=event.acted_by.user_id,
            metadata__control_event=str(event.pk),
            metadata__evidence_hash=event.evidence_hash,
        ).exists()
    ):
        raise ValidationError("شواهد بستن دوره با ممیزی آن سازگار نیست.")


def _readiness(organization, source, target, *, closing=None):
    issues = []
    expected_status = FiscalYearStatus.CLOSING if closing else FiscalYearStatus.ACTIVE
    if source.status != expected_status:
        issues.append("سال مبدأ در وضعیت مجاز بستن نیست.")
    try:
        configuration = (
            FiscalClosingConfiguration.objects.select_related(
                "fiscal_year", "result_account", "retained_account", "configured_by"
            )
            .filter(organization=organization, fiscal_year=source)
            .order_by("-version")
            .first()
        )
        if configuration is None:
            raise FiscalClosingConfiguration.DoesNotExist
        configuration.clean()
    except (FiscalClosingConfiguration.DoesNotExist, ValidationError):
        configuration = None
        issues.append("حساب نتیجه سال و سود انباشته باید به‌درستی تنظیم شوند.")
    periods = list(
        FiscalPeriod.objects.filter(organization=organization, fiscal_year=source)
        .order_by("starts_on")
        .prefetch_related("control_events")
    )
    cursor = source.starts_on
    for period in periods:
        if period.starts_on != cursor:
            issues.append("دوره‌های سال مالی پوشش پیوسته ندارند.")
        cursor = period.ends_on + timedelta(days=1)
        if period.status != FiscalPeriodStatus.CLOSED:
            issues.append(f"دوره {period.name} هنوز بسته نشده است.")
            continue
        event = period.control_events.order_by("-sequence").first()
        if event is None or event.action != "close" or not event.reconciliation_run_id:
            issues.append(f"شواهد بستن دوره {period.name} کامل نیست.")
        else:
            try:
                _verify_period_close(organization, event)
            except ValidationError:
                issues.append(
                    f"تطبیق تأییدشده دوره {period.name} نیازمند بررسی مجدد است."
                )
    if not periods or cursor != source.ends_on + timedelta(days=1):
        issues.append("دوره‌ها باید تمام سال مالی را پوشش دهند.")
    if (
        JournalEntry.objects.filter(
            organization=organization,
            period__fiscal_year=source,
            status__in=[JournalStatus.DRAFT, JournalStatus.PROPOSED],
        ).exists()
        or OpeningBalanceImport.objects.filter(
            organization=organization,
            fiscal_year=source,
            status__in=["draft", "proposed"],
        ).exists()
    ):
        issues.append("اسناد یا ورودی‌های افتتاحیه تعیین‌تکلیف‌نشده وجود دارد.")
    if (
        FiscalYear.objects.filter(
            organization=organization,
            ends_on__lt=source.starts_on,
            periods__journals__status=JournalStatus.POSTED,
        )
        .exclude(status__in=[FiscalYearStatus.CLOSED, FiscalYearStatus.ROLLED_FORWARD])
        .exists()
    ):
        issues.append("سال‌های پیشین دارای ثبت قطعی باید ابتدا نهایی شوند.")
    if FiscalYearClosing.objects.filter(
        organization=organization,
        target_year=source,
        status__in=[ClosingStatus.PREPARED, ClosingStatus.CLOSED],
    ).exists():
        issues.append("انتقال مانده از سال پیشین هنوز نهایی نشده است.")
    conflicts = (
        FiscalYearClosing.objects.filter(organization=organization)
        .filter(Q(source_year=source) | Q(target_year=target))
        .exclude(status__in=[ClosingStatus.REVERSED, ClosingStatus.CANCELLED])
    )
    if closing:
        conflicts = conflicts.exclude(pk=closing.pk)
    if conflicts.exists():
        issues.append("بستن یا انتقال متعارض برای این سال‌ها وجود دارد.")
    try:
        _target_checks(organization, source, target)
    except ValidationError as exc:
        issues.extend(exc.messages)
    snapshot = None
    try:
        snapshot = _snapshot(organization, source)
        if snapshot["prior_nominal_nonzero"]:
            issues.append("مانده حساب‌های موقت پیش از این سال تعیین‌تکلیف نشده است.")
        if configuration and any(
            row["account"] == str(configuration.result_account_id)
            for row in snapshot["balances"]
        ):
            issues.append("حساب نتیجه سال پیش از بستن باید مانده صفر داشته باشد.")
        account_ids = [row["account"] for row in snapshot["balances"]]
        if (
            Account.objects.filter(pk__in=account_ids)
            .filter(Q(is_posting=False) | Q(archived_at__isnull=False))
            .exists()
        ):
            issues.append("حساب دارای مانده باید برگ فعال و قابل ثبت باشد.")
    except ValidationError as exc:
        issues.extend(exc.messages)
    return {
        "ready": not issues,
        "issues": list(dict.fromkeys(issues)),
        "snapshot": snapshot,
        "configuration": configuration,
    }


@transaction.atomic
def inspect_year_end(
    *,
    organization: Organization,
    actor: User,
    source_year: FiscalYear,
    target_year: FiscalYear,
) -> dict:
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    _permission(organization, actor, BusinessPermissionCode.ACCOUNTING_YEAR_END_VIEW)
    source, target = _year(organization, source_year), _year(organization, target_year)
    return _readiness(organization, source, target)


@_failure_evidence
@transaction.atomic
def configure_year_end(
    *,
    organization: Organization,
    actor: User,
    fiscal_year: FiscalYear,
    result_account: Account,
    retained_account: Account,
    reason: str,
) -> FiscalClosingConfiguration:
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    member = _permission(
        organization, actor, BusinessPermissionCode.ACCOUNTING_YEAR_END_CONFIGURE
    )
    year = _year(organization, fiscal_year)
    if (
        year.status != FiscalYearStatus.ACTIVE
        or year.year_end_closings.exclude(
            status__in=[ClosingStatus.REVERSED, ClosingStatus.CANCELLED]
        ).exists()
    ):
        raise ValidationError("تنظیم حساب‌ها فقط پیش از آغاز بستن سال مجاز است.")
    reason = _require_reason(reason)
    try:
        result_account = Account.objects.get(
            organization=organization, pk=result_account.pk
        )
        retained_account = Account.objects.get(
            organization=organization, pk=retained_account.pk
        )
    except Account.DoesNotExist as exc:
        raise PermissionDenied("حساب‌های بستن سال در دسترس نیستند.") from exc
    if (
        result_account.organization_id != organization.pk
        or retained_account.organization_id != organization.pk
    ):
        raise PermissionDenied("حساب‌های بستن سال در دسترس نیستند.")
    existing = (
        FiscalClosingConfiguration.objects.filter(
            organization=organization, fiscal_year=year
        )
        .order_by("-version")
        .first()
    )
    previous = None
    if existing:
        if (existing.result_account_id, existing.retained_account_id) == (
            result_account.pk,
            retained_account.pk,
        ):
            return existing
        previous = {"configuration": str(existing.pk), "version": existing.version}
    config = FiscalClosingConfiguration.objects.create(
        organization=organization,
        fiscal_year=year,
        version=existing.version + 1 if existing else 1,
        result_account=result_account,
        retained_account=retained_account,
        configured_by=member,
        reason=reason,
    )
    record_audit_event(
        action=AuditAction.ACCOUNTING_YEAR_END_CONFIGURED,
        entity_type="accounting.FiscalClosingConfiguration",
        entity_id=config.pk,
        organization=organization,
        actor=actor,
        metadata={
            "previous": previous,
            "year": str(year.pk),
            "result_account": str(config.result_account_id),
            "retained_account": str(config.retained_account_id),
            "reason": reason,
        },
    )
    return config


def _event(closing, member, previous, reason, extra=None):
    evidence = {
        "source_hash": closing.source_snapshot["hash"],
        "final_hash": closing.final_snapshot.get("hash"),
        "reconciliation_hash": _hash(closing.reconciliation),
        "closing_journal": str(closing.closing_journal_id),
        "opening_journal": str(closing.opening_journal_id),
        "closing_reversal": str(closing.closing_reversal_id),
        "opening_reversal": str(closing.opening_reversal_id),
        "annual_result": str(closing.annual_result),
        "configuration": str(closing.configuration_id),
        "result_account": str(closing.configuration.result_account_id),
        "retained_account": str(closing.configuration.retained_account_id),
        "initiated_by": str(closing.initiated_by_id),
        "close_approved_by": str(closing.close_approved_by_id),
        "opening_approved_by": str(closing.opening_approved_by_id),
        "closed_at": closing.closed_at.isoformat() if closing.closed_at else None,
        "rolled_forward_at": closing.rolled_forward_at.isoformat()
        if closing.rolled_forward_at
        else None,
        "source_year": str(closing.source_year_id),
        "target_year": str(closing.target_year_id),
        "cutoff": str(closing.cutoff_date),
        "version": closing.version,
        **(extra or {}),
    }
    event = FiscalYearClosingEvent.objects.create(
        organization=closing.organization,
        closing=closing,
        sequence=closing.events.count() + 1,
        actor=member,
        previous_status=previous,
        new_status=closing.status,
        reason=reason,
        evidence=evidence,
        evidence_hash=_hash(evidence),
    )
    record_audit_event(
        action=AuditAction.ACCOUNTING_YEAR_END_TRANSITION,
        entity_type="accounting.FiscalYearClosing",
        entity_id=closing.pk,
        organization=closing.organization,
        actor=member.user,
        metadata={
            "event": str(event.pk),
            "previous_status": previous,
            "status": closing.status,
            "reason": reason,
            "evidence_hash": event.evidence_hash,
        },
    )


def _verify(closing):
    if closing.status in (
        ClosingStatus.CLOSED,
        ClosingStatus.ROLLED_FORWARD,
        ClosingStatus.REVERSED,
    ):
        if (
            closing.closing_journal_id is None
            and closing.source_snapshot.get("nominal_balance_count") != 0
        ):
            raise ValidationError("سند اختتامیه لازم در پرونده وجود ندارد.")
        if (
            closing.status == ClosingStatus.ROLLED_FORWARD
            and closing.opening_journal_id is None
            and closing.final_snapshot.get("balances") != []
        ):
            raise ValidationError("سند افتتاحیه لازم در پرونده وجود ندارد.")
    for journal in (
        closing.closing_journal,
        closing.opening_journal,
        closing.closing_reversal,
        closing.opening_reversal,
    ):
        if journal is not None and (
            journal.organization_id != closing.organization_id
            or journal.status != JournalStatus.POSTED
            or journal.payload_hash != _journal_payload_hash(journal)
        ):
            raise ValidationError("سند سال مالی با شواهد قطعی سازگار نیست.")
    for snapshot in (closing.source_snapshot, closing.final_snapshot):
        if snapshot and snapshot.get("hash") != _hash(
            {k: v for k, v in snapshot.items() if k != "hash"}
        ):
            raise ValidationError("شواهد مانده‌های سال تغییر کرده است.")
    events = list(closing.events.order_by("sequence"))
    previous = ""
    for index, event in enumerate(events, 1):
        if (
            event.sequence != index
            or event.previous_status != previous
            or event.evidence_hash != _hash(event.evidence)
        ):
            raise ValidationError("تاریخچه بستن سال معتبر نیست.")
        if not AuditEvent.objects.filter(
            organization=closing.organization,
            action=AuditAction.ACCOUNTING_YEAR_END_TRANSITION,
            entity_id=str(closing.pk),
            actor_id=event.actor.user_id,
            metadata__event=str(event.pk),
            metadata__evidence_hash=event.evidence_hash,
        ).exists():
            raise ValidationError("شواهد ممیزی بستن سال کامل نیست.")
        if (
            event.new_status == ClosingStatus.PREPARED
            and event.actor_id != closing.initiated_by_id
            or event.new_status == ClosingStatus.CLOSED
            and event.actor_id != closing.close_approved_by_id
            or event.new_status == ClosingStatus.ROLLED_FORWARD
            and event.actor_id != closing.opening_approved_by_id
        ):
            raise ValidationError("تأییدکننده پرونده با تاریخچه سازگار نیست.")
        previous = event.new_status
    if events:
        last = events[-1].evidence
        expected = {
            "result_account": str(closing.configuration.result_account_id),
            "retained_account": str(closing.configuration.retained_account_id),
            "initiated_by": str(closing.initiated_by_id),
            "close_approved_by": str(closing.close_approved_by_id),
            "opening_approved_by": str(closing.opening_approved_by_id),
            "closed_at": closing.closed_at.isoformat() if closing.closed_at else None,
            "rolled_forward_at": closing.rolled_forward_at.isoformat()
            if closing.rolled_forward_at
            else None,
        }
        if any(last.get(key) != value for key, value in expected.items()):
            raise ValidationError(
                "تأییدکنندگان، تنظیمات یا زمان‌های پرونده با شواهد سازگار نیستند."
            )
        if (
            Decimal(last["annual_result"]) != closing.annual_result
            or last["configuration"] != str(closing.configuration_id)
            or last["source_year"] != str(closing.source_year_id)
            or last["target_year"] != str(closing.target_year_id)
            or last["cutoff"] != str(closing.cutoff_date)
            or last["version"] != closing.version
            or last["closing_journal"] != str(closing.closing_journal_id)
            or last["opening_journal"] != str(closing.opening_journal_id)
            or last["closing_reversal"] != str(closing.closing_reversal_id)
            or last["opening_reversal"] != str(closing.opening_reversal_id)
        ):
            raise ValidationError("اطلاعات پرونده با تأیید ثبت‌شده سازگار نیست.")
    if (
        not events
        or previous != closing.status
        or events[-1].evidence["reconciliation_hash"] != _hash(closing.reconciliation)
        or events[-1].evidence["source_hash"] != closing.source_snapshot["hash"]
        or events[-1].evidence["final_hash"] != closing.final_snapshot.get("hash")
    ):
        raise ValidationError("وضعیت بستن سال با شواهد آن سازگار نیست.")


def _locked(organization, closing):
    try:
        result = (
            FiscalYearClosing.objects.select_for_update()
            .select_related(
                "organization",
                "source_year",
                "target_year",
                "configuration__result_account",
                "configuration__retained_account",
                "initiated_by__user",
            )
            .get(organization=organization, pk=closing.pk)
        )
    except FiscalYearClosing.DoesNotExist as exc:
        raise PermissionDenied("پرونده بستن سال در دسترس نیست.") from exc
    _verify(result)
    return result


@_failure_evidence
@transaction.atomic
def prepare_year_end(
    *,
    organization: Organization,
    actor: User,
    source_year: FiscalYear,
    target_year: FiscalYear,
    reason: str,
) -> FiscalYearClosing:
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    member = _permission(
        organization, actor, BusinessPermissionCode.ACCOUNTING_YEAR_END_PREPARE
    )
    _permission(organization, actor, BusinessPermissionCode.ACCOUNTING_JOURNALS_PREPARE)
    _permission(organization, actor, BusinessPermissionCode.ACCOUNTING_JOURNALS_SUBMIT)
    reason = _require_reason(reason)
    source, target = _year(organization, source_year), _year(organization, target_year)
    existing = (
        FiscalYearClosing.objects.filter(organization=organization, source_year=source)
        .exclude(status__in=[ClosingStatus.REVERSED, ClosingStatus.CANCELLED])
        .first()
    )
    if existing:
        if (
            existing.target_year_id != target.pk
            or existing.initiated_by_id != member.pk
        ):
            raise ValidationError("درخواست بستن دیگری برای این سال وجود دارد.")
        _verify(existing)
        return existing
    readiness = _readiness(organization, source, target)
    if not readiness["ready"]:
        raise ValidationError(readiness["issues"])
    snapshot = readiness["snapshot"]
    annual_result = -sum(
        (
            Decimal(row["net"])
            for row in snapshot["balances"]
            if row["type"] in TEMPORARY
        ),
        ZERO,
    )
    version = (
        FiscalYearClosing.objects.filter(source_year=source).aggregate(
            value=Max("version")
        )["value"]
        or 0
    ) + 1
    closing = FiscalYearClosing.objects.create(
        organization=organization,
        source_year=source,
        target_year=target,
        configuration=readiness["configuration"],
        version=version,
        cutoff_date=source.ends_on,
        initiated_by=member,
        source_snapshot=snapshot,
        annual_result=annual_result,
        reason=reason,
    )
    FiscalYear.objects.filter(pk=source.pk).update(
        status=FiscalYearStatus.CLOSING, updated_at=timezone.now()
    )
    _event(closing, member, "", reason)
    return closing


def _line(journal, row, net, organization, actor):
    if not net:
        return
    add_journal_line(
        organization=organization,
        actor=actor,
        journal=journal,
        account=Account.objects.get(organization=organization, pk=row["account"]),
        line_number=journal.lines.count() + 1,
        debit=max(net, ZERO),
        credit=max(-net, ZERO),
        description="انتقال حاکم‌شده مانده سال مالی",
        **{
            name: JournalLine._meta.get_field(name).remote_field.model.objects.get(
                organization=organization, pk=row[name]
            )
            if row.get(name)
            else None
            for name in DIMENSIONS
        },
    )


def _generated_journal(closing, approver, period, kind, label):
    return create_journal(
        organization=closing.organization,
        actor=closing.initiated_by.user,
        period=period,
        kind=kind,
        document_date=period.ends_on
        if kind == JournalKind.CLOSING
        else period.starts_on,
        accounting_date=period.ends_on
        if kind == JournalKind.CLOSING
        else period.starts_on,
        description=f"{label}: {closing.source_year.name} ← {closing.target_year.name}",
        source_key=f"YEAR-END:{closing.pk}:{kind}",
        source_uuid=closing.pk,
        occurrence_id=closing.pk,
        evidence_reference=f"year-end:{closing.pk}:v{closing.version}",
        reconciliation_reference=f"year-end:{closing.pk}:reconciliation",
        cutoff_date=closing.cutoff_date if kind == JournalKind.OPENING else None,
    )


def _post_generated(closing, journal, actor, reason):
    journal = submit_journal(
        organization=closing.organization,
        actor=closing.initiated_by.user,
        journal=journal,
    )
    return post_journal(
        organization=closing.organization, actor=actor, journal=journal, reason=reason
    )


def _raise_discrepancies(closing: FiscalYearClosing, discrepancies: list[dict]) -> None:
    names = dict(
        Account.objects.filter(
            organization=closing.organization,
            pk__in=[row["account"] for row in discrepancies],
        ).values_list("pk", "code")
    )
    labels = {str(pk): code for pk, code in names.items()}
    details = "؛ ".join(
        f"{labels.get(row['account'], 'حساب')}: مانده مورد انتظار {row['expected']}، مانده محاسبه‌شده {row['actual']}"
        for row in discrepancies
    )
    raise ValidationError(
        "تطبیق مانده‌ها ناموفق است. %(details)s",
        code="year_end_reconciliation",
        params={"details": details, "discrepancies": discrepancies},
    )


def _reconcile_final(closing, final):
    expected = _balances(closing.source_snapshot["balances"])
    templates = {_key(row): row for row in closing.source_snapshot["balances"]}
    for row in closing.source_snapshot["balances"]:
        if row["type"] not in TEMPORARY:
            continue
        net = Decimal(row["net"])
        expected.pop(_key(row), None)
        retained = {
            **row,
            "account": str(closing.configuration.retained_account_id),
            "type": AccountType.EQUITY,
        }
        key = _key(retained)
        expected[key] = expected.get(key, ZERO) + net
        templates[key] = retained
    expected = {key: value for key, value in expected.items() if value}
    actual = _balances(final["balances"])
    discrepancies = [
        {
            "account": templates.get(key, {}).get("account", key[0]),
            "dimensions": list(key[2:]),
            "expected": str(expected.get(key, ZERO)),
            "actual": str(actual.get(key, ZERO)),
        }
        for key in sorted(expected.keys() | actual.keys(), key=str)
        if expected.get(key, ZERO) != actual.get(key, ZERO)
    ]
    if discrepancies:
        _raise_discrepancies(closing, discrepancies)
    if sum(actual.values(), ZERO) or any(
        row["type"] in TEMPORARY for row in final["balances"]
    ):
        raise ValidationError(
            "تطبیق بستن سال ناموفق است؛ مانده‌های دائمی، موقت یا سود انباشته سازگار نیست."
        )
    return {
        "status": "PASS",
        "closing_reference": str(closing.pk),
        "closing_entry_required": bool(
            closing.source_snapshot["nominal_balance_count"]
        ),
        "discrepancies": discrepancies,
        "annual_result": str(closing.annual_result),
        "source_hash": closing.source_snapshot["hash"],
        "final_hash": final["hash"],
        "checks": [
            "nominal_zero",
            "permanent_dimensions_preserved",
            "retained_earnings_transformation",
            "balanced",
        ],
    }


@_failure_evidence
@transaction.atomic
def approve_year_end(
    *, organization: Organization, actor: User, closing: FiscalYearClosing, reason: str
) -> FiscalYearClosing:
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    member = _permission(
        organization, actor, BusinessPermissionCode.ACCOUNTING_YEAR_END_APPROVE
    )
    _permission(organization, actor, BusinessPermissionCode.ACCOUNTING_JOURNALS_APPROVE)
    _permission(organization, actor, BusinessPermissionCode.ACCOUNTING_JOURNALS_POST)
    reason = _require_reason(reason)
    closing = _locked(organization, closing)
    if member.pk == closing.initiated_by_id:
        raise PermissionDenied("تهیه‌کننده نمی‌تواند بستن سال خود را تأیید کند.")
    if closing.status in (ClosingStatus.CLOSED, ClosingStatus.ROLLED_FORWARD):
        return closing
    if closing.status != ClosingStatus.PREPARED:
        raise ValidationError("پرونده در انتظار تأیید بستن نیست.")
    ready = _readiness(
        organization, closing.source_year, closing.target_year, closing=closing
    )
    if (
        not ready["ready"]
        or ready["snapshot"]["hash"] != closing.source_snapshot["hash"]
    ):
        raise ValidationError(
            ready["issues"] or ["مانده‌ها از زمان درخواست تغییر کرده‌اند."]
        )
    period = closing.source_year.periods.order_by("-ends_on").first()
    journal = None
    if closing.source_snapshot["nominal_balance_count"]:
        with _year_end_operation():
            journal = _generated_journal(
                closing, actor, period, JournalKind.CLOSING, "بستن سال"
            )
            summary = defaultdict(lambda: ZERO)
            templates = {}
            for row in closing.source_snapshot["balances"]:
                if row["type"] in TEMPORARY:
                    net = Decimal(row["net"])
                    _line(journal, row, -net, organization, closing.initiated_by.user)
                    result = {
                        **row,
                        "account": str(closing.configuration.result_account_id),
                        "type": AccountType.EQUITY,
                    }
                    _line(journal, result, net, organization, closing.initiated_by.user)
                    summary[_key(result)] += net
                    templates[_key(result)] = result
            for key, net in summary.items():
                result = templates[key]
                _line(journal, result, -net, organization, closing.initiated_by.user)
                _line(
                    journal,
                    {
                        **result,
                        "account": str(closing.configuration.retained_account_id),
                    },
                    net,
                    organization,
                    closing.initiated_by.user,
                )
            journal = _post_generated(closing, journal, actor, reason)
    final = _snapshot(organization, closing.source_year)
    reconciliation = _reconcile_final(closing, final)
    FiscalYearClosing.objects.filter(pk=closing.pk).update(
        status=ClosingStatus.CLOSED,
        closing_journal=journal,
        close_approved_by=member,
        closed_at=timezone.now(),
        final_snapshot=final,
        reconciliation=reconciliation,
    )
    FiscalYear.objects.filter(pk=closing.source_year_id).update(
        status=FiscalYearStatus.CLOSED, updated_at=timezone.now()
    )
    closing.refresh_from_db()
    _event(closing, member, ClosingStatus.PREPARED, reason)
    return closing


def _opening_reconciliation(closing, journal):
    expected = _balances(closing.final_snapshot["balances"])
    actual = defaultdict(lambda: ZERO)
    source_lines = list(journal.lines.select_related("account")) if journal else []
    if len(source_lines) != len(expected):
        raise ValidationError("تعداد ردیف‌های افتتاحیه با مانده نهایی سازگار نیست.")
    for line in source_lines:
        if line.account.account_type not in PERMANENT:
            raise ValidationError("افتتاحیه نباید دارای مانده حساب موقت باشد.")
        row = {
            "account": str(line.account_id),
            "currency": journal.currency,
            **{
                name: str(getattr(line, f"{name}_id"))
                if getattr(line, f"{name}_id")
                else None
                for name in DIMENSIONS
            },
        }
        if _key(row) in actual:
            raise ValidationError("ردیف تکراری در مانده افتتاحیه وجود دارد.")
        actual[_key(row)] += line.debit - line.credit
    actual = {key: net for key, net in actual.items() if net}
    discrepancies = [
        {
            "account": key[0],
            "dimensions": list(key[2:]),
            "expected": str(expected.get(key, ZERO)),
            "actual": str(actual.get(key, ZERO)),
        }
        for key in sorted(expected.keys() | actual.keys(), key=str)
        if expected.get(key, ZERO) != actual.get(key, ZERO)
    ]
    debit = sum((max(net, ZERO) for net in actual.values()), ZERO)
    credit = sum((max(-net, ZERO) for net in actual.values()), ZERO)
    if discrepancies:
        _raise_discrepancies(closing, discrepancies)
    if debit != credit:
        raise ValidationError(
            "تطبیق مانده اختتامیه و افتتاحیه ناموفق است؛ پذیرش انجام نشد."
        )
    return {
        **closing.reconciliation,
        "opening_status": "PASS",
        "opening_journal": str(journal.pk) if journal else None,
        "opening_reference": str(closing.pk),
        "opening_entry_required": bool(expected),
        "opening_payload_hash": journal.payload_hash if journal else None,
        "opening_debit": str(debit),
        "opening_credit": str(credit),
        "discrepancies": discrepancies,
        "checks": closing.reconciliation["checks"]
        + ["closing_equals_opening", "opening_nominal_zero"],
    }


@_failure_evidence
@transaction.atomic
def roll_forward_year_end(
    *, organization: Organization, actor: User, closing: FiscalYearClosing, reason: str
) -> FiscalYearClosing:
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    member = _permission(
        organization, actor, BusinessPermissionCode.ACCOUNTING_YEAR_END_APPROVE
    )
    _permission(organization, actor, BusinessPermissionCode.ACCOUNTING_JOURNALS_APPROVE)
    _permission(organization, actor, BusinessPermissionCode.ACCOUNTING_JOURNALS_POST)
    reason = _require_reason(reason)
    closing = _locked(organization, closing)
    if member.pk == closing.initiated_by_id:
        raise PermissionDenied("تهیه‌کننده نمی‌تواند افتتاحیه خود را تأیید کند.")
    if closing.status == ClosingStatus.ROLLED_FORWARD:
        if (
            _opening_reconciliation(closing, closing.opening_journal).get(
                "opening_status"
            )
            != "PASS"
        ):
            raise ValidationError("افتتاحیه نیازمند بررسی مجدد است.")
        return closing
    if (
        closing.status != ClosingStatus.CLOSED
        or closing.source_year.status != FiscalYearStatus.CLOSED
    ):
        raise ValidationError("سال مبدأ هنوز نهایی نشده است.")
    period = _target_checks(organization, closing.source_year, closing.target_year)
    final = _snapshot(organization, closing.source_year)
    if final["hash"] != closing.final_snapshot["hash"]:
        raise ValidationError("مانده‌های نهایی مبدأ تغییر کرده‌اند.")
    journal = None
    if final["balances"]:
        with _year_end_operation():
            journal = _generated_journal(
                closing, actor, period, JournalKind.OPENING, "افتتاحیه سال بعد"
            )
            for row in final["balances"]:
                _line(
                    journal,
                    row,
                    Decimal(row["net"]),
                    organization,
                    closing.initiated_by.user,
                )
            journal = _post_generated(closing, journal, actor, reason)
    reconciliation = _opening_reconciliation(closing, journal)
    FiscalYearClosing.objects.filter(pk=closing.pk).update(
        status=ClosingStatus.ROLLED_FORWARD,
        opening_journal=journal,
        opening_approved_by=member,
        rolled_forward_at=timezone.now(),
        reconciliation=reconciliation,
    )
    FiscalYear.objects.filter(pk=closing.source_year_id).update(
        status=FiscalYearStatus.ROLLED_FORWARD, updated_at=timezone.now()
    )
    closing.refresh_from_db()
    _event(closing, member, ClosingStatus.CLOSED, reason)
    return closing


@_failure_evidence
@transaction.atomic
def reopen_year_end(
    *,
    organization: Organization,
    actor: User,
    closing: FiscalYearClosing,
    requested_by: OrganizationMembership,
    reason: str,
) -> FiscalYearClosing:
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    member = _permission(
        organization, actor, BusinessPermissionCode.ACCOUNTING_YEAR_END_REOPEN
    )
    _permission(organization, actor, BusinessPermissionCode.ACCOUNTING_JOURNALS_APPROVE)
    _permission(organization, actor, BusinessPermissionCode.ACCOUNTING_JOURNALS_POST)
    requester = OrganizationMembership.objects.select_related("user").get(
        pk=requested_by.pk
    )
    _validate_independent_requester(
        organization=organization,
        actor_membership=member,
        requested_by=requester,
        permission=BusinessPermissionCode.ACCOUNTING_YEAR_END_REOPEN,
    )
    reason = _require_reason(reason)
    closing = _locked(organization, closing)
    if member.pk == closing.initiated_by_id:
        raise PermissionDenied("تهیه‌کننده نمی‌تواند بازگشایی پرونده خود را تأیید کند.")
    if closing.status == ClosingStatus.REVERSED:
        return closing
    if closing.status not in (ClosingStatus.CLOSED, ClosingStatus.ROLLED_FORWARD):
        raise ValidationError("فقط سال نهایی‌شده قابل بازگشایی است.")
    if (
        FiscalYearClosing.objects.filter(
            organization=organization, source_year=closing.target_year
        )
        .exclude(status__in=[ClosingStatus.REVERSED, ClosingStatus.CANCELLED])
        .exists()
    ):
        raise ValidationError(
            "سال بعد دارای فرایند بستن فعال است؛ بازگشایی خودکار مجاز نیست."
        )
    related = FiscalYearClosing.objects.filter(
        organization=organization,
        source_year=closing.source_year,
        target_year=closing.target_year,
    )
    allowed = set()
    for row in related:
        allowed.update([row.opening_journal_id, row.opening_reversal_id])
    if (
        JournalEntry.objects.filter(
            organization=organization,
            period__fiscal_year=closing.target_year,
            status=JournalStatus.POSTED,
        )
        .exclude(pk__in=[pk for pk in allowed if pk])
        .exists()
    ):
        raise ValidationError(
            "سال بعد دارای ثبت قطعی دیگر است؛ تصمیم حسابداری جداگانه برای اصلاح لازم است."
        )
    previous = closing.status
    if (
        _snapshot(organization, closing.source_year)["hash"]
        != closing.final_snapshot["hash"]
    ):
        raise ValidationError("شواهد نهایی مبدأ تغییر کرده است.")
    with _year_end_operation():
        opening_reversal = None
        if closing.opening_journal_id:
            _opening_reconciliation(closing, closing.opening_journal)
            opening_reversal = reverse_journal(
                organization=organization,
                actor=actor,
                original=closing.opening_journal,
                requested_by=requester,
                accounting_date=closing.opening_journal.accounting_date,
                period=closing.opening_journal.period,
                reason=reason,
            )
        reversal = None
        if closing.closing_journal_id:
            reversal = reverse_journal(
                organization=organization,
                actor=actor,
                original=closing.closing_journal,
                requested_by=requester,
                accounting_date=closing.cutoff_date,
                period=closing.closing_journal.period,
                reason=reason,
            )
        # Existing protected period authority decides whether these actors may reopen.
        FiscalYear.objects.filter(pk=closing.source_year_id).update(
            status=FiscalYearStatus.ACTIVE, updated_at=timezone.now()
        )
        reopen_period(
            organization=organization,
            actor=actor,
            period=closing.source_year.periods.order_by("-ends_on").first(),
            requested_by=requester,
            reason=reason,
        )
    for original, inverse in (
        (closing.closing_journal, reversal),
        (closing.opening_journal, opening_reversal),
    ):
        if original is not None and inverse is not None:
            original_amounts = [
                (
                    line.account_id,
                    line.debit,
                    line.credit,
                    *(getattr(line, f"{name}_id") for name in DIMENSIONS),
                )
                for line in original.lines.order_by("line_number")
            ]
            inverse_amounts = [
                (
                    line.account_id,
                    line.credit,
                    line.debit,
                    *(getattr(line, f"{name}_id") for name in DIMENSIONS),
                )
                for line in inverse.lines.order_by("line_number")
            ]
            if original_amounts != inverse_amounts:
                raise ValidationError("تطبیق برگشت اسناد سال ناموفق است.")
    reconciliation = {
        **closing.reconciliation,
        "reversal_status": "PASS",
        "reopen_reason": reason,
        "requested_by": str(requester.pk),
    }
    FiscalYearClosing.objects.filter(pk=closing.pk).update(
        status=ClosingStatus.REVERSED,
        closing_reversal=reversal,
        opening_reversal=opening_reversal,
        reconciliation=reconciliation,
    )
    closing.refresh_from_db()
    _event(closing, member, previous, reason, {"requested_by": str(requester.pk)})
    return closing


@_failure_evidence
@transaction.atomic
def cancel_year_end(
    *, organization: Organization, actor: User, closing: FiscalYearClosing, reason: str
) -> FiscalYearClosing:
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    member = _permission(
        organization, actor, BusinessPermissionCode.ACCOUNTING_YEAR_END_PREPARE
    )
    reason = _require_reason(reason)
    closing = _locked(organization, closing)
    if member.pk != closing.initiated_by_id:
        _permission(
            organization, actor, BusinessPermissionCode.ACCOUNTING_YEAR_END_APPROVE
        )
    if closing.status == ClosingStatus.CANCELLED:
        return closing
    if closing.status != ClosingStatus.PREPARED:
        raise ValidationError(
            "پس از ثبت اختتامیه فقط بازگشایی با برگشت اسناد مجاز است."
        )
    FiscalYearClosing.objects.filter(pk=closing.pk).update(
        status=ClosingStatus.CANCELLED
    )
    FiscalYear.objects.filter(pk=closing.source_year_id).update(
        status=FiscalYearStatus.ACTIVE, updated_at=timezone.now()
    )
    closing.refresh_from_db()
    _event(closing, member, ClosingStatus.PREPARED, reason)
    return closing
