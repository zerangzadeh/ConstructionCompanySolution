"""Lineage reconciliation for the approved P2 manual/opening boundary."""

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, QuerySet

from apps.accounting.models import (
    JournalEntry,
    JournalKind,
    JournalLine,
    JournalStatus,
    OpeningBalanceImport,
    OpeningBalanceImportLine,
    OpeningImportStatus,
    ReconciliationExceptionDisposition,
    ReconciliationExceptionDispositionCode,
    ReconciliationExceptionSnapshot,
    ReconciliationReview,
    ReconciliationRun,
    ReconciliationScope,
    ReconciliationTieOutSnapshot,
    ReconciliationTieOutType,
)
from apps.accounting.posting_registry import get_posting_contract
from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode, Organization

RECONCILIATION_SCOPE_VERSION = 2


def _bounded_journals(
    *, organization: Organization, cutoff_date: date
) -> QuerySet[JournalEntry]:
    return JournalEntry.objects.filter(
        organization=organization,
        accounting_date__lte=cutoff_date,
    ).filter(
        Q(source_kind="manual", event_kind="manual_entry")
        | Q(source_kind="opening", event_kind="opening_balance")
        | Q(source_kind="accounting", event_kind="reversal")
        | Q(source_kind="accounting", event_kind="replacement")
    )


@dataclass(frozen=True, slots=True)
class ReconciliationException:
    code: str
    source_uuid: UUID
    journal_uuid: UUID | None
    line_uuid: UUID | None = None


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    cutoff_date: date
    source_count: int
    journal_count: int
    posted_count: int
    pending_count: int
    debit_total: Decimal
    credit_total: Decimal
    exceptions: tuple[ReconciliationException, ...]
    tie_outs: tuple["ReconciliationTieOut", ...]


@dataclass(frozen=True, slots=True)
class ReconciliationTieOut:
    tie_out_type: str
    source_uuid: UUID
    source_version: int
    journal_uuid: UUID | None
    source_line_count: int
    journal_line_count: int
    source_debit_total: Decimal
    source_credit_total: Decimal
    journal_debit_total: Decimal
    journal_credit_total: Decimal
    count_matches: bool
    amount_matches: bool
    source_version_matches: bool
    exact_line_matches: bool
    dimension_matches: bool
    correction_chain_matches: bool
    evidence: dict[str, object]


def _opening_line_signature(line: object) -> tuple[object, ...]:
    return (
        line.line_number,
        line.account_id,
        line.debit,
        line.credit,
        line.project_id,
        line.site_id,
        line.wbs_node_id,
        line.party_id,
    )


def _dimension_signature(line: object) -> tuple[object, ...]:
    return (line.project_id, line.site_id, line.wbs_node_id, line.party_id)


def _line_evidence(line: object) -> dict[str, object]:
    return {
        "line_uuid": str(line.pk),
        "source_line_uuid": (
            str(line.source_line_uuid)
            if getattr(line, "source_line_uuid", None)
            else None
        ),
        "line_number": line.line_number,
        "account_uuid": str(line.account_id),
        "debit": str(line.debit),
        "credit": str(line.credit),
        "dimensions": {
            "project_uuid": str(line.project_id) if line.project_id else None,
            "site_uuid": str(line.site_id) if line.site_id else None,
            "wbs_node_uuid": str(line.wbs_node_id) if line.wbs_node_id else None,
            "party_uuid": str(line.party_id) if line.party_id else None,
        },
        "account_snapshot": getattr(line, "account_snapshot", None),
        "dimension_snapshot": getattr(line, "dimension_snapshot", None),
    }


def _line_totals(lines: list[object]) -> tuple[Decimal, Decimal]:
    # Match retained DecimalField scale even when there are no lines to sum.
    return (
        sum((line.debit for line in lines), Decimal("0.000000")),
        sum((line.credit for line in lines), Decimal("0.000000")),
    )


def _posted_dimensions_match(journal: JournalEntry, lines: list[object]) -> bool:
    if journal.status != JournalStatus.POSTED:
        return True
    for line in lines:
        expected = {
            key: str(value)
            for key, value in {
                "project": line.project_id,
                "site": line.site_id,
                "wbs": line.wbs_node_id,
                "party": line.party_id,
            }.items()
            if value is not None
        }
        actual = {
            key: value.get("id")
            for key, value in line.dimension_snapshot.items()
            if isinstance(value, dict)
        }
        if actual != expected:
            return False
    return True


