import hashlib
import json
import uuid
from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, QuerySet, Sum
from django.utils import timezone

from apps.accounting.models import (
    Account,
    AccountType,
    ControlAccountMappingVersion,
    FiscalPeriod,
    FiscalPeriodControlEvent,
    FiscalPeriodStatus,
    FiscalYear,
    FiscalYearStatus,
    JournalEntry,
    JournalKind,
    JournalLine,
    JournalNumberSequence,
    JournalStatus,
    OpeningBalanceImport,
    OpeningBalanceImportLine,
    OpeningImportStatus,
    PeriodControlActionType,
    ReconciliationRun,
)
from apps.accounting.policy_calculations import (
    require_final_monetary_amount,
    resolve_accounting_posting_policies,
)
from apps.accounting.posting_registry import get_posting_contract
from apps.accounts.models import User
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
from apps.parties.models import BusinessParty
from apps.projects.models import Project, ProjectSite, WBSNode

ACCOUNTING_PRECISION_POLICY_CODE = "accounting-money-precision"
ACCOUNTING_ROUNDING_POLICY_CODE = "accounting-rounding"


def _lock_accounting_organization(organization: Organization) -> Organization:
    """Serialize financial mutations for one Tenant before narrower row locks."""

    return Organization.objects.select_for_update().get(pk=organization.pk)


def _require_reason(reason: str) -> str:
    normalized = reason.strip()
    if not normalized:
        raise ValidationError("ثبت دلیل الزامی است.")
    return normalized


def _validate_independent_requester(
    *,
    organization: Organization,
    actor_membership: OrganizationMembership,
    requested_by: OrganizationMembership,
    permission: BusinessPermissionCode,
) -> None:
    if (
        requested_by.organization_id != organization.pk
        or requested_by.status != MembershipStatus.ACTIVE
        or not requested_by.user.is_active
        or not membership_has_permission(requested_by, permission)
    ):
        raise PermissionDenied("درخواست‌کننده فعال و مجاز نیست.")
    if requested_by.pk == actor_membership.pk:
        raise PermissionDenied("درخواست و تأیید عملیات حفاظت‌شده باید مستقل باشد.")


def _journal_payload_hash(journal: JournalEntry) -> str:
    lines = list(
        journal.lines.order_by("line_number").values(
            "line_number",
            "account_id",
            "debit",
            "credit",
            "project_id",
            "site_id",
            "wbs_node_id",
            "party_id",
            "description",
            "source_line_uuid",
        )
    )
    payload = {
        "kind": journal.kind,
        "document_date": journal.document_date.isoformat(),
        "accounting_date": journal.accounting_date.isoformat(),
        "currency": journal.currency,
        "period_id": str(journal.period_id),
        "description": journal.description,
        "evidence_reference": journal.evidence_reference,
        "reconciliation_reference": journal.reconciliation_reference,
        "cutoff_date": (
            journal.cutoff_date.isoformat() if journal.cutoff_date else None
        ),
        "source_kind": journal.source_kind,
        "source_uuid": str(journal.source_uuid),
        "source_version": journal.source_version,
        "event_kind": journal.event_kind,
        "occurrence_id": str(journal.occurrence_id),
        "adjusts_id": str(journal.adjusts_id) if journal.adjusts_id else None,
        "adjustment_reason": journal.adjustment_reason,
        "lines": [
            {
                key: str(value) if value is not None else None
                for key, value in line.items()
            }
            for line in lines
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _snapshot_posted_lines(journal: JournalEntry) -> None:
    lines = journal.lines.select_related(
        "account", "project", "site", "wbs_node", "party"
    )
    for line in lines:
        account_snapshot = {
            "id": str(line.account_id),
            "code": line.account.code,
            "name": line.account.name,
            "type": line.account.account_type,
        }
        dimension_snapshot: dict[str, dict[str, str]] = {}
        if line.project_id:
            dimension_snapshot["project"] = {
                "id": str(line.project_id),
                "code": line.project.code,
                "name": line.project.name,
            }
        if line.site_id:
            dimension_snapshot["site"] = {
                "id": str(line.site_id),
                "code": line.site.code,
                "name": line.site.name,
            }
        if line.wbs_node_id:
            dimension_snapshot["wbs"] = {
                "id": str(line.wbs_node_id),
                "code": line.wbs_node.code,
                "name": line.wbs_node.title,
            }
        if line.party_id:
            dimension_snapshot["party"] = {
                "id": str(line.party_id),
                "name": line.party.display_name,
            }
        JournalLine.objects.filter(pk=line.pk).update(
            account_snapshot=account_snapshot,
            dimension_snapshot=dimension_snapshot,
        )


def _link_draft_line_to_source(
    *, line: JournalLine, source_line_uuid: uuid.UUID
) -> None:
    """Pin internal transfer lineage without exposing arbitrary source IDs."""

    if line.journal.status != JournalStatus.DRAFT:
        raise ValidationError("پیوند منبع فقط برای ردیف پیش‌نویس مجاز است.")
    JournalLine.objects.filter(pk=line.pk).update(source_line_uuid=source_line_uuid)


def list_accounts(*, organization: Organization, actor: User) -> QuerySet[Account]:
    """Return only the authorized Tenant's chart of accounts."""

    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_VIEW,
        message="اختیار مشاهده حسابداری را ندارید.",
    )
    return Account.objects.filter(organization=organization).select_related("parent")


@transaction.atomic
def create_account(
    *,
    organization: Organization,
    actor: User,
    code: str,
    name: str,
    account_type: str,
    parent: Account | None = None,
    is_posting: bool = False,
) -> Account:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_ACCOUNTS_MANAGE,
        message="اختیار مدیریت کدینگ حساب‌ها را ندارید.",
    )
    if account_type not in AccountType.values:
        raise ValidationError("نوع حساب معتبر نیست.")
    account = Account(
        organization=organization,
        code=code,
        name=name,
        account_type=account_type,
        parent=parent,
        is_posting=is_posting,
        created_by=actor,
    )
    account.save()
    record_audit_event(
        action=AuditAction.ACCOUNTING_ACCOUNT_CREATED,
        entity_type="accounting.Account",
        entity_id=account.pk,
        organization=organization,
        actor=actor,
        metadata={"code": account.code, "account_type": account.account_type},
    )
    return account


