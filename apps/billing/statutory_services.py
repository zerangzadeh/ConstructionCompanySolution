from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from hashlib import sha256
from typing import Protocol
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max, QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission, scope_queryset
from apps.organizations.models import (
    BusinessPermissionCode,
    Organization,
    PlatformPolicyVersion,
)
from apps.organizations.policy_services import (
    resolve_effective_platform_regulatory_policy,
)
from apps.organizations.policy_specs import (
    CONTRACTOR_COMPLIANCE_REGULATORY_POLICY_CODE,
    TAXPAYER_INVOICE_REGULATORY_POLICY_CODE,
)

from .models import (
    ClaimAdjustmentType,
    ComplianceEvidenceStatus,
    ContractorComplianceAssessment,
    PayableCertificate,
    PayableCertificateStatus,
    ProgressClaim,
    ProgressClaimCorrectionKind,
    StatutoryRecordKind,
    StatutoryRecordStatus,
    StatutorySubmissionEvidence,
    StatutorySubmissionResolution,
    StatutorySubmissionStatus,
    SubmissionResolutionAction,
    TaxpayerInvoice,
)


def _require(*, actor, organization, permission, project=None):
    return require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        project=project,
        message="اجازه انجام عملیات مقرراتی را ندارید.",
    )


def _resolve_reviewed_policy(
    *, organization: Organization, code: str, consumer: str, on_date: date
) -> PlatformPolicyVersion:
    if not organization.is_active:
        raise PermissionDenied("Tenant فعال نیست.")
    return resolve_effective_platform_regulatory_policy(
        code=code, consumer=consumer, on_date=on_date
    )


def models_q_effective_to(on_date: date):
    from django.db.models import Q

    return Q(policy_version__effective_to__isnull=True) | Q(
        policy_version__effective_to__gt=on_date
    )


def _decimal_rate(value: object) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError("نرخ سیاست Decimal معتبر نیست.") from exc
    if not parsed.is_finite() or parsed < 0 or parsed > 100:
        raise ValidationError("نرخ سیاست خارج از دامنه مجاز است.")
    return parsed


def _taxpayer_internal_facts(
    *, invoice_id, claim: ProgressClaim, kind: str, tax_code: str, taxable, tax, total
) -> dict[str, object]:
    return {
        "taxpayer_invoice_id": str(invoice_id),
        "document_kind": kind,
        "source_claim_id": str(claim.pk),
        "source_claim_number": claim.claim_number,
        "source_claim_revision": claim.revision_number,
        "contract_number": claim.contract.contract_number,
        "project_code": claim.project.code,
        "party_tax_identifier": claim.party_identity_snapshot.tax_identifier,
        "currency_code": claim.currency_code,
        "taxable_amount": str(taxable),
        "tax_amount": str(tax),
        "total_amount": str(total),
        "tax_code": tax_code,
        "source_approved_at": claim.approved_at.isoformat(),
    }


def _mapped_payload(*, parameters: dict[str, object], facts: dict[str, object]) -> dict:
    mapping = parameters["field_mapping"]
    unknown = sorted(set(mapping.values()) - set(facts))
    if unknown:
        raise ValidationError(
            f"نگاشت policy به داده‌های ثبت‌نشده اشاره دارد: {', '.join(unknown)}"
        )
    payload = {external: facts[internal] for external, internal in mapping.items()}
    missing = [
        field
        for field in parameters["required_fields"]
        if field not in payload or payload[field] in (None, "", [], {})
    ]
    if missing:
        raise ValidationError(
            f"preflight به علت فیلد الزامی فاقد مقدار متوقف شد: {', '.join(missing)}"
        )
    return payload


