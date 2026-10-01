from __future__ import annotations

import hashlib
import hmac
import json
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.accounting.models import FiscalPeriod, JournalKind, JournalStatus
from apps.accounting.posting_registry import get_posting_contract
from apps.accounting.services import (
    add_journal_line,
    create_journal,
    post_journal,
    reverse_journal,
    submit_journal,
)
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import (
    membership_has_permission,
    require_business_permission,
)
from apps.organizations.models import (
    BusinessPermissionCode,
    MembershipStatus,
    Organization,
    OrganizationMembership,
)
from apps.organizations.policy_services import resolve_active_tenant_policy
from apps.organizations.policy_specs import (
    TREASURY_SELF_APPROVAL_POLICY_CODE,
    validate_policy_for_consumer,
)
from apps.treasury.models import (
    AdvanceSettlement,
    AdvanceSettlementReversal,
    AdvanceSettlementStatus,
    AdvanceSettlementTransition,
    ChequeDirection,
    ChequeInstrument,
    ChequeStatus,
    ChequeTransition,
    PaymentRequest,
    PaymentRequestKind,
    PaymentRequestStatus,
    PaymentRequestTransition,
    TreasuryAccount,
    TreasuryAccountKind,
    TreasuryAccountLifecycleEvent,
    TreasuryAccountMappingVersion,
    TreasuryAccountStatus,
    TreasuryAdvance,
    TreasuryAdvanceReconciliationRun,
    TreasuryAdvanceStatus,
    TreasuryGLReconciliationReview,
    TreasuryGLReconciliationRun,
    TreasuryLegDirection,
    TreasuryMovement,
    TreasuryMovementKind,
    TreasuryMovementLeg,
    TreasuryMovementStatus,
    TreasuryMovementTransition,
    TreasuryPostingEvidence,
)

TREASURY_APPROVAL_CONSUMER = "treasury.operation.approve"
_BOUND_REVERSAL_TOKEN = object()


def _reason(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValidationError("ثبت دلیل الزامی است.")
    return value


def _lock_organization(organization: Organization) -> Organization:
    locked = Organization.objects.select_for_update().get(pk=organization.pk)
    if not locked.is_active:
        raise PermissionDenied("Tenant غیرفعال است.")
    return locked


def _fingerprint(value: str) -> tuple[str, str]:
    normalized = "".join(
        character for character in value.upper() if character.isalnum()
    )
    if len(normalized) < 4:
        raise ValidationError("شناسه حساس باید حداقل چهار نویسه داشته باشد.")
    digest = hmac.new(
        settings.SECRET_KEY.encode(), normalized.encode(), hashlib.sha256
    ).hexdigest()
    return normalized[-4:], digest


def _active_membership(
    *, organization: Organization, membership: OrganizationMembership
) -> OrganizationMembership:
    locked = (
        OrganizationMembership.objects.select_for_update()
        .select_related("user")
        .get(pk=membership.pk)
    )
    if (
        locked.organization_id != organization.pk
        or locked.status != MembershipStatus.ACTIVE
        or not locked.user.is_active
    ):
        raise PermissionDenied("عضویت فعال همین Tenant الزامی است.")
    return locked


def _approval_policy(
    *,
    organization: Organization,
    maker: OrganizationMembership,
    approver: OrganizationMembership,
):
    version = resolve_active_tenant_policy(
        organization=organization,
        policy_code=TREASURY_SELF_APPROVAL_POLICY_CODE,
    )
    validate_policy_for_consumer(
        policy_version=version,
        consumer=TREASURY_APPROVAL_CONSUMER,
        expected_policy_code=TREASURY_SELF_APPROVAL_POLICY_CODE,
    )
    if maker.pk == approver.pk and not version.parameters["allow_self_approval"]:
        raise PermissionDenied(
            "سیاست مؤثر، خودتأییدی این عملیات خزانه‌داری را مجاز نمی‌داند."
        )
    return version


def _payload_hash(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def masked_account_identifier(
    *, organization: Organization, actor, account: TreasuryAccount
) -> str:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_VIEW,
        message="اختیار مشاهده خزانه‌داری را ندارید.",
    )
    if account.organization_id != organization.pk:
        raise PermissionDenied("حساب متعلق به Tenant دیگری است.")
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_VIEW,
        message="اختیار مشاهده خزانه‌داری را ندارید.",
    )
    if not account.identifier_last4:
        return ""
    if membership_has_permission(
        membership, BusinessPermissionCode.TREASURY_SENSITIVE_VIEW
    ):
        return f"••••{account.identifier_last4}"
    return "••••"


@transaction.atomic
def create_treasury_account(
    *,
    organization: Organization,
    actor,
    code: str,
    name: str,
    kind: str,
    sensitive_identifier: str = "",
    custodian: OrganizationMembership | None = None,
) -> TreasuryAccount:
    organization = _lock_organization(organization)
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_ACCOUNTS_MANAGE,
        message="اختیار مدیریت حساب‌های خزانه‌داری را ندارید.",
    )
    if kind not in TreasuryAccountKind.values:
        raise ValidationError("نوع حساب خزانه‌داری معتبر نیست.")
    last4 = fingerprint = ""
    if sensitive_identifier:
        last4, fingerprint = _fingerprint(sensitive_identifier)
    if custodian is not None:
        custodian = _active_membership(organization=organization, membership=custodian)
    account = TreasuryAccount(
        organization=organization,
        code=code,
        name=name,
        kind=kind,
        currency="IRR",
        identifier_last4=last4,
        identifier_fingerprint=fingerprint,
        custodian=custodian,
        created_by=membership,
    )
    account.save()
    record_audit_event(
        action=AuditAction.TREASURY_ACCOUNT_CREATED,
        entity_type="treasury.TreasuryAccount",
        entity_id=account.pk,
        organization=organization,
        actor=actor,
        metadata={
            "code": account.code,
            "kind": kind,
            "identifier_retained": bool(last4),
        },
    )
    return account


@transaction.atomic
def create_account_mapping_version(
    *,
    organization: Organization,
    actor,
    account: TreasuryAccount,
    cash_ledger_account,
    clearing_ledger_account,
    effective_from: date,
    reason: str,
    requested_by: OrganizationMembership | None = None,
) -> TreasuryAccountMappingVersion:
    organization = _lock_organization(organization)
    approver = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_MAPPINGS_MANAGE,
        message="اختیار مدیریت نگاشت خزانه‌داری را ندارید.",
    )
    account = TreasuryAccount.objects.select_for_update().get(pk=account.pk)
    if account.organization_id != organization.pk:
        raise PermissionDenied("حساب متعلق به Tenant دیگری است.")
    latest = account.mapping_versions.select_for_update().order_by("-version").first()
    if latest is None:
        maker = _active_membership(
            organization=organization, membership=account.created_by
        )
    else:
        if requested_by is None:
            raise ValidationError("تغییر نگاشت به درخواست‌کننده صریح نیاز دارد.")
        maker = _active_membership(organization=organization, membership=requested_by)
        if not membership_has_permission(
            maker, BusinessPermissionCode.TREASURY_MAPPINGS_MANAGE
        ):
            raise PermissionDenied("درخواست‌کننده اختیار مدیریت نگاشت را ندارد.")
    policy = _approval_policy(organization=organization, maker=maker, approver=approver)
    for ledger_account in (cash_ledger_account, clearing_ledger_account):
        if (
            ledger_account.organization_id != organization.pk
            or not ledger_account.is_posting
            or ledger_account.archived_at is not None
        ):
            raise ValidationError("نگاشت فقط به حساب برگ فعال همین Tenant مجاز است.")
    active = account.mapping_versions.select_for_update().filter(is_active=True).first()
    version = (active.version + 1) if active else 1
    if active:
        TreasuryAccountMappingVersion.objects.filter(pk=active.pk).update(
            is_active=False,
            effective_to=effective_from,
        )
    mapping = TreasuryAccountMappingVersion(
        organization=organization,
        treasury_account=account,
        version=version,
        cash_ledger_account=cash_ledger_account,
        clearing_ledger_account=clearing_ledger_account,
        effective_from=effective_from,
        reason=_reason(reason),
        created_by=maker,
        approved_by=approver,
        approval_policy_version=policy,
    )
    mapping.save()
    record_audit_event(
        action=AuditAction.TREASURY_MAPPING_VERSIONED,
        entity_type="treasury.TreasuryAccountMappingVersion",
        entity_id=mapping.pk,
        organization=organization,
        actor=actor,
        metadata={
            "account": str(account.pk),
            "version": version,
            "policy_version": str(policy.pk),
        },
    )
    return mapping


