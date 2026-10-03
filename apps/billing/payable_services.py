"""Application services for subcontract measurement and payable certification."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, QuerySet, Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.contracts.models import (
    Contract,
    ContractAmendment,
    ContractAmendmentStatus,
    ContractDirection,
    ContractItem,
    ContractStatus,
    ContractTermVersion,
    ContractTermVersionStatus,
    ContractType,
)
from apps.organizations.authorization import (
    require_business_permission,
    scope_queryset,
)
from apps.organizations.models import (
    SUPPORTED_BASE_CURRENCY,
    BusinessPermissionCode,
    Organization,
    OrganizationSettings,
)
from apps.parties.models import PartyIdentitySnapshot

from .models import (
    MONEY_QUANTUM,
    QUANTITY_QUANTUM,
    PayableCertificate,
    PayableCertificateAdjustment,
    PayableCertificateAdjustmentType,
    PayableCertificateCorrectionKind,
    PayableCertificateItem,
    PayableCertificateStatus,
    PayableMeasurement,
    PayableMeasurementStatus,
)


def _decimal(
    value: Decimal | int | str,
    *,
    quantum: Decimal,
    label: str,
    positive: bool = False,
) -> Decimal:
    if isinstance(value, (bool, float)):
        raise ValidationError(f"{label} باید با Decimal وارد شود.")
    try:
        parsed = Decimal(value)
    except Exception as exc:
        raise ValidationError(f"{label} معتبر نیست.") from exc
    if not parsed.is_finite() or parsed != parsed.quantize(quantum):
        raise ValidationError(f"دقت {label} معتبر نیست.")
    if positive and parsed <= 0:
        raise ValidationError(f"{label} باید مثبت باشد.")
    return parsed


def _require(
    *,
    actor: User,
    organization: Organization,
    permission: BusinessPermissionCode,
    project: object,
):
    return require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        project=project,
        message="اجازه انجام عملیات گواهی پرداخت پیمان جزء را ندارید.",
    )


def _locked_subcontract(
    *, organization: Organization, contract: Contract, require_active: bool = True
) -> Contract:
    try:
        locked = (
            Contract.objects.select_for_update(of=("self",))
            .select_related("project", "party")
            .get(pk=contract.pk, organization=organization, deleted_at__isnull=True)
        )
    except Contract.DoesNotExist as exc:
        raise PermissionDenied("پیمان جزء متعلق به این سازمان نیست.") from exc
    if (
        locked.direction != ContractDirection.PAYABLE
        or locked.contract_type != ContractType.SUBCONTRACT
        or locked.party_id is None
    ):
        raise ValidationError(
            "گواهی پرداخت فقط برای پیمان جزء پرداختنی با طرف مرجع مجاز است."
        )
    if require_active and locked.status != ContractStatus.ACTIVE:
        raise ValidationError("عملیات جدید فقط برای پیمان جزء فعال مجاز است.")
    return locked


def get_payable_measurements(
    *, actor: User, organization: Organization
) -> QuerySet[PayableMeasurement]:
    membership = _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.PAYABLE_MEASUREMENTS_VIEW,
        project=None,
    )
    return scope_queryset(
        PayableMeasurement.objects.filter(organization=organization),
        membership=membership,
        project_lookup="project_id",
    ).select_related("project", "contract", "contract_item")


def get_payable_certificates(
    *, actor: User, organization: Organization
) -> QuerySet[PayableCertificate]:
    membership = _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.PAYABLE_CERTIFICATES_VIEW,
        project=None,
    )
    return scope_queryset(
        PayableCertificate.objects.filter(organization=organization),
        membership=membership,
        project_lookup="project_id",
    ).select_related(
        "project", "contract", "contract_term_version", "party_identity_snapshot"
    )


@transaction.atomic
def create_payable_measurement(
    *,
    organization: Organization,
    actor: User,
    contract_item: ContractItem,
    measured_on: date,
    period_quantity: Decimal,
    cumulative_quantity: Decimal,
    evidence_reference: str,
) -> PayableMeasurement:
    try:
        item = (
            ContractItem.objects.select_for_update(of=("self",))
            .select_related("contract__project", "contract__party")
            .get(pk=contract_item.pk, organization=organization)
        )
    except ContractItem.DoesNotExist as exc:
        raise PermissionDenied("ردیف پیمان متعلق به این سازمان نیست.") from exc
    contract = _locked_subcontract(organization=organization, contract=item.contract)
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.PAYABLE_MEASUREMENTS_RECORD,
        project=contract.project,
    )
    period = _decimal(
        period_quantity,
        quantum=QUANTITY_QUANTUM,
        label="مقدار دوره",
        positive=True,
    )
    cumulative = _decimal(
        cumulative_quantity,
        quantum=QUANTITY_QUANTUM,
        label="مقدار تجمعی",
        positive=True,
    )
    latest = (
        PayableMeasurement.objects.select_for_update(of=("self",))
        .filter(
            organization=organization,
            contract_item=item,
            status=PayableMeasurementStatus.VERIFIED,
        )
        .order_by("-measured_on", "-verified_at")
        .first()
    )
    previous = latest.cumulative_quantity if latest else Decimal(0)
    if latest and measured_on <= latest.measured_on:
        raise ValidationError(
            "تاریخ اندازه‌گیری جدید باید پس از آخرین شاهد تأییدشده باشد."
        )
    if cumulative != previous + period or cumulative > item.quantity:
        raise ValidationError(
            "مقدار دوره و تجمعی با سابقه و سقف ردیف پیمان سازگار نیست."
        )
    measurement = PayableMeasurement.objects.create(
        organization=organization,
        project=contract.project,
        contract=contract,
        contract_item=item,
        measured_on=measured_on,
        period_quantity=period,
        cumulative_quantity=cumulative,
        evidence_reference=evidence_reference.strip(),
        created_by=actor,
    )
    record_audit_event(
        action=AuditAction.PAYABLE_MEASUREMENT_RECORDED,
        entity_type="billing.PayableMeasurement",
        entity_id=measurement.pk,
        organization=organization,
        actor=actor,
        metadata={
            "contract_id": str(contract.pk),
            "stable_line_id": str(item.pk),
            "cumulative_quantity": str(cumulative),
        },
    )
    return measurement


@transaction.atomic
def submit_payable_measurement(
    *, organization: Organization, actor: User, measurement: PayableMeasurement
) -> PayableMeasurement:
    try:
        locked = (
            PayableMeasurement.objects.select_for_update(of=("self",))
            .select_related("project")
            .get(pk=measurement.pk, organization=organization)
        )
    except PayableMeasurement.DoesNotExist as exc:
        raise PermissionDenied("اندازه‌گیری متعلق به این سازمان نیست.") from exc
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.PAYABLE_MEASUREMENTS_RECORD,
        project=locked.project,
    )
    if locked.status != PayableMeasurementStatus.DRAFT:
        raise ValidationError("فقط اندازه‌گیری پیش‌نویس قابل ارسال است.")
    locked.status = PayableMeasurementStatus.SUBMITTED
    locked.submitted_by = actor
    locked.submitted_at = timezone.now()
    locked.save(update_fields=["status", "submitted_by", "submitted_at", "updated_at"])
    record_audit_event(
        action=AuditAction.PAYABLE_MEASUREMENT_SUBMITTED,
        entity_type="billing.PayableMeasurement",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"contract_id": str(locked.contract_id)},
    )
    return locked


@transaction.atomic
def decide_payable_measurement(
    *,
    organization: Organization,
    actor: User,
    measurement: PayableMeasurement,
    approved: bool,
    reason: str,
) -> PayableMeasurement:
    try:
        locked = (
            PayableMeasurement.objects.select_for_update(of=("self",))
            .select_related("project", "contract_item")
            .get(pk=measurement.pk, organization=organization)
        )
    except PayableMeasurement.DoesNotExist as exc:
        raise PermissionDenied("اندازه‌گیری متعلق به این سازمان نیست.") from exc
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.PAYABLE_MEASUREMENTS_VERIFY,
        project=locked.project,
    )
    if locked.status != PayableMeasurementStatus.SUBMITTED:
        raise ValidationError("فقط اندازه‌گیری ارسال‌شده قابل تصمیم‌گیری است.")
    if locked.created_by_id == actor.pk or locked.submitted_by_id == actor.pk:
        raise PermissionDenied(
            "ثبت‌کننده یا ارسال‌کننده نمی‌تواند همان اندازه‌گیری را تأیید کند."
        )
    if not reason.strip():
        raise ValidationError("دلیل تصمیم اندازه‌گیری الزامی است.")
    if approved:
        previous = (
            PayableMeasurement.objects.select_for_update(of=("self",))
            .filter(
                organization=organization,
                contract_item=locked.contract_item,
                status=PayableMeasurementStatus.VERIFIED,
            )
            .order_by("-measured_on", "-verified_at")
            .first()
        )
        prior_quantity = previous.cumulative_quantity if previous else Decimal(0)
        if previous and locked.measured_on <= previous.measured_on:
            raise ValidationError("یک شاهد جدیدتر برای این ردیف تأیید شده است.")
        if locked.cumulative_quantity != prior_quantity + locked.period_quantity:
            raise ValidationError(
                "توالی تجمعی اندازه‌گیری در زمان تأیید تغییر کرده است."
            )
        locked.status = PayableMeasurementStatus.VERIFIED
    else:
        locked.status = PayableMeasurementStatus.REJECTED
    locked.verified_by = actor
    locked.verified_at = timezone.now()
    locked.decision_reason = reason.strip()
    locked.save(
        update_fields=[
            "status",
            "verified_by",
            "verified_at",
            "decision_reason",
            "updated_at",
        ]
    )
    record_audit_event(
        action=(
            AuditAction.PAYABLE_MEASUREMENT_VERIFIED
            if approved
            else AuditAction.PAYABLE_MEASUREMENT_REJECTED
        ),
        entity_type="billing.PayableMeasurement",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"reason": locked.decision_reason},
    )
    return locked


def _term_for_cutoff(
    *, organization: Organization, contract: Contract, cutoff: date
) -> ContractTermVersion:
    term = (
        ContractTermVersion.objects.select_for_update(of=("self",))
        .filter(
            organization=organization,
            contract=contract,
            status__in=(
                ContractTermVersionStatus.APPROVED,
                ContractTermVersionStatus.SUPERSEDED,
            ),
            effective_from__lte=cutoff,
        )
        .order_by("-effective_from", "-version")
        .first()
    )
    if term is None:
        raise ValidationError("نسخه شرایط پرداختنی تأییدشده و مؤثر یافت نشد.")
    return term


def _identity_snapshot(contract: Contract) -> PartyIdentitySnapshot:
    snapshot = contract.party.identity_snapshots.order_by("-sequence").first()
    if snapshot is None:
        raise ValidationError("طرف پیمان جزء تصویر هویت قابل استناد ندارد.")
    return snapshot


@transaction.atomic
def create_payable_certificate(
    *,
    organization: Organization,
    actor: User,
    contract: Contract,
    period_start: date,
    period_end: date,
    measurement_cutoff: date,
) -> PayableCertificate:
    locked_contract = _locked_subcontract(organization=organization, contract=contract)
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.PAYABLE_CERTIFICATES_CREATE,
        project=locked_contract.project,
    )
    if (
        period_end < period_start
        or not period_start <= measurement_cutoff <= period_end
    ):
        raise ValidationError("دوره و تاریخ قطع گواهی پرداخت معتبر نیست.")
    certificates = PayableCertificate.objects.select_for_update(of=("self",)).filter(
        organization=organization, contract=locked_contract
    )
    if certificates.filter(
        revision_number=1,
        period_start__lte=period_end,
        period_end__gte=period_start,
    ).exists():
        raise ValidationError("دوره گواهی پرداخت با دوره موجود هم‌پوشانی دارد.")
    number = certificates.aggregate(value=Max("certificate_number"))["value"] or 0
    term = _term_for_cutoff(
        organization=organization, contract=locked_contract, cutoff=measurement_cutoff
    )
    settings, _ = OrganizationSettings.objects.get_or_create(
        organization=organization, defaults={"currency": SUPPORTED_BASE_CURRENCY}
    )
    certificate = PayableCertificate.objects.create(
        organization=organization,
        project=locked_contract.project,
        contract=locked_contract,
        contract_term_version=term,
        party_identity_snapshot=_identity_snapshot(locked_contract),
        certificate_number=number + 1,
        period_start=period_start,
        period_end=period_end,
        measurement_cutoff=measurement_cutoff,
        currency_code=settings.currency,
        created_by=actor,
        updated_by=actor,
    )
    record_audit_event(
        action=AuditAction.PAYABLE_CERTIFICATE_CREATED,
        entity_type="billing.PayableCertificate",
        entity_id=certificate.pk,
        organization=organization,
        actor=actor,
        metadata={
            "contract_id": str(locked_contract.pk),
            "certificate_number": certificate.certificate_number,
        },
    )
    return recalculate_payable_certificate(
        organization=organization, actor=actor, certificate=certificate
    )


def _effective_contract_ceiling(contract: Contract) -> Decimal:
    amendments = ContractAmendment.objects.select_for_update(of=("self",)).filter(
        contract=contract, status=ContractAmendmentStatus.APPROVED
    ).aggregate(total=Sum("value_change"))["total"] or Decimal(0)
    ceiling = contract.contract_value + amendments
    if ceiling < 0:
        raise ValidationError("سقف مؤثر پیمان جزء منفی است.")
    return ceiling


@transaction.atomic
def recalculate_payable_certificate(
    *, organization: Organization, actor: User, certificate: PayableCertificate
) -> PayableCertificate:
    try:
        locked = (
            PayableCertificate.objects.select_for_update(of=("self",))
            .select_related("project", "contract", "contract_term_version")
            .get(pk=certificate.pk, organization=organization)
        )
    except PayableCertificate.DoesNotExist as exc:
        raise PermissionDenied("گواهی پرداخت متعلق به این سازمان نیست.") from exc
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.PAYABLE_CERTIFICATES_REVISE,
        project=locked.project,
    )
    if locked.status != PayableCertificateStatus.DRAFT:
        raise ValidationError("فقط گواهی پرداخت پیش‌نویس قابل محاسبه مجدد است.")
    term = locked.contract_term_version
    if (
        term.contract_id != locked.contract_id
        or term.status
        not in {
            ContractTermVersionStatus.APPROVED,
            ContractTermVersionStatus.SUPERSEDED,
        }
        or term.effective_from > locked.measurement_cutoff
    ):
        raise ValidationError("نسخه شرایط پین‌شده برای گواهی پرداخت معتبر نیست.")
    PayableCertificateItem.objects.filter(certificate=locked).delete()
    PayableCertificateAdjustment.objects.filter(
        certificate=locked,
        adjustment_type__in=(
            PayableCertificateAdjustmentType.RETENTION,
            PayableCertificateAdjustmentType.ADVANCE_RECOVERY,
        ),
    ).delete()
    prior = list(
        PayableCertificate.objects.select_for_update(of=("self",))
        .filter(
            organization=organization,
            contract=locked.contract,
            status=PayableCertificateStatus.APPROVED,
        )
        .exclude(certificate_number=locked.certificate_number)
        .order_by("certificate_number", "revision_number")
    )
    prior_ids = [item.pk for item in prior]
    prior_gross = sum((item.gross_amount for item in prior), Decimal(0))
    ceiling = _effective_contract_ceiling(locked.contract)
    if prior_gross > ceiling:
        raise ValidationError("گواهی‌های پیشین از سقف مؤثر پیمان بیشتر هستند.")

    if locked.correction_kind == PayableCertificateCorrectionKind.CANCELLATION:
        PayableCertificateAdjustment.objects.filter(certificate=locked).delete()
        locked.gross_amount = Decimal(0)
        locked.adjustment_amount = Decimal(0)
        locked.net_amount = Decimal(0)
        locked.calculation_snapshot = {
            "calculation_order": ["linked_cancellation", "zero_final_amount"],
            "corrects_certificate_id": str(locked.corrects_id),
            "contract_ceiling": str(ceiling),
            "gross_final": "0",
            "adjustment_final": "0",
            "net_final": "0",
        }
        locked.updated_by = actor
        locked.save(
            update_fields=[
                "gross_amount",
                "adjustment_amount",
                "net_amount",
                "calculation_snapshot",
                "updated_by",
                "updated_at",
            ]
        )
        return locked

    prior_by_line = {
        row["stable_line_id"]: row["quantity"] or Decimal(0)
        for row in PayableCertificateItem.objects.filter(certificate_id__in=prior_ids)
        .values("stable_line_id")
        .annotate(quantity=Sum("current_quantity"))
    }
    measurements = (
        PayableMeasurement.objects.select_for_update(of=("self",))
        .filter(
            organization=organization,
            contract=locked.contract,
            status=PayableMeasurementStatus.VERIFIED,
            measured_on__lte=locked.measurement_cutoff,
        )
        .select_related("contract_item")
        .order_by("contract_item_id", "measured_on", "verified_at")
    )
    latest: dict[object, PayableMeasurement] = {}
    for measurement in measurements:
        latest[measurement.contract_item_id] = measurement
    gross = Decimal(0)
    line_evidence: list[dict[str, str]] = []
    for item in ContractItem.objects.filter(contract=locked.contract).order_by(
        "sort_order", "created_at"
    ):
        measurement = latest.get(item.pk)
        if measurement is None:
            continue
        previous = prior_by_line.get(item.pk, Decimal(0))
        if measurement.cumulative_quantity < previous:
            raise ValidationError("مقدار تجمعی شاهد از مقدار قبلاً گواهی‌شده کمتر است.")
        current = measurement.cumulative_quantity - previous
        if current == 0:
            continue
        amount = (current * item.unit_price).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        PayableCertificateItem.objects.create(
            certificate=locked,
            contract_item=item,
            measurement=measurement,
            stable_line_id=item.pk,
            previous_cumulative_quantity=previous,
            current_quantity=current,
            new_cumulative_quantity=measurement.cumulative_quantity,
            unit_rate_snapshot=item.unit_price,
            current_amount=amount,
        )
        gross += amount
        line_evidence.append(
            {
                "stable_line_id": str(item.pk),
                "measurement_id": str(measurement.pk),
                "evidence_reference": measurement.evidence_reference,
                "previous_certified_quantity": str(previous),
                "current_quantity": str(current),
                "new_cumulative_quantity": str(measurement.cumulative_quantity),
                "unit_rate": str(item.unit_price),
                "current_amount": str(amount),
            }
        )
    if prior_gross + gross > ceiling:
        raise ValidationError("جمع تجمعی گواهی‌شده از سقف مؤثر پیمان بیشتر است.")

    def add_capped(adjustment_type: str, rate: Decimal, cap: Decimal) -> None:
        consumed = abs(
            PayableCertificateAdjustment.objects.filter(
                certificate_id__in=prior_ids,
                adjustment_type=adjustment_type,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal(0)
        )
        remaining = max(cap - consumed, Decimal(0))
        amount = min(gross * rate / Decimal(100), remaining).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        if amount:
            PayableCertificateAdjustment.objects.create(
                certificate=locked,
                adjustment_type=adjustment_type,
                description=f"contract_term.{adjustment_type}",
                sequence=(
                    1
                    if adjustment_type == PayableCertificateAdjustmentType.RETENTION
                    else 2
                ),
                rate_snapshot=rate,
                base_amount_snapshot=gross,
                amount=-amount,
            )

    add_capped(
        PayableCertificateAdjustmentType.RETENTION,
        term.retention_rate,
        term.retention_cap,
    )
    add_capped(
        PayableCertificateAdjustmentType.ADVANCE_RECOVERY,
        term.advance_recovery_rate,
        term.advance_recovery_cap,
    )
    adjustments = list(
        PayableCertificateAdjustment.objects.filter(certificate=locked).order_by(
            "sequence", "created_at"
        )
    )
    adjustment_total = sum((item.amount for item in adjustments), Decimal(0))
    net = gross + adjustment_total
    if net < 0:
        raise ValidationError("کسور گواهی پرداخت از مبلغ ناخالص بیشتر است.")
    gross_final = gross.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    net_final = net.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    locked.gross_amount = gross_final
    locked.adjustment_amount = net_final - gross_final
    locked.net_amount = net_final
    locked.calculation_snapshot = {
        "calculation_order": [
            "measured_work_gross",
            "retention",
            "advance_recovery",
            "evidence_back_charges",
            "final_currency_rounding",
        ],
        "currency": locked.currency_code,
        "contract_value_snapshot": str(locked.contract.contract_value),
        "contract_ceiling": str(ceiling),
        "prior_approved_certificate_ids": [str(item.pk) for item in prior],
        "prior_approved_gross": str(prior_gross),
        "remaining_ceiling_before_certificate": str(ceiling - prior_gross),
        "contract_term_version_id": str(term.pk),
        "contract_term_version": term.version,
        "payment_due_days": term.payment_due_days,
        "retention_rate": str(term.retention_rate),
        "retention_cap": str(term.retention_cap),
        "advance_recovery_rate": str(term.advance_recovery_rate),
        "advance_recovery_cap": str(term.advance_recovery_cap),
        "gross_intermediate": str(gross),
        "adjustment_intermediate": str(adjustment_total),
        "gross_final": str(gross_final),
        "adjustment_final": str(locked.adjustment_amount),
        "net_final": str(net_final),
        "line_calculations": line_evidence,
        "adjustments": [
            {
                "type": item.adjustment_type,
                "amount": str(item.amount),
                "evidence": item.evidence,
            }
            for item in adjustments
        ],
    }
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "gross_amount",
            "adjustment_amount",
            "net_amount",
            "calculation_snapshot",
            "updated_by",
            "updated_at",
        ]
    )
    return locked


@transaction.atomic
def add_payable_back_charge(
    *,
    organization: Organization,
    actor: User,
    certificate: PayableCertificate,
    amount: Decimal,
    description: str,
    evidence: str,
) -> PayableCertificateAdjustment:
    try:
        locked = (
            PayableCertificate.objects.select_for_update(of=("self",))
            .select_related("project")
            .get(pk=certificate.pk, organization=organization)
        )
    except PayableCertificate.DoesNotExist as exc:
        raise PermissionDenied("گواهی پرداخت متعلق به این سازمان نیست.") from exc
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.PAYABLE_CERTIFICATES_REVISE,
        project=locked.project,
    )
    if locked.status != PayableCertificateStatus.DRAFT:
        raise ValidationError("کسورات فقط به گواهی پیش‌نویس افزوده می‌شوند.")
    value = _decimal(amount, quantum=MONEY_QUANTUM, label="مبلغ کسر", positive=True)
    if not description.strip() or not evidence.strip():
        raise ValidationError("شرح و مرجع شواهد کسر هزینه الزامی است.")
    sequence = (
        PayableCertificateAdjustment.objects.filter(
            certificate=locked, sequence__gte=100
        ).aggregate(value=Max("sequence"))["value"]
        or 99
    ) + 1
    adjustment = PayableCertificateAdjustment.objects.create(
        certificate=locked,
        adjustment_type=PayableCertificateAdjustmentType.BACK_CHARGE,
        description=description.strip(),
        sequence=sequence,
        amount=-value,
        evidence=evidence.strip(),
    )
    recalculate_payable_certificate(
        organization=organization, actor=actor, certificate=locked
    )
    adjustment.refresh_from_db()
    return adjustment


def _downstream_clear(
    *, organization: Organization, certificate: PayableCertificate
) -> None:
    from apps.subledgers.models import Obligation

    from .payable_handoffs import PAYABLE_CERTIFICATE_SOURCE_KIND

    if Obligation.objects.filter(
        organization=organization,
        source_kind=PAYABLE_CERTIFICATE_SOURCE_KIND,
        source_uuid=certificate.pk,
        source_version=certificate.revision_number,
    ).exists():
        raise ValidationError(
            "تعهد AP شناسایی‌شده باید پیش از اصلاح از مسیر مجاز حل شود."
        )


@transaction.atomic
def create_payable_certificate_correction(
    *,
    organization: Organization,
    actor: User,
    certificate: PayableCertificate,
    correction_kind: str,
    reason: str,
) -> PayableCertificate:
    if correction_kind not in {
        PayableCertificateCorrectionKind.REPLACEMENT,
        PayableCertificateCorrectionKind.CANCELLATION,
    }:
        raise ValidationError("نوع اصلاح گواهی پرداخت معتبر نیست.")
    try:
        locked = (
            PayableCertificate.objects.select_for_update(of=("self",))
            .select_related(
                "project",
                "contract",
                "contract_term_version",
                "party_identity_snapshot",
            )
            .get(pk=certificate.pk, organization=organization)
        )
    except PayableCertificate.DoesNotExist as exc:
        raise PermissionDenied("گواهی پرداخت متعلق به این سازمان نیست.") from exc
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.PAYABLE_CERTIFICATES_REVISE,
        project=locked.project,
    )
    if locked.status != PayableCertificateStatus.APPROVED:
        raise ValidationError("فقط گواهی پرداخت فعال و تأییدشده قابل اصلاح است.")
    if not reason.strip():
        raise ValidationError("دلیل اصلاح یا ابطال الزامی است.")
    _downstream_clear(organization=organization, certificate=locked)
    existing = PayableCertificate.objects.select_for_update(of=("self",)).filter(
        organization=organization,
        contract=locked.contract,
        certificate_number=locked.certificate_number,
    )
    if (
        existing.exclude(pk=locked.pk)
        .filter(
            status__in=(
                PayableCertificateStatus.DRAFT,
                PayableCertificateStatus.SUBMITTED,
                PayableCertificateStatus.APPROVED,
            )
        )
        .exists()
    ):
        raise ValidationError("برای این گواهی از قبل اصلاح فعال وجود دارد.")
    revision = (existing.aggregate(value=Max("revision_number"))["value"] or 0) + 1
    replacement = PayableCertificate.objects.create(
        organization=organization,
        project=locked.project,
        contract=locked.contract,
        contract_term_version=locked.contract_term_version,
        party_identity_snapshot=locked.party_identity_snapshot,
        certificate_number=locked.certificate_number,
        revision_number=revision,
        correction_kind=correction_kind,
        corrects=locked,
        correction_reason=reason.strip(),
        period_start=locked.period_start,
        period_end=locked.period_end,
        measurement_cutoff=locked.measurement_cutoff,
        currency_code=locked.currency_code,
        created_by=actor,
        updated_by=actor,
    )
    record_audit_event(
        action=AuditAction.PAYABLE_CERTIFICATE_CORRECTION_CREATED,
        entity_type="billing.PayableCertificate",
        entity_id=replacement.pk,
        organization=organization,
        actor=actor,
        metadata={
            "corrects_certificate_id": str(locked.pk),
            "correction_kind": correction_kind,
            "reason": reason.strip(),
        },
    )
    return recalculate_payable_certificate(
        organization=organization, actor=actor, certificate=replacement
    )


def _copy_returned_revision(
    *, organization: Organization, actor: User, certificate: PayableCertificate
) -> PayableCertificate:
    revision = PayableCertificate.objects.create(
        organization=organization,
        project=certificate.project,
        contract=certificate.contract,
        contract_term_version=certificate.contract_term_version,
        party_identity_snapshot=certificate.party_identity_snapshot,
        certificate_number=certificate.certificate_number,
        revision_number=certificate.revision_number + 1,
        correction_kind=certificate.correction_kind,
        corrects=certificate.corrects,
        correction_reason=certificate.correction_reason,
        period_start=certificate.period_start,
        period_end=certificate.period_end,
        measurement_cutoff=certificate.measurement_cutoff,
        currency_code=certificate.currency_code,
        created_by=actor,
        updated_by=actor,
    )
    for adjustment in certificate.adjustments.filter(
        adjustment_type=PayableCertificateAdjustmentType.BACK_CHARGE
    ):
        PayableCertificateAdjustment.objects.create(
            certificate=revision,
            adjustment_type=adjustment.adjustment_type,
            description=adjustment.description,
            sequence=adjustment.sequence,
            amount=adjustment.amount,
            evidence=adjustment.evidence,
        )
    return recalculate_payable_certificate(
        organization=organization, actor=actor, certificate=revision
    )


@transaction.atomic
def _approve_payable_certificate_domain(
    *,
    organization: Organization,
    actor: User,
    certificate: PayableCertificate,
    reason: str,
) -> PayableCertificate:
    try:
        locked = (
            PayableCertificate.objects.select_for_update(of=("self",))
            .select_related("contract_term_version", "corrects")
            .get(pk=certificate.pk, organization=organization)
        )
    except PayableCertificate.DoesNotExist as exc:
        raise PermissionDenied("گواهی پرداخت متعلق به این سازمان نیست.") from exc
    if locked.status != PayableCertificateStatus.SUBMITTED:
        raise ValidationError("فقط گواهی پرداخت ارسال‌شده قابل تأیید است.")
    if not reason.strip():
        raise ValidationError("دلیل تأیید گواهی پرداخت الزامی است.")
    if locked.correction_kind != PayableCertificateCorrectionKind.CANCELLATION and (
        not locked.items.exists() or locked.net_amount <= 0
    ):
        raise ValidationError("گواهی پرداخت باید ردیف و مبلغ خالص مثبت داشته باشد.")
    target = None
    target_status = None
    if locked.corrects_id:
        target = PayableCertificate.objects.select_for_update(of=("self",)).get(
            pk=locked.corrects_id, organization=organization
        )
        if target.status != PayableCertificateStatus.APPROVED:
            raise ValidationError("گواهی مرجع اصلاح دیگر فعال نیست.")
        _downstream_clear(organization=organization, certificate=target)
    now = timezone.now()
    if target is not None:
        target_status = (
            PayableCertificateStatus.CANCELLED
            if locked.correction_kind == PayableCertificateCorrectionKind.CANCELLATION
            else PayableCertificateStatus.SUPERSEDED
        )
        PayableCertificate.objects.filter(pk=target.pk).update(
            status=target_status, updated_at=now
        )
    locked.status = PayableCertificateStatus.APPROVED
    locked.approved_by = actor
    locked.approved_at = now
    locked.approval_reason = reason.strip()
    locked.due_date = timezone.localdate(
        now, timezone=ZoneInfo(organization.timezone)
    ) + timedelta(days=locked.contract_term_version.payment_due_days)
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "approval_reason",
            "due_date",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.PAYABLE_CERTIFICATE_APPROVED,
        entity_type="billing.PayableCertificate",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"reason": locked.approval_reason},
    )
    if target is not None and target_status is not None:
        record_audit_event(
            action=(
                AuditAction.PAYABLE_CERTIFICATE_CANCELLED
                if target_status == PayableCertificateStatus.CANCELLED
                else AuditAction.PAYABLE_CERTIFICATE_SUPERSEDED
            ),
            entity_type="billing.PayableCertificate",
            entity_id=target.pk,
            organization=organization,
            actor=actor,
            metadata={"replacement_id": str(locked.pk)},
        )
    return locked


@transaction.atomic
def _return_payable_certificate_domain(
    *,
    organization: Organization,
    actor: User,
    certificate: PayableCertificate,
    reason: str,
) -> PayableCertificate:
    try:
        locked = PayableCertificate.objects.select_for_update(of=("self",)).get(
            pk=certificate.pk, organization=organization
        )
    except PayableCertificate.DoesNotExist as exc:
        raise PermissionDenied("گواهی پرداخت متعلق به این سازمان نیست.") from exc
    if locked.status != PayableCertificateStatus.SUBMITTED:
        raise ValidationError("فقط گواهی پرداخت ارسال‌شده قابل بازگردانی است.")
    if not reason.strip():
        raise ValidationError("دلیل بازگردانی الزامی است.")
    revision = _copy_returned_revision(
        organization=organization, actor=actor, certificate=locked
    )
    now = timezone.now()
    locked.status = PayableCertificateStatus.RETURNED
    locked.returned_by = actor
    locked.returned_at = now
    locked.return_reason = reason.strip()
    locked.returned_revision = revision
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "status",
            "returned_by",
            "returned_at",
            "return_reason",
            "returned_revision",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.PAYABLE_CERTIFICATE_RETURNED,
        entity_type="billing.PayableCertificate",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"reason": locked.return_reason, "revision_id": str(revision.pk)},
    )
    return locked


def submit_payable_certificate(
    *, organization: Organization, actor: User, certificate: PayableCertificate
):
    from .payable_workflow import submit_payable_certificate_with_workflow

    return submit_payable_certificate_with_workflow(
        organization=organization, actor=actor, certificate=certificate
    )


def approve_payable_certificate(
    *,
    organization: Organization,
    actor: User,
    certificate: PayableCertificate,
    reason: str,
) -> PayableCertificate:
    from .payable_workflow import approve_payable_certificate_with_workflow

    return approve_payable_certificate_with_workflow(
        organization=organization,
        actor=actor,
        certificate=certificate,
        reason=reason,
    )


def return_payable_certificate(
    *,
    organization: Organization,
    actor: User,
    certificate: PayableCertificate,
    reason: str,
) -> PayableCertificate:
    from .payable_workflow import return_payable_certificate_with_workflow

    return return_payable_certificate_with_workflow(
        organization=organization,
        actor=actor,
        certificate=certificate,
        reason=reason,
    )