@transaction.atomic
def create_control_account_mapping_version(
    *,
    organization: Organization,
    actor: User,
    source_kind: str,
    direction: str,
    control_account: Account,
    effective_from: date,
    effective_to: date | None,
    reason: str,
) -> ControlAccountMappingVersion:
    """Create the immutable Accounting policy used to pin AP/AR obligations."""

    organization = _lock_accounting_organization(organization)
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_CONTROL_ACCOUNT_MAPPINGS_MANAGE,
        message="اختیار مدیریت نگاشت حساب کنترل را ندارید.",
    )
    source_kind = source_kind.strip()
    if not source_kind:
        raise ValidationError("نوع منبع نگاشت الزامی است.")
    if direction not in {"payable", "receivable"}:
        raise ValidationError("جهت نگاشت حساب کنترل معتبر نیست.")
    if effective_to and effective_to < effective_from:
        raise ValidationError("بازه اعتبار نگاشت نامعتبر است.")
    control_account = Account.objects.select_for_update().get(pk=control_account.pk)
    if (
        control_account.organization_id != organization.pk
        or not control_account.is_posting
        or control_account.archived_at is not None
    ):
        raise ValidationError("نگاشت فقط به حساب برگ فعال همین Tenant مجاز است.")
    scope = ControlAccountMappingVersion.objects.select_for_update().filter(
        organization=organization, source_kind=source_kind, direction=direction
    )
    if (
        scope.filter(effective_from__lte=effective_to if effective_to else date.max)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=effective_from))
        .exists()
    ):
        raise ValidationError("بازه نگاشت حساب کنترل با نسخه موجود هم‌پوشانی دارد.")
    version = (
        scope.order_by("-version").values_list("version", flat=True).first() or 0
    ) + 1
    mapping = ControlAccountMappingVersion(
        organization=organization,
        source_kind=source_kind,
        direction=direction,
        version=version,
        control_account=control_account,
        effective_from=effective_from,
        effective_to=effective_to,
        reason=_require_reason(reason),
        created_by=membership,
    )
    mapping.save()
    record_audit_event(
        action=AuditAction.ACCOUNTING_CONTROL_ACCOUNT_MAPPING_VERSIONED,
        entity_type="accounting.ControlAccountMappingVersion",
        entity_id=mapping.pk,
        organization=organization,
        actor=actor,
        metadata={
            "source_kind": source_kind,
            "direction": direction,
            "version": version,
        },
    )
    return mapping


def resolve_control_account_mapping(
    *, organization: Organization, source_kind: str, direction: str, effective_on: date
) -> ControlAccountMappingVersion:
    """Return the one approved mapping or fail closed without any fallback."""

    mappings = ControlAccountMappingVersion.objects.filter(
        organization=organization,
        source_kind=source_kind,
        direction=direction,
        effective_from__lte=effective_on,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=effective_on))
    try:
        return mappings.select_related("control_account").get()
    except ControlAccountMappingVersion.DoesNotExist as exc:
        raise ValidationError(
            "نگاشت مؤثر حساب کنترل برای این تعهد تأیید نشده است."
        ) from exc
    except ControlAccountMappingVersion.MultipleObjectsReturned as exc:
        raise ValidationError("نگاشت مؤثر حساب کنترل مبهم است.") from exc


@transaction.atomic
def create_fiscal_year(
    *,
    organization: Organization,
    actor: User,
    code: str,
    name: str,
    starts_on: date,
    ends_on: date,
    calendar_version: int,
) -> FiscalYear:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_PERIODS_MANAGE,
        message="اختیار مدیریت سال مالی را ندارید.",
    )
    Organization.objects.select_for_update().get(pk=organization.pk)
    if FiscalYear.objects.filter(
        organization=organization, starts_on__lte=ends_on, ends_on__gte=starts_on
    ).exists():
        raise ValidationError("سال مالی با سال موجود هم‌پوشانی دارد.")
    fiscal_year = FiscalYear(
        organization=organization,
        code=code,
        name=name.strip(),
        starts_on=starts_on,
        ends_on=ends_on,
        calendar_version=calendar_version,
        status=FiscalYearStatus.ACTIVE,
        created_by=actor,
    )
    fiscal_year.save()
    record_audit_event(
        action=AuditAction.ACCOUNTING_FISCAL_YEAR_CREATED,
        entity_type="accounting.FiscalYear",
        entity_id=fiscal_year.pk,
        organization=organization,
        actor=actor,
        metadata={"code": fiscal_year.code, "calendar_version": calendar_version},
    )
    return fiscal_year