@transaction.atomic
def transition_treasury_account(
    *,
    organization: Organization,
    actor,
    account: TreasuryAccount,
    to_status: str,
    reason: str,
    requested_by: OrganizationMembership | None = None,
) -> TreasuryAccount:
    organization = _lock_organization(organization)
    approver = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_ACCOUNTS_MANAGE,
        message="اختیار تغییر وضعیت حساب خزانه‌داری را ندارید.",
    )
    account = TreasuryAccount.objects.select_for_update().get(pk=account.pk)
    if account.organization_id != organization.pk:
        raise PermissionDenied("حساب متعلق به Tenant دیگری است.")
    transitions = {
        TreasuryAccountStatus.DRAFT: {TreasuryAccountStatus.ACTIVE},
        TreasuryAccountStatus.ACTIVE: {
            TreasuryAccountStatus.SUSPENDED,
            TreasuryAccountStatus.CLOSED,
        },
        TreasuryAccountStatus.SUSPENDED: {
            TreasuryAccountStatus.ACTIVE,
            TreasuryAccountStatus.CLOSED,
        },
        TreasuryAccountStatus.CLOSED: set(),
    }
    if to_status not in transitions[account.status]:
        raise ValidationError("گذار وضعیت حساب خزانه‌داری مجاز نیست.")
    if account.status == TreasuryAccountStatus.DRAFT:
        maker = _active_membership(
            organization=organization, membership=account.created_by
        )
    else:
        if requested_by is None:
            raise ValidationError("تغییر وضعیت حساب به درخواست‌کننده صریح نیاز دارد.")
        maker = _active_membership(organization=organization, membership=requested_by)
        if not membership_has_permission(
            maker, BusinessPermissionCode.TREASURY_ACCOUNTS_MANAGE
        ):
            raise PermissionDenied("درخواست‌کننده اختیار مدیریت حساب را ندارد.")
    policy = _approval_policy(organization=organization, maker=maker, approver=approver)
    if (
        to_status == TreasuryAccountStatus.ACTIVE
        and not account.mapping_versions.filter(is_active=True).exists()
    ):
        raise ValidationError("فعال‌سازی حساب بدون نگاشت حسابداری مؤثر مجاز نیست.")
    if to_status == TreasuryAccountStatus.CLOSED:
        balance = account.movement_legs.filter(
            movement__status=TreasuryMovementStatus.POSTED
        ).aggregate(
            incoming=Sum("amount", filter=Q(direction=TreasuryLegDirection.IN)),
            outgoing=Sum("amount", filter=Q(direction=TreasuryLegDirection.OUT)),
        )
        if (balance["incoming"] or Decimal(0)) != (balance["outgoing"] or Decimal(0)):
            raise ValidationError("بستن حساب دارای مانده مجاز نیست.")
        if account.cheques.exclude(
            status__in=[
                ChequeStatus.CLEARED,
                ChequeStatus.BOUNCED,
                ChequeStatus.CANCELLED,
            ]
        ).exists():
            raise ValidationError("بستن حساب دارای چک تعیین‌تکلیف‌نشده مجاز نیست.")
    old = account.status
    TreasuryAccount.objects.filter(pk=account.pk).update(
        status=to_status, updated_at=timezone.now()
    )
    TreasuryAccountLifecycleEvent.objects.create(
        organization=organization,
        account=account,
        from_status=old,
        to_status=to_status,
        reason=_reason(reason),
        actor=approver,
        requested_by=maker,
        approval_policy_version=policy,
    )
    account.refresh_from_db()
    record_audit_event(
        action=AuditAction.TREASURY_ACCOUNT_TRANSITIONED,
        entity_type="treasury.TreasuryAccount",
        entity_id=account.pk,
        organization=organization,
        actor=actor,
        metadata={
            "from": old,
            "to": to_status,
            "reason": reason.strip(),
            "policy_version": str(policy.pk),
        },
    )
    return account


def _movement_payload(
    *,
    kind: str,
    movement_date: date,
    amount: Decimal,
    description: str,
    accounts: list[TreasuryAccount],
    project,
    site,
    party,
) -> dict[str, object]:
    return {
        "kind": kind,
        "movement_date": movement_date.isoformat(),
        "amount": str(amount),
        "currency": "IRR",
        "description": description.strip(),
        "accounts": [str(account.pk) for account in accounts],
        "project": str(project.pk) if project else None,
        "site": str(site.pk) if site else None,
        "party": str(party.pk) if party else None,
    }


@transaction.atomic
def create_movement(
    *,
    organization: Organization,
    actor,
    kind: str,
    movement_date: date,
    amount: Decimal,
    description: str,
    idempotency_key: str,
    account: TreasuryAccount | None = None,
    source_account: TreasuryAccount | None = None,
    destination_account: TreasuryAccount | None = None,
    project=None,
    site=None,
    party=None,
) -> TreasuryMovement:
    organization = _lock_organization(organization)
    maker = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_MOVEMENTS_CREATE,
        message="اختیار ایجاد حرکت خزانه‌داری را ندارید.",
        project=project,
        site=site,
    )
    if kind not in {
        TreasuryMovementKind.RECEIPT,
        TreasuryMovementKind.DISBURSEMENT,
        TreasuryMovementKind.TRANSFER,
    }:
        raise ValidationError("نوع حرکت مستقیم معتبر نیست.")
    if not isinstance(amount, Decimal) or not amount.is_finite() or amount <= 0:
        raise ValidationError("مبلغ حرکت باید Decimal مثبت و متناهی باشد.")
    if kind == TreasuryMovementKind.TRANSFER:
        if (
            not source_account
            or not destination_account
            or source_account.pk == destination_account.pk
        ):
            raise ValidationError("انتقال به دو حساب مبدأ و مقصد متمایز نیاز دارد.")
        accounts = [source_account, destination_account]
    else:
        if not account:
            raise ValidationError("حساب حرکت الزامی است.")
        accounts = [account]
    requested_ids = [candidate.pk for candidate in accounts]
    locked_by_id = {
        candidate.pk: candidate
        for candidate in TreasuryAccount.objects.select_for_update()
        .filter(organization=organization, pk__in=requested_ids)
        .order_by("pk")
    }
    if len(locked_by_id) != len(requested_ids):
        raise ValidationError("همه حساب‌های حرکت باید متعلق به همین Tenant باشند.")
    accounts = [locked_by_id[account_id] for account_id in requested_ids]
    if kind == TreasuryMovementKind.TRANSFER:
        source_account, destination_account = accounts
    else:
        account = accounts[0]
    for candidate in accounts:
        if (
            candidate.organization_id != organization.pk
            or candidate.status != TreasuryAccountStatus.ACTIVE
        ):
            raise ValidationError("حرکت فقط روی حساب فعال همین Tenant مجاز است.")
    payload = _movement_payload(
        kind=kind,
        movement_date=movement_date,
        amount=amount,
        description=description,
        accounts=accounts,
        project=project,
        site=site,
        party=party,
    )
    digest = _payload_hash(payload)
    normalized_key = idempotency_key.strip()
    existing = TreasuryMovement.objects.filter(
        organization=organization, idempotency_key=normalized_key
    ).first()
    if existing:
        if existing.payload_hash == digest:
            return existing
        raise ValidationError("کلید idempotency با محتوای متفاوت قبلاً استفاده شده است.")
    movement = TreasuryMovement(
        organization=organization,
        kind=kind,
        movement_date=movement_date,
        amount=amount,
        description=description.strip(),
        idempotency_key=normalized_key,
        payload_hash=digest,
        project=project,
        site=site,
        party=party,
        created_by=maker,
    )
    movement.save()
    if kind == TreasuryMovementKind.RECEIPT:
        legs = [(account, TreasuryLegDirection.IN)]
    elif kind == TreasuryMovementKind.DISBURSEMENT:
        legs = [(account, TreasuryLegDirection.OUT)]
    else:
        legs = [
            (source_account, TreasuryLegDirection.OUT),
            (destination_account, TreasuryLegDirection.IN),
        ]
    for number, (leg_account, direction) in enumerate(legs, start=1):
        TreasuryMovementLeg.objects.create(
            organization=organization,
            movement=movement,
            line_number=number,
            account=leg_account,
            direction=direction,
            amount=amount,
        )
    record_audit_event(
        action=AuditAction.TREASURY_MOVEMENT_CREATED,
        entity_type="treasury.TreasuryMovement",
        entity_id=movement.pk,
        organization=organization,
        actor=actor,
        metadata={"kind": kind, "idempotency_key": normalized_key},
    )
    return movement


@transaction.atomic
def submit_movement(
    *, organization: Organization, actor, movement: TreasuryMovement, reason: str
) -> TreasuryMovement:
    organization = _lock_organization(organization)
    submitter = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_MOVEMENTS_SUBMIT,
        message="اختیار ارسال حرکت خزانه‌داری را ندارید.",
        project=movement.project,
        site=movement.site,
    )
    movement = TreasuryMovement.objects.select_for_update().get(pk=movement.pk)
    if (
        movement.organization_id != organization.pk
        or movement.status != TreasuryMovementStatus.DRAFT
    ):
        raise ValidationError("فقط پیش‌نویس همین Tenant قابل ارسال است.")
    if movement.created_by_id != submitter.pk:
        raise PermissionDenied("فقط سازنده حرکت می‌تواند آن را ارسال کند.")
    legs = list(movement.legs.select_related("account").order_by("line_number"))
    if movement.kind == TreasuryMovementKind.TRANSFER:
        if len(legs) != 2 or {leg.direction for leg in legs} != {
            TreasuryLegDirection.IN,
            TreasuryLegDirection.OUT,
        }:
            raise ValidationError(
                "انتقال باید دقیقاً یک ردیف مبدأ و یک ردیف مقصد داشته باشد."
            )
    elif len(legs) != 1:
        raise ValidationError("دریافت یا پرداخت باید دقیقاً یک ردیف حساب داشته باشد.")
    if any(
        leg.amount != movement.amount
        or leg.account.status != TreasuryAccountStatus.ACTIVE
        for leg in legs
    ):
        raise ValidationError("ردیف یا حساب حرکت معتبر نیست.")
    now = timezone.now()
    TreasuryMovement.objects.filter(pk=movement.pk).update(
        status=TreasuryMovementStatus.SUBMITTED,
        submitted_by=submitter,
        submitted_at=now,
        updated_at=now,
    )
    TreasuryMovementTransition.objects.create(
        organization=organization,
        movement=movement,
        from_status=TreasuryMovementStatus.DRAFT,
        to_status=TreasuryMovementStatus.SUBMITTED,
        reason=_reason(reason),
        actor=submitter,
    )
    movement.refresh_from_db()
    return movement


def _mapping_for_leg(
    leg: TreasuryMovementLeg, on_date: date
) -> TreasuryAccountMappingVersion:
    mapping = (
        leg.account.mapping_versions.select_for_update()
        .filter(is_active=True, effective_from__lte=on_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on_date))
        .select_related("cash_ledger_account", "clearing_ledger_account")
        .first()
    )
    if mapping is None:
        raise ValidationError("نگاشت حسابداری مؤثر برای حساب خزانه‌داری موجود نیست.")
    return mapping