@transaction.atomic
def create_taxpayer_invoice(
    *,
    organization: Organization,
    actor: User,
    source_claim: ProgressClaim,
    record_kind: str,
    reason: str,
    corrects: TaxpayerInvoice | None = None,
) -> TaxpayerInvoice:
    try:
        claim = (
            ProgressClaim.objects.select_for_update(of=("self",))
            .select_related("project", "contract", "party_identity_snapshot")
            .get(pk=source_claim.pk, organization=organization)
        )
    except ProgressClaim.DoesNotExist as exc:
        raise PermissionDenied("صورت‌وضعیت منبع متعلق به این Tenant نیست.") from exc
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.TAXPAYER_INVOICES_PREPARE,
        project=claim.project,
    )
    if claim.status != "approved" or not claim.approved_at:
        raise ValidationError("فقط revision تأییدشده صورت‌وضعیت منبع صورتحساب است.")
    kind_by_claim = {
        ProgressClaimCorrectionKind.ORDINARY: StatutoryRecordKind.ORIGINAL,
        ProgressClaimCorrectionKind.REPLACEMENT: StatutoryRecordKind.CORRECTION,
        ProgressClaimCorrectionKind.CANCELLATION: StatutoryRecordKind.CANCELLATION,
    }
    if record_kind != kind_by_claim[claim.correction_kind]:
        raise ValidationError(
            "نوع صورتحساب باید با lineage صورت‌وضعیت تأییدشده منطبق باشد."
        )
    locked_corrects = None
    if record_kind == StatutoryRecordKind.ORIGINAL:
        if corrects is not None:
            raise ValidationError("صورتحساب اصلی سابقه اصلاح ندارد.")
        series_id = None
        version_number = 1
    else:
        if corrects is None:
            raise ValidationError("صورتحساب اصلاحی/ابطالی باید به نسخه قبلی متصل باشد.")
        try:
            locked_corrects = TaxpayerInvoice.objects.select_for_update().get(
                pk=corrects.pk, organization=organization
            )
        except TaxpayerInvoice.DoesNotExist as exc:
            raise PermissionDenied("صورتحساب پیشین متعلق به این Tenant نیست.") from exc
        if (
            locked_corrects.status != StatutoryRecordStatus.APPROVED
            or claim.corrects_id != locked_corrects.source_claim_id
        ):
            raise ValidationError("lineage اصلاح تجاری و صورتحساب با هم منطبق نیست.")
        series_id = locked_corrects.series_id
        version_number = locked_corrects.version + 1
    policy = _resolve_reviewed_policy(
        organization=organization,
        code=TAXPAYER_INVOICE_REGULATORY_POLICY_CODE,
        consumer="billing.taxpayer_invoice.prepare",
        on_date=claim.approved_at.date(),
    )
    tax_adjustment = claim.adjustments.filter(
        adjustment_type=ClaimAdjustmentType.TAX
    ).first()
    taxable = tax_adjustment.base_amount_snapshot if tax_adjustment else Decimal(0)
    tax = tax_adjustment.amount if tax_adjustment else Decimal(0)
    total = taxable + tax
    if record_kind == StatutoryRecordKind.CANCELLATION:
        taxable = tax = total = Decimal(0)
    invoice = TaxpayerInvoice(
        organization=organization,
        project=claim.project,
        contract=claim.contract,
        source_claim=claim,
        party_identity_snapshot=claim.party_identity_snapshot,
        policy_version=policy,
        version=version_number,
        record_kind=record_kind,
        corrects=locked_corrects,
        reason=reason,
        schema_identifier=policy.parameters["schema_identifier"],
        tax_code=policy.parameters["tax_code"],
        currency_code=claim.currency_code,
        taxable_amount=taxable,
        tax_amount=tax,
        total_amount=total,
        created_by=actor,
        updated_by=actor,
    )
    if series_id is not None:
        invoice.series_id = series_id
    facts = _taxpayer_internal_facts(
        invoice_id=invoice.pk,
        claim=claim,
        kind=record_kind,
        tax_code=invoice.tax_code,
        taxable=taxable,
        tax=tax,
        total=total,
    )
    invoice.payload_snapshot = _mapped_payload(
        parameters=policy.parameters, facts=facts
    )
    invoice.preflight_snapshot = {
        "passed": True,
        "schema_identifier": invoice.schema_identifier,
        "policy_version_id": str(policy.pk),
        "required_fields": policy.parameters["required_fields"],
    }
    invoice.save()
    record_audit_event(
        action=AuditAction.TAXPAYER_INVOICE_CREATED,
        entity_type="billing.TaxpayerInvoice",
        entity_id=invoice.pk,
        organization=organization,
        actor=actor,
        metadata={
            "source_claim_id": str(claim.pk),
            "record_kind": record_kind,
            "policy_version_id": str(policy.pk),
        },
    )
    return invoice