def _self_source_tie_out(
    *, journal: JournalEntry, tie_out_type: str
) -> ReconciliationTieOut:
    lines = list(journal.lines.all())
    debit, credit = _line_totals(lines)
    identity_matches = all(line.source_line_uuid == line.pk for line in lines)
    version_matches = journal.source_version == 1
    dimension_matches = _posted_dimensions_match(journal, lines)
    adjustment_chain_matches = True
    if journal.adjusts_id:
        adjustment_chain_matches = bool(
            journal.kind == JournalKind.MANUAL
            and journal.adjusts.status == JournalStatus.POSTED
            and journal.adjusts.period.status == "closed"
            and journal.period.is_adjustment
            and journal.adjustment_reason.strip()
        )
    evidence = {
        "source_model": "accounting.JournalEntry",
        "journal_kind": journal.kind,
        "journal_status": journal.status,
        "adjusts_journal_uuid": str(journal.adjusts_id) if journal.adjusts_id else None,
        "adjustment_reason": journal.adjustment_reason,
        "lines": [_line_evidence(line) for line in lines],
    }
    return ReconciliationTieOut(
        tie_out_type=tie_out_type,
        source_uuid=journal.source_uuid,
        source_version=journal.source_version,
        journal_uuid=journal.pk,
        source_line_count=len(lines),
        journal_line_count=len(lines),
        source_debit_total=debit,
        source_credit_total=credit,
        journal_debit_total=debit,
        journal_credit_total=credit,
        count_matches=True,
        amount_matches=True,
        source_version_matches=version_matches,
        exact_line_matches=identity_matches,
        dimension_matches=dimension_matches,
        correction_chain_matches=adjustment_chain_matches,
        evidence=evidence,
    )


def _opening_import_tie_out(
    opening_import: OpeningBalanceImport,
) -> ReconciliationTieOut:
    source_lines = list(opening_import.lines.all())
    journal = opening_import.accepted_journal
    journal_lines = list(journal.lines.all()) if journal else []
    source_debit, source_credit = _line_totals(source_lines)
    journal_debit, journal_credit = _line_totals(journal_lines)
    source_by_id = {line.pk: line for line in source_lines}
    exact_line_matches = bool(journal) and all(
        (source_line := source_by_id.get(line.source_line_uuid)) is not None
        and _opening_line_signature(source_line) == _opening_line_signature(line)
        for line in journal_lines
    )
    pending = opening_import.status != OpeningImportStatus.ACCEPTED
    count_matches = pending or len(source_lines) == len(journal_lines)
    amount_matches = pending or (source_debit, source_credit) == (
        journal_debit,
        journal_credit,
    )
    source_version = journal.source_version if journal else 1
    source_version_matches = pending or (bool(journal) and source_version == 1)
    dimension_matches = pending or (
        bool(journal)
        and all(
            (source_line := source_by_id.get(line.source_line_uuid)) is not None
            and _dimension_signature(source_line) == _dimension_signature(line)
            for line in journal_lines
        )
    )
    if journal:
        dimension_matches = dimension_matches and _posted_dimensions_match(
            journal, journal_lines
        )
    chain_matches = pending or (
        bool(journal)
        and (
            journal.organization_id == opening_import.organization_id
            and journal.source_uuid == opening_import.pk
            and journal.occurrence_id == opening_import.pk
            and journal.kind == JournalKind.OPENING
            and journal.status == JournalStatus.POSTED
        )
    )
    evidence = {
        "source_model": "accounting.OpeningBalanceImport",
        "source_status": opening_import.status,
        "journal_kind": journal.kind if journal else None,
        "journal_status": journal.status if journal else None,
        "source_lines": [_line_evidence(line) for line in source_lines],
        "journal_lines": [_line_evidence(line) for line in journal_lines],
    }
    return ReconciliationTieOut(
        tie_out_type=ReconciliationTieOutType.OPENING,
        source_uuid=opening_import.pk,
        source_version=source_version,
        journal_uuid=journal.pk if journal else None,
        source_line_count=len(source_lines),
        journal_line_count=len(journal_lines),
        source_debit_total=source_debit,
        source_credit_total=source_credit,
        journal_debit_total=journal_debit,
        journal_credit_total=journal_credit,
        count_matches=count_matches,
        amount_matches=amount_matches,
        source_version_matches=source_version_matches,
        exact_line_matches=pending or (exact_line_matches and count_matches),
        dimension_matches=dimension_matches and count_matches,
        correction_chain_matches=chain_matches,
        evidence=evidence,
    )