@transaction.atomic
def approve_and_post_movement(
    *,
    organization: Organization,
    actor,
    movement: TreasuryMovement,
    accounting_preparer: OrganizationMembership,
    period: FiscalPeriod,
    reason: str,
) -> TreasuryMovement:
    organization = _lock_organization(organization)
    approver = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_MOVEMENTS_APPROVE,
        message="اختیار تأیید حرکت خزانه‌داری را ندارید.",
        project=movement.project,
        site=movement.site,
    )
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_MOVEMENTS_POST,
        message="اختیار ثبت قطعی حرکت خزانه‌داری را ندارید.",
        project=movement.project,
        site=movement.site,
    )
    accounting_preparer = _active_membership(
        organization=organization, membership=accounting_preparer
    )
    if accounting_preparer.pk == approver.pk:
        raise PermissionDenied("ثبت حسابداری حفاظت‌شده به تهیه‌کننده مستقل نیاز دارد.")
    movement = (
        TreasuryMovement.objects.select_for_update()
        .select_related("created_by")
        .get(pk=movement.pk)
    )
    if movement.organization_id != organization.pk:
        raise PermissionDenied("حرکت متعلق به Tenant دیگری است.")
    if movement.status == TreasuryMovementStatus.POSTED:
        return movement
    if movement.status != TreasuryMovementStatus.SUBMITTED:
        raise ValidationError("فقط حرکت ارسال‌شده قابل تأیید و ثبت است.")
    policy = _approval_policy(
        organization=organization, maker=movement.created_by, approver=approver
    )
    locked_period = FiscalPeriod.objects.select_for_update().get(pk=period.pk)
    if locked_period.organization_id != organization.pk or not (
        locked_period.starts_on <= movement.movement_date <= locked_period.ends_on
    ):
        raise ValidationError("دوره مالی با Tenant یا تاریخ حرکت سازگار نیست.")
    legs = list(
        movement.legs.select_for_update()
        .select_related("account")
        .order_by("line_number")
    )
    mappings = [_mapping_for_leg(leg, movement.movement_date) for leg in legs]
    now = timezone.now()
    TreasuryMovement.objects.filter(pk=movement.pk).update(
        status=TreasuryMovementStatus.APPROVED,
        approved_by=approver,
        approved_at=now,
        approval_policy_version=policy,
        updated_at=now,
    )
    TreasuryMovementTransition.objects.create(
        organization=organization,
        movement=movement,
        from_status=TreasuryMovementStatus.SUBMITTED,
        to_status=TreasuryMovementStatus.APPROVED,
        reason=_reason(reason),
        actor=approver,
        approval_policy_version=policy,
    )
    journal = create_journal(
        organization=organization,
        actor=accounting_preparer.user,
        period=locked_period,
        kind=JournalKind.OPERATIONAL,
        document_date=movement.movement_date,
        accounting_date=movement.movement_date,
        description=movement.description,
        source_key=f"TREASURY:{movement.pk}:V{movement.version}:POSTED",
        source_kind="treasury",
        source_uuid=movement.pk,
        source_version=movement.version,
        event_kind="movement_posted",
        occurrence_id=movement.occurrence_id,
        evidence_reference=f"treasury-movement:{movement.pk}",
        reconciliation_reference=f"treasury-to-gl:{movement.pk}",
    )
    line_number = 1
    if movement.kind in {
        TreasuryMovementKind.RECEIPT,
        TreasuryMovementKind.DISBURSEMENT,
    }:
        leg, mapping = legs[0], mappings[0]
        receipt = movement.kind == TreasuryMovementKind.RECEIPT
        add_journal_line(
            organization=organization,
            actor=accounting_preparer.user,
            journal=journal,
            account=mapping.cash_ledger_account,
            line_number=line_number,
            debit=movement.amount if receipt else Decimal(0),
            credit=Decimal(0) if receipt else movement.amount,
            description=movement.description,
            project=movement.project,
            site=movement.site,
            party=movement.party,
            source_line_uuid=leg.pk,
        )
        line_number += 1
        add_journal_line(
            organization=organization,
            actor=accounting_preparer.user,
            journal=journal,
            account=mapping.clearing_ledger_account,
            line_number=line_number,
            debit=Decimal(0) if receipt else movement.amount,
            credit=movement.amount if receipt else Decimal(0),
            description=movement.description,
            project=movement.project,
            site=movement.site,
            party=movement.party,
            source_line_uuid=leg.pk,
        )
    else:
        outgoing = next(
            (
                pair
                for pair in zip(legs, mappings, strict=True)
                if pair[0].direction == TreasuryLegDirection.OUT
            ),
            None,
        )
        incoming = next(
            (
                pair
                for pair in zip(legs, mappings, strict=True)
                if pair[0].direction == TreasuryLegDirection.IN
            ),
            None,
        )
        if not outgoing or not incoming:
            raise ValidationError("ردیف‌های انتقال معتبر نیستند.")
        for leg, mapping, debit, credit in (
            (incoming[0], incoming[1], movement.amount, Decimal(0)),
            (outgoing[0], outgoing[1], Decimal(0), movement.amount),
        ):
            add_journal_line(
                organization=organization,
                actor=accounting_preparer.user,
                journal=journal,
                account=mapping.cash_ledger_account,
                line_number=line_number,
                debit=debit,
                credit=credit,
                description=movement.description,
                project=movement.project,
                site=movement.site,
                party=movement.party,
                source_line_uuid=leg.pk,
            )
            line_number += 1
    journal = submit_journal(
        organization=organization, actor=accounting_preparer.user, journal=journal
    )
    journal = post_journal(
        organization=organization, actor=actor, journal=journal, reason=reason
    )
    contract = get_posting_contract(
        source_kind="treasury", event_kind="movement_posted"
    )
    TreasuryPostingEvidence.objects.create(
        organization=organization,
        movement=movement,
        journal=journal,
        source_version=movement.version,
        occurrence_id=movement.occurrence_id,
        source_line_ids=[str(leg.pk) for leg in legs],
        mapping_version_ids=[str(mapping.pk) for mapping in mappings],
        posting_rule_code=contract.rule_code,
        posting_rule_version=contract.rule_version,
        precision_policy_version=journal.precision_policy_version,
        rounding_policy_version=journal.rounding_policy_version,
        approval_policy_version=policy,
        fiscal_period=locked_period,
    )
    posted_at = timezone.now()
    TreasuryMovement.objects.filter(pk=movement.pk).update(
        status=TreasuryMovementStatus.POSTED,
        journal=journal,
        posted_at=posted_at,
        updated_at=posted_at,
    )
    TreasuryMovementTransition.objects.create(
        organization=organization,
        movement=movement,
        from_status=TreasuryMovementStatus.APPROVED,
        to_status=TreasuryMovementStatus.POSTED,
        reason=reason.strip(),
        actor=approver,
        approval_policy_version=policy,
    )
    movement.refresh_from_db()
    record_audit_event(
        action=AuditAction.TREASURY_MOVEMENT_TRANSITIONED,
        entity_type="treasury.TreasuryMovement",
        entity_id=movement.pk,
        organization=organization,
        actor=actor,
        metadata={
            "to": "posted",
            "journal": str(journal.pk),
            "policy_version": str(policy.pk),
        },
    )
    return movement


