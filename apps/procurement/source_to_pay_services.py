import hashlib
import json
from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission, scope_queryset
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.procurement.models import (
    GoodsReceiptItem,
    GoodsReceiptStatus,
    PurchaseOrder,
    PurchaseOrderChangeDecision,
    PurchaseOrderChangeDecisionEvidence,
    PurchaseOrderChangeLine,
    PurchaseOrderChangeRequest,
    PurchaseOrderStatus,
    PurchaseOrderVersion,
    PurchaseOrderVersionLine,
    ServiceAcceptance,
    ServiceAcceptanceItem,
    ServiceAcceptanceStatus,
)
from core.identifiers import canonicalize_upper_identifier


def _hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _lock_order(*, organization: Organization, order: PurchaseOrder) -> PurchaseOrder:
    try:
        locked = (
            PurchaseOrder.objects.select_for_update(of=("self",))
            .select_related("project", "current_version")
            .get(pk=order.pk, organization=organization)
        )
    except PurchaseOrder.DoesNotExist as exc:
        raise PermissionDenied("سفارش خرید در این Tenant یافت نشد.") from exc
    return locked


def service_acceptance_queryset(*, organization: Organization, actor):
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SERVICE_ACCEPTANCES_VIEW,
        message="اختیار مشاهده پذیرش خدمت را ندارید.",
        allow_any_scope=True,
    )
    return scope_queryset(
        ServiceAcceptance.objects.filter(organization=organization),
        membership=membership,
        project_lookup="project_id",
    )


@transaction.atomic
def request_purchase_order_change(
    *,
    organization: Organization,
    actor,
    purchase_order: PurchaseOrder,
    line_changes: dict[str, tuple[Decimal, Decimal]],
    reason: str,
    evidence: str,
    idempotency_key: str,
) -> PurchaseOrderChangeRequest:
    order = _lock_order(organization=organization, order=purchase_order)
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.PURCHASE_ORDER_CHANGES_REQUEST,
        message="اختیار درخواست تغییر سفارش خرید را ندارید.",
        project=order.project,
    )
    if order.status != PurchaseOrderStatus.ISSUED or not order.current_version_id:
        raise ValidationError("فقط سفارش صادرشده با نسخه حاکم قابل تغییر است.")
    reason = reason.strip()
    evidence = evidence.strip()
    idempotency_key = idempotency_key.strip()
    if not reason or not evidence or not idempotency_key or not line_changes:
        raise ValidationError("ردیف، دلیل، شاهد و کلید idempotency تغییر الزامی است.")
    base_lines = {
        str(line.pk): line
        for line in PurchaseOrderVersionLine.objects.select_for_update(of=("self",))
        .select_related("award_allocation")
        .filter(version=order.current_version)
    }
    if set(line_changes) - set(base_lines):
        raise PermissionDenied("ردیف تغییر متعلق به نسخه حاکم سفارش نیست.")
    payload = [
        {
            "line": key,
            "quantity": str(line_changes[key][0]),
            "unit_price": str(line_changes[key][1]),
        }
        for key in sorted(line_changes)
    ]
    fingerprint = _hash(payload)
    existing = PurchaseOrderChangeRequest.objects.filter(
        purchase_order=order, idempotency_key=idempotency_key
    ).first()
    if existing:
        if existing.payload_hash != fingerprint:
            raise ValidationError(
                "کلید idempotency تغییر با محتوای متفاوت استفاده شده است."
            )
        return existing
    request = PurchaseOrderChangeRequest.objects.create(
        organization=organization,
        purchase_order=order,
        base_version=order.current_version,
        reason=reason,
        evidence=evidence,
        requested_by=actor,
        requested_at=timezone.now(),
        idempotency_key=idempotency_key,
        payload_hash=fingerprint,
    )
    for key, (quantity, unit_price) in line_changes.items():
        if quantity <= 0 or unit_price < 0:
            raise ValidationError("مقدار مثبت و قیمت نامنفی برای تغییر الزامی است.")
        PurchaseOrderChangeLine.objects.create(
            organization=organization,
            change_request=request,
            base_line=base_lines[key],
            revised_quantity=quantity,
            revised_unit_price=unit_price,
        )
    record_audit_event(
        action="purchase_order.change_requested",
        entity_type="procurement.PurchaseOrderChangeRequest",
        entity_id=request.pk,
        organization=organization,
        actor=actor,
        metadata={"purchase_order_id": str(order.pk)},
    )
    return request


def _consumed_quantity(line: PurchaseOrderVersionLine) -> Decimal:
    goods = GoodsReceiptItem.objects.filter(
        purchase_order_item=line.source_item,
        goods_receipt__status=GoodsReceiptStatus.POSTED,
    ).aggregate(total=Sum("quantity"))["total"] or Decimal(0)
    services = ServiceAcceptanceItem.objects.filter(
        purchase_order_version_line__source_item=line.source_item,
        acceptance__status=ServiceAcceptanceStatus.ACCEPTED,
    ).aggregate(total=Sum("quantity"))["total"] or Decimal(0)
    return goods + services