def _correction_tie_out(journal: JournalEntry) -> ReconciliationTieOut:
    source = (
        journal.reverses if journal.kind == JournalKind.REVERSAL else journal.replaces
    )
    source_lines = list(source.lines.all()) if source else []
    journal_lines = list(journal.lines.all())
    source_debit, source_credit = _line_totals(source_lines)
    journal_debit, journal_credit = _line_totals(journal_lines)
    source_by_id = {line.pk: line for line in source_lines}
    link_matches = bool(source) and (
        journal.source_uuid == source.pk and journal.occurrence_id == source.pk
    )
    if journal.kind == JournalKind.REVERSAL:
        version_matches = journal.source_version == 1
        exact_matches = all(
            (source_line := source_by_id.get(line.source_line_uuid)) is not None
            and source_line.line_number == line.line_number
            and source_line.account_id == line.account_id
            and source_line.debit == line.credit
            and source_line.credit == line.debit
            for line in journal_lines
        )
        dimension_matches = all(
            (source_line := source_by_id.get(line.source_line_uuid)) is not None
            and _dimension_signature(source_line) == _dimension_signature(line)
            for line in journal_lines
        )
        amount_matches = (source_debit, source_credit) == (
            journal_credit,
            journal_debit,
        )
    else:
        version_matches = (
            bool(source) and journal.source_version == source.source_version + 1
        )
        exact_matches = all(line.source_line_uuid == line.pk for line in journal_lines)
        dimension_matches = True
        amount_matches = True
    count_matches = bool(source) and (
        journal.kind == JournalKind.REPLACEMENT
        or len(source_lines) == len(journal_lines)
    )
    dimension_matches = dimension_matches and _posted_dimensions_match(
        journal, journal_lines
    )
    chain_matches = link_matches and version_matches
    if journal.kind == JournalKind.REVERSAL:
        chain_matches = chain_matches and count_matches and amount_matches
    evidence = {
        "source_model": "accounting.JournalEntry",
        "correction_kind": journal.kind,
        "source_journal_uuid": str(source.pk) if source else None,
        "source_journal_kind": source.kind if source else None,
        "source_journal_version": source.source_version if source else None,
        "journal_status": journal.status,
        "source_lines": [_line_evidence(line) for line in source_lines],
        "journal_lines": [_line_evidence(line) for line in journal_lines],
    }
    return ReconciliationTieOut(
        tie_out_type=ReconciliationTieOutType.CORRECTION,
        source_uuid=journal.source_uuid,
        source_version=journal.source_version,
        journal_uuid=journal.pk,
        source_line_count=len(source_lines),
        journal_line_count=len(journal_lines),
        source_debit_total=source_debit,
        source_credit_total=source_credit,
        journal_debit_total=journal_debit,
        journal_credit_total=journal_credit,
        count_matches=count_matches,
        amount_matches=amount_matches,
        source_version_matches=version_matches,
        exact_line_matches=exact_matches and count_matches,
        dimension_matches=dimension_matches and count_matches,
        correction_chain_matches=chain_matches,
        evidence=evidence,
    )


def _tie_out_exceptions(
    tie_outs: list[ReconciliationTieOut],
) -> list[ReconciliationException]:
    exceptions: list[ReconciliationException] = []
    checks = (
        ("count_matches", "count_mismatch"),
        ("amount_matches", "amount_mismatch"),
        ("source_version_matches", "source_version_mismatch"),
        ("exact_line_matches", "exact_line_mismatch"),
        ("dimension_matches", "dimension_mismatch"),
        ("correction_chain_matches", "correction_chain_mismatch"),
    )
    for tie_out in tie_outs:
        for field_name, suffix in checks:
            if not getattr(tie_out, field_name):
                exceptions.append(
                    ReconciliationException(
                        code=f"{tie_out.tie_out_type}_{suffix}",
                        source_uuid=tie_out.source_uuid,
                        journal_uuid=tie_out.journal_uuid,
                    )
                )
    return exceptions


