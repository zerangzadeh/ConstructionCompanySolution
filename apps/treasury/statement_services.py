from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from itertools import islice
from pathlib import PurePath

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode, OrganizationMembership
from apps.treasury.models import (
    BankReconciliationRun,
    BankReconciliationRunProvenance,
    BankStatementImport,
    BankStatementLine,
    StatementImportStatus,
    StatementMatchProposal,
    StatementMatchStatus,
    TreasuryAccount,
    TreasuryAccountKind,
    TreasuryAccountStatus,
    TreasuryLegDirection,
    TreasuryMovement,
    TreasuryMovementClearing,
    TreasuryMovementClearingReversal,
    TreasuryMovementLeg,
    TreasuryMovementStatus,
)
from apps.treasury.services import (
    _active_membership,
    _approval_policy,
    _lock_organization,
    _payload_hash,
    _reason,
)

EXACT_MATCH_BASIS = "account_direction_amount_date_exact"
_SENSITIVE_RAW_KEYS = {
    "account",
    "account_number",
    "card",
    "card_number",
    "credential",
    "iban",
    "password",
    "secret",
    "token",
}


@dataclass(frozen=True, slots=True)
class StatementRowInput:
    row_number: int
    transaction_date: date
    direction: str
    amount: Decimal
    provider_row_id: str = ""
    value_date: date | None = None
    reference: str = ""
    description: str = ""
    raw_evidence: dict[str, object] | None = None
    currency: str = "IRR"


def _canonical_text(value: str, *, field: str, required: bool = False) -> str:
    result = value.strip()
    if required and not result:
        raise ValidationError({field: "این مقدار الزامی است."})
    return result


def _validate_raw_evidence(value: object) -> dict[str, object]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationError("شواهد خام هر ردیف باید یک شیء JSON باشد.")

    def inspect(item: object) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                if str(key).strip().lower() in _SENSITIVE_RAW_KEYS:
                    raise ValidationError("شواهد خام شامل کلید حساس غیرمجاز است.")
                inspect(nested)
        elif isinstance(item, list):
            for nested in item:
                inspect(nested)
        elif not isinstance(item, (str, int, bool, type(None))):
            raise ValidationError("شواهد خام باید JSON قطعی و غیرحساس باشد.")

    inspect(value)
    return value


def _row_payload(row: StatementRowInput) -> dict[str, object]:
    raw_evidence = _validate_raw_evidence(row.raw_evidence)
    if not isinstance(row.row_number, int) or row.row_number <= 0:
        raise ValidationError("شماره ردیف باید عدد صحیح مثبت باشد.")
    if row.direction not in TreasuryLegDirection.values:
        raise ValidationError("جهت ردیف صورتحساب نامعتبر است.")
    if not isinstance(row.amount, Decimal) or not row.amount.is_finite():
        raise ValidationError("مبلغ ردیف باید Decimal متناهی باشد.")
    if row.amount <= 0:
        raise ValidationError("مبلغ ردیف باید مثبت باشد.")
    if row.currency != "IRR":
        raise ValidationError("در این مرحله فقط واحد پول IRR مجاز است.")
    return {
        "row_number": row.row_number,
        "provider_row_id": row.provider_row_id.strip(),
        "transaction_date": row.transaction_date.isoformat(),
        "value_date": row.value_date.isoformat() if row.value_date else None,
        "direction": row.direction,
        "amount": f"{row.amount:.6f}",
        "currency": row.currency,
        "reference": row.reference.strip(),
        "description": row.description.strip(),
        "raw_evidence": raw_evidence,
    }


def _lock_memberships(
    *, organization, memberships: Iterable[OrganizationMembership]
) -> dict[object, OrganizationMembership]:
    locked: dict[object, OrganizationMembership] = {}
    unique = {membership.pk: membership for membership in memberships}
    for membership_id in sorted(unique, key=str):
        item = _active_membership(
            organization=organization, membership=unique[membership_id]
        )
        locked[item.pk] = item
    return locked