@transaction.atomic
def create_contractor_compliance_assessment(
    *,
    organization: Organization,
    actor: User,
    source_certificate: PayableCertificate,
    clearance_evidence=None,
) -> ContractorComplianceAssessment:
    try:
        certificate = (
            PayableCertificate.objects.select_for_update(of=("self",))
            .select_related("project", "contract", "party_identity_snapshot")
            .get(pk=source_certificate.pk, organization=organization)
        )
    except PayableCertificate.DoesNotExist as exc:
        raise PermissionDenied("گواهی پرداخت منبع متعلق به این Tenant نیست.") from exc
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.CONTRACTOR_COMPLIANCE_PREPARE,
        project=certificate.project,
    )
    if certificate.status != PayableCertificateStatus.APPROVED:
        raise ValidationError("فقط گواهی پرداخت تأییدشده قابل ارزیابی است.")
    if ContractorComplianceAssessment.objects.filter(
        source_certificate=certificate
    ).exists():
        raise ValidationError(
            "برای این revision گواهی پرداخت قبلاً ارزیابی ثبت شده است."
        )
    policy = _resolve_reviewed_policy(
        organization=organization,
        code=CONTRACTOR_COMPLIANCE_REGULATORY_POLICY_CODE,
        consumer="billing.contractor_compliance.calculate",
        on_date=certificate.approved_at.date(),
    )
    parameters = policy.parameters
    basis = (
        certificate.gross_amount
        if parameters["deduction_basis"] == "gross"
        else certificate.net_amount
    )
    rate = _decimal_rate(parameters["deduction_rate"])
    deduction = (basis * rate / Decimal(100)).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )
    evidence = None
    if clearance_evidence is not None:
        evidence = certificate.contract.compliance_evidence.filter(
            pk=clearance_evidence.pk,
            organization=organization,
            evidence_kind="clearance",
            status=ComplianceEvidenceStatus.APPROVED,
            effective_from__lte=certificate.period_end,
        ).first()
        if evidence is None or (
            evidence.expires_on and evidence.expires_on < certificate.period_end
        ):
            raise ValidationError("مفاصاحساب برای قرارداد و دوره ارزیابی معتبر نیست.")
    if parameters["clearance_required"] and evidence is None:
        raise ValidationError("سیاست بررسی‌شده برای این دوره مفاصاحساب معتبر می‌خواهد.")
    assessment = ContractorComplianceAssessment.objects.create(
        organization=organization,
        project=certificate.project,
        contract=certificate.contract,
        source_certificate=certificate,
        party_identity_snapshot=certificate.party_identity_snapshot,
        policy_version=policy,
        clearance_evidence=evidence,
        period_start=certificate.period_start,
        period_end=certificate.period_end,
        basis_amount=basis,
        deduction_rate=rate,
        deduction_amount=deduction,
        currency_code=certificate.currency_code,
        clearance_required=parameters["clearance_required"],
        calculation_snapshot={
            "policy_version_id": str(policy.pk),
            "deduction_basis": parameters["deduction_basis"],
            "basis_amount": str(basis),
            "deduction_rate": str(rate),
            "deduction_amount": str(deduction),
            "clearance_evidence_id": str(evidence.pk) if evidence else None,
            "schema_identifier": parameters["schema_identifier"],
        },
        created_by=actor,
        updated_by=actor,
    )
    record_audit_event(
        action=AuditAction.CONTRACTOR_COMPLIANCE_CREATED,
        entity_type="billing.ContractorComplianceAssessment",
        entity_id=assessment.pk,
        organization=organization,
        actor=actor,
        metadata={
            "source_certificate_id": str(certificate.pk),
            "policy_version_id": str(policy.pk),
        },
    )
    return assessment


