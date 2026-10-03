"""Dormant, explicit financial handoffs for approved receivable claims."""

from __future__ import annotations

from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.organizations.models import Organization
from apps.subledgers.models import ObligationDirection
from apps.subledgers.services import (
    ObligationSourceSnapshot,
    register_source_resolver,
    registered_source_kinds,
)

from .models import ProgressClaim, ProgressClaimCorrectionKind

PROGRESS_CLAIM_SOURCE_KIND = "billing.progress_claim.v1"
PROGRESS_CLAIM_POSTING_EVENT_KIND = "claim_approved"


def resolve_progress_claim_obligation_source(
    organization: Organization,
    source_uuid: UUID,
    source_version: int,
    source_line_key: str,
) -> ObligationSourceSnapshot:
    """Resolve one active approved claim without creating downstream records."""

    if source_line_key:
        raise ValidationError("منبع AR صورت‌وضعیت در سطح سند ثبت می‌شود.")
    try:
        claim = (
            ProgressClaim.objects.select_related(
                "project",
                "contract__party",
                "party_identity_snapshot",
                "baseline",
                "contract_term_version",
                "regulatory_rule_version",
            )
            .get(pk=source_uuid, organization=organization)
        )
    except ProgressClaim.DoesNotExist as exc:
        raise PermissionDenied("منبع صورت‌وضعیت متعلق به این Tenant نیست.") from exc
    if claim.revision_number != source_version:
        raise ValidationError("نسخه منبع صورت‌وضعیت با درخواست AR هم‌خوان نیست.")
    if claim.status != "approved" or claim.approved_at is None:
        raise ValidationError("فقط صورت‌وضعیت تأییدشده فعال قابل شناسایی در AR است.")
    if claim.correction_kind == ProgressClaimCorrectionKind.CANCELLATION:
        raise ValidationError("سند ابطال تعهد دریافتنی ایجاد نمی‌کند.")
    if claim.net_amount <= 0 or claim.currency_code != "IRR" or claim.due_date is None:
        raise ValidationError("مبلغ مثبت و ارز IRR برای تعهد دریافتنی الزامی است.")
    identity = claim.party_identity_snapshot
    snapshot = {
        "claim_id": str(claim.pk),
        "claim_number": claim.claim_number,
        "revision_number": claim.revision_number,
        "correction_kind": claim.correction_kind,
        "corrects_claim_id": str(claim.corrects_id) if claim.corrects_id else None,
        "period_start": claim.period_start.isoformat(),
        "period_end": claim.period_end.isoformat(),
        "measurement_cutoff": claim.measurement_cutoff.isoformat(),
        "baseline_id": str(claim.baseline_id),
        "baseline_version": claim.baseline.version,
        "contract_term_version_id": str(claim.contract_term_version_id),
        "regulatory_rule_version_id": str(claim.regulatory_rule_version_id),
        "party_identity_snapshot_id": str(claim.party_identity_snapshot_id),
        "currency": claim.currency_code,
        "gross_amount": str(claim.gross_amount),
        "adjustment_amount": str(claim.adjustment_amount),
        "net_amount": str(claim.net_amount),
        "calculation": claim.calculation_snapshot,
        "submission": claim.submission_snapshot,
        "approved_at": claim.approved_at.isoformat(),
        "due_date": claim.due_date.isoformat(),
        "approved_by_id": str(claim.approved_by_id),
        "approval_reason": claim.approval_reason,
    }
    recognized_on = timezone.localdate(claim.approved_at)
    return ObligationSourceSnapshot(
        source_kind=PROGRESS_CLAIM_SOURCE_KIND,
        source_uuid=claim.pk,
        source_version=claim.revision_number,
        source_line_key="",
        source_status=claim.status,
        direction=ObligationDirection.RECEIVABLE,
        amount=claim.net_amount,
        currency=claim.currency_code,
        recognized_on=recognized_on,
        due_date=claim.due_date,
        party_id=identity.party_id,
        party_name=identity.legal_name or identity.display_name,
        party_tax_identifier=identity.tax_identifier,
        project_id=claim.project_id,
        contract_id=claim.contract_id,
        source_snapshot=snapshot,
    )


def register_progress_claim_financial_handoffs() -> None:
    """Register the source resolver once; recognition remains an explicit action."""

    if PROGRESS_CLAIM_SOURCE_KIND not in registered_source_kinds():
        register_source_resolver(
            PROGRESS_CLAIM_SOURCE_KIND, resolve_progress_claim_obligation_source
        )