@transaction.atomic
def create_fiscal_period(
    *,
    organization: Organization,
    actor: User,
    fiscal_year: FiscalYear,
    number: int,
    name: str,
    starts_on: date,
    ends_on: date,
    is_adjustment: bool = False,
) -> FiscalPeriod:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_PERIODS_MANAGE,
        message="اختیار مدیریت دوره مالی را ندارید.",
    )
    locked_year = FiscalYear.objects.select_for_update().get(pk=fiscal_year.pk)
    if locked_year.organization_id != organization.pk:
        raise PermissionDenied("سال مالی متعلق به Tenant دیگری است.")
    if FiscalPeriod.objects.filter(
        fiscal_year=locked_year, starts_on__lte=ends_on, ends_on__gte=starts_on
    ).exists():
        raise ValidationError("دوره مالی با دوره موجود هم‌پوشانی دارد.")
    period = FiscalPeriod(
        organization=organization,
        fiscal_year=locked_year,
        number=number,
        name=name.strip(),
        starts_on=starts_on,
        ends_on=ends_on,
        is_adjustment=is_adjustment,
    )
    period.save()
    record_audit_event(
        action=AuditAction.ACCOUNTING_FISCAL_PERIOD_CREATED,
        entity_type="accounting.FiscalPeriod",
        entity_id=period.pk,
        organization=organization,
        actor=actor,
        metadata={"fiscal_year": locked_year.code, "period_number": number},
    )
    return period


@transaction.atomic
def create_journal(
    *,
    organization: Organization,
    actor: User,
    period: FiscalPeriod,
    kind: str,
    document_date: date,
    accounting_date: date,
    description: str,
    source_key: str,
    evidence_reference: str = "",
    reconciliation_reference: str = "",
    cutoff_date: date | None = None,
    source_kind: str | None = None,
    source_uuid: uuid.UUID | None = None,
    source_version: int = 1,
    event_kind: str | None = None,
    occurrence_id: uuid.UUID | None = None,
    reverses: JournalEntry | None = None,
    replaces: JournalEntry | None = None,
    adjusts: JournalEntry | None = None,
    adjustment_reason: str = "",
) -> JournalEntry:
    organization = _lock_accounting_organization(organization)
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_JOURNALS_PREPARE,
        message="اختیار تهیه سند حسابداری را ندارید.",
    )
    if kind not in JournalKind.values:
        raise ValidationError("نوع سند معتبر نیست.")
    default_contract = {
        JournalKind.MANUAL: ("manual", "manual_entry"),
        JournalKind.OPENING: ("opening", "opening_balance"),
        JournalKind.REVERSAL: ("accounting", "reversal"),
        JournalKind.REPLACEMENT: ("accounting", "replacement"),
        JournalKind.OPERATIONAL: ("treasury", "movement_posted"),
    }[kind]
    resolved_source_kind = source_kind or default_contract[0]
    resolved_event_kind = event_kind or default_contract[1]
    get_posting_contract(
        source_kind=resolved_source_kind, event_kind=resolved_event_kind
    )
    period = FiscalPeriod.objects.select_for_update().get(pk=period.pk)
    if period.organization_id != organization.pk:
        raise PermissionDenied("دوره مالی متعلق به Tenant دیگری است.")
    if period.status != FiscalPeriodStatus.OPEN:
        raise ValidationError("سند فقط در دوره مالی باز قابل تهیه است.")
    normalized_source_key = source_key.strip()
    existing = JournalEntry.objects.filter(
        organization=organization, source_key=normalized_source_key
    ).first()
    if existing:
        same_request = (
            existing.kind == kind
            and existing.period_id == period.pk
            and existing.document_date == document_date
            and existing.accounting_date == accounting_date
            and existing.description == description.strip()
            and existing.evidence_reference == evidence_reference.strip()
            and existing.reconciliation_reference == reconciliation_reference.strip()
            and existing.cutoff_date == cutoff_date
            and existing.source_kind == resolved_source_kind
            and existing.source_version == source_version
            and existing.event_kind == resolved_event_kind
            and (source_uuid is None or existing.source_uuid == source_uuid)
            and (occurrence_id is None or existing.occurrence_id == occurrence_id)
            and existing.reverses_id == (reverses.pk if reverses else None)
            and existing.replaces_id == (replaces.pk if replaces else None)
            and existing.adjusts_id == (adjusts.pk if adjusts else None)
            and existing.adjustment_reason == adjustment_reason.strip()
        )
        if same_request:
            return existing
        raise ValidationError("کلید منبع با محتوای متفاوت قبلاً استفاده شده است.")
    journal = JournalEntry(
        organization=organization,
        period=period,
        kind=kind,
        document_date=document_date,
        accounting_date=accounting_date,
        description=description.strip(),
        source_key=normalized_source_key,
        source_kind=resolved_source_kind,
        source_version=source_version,
        event_kind=resolved_event_kind,
        evidence_reference=evidence_reference.strip(),
        reconciliation_reference=reconciliation_reference.strip(),
        cutoff_date=cutoff_date,
        prepared_by=membership,
        reverses=reverses,
        replaces=replaces,
        adjusts=adjusts,
        adjustment_reason=adjustment_reason.strip(),
    )
    journal.source_uuid = source_uuid or journal.pk
    journal.occurrence_id = occurrence_id or journal.pk
    identity_match = JournalEntry.objects.filter(
        organization=organization,
        source_kind=journal.source_kind,
        source_uuid=journal.source_uuid,
        source_version=journal.source_version,
        event_kind=journal.event_kind,
        occurrence_id=journal.occurrence_id,
    ).first()
    if identity_match:
        if identity_match.source_key == journal.source_key:
            return identity_match
        raise ValidationError("هویت رویداد با کلید منبع دیگری قبلاً ثبت شده است.")
    journal.save()
    record_audit_event(
        action=AuditAction.ACCOUNTING_JOURNAL_CREATED,
        entity_type="accounting.JournalEntry",
        entity_id=journal.pk,
        organization=organization,
        actor=actor,
        metadata={"kind": kind, "source_key": journal.source_key},
    )
    return journal