def get_taxpayer_invoices(*, actor, organization) -> QuerySet[TaxpayerInvoice]:
    membership = _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.TAXPAYER_INVOICES_VIEW,
    )
    return scope_queryset(
        TaxpayerInvoice.objects.filter(organization=organization),
        membership=membership,
        project_lookup="project_id",
    ).select_related("project", "contract", "source_claim", "policy_version")


def get_contractor_assessments(
    *, actor, organization
) -> QuerySet[ContractorComplianceAssessment]:
    membership = _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.CONTRACTOR_COMPLIANCE_VIEW,
    )
    return scope_queryset(
        ContractorComplianceAssessment.objects.filter(organization=organization),
        membership=membership,
        project_lookup="project_id",
    ).select_related("project", "contract", "source_certificate", "policy_version")


def _target_details(target):
    if isinstance(target, TaxpayerInvoice):
        policy = target.policy_version
        return {
            "taxpayer_invoice": target,
            "contractor_assessment": None,
            "schema_identifier": target.schema_identifier,
            "provider_key": policy.parameters["provider_key"],
            "mode": policy.parameters["submission_mode"],
            "payload": target.payload_snapshot,
            "project": target.project,
        }
    if isinstance(target, ContractorComplianceAssessment):
        return {
            "taxpayer_invoice": None,
            "contractor_assessment": target,
            "schema_identifier": target.policy_version.parameters["schema_identifier"],
            "provider_key": "",
            "mode": "export_only",
            "payload": target.calculation_snapshot,
            "project": target.project,
        }
    raise TypeError("نوع هدف ارسال مقرراتی پشتیبانی نمی‌شود.")


@dataclass(frozen=True, slots=True)
class AdapterResult:
    status: str
    response_payload: dict
    provider_reference: str = ""
    error_code: str = ""
    error_message: str = ""


class StatutoryTestAdapter(Protocol):
    def submit(
        self, *, payload: dict, correlation_id: UUID, schema_identifier: str
    ) -> AdapterResult: ...


def _safe_external_payload(value: object) -> None:
    forbidden = ("credential", "password", "secret", "token", "private_key")
    if isinstance(value, dict):
        for key, nested in value.items():
            if any(part in str(key).casefold() for part in forbidden):
                raise ValidationError(
                    "ثبت credential یا secret در شاهد ارسال مجاز نیست."
                )
            _safe_external_payload(nested)
    elif isinstance(value, list):
        for nested in value:
            _safe_external_payload(nested)