@transaction.atomic
def reverse_posted_movement(
    *,
    organization: Organization,
    actor,
    movement: TreasuryMovement,
    requested_by: OrganizationMembership,
    accounting_date: date,
    period: FiscalPeriod,
    reason: str,
    _boundary_token: object | None = None,
) -> TreasuryMovement:
    organization = _lock_organization(organization)
    approver = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_MOVEMENTS_REVERSE,
        message="اختیار برگشت حرکت خزانه‌داری را ندارید.",
    )
    requested_by = _active_membership(
        organization=organization, membership=requested_by
    )
    if requested_by.pk == approver.pk:
        raise PermissionDenied("برگشت مالی حفاظت‌شده به درخواست‌کننده مستقل نیاز دارد.")
    movement = TreasuryMovement.objects.select_for_update().get(pk=movement.pk)
    if (
        movement.organization_id != organization.pk
        or movement.status != TreasuryMovementStatus.POSTED
    ):
        raise ValidationError("فقط حرکت قطعی همین Tenant قابل برگشت است.")
    if _boundary_token is not _BOUND_REVERSAL_TOKEN and (
        hasattr(movement, "issued_advance")
        or movement.advance_settlements.filter(
            status=AdvanceSettlementStatus.APPROVED, reversal__isnull=True
        ).exists()
    ):
        raise ValidationError("حرکت متصل به تنخواه فقط از خدمت برگشت یکپارچه مجاز است.")
    from apps.subledgers.models import SettlementAllocation

    if SettlementAllocation.objects.filter(
        treasury_movement=movement, reversal__isnull=True
    ).exists():
        raise ValidationError(
            "حرکت دارای تخصیص فعال AP/AR است؛ ابتدا تخصیص تسویه را برگشت دهید."
        )
    existing = TreasuryMovement.objects.filter(reverses=movement).first()
    if existing:
        return existing
    policy = _approval_policy(
        organization=organization, maker=requested_by, approver=approver
    )
    reversal_journal = reverse_journal(
        organization=organization,
        actor=actor,
        original=movement.journal,
        requested_by=requested_by,
        accounting_date=accounting_date,
        period=period,
        reason=reason,
    )
    reversal = TreasuryMovement(
        organization=organization,
        kind=TreasuryMovementKind.REVERSAL,
        status=TreasuryMovementStatus.DRAFT,
        movement_date=accounting_date,
        amount=movement.amount,
        description=f"برگشت: {movement.description}",
        idempotency_key=f"REVERSAL:{movement.pk}",
        payload_hash=_payload_hash(
            {"reverses": str(movement.pk), "date": accounting_date.isoformat()}
        ),
        version=1,
        project=movement.project,
        site=movement.site,
        party=movement.party,
        created_by=requested_by,
        reverses=movement,
    )
    reversal.save()
    for source_leg in movement.legs.order_by("line_number"):
        TreasuryMovementLeg.objects.create(
            organization=organization,
            movement=reversal,
            line_number=source_leg.line_number,
            account=source_leg.account,
            direction=(
                TreasuryLegDirection.OUT
                if source_leg.direction == TreasuryLegDirection.IN
                else TreasuryLegDirection.IN
            ),
            amount=source_leg.amount,
        )
    now = timezone.now()
    TreasuryMovement.objects.filter(pk=reversal.pk).update(
        status=TreasuryMovementStatus.POSTED,
        submitted_by=requested_by,
        submitted_at=now,
        approved_by=approver,
        approved_at=now,
        posted_at=now,
        approval_policy_version=policy,
        journal=reversal_journal,
        updated_at=now,
    )
    reversal.refresh_from_db()
    contract = get_posting_contract(source_kind="accounting", event_kind="reversal")
    original_evidence = movement.posting_evidence
    TreasuryPostingEvidence.objects.create(
        organization=organization,
        movement=reversal,
        journal=reversal_journal,
        source_version=reversal.version,
        occurrence_id=reversal.occurrence_id,
        source_line_ids=[str(leg.pk) for leg in reversal.legs.order_by("line_number")],
        mapping_version_ids=original_evidence.mapping_version_ids,
        posting_rule_code=contract.rule_code,
        posting_rule_version=contract.rule_version,
        precision_policy_version=reversal_journal.precision_policy_version,
        rounding_policy_version=reversal_journal.rounding_policy_version,
        approval_policy_version=policy,
        fiscal_period=period,
    )
    record_audit_event(
        action=AuditAction.TREASURY_MOVEMENT_REVERSED,
        entity_type="treasury.TreasuryMovement",
        entity_id=movement.pk,
        organization=organization,
        actor=actor,
        metadata={
            "reversal": str(reversal.pk),
            "journal": str(reversal_journal.pk),
            "reason": reason.strip(),
        },
    )
    return reversal


@transaction.atomic
def create_cheque(
    *,
    organization: Organization,
    actor,
    direction: str,
    controlled_account: TreasuryAccount,
    amount: Decimal,
    due_date: date,
    serial: str,
    party=None,
    custodian: OrganizationMembership | None = None,
) -> ChequeInstrument:
    organization = _lock_organization(organization)
    maker = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_CHEQUES_MANAGE,
        message="اختیار مدیریت چک را ندارید.",
    )
    if direction not in ChequeDirection.values:
        raise ValidationError("جهت چک معتبر نیست.")
    if (
        controlled_account.organization_id != organization.pk
        or controlled_account.kind != TreasuryAccountKind.BANK
    ):
        raise ValidationError("چک باید به حساب بانکی همین Tenant مرتبط باشد.")
    if not isinstance(amount, Decimal) or amount <= 0:
        raise ValidationError("مبلغ چک باید Decimal مثبت باشد.")
    last4, fingerprint = _fingerprint(serial)
    if custodian:
        custodian = _active_membership(organization=organization, membership=custodian)
    cheque = ChequeInstrument(
        organization=organization,
        direction=direction,
        controlled_account=controlled_account,
        amount=amount,
        due_date=due_date,
        party=party,
        serial_last4=last4,
        serial_fingerprint=fingerprint,
        custodian=custodian,
        created_by=maker,
    )
    cheque.save()
    record_audit_event(
        action=AuditAction.TREASURY_CHEQUE_CREATED,
        entity_type="treasury.ChequeInstrument",
        entity_id=cheque.pk,
        organization=organization,
        actor=actor,
        metadata={"direction": direction, "account": str(controlled_account.pk)},
    )
    return cheque


_CHEQUE_TRANSITIONS = {
    ChequeDirection.INCOMING: {
        ChequeStatus.DRAFT: {ChequeStatus.RECEIVED, ChequeStatus.CANCELLED},
        ChequeStatus.RECEIVED: {ChequeStatus.DEPOSITED, ChequeStatus.CANCELLED},
        ChequeStatus.DEPOSITED: {ChequeStatus.PRESENTED},
        ChequeStatus.PRESENTED: {ChequeStatus.CLEARED, ChequeStatus.BOUNCED},
    },
    ChequeDirection.OUTGOING: {
        ChequeStatus.DRAFT: {ChequeStatus.ISSUED, ChequeStatus.CANCELLED},
        ChequeStatus.ISSUED: {ChequeStatus.DELIVERED, ChequeStatus.CANCELLED},
        ChequeStatus.DELIVERED: {ChequeStatus.PRESENTED},
        ChequeStatus.PRESENTED: {ChequeStatus.CLEARED, ChequeStatus.BOUNCED},
    },
}


@transaction.atomic
def transition_cheque(
    *,
    organization: Organization,
    actor,
    cheque: ChequeInstrument,
    to_status: str,
    reason: str,
) -> ChequeInstrument:
    organization = _lock_organization(organization)
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_CHEQUES_MANAGE,
        message="اختیار مدیریت چک را ندارید.",
    )
    cheque = ChequeInstrument.objects.select_for_update().get(pk=cheque.pk)
    if cheque.organization_id != organization.pk:
        raise PermissionDenied("چک متعلق به Tenant دیگری است.")
    if to_status == ChequeStatus.CLEARED:
        raise ValidationError(
            "وصول قطعی فقط از خدمت اتمیک وصول و ثبت حسابداری مجاز است."
        )
    if to_status not in _CHEQUE_TRANSITIONS.get(cheque.direction, {}).get(
        cheque.status, set()
    ):
        raise ValidationError("گذار وضعیت چک مجاز نیست.")
    old = cheque.status
    ChequeInstrument.objects.filter(pk=cheque.pk).update(
        status=to_status, updated_at=timezone.now()
    )
    ChequeTransition.objects.create(
        organization=organization,
        cheque=cheque,
        from_status=old,
        to_status=to_status,
        reason=_reason(reason),
        actor=membership,
    )
    cheque.refresh_from_db()
    return cheque


@transaction.atomic
def clear_cheque(
    *,
    organization: Organization,
    actor,
    cheque: ChequeInstrument,
    accounting_preparer: OrganizationMembership,
    period: FiscalPeriod,
    clearing_date: date,
    reason: str,
) -> ChequeInstrument:
    organization = _lock_organization(organization)
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_CHEQUES_CLEAR,
        message="اختیار ثبت وصول قطعی چک را ندارید.",
    )
    cheque = ChequeInstrument.objects.select_for_update().get(pk=cheque.pk)
    if (
        cheque.organization_id != organization.pk
        or cheque.status != ChequeStatus.PRESENTED
    ):
        raise ValidationError("فقط چک ارائه‌شده همین Tenant قابل وصول قطعی است.")
    kind = (
        TreasuryMovementKind.RECEIPT
        if cheque.direction == ChequeDirection.INCOMING
        else TreasuryMovementKind.DISBURSEMENT
    )
    movement = create_movement(
        organization=organization,
        actor=cheque.created_by.user,
        kind=kind,
        movement_date=clearing_date,
        amount=cheque.amount,
        description=f"وصول چک ••••{cheque.serial_last4}",
        idempotency_key=f"CHEQUE:{cheque.pk}:CLEAR",
        account=cheque.controlled_account,
        party=cheque.party,
    )
    movement = submit_movement(
        organization=organization,
        actor=cheque.created_by.user,
        movement=movement,
        reason=reason,
    )
    movement = approve_and_post_movement(
        organization=organization,
        actor=actor,
        movement=movement,
        accounting_preparer=accounting_preparer,
        period=period,
        reason=reason,
    )
    policy = movement.approval_policy_version
    ChequeInstrument.objects.filter(pk=cheque.pk).update(
        status=ChequeStatus.CLEARED,
        cleared_movement=movement,
        updated_at=timezone.now(),
    )
    ChequeTransition.objects.create(
        organization=organization,
        cheque=cheque,
        from_status=ChequeStatus.PRESENTED,
        to_status=ChequeStatus.CLEARED,
        reason=_reason(reason),
        actor=movement.approved_by,
        approval_policy_version=policy,
    )
    cheque.refresh_from_db()
    record_audit_event(
        action=AuditAction.TREASURY_CHEQUE_TRANSITIONED,
        entity_type="treasury.ChequeInstrument",
        entity_id=cheque.pk,
        organization=organization,
        actor=actor,
        metadata={
            "to": "cleared",
            "movement": str(movement.pk),
            "journal": str(movement.journal_id),
        },
    )
    return cheque