@transaction.atomic
def create_controlled_adjustment(
    *,
    organization: Organization,
    actor: User,
    original: JournalEntry,
    period: FiscalPeriod,
    document_date: date,
    accounting_date: date,
    description: str,
    source_key: str,
    reason: str,
    evidence_reference: str,
    reconciliation_reference: str,
) -> JournalEntry:
    """Create a manual-source late adjustment without rewriting closed history."""

    organization = _lock_accounting_organization(organization)
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_ADJUSTMENTS_PREPARE,
        message="اختیار تهیه تعدیل کنترل‌شده را ندارید.",
    )
    normalized_reason = _require_reason(reason)
    if not evidence_reference.strip() or not reconciliation_reference.strip():
        raise ValidationError("تعدیل کنترل‌شده به مدرک و مرجع تطبیق نیاز دارد.")
    locked_original = (
        JournalEntry.objects.select_for_update()
        .select_related("period")
        .get(pk=original.pk)
    )
    locked_period = FiscalPeriod.objects.select_for_update().get(pk=period.pk)
    if (
        locked_original.organization_id != organization.pk
        or locked_original.status != JournalStatus.POSTED
        or locked_original.period.status != FiscalPeriodStatus.CLOSED
    ):
        raise ValidationError("تعدیل فقط برای سند قطعی دوره بسته همین Tenant مجاز است.")
    if (
        locked_period.organization_id != organization.pk
        or not locked_period.is_adjustment
        or locked_period.status != FiscalPeriodStatus.OPEN
    ):
        raise ValidationError("تعدیل فقط در دوره تعدیلی باز همین Tenant مجاز است.")
    existing = JournalEntry.objects.filter(
        organization=organization, source_key=source_key.strip()
    ).first()
    journal = create_journal(
        organization=organization,
        actor=actor,
        period=locked_period,
        kind=JournalKind.MANUAL,
        document_date=document_date,
        accounting_date=accounting_date,
        description=description,
        source_key=source_key,
        evidence_reference=evidence_reference,
        reconciliation_reference=reconciliation_reference,
        adjusts=locked_original,
        adjustment_reason=normalized_reason,
    )
    if existing is None:
        record_audit_event(
            action=AuditAction.ACCOUNTING_CONTROLLED_ADJUSTMENT_CREATED,
            entity_type="accounting.JournalEntry",
            entity_id=journal.pk,
            organization=organization,
            actor=actor,
            metadata={
                "adjusts_journal": str(locked_original.pk),
                "reason": normalized_reason,
                "evidence_reference": evidence_reference.strip(),
                "reconciliation_reference": reconciliation_reference.strip(),
            },
        )
    return journal


@transaction.atomic
def add_journal_line(
    *,
    organization: Organization,
    actor: User,
    journal: JournalEntry,
    account: Account,
    line_number: int,
    debit: Decimal = Decimal(0),
    credit: Decimal = Decimal(0),
    description: str = "",
    project: Project | None = None,
    site: ProjectSite | None = None,
    wbs_node: WBSNode | None = None,
    party: BusinessParty | None = None,
    source_line_uuid: uuid.UUID | None = None,
) -> JournalLine:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_JOURNALS_PREPARE,
        message="اختیار تهیه سند حسابداری را ندارید.",
        project=project,
        site=site,
    )
    locked = JournalEntry.objects.select_for_update().get(pk=journal.pk)
    if locked.organization_id != organization.pk:
        raise PermissionDenied("سند متعلق به Tenant دیگری است.")
    if locked.prepared_by.user_id != actor.pk:
        raise PermissionDenied("فقط تهیه‌کننده می‌تواند ردیف پیش‌نویس را تغییر دهد.")
    line = JournalLine(
        organization=organization,
        journal=locked,
        line_number=line_number,
        account=account,
        description=description.strip(),
        debit=debit,
        credit=credit,
        project=project,
        site=site,
        wbs_node=wbs_node,
        party=party,
    )
    if source_line_uuid is not None:
        line.source_line_uuid = source_line_uuid
    line.save()
    return line


@transaction.atomic
def submit_journal(
    *, organization: Organization, actor: User, journal: JournalEntry
) -> JournalEntry:
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_JOURNALS_SUBMIT,
        message="اختیار ارسال سند حسابداری را ندارید.",
    )
    locked = JournalEntry.objects.select_for_update().get(pk=journal.pk)
    if (
        locked.organization_id != organization.pk
        or locked.status != JournalStatus.DRAFT
    ):
        raise ValidationError("فقط پیش‌نویس همین Tenant قابل ارسال است.")
    if locked.prepared_by_id != membership.pk:
        raise PermissionDenied("فقط تهیه‌کننده سند می‌تواند آن را ارسال کند.")
    totals = locked.lines.aggregate(debit=Sum("debit"), credit=Sum("credit"))
    if not locked.lines.exists() or totals["debit"] != totals["credit"]:
        raise ValidationError(
            "سند باید دارای ردیف و از نظر بدهکار/بستانکار متوازن باشد."
        )
    precision, rounding = resolve_accounting_posting_policies(organization=organization)
    for line in locked.lines.all():
        require_final_monetary_amount(
            line.debit, precision=precision, rounding=rounding
        )
        require_final_monetary_amount(
            line.credit, precision=precision, rounding=rounding
        )
    contract = get_posting_contract(
        source_kind=locked.source_kind, event_kind=locked.event_kind
    )
    payload_hash = _journal_payload_hash(locked)
    now = timezone.now()
    JournalEntry.objects.filter(pk=locked.pk).update(
        status=JournalStatus.PROPOSED,
        submitted_by=membership,
        submitted_at=now,
        precision_policy_version=precision.version,
        rounding_policy_version=rounding.version,
        payload_hash=payload_hash,
        posting_rule_code=contract.rule_code,
        posting_rule_version=contract.rule_version,
        updated_at=now,
    )
    locked.refresh_from_db()
    record_audit_event(
        action=AuditAction.ACCOUNTING_JOURNAL_SUBMITTED,
        entity_type="accounting.JournalEntry",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={
            "precision_policy_version": precision.version.version,
            "rounding_policy_version": rounding.version.version,
        },
    )
    return locked