def inspect_manual_opening_reconciliation(
    *, organization: Organization, actor: User, cutoff_date: date
) -> ReconciliationReport:
    """Inspect retained source-to-journal lineage without creating a signed run.

    This synchronous preflight is deliberately limited to Accounting-owned manual,
    opening, reversal and replacement facts. Durable runs and protected sign-off
    remain later sessions in the recalibrated S13-S22 contract.
    """

    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_VIEW,
        message="اختیار مشاهده تطبیق حسابداری را ندارید.",
    )
    journals = list(
        _bounded_journals(organization=organization, cutoff_date=cutoff_date)
        .prefetch_related("lines")
        .order_by("accounting_date", "created_at", "pk")
    )
    exceptions: list[ReconciliationException] = []
    posted_count = 0
    pending_count = 0
    debit_total = Decimal("0.000000")
    credit_total = Decimal("0.000000")

    for journal in journals:
        get_posting_contract(
            source_kind=journal.source_kind, event_kind=journal.event_kind
        )
        lines = list(journal.lines.all())
        for line in lines:
            if not line.source_line_uuid:
                exceptions.append(
                    ReconciliationException(
                        code="missing_source_line",
                        source_uuid=journal.source_uuid,
                        journal_uuid=journal.pk,
                        line_uuid=line.pk,
                    )
                )
        if journal.status == JournalStatus.POSTED:
            posted_count += 1
            debit_total += sum((line.debit for line in lines), Decimal(0))
            credit_total += sum((line.credit for line in lines), Decimal(0))
        else:
            pending_count += 1

        if journal.kind == JournalKind.MANUAL and (
            journal.source_uuid != journal.pk or journal.occurrence_id != journal.pk
        ):
            exceptions.append(
                ReconciliationException(
                    code="manual_identity_mismatch",
                    source_uuid=journal.source_uuid,
                    journal_uuid=journal.pk,
                )
            )
        if (
            journal.kind == JournalKind.REVERSAL
            and journal.reverses_id != journal.source_uuid
        ):
            exceptions.append(
                ReconciliationException(
                    code="reversal_source_mismatch",
                    source_uuid=journal.source_uuid,
                    journal_uuid=journal.pk,
                )
            )
        if (
            journal.kind == JournalKind.REPLACEMENT
            and journal.replaces_id != journal.source_uuid
        ):
            exceptions.append(
                ReconciliationException(
                    code="replacement_source_mismatch",
                    source_uuid=journal.source_uuid,
                    journal_uuid=journal.pk,
                )
            )

    opening_imports = list(
        OpeningBalanceImport.objects.filter(
            organization=organization, cutoff_date__lte=cutoff_date
        )
        .select_related("accepted_journal")
        .prefetch_related("lines", "accepted_journal__lines")
        .order_by("cutoff_date", "created_at", "pk")
    )
    for opening_import in opening_imports:
        if opening_import.status != OpeningImportStatus.ACCEPTED:
            pending_count += 1
            continue
        journal = opening_import.accepted_journal
        if (
            journal is None
            or journal.organization_id != organization.pk
            or journal.source_uuid != opening_import.pk
            or journal.status != JournalStatus.POSTED
        ):
            exceptions.append(
                ReconciliationException(
                    code="opening_posting_missing",
                    source_uuid=opening_import.pk,
                    journal_uuid=journal.pk if journal else None,
                )
            )
            continue
        source_by_id = {line.pk: line for line in opening_import.lines.all()}
        for journal_line in journal.lines.all():
            source_line = source_by_id.get(journal_line.source_line_uuid)
            if source_line is None or _opening_line_signature(
                source_line
            ) != _opening_line_signature(journal_line):
                exceptions.append(
                    ReconciliationException(
                        code="opening_line_mismatch",
                        source_uuid=opening_import.pk,
                        journal_uuid=journal.pk,
                        line_uuid=journal_line.pk,
                    )
                )
        if len(source_by_id) != journal.lines.count():
            exceptions.append(
                ReconciliationException(
                    code="opening_line_count_mismatch",
                    source_uuid=opening_import.pk,
                    journal_uuid=journal.pk,
                )
            )

    opening_import_by_journal = {
        item.accepted_journal_id: item
        for item in opening_imports
        if item.accepted_journal_id is not None
    }
    processed_opening_ids: set[UUID] = set()
    tie_outs: list[ReconciliationTieOut] = []
    for journal in journals:
        if journal.kind == JournalKind.MANUAL:
            tie_outs.append(
                _self_source_tie_out(
                    journal=journal, tie_out_type=ReconciliationTieOutType.MANUAL
                )
            )
        elif journal.kind == JournalKind.OPENING:
            opening_import = opening_import_by_journal.get(journal.pk)
            if opening_import is None:
                tie_outs.append(
                    _self_source_tie_out(
                        journal=journal,
                        tie_out_type=ReconciliationTieOutType.OPENING,
                    )
                )
            else:
                tie_outs.append(_opening_import_tie_out(opening_import))
                processed_opening_ids.add(opening_import.pk)
        else:
            tie_outs.append(_correction_tie_out(journal))
    tie_outs.extend(
        _opening_import_tie_out(opening_import)
        for opening_import in opening_imports
        if opening_import.pk not in processed_opening_ids
    )
    exceptions.extend(_tie_out_exceptions(tie_outs))

    if debit_total != credit_total:
        raise ValidationError("جمع اسناد قطعی در دامنه تطبیق متوازن نیست.")
    imported_journal_ids = {
        opening_import.accepted_journal_id
        for opening_import in opening_imports
        if opening_import.accepted_journal_id is not None
    }
    return ReconciliationReport(
        cutoff_date=cutoff_date,
        source_count=(
            len(journals)
            + len(opening_imports)
            - sum(journal.pk in imported_journal_ids for journal in journals)
        ),
        journal_count=len(journals),
        posted_count=posted_count,
        pending_count=pending_count,
        debit_total=debit_total,
        credit_total=credit_total,
        exceptions=tuple(exceptions),
        tie_outs=tuple(tie_outs),
    )


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _reconciliation_input_evidence(
    *, organization: Organization, cutoff_date: date
) -> dict[str, object]:
    journal_fields = (
        "id",
        "period_id",
        "kind",
        "status",
        "number",
        "document_date",
        "accounting_date",
        "currency",
        "source_key",
        "source_kind",
        "source_uuid",
        "source_version",
        "event_kind",
        "occurrence_id",
        "payload_hash",
        "posting_rule_code",
        "posting_rule_version",
        "cutoff_date",
        "reverses_id",
        "replaces_id",
    )
    line_fields = (
        "id",
        "journal_id",
        "line_number",
        "account_id",
        "debit",
        "credit",
        "project_id",
        "site_id",
        "wbs_node_id",
        "party_id",
        "source_line_uuid",
        "account_snapshot",
        "dimension_snapshot",
    )
    journals = list(
        _bounded_journals(organization=organization, cutoff_date=cutoff_date)
        .order_by("accounting_date", "created_at", "pk")
        .values(*journal_fields)
    )
    journal_ids = [journal["id"] for journal in journals]
    journal_lines = list(
        JournalLine.objects.filter(
            organization=organization, journal_id__in=journal_ids
        )
        .order_by("journal_id", "line_number", "pk")
        .values(*line_fields)
    )
    opening_imports = list(
        OpeningBalanceImport.objects.filter(
            organization=organization, cutoff_date__lte=cutoff_date
        )
        .order_by("cutoff_date", "created_at", "pk")
        .values(
            "id",
            "fiscal_year_id",
            "period_id",
            "source_reference",
            "cutoff_date",
            "evidence_reference",
            "reconciliation_reference",
            "status",
            "accepted_journal_id",
        )
    )
    opening_ids = [item["id"] for item in opening_imports]
    opening_lines = list(
        OpeningBalanceImportLine.objects.filter(
            organization=organization, opening_import_id__in=opening_ids
        )
        .order_by("opening_import_id", "line_number", "pk")
        .values(
            "id",
            "opening_import_id",
            "line_number",
            "account_id",
            "debit",
            "credit",
            "project_id",
            "site_id",
            "wbs_node_id",
            "party_id",
        )
    )
    return {
        "journals": journals,
        "journal_lines": journal_lines,
        "opening_imports": opening_imports,
        "opening_import_lines": opening_lines,
    }