@transaction.atomic
def preview_statement_import(
    *,
    organization,
    actor,
    account: TreasuryAccount,
    provider_code: str,
    format_code: str,
    period_start: date,
    period_end: date,
    file_name: str,
    source_bytes: bytes,
    rows: Iterable[StatementRowInput],
    max_file_bytes: int,
    max_rows: int,
    idempotency_key: str,
) -> BankStatementImport:
    organization = _lock_organization(organization)
    maker = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_STATEMENTS_IMPORT,
        message="اختیار ورود صورتحساب بانکی را ندارید.",
    )
    maker = _active_membership(organization=organization, membership=maker)
    account = TreasuryAccount.objects.select_for_update().get(pk=account.pk)
    if account.organization_id != organization.pk:
        raise PermissionDenied("حساب بانکی متعلق به این Tenant نیست.")
    if (
        account.kind != TreasuryAccountKind.BANK
        or account.status != TreasuryAccountStatus.ACTIVE
    ):
        raise ValidationError("ورود صورتحساب فقط برای حساب بانکی فعال مجاز است.")
    if not isinstance(max_file_bytes, int) or max_file_bytes <= 0:
        raise ValidationError("حد مثبت حجم فایل برای اجرای همگام الزامی است.")
    if not isinstance(max_rows, int) or max_rows <= 0:
        raise ValidationError("حد مثبت تعداد ردیف برای اجرای همگام الزامی است.")
    if not isinstance(source_bytes, bytes) or not source_bytes:
        raise ValidationError("بایت‌های دقیق منبع صورتحساب الزامی است.")
    if len(source_bytes) > max_file_bytes:
        raise ValidationError("حجم منبع از حد صریح این اجرا بیشتر است.")
    if period_end < period_start:
        raise ValidationError("بازه صورتحساب نامعتبر است.")
    provider_code = _canonical_text(provider_code, field="provider_code", required=True)
    format_code = _canonical_text(format_code, field="format_code", required=True)
    idempotency_key = _canonical_text(
        idempotency_key, field="idempotency_key", required=True
    )
    file_name = PurePath(file_name.strip()).name
    if not file_name or len(file_name) > 255:
        raise ValidationError("نام فایل معتبر و بدون مسیر الزامی است.")
    materialized = list(islice(iter(rows), max_rows + 1))
    if not materialized:
        raise ValidationError("صورتحساب باید دست‌کم یک ردیف داشته باشد.")
    if len(materialized) > max_rows:
        raise ValidationError("تعداد ردیف‌ها از حد صریح این اجرا بیشتر است.")
    row_payloads = [_row_payload(row) for row in materialized]
    numbers = [payload["row_number"] for payload in row_payloads]
    if len(set(numbers)) != len(numbers):
        raise ValidationError("شماره ردیف صورتحساب تکراری است.")
    for payload in row_payloads:
        row_date = date.fromisoformat(str(payload["transaction_date"]))
        if not period_start <= row_date <= period_end:
            raise ValidationError("تاریخ ردیف خارج از بازه صورتحساب است.")
    file_hash = hashlib.sha256(source_bytes).hexdigest()
    evidence_hashes = [
        _payload_hash(
            {key: value for key, value in payload.items() if key != "row_number"}
        )
        for payload in row_payloads
    ]
    if len(set(evidence_hashes)) != len(evidence_hashes):
        raise ValidationError("محتوای دقیق ردیف صورتحساب در فایل تکراری است.")
    payload = {
        "account": str(account.pk),
        "provider_code": provider_code,
        "format_code": format_code,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "file_name": file_name,
        "file_hash": file_hash,
        "file_size": len(source_bytes),
        "max_file_bytes": max_file_bytes,
        "max_rows": max_rows,
        "row_hashes": evidence_hashes,
    }
    payload_hash = _payload_hash(payload)
    existing = BankStatementImport.objects.filter(
        organization=organization, idempotency_key=idempotency_key
    ).first()
    if existing:
        if existing.payload_hash != payload_hash:
            raise ValidationError("کلید تکرارپذیری با محتوای دیگری استفاده شده است.")
        return existing
    if BankStatementImport.objects.filter(
        organization=organization, account=account, file_hash=file_hash
    ).exists():
        raise ValidationError("این فایل قبلاً برای حساب وارد شده است.")
    if BankStatementLine.objects.filter(
        organization=organization,
        account=account,
        evidence_hash__in=evidence_hashes,
    ).exists():
        raise ValidationError("حداقل یک ردیف دقیق قبلاً وارد شده است.")
    provider_ids = [
        str(payload["provider_row_id"])
        for payload in row_payloads
        if payload["provider_row_id"]
    ]
    if len(set(provider_ids)) != len(provider_ids):
        raise ValidationError("شناسه ردیف ارائه‌دهنده در فایل تکراری است.")
    if (
        provider_ids
        and BankStatementLine.objects.filter(
            organization=organization,
            account=account,
            provider_code=provider_code,
            provider_row_id__in=provider_ids,
        ).exists()
    ):
        raise ValidationError("شناسه ردیف ارائه‌دهنده قبلاً وارد شده است.")
    try:
        statement_import = BankStatementImport.objects.create(
            organization=organization,
            account=account,
            provider_code=provider_code,
            format_code=format_code,
            period_start=period_start,
            period_end=period_end,
            file_name=file_name,
            file_hash=file_hash,
            file_size=len(source_bytes),
            max_file_bytes=max_file_bytes,
            max_rows=max_rows,
            row_count=len(row_payloads),
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            created_by=maker,
        )
        BankStatementLine.objects.bulk_create(
            [
                BankStatementLine(
                    organization=organization,
                    statement_import=statement_import,
                    account=account,
                    provider_code=provider_code,
                    evidence_hash=evidence_hash,
                    **row_payload,
                )
                for row_payload, evidence_hash in zip(
                    row_payloads, evidence_hashes, strict=True
                )
            ]
        )
    except IntegrityError as exc:
        raise ValidationError("فایل یا ردیف صورتحساب به‌طور همزمان تکراری شد.") from exc
    record_audit_event(
        action=AuditAction.TREASURY_STATEMENT_IMPORT_PREVIEWED,
        entity_type="treasury.BankStatementImport",
        entity_id=statement_import.pk,
        organization=organization,
        actor=actor,
        metadata={
            "account": str(account.pk),
            "file_hash": file_hash,
            "row_count": len(row_payloads),
            "payload_hash": payload_hash,
        },
    )
    return statement_import