@transaction.atomic
def post_journal(
    *, organization: Organization, actor: User, journal: JournalEntry, reason: str
) -> JournalEntry:
    organization = _lock_accounting_organization(organization)
    approver = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_JOURNALS_APPROVE,
        message="اختیار تأیید سند حسابداری را ندارید.",
    )
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_JOURNALS_POST,
        message="اختیار ثبت قطعی سند حسابداری را ندارید.",
    )
    normalized_reason = _require_reason(reason)
    locked = (
        JournalEntry.objects.select_for_update()
        .select_related("period")
        .get(pk=journal.pk)
    )
    period = FiscalPeriod.objects.select_for_update().get(pk=locked.period_id)
    if locked.organization_id != organization.pk:
        raise ValidationError("سند متعلق به این Tenant نیست.")
    if locked.status == JournalStatus.POSTED:
        return locked
    if locked.status != JournalStatus.PROPOSED:
        raise ValidationError("فقط سند پیشنهادی همین Tenant قابل ثبت است.")
    if approver.pk == locked.prepared_by_id:
        raise PermissionDenied("تهیه‌کننده نمی‌تواند همان سند حفاظت‌شده را تأیید کند.")
    if period.status != FiscalPeriodStatus.OPEN:
        raise ValidationError("دوره مالی بسته است.")
    if not locked.payload_hash or locked.payload_hash != _journal_payload_hash(locked):
        raise ValidationError("محتوای سند پس از ارسال تغییر کرده است.")
    contract = get_posting_contract(
        source_kind=locked.source_kind, event_kind=locked.event_kind
    )
    if (
        locked.posting_rule_code != contract.rule_code
        or locked.posting_rule_version != contract.rule_version
    ):
        raise ValidationError("نسخه قاعده ثبت سند معتبر نیست.")
    sequence, _ = JournalNumberSequence.objects.select_for_update().get_or_create(
        organization=organization
    )
    number = sequence.next_number
    sequence.next_number += 1
    sequence.save(update_fields=["next_number"])
    _snapshot_posted_lines(locked)
    now = timezone.now()
    JournalEntry.objects.filter(pk=locked.pk).update(
        status=JournalStatus.POSTED,
        number=number,
        posted_by=approver,
        posted_at=now,
        updated_at=now,
    )
    locked.refresh_from_db()
    record_audit_event(
        action=AuditAction.ACCOUNTING_JOURNAL_POSTED,
        entity_type="accounting.JournalEntry",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"number": number, "reason": normalized_reason, "kind": locked.kind},
    )
    return locked


@transaction.atomic
def create_replacement_journal(
    *,
    organization: Organization,
    actor: User,
    original: JournalEntry,
    period: FiscalPeriod,
    document_date: date,
    accounting_date: date,
    description: str,
) -> JournalEntry:
    organization = _lock_accounting_organization(organization)
    locked_original = JournalEntry.objects.select_for_update().get(pk=original.pk)
    if (
        locked_original.organization_id != organization.pk
        or locked_original.status != JournalStatus.POSTED
    ):
        raise ValidationError("فقط سند ثبت‌شده همین Tenant قابل جایگزینی است.")
    if not JournalEntry.objects.filter(
        reverses=locked_original, status=JournalStatus.POSTED
    ).exists():
        raise ValidationError("جایگزینی فقط پس از ثبت برگشت مرتبط مجاز است.")
    return create_journal(
        organization=organization,
        actor=actor,
        period=period,
        kind=JournalKind.REPLACEMENT,
        document_date=document_date,
        accounting_date=accounting_date,
        description=description,
        source_key=f"REPLACEMENT:{locked_original.pk}",
        source_kind="accounting",
        source_uuid=locked_original.pk,
        source_version=locked_original.source_version + 1,
        event_kind="replacement",
        occurrence_id=locked_original.pk,
        replaces=locked_original,
    )


@transaction.atomic
def reverse_journal(
    *,
    organization: Organization,
    actor: User,
    original: JournalEntry,
    requested_by: OrganizationMembership,
    accounting_date: date,
    period: FiscalPeriod,
    reason: str,
) -> JournalEntry:
    organization = _lock_accounting_organization(organization)
    normalized_reason = _require_reason(reason)
    approver = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_JOURNALS_APPROVE,
        message="اختیار تأیید برگشت سند را ندارید.",
    )
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_JOURNALS_POST,
        message="اختیار ثبت برگشت سند را ندارید.",
    )
    _validate_independent_requester(
        organization=organization,
        actor_membership=approver,
        requested_by=requested_by,
        permission=BusinessPermissionCode.ACCOUNTING_JOURNALS_PREPARE,
    )
    locked_original = JournalEntry.objects.select_for_update().get(pk=original.pk)
    if (
        locked_original.organization_id != organization.pk
        or locked_original.status != JournalStatus.POSTED
    ):
        raise ValidationError("فقط سند ثبت‌شده همین Tenant قابل برگشت است.")
    existing = JournalEntry.objects.filter(reverses=locked_original).first()
    if existing:
        return existing
    reversal = create_journal(
        organization=organization,
        actor=requested_by.user,
        period=period,
        kind=JournalKind.REVERSAL,
        document_date=accounting_date,
        accounting_date=accounting_date,
        description=f"برگشت سند {locked_original.number}: {normalized_reason}",
        source_key=f"REVERSAL:{locked_original.pk}",
        source_kind="accounting",
        source_uuid=locked_original.pk,
        event_kind="reversal",
        occurrence_id=locked_original.pk,
        reverses=locked_original,
    )
    for source_line in locked_original.lines.order_by("line_number"):
        reversal_line = add_journal_line(
            organization=organization,
            actor=requested_by.user,
            journal=reversal,
            account=source_line.account,
            line_number=source_line.line_number,
            debit=source_line.credit,
            credit=source_line.debit,
            description=source_line.description,
            project=source_line.project,
            site=source_line.site,
            wbs_node=source_line.wbs_node,
            party=source_line.party,
        )
        _link_draft_line_to_source(line=reversal_line, source_line_uuid=source_line.pk)
    reversal = submit_journal(
        organization=organization, actor=requested_by.user, journal=reversal
    )
    posted = post_journal(
        organization=organization,
        actor=actor,
        journal=reversal,
        reason=normalized_reason,
    )
    record_audit_event(
        action=AuditAction.ACCOUNTING_JOURNAL_REVERSED,
        entity_type="accounting.JournalEntry",
        entity_id=locked_original.pk,
        organization=organization,
        actor=actor,
        metadata={"reversal_journal": str(posted.pk), "reason": normalized_reason},
    )
    return posted