@transaction.atomic
def create_manual_opening_reconciliation_run(
    *, organization: Organization, actor: User, cutoff_date: date
) -> ReconciliationRun:
    """Retain an immutable, idempotent snapshot; this is not review/sign-off."""

    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_RECONCILIATIONS_RUN,
        message="اختیار اجرای تطبیق حسابداری را ندارید.",
    )
    report = inspect_manual_opening_reconciliation(
        organization=organization,
        actor=actor,
        cutoff_date=cutoff_date,
    )
    scope_payload = {
        "scope": ReconciliationScope.MANUAL_OPENING_CORRECTION,
        "scope_version": RECONCILIATION_SCOPE_VERSION,
        "cutoff_date": cutoff_date.isoformat(),
    }
    scope_hash = _canonical_hash(scope_payload)
    input_hash = _canonical_hash(
        {
            **scope_payload,
            "evidence": _reconciliation_input_evidence(
                organization=organization, cutoff_date=cutoff_date
            ),
        }
    )
    exception_payload = [
        {
            "code": item.code,
            "source_uuid": str(item.source_uuid),
            "journal_uuid": str(item.journal_uuid) if item.journal_uuid else None,
            "line_uuid": str(item.line_uuid) if item.line_uuid else None,
        }
        for item in report.exceptions
    ]
    tie_out_payload = []
    for item in report.tie_outs:
        evidence_hash = _canonical_hash(item.evidence)
        tie_out_payload.append(
            {
                "tie_out_type": item.tie_out_type,
                "source_uuid": str(item.source_uuid),
                "source_version": item.source_version,
                "journal_uuid": str(item.journal_uuid) if item.journal_uuid else None,
                "source_line_count": item.source_line_count,
                "journal_line_count": item.journal_line_count,
                "source_debit_total": str(item.source_debit_total),
                "source_credit_total": str(item.source_credit_total),
                "journal_debit_total": str(item.journal_debit_total),
                "journal_credit_total": str(item.journal_credit_total),
                "count_matches": item.count_matches,
                "amount_matches": item.amount_matches,
                "source_version_matches": item.source_version_matches,
                "exact_line_matches": item.exact_line_matches,
                "dimension_matches": item.dimension_matches,
                "correction_chain_matches": item.correction_chain_matches,
                "evidence": item.evidence,
                "evidence_hash": evidence_hash,
            }
        )
    result_hash = _canonical_hash(
        {
            "source_count": report.source_count,
            "journal_count": report.journal_count,
            "posted_count": report.posted_count,
            "pending_count": report.pending_count,
            "debit_total": str(report.debit_total),
            "credit_total": str(report.credit_total),
            "exceptions": exception_payload,
            "tie_outs": tie_out_payload,
        }
    )
    existing = ReconciliationRun.objects.filter(
        organization=organization,
        scope_hash=scope_hash,
        input_hash=input_hash,
    ).first()
    if existing is not None:
        return existing

    run = ReconciliationRun(
        organization=organization,
        scope=ReconciliationScope.MANUAL_OPENING_CORRECTION,
        scope_version=RECONCILIATION_SCOPE_VERSION,
        cutoff_date=cutoff_date,
        scope_hash=scope_hash,
        input_hash=input_hash,
        result_hash=result_hash,
        source_count=report.source_count,
        journal_count=report.journal_count,
        posted_count=report.posted_count,
        pending_count=report.pending_count,
        debit_total=report.debit_total,
        credit_total=report.credit_total,
        exception_count=len(report.exceptions),
        created_by=membership,
    )
    run.save()
    ReconciliationExceptionSnapshot.objects.bulk_create(
        [
            ReconciliationExceptionSnapshot(
                organization=organization,
                run=run,
                sequence=sequence,
                **payload,
            )
            for sequence, payload in enumerate(exception_payload, start=1)
        ]
    )
    ReconciliationTieOutSnapshot.objects.bulk_create(
        [
            ReconciliationTieOutSnapshot(
                organization=organization,
                run=run,
                sequence=sequence,
                **payload,
            )
            for sequence, payload in enumerate(tie_out_payload, start=1)
        ]
    )
    record_audit_event(
        action=AuditAction.ACCOUNTING_RECONCILIATION_RUN_CREATED,
        entity_type="accounting.ReconciliationRun",
        entity_id=str(run.pk),
        organization=organization,
        actor=actor,
        metadata={
            "scope": run.scope,
            "scope_version": run.scope_version,
            "cutoff_date": run.cutoff_date.isoformat(),
            "scope_hash": run.scope_hash,
            "input_hash": run.input_hash,
            "result_hash": run.result_hash,
            "exception_count": run.exception_count,
            "tie_out_count": len(tie_out_payload),
        },
    )
    return run