@transaction.atomic
def accept_statement_import(
    *, organization, actor, statement_import: BankStatementImport, reason: str
) -> BankStatementImport:
    organization = _lock_organization(organization)
    checker = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_STATEMENTS_ACCEPT,
        message="اختیار پذیرش صورتحساب بانکی را ندارید.",
    )
    locked_members = _lock_memberships(
        organization=organization,
        memberships=(statement_import.created_by, checker),
    )
    checker = locked_members[checker.pk]
    statement_import = (
        BankStatementImport.objects.select_for_update()
        .select_related("created_by", "account")
        .get(pk=statement_import.pk)
    )
    if statement_import.organization_id != organization.pk:
        raise PermissionDenied("صورتحساب متعلق به این Tenant نیست.")
    reason = _reason(reason)
    acceptance_hash = _payload_hash(
        {
            "import": str(statement_import.pk),
            "payload_hash": statement_import.payload_hash,
            "checker": str(checker.pk),
            "reason": reason,
        }
    )
    if statement_import.status == StatementImportStatus.ACCEPTED:
        if statement_import.acceptance_hash == acceptance_hash:
            return statement_import
        raise ValidationError("صورتحساب قبلاً با تصمیم دیگری پذیرفته شده است.")
    if statement_import.status != StatementImportStatus.PREVIEWED:
        raise ValidationError("فقط پیش‌نمایش صورتحساب قابل پذیرش است.")
    lines = list(statement_import.lines.order_by("row_number"))
    if len(lines) != statement_import.row_count:
        raise ValidationError("تعداد ردیف‌های نگهداری‌شده با پیش‌نمایش سازگار نیست.")
    retained_hashes = []
    for line in lines:
        retained_payload = {
            "provider_row_id": line.provider_row_id,
            "transaction_date": line.transaction_date.isoformat(),
            "value_date": line.value_date.isoformat() if line.value_date else None,
            "direction": line.direction,
            "amount": f"{line.amount:.6f}",
            "currency": line.currency,
            "reference": line.reference,
            "description": line.description,
            "raw_evidence": line.raw_evidence,
        }
        retained_hash = _payload_hash(retained_payload)
        if retained_hash != line.evidence_hash:
            raise ValidationError("شواهد نگهداری‌شده ردیف صورتحساب تغییر کرده است.")
        retained_hashes.append(retained_hash)
    retained_import_payload = {
        "account": str(statement_import.account_id),
        "provider_code": statement_import.provider_code,
        "format_code": statement_import.format_code,
        "period_start": statement_import.period_start.isoformat(),
        "period_end": statement_import.period_end.isoformat(),
        "file_name": statement_import.file_name,
        "file_hash": statement_import.file_hash,
        "file_size": statement_import.file_size,
        "max_file_bytes": statement_import.max_file_bytes,
        "max_rows": statement_import.max_rows,
        "row_hashes": retained_hashes,
    }
    if _payload_hash(retained_import_payload) != statement_import.payload_hash:
        raise ValidationError("شواهد نگهداری‌شده پیش‌نمایش تغییر کرده است.")
    policy = _approval_policy(
        organization=organization,
        maker=locked_members[statement_import.created_by_id],
        approver=checker,
    )
    now = timezone.now()
    BankStatementImport.objects.filter(pk=statement_import.pk).update(
        status=StatementImportStatus.ACCEPTED,
        accepted_by=checker,
        accepted_at=now,
        approval_policy_version=policy,
        acceptance_hash=acceptance_hash,
        updated_at=now,
    )
    statement_import.refresh_from_db()
    record_audit_event(
        action=AuditAction.TREASURY_STATEMENT_IMPORT_DECIDED,
        entity_type="treasury.BankStatementImport",
        entity_id=statement_import.pk,
        organization=organization,
        actor=actor,
        metadata={"to": "accepted", "acceptance_hash": acceptance_hash},
    )
    return statement_import