@transaction.atomic
def bounce_cleared_cheque(
    *,
    organization: Organization,
    actor,
    cheque: ChequeInstrument,
    requested_by: OrganizationMembership,
    accounting_date: date,
    period: FiscalPeriod,
    reason: str,
) -> ChequeInstrument:
    """Bounce a cleared cheque only with the linked immutable cash/GL reversal."""

    organization = _lock_organization(organization)
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_CHEQUES_CLEAR,
        message="اختیار ثبت برگشت چک وصول‌شده را ندارید.",
    )
    cheque = ChequeInstrument.objects.select_for_update().get(pk=cheque.pk)
    if (
        cheque.organization_id != organization.pk
        or cheque.status != ChequeStatus.CLEARED
        or not cheque.cleared_movement_id
    ):
        raise ValidationError("فقط چک وصول‌شده همین Tenant قابل برگشت است.")
    reversal = reverse_posted_movement(
        organization=organization,
        actor=actor,
        movement=cheque.cleared_movement,
        requested_by=requested_by,
        accounting_date=accounting_date,
        period=period,
        reason=reason,
    )
    ChequeInstrument.objects.filter(pk=cheque.pk).update(
        status=ChequeStatus.BOUNCED, updated_at=timezone.now()
    )
    ChequeTransition.objects.create(
        organization=organization,
        cheque=cheque,
        from_status=ChequeStatus.CLEARED,
        to_status=ChequeStatus.BOUNCED,
        reason=_reason(reason),
        actor=reversal.approved_by,
        approval_policy_version=reversal.approval_policy_version,
    )
    cheque.refresh_from_db()
    record_audit_event(
        action=AuditAction.TREASURY_CHEQUE_TRANSITIONED,
        entity_type="treasury.ChequeInstrument",
        entity_id=cheque.pk,
        organization=organization,
        actor=actor,
        metadata={"to": "bounced", "reversal_movement": str(reversal.pk)},
    )
    return cheque


@transaction.atomic
def run_treasury_gl_reconciliation(
    *, organization: Organization, actor, cutoff_date: date
) -> TreasuryGLReconciliationRun:
    organization = _lock_organization(organization)
    runner = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_RECONCILIATIONS_RUN,
        message="اختیار اجرای تطبیق خزانه‌داری را ندارید.",
    )
    movements = list(
        TreasuryMovement.objects.filter(
            organization=organization,
            status=TreasuryMovementStatus.POSTED,
            movement_date__lte=cutoff_date,
        )
        .select_related("journal", "posting_evidence")
        .prefetch_related("legs")
    )
    exceptions: list[dict[str, str]] = []
    treasury_in = treasury_out = journal_debit = journal_credit = Decimal(0)
    journal_ids: set[str] = set()
    for movement in movements:
        legs = list(movement.legs.all())
        for leg in legs:
            if leg.direction == TreasuryLegDirection.IN:
                treasury_in += leg.amount
            else:
                treasury_out += leg.amount
        journal = movement.journal
        if not journal or journal.status != JournalStatus.POSTED:
            exceptions.append(
                {"movement": str(movement.pk), "code": "missing_posted_journal"}
            )
            continue
        journal_ids.add(str(journal.pk))
        reversal_identity_valid = (
            movement.kind == TreasuryMovementKind.REVERSAL
            and movement.reverses_id
            and journal.reverses_id == movement.reverses.journal_id
        )
        if (
            not reversal_identity_valid and journal.source_uuid != movement.pk
        ) or journal.source_version != movement.version:
            exceptions.append(
                {"movement": str(movement.pk), "code": "source_identity_mismatch"}
            )
        evidence = movement.posting_evidence
        actual_source_lines = {
            str(value)
            for value in journal.lines.values_list("source_line_uuid", flat=True)
        }
        if movement.kind != TreasuryMovementKind.REVERSAL and not set(
            evidence.source_line_ids
        ).issubset(actual_source_lines):
            exceptions.append(
                {"movement": str(movement.pk), "code": "source_line_mismatch"}
            )
        mappings = {
            str(mapping.pk): mapping
            for mapping in TreasuryAccountMappingVersion.objects.filter(
                organization=organization,
                pk__in=evidence.mapping_version_ids,
            )
        }
        if len(mappings) != len(evidence.mapping_version_ids) or len(legs) != len(
            evidence.mapping_version_ids
        ):
            exceptions.append(
                {"movement": str(movement.pk), "code": "mapping_identity_mismatch"}
            )
        else:
            for leg, mapping_id in zip(legs, evidence.mapping_version_ids, strict=True):
                mapping = mappings[mapping_id]
                expected = {
                    "account_id": mapping.cash_ledger_account_id,
                    "debit": (
                        leg.amount
                        if leg.direction == TreasuryLegDirection.IN
                        else Decimal(0)
                    ),
                    "credit": (
                        leg.amount
                        if leg.direction == TreasuryLegDirection.OUT
                        else Decimal(0)
                    ),
                }
                if (
                    mapping.treasury_account_id != leg.account_id
                    or journal.lines.filter(**expected).count() != 1
                ):
                    exceptions.append(
                        {"movement": str(movement.pk), "code": "cash_leg_mismatch"}
                    )
        totals = journal.lines.aggregate(debit=Sum("debit"), credit=Sum("credit"))
        journal_debit += totals["debit"] or Decimal(0)
        journal_credit += totals["credit"] or Decimal(0)
    payload = {
        "cutoff": cutoff_date.isoformat(),
        "movements": [str(item.pk) for item in movements],
        "journals": sorted(journal_ids),
        "treasury_in": str(treasury_in),
        "treasury_out": str(treasury_out),
        "journal_debit": str(journal_debit),
        "journal_credit": str(journal_credit),
        "exceptions": exceptions,
    }
    run = TreasuryGLReconciliationRun.objects.create(
        organization=organization,
        cutoff_date=cutoff_date,
        movement_count=len(movements),
        journal_count=len(journal_ids),
        treasury_in=treasury_in,
        treasury_out=treasury_out,
        journal_debit=journal_debit,
        journal_credit=journal_credit,
        exceptions=exceptions,
        evidence_hash=_payload_hash(payload),
        run_by=runner,
    )
    record_audit_event(
        action=AuditAction.TREASURY_RECONCILIATION_RETAINED,
        entity_type="treasury.TreasuryGLReconciliationRun",
        entity_id=run.pk,
        organization=organization,
        actor=actor,
        metadata={
            "cutoff": cutoff_date.isoformat(),
            "exceptions": len(exceptions),
            "evidence_hash": run.evidence_hash,
        },
    )
    return run


def _treasury_reconciliation_review_hash(run: TreasuryGLReconciliationRun) -> str:
    return _payload_hash(
        {
            "run": str(run.pk),
            "cutoff_date": run.cutoff_date,
            "movement_count": run.movement_count,
            "journal_count": run.journal_count,
            "treasury_in": run.treasury_in,
            "treasury_out": run.treasury_out,
            "journal_debit": run.journal_debit,
            "journal_credit": run.journal_credit,
            "exceptions": run.exceptions,
            "evidence_hash": run.evidence_hash,
            "run_by": str(run.run_by_id),
        }
    )


@transaction.atomic
def review_treasury_gl_reconciliation(
    *,
    organization: Organization,
    actor,
    run: TreasuryGLReconciliationRun,
    reason: str,
) -> TreasuryGLReconciliationReview:
    """Independently sign one immutable retained cash-to-GL run."""

    organization = _lock_organization(organization)
    reviewer = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_RECONCILIATIONS_REVIEW,
        message="اختیار بررسی مستقل تطبیق خزانه‌داری را ندارید.",
    )
    reviewer = _active_membership(organization=organization, membership=reviewer)
    run = (
        TreasuryGLReconciliationRun.objects.select_for_update()
        .select_related("run_by")
        .get(pk=run.pk)
    )
    if run.organization_id != organization.pk:
        raise PermissionDenied("اجرای تطبیق متعلق به Tenant دیگری است.")
    if reviewer.pk == run.run_by_id:
        raise PermissionDenied("اجراکننده تطبیق نمی‌تواند همان اجرا را بررسی کند.")
    reason = _reason(reason)
    signed_hash = _treasury_reconciliation_review_hash(run)
    existing = TreasuryGLReconciliationReview.objects.filter(run=run).first()
    if existing:
        if (
            existing.reviewed_by_id == reviewer.pk
            and existing.reason == reason
            and existing.run_evidence_hash == run.evidence_hash
            and existing.signed_evidence_hash == signed_hash
        ):
            return existing
        raise ValidationError("اجرای تطبیق قبلاً بررسی شده است.")
    review = TreasuryGLReconciliationReview.objects.create(
        organization=organization,
        run=run,
        reason=reason,
        run_evidence_hash=run.evidence_hash,
        signed_evidence_hash=signed_hash,
        reviewed_by=reviewer,
    )
    record_audit_event(
        action=AuditAction.TREASURY_RECONCILIATION_REVIEWED,
        entity_type="treasury.TreasuryGLReconciliationReview",
        entity_id=review.pk,
        organization=organization,
        actor=actor,
        metadata={
            "run": str(run.pk),
            "reason": reason,
            "reviewed_by": str(reviewer.pk),
            "run_evidence_hash": run.evidence_hash,
            "signed_evidence_hash": signed_hash,
        },
    )
    return review


def verify_treasury_gl_reconciliation_review(
    *, organization: Organization, run: TreasuryGLReconciliationRun
) -> TreasuryGLReconciliationReview:
    run = TreasuryGLReconciliationRun.objects.get(
        pk=run.pk, organization=organization
    )
    try:
        review = run.review
    except TreasuryGLReconciliationReview.DoesNotExist as exc:
        raise ValidationError("اجرای تطبیق فاقد بررسی مستقل است.") from exc
    if (
        review.run_evidence_hash != run.evidence_hash
        or review.signed_evidence_hash != _treasury_reconciliation_review_hash(run)
    ):
        raise ValidationError("بررسی مستقل با شواهد نگهداری‌شده سازگار نیست.")
    return review


def _request_payload(
    *, kind: str, amount: Decimal, purpose: str, employee, party, project, site
) -> dict[str, object]:
    return {
        "kind": kind,
        "amount": str(amount),
        "purpose": purpose.strip(),
        "employee": str(employee.pk) if employee else None,
        "party": str(party.pk) if party else None,
        "project": str(project.pk) if project else None,
        "site": str(site.pk) if site else None,
    }


