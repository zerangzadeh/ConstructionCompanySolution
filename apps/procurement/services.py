from datetime import date, datetime
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import QuerySet, Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.materials.models import Material, UnitOfMeasure
from apps.organizations.authorization import (
    membership_has_permission,
    require_business_permission,
    scope_queryset,
)
from apps.organizations.models import (
    BusinessPermissionCode,
    Organization,
    OrganizationMembership,
)
from apps.parties.models import BusinessParty, PartyRoleType
from apps.procurement.models import (
    GoodsReceipt,
    GoodsReceiptItem,
    GoodsReceiptStatus,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
    PurchaseRequest,
    PurchaseRequestItem,
    PurchaseRequestStatus,
)
from apps.projects.models import Project
from core.identifiers import canonicalize_upper_identifier


def _validate_active_access(
    *,
    organization: Organization,
    user: User,
    permission: BusinessPermissionCode,
    allow_any_scope: bool = False,
) -> OrganizationMembership:
    return require_business_permission(
        user=user,
        organization=organization,
        permission=permission,
        message="اجازه مشاهده اطلاعات خرید این سازمان را ندارید.",
        allow_any_scope=allow_any_scope,
    )


def _require_role(
    *,
    organization: Organization,
    actor: User,
    permission: str,
    message: str,
    project: Project | None = None,
    allow_any_scope: bool = False,
) -> OrganizationMembership:
    return require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        message=message,
        project=project,
        allow_any_scope=allow_any_scope,
    )


def _has_management_access(
    actor: User, membership: OrganizationMembership | None
) -> bool:
    return bool(
        membership
        and membership_has_permission(
            membership, BusinessPermissionCode.PURCHASE_REQUESTS_APPROVE
        )
    )


def _validate_project(*, organization: Organization, project: Project) -> None:
    if project.organization_id != organization.pk or project.deleted_at is not None:
        raise PermissionDenied("پروژه متعلق به این سازمان نیست.")


def _validate_material(
    *,
    organization: Organization,
    material: Material,
    unit_of_measure: UnitOfMeasure | None = None,
) -> UnitOfMeasure:
    unit = unit_of_measure or material.unit_of_measure
    if (
        material.organization_id != organization.pk
        or unit.organization_id != organization.pk
        or material.unit_of_measure_id != unit.pk
        or not material.is_active
        or material.archived_at is not None
        or not unit.is_active
        or unit.archived_at is not None
    ):
        raise PermissionDenied(
            "مصالح و واحد اندازه‌گیری باید رکوردهای فعال این سازمان باشند."
        )
    return unit


def _validate_supplier(*, organization: Organization, supplier: BusinessParty) -> None:
    if supplier.organization_id != organization.pk or supplier.archived_at is not None:
        raise PermissionDenied("تأمین‌کننده متعلق به این سازمان نیست.")
    if not supplier.roles.filter(
        organization=organization,
        role=PartyRoleType.SUPPLIER,
        is_active=True,
    ).exists():
        raise ValueError("طرف تجاری انتخاب‌شده باید نقش فعال تأمین‌کننده داشته باشد.")


def _save_validated(instance: object, message: str) -> None:
    try:
        instance.full_clean()
        instance.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError(message) from exc


def _get_locked_request(
    *, organization: Organization, purchase_request: PurchaseRequest
) -> PurchaseRequest:
    try:
        request = PurchaseRequest.objects.select_for_update().get(
            pk=purchase_request.pk, organization=organization
        )
    except PurchaseRequest.DoesNotExist as exc:
        raise PermissionDenied("درخواست خرید در این سازمان یافت نشد.") from exc
    _validate_project(organization=organization, project=request.project)
    return request


def _get_locked_order(
    *, organization: Organization, purchase_order: PurchaseOrder
) -> PurchaseOrder:
    try:
        order = (
            PurchaseOrder.objects.select_for_update(of=("self",))
            .select_related("project", "supplier", "purchase_request")
            .get(pk=purchase_order.pk, organization=organization)
        )
    except PurchaseOrder.DoesNotExist as exc:
        raise PermissionDenied("سفارش خرید در این سازمان یافت نشد.") from exc
    _validate_project(organization=organization, project=order.project)
    return order


