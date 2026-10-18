"""SPEC-002 source-specific L2 drafts; no new posting rule or financial fallback."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import DatabaseError, transaction

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization
from apps.projects.models import Project, ProjectSite

from .models import Account, FiscalPeriod, JournalEntry, JournalKind, JournalLine
from .recognition_models import (
    RecognitionMappingApproval,
    RecognitionMappingVersion,
    SourceRecognitionDraft,
)
from .recognition_registry import RecognitionRequest, resolve_recognition_owner
from .recognition_sources import (
    DRAFT_EVENT,
    DRAFT_REVERSAL_EVENT,
    FAMILIES,
    SourceEvidence,
    digest,
    read_source,
    validate_mapping_assignments,
)
from .services import _journal_payload_hash


def _require(organization, actor, permission):
    return require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        message="اختیار صریح شناسایی حسابداری لازم است.",
    )


def _lock(organization):
    return Organization.objects.select_for_update().get(pk=organization.pk)


@transaction.atomic
def prepare_recognition_mapping(
    *,
    organization: Organization,
    actor: User,
    source_family: str,
    source_event: str,
    effective_from: date,
    account_assignments: dict,
    evidence_reference: str,
) -> RecognitionMappingVersion:
    organization = _lock(organization)
    membership = _require(organization, actor, P.ACCOUNTING_RECOGNITION_MAPPINGS_MANAGE)
    versions = RecognitionMappingVersion.objects.filter(
        organization=organization,
        source_family=source_family,
        source_event=source_event,
    )
    version = (
        versions.order_by("-version").values_list("version", flat=True).first() or 0
    ) + 1
    mapping = RecognitionMappingVersion.objects.create(
        organization=organization,
        source_family=source_family,
        source_event=source_event,
        version=version,
        effective_from=effective_from,
        account_assignments=account_assignments,
        evidence_reference=evidence_reference.strip(),
        prepared_by=membership,
    )
    _audit(
        organization,
        actor,
        AuditAction.ACCOUNTING_RECOGNITION_MAPPING_PREPARED,
        mapping.pk,
        {"family": source_family, "event": source_event, "version": version},
    )
    return mapping


@transaction.atomic
def approve_recognition_mapping(
    *,
    organization: Organization,
    actor: User,
    mapping: RecognitionMappingVersion,
    reason: str,
) -> RecognitionMappingApproval:
    organization = _lock(organization)
    membership = _require(
        organization, actor, P.ACCOUNTING_RECOGNITION_MAPPINGS_APPROVE
    )
    mapping = RecognitionMappingVersion.objects.get(
        pk=mapping.pk, organization=organization
    )
    validate_mapping_assignments(mapping)
    existing = RecognitionMappingApproval.objects.filter(
        mapping=mapping, organization=organization
    ).first()
    if existing:
        if (
            existing.approved_by_id == membership.pk
            and existing.reason == reason.strip()
        ):
            return existing
        raise ValidationError("پذیرش نگاشت پیش‌تر ثبت شده است.")
    approved = RecognitionMappingVersion.objects.filter(
        organization=organization,
        source_family=mapping.source_family,
        source_event=mapping.source_event,
        approval__isnull=False,
    )
    if (
        approved.filter(effective_from__gte=mapping.effective_from).exists()
        or approved.filter(version__gte=mapping.version).exists()
    ):
        raise ValidationError("پذیرش نسخه باید صریح و آینده‌نگر پس از نسخه قبلی باشد.")
    approval = RecognitionMappingApproval.objects.create(
        organization=organization,
        mapping=mapping,
        approved_by=membership,
        reason=reason.strip(),
    )
    _audit(
        organization,
        actor,
        AuditAction.ACCOUNTING_RECOGNITION_MAPPING_APPROVED,
        mapping.pk,
        {"version": mapping.version, "reason": reason.strip()},
    )
    return approval


def _audit(organization, actor, action, identity, metadata):
    record_audit_event(
        organization=organization,
        actor=actor,
        action=action,
        entity_type="accounting.SourceRecognitionDraft",
        entity_id=identity,
        metadata=metadata,
    )


def _policy(organization, source: SourceEvidence):
    family, occurrence, recognition_type, owner, _ = FAMILIES[source.kind]
    # Immutable event UUID is the occurrence. Native source revisions/fingerprints
    # remain in the effect's version reference and full immutable snapshot.
    return resolve_recognition_owner(
        request=RecognitionRequest(
            organization.pk,
            organization.pk,
            family,
            occurrence,
            source.identity,
            1,
            recognition_type,
            owner,
            True,
        )
    )


def _prior(organization, source):
    if not source.previous_id:
        return None
    prior = SourceRecognitionDraft.objects.filter(
        organization=organization,
        source_kind=source.kind,
        source_uuid=source.previous_id,
        is_reversal=False,
    ).first()
    if prior is None:
        raise ValidationError("تحویل معتبر منبع پیشین برای اصلاح/برگشت لازم است.")
    if not source.reversal and not prior.successors.filter(is_reversal=True).exists():
        raise ValidationError("برگشت صریح رخداد قبلی پیش از جایگزینی لازم است.")
    return prior


def _mapped_rows(source, mapping):
    validate_mapping_assignments(mapping)
    rows = []
    for item in source.rows:
        amount = Decimal(item["amount"])
        if amount == 0:
            continue
        pair = mapping.account_assignments.get(item["key"])
        if pair is None:
            raise ValidationError(
                "نگاشت صریح جزء منبع موجود نیست؛ نگاشت جایگزین مجاز نیست."
            )
        debit_id, credit_id = pair["debit"], pair["credit"]
        if amount < 0:
            debit_id, credit_id = credit_id, debit_id
        for account_id, side in ((debit_id, "debit"), (credit_id, "credit")):
            rows.append(
                {
                    **item,
                    "account_id": account_id,
                    "debit": str(abs(amount) if side == "debit" else Decimal(0)),
                    "credit": str(abs(amount) if side == "credit" else Decimal(0)),
                }
            )
    if not rows:
        raise ValidationError("منبع بدون مبلغ غیرصفر خروجی حسابداری ندارد.")
    return rows


def _journal_rows(journal):
    return [
        {
            "source_line_uuid": str(line.source_line_uuid),
            "account_id": str(line.account_id),
            "debit": str(line.debit),
            "credit": str(line.credit),
            "project_id": str(line.project_id) if line.project_id else None,
            "site_id": str(line.site_id) if line.site_id else None,
            "wbs_node_id": str(line.wbs_node_id) if line.wbs_node_id else None,
            "party_id": str(line.party_id) if line.party_id else None,
        }
        for line in journal.lines.order_by("line_number")
    ]


def _target_matches(effect):
    journal = effect.journal
    if (
        journal.organization_id != effect.organization_id
        or journal.source_kind != f"recognition.{effect.source_kind}"
        or journal.source_uuid != effect.source_uuid
        or journal.source_version != 1
        or journal.source_key
        != f"L2:{effect.source_kind}:{effect.source_uuid}:{effect.source_event}"
        or journal.event_kind
        != (DRAFT_REVERSAL_EVENT if effect.is_reversal else DRAFT_EVENT)
        or journal.kind != JournalKind.OPERATIONAL
        or journal.status != "draft"
        or journal.currency != effect.source_snapshot["currency"]
        or journal.document_date.isoformat() != effect.source_snapshot["occurred_on"]
        or journal.reconciliation_reference != effect.source_sha256
        or journal.evidence_reference
        != f"SPEC-002;mapping:{effect.mapping_id}:v{effect.mapping.version}"
    ):
        return False
    actual = _journal_rows(effect.journal)
    expected = effect.target_snapshot
    if not expected or expected[0].get("journal_sha256") != _journal_payload_hash(
        journal
    ):
        return False
    fields = (
        "source_line_uuid",
        "account_id",
        "project_id",
        "site_id",
        "wbs_node_id",
        "party_id",
    )

    return len(actual) == len(expected) and all(
        all(a[k] == b[k] for k in fields)
        and Decimal(a["debit"]) == Decimal(b["debit"])
        and Decimal(a["credit"]) == Decimal(b["credit"])
        for a, b in zip(actual, expected, strict=True)
    )


def _reversal_conserves(source, previous):
    def grouped(rows):
        result = {}
        for row in rows:
            context = row.get("context", {})
            key = tuple(
                row.get(field)
                for field in ("key", "project_id", "site_id", "wbs_node_id", "party_id")
            ) + tuple(
                context.get(field)
                for field in ("asset_id", "cost_center_id", "employee_id")
            )
            result[key] = result.get(key, Decimal(0)) + Decimal(row["amount"])
        return result

    old, new = grouped(previous.source_snapshot["rows"]), grouped(source.rows)
    if source.kind in {"payroll", "depreciation"}:
        return new == {key: -amount for key, amount in old.items()}
    return new == old


@transaction.atomic
def prepare_source_recognition(
    *,
    organization: Organization,
    actor: User,
    source_kind: str,
    source_id: UUID,
    accounting_date: date | None = None,
) -> SourceRecognitionDraft:
    organization = _lock(organization)
    membership = _require(organization, actor, P.ACCOUNTING_RECOGNITION_PREPARE)
    source = read_source(
        organization=organization,
        actor=actor,
        kind=source_kind,
        identity=source_id,
        permission=P.ACCOUNTING_RECOGNITION_PREPARE,
    )
    resolution = _policy(organization, source)
    snapshot = source.snapshot()
    sha = digest(snapshot)
    existing = (
        SourceRecognitionDraft.objects.filter(
            organization=organization,
            source_kind=source_kind,
            source_uuid=source_id,
            source_event=source.event,
        )
        .select_related("journal", "mapping")
        .first()
    )
    if existing:
        if (
            existing.source_sha256 != sha
            or not _target_matches(existing)
            or (
                accounting_date is not None
                and existing.journal.accounting_date != accounting_date
            )
        ):
            raise ValidationError("محتوای منبع/هدف تکرار با شواهد قبلی یکسان نیست.")
        return existing
    previous = _prior(organization, source)
    family = resolution.policy.source_family
    if source.reversal:
        if not _target_matches(previous):
            raise ValidationError("هدف پیشین با شواهد محفوظ تطبیق ندارد.")
        mapping = previous.mapping
        # Validate source reversal conservation before emitting inverse target rows.
        if not _reversal_conserves(source, previous):
            raise ValidationError("مبلغ برگشت منبع با رخداد قبلی برابر نیست.")
        rows = [
            {**row, "debit": row["credit"], "credit": row["debit"]}
            for row in previous.target_snapshot
        ]
    else:
        mapping = (
            RecognitionMappingVersion.objects.filter(
                organization=organization,
                source_family=family,
                source_event=source.event,
                effective_from__lte=source.occurred_on,
                approval__isnull=False,
            )
            .order_by("-effective_from", "-version")
            .first()
        )
        if mapping is None:
            raise ValidationError("نگاشت پذیرفته‌شده و مؤثر حسابداری موجود نیست.")
        rows = _mapped_rows(source, mapping)
    if source.currency != organization.settings.currency or source.currency != "IRR":
        raise ValidationError("ارز منبع و حسابداری سازگار نیست.")
    requested_date = accounting_date or source.occurred_on
    periods = FiscalPeriod.objects.select_for_update().filter(
        organization=organization,
        status="open",
        is_adjustment=False,
        starts_on__lte=requested_date,
        ends_on__gte=requested_date,
    )
    if periods.count() != 1:
        raise ValidationError("یک دوره مالی باز و صریح لازم است.")
    _require(organization, actor, P.ACCOUNTING_JOURNALS_PREPARE)
    for row in rows:
        project = (
            Project.objects.get(pk=row["project_id"], organization=organization)
            if row["project_id"]
            else None
        )
        site = (
            ProjectSite.objects.get(pk=row["site_id"], organization=organization)
            if row["site_id"]
            else None
        )
        require_business_permission(
            user=actor,
            organization=organization,
            permission=P.ACCOUNTING_JOURNALS_PREPARE,
            project=project,
            site=site,
            message="محدوده تهیه سند منبع لازم است.",
        )
    journal = JournalEntry.objects.create(
        organization=organization,
        period=periods.get(),
        kind=JournalKind.OPERATIONAL,
        document_date=source.occurred_on,
        accounting_date=requested_date,
        currency=source.currency,
        description=f"{family}: {source.identity}",
        source_key=f"L2:{source_kind}:{source.identity}:{source.event}",
        source_kind=f"recognition.{source_kind}",
        source_uuid=source.identity,
        source_version=1,
        event_kind=DRAFT_REVERSAL_EVENT if source.reversal else DRAFT_EVENT,
        occurrence_id=source.identity,
        prepared_by=membership,
        evidence_reference=f"SPEC-002;mapping:{mapping.pk}:v{mapping.version}",
        reconciliation_reference=f"{sha}",
    )
    for number, row in enumerate(rows, 1):
        # FK model validation enforces tenant/project/site/WBS/party consistency.
        account = Account.objects.select_for_update().get(
            pk=row["account_id"],
            organization=organization,
            is_posting=True,
            archived_at__isnull=True,
        )
        JournalLine.objects.create(
            organization=organization,
            journal=journal,
            account=account,
            line_number=number,
            debit=Decimal(row["debit"]),
            credit=Decimal(row["credit"]),
            source_line_uuid=row["source_line_uuid"],
            project_id=row["project_id"],
            site_id=row["site_id"],
            wbs_node_id=row["wbs_node_id"],
            party_id=row["party_id"],
        )
    journal_sha256 = _journal_payload_hash(journal)
    rows = [{**row, "journal_sha256": journal_sha256} for row in rows]
    effect = SourceRecognitionDraft.objects.create(
        organization=organization,
        source_kind=source_kind,
        source_uuid=source.identity,
        source_event=source.event,
        source_version_reference=source.version,
        source_snapshot=snapshot,
        source_sha256=sha,
        mapping=mapping,
        journal=journal,
        predecessor=previous,
        is_reversal=source.reversal,
        target_snapshot=rows,
        created_by=membership,
    )
    _audit(
        organization,
        actor,
        AuditAction.ACCOUNTING_SOURCE_RECOGNIZED,
        effect.pk,
        {
            **resolution.audit_metadata(),
            "native_source_version": source.version,
            "source_sha256": sha,
            "mapping_id": str(mapping.pk),
            "mapping_version": mapping.version,
            "journal_id": str(journal.pk),
            "predecessor_id": str(previous.pk) if previous else None,
            "is_reversal": source.reversal,
            "target_status": "draft",
        },
    )
    return effect


def attempt_source_recognition(
    *,
    organization: Organization,
    actor: User,
    source_kind: str,
    source_id: UUID,
    accounting_date: date | None = None,
) -> SourceRecognitionDraft | None:
    """Savepoint failure preserves finalized source and explicit retry/error evidence."""
    try:
        return prepare_source_recognition(
            organization=organization,
            actor=actor,
            source_kind=source_kind,
            source_id=source_id,
            accounting_date=accounting_date,
        )
    except (
        ValidationError,
        PermissionDenied,
        ObjectDoesNotExist,
        DatabaseError,
    ) as exc:
        # No exception text/PII or arbitrary database detail is copied into audit.
        _audit(
            organization,
            actor,
            AuditAction.ACCOUNTING_SOURCE_RECOGNITION_FAILED,
            source_id,
            {
                "source_kind": source_kind,
                "source_id": str(source_id),
                "failure_class": type(exc).__name__,
                "retry_required": True,
            },
        )
        return None


@transaction.atomic
def reconcile_source_recognition(
    *, organization: Organization, actor: User, effect: SourceRecognitionDraft
) -> dict:
    organization = _lock(organization)
    _require(organization, actor, P.ACCOUNTING_RECOGNITION_VIEW)
    effect = SourceRecognitionDraft.objects.select_related("journal", "mapping").get(
        pk=effect.pk, organization=organization
    )
    source = read_source(
        organization=organization,
        actor=actor,
        kind=effect.source_kind,
        identity=effect.source_uuid,
        permission=P.ACCOUNTING_RECOGNITION_VIEW,
        historical_event=effect.source_event,
    )
    source_matches = digest(source.snapshot()) == effect.source_sha256
    target_matches = _target_matches(effect)
    result = {
        "effect_id": str(effect.pk),
        "source_id": str(effect.source_uuid),
        "source_version_reference": effect.source_version_reference,
        "source_sha256": effect.source_sha256,
        "journal_id": str(effect.journal_id),
        "journal_status": effect.journal.status,
        "mapping_id": str(effect.mapping_id),
        "mapping_version": effect.mapping.version,
        "source_matches": source_matches,
        "target_matches": target_matches,
        "predecessor_id": str(effect.predecessor_id) if effect.predecessor_id else None,
        "successor_ids": [
            str(pk) for pk in effect.successors.values_list("pk", flat=True)
        ],
        "is_reversal": effect.is_reversal,
        "status": "matched" if source_matches and target_matches else "exception",
    }
    _audit(
        organization, actor, AuditAction.ACCOUNTING_SOURCE_RECONCILED, effect.pk, result
    )
    return result