@transaction.atomic
def record_statutory_submission(
    *,
    organization: Organization,
    actor: User,
    target,
    idempotency_key: str,
    correlation_id: UUID,
    adapter: StatutoryTestAdapter | None = None,
    retry_of: StatutorySubmissionEvidence | None = None,
) -> StatutorySubmissionEvidence:
    if not idempotency_key.strip():
        raise ValidationError("کلید idempotency الزامی است.")
    # Serialize retry/idempotency allocation per Tenant. This is intentionally
    # database-backed because adapters may be invoked concurrently by callers.
    Organization.objects.select_for_update(of=("self",)).get(pk=organization.pk)
    model = type(target)
    if model not in (TaxpayerInvoice, ContractorComplianceAssessment):
        raise TypeError("نوع هدف ارسال مقرراتی پشتیبانی نمی‌شود.")
    try:
        locked = model.objects.select_for_update().get(
            pk=target.pk, organization=organization
        )
    except model.DoesNotExist as exc:
        raise PermissionDenied("هدف ارسال متعلق به این Tenant نیست.") from exc
    details = _target_details(locked)
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.STATUTORY_SUBMISSIONS_EXECUTE,
        project=details["project"],
    )
    existing = StatutorySubmissionEvidence.objects.filter(
        organization=organization, idempotency_key=idempotency_key.strip()
    ).first()
    if existing:
        expected_id = locked.pk
        actual_id = existing.taxpayer_invoice_id or existing.contractor_assessment_id
        if actual_id != expected_id:
            raise ValidationError("کلید idempotency قبلاً برای هدف دیگری مصرف شده است.")
        return existing
    if locked.status != StatutoryRecordStatus.APPROVED:
        raise ValidationError("فقط سابقه تأییدشده قابل خروجی/ارسال است.")
    prior_attempts = StatutorySubmissionEvidence.objects.filter(
        taxpayer_invoice=details["taxpayer_invoice"],
        contractor_assessment=details["contractor_assessment"],
    )
    if prior_attempts.filter(
        status__in=(
            StatutorySubmissionStatus.EXPORTED,
            StatutorySubmissionStatus.ACCEPTED,
        )
    ).exists():
        raise ValidationError("برای این نسخه قبلاً خروجی/پذیرش موفق ثبت شده است.")
    if prior_attempts.exists() and retry_of is None:
        raise ValidationError("تلاش بعدی باید به تلاش ناموفق و مجوز retry متصل باشد.")
    if retry_of is not None:
        prior = (
            StatutorySubmissionEvidence.objects.select_for_update()
            .filter(pk=retry_of.pk, organization=organization)
            .first()
        )
        if (
            prior is None
            or (prior.taxpayer_invoice_id or prior.contractor_assessment_id)
            != locked.pk
            or prior.status
            not in {
                StatutorySubmissionStatus.REJECTED,
                StatutorySubmissionStatus.PROVIDER_ERROR,
            }
            or not prior.resolutions.filter(
                action=SubmissionResolutionAction.RETRY_AUTHORIZED
            ).exists()
        ):
            raise ValidationError("تلاش مجدد به خطای حل‌شده و مجوز انسانی نیاز دارد.")
    payload = details["payload"]
    _safe_external_payload(payload)
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    attempt_number = (
        prior_attempts.aggregate(value=Max("attempt_number"))["value"] or 0
    ) + 1
    if details["mode"] == "export_only":
        result = AdapterResult(
            status=StatutorySubmissionStatus.EXPORTED, response_payload={}
        )
    else:
        if adapter is None:
            raise ValidationError("حالت adapter آزمون به adapter صریح نیاز دارد.")
        try:
            result = adapter.submit(
                payload=payload,
                correlation_id=correlation_id,
                schema_identifier=details["schema_identifier"],
            )
        except (ConnectionError, RuntimeError, TimeoutError) as exc:
            result = AdapterResult(
                status=StatutorySubmissionStatus.PROVIDER_ERROR,
                response_payload={},
                error_code=type(exc).__name__,
                error_message=str(exc)[:2000],
            )
    if result.status not in StatutorySubmissionStatus.values:
        raise ValidationError("adapter وضعیت ثبت‌نشده برگرداند.")
    _safe_external_payload(result.response_payload)
    try:
        evidence = StatutorySubmissionEvidence.objects.create(
            organization=organization,
            taxpayer_invoice=details["taxpayer_invoice"],
            contractor_assessment=details["contractor_assessment"],
            retry_of=retry_of,
            attempt_number=attempt_number,
            idempotency_key=idempotency_key.strip(),
            correlation_id=correlation_id,
            schema_identifier=details["schema_identifier"],
            provider_key=details["provider_key"],
            request_payload=payload,
            request_sha256=sha256(canonical).hexdigest(),
            response_payload=result.response_payload,
            status=result.status,
            provider_reference=result.provider_reference,
            error_code=result.error_code,
            error_message=result.error_message,
            recorded_by=actor,
        )
    except IntegrityError as exc:
        raise ValidationError("تلاش تکراری یا correlation ID تکراری است.") from exc
    record_audit_event(
        action=AuditAction.STATUTORY_SUBMISSION_RECORDED,
        entity_type="billing.StatutorySubmissionEvidence",
        entity_id=evidence.pk,
        organization=organization,
        actor=actor,
        correlation_id=correlation_id,
        metadata={
            "status": evidence.status,
            "attempt_number": evidence.attempt_number,
            "request_sha256": evidence.request_sha256,
        },
    )
    return evidence