@transaction.atomic
def create_payment_request(
    *,
    organization: Organization,
    actor,
    kind: str,
    amount: Decimal,
    purpose: str,
    idempotency_key: str,
    employee=None,
    party=None,
    project=None,
    site=None,
) -> PaymentRequest:
    organization = _lock_organization(organization)
    maker = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_PAYMENT_REQUESTS_CREATE,
        message="اختیار ایجاد درخواست پرداخت را ندارید.",
        project=project,
        site=site,
    )
    if kind not in PaymentRequestKind.values:
        raise ValidationError("نوع درخواست پرداخت معتبر نیست.")
    if not isinstance(amount, Decimal) or not amount.is_finite() or amount <= 0:
        raise ValidationError("مبلغ درخواست باید Decimal مثبت و متناهی باشد.")
    if kind == PaymentRequestKind.EMPLOYEE_ADVANCE:
        if employee is None or party is not None:
            raise ValidationError("تنخواه کارمند به دقیقاً یک کارمند نیاز دارد.")
    elif employee is not None or party is None:
        raise ValidationError(
            "درخواست پرداخت/پیش‌پرداخت به دقیقاً یک طرف تجاری نیاز دارد."
        )
    payload = _request_payload(
        kind=kind,
        amount=amount,
        purpose=purpose,
        employee=employee,
        party=party,
        project=project,
        site=site,
    )
    digest = _payload_hash(payload)
    normalized_key = idempotency_key.strip()
    existing = PaymentRequest.objects.filter(
        organization=organization, idempotency_key=normalized_key
    ).first()
    if existing:
        if existing.payload_hash == digest:
            return existing
        raise ValidationError("کلید idempotency با محتوای متفاوت قبلاً استفاده شده است.")
    request = PaymentRequest(
        organization=organization,
        kind=kind,
        amount=amount,
        purpose=purpose.strip(),
        idempotency_key=normalized_key,
        payload_hash=digest,
        employee=employee,
        party=party,
        project=project,
        site=site,
        created_by=maker,
    )
    request.save()
    record_audit_event(
        action=AuditAction.TREASURY_PAYMENT_REQUEST_CREATED,
        entity_type="treasury.PaymentRequest",
        entity_id=request.pk,
        organization=organization,
        actor=actor,
        metadata={"kind": kind, "idempotency_key": normalized_key},
    )
    return request


def _record_request_transition(
    *,
    request: PaymentRequest,
    from_status: str,
    to_status: str,
    reason: str,
    actor_membership: OrganizationMembership,
    requested_by: OrganizationMembership,
    policy=None,
) -> None:
    PaymentRequestTransition.objects.create(
        organization=request.organization,
        request=request,
        from_status=from_status,
        to_status=to_status,
        reason=_reason(reason),
        actor=actor_membership,
        requested_by=requested_by,
        approval_policy_version=policy,
    )


@transaction.atomic
def submit_payment_request(
    *, organization: Organization, actor, request: PaymentRequest, reason: str
) -> PaymentRequest:
    organization = _lock_organization(organization)
    submitter = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_PAYMENT_REQUESTS_SUBMIT,
        message="اختیار ارسال درخواست پرداخت را ندارید.",
        project=request.project,
        site=request.site,
    )
    request = PaymentRequest.objects.select_for_update().get(pk=request.pk)
    if (
        request.organization_id != organization.pk
        or request.status != PaymentRequestStatus.DRAFT
    ):
        raise ValidationError("فقط پیش‌نویس همین Tenant قابل ارسال است.")
    if request.created_by_id != submitter.pk:
        raise PermissionDenied("فقط سازنده می‌تواند درخواست را ارسال کند.")
    now = timezone.now()
    PaymentRequest.objects.filter(pk=request.pk).update(
        status=PaymentRequestStatus.SUBMITTED,
        submitted_by=submitter,
        submitted_at=now,
        updated_at=now,
    )
    _record_request_transition(
        request=request,
        from_status=PaymentRequestStatus.DRAFT,
        to_status=PaymentRequestStatus.SUBMITTED,
        reason=reason,
        actor_membership=submitter,
        requested_by=submitter,
    )
    request.refresh_from_db()
    record_audit_event(
        action=AuditAction.TREASURY_PAYMENT_REQUEST_TRANSITIONED,
        entity_type="treasury.PaymentRequest",
        entity_id=request.pk,
        organization=organization,
        actor=actor,
        metadata={"to": PaymentRequestStatus.SUBMITTED},
    )
    return request


@transaction.atomic
def decide_payment_request(
    *,
    organization: Organization,
    actor,
    request: PaymentRequest,
    approve: bool,
    reason: str,
) -> PaymentRequest:
    organization = _lock_organization(organization)
    approver = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_PAYMENT_REQUESTS_APPROVE,
        message="اختیار تصمیم‌گیری درخواست پرداخت را ندارید.",
        project=request.project,
        site=request.site,
    )
    request = (
        PaymentRequest.objects.select_for_update(of=("self",))
        .select_related("submitted_by")
        .get(pk=request.pk)
    )
    if (
        request.organization_id != organization.pk
        or request.status != PaymentRequestStatus.SUBMITTED
    ):
        raise ValidationError("فقط درخواست ارسال‌شده همین Tenant قابل تصمیم است.")
    maker = _active_membership(
        organization=organization, membership=request.submitted_by
    )
    policy = _approval_policy(organization=organization, maker=maker, approver=approver)
    to_status = (
        PaymentRequestStatus.APPROVED if approve else PaymentRequestStatus.REJECTED
    )
    now = timezone.now()
    updates = {
        "status": to_status,
        "approval_policy_version": policy,
        "updated_at": now,
    }
    if approve:
        updates.update({"approved_by": approver, "approved_at": now})
    PaymentRequest.objects.filter(pk=request.pk).update(**updates)
    _record_request_transition(
        request=request,
        from_status=PaymentRequestStatus.SUBMITTED,
        to_status=to_status,
        reason=reason,
        actor_membership=approver,
        requested_by=maker,
        policy=policy,
    )
    request.refresh_from_db()
    record_audit_event(
        action=AuditAction.TREASURY_PAYMENT_REQUEST_TRANSITIONED,
        entity_type="treasury.PaymentRequest",
        entity_id=request.pk,
        organization=organization,
        actor=actor,
        metadata={"to": to_status, "policy_version": str(policy.pk)},
    )
    return request


@transaction.atomic
def cancel_payment_request(
    *, organization: Organization, actor, request: PaymentRequest, reason: str
) -> PaymentRequest:
    organization = _lock_organization(organization)
    actor_membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_PAYMENT_REQUESTS_CREATE,
        message="اختیار لغو درخواست پرداخت را ندارید.",
        project=request.project,
        site=request.site,
    )
    request = PaymentRequest.objects.select_for_update().get(pk=request.pk)
    if request.organization_id != organization.pk or request.status not in {
        PaymentRequestStatus.DRAFT,
        PaymentRequestStatus.SUBMITTED,
        PaymentRequestStatus.APPROVED,
    }:
        raise ValidationError("درخواست در این وضعیت قابل لغو نیست.")
    if request.created_by_id != actor_membership.pk:
        raise PermissionDenied("فقط سازنده می‌تواند درخواست را لغو کند.")
    previous = request.status
    PaymentRequest.objects.filter(pk=request.pk).update(
        status=PaymentRequestStatus.CANCELLED, updated_at=timezone.now()
    )
    _record_request_transition(
        request=request,
        from_status=previous,
        to_status=PaymentRequestStatus.CANCELLED,
        reason=reason,
        actor_membership=actor_membership,
        requested_by=actor_membership,
    )
    request.refresh_from_db()
    record_audit_event(
        action=AuditAction.TREASURY_PAYMENT_REQUEST_TRANSITIONED,
        entity_type="treasury.PaymentRequest",
        entity_id=request.pk,
        organization=organization,
        actor=actor,
        metadata={"to": PaymentRequestStatus.CANCELLED},
    )
    return request


@transaction.atomic
def release_payment_request(
    *,
    organization: Organization,
    actor,
    request: PaymentRequest,
    movement: TreasuryMovement,
    reason: str,
) -> PaymentRequest:
    organization = _lock_organization(organization)
    releaser = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_PAYMENT_REQUESTS_RELEASE,
        message="اختیار تخصیص پرداخت قطعی را ندارید.",
        project=request.project,
        site=request.site,
    )
    request = PaymentRequest.objects.select_for_update().get(pk=request.pk)
    movement = TreasuryMovement.objects.select_for_update().get(pk=movement.pk)
    if request.status == PaymentRequestStatus.RELEASED:
        if request.released_movement_id == movement.pk:
            return request
        raise ValidationError("درخواست قبلاً به حرکت دیگری متصل شده است.")
    if (
        request.organization_id != organization.pk
        or request.status != PaymentRequestStatus.APPROVED
    ):
        raise ValidationError("فقط درخواست تأییدشده همین Tenant قابل تخصیص است.")
    if (
        movement.organization_id != organization.pk
        or movement.kind != TreasuryMovementKind.DISBURSEMENT
        or movement.status != TreasuryMovementStatus.POSTED
        or hasattr(movement, "reversal_movement")
        or movement.amount != request.amount
        or movement.currency != request.currency
        or movement.party_id != request.party_id
    ):
        raise ValidationError("حرکت پرداخت قطعی با درخواست هم‌خوان نیست.")
    PaymentRequest.objects.filter(pk=request.pk).update(
        status=PaymentRequestStatus.RELEASED,
        released_movement=movement,
        updated_at=timezone.now(),
    )
    _record_request_transition(
        request=request,
        from_status=PaymentRequestStatus.APPROVED,
        to_status=PaymentRequestStatus.RELEASED,
        reason=reason,
        actor_membership=releaser,
        requested_by=request.submitted_by,
        policy=request.approval_policy_version,
    )
    request.refresh_from_db()
    record_audit_event(
        action=AuditAction.TREASURY_PAYMENT_REQUEST_RELEASED,
        entity_type="treasury.PaymentRequest",
        entity_id=request.pk,
        organization=organization,
        actor=actor,
        metadata={"movement": str(movement.pk)},
    )
    return request


