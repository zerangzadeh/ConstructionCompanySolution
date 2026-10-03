"""Dormant AP and Accounting handoffs for approved payable certificates."""

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

from .models import (
    PayableCertificate,
    PayableCertificateCorrectionKind,
    PayableCertificateStatus,
)

PAYABLE_CERTIFICATE_SOURCE_KIND = "billing.payable_certificate.v1"
PAYABLE_CERTIFICATE_POSTING_EVENT_KIND = "certificate_approved"


def resolve_payable_certificate_obligation_source(
    organization: Organization,
    source_uuid: UUID,
    source_version: int,
    source_line_key: str,
) -> ObligationSourceSnapshot:
    if source_line_key:
        raise ValidationError("منبع AP گواهی پرداخت در سطح سند ثبت می‌شود.")
    try:
        certificate = PayableCertificate.objects.select_related(
            "project",
            "contract__party",
            "contract_term_version",
            "party_identity_snapshot",
        ).get(pk=source_uuid, organization=organization)
    except PayableCertificate.DoesNotExist as exc:
        raise PermissionDenied("منبع گواهی پرداخت متعلق به این Tenant نیست.") from exc
    if certificate.revision_number != source_version:
        raise ValidationError("نسخه منبع گواهی پرداخت با درخواست AP هم‌خوان نیست.")
    if (
        certificate.status != PayableCertificateStatus.APPROVED
        or certificate.approved_at is None
    ):
        raise ValidationError("فقط گواهی پرداخت تأییدشده فعال قابل شناسایی در AP است.")
    if certificate.correction_kind == PayableCertificateCorrectionKind.CANCELLATION:
        raise ValidationError("سند ابطال تعهد پرداختنی ایجاد نمی‌کند.")
    if (
        certificate.net_amount <= 0
        or certificate.currency_code != "IRR"
        or certificate.due_date is None
    ):
        raise ValidationError("مبلغ مثبت، ارز IRR و سررسید برای تعهد AP الزامی است.")
    identity = certificate.party_identity_snapshot
    snapshot = {
        "certificate_id": str(certificate.pk),
        "certificate_number": certificate.certificate_number,
        "revision_number": certificate.revision_number,
        "correction_kind": certificate.correction_kind,
        "corrects_certificate_id": (
            str(certificate.corrects_id) if certificate.corrects_id else None
        ),
        "period_start": certificate.period_start.isoformat(),
        "period_end": certificate.period_end.isoformat(),
        "measurement_cutoff": certificate.measurement_cutoff.isoformat(),
        "contract_term_version_id": str(certificate.contract_term_version_id),
        "party_identity_snapshot_id": str(certificate.party_identity_snapshot_id),
        "currency": certificate.currency_code,
        "gross_amount": str(certificate.gross_amount),
        "adjustment_amount": str(certificate.adjustment_amount),
        "net_amount": str(certificate.net_amount),
        "calculation": certificate.calculation_snapshot,
        "submission": certificate.submission_snapshot,
        "approved_at": certificate.approved_at.isoformat(),
        "due_date": certificate.due_date.isoformat(),
        "approved_by_id": str(certificate.approved_by_id),
        "approval_reason": certificate.approval_reason,
    }
    return ObligationSourceSnapshot(
        source_kind=PAYABLE_CERTIFICATE_SOURCE_KIND,
        source_uuid=certificate.pk,
        source_version=certificate.revision_number,
        source_line_key="",
        source_status=certificate.status,
        direction=ObligationDirection.PAYABLE,
        amount=certificate.net_amount,
        currency=certificate.currency_code,
        recognized_on=timezone.localdate(certificate.approved_at),
        due_date=certificate.due_date,
        party_id=identity.party_id,
        party_name=identity.legal_name or identity.display_name,
        party_tax_identifier=identity.tax_identifier,
        project_id=certificate.project_id,
        contract_id=certificate.contract_id,
        source_snapshot=snapshot,
    )


def register_payable_certificate_financial_handoffs() -> None:
    if PAYABLE_CERTIFICATE_SOURCE_KIND not in registered_source_kinds():
        register_source_resolver(
            PAYABLE_CERTIFICATE_SOURCE_KIND,
            resolve_payable_certificate_obligation_source,
        )