@transaction.atomic
def resolve_submission_error(
    *,
    organization: Organization,
    actor: User,
    submission: StatutorySubmissionEvidence,
    action: str,
    note: str,
    provider_reference: str = "",
) -> StatutorySubmissionResolution:
    try:
        locked = StatutorySubmissionEvidence.objects.select_for_update().get(
            pk=submission.pk, organization=organization
        )
    except StatutorySubmissionEvidence.DoesNotExist as exc:
        raise PermissionDenied("شاهد ارسال متعلق به این Tenant نیست.") from exc
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.STATUTORY_SUBMISSIONS_RESOLVE,
    )
    if locked.status not in {
        StatutorySubmissionStatus.REJECTED,
        StatutorySubmissionStatus.PROVIDER_ERROR,
    }:
        raise ValidationError("فقط خطا یا رد provider نیازمند حل انسانی است.")
    if action not in SubmissionResolutionAction.values:
        raise ValidationError("اقدام حل انسانی ثبت نشده است.")
    resolution = StatutorySubmissionResolution.objects.create(
        submission=locked,
        organization=organization,
        action=action,
        note=note,
        provider_reference=provider_reference,
        resolved_by=actor,
    )
    record_audit_event(
        action=AuditAction.STATUTORY_SUBMISSION_RESOLVED,
        entity_type="billing.StatutorySubmissionResolution",
        entity_id=resolution.pk,
        organization=organization,
        actor=actor,
        metadata={"submission_id": str(locked.pk), "action": action},
    )
    return resolution


def reconcile_taxpayer_invoice(*, actor, organization, invoice) -> dict[str, object]:
    locked = get_taxpayer_invoices(actor=actor, organization=organization).get(
        pk=invoice.pk
    )
    return {
        "invoice_id": str(locked.pk),
        "source_claim_id": str(locked.source_claim_id),
        "source_claim_status": locked.source_claim.status,
        "source_claim_net_amount": str(locked.source_claim.net_amount),
        "taxpayer_total_amount": str(locked.total_amount),
        "policy_version_id": str(locked.policy_version_id),
        "submission_evidence": [
            {
                "id": str(item.pk),
                "status": item.status,
                "correlation_id": str(item.correlation_id),
                "request_sha256": item.request_sha256,
            }
            for item in locked.submission_evidence.order_by("attempt_number")
        ],
        "financial_effect": "none",
    }


def reconcile_contractor_assessment(
    *, actor, organization, assessment
) -> dict[str, object]:
    locked = get_contractor_assessments(actor=actor, organization=organization).get(
        pk=assessment.pk
    )
    return {
        "assessment_id": str(locked.pk),
        "source_certificate_id": str(locked.source_certificate_id),
        "source_certificate_status": locked.source_certificate.status,
        "source_certificate_gross_amount": str(locked.source_certificate.gross_amount),
        "source_certificate_net_amount": str(locked.source_certificate.net_amount),
        "deduction_amount": str(locked.deduction_amount),
        "policy_version_id": str(locked.policy_version_id),
        "submission_evidence": [
            {
                "id": str(item.pk),
                "status": item.status,
                "correlation_id": str(item.correlation_id),
                "request_sha256": item.request_sha256,
            }
            for item in locked.submission_evidence.order_by("attempt_number")
        ],
        "financial_effect": "none",
    }


def submit_taxpayer_invoice(*, organization, actor, invoice):
    from .commercial_workflow import submit_commercial_record

    return submit_commercial_record(
        organization=organization, actor=actor, record=invoice
    )


def submit_contractor_assessment(*, organization, actor, assessment):
    from .commercial_workflow import submit_commercial_record

    return submit_commercial_record(
        organization=organization, actor=actor, record=assessment
    )