@transaction.atomic
def cancel_statement_import(
    *, organization, actor, statement_import: BankStatementImport, reason: str
) -> BankStatementImport:
    organization = _lock_organization(organization)
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_STATEMENTS_IMPORT,
        message="اختیار لغو پیش‌نمایش صورتحساب را ندارید.",
    )
    statement_import = BankStatementImport.objects.select_for_update().get(
        pk=statement_import.pk
    )
    if statement_import.organization_id != organization.pk:
        raise PermissionDenied("صورتحساب متعلق به این Tenant نیست.")
    if statement_import.status != StatementImportStatus.PREVIEWED:
        raise ValidationError("فقط پیش‌نمایش صورتحساب قابل لغو است.")
    reason = _reason(reason)
    BankStatementImport.objects.filter(pk=statement_import.pk).update(
        status=StatementImportStatus.CANCELLED, updated_at=timezone.now()
    )
    statement_import.refresh_from_db()
    record_audit_event(
        action=AuditAction.TREASURY_STATEMENT_IMPORT_DECIDED,
        entity_type="treasury.BankStatementImport",
        entity_id=statement_import.pk,
        organization=organization,
        actor=actor,
        metadata={"to": "cancelled", "reason": reason},
    )
    return statement_import


def _exact_candidates(line: BankStatementLine):
    return (
        TreasuryMovementLeg.objects.filter(
            organization=line.organization,
            account=line.account,
            direction=line.direction,
            amount=line.amount,
            movement__status=TreasuryMovementStatus.POSTED,
            movement__movement_date=line.transaction_date,
            movement__reversal_movement__isnull=True,
        )
        .exclude(movement__bank_clearings__active=True)
        .select_related("movement")
        .order_by("movement_id", "line_number")
    )