@transaction.atomic
def decide_purchase_order_change(
    *,
    organization: Organization,
    actor,
    change_request: PurchaseOrderChangeRequest,
    approve: bool,
    reason: str,
) -> PurchaseOrderChangeDecisionEvidence:
    request = (
        PurchaseOrderChangeRequest.objects.select_for_update()
        .select_related("purchase_order__project", "base_version", "requested_by")
        .get(pk=change_request.pk, organization=organization)
    )
    order = _lock_order(organization=organization, order=request.purchase_order)
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.PURCHASE_ORDER_CHANGES_APPROVE,
        message="اختیار تصمیم تغییر سفارش خرید را ندارید.",
        project=order.project,
    )
    if request.requested_by_id == actor.pk:
        raise PermissionDenied("درخواست‌کننده تغییر نمی‌تواند تصمیم‌گیر آن باشد.")
    existing = PurchaseOrderChangeDecisionEvidence.objects.filter(
        change_request=request
    ).first()
    if existing:
        if (existing.decision == PurchaseOrderChangeDecision.APPROVED) != approve:
            raise ValidationError(
                "درخواست تغییر قبلاً با نتیجه دیگری تعیین تکلیف شده است."
            )
        return existing
    reason = reason.strip()
    if not reason:
        raise ValidationError("دلیل تصمیم تغییر سفارش الزامی است.")
    if (
        order.status != PurchaseOrderStatus.ISSUED
        or order.current_version_id != request.base_version_id
    ):
        raise ValidationError("نسخه پایه دیگر حاکم نیست؛ درخواست تغییر جدید لازم است.")
    resulting_version = None
    if approve:
        changes = {
            item.base_line_id: item
            for item in request.lines.select_for_update(of=("self",)).select_related(
                "base_line__award_allocation"
            )
        }
        base_lines = list(
            request.base_version.lines.select_for_update(of=("self",)).select_related(
                "source_item", "material", "unit_of_measure", "award_allocation"
            )
        )
        payload = []
        for line in base_lines:
            change = changes.get(line.pk)
            quantity = change.revised_quantity if change else line.quantity
            unit_price = change.revised_unit_price if change else line.unit_price
            if quantity < _consumed_quantity(line):
                raise ValidationError("تغییر نمی‌تواند از مقدار پذیرفته‌شده کمتر باشد.")
            if line.award_allocation_id and quantity > line.award_allocation.quantity:
                raise ValidationError("تغییر نمی‌تواند از تخصیص انتخاب منبع فراتر رود.")
            payload.append(
                {
                    "source_item": str(line.source_item_id),
                    "quantity": str(quantity),
                    "unit_price": str(unit_price),
                }
            )
        version_number = request.base_version.version_number + 1
        resulting_version = PurchaseOrderVersion.objects.create(
            organization=organization,
            purchase_order=order,
            version_number=version_number,
            source_award=request.base_version.source_award,
            supersedes=request.base_version,
            effective_at=timezone.now(),
            reason=reason,
            payload_hash=_hash(payload),
            idempotency_key=f"change:{request.pk}",
            created_by=actor,
        )
        for line in base_lines:
            change = changes.get(line.pk)
            PurchaseOrderVersionLine.objects.create(
                organization=organization,
                version=resulting_version,
                source_item=line.source_item,
                award_allocation=line.award_allocation,
                material=line.material,
                unit_of_measure=line.unit_of_measure,
                description=line.description,
                quantity=change.revised_quantity if change else line.quantity,
                unit_price=change.revised_unit_price if change else line.unit_price,
                sort_order=line.sort_order,
            )
        order.current_version = resulting_version
        order.updated_by = actor
        order.save(update_fields=["current_version", "updated_by", "updated_at"])
    decision = PurchaseOrderChangeDecisionEvidence.objects.create(
        organization=organization,
        change_request=request,
        decision=(
            PurchaseOrderChangeDecision.APPROVED
            if approve
            else PurchaseOrderChangeDecision.REJECTED
        ),
        decided_by=actor,
        decided_at=timezone.now(),
        reason=reason,
        resulting_version=resulting_version,
    )
    record_audit_event(
        action="purchase_order.change_decided",
        entity_type="procurement.PurchaseOrderChangeDecisionEvidence",
        entity_id=decision.pk,
        organization=organization,
        actor=actor,
        metadata={"approved": approve, "purchase_order_id": str(order.pk)},
    )
    return decision


@transaction.atomic
def create_service_acceptance(
    *,
    organization: Organization,
    actor,
    purchase_order: PurchaseOrder,
    acceptance_number: str,
    accepted_on: date,
    notes: str = "",
) -> ServiceAcceptance:
    order = _lock_order(organization=organization, order=purchase_order)
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SERVICE_ACCEPTANCES_CREATE,
        message="اختیار ایجاد پذیرش خدمت را ندارید.",
        project=order.project,
    )
    if order.status != PurchaseOrderStatus.ISSUED or not order.current_version_id:
        raise ValidationError("پذیرش خدمت فقط برای سفارش صادرشده نسخه‌دار مجاز است.")
    number = canonicalize_upper_identifier(acceptance_number)
    return ServiceAcceptance.objects.create(
        organization=organization,
        purchase_order=order,
        purchase_order_version=order.current_version,
        project=order.project,
        acceptance_number=number,
        accepted_on=accepted_on,
        notes=notes.strip(),
        created_by=actor,
    )