@transaction.atomic
def open_advance(
    *, organization: Organization, actor, request: PaymentRequest
) -> TreasuryAdvance:
    organization = _lock_organization(organization)
    opener = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_ADVANCES_MANAGE,
        message="اختیار مدیریت تنخواه را ندارید.",
        project=request.project,
        site=request.site,
    )
    request = (
        PaymentRequest.objects.select_for_update(of=("self",))
        .select_related("released_movement")
        .get(pk=request.pk)
    )
    existing = TreasuryAdvance.objects.filter(request=request).first()
    if existing:
        return existing
    if (
        request.organization_id != organization.pk
        or request.kind
        not in {PaymentRequestKind.EMPLOYEE_ADVANCE, PaymentRequestKind.VENDOR_ADVANCE}
        or request.status != PaymentRequestStatus.RELEASED
        or not request.released_movement_id
        or request.released_movement.status != TreasuryMovementStatus.POSTED
    ):
        raise ValidationError("تنها درخواست تنخواه پرداخت‌شده قابل بازشدن است.")
    advance = TreasuryAdvance.objects.create(
        organization=organization,
        request=request,
        issue_movement=request.released_movement,
        opened_by=opener,
    )
    record_audit_event(
        action=AuditAction.TREASURY_ADVANCE_OPENED,
        entity_type="treasury.TreasuryAdvance",
        entity_id=advance.pk,
        organization=organization,
        actor=actor,
        metadata={
            "request": str(request.pk),
            "movement": str(request.released_movement_id),
        },
    )
    return advance


def _active_settlement_amount(*, advance=None, movement=None) -> Decimal:
    query = AdvanceSettlement.objects.filter(
        status=AdvanceSettlementStatus.APPROVED, reversal__isnull=True
    )
    if advance is not None:
        query = query.filter(advance=advance)
    if movement is not None:
        query = query.filter(receipt_movement=movement)
    return query.aggregate(total=Sum("amount"))["total"] or Decimal(0)


@transaction.atomic
def create_advance_settlement(
    *,
    organization: Organization,
    actor,
    advance: TreasuryAdvance,
    receipt_movement: TreasuryMovement,
    amount: Decimal,
    idempotency_key: str,
) -> AdvanceSettlement:
    organization = _lock_organization(organization)
    maker = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_ADVANCES_SETTLE,
        message="اختیار ثبت تسویه تنخواه را ندارید.",
        project=advance.request.project,
        site=advance.request.site,
    )
    advance = (
        TreasuryAdvance.objects.select_for_update()
        .select_related("request")
        .get(pk=advance.pk)
    )
    receipt_movement = TreasuryMovement.objects.select_for_update().get(
        pk=receipt_movement.pk
    )
    if not isinstance(amount, Decimal) or not amount.is_finite() or amount <= 0:
        raise ValidationError("مبلغ تسویه باید Decimal مثبت و متناهی باشد.")
    payload = {
        "advance": str(advance.pk),
        "receipt": str(receipt_movement.pk),
        "amount": str(amount),
    }
    digest = _payload_hash(payload)
    normalized_key = idempotency_key.strip()
    existing = AdvanceSettlement.objects.filter(
        organization=organization, idempotency_key=normalized_key
    ).first()
    if existing:
        if existing.payload_hash == digest:
            return existing
        raise ValidationError(
            "کلید idempotency تسویه با محتوای متفاوت استفاده شده است."
        )
    request = advance.request
    if (
        advance.organization_id != organization.pk
        or advance.status == TreasuryAdvanceStatus.REVERSED
        or receipt_movement.organization_id != organization.pk
        or receipt_movement.kind != TreasuryMovementKind.RECEIPT
        or receipt_movement.status != TreasuryMovementStatus.POSTED
        or hasattr(receipt_movement, "reversal_movement")
        or receipt_movement.party_id != request.party_id
    ):
        raise ValidationError("حرکت دریافت با تنخواه هم‌خوان نیست.")
    settlement = AdvanceSettlement.objects.create(
        organization=organization,
        advance=advance,
        receipt_movement=receipt_movement,
        amount=amount,
        idempotency_key=normalized_key,
        payload_hash=digest,
        created_by=maker,
    )
    record_audit_event(
        action=AuditAction.TREASURY_ADVANCE_SETTLEMENT_CREATED,
        entity_type="treasury.AdvanceSettlement",
        entity_id=settlement.pk,
        organization=organization,
        actor=actor,
        metadata={"advance": str(advance.pk), "receipt": str(receipt_movement.pk)},
    )
    return settlement


@transaction.atomic
def submit_advance_settlement(
    *, organization: Organization, actor, settlement: AdvanceSettlement, reason: str
) -> AdvanceSettlement:
    organization = _lock_organization(organization)
    submitter = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_ADVANCES_SETTLE,
        message="اختیار ارسال تسویه تنخواه را ندارید.",
        project=settlement.advance.request.project,
        site=settlement.advance.request.site,
    )
    settlement = AdvanceSettlement.objects.select_for_update().get(pk=settlement.pk)
    if (
        settlement.organization_id != organization.pk
        or settlement.status != AdvanceSettlementStatus.DRAFT
    ):
        raise ValidationError("فقط پیش‌نویس تسویه همین Tenant قابل ارسال است.")
    if settlement.created_by_id != submitter.pk:
        raise PermissionDenied("فقط سازنده می‌تواند تسویه را ارسال کند.")
    now = timezone.now()
    AdvanceSettlement.objects.filter(pk=settlement.pk).update(
        status=AdvanceSettlementStatus.SUBMITTED,
        submitted_by=submitter,
        submitted_at=now,
        updated_at=now,
    )
    AdvanceSettlementTransition.objects.create(
        organization=organization,
        settlement=settlement,
        from_status=AdvanceSettlementStatus.DRAFT,
        to_status=AdvanceSettlementStatus.SUBMITTED,
        reason=_reason(reason),
        actor=submitter,
        requested_by=submitter,
    )
    settlement.refresh_from_db()
    record_audit_event(
        action=AuditAction.TREASURY_ADVANCE_SETTLEMENT_TRANSITIONED,
        entity_type="treasury.AdvanceSettlement",
        entity_id=settlement.pk,
        organization=organization,
        actor=actor,
        metadata={"to": AdvanceSettlementStatus.SUBMITTED},
    )
    return settlement


@transaction.atomic
def cancel_advance_settlement(
    *, organization: Organization, actor, settlement: AdvanceSettlement, reason: str
) -> AdvanceSettlement:
    organization = _lock_organization(organization)
    actor_membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_ADVANCES_SETTLE,
        message="اختیار لغو تسویه تنخواه را ندارید.",
        project=settlement.advance.request.project,
        site=settlement.advance.request.site,
    )
    settlement = AdvanceSettlement.objects.select_for_update().get(pk=settlement.pk)
    if settlement.organization_id != organization.pk or settlement.status not in {
        AdvanceSettlementStatus.DRAFT,
        AdvanceSettlementStatus.SUBMITTED,
    }:
        raise ValidationError("تسویه در این وضعیت قابل لغو نیست.")
    if settlement.created_by_id != actor_membership.pk:
        raise PermissionDenied("فقط سازنده می‌تواند تسویه را لغو کند.")
    previous = settlement.status
    AdvanceSettlement.objects.filter(pk=settlement.pk).update(
        status=AdvanceSettlementStatus.CANCELLED, updated_at=timezone.now()
    )
    AdvanceSettlementTransition.objects.create(
        organization=organization,
        settlement=settlement,
        from_status=previous,
        to_status=AdvanceSettlementStatus.CANCELLED,
        reason=_reason(reason),
        actor=actor_membership,
        requested_by=actor_membership,
    )
    settlement.refresh_from_db()
    record_audit_event(
        action=AuditAction.TREASURY_ADVANCE_SETTLEMENT_TRANSITIONED,
        entity_type="treasury.AdvanceSettlement",
        entity_id=settlement.pk,
        organization=organization,
        actor=actor,
        metadata={"to": AdvanceSettlementStatus.CANCELLED},
    )
    return settlement


@transaction.atomic
def decide_advance_settlement(
    *,
    organization: Organization,
    actor,
    settlement: AdvanceSettlement,
    approve: bool,
    reason: str,
) -> AdvanceSettlement:
    organization = _lock_organization(organization)
    approver = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_ADVANCES_SETTLE,
        message="اختیار تصمیم تسویه تنخواه را ندارید.",
        project=settlement.advance.request.project,
        site=settlement.advance.request.site,
    )
    settlement = (
        AdvanceSettlement.objects.select_for_update(of=("self",))
        .select_related("submitted_by")
        .get(pk=settlement.pk)
    )
    advance = (
        TreasuryAdvance.objects.select_for_update()
        .select_related("request")
        .get(pk=settlement.advance_id)
    )
    movement = TreasuryMovement.objects.select_for_update().get(
        pk=settlement.receipt_movement_id
    )
    if (
        settlement.organization_id != organization.pk
        or settlement.status != AdvanceSettlementStatus.SUBMITTED
    ):
        raise ValidationError("فقط تسویه ارسال‌شده همین Tenant قابل تصمیم است.")
    maker = _active_membership(
        organization=organization, membership=settlement.submitted_by
    )
    policy = _approval_policy(organization=organization, maker=maker, approver=approver)
    to_status = (
        AdvanceSettlementStatus.APPROVED
        if approve
        else AdvanceSettlementStatus.REJECTED
    )
    if approve:
        advance_used = _active_settlement_amount(advance=advance)
        receipt_used = _active_settlement_amount(movement=movement)
        if (
            advance_used + settlement.amount > advance.request.amount
            or receipt_used + settlement.amount > movement.amount
        ):
            raise ValidationError(
                "مبلغ تسویه از مانده تنخواه یا ظرفیت دریافت بیشتر است."
            )
    now = timezone.now()
    updates = {
        "status": to_status,
        "approval_policy_version": policy,
        "updated_at": now,
    }
    if approve:
        updates.update({"approved_by": approver, "approved_at": now})
    AdvanceSettlement.objects.filter(pk=settlement.pk).update(**updates)
    AdvanceSettlementTransition.objects.create(
        organization=organization,
        settlement=settlement,
        from_status=AdvanceSettlementStatus.SUBMITTED,
        to_status=to_status,
        reason=_reason(reason),
        actor=approver,
        requested_by=maker,
        approval_policy_version=policy,
    )
    if approve:
        settled = _active_settlement_amount(advance=advance)
        status = (
            TreasuryAdvanceStatus.SETTLED
            if settled == advance.request.amount
            else TreasuryAdvanceStatus.PARTIALLY_SETTLED
        )
        TreasuryAdvance.objects.filter(pk=advance.pk).update(
            status=status, updated_at=now
        )
    settlement.refresh_from_db()
    record_audit_event(
        action=AuditAction.TREASURY_ADVANCE_SETTLEMENT_TRANSITIONED,
        entity_type="treasury.AdvanceSettlement",
        entity_id=settlement.pk,
        organization=organization,
        actor=actor,
        metadata={"to": to_status, "policy_version": str(policy.pk)},
    )
    return settlement