@transaction.atomic
def create_opening_import(
    *,
    organization: Organization,
    actor: User,
    fiscal_year: FiscalYear,
    period: FiscalPeriod,
    source_reference: str,
    cutoff_date: date,
    evidence_reference: str,
    reconciliation_reference: str,
) -> OpeningBalanceImport:
    organization = _lock_accounting_organization(organization)
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_JOURNALS_PREPARE,
        message="اختیار تهیه ورودی افتتاحیه را ندارید.",
    )
    period = FiscalPeriod.objects.select_for_update().get(pk=period.pk)
    if period.organization_id != organization.pk:
        raise PermissionDenied("دوره مالی متعلق به Tenant دیگری است.")
    if period.status != FiscalPeriodStatus.OPEN:
        raise ValidationError("افتتاحیه فقط در دوره مالی باز قابل تهیه است.")
    opening_import = OpeningBalanceImport(
        organization=organization,
        fiscal_year=fiscal_year,
        period=period,
        source_reference=source_reference.strip(),
        cutoff_date=cutoff_date,
        evidence_reference=evidence_reference.strip(),
        reconciliation_reference=reconciliation_reference.strip(),
        prepared_by=membership,
    )
    opening_import.save()
    record_audit_event(
        action=AuditAction.ACCOUNTING_OPENING_IMPORT_CREATED,
        entity_type="accounting.OpeningBalanceImport",
        entity_id=opening_import.pk,
        organization=organization,
        actor=actor,
        metadata={"cutoff_date": cutoff_date.isoformat()},
    )
    return opening_import


@transaction.atomic
def add_opening_import_line(
    *,
    organization: Organization,
    actor: User,
    opening_import: OpeningBalanceImport,
    account: Account,
    line_number: int,
    debit: Decimal = Decimal(0),
    credit: Decimal = Decimal(0),
    description: str = "",
    project: Project | None = None,
    site: ProjectSite | None = None,
    wbs_node: WBSNode | None = None,
    party: BusinessParty | None = None,
) -> OpeningBalanceImportLine:
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_JOURNALS_PREPARE,
        message="اختیار تهیه ورودی افتتاحیه را ندارید.",
        project=project,
        site=site,
    )
    locked = OpeningBalanceImport.objects.select_for_update().get(pk=opening_import.pk)
    if (
        locked.organization_id != organization.pk
        or locked.prepared_by_id != membership.pk
    ):
        raise PermissionDenied("ورودی افتتاحیه متعلق به تهیه‌کننده همین Tenant نیست.")
    line = OpeningBalanceImportLine(
        organization=organization,
        opening_import=locked,
        line_number=line_number,
        account=account,
        debit=debit,
        credit=credit,
        description=description.strip(),
        project=project,
        site=site,
        wbs_node=wbs_node,
        party=party,
    )
    line.save()
    return line


@transaction.atomic
def submit_opening_import(
    *, organization: Organization, actor: User, opening_import: OpeningBalanceImport
) -> OpeningBalanceImport:
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_JOURNALS_SUBMIT,
        message="اختیار ارسال ورودی افتتاحیه را ندارید.",
    )
    locked = OpeningBalanceImport.objects.select_for_update().get(pk=opening_import.pk)
    if (
        locked.organization_id != organization.pk
        or locked.prepared_by_id != membership.pk
        or locked.status != OpeningImportStatus.DRAFT
    ):
        raise ValidationError("فقط پیش‌نویس خود تهیه‌کننده قابل ارسال است.")
    totals = locked.lines.aggregate(debit=Sum("debit"), credit=Sum("credit"))
    if not locked.lines.exists() or totals["debit"] != totals["credit"]:
        raise ValidationError("ورودی افتتاحیه باید متوازن و دارای ردیف باشد.")
    OpeningBalanceImport.objects.filter(pk=locked.pk).update(
        status=OpeningImportStatus.PROPOSED,
        proposed_at=timezone.now(),
        updated_at=timezone.now(),
    )
    locked.refresh_from_db()
    record_audit_event(
        action=AuditAction.ACCOUNTING_OPENING_IMPORT_SUBMITTED,
        entity_type="accounting.OpeningBalanceImport",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"line_count": locked.lines.count()},
    )
    return locked