@transaction.atomic
def add_service_acceptance_item(
    *,
    organization: Organization,
    actor,
    acceptance: ServiceAcceptance,
    purchase_order_version_line: PurchaseOrderVersionLine,
    quantity: Decimal,
    evidence: str,
) -> ServiceAcceptanceItem:
    acceptance = (
        ServiceAcceptance.objects.select_for_update()
        .select_related("project")
        .get(pk=acceptance.pk, organization=organization)
    )
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SERVICE_ACCEPTANCES_CREATE,
        message="اختیار ویرایش پذیرش خدمت را ندارید.",
        project=acceptance.project,
    )
    if acceptance.status != ServiceAcceptanceStatus.DRAFT:
        raise ValidationError("فقط پذیرش خدمت پیش‌نویس قابل ویرایش است.")
    try:
        line = PurchaseOrderVersionLine.objects.select_for_update().get(
            pk=purchase_order_version_line.pk,
            version=acceptance.purchase_order_version,
            organization=organization,
        )
    except PurchaseOrderVersionLine.DoesNotExist as exc:
        raise PermissionDenied("ردیف نسخه سفارش در این پذیرش معتبر نیست.") from exc
    if quantity <= 0 or not evidence.strip():
        raise ValidationError("مقدار مثبت و شاهد پذیرش الزامی است.")
    return ServiceAcceptanceItem.objects.create(
        organization=organization,
        acceptance=acceptance,
        purchase_order_version_line=line,
        quantity=quantity,
        evidence=evidence.strip(),
    )


@transaction.atomic
def accept_service(
    *, organization: Organization, actor, acceptance: ServiceAcceptance
) -> ServiceAcceptance:
    acceptance = (
        ServiceAcceptance.objects.select_for_update()
        .select_related("project")
        .get(pk=acceptance.pk, organization=organization)
    )
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SERVICE_ACCEPTANCES_ACCEPT,
        message="اختیار نهایی‌سازی پذیرش خدمت را ندارید.",
        project=acceptance.project,
    )
    if acceptance.status != ServiceAcceptanceStatus.DRAFT:
        raise ValidationError("فقط پذیرش خدمت پیش‌نویس قابل نهایی‌سازی است.")
    items = list(
        acceptance.items.select_for_update().select_related(
            "purchase_order_version_line"
        )
    )
    if not items:
        raise ValidationError("پذیرش خدمت باید حداقل یک ردیف داشته باشد.")
    for item in items:
        previous = ServiceAcceptanceItem.objects.filter(
            purchase_order_version_line__source_item_id=(
                item.purchase_order_version_line.source_item_id
            ),
            acceptance__status=ServiceAcceptanceStatus.ACCEPTED,
        ).aggregate(total=Sum("quantity"))["total"] or Decimal(0)
        if previous + item.quantity > item.purchase_order_version_line.quantity:
            raise ValidationError("مقدار تجمعی پذیرش خدمت از سفارش بیشتر است.")
    acceptance.status = ServiceAcceptanceStatus.ACCEPTED
    acceptance.accepted_by = actor
    acceptance.accepted_at = timezone.now()
    acceptance.save(
        update_fields=["status", "accepted_by", "accepted_at", "updated_at"]
    )
    record_audit_event(
        action="service_acceptance.accepted",
        entity_type="procurement.ServiceAcceptance",
        entity_id=acceptance.pk,
        organization=organization,
        actor=actor,
        metadata={"purchase_order_id": str(acceptance.purchase_order_id)},
    )
    return acceptance


@transaction.atomic
def void_service_acceptance(
    *,
    organization: Organization,
    actor,
    acceptance: ServiceAcceptance,
    reason: str,
) -> ServiceAcceptance:
    acceptance = (
        ServiceAcceptance.objects.select_for_update()
        .select_related("project")
        .get(pk=acceptance.pk, organization=organization)
    )
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SERVICE_ACCEPTANCES_VOID,
        message="اختیار ابطال پذیرش خدمت را ندارید.",
        project=acceptance.project,
    )
    if acceptance.status != ServiceAcceptanceStatus.ACCEPTED or not reason.strip():
        raise ValidationError("فقط پذیرش نهایی با دلیل قابل ابطال است.")
    from apps.subledgers.models import SupplierInvoiceMatchLine

    if SupplierInvoiceMatchLine.objects.filter(
        invoice_line__purchase_order_version_line__service_acceptance_items__acceptance=(
            acceptance
        )
    ).exists():
        raise ValidationError(
            "پذیرش دارای صورتحساب وابسته تا اصلاح منبع قابل ابطال نیست."
        )
    acceptance.status = ServiceAcceptanceStatus.VOID
    acceptance.voided_by = actor
    acceptance.voided_at = timezone.now()
    acceptance.void_reason = reason.strip()
    acceptance.save(
        update_fields=["status", "voided_by", "voided_at", "void_reason", "updated_at"]
    )
    return acceptance