@transaction.atomic
def dispose_reconciliation_exception(
    *,
    organization: Organization,
    actor: User,
    exception: ReconciliationExceptionSnapshot,
    disposition: str,
    reason: str,
    evidence_reference: str = "",
) -> ReconciliationExceptionDisposition:
    """Append one controlled disposition without changing retained evidence."""

    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_RECONCILIATIONS_DISPOSE,
        message="اختیار تعیین تکلیف استثنای تطبیق حسابداری را ندارید.",
    )
    if disposition not in ReconciliationExceptionDispositionCode.values:
        raise ValidationError("نوع تعیین تکلیف استثنای تطبیق معتبر نیست.")
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValidationError("دلیل تعیین تکلیف استثنای تطبیق الزامی است.")
    normalized_evidence = evidence_reference.strip()

    locked_exception = (
        ReconciliationExceptionSnapshot.objects.select_for_update()
        .select_related("run")
        .get(pk=exception.pk)
    )
    if (
        locked_exception.organization_id != organization.pk
        or locked_exception.run.organization_id != organization.pk
    ):
        raise PermissionDenied("استثنای تطبیق متعلق به Tenant دیگری است.")

    existing = ReconciliationExceptionDisposition.objects.filter(
        exception=locked_exception
    ).first()
    if existing is not None:
        same_request = (
            existing.disposition == disposition
            and existing.reason == normalized_reason
            and existing.evidence_reference == normalized_evidence
            and existing.disposed_by_id == membership.pk
        )
        if same_request:
            return existing
        raise ValidationError("استثنای تطبیق قبلاً تعیین تکلیف شده است.")

    result = ReconciliationExceptionDisposition(
        organization=organization,
        exception=locked_exception,
        disposition=disposition,
        reason=normalized_reason,
        evidence_reference=normalized_evidence,
        disposed_by=membership,
    )
    result.save()
    record_audit_event(
        action=AuditAction.ACCOUNTING_RECONCILIATION_EXCEPTION_DISPOSED,
        entity_type="accounting.ReconciliationExceptionDisposition",
        entity_id=str(result.pk),
        organization=organization,
        actor=actor,
        metadata={
            "run_uuid": str(locked_exception.run_id),
            "exception_uuid": str(locked_exception.pk),
            "exception_code": locked_exception.code,
            "disposition": result.disposition,
            "reason": result.reason,
            "evidence_reference": result.evidence_reference,
        },
    )
    return result