@transaction.atomic
def accept_opening_import(
    *,
    organization: Organization,
    actor: User,
    opening_import: OpeningBalanceImport,
    reason: str,
) -> JournalEntry:
    organization = _lock_accounting_organization(organization)
    approver = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_JOURNALS_APPROVE,
        message="اختیار تأیید ورودی افتتاحیه را ندارید.",
    )
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_JOURNALS_POST,
        message="اختیار ثبت ورودی افتتاحیه را ندارید.",
    )
    normalized_reason = _require_reason(reason)
    locked = (
        OpeningBalanceImport.objects.select_for_update()
        .select_related("prepared_by__user", "period")
        .get(pk=opening_import.pk)
    )
    if locked.organization_id != organization.pk:
        raise PermissionDenied("ورودی افتتاحیه متعلق به Tenant دیگری است.")
    if locked.status == OpeningImportStatus.ACCEPTED and locked.accepted_journal_id:
        return locked.accepted_journal
    if locked.status != OpeningImportStatus.PROPOSED:
        raise ValidationError("فقط ورودی آماده بررسی قابل پذیرش است.")
    if approver.pk == locked.prepared_by_id:
        raise PermissionDenied("تهیه‌کننده نمی‌تواند افتتاحیه را تأیید کند.")
    journal = create_journal(
        organization=organization,
        actor=locked.prepared_by.user,
        period=locked.period,
        kind=JournalKind.OPENING,
        document_date=locked.period.starts_on,
        accounting_date=locked.period.starts_on,
        description=f"افتتاحیه کنترل‌شده: {locked.source_reference}",
        source_key=f"OPENING-IMPORT:{locked.pk}",
        evidence_reference=locked.evidence_reference,
        reconciliation_reference=locked.reconciliation_reference,
        cutoff_date=locked.cutoff_date,
        source_kind="opening",
        source_uuid=locked.pk,
        event_kind="opening_balance",
        occurrence_id=locked.pk,
    )
    for source_line in locked.lines.order_by("line_number"):
        journal_line = add_journal_line(
            organization=organization,
            actor=locked.prepared_by.user,
            journal=journal,
            account=source_line.account,
            line_number=source_line.line_number,
            debit=source_line.debit,
            credit=source_line.credit,
            description=source_line.description,
            project=source_line.project,
            site=source_line.site,
            wbs_node=source_line.wbs_node,
            party=source_line.party,
        )
        _link_draft_line_to_source(line=journal_line, source_line_uuid=source_line.pk)
    journal = submit_journal(
        organization=organization, actor=locked.prepared_by.user, journal=journal
    )
    journal = post_journal(
        organization=organization,
        actor=actor,
        journal=journal,
        reason=normalized_reason,
    )
    now = timezone.now()
    OpeningBalanceImport.objects.filter(pk=locked.pk).update(
        status=OpeningImportStatus.ACCEPTED,
        accepted_by=approver,
        accepted_at=now,
        accepted_journal=journal,
        updated_at=now,
    )
    record_audit_event(
        action=AuditAction.ACCOUNTING_OPENING_IMPORT_ACCEPTED,
        entity_type="accounting.OpeningBalanceImport",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"journal": str(journal.pk), "reason": normalized_reason},
    )
    return journal