@transaction.atomic
def generate_statement_match_suggestions(
    *,
    organization,
    actor,
    statement_line: BankStatementLine,
    idempotency_key: str,
) -> tuple[StatementMatchProposal, ...]:
    organization = _lock_organization(organization)
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_STATEMENT_MATCHES_MANAGE,
        message="اختیار پیشنهاد تطبیق بانکی را ندارید.",
    )
    statement_line = (
        BankStatementLine.objects.select_for_update()
        .select_related("statement_import", "account")
        .get(pk=statement_line.pk)
    )
    if statement_line.organization_id != organization.pk:
        raise PermissionDenied("ردیف صورتحساب متعلق به این Tenant نیست.")
    if statement_line.statement_import.status != StatementImportStatus.ACCEPTED:
        raise ValidationError("فقط ردیف صورتحساب پذیرفته‌شده قابل تطبیق است.")
    idempotency_key = _canonical_text(
        idempotency_key, field="idempotency_key", required=True
    )
    candidates = list(_exact_candidates(statement_line))
    proposals: list[StatementMatchProposal] = []
    deterministic = len(candidates) == 1
    for leg in candidates:
        require_business_permission(
            user=actor,
            organization=organization,
            permission=BusinessPermissionCode.TREASURY_STATEMENT_MATCHES_MANAGE,
            project=leg.movement.project,
            site=leg.movement.site,
            message="دامنه دسترسی حرکت خزانه‌داری کافی نیست.",
        )
        evidence_hash = _payload_hash(
            {
                "line": str(statement_line.pk),
                "line_hash": statement_line.evidence_hash,
                "movement": str(leg.movement_id),
                "movement_version": leg.movement.version,
                "leg": str(leg.pk),
                "basis": EXACT_MATCH_BASIS,
                "deterministic": deterministic,
                "generation_key": idempotency_key,
            }
        )
        proposal, created = StatementMatchProposal.objects.get_or_create(
            statement_line=statement_line,
            movement=leg.movement,
            generation_key=idempotency_key,
            defaults={
                "organization": organization,
                "movement_leg": leg,
                "deterministic": deterministic,
                "basis": EXACT_MATCH_BASIS,
                "evidence_hash": evidence_hash,
                "proposed_by": membership,
            },
        )
        if not created and proposal.evidence_hash != evidence_hash:
            raise ValidationError(
                "کلید تکرارپذیری پیشنهاد با شواهد دیگری استفاده شده است."
            )
        proposals.append(proposal)
    if proposals:
        record_audit_event(
            action=AuditAction.TREASURY_STATEMENT_MATCH_PROPOSED,
            entity_type="treasury.BankStatementLine",
            entity_id=statement_line.pk,
            organization=organization,
            actor=actor,
            metadata={
                "candidate_count": len(proposals),
                "deterministic": deterministic,
                "basis": EXACT_MATCH_BASIS,
            },
        )
    return tuple(proposals)


def _assert_exact_match(proposal: StatementMatchProposal) -> None:
    line = proposal.statement_line
    movement = proposal.movement
    leg = proposal.movement_leg
    if (
        line.account_id != leg.account_id
        or line.direction != leg.direction
        or line.amount != leg.amount
        or line.currency != movement.currency
        or line.transaction_date != movement.movement_date
        or leg.movement_id != movement.pk
        or movement.status != TreasuryMovementStatus.POSTED
        or TreasuryMovement.objects.filter(reverses=movement).exists()
    ):
        raise ValidationError("پیشنهاد دیگر با حقایق دقیق ردیف و حرکت سازگار نیست.")


