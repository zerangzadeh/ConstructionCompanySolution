"""Read-only P6 commercial timeline, comparison and exception presentation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.urls import reverse

from apps.accounts.models import User
from apps.billing.models import PayableCertificate, ProgressClaim
from apps.organizations.authorization import (
    has_business_permission,
    require_business_permission,
)
from apps.organizations.models import BusinessPermissionCode, Organization

from .contractual_services import get_contractual_records
from .models import Contract, ContractualRecordStatus
from .services import get_organization_contracts


@dataclass(frozen=True)
class CommercialTimelineEvent:
    occurred_on: date | None
    sequence: int
    source: str
    title: str
    status: str
    detail_url: str


@dataclass(frozen=True)
class CommercialComparisonRow:
    source: str
    reference: str
    status: str
    requested_amount: Decimal | None
    approved_amount: Decimal | None
    requested_eot_days: int | None
    approved_eot_days: int | None
    currency_code: str
    detail_url: str


@dataclass(frozen=True)
class CommercialException:
    category: str
    reference: str
    detail: str
    detail_url: str


@dataclass(frozen=True)
class CommercialEvidenceItem:
    record_reference: str
    label: str
    source_type: str
    source_id: str
    detail_url: str


@dataclass(frozen=True)
class CommercialReview:
    contract: Contract
    timeline: tuple[CommercialTimelineEvent, ...]
    comparison_rows: tuple[CommercialComparisonRow, ...]
    evidence: tuple[CommercialEvidenceItem, ...]
    exceptions: tuple[CommercialException, ...]
    unavailable_sources: tuple[str, ...]


def _require_review_access(*, organization: Organization, actor: User, contract: Contract) -> None:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.CONTRACTUAL_RECORDS_VIEW,
        project=contract.project,
        message="اجازه مشاهده مرور تجاری قرارداد را ندارید.",
    )


def _can_view(*, organization: Organization, actor: User, permission, project) -> bool:
    return has_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        project=project,
    )


def get_commercial_review(
    *, organization: Organization, actor: User, contract_id
) -> CommercialReview:
    """Return existing P6 evidence only; never derive authority or mutate sources."""

    try:
        contract = get_organization_contracts(user=actor, organization=organization).get(
            pk=contract_id
        )
    except Contract.DoesNotExist as exc:
        raise PermissionDenied("قرارداد قابل مشاهده نیست.") from exc
    _require_review_access(organization=organization, actor=actor, contract=contract)
    records = tuple(
        get_contractual_records(actor=actor, organization=organization)
        .filter(contract=contract)
        .prefetch_related("evidence_links")
    )
    timeline: list[CommercialTimelineEvent] = []
    comparison: list[CommercialComparisonRow] = []
    exceptions: list[CommercialException] = []
    evidence_items: list[CommercialEvidenceItem] = []
    for record in records:
        detail_url = reverse("contracts:contractual_detail", kwargs={"record_id": record.pk})
        occurred_on = record.notice_date or (
            record.approved_at.date() if record.approved_at else record.created_at.date()
        )
        timeline.append(
            CommercialTimelineEvent(
                occurred_on, 20, record.get_kind_display(), record.title, record.status, detail_url
            )
        )
        comparison.append(
            CommercialComparisonRow(
                source=record.get_kind_display(),
                reference=record.record_number,
                status=record.status,
                requested_amount=record.requested_amount,
                approved_amount=record.approved_amount,
                requested_eot_days=record.requested_eot_days,
                approved_eot_days=record.approved_eot_days,
                currency_code="—",
                detail_url=detail_url,
            )
        )
        links = tuple(record.evidence_links.all())
        for link in links:
            source_name, source = next(
                (name, getattr(link, name))
                for name in (
                    "document_version",
                    "project_control_item",
                    "project_change_proposal",
                    "schedule_revision",
                    "progress_record",
                    "payable_measurement",
                )
                if getattr(link, name) is not None
            )
            evidence_items.append(
                CommercialEvidenceItem(
                    record.record_number,
                    link.label,
                    source_name,
                    str(source.pk),
                    detail_url,
                )
            )
        if not links:
            exceptions.append(
                CommercialException("شاهد", record.record_number, "پیوند شاهد ثبت نشده است.", detail_url)
            )
        if record.status in {
            ContractualRecordStatus.RETURNED,
            ContractualRecordStatus.WITHDRAWN,
            ContractualRecordStatus.CANCELLED,
            ContractualRecordStatus.SUPERSEDED,
        }:
            exceptions.append(
                CommercialException("وضعیت", record.record_number, record.get_status_display(), detail_url)
            )

    unavailable: list[str] = []
    if _can_view(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.CLAIMS_VIEW,
        project=contract.project,
    ):
        claims = ProgressClaim.objects.filter(
            organization=organization, project=contract.project, contract=contract
        ).order_by("period_end", "claim_number", "revision_number")
        for claim in claims:
            detail_url = reverse("billing:claim_detail", kwargs={"claim_id": claim.pk})
            timeline.append(
                CommercialTimelineEvent(
                    claim.approved_at.date() if claim.approved_at else claim.period_end,
                    30,
                    "صورت‌وضعیت دریافتنی",
                    f"صورت‌وضعیت {claim.claim_number} / نسخه {claim.revision_number}",
                    claim.status,
                    detail_url,
                )
            )
            comparison.append(
                CommercialComparisonRow(
                    "صورت‌وضعیت دریافتنی",
                    f"{claim.claim_number}/{claim.revision_number}",
                    claim.status,
                    claim.gross_amount,
                    claim.net_amount,
                    None,
                    None,
                    claim.currency_code,
                    detail_url,
                )
            )
    else:
        unavailable.append("صورت‌وضعیت‌های دریافتنی")

    if _can_view(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PAYABLE_CERTIFICATES_VIEW,
        project=contract.project,
    ):
        certificates = PayableCertificate.objects.filter(
            organization=organization, project=contract.project, contract=contract
        ).order_by("period_end", "certificate_number", "revision_number")
        for certificate in certificates:
            detail_url = reverse(
                "billing:payable_certificate_detail", kwargs={"certificate_id": certificate.pk}
            )
            timeline.append(
                CommercialTimelineEvent(
                    certificate.approved_at.date()
                    if certificate.approved_at
                    else certificate.period_end,
                    40,
                    "گواهی پرداخت پیمان جزء",
                    f"گواهی {certificate.certificate_number} / نسخه {certificate.revision_number}",
                    certificate.status,
                    detail_url,
                )
            )
            comparison.append(
                CommercialComparisonRow(
                    "گواهی پرداخت پیمان جزء",
                    f"{certificate.certificate_number}/{certificate.revision_number}",
                    certificate.status,
                    certificate.gross_amount,
                    certificate.net_amount,
                    None,
                    None,
                    certificate.currency_code,
                    detail_url,
                )
            )
    else:
        unavailable.append("گواهی‌های پرداخت پیمان جزء")

    return CommercialReview(
        contract=contract,
        timeline=tuple(sorted(timeline, key=lambda item: (item.occurred_on or date.min, item.sequence, item.title))),
        comparison_rows=tuple(comparison),
        evidence=tuple(evidence_items),
        exceptions=tuple(exceptions),
        unavailable_sources=tuple(unavailable),
    )