def _get_locked_receipt(
    *, organization: Organization, goods_receipt: GoodsReceipt
) -> GoodsReceipt:
    try:
        receipt = (
            GoodsReceipt.objects.select_for_update()
            .select_related("purchase_order", "project")
            .get(pk=goods_receipt.pk, organization=organization)
        )
    except GoodsReceipt.DoesNotExist as exc:
        raise PermissionDenied("رسید کالا در این سازمان یافت نشد.") from exc
    return receipt


@transaction.atomic
def create_purchase_request(
    *,
    organization: Organization,
    actor: User,
    project: Project,
    request_number: str,
    title: str,
    required_by: date | None = None,
    notes: str = "",
) -> PurchaseRequest:
    _require_role(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PURCHASE_REQUESTS_CREATE,
        message="اجازه ایجاد درخواست خرید در این سازمان را ندارید.",
        project=project,
    )
    _validate_project(organization=organization, project=project)
    normalized_number = canonicalize_upper_identifier(request_number)
    if not normalized_number or not title.strip():
        raise ValueError("وارد کردن شماره و عنوان درخواست الزامی است.")
    request = PurchaseRequest(
        organization=organization,
        project=project,
        request_number=normalized_number,
        title=title.strip(),
        required_by=required_by,
        notes=notes.strip(),
        created_by=actor,
        updated_by=actor,
    )
    _save_validated(request, "اطلاعات درخواست خرید معتبر نیست.")
    record_audit_event(
        action=AuditAction.PURCHASE_REQUEST_CREATED,
        entity_type="purchase_request",
        entity_id=request.pk,
        organization=organization,
        actor=actor,
        metadata={
            "request_number": request.request_number,
            "project_id": str(project.pk),
        },
    )
    return request