@transaction.atomic
def confirm_statement_match(
    *, organization, actor, proposal: StatementMatchProposal, reason: str
) -> TreasuryMovementClearing:
    organization = _lock_organization(organization)
    checker = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_STATEMENT_MATCHES_CLEAR,
        project=proposal.movement.project,
        site=proposal.movement.site,
        message="اختیار تأیید تطبیق بانکی را ندارید.",
    )
    locked_members = _lock_memberships(
        organization=organization, memberships=(proposal.proposed_by, checker)
    )
    checker = locked_members[checker.pk]
    TreasuryAccount.objects.select_for_update().get(
        pk=proposal.statement_line.account_id
    )
    BankStatementImport.objects.select_for_update().get(
        pk=proposal.statement_line.statement_import_id
    )
    BankStatementLine.objects.select_for_update().get(pk=proposal.statement_line_id)
    TreasuryMovement.objects.select_for_update().get(pk=proposal.movement_id)
    TreasuryMovementLeg.objects.select_for_update().get(pk=proposal.movement_leg_id)
    proposal = (
        StatementMatchProposal.objects.select_for_update()
        .select_related("statement_line__statement_import", "movement", "movement_leg")
        .get(pk=proposal.pk)
    )
    if proposal.organization_id != organization.pk:
        raise PermissionDenied("پیشنهاد متعلق به این Tenant نیست.")
    if proposal.status == StatementMatchStatus.CONFIRMED:
        return proposal.clearing
    if proposal.status != StatementMatchStatus.SUGGESTED:
        raise ValidationError("فقط پیشنهاد فعال قابل تأیید است.")
    if (
        proposal.statement_line.statement_import.status
        != StatementImportStatus.ACCEPTED
    ):
        raise ValidationError("صورتحساب پذیرفته‌شده الزامی است.")
    _assert_exact_match(proposal)
    if TreasuryMovementClearing.objects.filter(
        Q(statement_line=proposal.statement_line) | Q(movement=proposal.movement),
        active=True,
    ).exists():
        raise ValidationError("ردیف یا حرکت قبلاً تسویه بانکی فعال دارد.")
    reason = _reason(reason)
    policy = _approval_policy(
        organization=organization,
        maker=locked_members[proposal.proposed_by_id],
        approver=checker,
    )
    evidence_hash = _payload_hash(
        {
            "proposal": str(proposal.pk),
            "proposal_hash": proposal.evidence_hash,
            "checker": str(checker.pk),
            "policy": str(policy.pk),
            "reason": reason,
        }
    )
    try:
        clearing = TreasuryMovementClearing.objects.create(
            organization=organization,
            proposal=proposal,
            statement_line=proposal.statement_line,
            movement=proposal.movement,
            cleared_by=checker,
            approval_policy_version=policy,
            evidence_hash=evidence_hash,
        )
    except IntegrityError as exc:
        raise ValidationError("تسویه بانکی همزمان دیگری ثبت شده است.") from exc
    now = timezone.now()
    StatementMatchProposal.objects.filter(pk=proposal.pk).update(
        status=StatementMatchStatus.CONFIRMED,
        decided_by=checker,
        decided_at=now,
        decision_reason=reason,
        approval_policy_version=policy,
        updated_at=now,
    )
    record_audit_event(
        action=AuditAction.TREASURY_STATEMENT_MATCH_DECIDED,
        entity_type="treasury.StatementMatchProposal",
        entity_id=proposal.pk,
        organization=organization,
        actor=actor,
        metadata={"to": "confirmed", "clearing": str(clearing.pk)},
    )
    return clearing


@transaction.atomic
def reject_statement_match(
    *, organization, actor, proposal: StatementMatchProposal, reason: str
) -> StatementMatchProposal:
    organization = _lock_organization(organization)
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_STATEMENT_MATCHES_MANAGE,
        project=proposal.movement.project,
        site=proposal.movement.site,
        message="اختیار رد پیشنهاد تطبیق را ندارید.",
    )
    proposal = StatementMatchProposal.objects.select_for_update().get(pk=proposal.pk)
    if proposal.organization_id != organization.pk:
        raise PermissionDenied("پیشنهاد متعلق به این Tenant نیست.")
    if proposal.status != StatementMatchStatus.SUGGESTED:
        raise ValidationError("فقط پیشنهاد فعال قابل رد است.")
    reason = _reason(reason)
    now = timezone.now()
    StatementMatchProposal.objects.filter(pk=proposal.pk).update(
        status=StatementMatchStatus.REJECTED,
        decided_by=membership,
        decided_at=now,
        decision_reason=reason,
        updated_at=now,
    )
    proposal.refresh_from_db()
    record_audit_event(
        action=AuditAction.TREASURY_STATEMENT_MATCH_DECIDED,
        entity_type="treasury.StatementMatchProposal",
        entity_id=proposal.pk,
        organization=organization,
        actor=actor,
        metadata={"to": "rejected", "reason": reason},
    )
    return proposal