@transaction.atomic
def reverse_advance_issue(
    *,
    organization: Organization,
    actor,
    advance: TreasuryAdvance,
    requested_by: OrganizationMembership,
    accounting_date: date,
    period: FiscalPeriod,
    reason: str,
) -> TreasuryAdvance:
    organization = _lock_organization(organization)
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_ADVANCES_REVERSE,
        message="اختیار برگشت تنخواه را ندارید.",
        project=advance.request.project,
        site=advance.request.site,
    )
    advance = TreasuryAdvance.objects.select_for_update().get(pk=advance.pk)
    if advance.organization_id != organization.pk:
        raise ValidationError("تنخواه متعلق به Tenant دیگری است.")
    if advance.status == TreasuryAdvanceStatus.REVERSED:
        return advance
    if _active_settlement_amount(advance=advance):
        raise ValidationError(
            "پیش از برگشت اصل تنخواه، تمام تسویه‌های فعال باید برگشت خورند."
        )
    reversal = reverse_posted_movement(
        organization=organization,
        actor=actor,
        movement=advance.issue_movement,
        requested_by=requested_by,
        accounting_date=accounting_date,
        period=period,
        reason=reason,
        _boundary_token=_BOUND_REVERSAL_TOKEN,
    )
    TreasuryAdvance.objects.filter(pk=advance.pk).update(
        status=TreasuryAdvanceStatus.REVERSED,
        reversal_movement=reversal,
        updated_at=timezone.now(),
    )
    advance.refresh_from_db()
    record_audit_event(
        action=AuditAction.TREASURY_ADVANCE_REVERSED,
        entity_type="treasury.TreasuryAdvance",
        entity_id=advance.pk,
        organization=organization,
        actor=actor,
        metadata={"reversal_movement": str(reversal.pk)},
    )
    return advance


@transaction.atomic
def reverse_advance_settlement(
    *,
    organization: Organization,
    actor,
    settlement: AdvanceSettlement,
    requested_by: OrganizationMembership,
    accounting_date: date,
    period: FiscalPeriod,
    reason: str,
) -> AdvanceSettlementReversal:
    organization = _lock_organization(organization)
    actor_membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_ADVANCES_REVERSE,
        message="اختیار برگشت تسویه تنخواه را ندارید.",
        project=settlement.advance.request.project,
        site=settlement.advance.request.site,
    )
    requested_by = _active_membership(
        organization=organization, membership=requested_by
    )
    policy = _approval_policy(
        organization=organization, maker=requested_by, approver=actor_membership
    )
    settlement = AdvanceSettlement.objects.select_for_update().get(pk=settlement.pk)
    existing = AdvanceSettlementReversal.objects.filter(settlement=settlement).first()
    if existing:
        return existing
    if (
        settlement.organization_id != organization.pk
        or settlement.status != AdvanceSettlementStatus.APPROVED
    ):
        raise ValidationError("فقط تسویه تأییدشده همین Tenant قابل برگشت است.")
    other_active_allocations = settlement.receipt_movement.advance_settlements.filter(
        status=AdvanceSettlementStatus.APPROVED,
        reversal__isnull=True,
    ).exclude(pk=settlement.pk)
    reversal_movement = None
    if not other_active_allocations.exists() and (
        settlement.amount == settlement.receipt_movement.amount
    ):
        reversal_movement = reverse_posted_movement(
            organization=organization,
            actor=actor,
            movement=settlement.receipt_movement,
            requested_by=requested_by,
            accounting_date=accounting_date,
            period=period,
            reason=reason,
            _boundary_token=_BOUND_REVERSAL_TOKEN,
        )
    reversal = AdvanceSettlementReversal.objects.create(
        organization=organization,
        settlement=settlement,
        reversal_movement=reversal_movement,
        actor=actor_membership,
        requested_by=requested_by,
        approval_policy_version=policy,
        reason=_reason(reason),
    )
    advance = (
        TreasuryAdvance.objects.select_for_update()
        .select_related("request")
        .get(pk=settlement.advance_id)
    )
    remaining_settled = _active_settlement_amount(advance=advance)
    new_status = (
        TreasuryAdvanceStatus.OPEN
        if remaining_settled == 0
        else TreasuryAdvanceStatus.PARTIALLY_SETTLED
    )
    TreasuryAdvance.objects.filter(pk=advance.pk).update(
        status=new_status, updated_at=timezone.now()
    )
    record_audit_event(
        action=AuditAction.TREASURY_ADVANCE_SETTLEMENT_REVERSED,
        entity_type="treasury.AdvanceSettlement",
        entity_id=settlement.pk,
        organization=organization,
        actor=actor,
        metadata={
            "reversal_movement": (
                str(reversal_movement.pk) if reversal_movement else None
            ),
            "policy_version": str(policy.pk),
        },
    )
    return reversal


@transaction.atomic
def run_advance_reconciliation(
    *, organization: Organization, actor, cutoff_date: date, idempotency_key: str
) -> TreasuryAdvanceReconciliationRun:
    organization = _lock_organization(organization)
    runner = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TREASURY_RECONCILIATIONS_RUN,
        message="اختیار اجرای تطبیق تنخواه را ندارید.",
    )
    normalized_key = idempotency_key.strip()
    advances = list(
        TreasuryAdvance.objects.filter(
            organization=organization,
            issue_movement__movement_date__lte=cutoff_date,
        )
        .select_related("request", "issue_movement__journal", "reversal_movement")
        .order_by("pk")
    )
    issued_total = Decimal(0)
    settled_total = Decimal(0)
    outstanding_total = Decimal(0)
    exceptions: list[dict[str, str]] = []
    for advance in advances:
        amount = advance.request.amount
        if advance.status != TreasuryAdvanceStatus.REVERSED:
            issued_total += amount
        movement = advance.issue_movement
        if (
            movement.status != TreasuryMovementStatus.POSTED
            or not movement.journal_id
            or not hasattr(movement, "posting_evidence")
        ):
            exceptions.append(
                {"advance": str(advance.pk), "code": "issue_posting_missing"}
            )
        active = list(
            advance.settlements.filter(
                status=AdvanceSettlementStatus.APPROVED,
                reversal__isnull=True,
                receipt_movement__movement_date__lte=cutoff_date,
            ).select_related("receipt_movement__journal")
        )
        active_total = sum((item.amount for item in active), Decimal(0))
        if active_total > amount:
            exceptions.append(
                {"advance": str(advance.pk), "code": "settlement_overapplied"}
            )
        for item in active:
            receipt = item.receipt_movement
            if (
                receipt.status != TreasuryMovementStatus.POSTED
                or not receipt.journal_id
                or not hasattr(receipt, "posting_evidence")
            ):
                exceptions.append(
                    {"settlement": str(item.pk), "code": "receipt_posting_missing"}
                )
        if advance.status != TreasuryAdvanceStatus.REVERSED:
            settled_total += active_total
            outstanding_total += amount - active_total
    payload = {
        "cutoff": cutoff_date.isoformat(),
        "advances": [str(item.pk) for item in advances],
        "issued": str(issued_total),
        "settled": str(settled_total),
        "outstanding": str(outstanding_total),
        "exceptions": exceptions,
    }
    digest = _payload_hash(payload)
    existing = TreasuryAdvanceReconciliationRun.objects.filter(
        organization=organization, idempotency_key=normalized_key
    ).first()
    if existing:
        if existing.evidence_hash == digest:
            return existing
        raise ValidationError("کلید اجرای تطبیق با شواهد متفاوت استفاده شده است.")
    run = TreasuryAdvanceReconciliationRun.objects.create(
        organization=organization,
        cutoff_date=cutoff_date,
        idempotency_key=normalized_key,
        evidence_hash=digest,
        advance_count=len(advances),
        issued_total=issued_total,
        settled_total=settled_total,
        outstanding_total=outstanding_total,
        exceptions=exceptions,
        run_by=runner,
    )
    record_audit_event(
        action=AuditAction.TREASURY_ADVANCE_RECONCILIATION_RETAINED,
        entity_type="treasury.TreasuryAdvanceReconciliationRun",
        entity_id=run.pk,
        organization=organization,
        actor=actor,
        metadata={
            "cutoff": cutoff_date.isoformat(),
            "exceptions": len(exceptions),
            "evidence_hash": digest,
        },
    )
    return run