@transaction.atomic
def add_purchase_request_item(
    *,
    organization: Organization,
    actor: User,
    purchase_request: PurchaseRequest,
    material: Material,
    quantity: Decimal,
    unit_of_measure: UnitOfMeasure | None = None,
    description: str = "",
    sort_order: int = 0,
) -> PurchaseRequestItem:
    request = _get_locked_request(
        organization=organization, purchase_request=purchase_request
    )
    membership = _require_role(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PURCHASE_REQUEST_ITEMS_ADD,
        message="اجازه ویرایش درخواست‌های خرید این سازمان را ندارید.",
        project=request.project,
    )
    if request.status != PurchaseRequestStatus.DRAFT:
        raise ValueError("فقط ردیف‌های درخواست خرید پیش‌نویس قابل تغییر هستند.")
    if (
        not _has_management_access(actor, membership)
        and request.created_by_id != actor.pk
    ):
        raise PermissionDenied("اجازه ویرایش این درخواست خرید را ندارید.")
    unit = _validate_material(
        organization=organization,
        material=material,
        unit_of_measure=unit_of_measure,
    )
    if quantity <= Decimal(0):
        raise ValueError("مقدار درخواستی باید مثبت باشد.")
    item = PurchaseRequestItem(
        organization=organization,
        purchase_request=request,
        material=material,
        unit_of_measure=unit,
        description=description.strip() or material.name,
        quantity=quantity,
        sort_order=sort_order,
        created_by=actor,
    )
    _save_validated(item, "اطلاعات ردیف درخواست خرید معتبر نیست.")
    request.updated_by = actor
    request.save(update_fields=["updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.PURCHASE_REQUEST_ITEM_ADDED,
        entity_type="purchase_request_item",
        entity_id=item.pk,
        organization=organization,
        actor=actor,
        metadata={
            "purchase_request_id": str(request.pk),
            "material_id": str(material.pk),
            "quantity": str(item.quantity),
        },
    )
    return item


@transaction.atomic
def _submit_purchase_request_domain(
    *, organization: Organization, actor: User, purchase_request: PurchaseRequest
) -> PurchaseRequest:
    request = _get_locked_request(
        organization=organization, purchase_request=purchase_request
    )
    membership = _require_role(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PURCHASE_REQUESTS_SUBMIT,
        message="اجازه ارسال درخواست‌های خرید این سازمان را ندارید.",
        project=request.project,
    )
    if (
        not _has_management_access(actor, membership)
        and request.created_by_id != actor.pk
    ):
        raise PermissionDenied("اجازه ارسال این درخواست خرید را ندارید.")
    if request.status != PurchaseRequestStatus.DRAFT:
        raise ValueError("فقط درخواست‌های خرید پیش‌نویس قابل ارسال هستند.")
    if not request.items.exists():
        raise ValueError("درخواست خرید باید حداقل یک ردیف داشته باشد.")
    request.status = PurchaseRequestStatus.SUBMITTED
    request.submitted_at = timezone.now()
    request.updated_by = actor
    request.save(update_fields=["status", "submitted_at", "updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.PURCHASE_REQUEST_SUBMITTED,
        entity_type="purchase_request",
        entity_id=request.pk,
        organization=organization,
        actor=actor,
        metadata={"previous_status": PurchaseRequestStatus.DRAFT},
    )
    return request


@transaction.atomic
def _decide_purchase_request_domain(
    *,
    organization: Organization,
    actor: User,
    purchase_request: PurchaseRequest,
    approve: bool,
    reason: str = "",
) -> PurchaseRequest:
    request = _get_locked_request(
        organization=organization, purchase_request=purchase_request
    )
    _require_role(
        organization=organization,
        actor=actor,
        permission=(
            BusinessPermissionCode.PURCHASE_REQUESTS_APPROVE
            if approve
            else BusinessPermissionCode.PURCHASE_REQUESTS_REJECT
        ),
        message="اجازه تأیید درخواست‌های خرید این سازمان را ندارید.",
        project=request.project,
    )
    if request.status != PurchaseRequestStatus.SUBMITTED:
        raise ValueError("فقط درخواست‌های خرید ارسال‌شده قابل تعیین تکلیف هستند.")
    if not approve and not reason.strip():
        raise ValueError("وارد کردن دلیل رد الزامی است.")
    request.status = (
        PurchaseRequestStatus.APPROVED if approve else PurchaseRequestStatus.REJECTED
    )
    request.approved_at = timezone.now() if approve else None
    request.approved_by = actor if approve else None
    request.decision_reason = reason.strip()
    request.updated_by = actor
    request.save(
        update_fields=[
            "status",
            "approved_at",
            "approved_by",
            "decision_reason",
            "updated_by",
            "updated_at",
        ]
    )
    action = (
        AuditAction.PURCHASE_REQUEST_APPROVED
        if approve
        else AuditAction.PURCHASE_REQUEST_REJECTED
    )
    record_audit_event(
        action=action,
        entity_type="purchase_request",
        entity_id=request.pk,
        organization=organization,
        actor=actor,
        metadata={
            "previous_status": PurchaseRequestStatus.SUBMITTED,
            "status": request.status,
            "reason": request.decision_reason,
        },
    )
    return request


def approve_purchase_request(
    *,
    organization: Organization,
    actor: User,
    purchase_request: PurchaseRequest,
    reason: str = "",
) -> PurchaseRequest:
    from .workflow import decide_purchase_request_with_workflow

    return decide_purchase_request_with_workflow(
        organization=organization,
        actor=actor,
        purchase_request=purchase_request,
        outcome="approved",
        reason=reason,
    )


def reject_purchase_request(
    *,
    organization: Organization,
    actor: User,
    purchase_request: PurchaseRequest,
    reason: str = "",
) -> PurchaseRequest:
    from .workflow import decide_purchase_request_with_workflow

    return decide_purchase_request_with_workflow(
        organization=organization,
        actor=actor,
        purchase_request=purchase_request,
        outcome="rejected",
        reason=reason,
    )


@transaction.atomic
def _cancel_purchase_request_domain(
    *,
    organization: Organization,
    actor: User,
    purchase_request: PurchaseRequest,
    reason: str,
) -> PurchaseRequest:
    request = _get_locked_request(
        organization=organization, purchase_request=purchase_request
    )
    membership = _require_role(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PURCHASE_REQUESTS_CANCEL,
        message="اجازه لغو درخواست‌های خرید این سازمان را ندارید.",
        project=request.project,
    )
    if (
        not _has_management_access(actor, membership)
        and request.created_by_id != actor.pk
    ):
        raise PermissionDenied("اجازه لغو این درخواست خرید را ندارید.")
    if request.status not in {
        PurchaseRequestStatus.DRAFT,
        PurchaseRequestStatus.SUBMITTED,
    }:
        raise ValueError("فقط درخواست‌های خرید پیش‌نویس یا ارسال‌شده قابل لغو هستند.")
    if not reason.strip():
        raise ValueError("وارد کردن دلیل لغو الزامی است.")
    previous_status = request.status
    request.status = PurchaseRequestStatus.CANCELLED
    request.decision_reason = reason.strip()
    request.updated_by = actor
    request.save(
        update_fields=["status", "decision_reason", "updated_by", "updated_at"]
    )
    record_audit_event(
        action=AuditAction.PURCHASE_REQUEST_CANCELLED,
        entity_type="purchase_request",
        entity_id=request.pk,
        organization=organization,
        actor=actor,
        metadata={"previous_status": previous_status, "reason": reason.strip()},
    )
    return request


def submit_purchase_request(
    *, organization: Organization, actor: User, purchase_request: PurchaseRequest
) -> PurchaseRequest:
    from .workflow import submit_purchase_request_with_workflow

    return submit_purchase_request_with_workflow(
        organization=organization,
        actor=actor,
        purchase_request=purchase_request,
    )


def decide_purchase_request(
    *,
    organization: Organization,
    actor: User,
    purchase_request: PurchaseRequest,
    approve: bool,
    reason: str = "",
) -> PurchaseRequest:
    from .workflow import decide_purchase_request_with_workflow

    return decide_purchase_request_with_workflow(
        organization=organization,
        actor=actor,
        purchase_request=purchase_request,
        outcome="approved" if approve else "rejected",
        reason=reason,
    )


def cancel_purchase_request(
    *,
    organization: Organization,
    actor: User,
    purchase_request: PurchaseRequest,
    reason: str,
) -> PurchaseRequest:
    from .workflow import cancel_purchase_request_with_workflow

    return cancel_purchase_request_with_workflow(
        organization=organization,
        actor=actor,
        purchase_request=purchase_request,
        reason=reason,
    )


def get_organization_purchase_requests(
    *, user: User, organization: Organization
) -> QuerySet[PurchaseRequest]:
    membership = _validate_active_access(
        organization=organization,
        user=user,
        permission=BusinessPermissionCode.PURCHASE_REQUESTS_VIEW,
        allow_any_scope=True,
    )
    return scope_queryset(
        PurchaseRequest.objects.filter(
            organization=organization, project__deleted_at__isnull=True
        ),
        membership=membership,
        project_lookup="project_id",
    ).select_related("project", "created_by", "approved_by", "updated_by")


def get_organization_purchase_request(
    *, user: User, organization: Organization, purchase_request_id: str
) -> PurchaseRequest:
    try:
        return (
            get_organization_purchase_requests(user=user, organization=organization)
            .prefetch_related("items__material", "items__unit_of_measure")
            .get(pk=purchase_request_id)
        )
    except PurchaseRequest.DoesNotExist as exc:
        raise PermissionDenied("درخواست خرید در این سازمان یافت نشد.") from exc


@transaction.atomic
def create_purchase_order(
    *,
    organization: Organization,
    actor: User,
    project: Project,
    supplier: BusinessParty,
    order_number: str,
    order_date: date,
    purchase_request: PurchaseRequest | None = None,
    expected_delivery_date: date | None = None,
    notes: str = "",
) -> PurchaseOrder:
    _require_role(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PURCHASE_ORDERS_CREATE,
        message="اجازه ایجاد سفارش خرید در این سازمان را ندارید.",
        project=project,
    )
    _validate_project(organization=organization, project=project)
    _validate_supplier(organization=organization, supplier=supplier)
    if purchase_request is not None:
        request = _get_locked_request(
            organization=organization, purchase_request=purchase_request
        )
        if request.project_id != project.pk:
            raise PermissionDenied("درخواست خرید متعلق به این پروژه نیست.")
        if request.status != PurchaseRequestStatus.APPROVED:
            raise ValueError("فقط درخواست‌های خرید تأییدشده قابل سفارش هستند.")
    normalized_number = canonicalize_upper_identifier(order_number)
    if not normalized_number:
        raise ValueError("وارد کردن شماره سفارش الزامی است.")
    order = PurchaseOrder(
        organization=organization,
        project=project,
        purchase_request=purchase_request,
        supplier=supplier,
        order_number=normalized_number,
        order_date=order_date,
        expected_delivery_date=expected_delivery_date,
        notes=notes.strip(),
        created_by=actor,
        updated_by=actor,
    )
    _save_validated(order, "اطلاعات سفارش خرید معتبر نیست.")
    record_audit_event(
        action=AuditAction.PURCHASE_ORDER_CREATED,
        entity_type="purchase_order",
        entity_id=order.pk,
        organization=organization,
        actor=actor,
        metadata={
            "order_number": order.order_number,
            "project_id": str(project.pk),
            "supplier_id": str(supplier.pk),
            "purchase_request_id": str(purchase_request.pk)
            if purchase_request
            else None,
        },
    )
    return order


@transaction.atomic
def add_purchase_order_item(
    *,
    organization: Organization,
    actor: User,
    purchase_order: PurchaseOrder,
    material: Material,
    quantity: Decimal,
    unit_price: Decimal,
    unit_of_measure: UnitOfMeasure | None = None,
    purchase_request_item: PurchaseRequestItem | None = None,
    description: str = "",
    sort_order: int = 0,
) -> PurchaseOrderItem:
    order = _get_locked_order(organization=organization, purchase_order=purchase_order)
    _require_role(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PURCHASE_ORDER_ITEMS_ADD,
        message="اجازه ویرایش سفارش‌های خرید این سازمان را ندارید.",
        project=order.project,
    )
    if order.status != PurchaseOrderStatus.DRAFT:
        raise ValueError("فقط ردیف‌های سفارش خرید پیش‌نویس قابل تغییر هستند.")
    unit = _validate_material(
        organization=organization,
        material=material,
        unit_of_measure=unit_of_measure,
    )
    if quantity <= Decimal(0) or unit_price < Decimal(0):
        raise ValueError("مقدار سفارش باید مثبت و قیمت نباید منفی باشد.")
    if purchase_request_item is not None:
        try:
            request_item = PurchaseRequestItem.objects.select_for_update().get(
                pk=purchase_request_item.pk,
                organization=organization,
                purchase_request=order.purchase_request,
            )
        except PurchaseRequestItem.DoesNotExist as exc:
            raise PermissionDenied(
                "ردیف درخواست متعلق به درخواست خرید مرتبط نیست."
            ) from exc
        if request_item.material_id != material.pk:
            raise ValueError("مصالح سفارش باید با ردیف درخواست مطابقت داشته باشد.")
        already_ordered = PurchaseOrderItem.objects.filter(
            purchase_request_item=request_item,
            purchase_order__status__in={
                PurchaseOrderStatus.DRAFT,
                PurchaseOrderStatus.ISSUED,
                PurchaseOrderStatus.COMPLETED,
            },
        ).exclude(purchase_order=order).aggregate(total=Sum("quantity"))[
            "total"
        ] or Decimal(0)
        current_ordered = order.items.filter(
            purchase_request_item=request_item
        ).aggregate(total=Sum("quantity"))["total"] or Decimal(0)
        if already_ordered + current_ordered + quantity > request_item.quantity:
            raise ValueError("مقدار سفارش نمی‌تواند از مقدار درخواستی بیشتر باشد.")
    item = PurchaseOrderItem(
        organization=organization,
        purchase_order=order,
        purchase_request_item=purchase_request_item,
        material=material,
        unit_of_measure=unit,
        description=description.strip() or material.name,
        quantity=quantity,
        unit_price=unit_price,
        sort_order=sort_order,
    )
    _save_validated(item, "اطلاعات ردیف سفارش خرید معتبر نیست.")
    order.updated_by = actor
    order.save(update_fields=["updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.PURCHASE_ORDER_ITEM_ADDED,
        entity_type="purchase_order_item",
        entity_id=item.pk,
        organization=organization,
        actor=actor,
        metadata={
            "purchase_order_id": str(order.pk),
            "material_id": str(material.pk),
            "quantity": str(item.quantity),
            "unit_price": str(item.unit_price),
            "line_total": str(item.line_total),
        },
    )
    return item


@transaction.atomic
def issue_purchase_order(
    *, organization: Organization, actor: User, purchase_order: PurchaseOrder
) -> PurchaseOrder:
    order = _get_locked_order(organization=organization, purchase_order=purchase_order)
    _require_role(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PURCHASE_ORDERS_ISSUE,
        message="اجازه صدور سفارش‌های خرید این سازمان را ندارید.",
        project=order.project,
    )
    if order.status != PurchaseOrderStatus.DRAFT:
        raise ValueError("فقط سفارش‌های خرید پیش‌نویس قابل صدور هستند.")
    _validate_supplier(organization=organization, supplier=order.supplier)
    if not order.items.exists():
        raise ValueError("سفارش خرید باید حداقل یک ردیف داشته باشد.")
    order.status = PurchaseOrderStatus.ISSUED
    order.issued_at = timezone.now()
    order.issued_by = actor
    order.updated_by = actor
    order.save(
        update_fields=["status", "issued_at", "issued_by", "updated_by", "updated_at"]
    )
    record_audit_event(
        action=AuditAction.PURCHASE_ORDER_ISSUED,
        entity_type="purchase_order",
        entity_id=order.pk,
        organization=organization,
        actor=actor,
        metadata={"total_amount": str(order.total_amount)},
    )
    return order


@transaction.atomic
def cancel_purchase_order(
    *,
    organization: Organization,
    actor: User,
    purchase_order: PurchaseOrder,
    reason: str,
) -> PurchaseOrder:
    order = _get_locked_order(organization=organization, purchase_order=purchase_order)
    _require_role(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PURCHASE_ORDERS_CANCEL,
        message="اجازه لغو سفارش‌های خرید این سازمان را ندارید.",
        project=order.project,
    )
    if order.status not in {PurchaseOrderStatus.DRAFT, PurchaseOrderStatus.ISSUED}:
        raise ValueError("فقط سفارش‌های خرید پیش‌نویس یا صادرشده قابل لغو هستند.")
    if not reason.strip():
        raise ValueError("وارد کردن دلیل لغو الزامی است.")
    if order.goods_receipts.filter(status=GoodsReceiptStatus.POSTED).exists():
        raise ValueError("سفارش دارای رسید نهایی‌شده قابل لغو نیست.")
    previous_status = order.status
    order.status = PurchaseOrderStatus.CANCELLED
    order.cancelled_at = timezone.now()
    order.cancellation_reason = reason.strip()
    order.updated_by = actor
    order.save(
        update_fields=[
            "status",
            "cancelled_at",
            "cancellation_reason",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.PURCHASE_ORDER_CANCELLED,
        entity_type="purchase_order",
        entity_id=order.pk,
        organization=organization,
        actor=actor,
        metadata={"previous_status": previous_status, "reason": reason.strip()},
    )
    return order


def get_organization_purchase_orders(
    *, user: User, organization: Organization
) -> QuerySet[PurchaseOrder]:
    membership = _validate_active_access(
        organization=organization,
        user=user,
        permission=BusinessPermissionCode.PURCHASE_ORDERS_VIEW,
        allow_any_scope=True,
    )
    return scope_queryset(
        PurchaseOrder.objects.filter(
            organization=organization, project__deleted_at__isnull=True
        ),
        membership=membership,
        project_lookup="project_id",
    ).select_related(
        "project", "supplier", "purchase_request", "created_by", "issued_by"
    )


def get_organization_purchase_order(
    *, user: User, organization: Organization, purchase_order_id: str
) -> PurchaseOrder:
    try:
        return (
            get_organization_purchase_orders(user=user, organization=organization)
            .prefetch_related(
                "items__material", "items__unit_of_measure", "goods_receipts"
            )
            .get(pk=purchase_order_id)
        )
    except PurchaseOrder.DoesNotExist as exc:
        raise PermissionDenied("سفارش خرید در این سازمان یافت نشد.") from exc


@transaction.atomic
def create_goods_receipt(
    *,
    organization: Organization,
    actor: User,
    purchase_order: PurchaseOrder,
    receipt_number: str,
    received_at: datetime,
    notes: str = "",
) -> GoodsReceipt:
    order = _get_locked_order(organization=organization, purchase_order=purchase_order)
    _require_role(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.GOODS_RECEIPTS_CREATE,
        message="اجازه دریافت کالا در این سازمان را ندارید.",
        project=order.project,
    )
    if order.status != PurchaseOrderStatus.ISSUED:
        raise ValueError("دریافت کالا فقط در برابر سفارش صادرشده امکان‌پذیر است.")
    if timezone.is_naive(received_at):
        raise ValueError("زمان رسید باید دارای منطقه زمانی باشد.")
    normalized_number = canonicalize_upper_identifier(receipt_number)
    if not normalized_number:
        raise ValueError("وارد کردن شماره رسید الزامی است.")
    receipt = GoodsReceipt(
        organization=organization,
        purchase_order=order,
        project=order.project,
        receipt_number=normalized_number,
        received_at=received_at,
        notes=notes.strip(),
        created_by=actor,
        updated_by=actor,
    )
    _save_validated(receipt, "اطلاعات رسید کالا معتبر نیست.")
    record_audit_event(
        action=AuditAction.GOODS_RECEIPT_CREATED,
        entity_type="goods_receipt",
        entity_id=receipt.pk,
        organization=organization,
        actor=actor,
        metadata={
            "purchase_order_id": str(order.pk),
            "receipt_number": receipt.receipt_number,
        },
    )
    return receipt


@transaction.atomic
def add_goods_receipt_item(
    *,
    organization: Organization,
    actor: User,
    goods_receipt: GoodsReceipt,
    purchase_order_item: PurchaseOrderItem,
    quantity: Decimal,
    notes: str = "",
) -> GoodsReceiptItem:
    receipt = _get_locked_receipt(
        organization=organization, goods_receipt=goods_receipt
    )
    _require_role(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.GOODS_RECEIPT_ITEMS_ADD,
        message="اجازه ویرایش رسیدهای کالای این سازمان را ندارید.",
        project=receipt.purchase_order.project,
    )
    if receipt.status != GoodsReceiptStatus.DRAFT:
        raise ValueError("فقط ردیف‌های رسید کالای پیش‌نویس قابل تغییر هستند.")
    try:
        order_item = PurchaseOrderItem.objects.select_for_update().get(
            pk=purchase_order_item.pk,
            organization=organization,
            purchase_order=receipt.purchase_order,
        )
    except PurchaseOrderItem.DoesNotExist as exc:
        raise PermissionDenied("ردیف سفارش متعلق به سفارش این رسید نیست.") from exc
    if quantity <= Decimal(0):
        raise ValueError("مقدار دریافتی باید مثبت باشد.")
    item = GoodsReceiptItem(
        organization=organization,
        goods_receipt=receipt,
        purchase_order_item=order_item,
        material=order_item.material,
        unit_of_measure=order_item.unit_of_measure,
        quantity=quantity,
        notes=notes.strip(),
        created_by=actor,
    )
    _save_validated(item, "اطلاعات ردیف رسید کالا معتبر نیست.")
    receipt.updated_by = actor
    receipt.save(update_fields=["updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.GOODS_RECEIPT_ITEM_ADDED,
        entity_type="goods_receipt_item",
        entity_id=item.pk,
        organization=organization,
        actor=actor,
        metadata={
            "goods_receipt_id": str(receipt.pk),
            "purchase_order_item_id": str(order_item.pk),
            "quantity": str(item.quantity),
        },
    )
    return item


def _order_is_fully_received(order: PurchaseOrder) -> bool:
    received = {
        row["purchase_order_item_id"]: row["total"]
        for row in GoodsReceiptItem.objects.filter(
            goods_receipt__purchase_order=order,
            goods_receipt__status=GoodsReceiptStatus.POSTED,
        )
        .values("purchase_order_item_id")
        .annotate(total=Sum("quantity"))
    }
    return order.items.exists() and all(
        received.get(item.pk, Decimal(0)) >= item.quantity for item in order.items.all()
    )


@transaction.atomic
def post_goods_receipt(
    *, organization: Organization, actor: User, goods_receipt: GoodsReceipt
) -> GoodsReceipt:
    receipt = _get_locked_receipt(
        organization=organization, goods_receipt=goods_receipt
    )
    _require_role(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.GOODS_RECEIPTS_POST,
        message="اجازه نهایی‌سازی رسیدهای کالای این سازمان را ندارید.",
        project=receipt.purchase_order.project,
    )
    order = _get_locked_order(
        organization=organization, purchase_order=receipt.purchase_order
    )
    if receipt.status != GoodsReceiptStatus.DRAFT:
        raise ValueError("فقط رسیدهای کالای پیش‌نویس قابل نهایی‌سازی هستند.")
    if order.status != PurchaseOrderStatus.ISSUED:
        raise ValueError("سفارش خرید برای دریافت کالا باز نیست.")
    items = list(
        receipt.items.select_related("purchase_order_item").select_for_update()
    )
    if not items:
        raise ValueError("رسید کالا باید حداقل یک ردیف داشته باشد.")
    for item in items:
        already_received = GoodsReceiptItem.objects.filter(
            purchase_order_item=item.purchase_order_item,
            goods_receipt__status=GoodsReceiptStatus.POSTED,
        ).aggregate(total=Sum("quantity"))["total"] or Decimal(0)
        if already_received + item.quantity > item.purchase_order_item.quantity:
            raise ValueError("مقدار دریافتی نمی‌تواند از مقدار سفارش بیشتر باشد.")
    receipt.status = GoodsReceiptStatus.POSTED
    receipt.posted_at = timezone.now()
    receipt.posted_by = actor
    receipt.updated_by = actor
    receipt.save(
        update_fields=["status", "posted_at", "posted_by", "updated_by", "updated_at"]
    )
    record_audit_event(
        action=AuditAction.GOODS_RECEIPT_POSTED,
        entity_type="goods_receipt",
        entity_id=receipt.pk,
        organization=organization,
        actor=actor,
        metadata={"purchase_order_id": str(order.pk)},
    )
    if _order_is_fully_received(order):
        order.status = PurchaseOrderStatus.COMPLETED
        order.updated_by = actor
        order.save(update_fields=["status", "updated_by", "updated_at"])
        record_audit_event(
            action=AuditAction.PURCHASE_ORDER_COMPLETED,
            entity_type="purchase_order",
            entity_id=order.pk,
            organization=organization,
            actor=actor,
            metadata={"goods_receipt_id": str(receipt.pk)},
        )
    return receipt


@transaction.atomic
def void_goods_receipt(
    *,
    organization: Organization,
    actor: User,
    goods_receipt: GoodsReceipt,
    reason: str,
) -> GoodsReceipt:
    receipt = _get_locked_receipt(
        organization=organization, goods_receipt=goods_receipt
    )
    _require_role(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.GOODS_RECEIPTS_VOID,
        message="اجازه ابطال رسیدهای کالای این سازمان را ندارید.",
        project=receipt.purchase_order.project,
    )
    order = _get_locked_order(
        organization=organization, purchase_order=receipt.purchase_order
    )
    if receipt.status != GoodsReceiptStatus.POSTED:
        raise ValueError("فقط رسیدهای کالای نهایی‌شده قابل ابطال هستند.")
    if not reason.strip():
        raise ValueError("وارد کردن دلیل ابطال الزامی است.")
    if receipt.items.filter(
        stock_transactions__status="posted",
        stock_transactions__transaction_type="receipt",
    ).exists():
        raise ValueError(
            "پیش از ابطال رسید کالا، دریافت‌های نهایی‌شده انبار را برگشت دهید."
        )
    receipt.status = GoodsReceiptStatus.VOID
    receipt.voided_at = timezone.now()
    receipt.voided_by = actor
    receipt.void_reason = reason.strip()
    receipt.updated_by = actor
    receipt.save(
        update_fields=[
            "status",
            "voided_at",
            "voided_by",
            "void_reason",
            "updated_by",
            "updated_at",
        ]
    )
    if order.status == PurchaseOrderStatus.COMPLETED and not _order_is_fully_received(
        order
    ):
        order.status = PurchaseOrderStatus.ISSUED
        order.updated_by = actor
        order.save(update_fields=["status", "updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.GOODS_RECEIPT_VOIDED,
        entity_type="goods_receipt",
        entity_id=receipt.pk,
        organization=organization,
        actor=actor,
        metadata={"purchase_order_id": str(order.pk), "reason": reason.strip()},
    )
    return receipt


def get_organization_goods_receipts(
    *, user: User, organization: Organization
) -> QuerySet[GoodsReceipt]:
    membership = _validate_active_access(
        organization=organization,
        user=user,
        permission=BusinessPermissionCode.GOODS_RECEIPTS_VIEW,
        allow_any_scope=True,
    )
    return scope_queryset(
        GoodsReceipt.objects.filter(
            organization=organization, project__deleted_at__isnull=True
        ),
        membership=membership,
        project_lookup="project_id",
    ).select_related(
        "purchase_order", "project", "created_by", "posted_by", "voided_by"
    )


def get_organization_goods_receipt(
    *, user: User, organization: Organization, goods_receipt_id: str
) -> GoodsReceipt:
    try:
        return (
            get_organization_goods_receipts(user=user, organization=organization)
            .prefetch_related(
                "items__purchase_order_item",
                "items__material",
                "items__unit_of_measure",
            )
            .get(pk=goods_receipt_id)
        )
    except GoodsReceipt.DoesNotExist as exc:
        raise PermissionDenied("رسید کالا در این سازمان یافت نشد.") from exc