def _retained_reconciliation_evidence(
    *, organization: Organization, run: ReconciliationRun
) -> dict[str, str]:
    """Verify immutable run/snapshot/audit evidence and return signed hashes."""

    if run.organization_id != organization.pk:
        raise PermissionDenied("اجرای تطبیق متعلق به Tenant دیگری است.")
    if (
        run.scope != ReconciliationScope.MANUAL_OPENING_CORRECTION
        or run.scope_version != RECONCILIATION_SCOPE_VERSION
    ):
        raise ValidationError("دامنه یا نسخه اجرای تطبیق قابل تأیید نیست.")

    scope_hash = _canonical_hash(
        {
            "scope": run.scope,
            "scope_version": run.scope_version,
            "cutoff_date": run.cutoff_date.isoformat(),
        }
    )
    if scope_hash != run.scope_hash:
        raise ValidationError("شواهد دامنه اجرای تطبیق دستکاری شده است.")

    exceptions = list(run.exceptions.order_by("sequence", "pk"))
    if [item.sequence for item in exceptions] != list(
        range(1, len(exceptions) + 1)
    ) or len(exceptions) != run.exception_count:
        raise ValidationError("شواهد استثناهای اجرای تطبیق کامل و پیوسته نیست.")
    exception_payload = [
        {
            "code": item.code,
            "source_uuid": str(item.source_uuid),
            "journal_uuid": str(item.journal_uuid) if item.journal_uuid else None,
            "line_uuid": str(item.line_uuid) if item.line_uuid else None,
        }
        for item in exceptions
    ]

    tie_outs = list(run.tie_outs.order_by("sequence", "pk"))
    if [item.sequence for item in tie_outs] != list(range(1, len(tie_outs) + 1)):
        raise ValidationError("شواهد تفصیلی اجرای تطبیق کامل و پیوسته نیست.")
    tie_out_payload: list[dict[str, object]] = []
    for item in tie_outs:
        evidence_hash = _canonical_hash(item.evidence)
        if evidence_hash != item.evidence_hash:
            raise ValidationError("شواهد تفصیلی اجرای تطبیق دستکاری شده است.")
        tie_out_payload.append(
            {
                "tie_out_type": item.tie_out_type,
                "source_uuid": str(item.source_uuid),
                "source_version": item.source_version,
                "journal_uuid": str(item.journal_uuid) if item.journal_uuid else None,
                "source_line_count": item.source_line_count,
                "journal_line_count": item.journal_line_count,
                "source_debit_total": str(item.source_debit_total),
                "source_credit_total": str(item.source_credit_total),
                "journal_debit_total": str(item.journal_debit_total),
                "journal_credit_total": str(item.journal_credit_total),
                "count_matches": item.count_matches,
                "amount_matches": item.amount_matches,
                "source_version_matches": item.source_version_matches,
                "exact_line_matches": item.exact_line_matches,
                "dimension_matches": item.dimension_matches,
                "correction_chain_matches": item.correction_chain_matches,
                "evidence": item.evidence,
                "evidence_hash": item.evidence_hash,
            }
        )
    result_hash = _canonical_hash(
        {
            "source_count": run.source_count,
            "journal_count": run.journal_count,
            "posted_count": run.posted_count,
            "pending_count": run.pending_count,
            "debit_total": str(run.debit_total),
            "credit_total": str(run.credit_total),
            "exceptions": exception_payload,
            "tie_outs": tie_out_payload,
        }
    )
    if result_hash != run.result_hash:
        raise ValidationError("نتیجه نگهداری‌شده اجرای تطبیق دستکاری شده است.")

    creation_events = list(
        AuditEvent.objects.filter(
            organization=organization,
            action=AuditAction.ACCOUNTING_RECONCILIATION_RUN_CREATED,
            entity_type="accounting.ReconciliationRun",
            entity_id=str(run.pk),
        )
    )
    if len(creation_events) != 1:
        raise ValidationError("شواهد ممیزی ایجاد اجرای تطبیق کامل نیست.")
    event = creation_events[0]
    if event.actor_id != run.created_by.user_id or any(
        event.metadata.get(key) != value
        for key, value in {
            "scope": run.scope,
            "scope_version": run.scope_version,
            "cutoff_date": run.cutoff_date.isoformat(),
            "scope_hash": run.scope_hash,
            "input_hash": run.input_hash,
            "result_hash": run.result_hash,
            "exception_count": run.exception_count,
            "tie_out_count": len(tie_outs),
        }.items()
    ):
        raise ValidationError(
            "شواهد ممیزی اجرای تطبیق با رکورد نگهداری‌شده سازگار نیست."
        )

    disposition_payload: list[dict[str, object]] = []
    for item in exceptions:
        try:
            disposition = item.disposition
        except ReconciliationExceptionDisposition.DoesNotExist as exc:
            raise ValidationError(
                "همه استثناهای اجرای تطبیق باید پیش از تأیید تعیین تکلیف شوند."
            ) from exc
        if disposition.organization_id != organization.pk:
            raise ValidationError("تعیین تکلیف استثنا با Tenant اجرا سازگار نیست.")
        disposition_events = list(
            AuditEvent.objects.filter(
                organization=organization,
                action=AuditAction.ACCOUNTING_RECONCILIATION_EXCEPTION_DISPOSED,
                entity_type="accounting.ReconciliationExceptionDisposition",
                entity_id=str(disposition.pk),
            )
        )
        if len(disposition_events) != 1:
            raise ValidationError("شواهد ممیزی تعیین تکلیف استثنا کامل نیست.")
        disposition_event = disposition_events[0]
        if disposition_event.actor_id != disposition.disposed_by.user_id or any(
            disposition_event.metadata.get(key) != value
            for key, value in {
                "run_uuid": str(run.pk),
                "exception_uuid": str(item.pk),
                "exception_code": item.code,
                "disposition": disposition.disposition,
                "reason": disposition.reason,
                "evidence_reference": disposition.evidence_reference,
            }.items()
        ):
            raise ValidationError(
                "شواهد ممیزی تعیین تکلیف با رکورد نگهداری‌شده سازگار نیست."
            )
        disposition_payload.append(
            {
                "exception_uuid": str(item.pk),
                "disposition_uuid": str(disposition.pk),
                "disposition": disposition.disposition,
                "reason": disposition.reason,
                "evidence_reference": disposition.evidence_reference,
                "disposed_by": str(disposition.disposed_by_id),
            }
        )
    return {
        "scope_hash": scope_hash,
        "input_hash": run.input_hash,
        "result_hash": result_hash,
        "disposition_hash": _canonical_hash(disposition_payload),
    }