@transaction.atomic
def _approve_taxpayer_invoice_domain(*, organization, actor, invoice, reason):
    locked = TaxpayerInvoice.objects.select_for_update().get(
        pk=invoice.pk, organization=organization
    )
    if locked.status != StatutoryRecordStatus.SUBMITTED or not reason.strip():
        raise ValidationError("صورتحساب ارسالی و دلیل تصمیم الزامی است.")
    if locked.corrects_id:
        predecessor = TaxpayerInvoice.objects.select_for_update().get(
            pk=locked.corrects_id, organization=organization
        )
        predecessor_status = (
            StatutoryRecordStatus.CANCELLED
            if locked.record_kind == StatutoryRecordKind.CANCELLATION
            else StatutoryRecordStatus.SUPERSEDED
        )
        TaxpayerInvoice.objects.filter(pk=predecessor.pk).update(
            status=predecessor_status, updated_at=timezone.now()
        )
    locked.status = StatutoryRecordStatus.APPROVED
    locked.approved_by = actor
    locked.approved_at = timezone.now()
    locked.decision_reason = reason.strip()
    locked.updated_by = actor
    locked.save()
    record_audit_event(
        action=AuditAction.TAXPAYER_INVOICE_APPROVED,
        entity_type="billing.TaxpayerInvoice",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"reason": reason.strip()},
    )
    return locked


@transaction.atomic
def _return_taxpayer_invoice_domain(*, organization, actor, invoice, reason):
    locked = TaxpayerInvoice.objects.select_for_update().get(
        pk=invoice.pk, organization=organization
    )
    if locked.status != StatutoryRecordStatus.SUBMITTED or not reason.strip():
        raise ValidationError("صورتحساب ارسالی و دلیل بازگشت الزامی است.")
    locked.status = StatutoryRecordStatus.RETURNED
    locked.approved_by = actor
    locked.approved_at = timezone.now()
    locked.decision_reason = reason.strip()
    locked.updated_by = actor
    locked.save()
    record_audit_event(
        action=AuditAction.TAXPAYER_INVOICE_RETURNED,
        entity_type="billing.TaxpayerInvoice",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"reason": reason.strip()},
    )
    return locked


@transaction.atomic
def _approve_contractor_domain(*, organization, actor, assessment, reason):
    locked = ContractorComplianceAssessment.objects.select_for_update().get(
        pk=assessment.pk, organization=organization
    )
    if locked.status != StatutoryRecordStatus.SUBMITTED or not reason.strip():
        raise ValidationError("ارزیابی ارسالی و دلیل تصمیم الزامی است.")
    locked.status = StatutoryRecordStatus.APPROVED
    locked.approved_by = actor
    locked.approved_at = timezone.now()
    locked.decision_reason = reason.strip()
    locked.updated_by = actor
    locked.save()
    record_audit_event(
        action=AuditAction.CONTRACTOR_COMPLIANCE_APPROVED,
        entity_type="billing.ContractorComplianceAssessment",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"reason": reason.strip()},
    )
    return locked


@transaction.atomic
def _return_contractor_domain(*, organization, actor, assessment, reason):
    locked = ContractorComplianceAssessment.objects.select_for_update().get(
        pk=assessment.pk, organization=organization
    )
    if locked.status != StatutoryRecordStatus.SUBMITTED or not reason.strip():
        raise ValidationError("ارزیابی ارسالی و دلیل بازگشت الزامی است.")
    locked.status = StatutoryRecordStatus.RETURNED
    locked.approved_by = actor
    locked.approved_at = timezone.now()
    locked.decision_reason = reason.strip()
    locked.updated_by = actor
    locked.save()
    record_audit_event(
        action=AuditAction.CONTRACTOR_COMPLIANCE_RETURNED,
        entity_type="billing.ContractorComplianceAssessment",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"reason": reason.strip()},
    )
    return locked


def decide_taxpayer_invoice(*, organization, actor, invoice, approved, reason):
    from .commercial_workflow import decide_commercial_record

    return decide_commercial_record(
        organization=organization,
        actor=actor,
        record=invoice,
        approved=approved,
        reason=reason,
    )


def decide_contractor_assessment(*, organization, actor, assessment, approved, reason):
    from .commercial_workflow import decide_commercial_record

    return decide_commercial_record(
        organization=organization,
        actor=actor,
        record=assessment,
        approved=approved,
        reason=reason,
    )