@transaction.atomic
def reverse_statement_clearing(
    *, organization, actor, clearing: TreasuryMovementClearing, reason: str
) -> TreasuryMovementClearingReversal:
    organization = _lock_organization(organization)
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_STATEMENT_MATCHES_MANAGE,
        project=clearing.movement.project,
        site=clearing.movement.site,
        message="اختیار اصلاح تطبیق بانکی را ندارید.",
    )
    TreasuryAccount.objects.select_for_update().get(
        pk=clearing.statement_line.account_id
    )
    clearing = (
        TreasuryMovementClearing.objects.select_for_update()
        .select_related("proposal", "statement_line", "movement")
        .get(pk=clearing.pk)
    )
    if clearing.organization_id != organization.pk:
        raise PermissionDenied("تسویه متعلق به این Tenant نیست.")
    if not clearing.active:
        if hasattr(clearing, "reversal"):
            return clearing.reversal
        raise ValidationError("تسویه فعال نیست.")
    reason = _reason(reason)
    evidence_hash = _payload_hash(
        {
            "clearing": str(clearing.pk),
            "clearing_hash": clearing.evidence_hash,
            "actor": str(membership.pk),
            "reason": reason,
        }
    )
    reversal = TreasuryMovementClearingReversal.objects.create(
        organization=organization,
        clearing=clearing,
        reason=reason,
        reversed_by=membership,
        evidence_hash=evidence_hash,
    )
    TreasuryMovementClearing.objects.filter(pk=clearing.pk).update(active=False)
    StatementMatchProposal.objects.filter(pk=clearing.proposal_id).update(
        status=StatementMatchStatus.REVERSED, updated_at=timezone.now()
    )
    record_audit_event(
        action=AuditAction.TREASURY_CLEARING_REVERSED,
        entity_type="treasury.TreasuryMovementClearingReversal",
        entity_id=reversal.pk,
        organization=organization,
        actor=actor,
        metadata={"clearing": str(clearing.pk), "evidence_hash": evidence_hash},
    )
    return reversal