def verify_signed_reconciliation_run(
    *, organization: Organization, run: ReconciliationRun
) -> ReconciliationReview:
    """Verify retained/sign-off evidence and prove it still covers the cutoff."""

    evidence = _retained_reconciliation_evidence(
        organization=organization, run=run
    )
    scope_payload = {
        "scope": run.scope,
        "scope_version": run.scope_version,
        "cutoff_date": run.cutoff_date.isoformat(),
    }
    current_input_hash = _canonical_hash(
        {
            **scope_payload,
            "evidence": _reconciliation_input_evidence(
                organization=organization, cutoff_date=run.cutoff_date
            ),
        }
    )
    if current_input_hash != run.input_hash:
        raise ValidationError(
            "تطبیق امضاشده آخرین وضعیت قطعی در تاریخ برش را پوشش نمی‌دهد."
        )
    try:
        review = run.review
    except ReconciliationReview.DoesNotExist as exc:
        raise ValidationError("اجرای تطبیق فاقد تأیید مستقل است.") from exc
    signed_evidence_hash = _canonical_hash({"run_uuid": str(run.pk), **evidence})
    if any(
        (
            review.scope_hash != evidence["scope_hash"],
            review.input_hash != evidence["input_hash"],
            review.result_hash != evidence["result_hash"],
            review.disposition_hash != evidence["disposition_hash"],
            review.signed_evidence_hash != signed_evidence_hash,
        )
    ):
        raise ValidationError("تأیید تطبیق با شواهد نگهداری‌شده سازگار نیست.")
    sign_off_events = list(
        AuditEvent.objects.filter(
            organization=organization,
            action=AuditAction.ACCOUNTING_RECONCILIATION_SIGNED_OFF,
            entity_type="accounting.ReconciliationReview",
            entity_id=str(review.pk),
        )
    )
    if len(sign_off_events) != 1:
        raise ValidationError("شواهد ممیزی تأیید تطبیق کامل نیست.")
    event = sign_off_events[0]
    if event.actor_id != review.reviewed_by.user_id or any(
        event.metadata.get(key) != value
        for key, value in {
            "run_uuid": str(run.pk),
            "reason": review.reason,
            "scope_hash": review.scope_hash,
            "input_hash": review.input_hash,
            "result_hash": review.result_hash,
            "disposition_hash": review.disposition_hash,
            "signed_evidence_hash": review.signed_evidence_hash,
        }.items()
    ):
        raise ValidationError("ممیزی تأیید تطبیق با شواهد امضاشده سازگار نیست.")
    return review


@transaction.atomic
def sign_off_reconciliation_run(
    *,
    organization: Organization,
    actor: User,
    run: ReconciliationRun,
    reason: str,
) -> ReconciliationReview:
    """Independently sign immutable retained evidence without changing finances."""

    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    reviewer = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_RECONCILIATIONS_SIGN_OFF,
        message="اختیار بررسی و تأیید مستقل تطبیق حسابداری را ندارید.",
    )
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValidationError("دلیل تأیید تطبیق الزامی است.")

    locked_run = (
        ReconciliationRun.objects.select_for_update()
        .select_related("created_by__user")
        .get(pk=run.pk)
    )
    if locked_run.organization_id != organization.pk:
        raise PermissionDenied("اجرای تطبیق متعلق به Tenant دیگری است.")
    if reviewer.pk == locked_run.created_by_id:
        raise PermissionDenied("ایجادکننده اجرا نمی‌تواند همان تطبیق را تأیید کند.")

    evidence = _retained_reconciliation_evidence(
        organization=organization, run=locked_run
    )
    disposer_ids = set(
        ReconciliationExceptionDisposition.objects.filter(
            exception__run=locked_run
        ).values_list("disposed_by_id", flat=True)
    )
    if reviewer.pk in disposer_ids:
        raise PermissionDenied(
            "تعیین‌کننده تکلیف استثنا نمی‌تواند همان اجرای تطبیق را تأیید کند."
        )
    signed_evidence_hash = _canonical_hash({"run_uuid": str(locked_run.pk), **evidence})

    existing = ReconciliationReview.objects.filter(run=locked_run).first()
    if existing is not None:
        same_request = (
            existing.organization_id == organization.pk
            and existing.reviewed_by_id == reviewer.pk
            and existing.reason == normalized_reason
            and existing.scope_hash == evidence["scope_hash"]
            and existing.input_hash == evidence["input_hash"]
            and existing.result_hash == evidence["result_hash"]
            and existing.disposition_hash == evidence["disposition_hash"]
            and existing.signed_evidence_hash == signed_evidence_hash
        )
        if same_request:
            return existing
        raise ValidationError("اجرای تطبیق قبلاً تأیید شده است.")

    review = ReconciliationReview(
        organization=organization,
        run=locked_run,
        reviewed_by=reviewer,
        reason=normalized_reason,
        signed_evidence_hash=signed_evidence_hash,
        **evidence,
    )
    review.save()
    record_audit_event(
        action=AuditAction.ACCOUNTING_RECONCILIATION_SIGNED_OFF,
        entity_type="accounting.ReconciliationReview",
        entity_id=str(review.pk),
        organization=organization,
        actor=actor,
        metadata={
            "run_uuid": str(locked_run.pk),
            "reason": review.reason,
            "scope_hash": review.scope_hash,
            "input_hash": review.input_hash,
            "result_hash": review.result_hash,
            "disposition_hash": review.disposition_hash,
            "signed_evidence_hash": review.signed_evidence_hash,
        },
    )
    return review
