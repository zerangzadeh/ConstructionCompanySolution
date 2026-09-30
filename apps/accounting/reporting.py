"""Accounting-owned financial read models built only from posted journal lines."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import QuerySet

from apps.accounting.models import (
    Account,
    AccountType,
    FinancialStatementKind,
    FinancialStatementLineSnapshot,
    FinancialStatementRun,
    JournalLine,
    JournalStatus,
)
from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode, Organization

ZERO = Decimal(0)
BALANCE_SHEET_TYPES = frozenset(
    {AccountType.ASSET, AccountType.LIABILITY, AccountType.EQUITY}
)
PROFIT_LOSS_TYPES = frozenset({AccountType.INCOME, AccountType.EXPENSE})


@dataclass(frozen=True, slots=True)
class StatementLine:
    account_id: object
    account_code: str
    account_name: str
    account_type: str
    opening_debit: Decimal
    opening_credit: Decimal
    period_debit: Decimal
    period_credit: Decimal
    closing_debit: Decimal
    closing_credit: Decimal
    amount: Decimal
    source_line_count: int
    source_line_evidence: tuple[dict[str, object], ...]


@dataclass(frozen=True, slots=True)
class StatementResult:
    kind: str
    starts_on: date | None
    ends_on: date
    source_line_count: int
    debit_total: Decimal
    credit_total: Decimal
    net_total: Decimal
    scope_hash: str
    input_hash: str
    result_hash: str
    lines: tuple[StatementLine, ...]


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _validate_retained_statement(
    *, run: FinancialStatementRun, result: StatementResult
) -> None:
    """Fail closed if a retained run or any exact line snapshot diverges."""

    if (
        run.scope_hash != result.scope_hash
        or run.input_hash != result.input_hash
        or run.result_hash != result.result_hash
        or run.source_line_count != result.source_line_count
        or run.debit_total != result.debit_total
        or run.credit_total != result.credit_total
        or run.net_total != result.net_total
    ):
        raise ValidationError("شواهد گزارش نگهداری‌شده با نتیجه فعلی ناسازگار است.")
    snapshots = list(run.lines.order_by("sequence", "pk"))
    if [item.sequence for item in snapshots] != list(
        range(1, len(snapshots) + 1)
    ) or len(snapshots) != len(result.lines):
        raise ValidationError("ردیف‌های گزارش نگهداری‌شده کامل و پیوسته نیست.")
    for item, expected in zip(snapshots, result.lines, strict=True):
        if any(
            (
                item.account_id != expected.account_id,
                item.account_code != expected.account_code,
                item.account_name != expected.account_name,
                item.account_type != expected.account_type,
                item.opening_debit != expected.opening_debit,
                item.opening_credit != expected.opening_credit,
                item.period_debit != expected.period_debit,
                item.period_credit != expected.period_credit,
                item.closing_debit != expected.closing_debit,
                item.closing_credit != expected.closing_credit,
                item.amount != expected.amount,
                item.source_line_count != expected.source_line_count,
                item.source_line_evidence != list(expected.source_line_evidence),
            )
        ):
            raise ValidationError("ردیف‌های گزارش نگهداری‌شده دستکاری شده است.")


def _posted_lines(*, organization: Organization, ends_on: date) -> list[JournalLine]:
    lines = list(
        JournalLine.objects.filter(
            organization=organization,
            journal__status=JournalStatus.POSTED,
            journal__accounting_date__lte=ends_on,
        )
        .select_related("journal", "account")
        .order_by(
            "journal__accounting_date",
            "journal__number",
            "line_number",
            "pk",
        )
    )
    if any(not line.account_snapshot for line in lines):
        raise ValidationError("گزارش مالی بدون تصویر قطعی حساب قابل تولید نیست.")
    return lines


def build_statement(
    *,
    organization: Organization,
    actor: User,
    kind: str,
    ends_on: date,
    starts_on: date | None = None,
) -> StatementResult:
    """Build a deterministic read model without retaining or mutating evidence."""

    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_REPORTS_VIEW,
        message="اختیار مشاهده گزارش‌های حسابداری را ندارید.",
    )
    if kind not in FinancialStatementKind.values:
        raise ValidationError("نوع گزارش مالی معتبر نیست.")
    if kind == FinancialStatementKind.PROFIT_LOSS and starts_on is None:
        raise ValidationError("صورت سود و زیان به تاریخ شروع نیاز دارد.")
    if starts_on and ends_on < starts_on:
        raise ValidationError("پایان بازه گزارش پیش از شروع آن است.")

    source_lines = _posted_lines(organization=organization, ends_on=ends_on)
    if kind == FinancialStatementKind.BALANCE_SHEET:
        allowed_types = BALANCE_SHEET_TYPES
    elif kind == FinancialStatementKind.PROFIT_LOSS:
        allowed_types = PROFIT_LOSS_TYPES
    else:
        allowed_types = frozenset(AccountType.values)

    included = [
        line
        for line in source_lines
        if line.account_snapshot.get("type") in allowed_types
        and (
            kind != FinancialStatementKind.PROFIT_LOSS
            or line.journal.accounting_date >= starts_on
        )
    ]
    evidence = [
        {
            "line": str(line.pk),
            "journal": str(line.journal_id),
            "journal_number": line.journal.number,
            "accounting_date": line.journal.accounting_date.isoformat(),
            "payload_hash": line.journal.payload_hash,
            "account": line.account_snapshot,
            "dimensions": line.dimension_snapshot,
            "source_line_uuid": str(line.source_line_uuid),
            "debit": str(line.debit),
            "credit": str(line.credit),
        }
        for line in included
    ]
    scope = {
        "version": 1,
        "organization": str(organization.pk),
        "kind": kind,
        "starts_on": starts_on.isoformat() if starts_on else None,
        "ends_on": ends_on.isoformat(),
        "currency": "IRR",
        "authority": "posted_journal_lines",
    }

    balances: dict[object, dict[str, object]] = defaultdict(
        lambda: {
            "opening_debit": ZERO,
            "opening_credit": ZERO,
            "period_debit": ZERO,
            "period_credit": ZERO,
            "count": 0,
        }
    )
    account_evidence: dict[object, dict[str, str]] = {}
    source_evidence_by_account: dict[object, list[dict[str, object]]] = defaultdict(
        list
    )
    for line in included:
        account_id = line.account_id
        account_evidence[account_id] = line.account_snapshot
        source_evidence_by_account[account_id].append(
            {
                "line": str(line.pk),
                "journal": str(line.journal_id),
                "journal_number": line.journal.number,
                "accounting_date": line.journal.accounting_date.isoformat(),
                "source_line_uuid": str(line.source_line_uuid),
                "debit": str(line.debit),
                "credit": str(line.credit),
            }
        )
        row = balances[account_id]
        is_opening = bool(starts_on and line.journal.accounting_date < starts_on)
        if is_opening:
            row["opening_debit"] += line.debit  # type: ignore[operator]
            row["opening_credit"] += line.credit  # type: ignore[operator]
        else:
            row["period_debit"] += line.debit  # type: ignore[operator]
            row["period_credit"] += line.credit  # type: ignore[operator]
        row["count"] += 1  # type: ignore[operator]

    rows: list[StatementLine] = []
    for account_id, values in balances.items():
        snapshot = account_evidence[account_id]
        opening_net = values["opening_debit"] - values["opening_credit"]  # type: ignore[operator]
        period_net = values["period_debit"] - values["period_credit"]  # type: ignore[operator]
        closing_net = opening_net + period_net
        closing_debit = max(closing_net, ZERO)
        closing_credit = max(-closing_net, ZERO)
        account_type = snapshot["type"]
        amount = (
            -closing_net
            if account_type
            in (AccountType.LIABILITY, AccountType.EQUITY, AccountType.INCOME)
            else closing_net
        )
        rows.append(
            StatementLine(
                account_id=account_id,
                account_code=snapshot["code"],
                account_name=snapshot["name"],
                account_type=account_type,
                opening_debit=values["opening_debit"],  # type: ignore[arg-type]
                opening_credit=values["opening_credit"],  # type: ignore[arg-type]
                period_debit=values["period_debit"],  # type: ignore[arg-type]
                period_credit=values["period_credit"],  # type: ignore[arg-type]
                closing_debit=closing_debit,
                closing_credit=closing_credit,
                amount=amount,
                source_line_count=values["count"],  # type: ignore[arg-type]
                source_line_evidence=tuple(source_evidence_by_account[account_id]),
            )
        )
    rows.sort(key=lambda row: row.account_code)
    result_payload = [
        {
            "account_id": str(row.account_id),
            "account_code": row.account_code,
            "account_name": row.account_name,
            "account_type": row.account_type,
            "opening_debit": str(row.opening_debit),
            "opening_credit": str(row.opening_credit),
            "period_debit": str(row.period_debit),
            "period_credit": str(row.period_credit),
            "closing_debit": str(row.closing_debit),
            "closing_credit": str(row.closing_credit),
            "amount": str(row.amount),
            "source_line_count": row.source_line_count,
            "source_line_evidence": row.source_line_evidence,
        }
        for row in rows
    ]
    debit_total = sum((row.period_debit for row in rows), ZERO)
    credit_total = sum((row.period_credit for row in rows), ZERO)
    if kind == FinancialStatementKind.PROFIT_LOSS:
        net_total = sum(
            (
                row.amount if row.account_type == AccountType.INCOME else -row.amount
                for row in rows
            ),
            ZERO,
        )
    elif kind == FinancialStatementKind.BALANCE_SHEET:
        net_total = sum(
            (
                row.amount if row.account_type == AccountType.ASSET else -row.amount
                for row in rows
            ),
            ZERO,
        )
    else:
        net_total = sum((row.closing_debit - row.closing_credit for row in rows), ZERO)
    return StatementResult(
        kind=kind,
        starts_on=starts_on,
        ends_on=ends_on,
        source_line_count=len(included),
        debit_total=debit_total,
        credit_total=credit_total,
        net_total=net_total,
        scope_hash=_canonical_hash(scope),
        input_hash=_canonical_hash(evidence),
        result_hash=_canonical_hash(result_payload),
        lines=tuple(rows),
    )


@transaction.atomic
def retain_statement(
    *,
    organization: Organization,
    actor: User,
    kind: str,
    ends_on: date,
    starts_on: date | None = None,
) -> FinancialStatementRun:
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_STATEMENTS_RUN,
        message="اختیار نگهداری صورت مالی را ندارید.",
    )
    result = build_statement(
        organization=organization,
        actor=actor,
        kind=kind,
        starts_on=starts_on,
        ends_on=ends_on,
    )
    existing = FinancialStatementRun.objects.filter(
        organization=organization,
        kind=kind,
        starts_on=starts_on,
        ends_on=ends_on,
        input_hash=result.input_hash,
    ).first()
    if existing:
        _validate_retained_statement(run=existing, result=result)
        return existing
    run = FinancialStatementRun.objects.create(
        organization=organization,
        kind=kind,
        starts_on=starts_on,
        ends_on=ends_on,
        scope_hash=result.scope_hash,
        input_hash=result.input_hash,
        result_hash=result.result_hash,
        source_line_count=result.source_line_count,
        debit_total=result.debit_total,
        credit_total=result.credit_total,
        net_total=result.net_total,
        created_by=membership,
    )
    FinancialStatementLineSnapshot.objects.bulk_create(
        [
            FinancialStatementLineSnapshot(
                organization=organization,
                run=run,
                sequence=sequence,
                account_id=row.account_id,
                account_code=row.account_code,
                account_name=row.account_name,
                account_type=row.account_type,
                opening_debit=row.opening_debit,
                opening_credit=row.opening_credit,
                period_debit=row.period_debit,
                period_credit=row.period_credit,
                closing_debit=row.closing_debit,
                closing_credit=row.closing_credit,
                amount=row.amount,
                source_line_count=row.source_line_count,
                source_line_evidence=list(row.source_line_evidence),
            )
            for sequence, row in enumerate(result.lines, start=1)
        ]
    )
    record_audit_event(
        action=AuditAction.ACCOUNTING_STATEMENT_RETAINED,
        entity_type="accounting.FinancialStatementRun",
        entity_id=run.pk,
        organization=organization,
        actor=actor,
        metadata={
            "kind": kind,
            "starts_on": starts_on.isoformat() if starts_on else None,
            "ends_on": ends_on.isoformat(),
            "input_hash": result.input_hash,
            "result_hash": result.result_hash,
        },
    )
    return run


def list_general_ledger(
    *,
    organization: Organization,
    actor: User,
    account: Account,
    starts_on: date | None,
    ends_on: date,
) -> QuerySet[JournalLine]:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_REPORTS_VIEW,
        message="اختیار مشاهده دفتر حساب را ندارید.",
    )
    if account.organization_id != organization.pk:
        raise PermissionDenied("حساب متعلق به Tenant دیگری است.")
    if starts_on and ends_on < starts_on:
        raise ValidationError("پایان بازه گزارش پیش از شروع آن است.")
    queryset = JournalLine.objects.filter(
        organization=organization,
        account=account,
        journal__status=JournalStatus.POSTED,
        journal__accounting_date__lte=ends_on,
    )
    if starts_on:
        queryset = queryset.filter(journal__accounting_date__gte=starts_on)
    return queryset.select_related("journal").order_by(
        "journal__accounting_date", "journal__number", "line_number"
    )