@transaction.atomic
def close_period(
    *,
    organization: Organization,
    actor: User,
    period: FiscalPeriod,
    requested_by: OrganizationMembership,
    reason: str,
) -> FiscalPeriod:
    organization = _lock_accounting_organization(organization)
    approver = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_PERIODS_CLOSE,
        message="اختیار بستن دوره مالی را ندارید.",
    )
    _validate_independent_requester(
        organization=organization,
        actor_membership=approver,
        requested_by=requested_by,
        permission=BusinessPermissionCode.ACCOUNTING_PERIODS_CLOSE,
    )
    normalized_reason = _require_reason(reason)
    locked = FiscalPeriod.objects.select_for_update().get(pk=period.pk)
    if locked.organization_id != organization.pk:
        raise PermissionDenied("دوره مالی متعلق به Tenant دیگری است.")
    previous = locked.control_events.order_by("-sequence").first()
    if locked.status == FiscalPeriodStatus.CLOSED:
        if (
            previous is not None
            and previous.action == PeriodControlActionType.CLOSE
            and previous.requested_by_id == requested_by.pk
            and previous.acted_by_id == approver.pk
            and previous.reason == normalized_reason
        ):
            return locked
        raise ValidationError("فقط دوره باز همین Tenant قابل بستن است.")
    if locked.status != FiscalPeriodStatus.OPEN:
        raise ValidationError("فقط دوره باز همین Tenant قابل بستن است.")
    if locked.journals.filter(
        status__in=[JournalStatus.DRAFT, JournalStatus.PROPOSED]
    ).exists():
        raise ValidationError("دوره دارای سند پیش‌نویس یا پیشنهادی تعیین‌تکلیف‌نشده است.")
    if locked.opening_balance_imports.filter(
        status__in=[OpeningImportStatus.DRAFT, OpeningImportStatus.PROPOSED]
    ).exists():
        raise ValidationError("دوره دارای ورودی افتتاحیه تعیین‌تکلیف‌نشده است.")
    reconciliation = (
        ReconciliationRun.objects.select_related("review")
        .filter(organization=organization, cutoff_date=locked.ends_on)
        .filter(review__isnull=False)
        .order_by("-created_at")
        .first()
    )
    if reconciliation is None:
        raise ValidationError(
            "بستن دوره به تطبیق نگهداری‌شده و تأیید مستقل در پایان دوره نیاز دارد."
        )
    from apps.accounting.reconciliation import verify_signed_reconciliation_run

    reconciliation_review = verify_signed_reconciliation_run(
        organization=organization, run=reconciliation
    )
    from apps.accounting.reporting import retain_statement

    trial_balance = retain_statement(
        organization=organization,
        actor=actor,
        kind="trial_balance",
        starts_on=locked.starts_on,
        ends_on=locked.ends_on,
    )
    if trial_balance.debit_total != trial_balance.credit_total:
        raise ValidationError("گردش بدهکار و بستانکار تراز آزمایشی دوره برابر نیست.")
    balance_sheet = retain_statement(
        organization=organization,
        actor=actor,
        kind="balance_sheet",
        ends_on=locked.ends_on,
    )
    profit_loss = retain_statement(
        organization=organization,
        actor=actor,
        kind="profit_loss",
        starts_on=locked.fiscal_year.starts_on,
        ends_on=locked.ends_on,
    )
    sequence = previous.sequence + 1 if previous else 1
    evidence_payload = {
        "period": str(locked.pk),
        "sequence": sequence,
        "action": PeriodControlActionType.CLOSE,
        "requested_by": str(requested_by.pk),
        "acted_by": str(approver.pk),
        "reason": normalized_reason,
        "reconciliation": str(reconciliation.pk),
        "reconciliation_evidence": reconciliation.result_hash,
        "reconciliation_sign_off": reconciliation_review.signed_evidence_hash,
        "trial_balance_input": trial_balance.input_hash,
        "trial_balance_result": trial_balance.result_hash,
        "balance_sheet_input": balance_sheet.input_hash,
        "balance_sheet_result": balance_sheet.result_hash,
        "profit_loss_input": profit_loss.input_hash,
        "profit_loss_result": profit_loss.result_hash,
    }
    evidence_hash = hashlib.sha256(
        json.dumps(evidence_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    event = FiscalPeriodControlEvent.objects.create(
        organization=organization,
        period=locked,
        sequence=sequence,
        action=PeriodControlActionType.CLOSE,
        requested_by=requested_by,
        acted_by=approver,
        reason=normalized_reason,
        reconciliation_run=reconciliation,
        trial_balance_run=trial_balance,
        balance_sheet_run=balance_sheet,
        profit_loss_run=profit_loss,
        evidence_hash=evidence_hash,
    )
    FiscalPeriod.objects.filter(pk=locked.pk).update(
        status=FiscalPeriodStatus.CLOSED, updated_at=timezone.now()
    )
    locked.refresh_from_db()
    record_audit_event(
        action=AuditAction.ACCOUNTING_PERIOD_CLOSED,
        entity_type="accounting.FiscalPeriod",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={
            "requested_by_membership": str(requested_by.pk),
            "reason": normalized_reason,
            "control_event": str(event.pk),
            "evidence_hash": evidence_hash,
        },
    )
    return locked


@transaction.atomic
def reopen_period(
    *,
    organization: Organization,
    actor: User,
    period: FiscalPeriod,
    requested_by: OrganizationMembership,
    reason: str,
) -> FiscalPeriod:
    organization = _lock_accounting_organization(organization)
    approver = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTING_PERIODS_REOPEN,
        message="اختیار بازگشایی دوره مالی را ندارید.",
    )
    _validate_independent_requester(
        organization=organization,
        actor_membership=approver,
        requested_by=requested_by,
        permission=BusinessPermissionCode.ACCOUNTING_PERIODS_REOPEN,
    )
    normalized_reason = _require_reason(reason)
    locked = FiscalPeriod.objects.select_for_update().get(pk=period.pk)
    if locked.organization_id != organization.pk:
        raise PermissionDenied("دوره مالی متعلق به Tenant دیگری است.")
    latest_event = locked.control_events.order_by("-sequence").first()
    if locked.status == FiscalPeriodStatus.OPEN:
        if (
            latest_event is not None
            and latest_event.action == PeriodControlActionType.REOPEN
            and latest_event.requested_by_id == requested_by.pk
            and latest_event.acted_by_id == approver.pk
            and latest_event.reason == normalized_reason
        ):
            return locked
        raise ValidationError("فقط دوره بسته همین Tenant قابل بازگشایی است.")
    if locked.status != FiscalPeriodStatus.CLOSED:
        raise ValidationError("فقط دوره بسته همین Tenant قابل بازگشایی است.")
    close_event = (
        locked.control_events.filter(action=PeriodControlActionType.CLOSE)
        .order_by("-sequence")
        .first()
    )
    if close_event is None or hasattr(close_event, "reopen_event"):
        raise ValidationError("سابقه بستن فعال و قابل بازگشایی یافت نشد.")
    if approver.pk == close_event.acted_by_id:
        raise PermissionDenied("تأییدکننده بستن نمی‌تواند همان بستن را بازگشایی کند.")
    if requested_by.pk == close_event.acted_by_id:
        raise PermissionDenied(
            "درخواست‌کننده بازگشایی باید از تأییدکننده بستن مستقل باشد."
        )
    sequence = close_event.sequence + 1
    evidence_payload = {
        "period": str(locked.pk),
        "sequence": sequence,
        "action": PeriodControlActionType.REOPEN,
        "related_close": str(close_event.pk),
        "close_evidence_hash": close_event.evidence_hash,
        "requested_by": str(requested_by.pk),
        "acted_by": str(approver.pk),
        "reason": normalized_reason,
    }
    evidence_hash = hashlib.sha256(
        json.dumps(evidence_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    event = FiscalPeriodControlEvent.objects.create(
        organization=organization,
        period=locked,
        sequence=sequence,
        action=PeriodControlActionType.REOPEN,
        requested_by=requested_by,
        acted_by=approver,
        reason=normalized_reason,
        related_close=close_event,
        evidence_hash=evidence_hash,
    )
    FiscalPeriod.objects.filter(pk=locked.pk).update(
        status=FiscalPeriodStatus.OPEN, updated_at=timezone.now()
    )
    locked.refresh_from_db()
    record_audit_event(
        action=AuditAction.ACCOUNTING_PERIOD_REOPENED,
        entity_type="accounting.FiscalPeriod",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={
            "requested_by_membership": str(requested_by.pk),
            "reason": normalized_reason,
            "control_event": str(event.pk),
            "evidence_hash": evidence_hash,
        },
    )
    return locked