@transaction.atomic
def run_bank_reconciliation(
    *,
    organization,
    actor,
    statement_import: BankStatementImport,
    as_of_date: date,
    idempotency_key: str,
) -> BankReconciliationRun:
    organization = _lock_organization(organization)
    runner = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_BANK_RECONCILIATIONS_RUN,
        message="اختیار اجرای تطبیق بانکی را ندارید.",
    )
    statement_import = (
        BankStatementImport.objects.select_for_update()
        .select_related("account")
        .get(pk=statement_import.pk)
    )
    if statement_import.organization_id != organization.pk:
        raise PermissionDenied("صورتحساب متعلق به این Tenant نیست.")
    if statement_import.status != StatementImportStatus.ACCEPTED:
        raise ValidationError("تطبیق فقط برای صورتحساب پذیرفته‌شده مجاز است.")
    if not statement_import.period_start <= as_of_date <= statement_import.period_end:
        raise ValidationError("تاریخ تطبیق باید در بازه صورتحساب باشد.")
    idempotency_key = _canonical_text(
        idempotency_key, field="idempotency_key", required=True
    )
    lines = list(
        statement_import.lines.filter(transaction_date__lte=as_of_date).order_by(
            "row_number"
        )
    )
    active_clearings = list(
        TreasuryMovementClearing.objects.filter(
            organization=organization,
            statement_line__in=lines,
            active=True,
        ).select_related("statement_line", "movement", "proposal__movement_leg")
    )
    cleared_line_ids = {item.statement_line_id for item in active_clearings}
    unmatched_line_ids = [
        str(line.pk) for line in lines if line.pk not in cleared_line_ids
    ]
    statement_in = sum(
        (line.amount for line in lines if line.direction == TreasuryLegDirection.IN),
        Decimal(0),
    )
    statement_out = sum(
        (line.amount for line in lines if line.direction == TreasuryLegDirection.OUT),
        Decimal(0),
    )
    cleared_book_in = sum(
        (
            item.proposal.movement_leg.amount
            for item in active_clearings
            if item.proposal.movement_leg.direction == TreasuryLegDirection.IN
        ),
        Decimal(0),
    )
    cleared_book_out = sum(
        (
            item.proposal.movement_leg.amount
            for item in active_clearings
            if item.proposal.movement_leg.direction == TreasuryLegDirection.OUT
        ),
        Decimal(0),
    )
    book_movements = (
        TreasuryMovement.objects.filter(
            organization=organization,
            status=TreasuryMovementStatus.POSTED,
            movement_date__lte=as_of_date,
            legs__account=statement_import.account,
            reversal_movement__isnull=True,
        )
        .exclude(bank_clearings__active=True)
        .order_by("pk")
        .distinct()
    )
    uncleared_movement_ids = [
        str(pk) for pk in book_movements.values_list("pk", flat=True)
    ]
    exceptions: list[dict[str, object]] = []
    if unmatched_line_ids:
        exceptions.append(
            {"code": "unmatched_statement_lines", "count": len(unmatched_line_ids)}
        )
    if uncleared_movement_ids:
        exceptions.append(
            {"code": "uncleared_book_movements", "count": len(uncleared_movement_ids)}
        )
    if statement_in != cleared_book_in or statement_out != cleared_book_out:
        exceptions.append({"code": "exact_totals_difference"})
    payload = {
        "statement_import": str(statement_import.pk),
        "statement_payload_hash": statement_import.payload_hash,
        "account": str(statement_import.account_id),
        "as_of_date": as_of_date.isoformat(),
        "statement_in": str(statement_in),
        "statement_out": str(statement_out),
        "cleared_book_in": str(cleared_book_in),
        "cleared_book_out": str(cleared_book_out),
        "unmatched_line_ids": unmatched_line_ids,
        "uncleared_movement_ids": uncleared_movement_ids,
        "exceptions": exceptions,
    }
    evidence_hash = _payload_hash(payload)
    existing = BankReconciliationRun.objects.filter(
        organization=organization, idempotency_key=idempotency_key
    ).first()
    if existing:
        if existing.evidence_hash != evidence_hash:
            raise ValidationError(
                "کلید تکرارپذیری تطبیق با شواهد دیگری استفاده شده است."
            )
        return existing
    prior = (
        BankReconciliationRun.objects.select_for_update(of=("self",))
        .filter(
            organization=organization,
            statement_import=statement_import,
            account=statement_import.account,
            as_of_date=as_of_date,
            grain_revision__isnull=False,
            invalidation__isnull=True,
        )
        .order_by("-grain_revision")
        .first()
    )
    grain_revision = (prior.grain_revision if prior else 0) + 1
    run = BankReconciliationRun.objects.create(
        organization=organization,
        statement_import=statement_import,
        account=statement_import.account,
        as_of_date=as_of_date,
        idempotency_key=idempotency_key,
        evidence_hash=evidence_hash,
        statement_in=statement_in,
        statement_out=statement_out,
        cleared_book_in=cleared_book_in,
        cleared_book_out=cleared_book_out,
        unmatched_line_ids=unmatched_line_ids,
        uncleared_movement_ids=uncleared_movement_ids,
        exceptions=exceptions,
        run_by=runner,
        grain_revision=grain_revision,
        supersedes=prior,
    )
    BankReconciliationRunProvenance.objects.create(
        run=run, classification="prospective", evidence_hash=evidence_hash
    )
    record_audit_event(
        action=AuditAction.TREASURY_BANK_RECONCILIATION_RETAINED,
        entity_type="treasury.BankReconciliationRun",
        entity_id=run.pk,
        organization=organization,
        actor=actor,
        metadata={
            "account": str(statement_import.account_id),
            "as_of_date": as_of_date.isoformat(),
            "exception_count": len(exceptions),
            "evidence_hash": evidence_hash,
        },
    )
    return run
