from datetime import datetime
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet, Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.inventory.models import (
    StockTransaction,
    StockTransactionStatus,
    StockTransactionType,
    Warehouse,
)
from apps.materials.models import Material, UnitOfMeasure
from apps.organizations.authorization import (
    get_active_membership,
    require_business_permission,
)
from apps.organizations.models import (
    BusinessPermissionCode,
    Organization,
)
from apps.procurement.models import GoodsReceipt, GoodsReceiptItem, GoodsReceiptStatus
from apps.projects.models import Project
from core.identifiers import canonicalize_upper_identifier

_LEDGER_STATUSES = {
    StockTransactionStatus.POSTED,
    StockTransactionStatus.REVERSED,
}


def _validate_active_access(*, organization: Organization, user: User) -> None:
    if user.is_superuser and user.is_active:
        return
    get_active_membership(user=user, organization=organization)


def _require_role(
    *, organization: Organization, actor: User, permission: str, message: str
) -> None:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        message=message,
    )


def _validate_project(
    *, organization: Organization, project: Project | None
) -> Project | None:
    if project is None:
        return None
    try:
        stored = Project.objects.select_for_update().get(
            pk=project.pk,
            organization=organization,
        )
    except Project.DoesNotExist as exc:
        raise PermissionDenied("پروژه متعلق به این سازمان نیست.") from exc
    if stored.deleted_at is not None:
        raise PermissionDenied("پروژه متعلق به این سازمان نیست.")
    return stored


def _validate_material(
    *,
    organization: Organization,
    material: Material,
    unit_of_measure: UnitOfMeasure,
) -> tuple[Material, UnitOfMeasure]:
    try:
        stored = (
            Material.objects.select_for_update()
            .select_related("unit_of_measure")
            .get(pk=material.pk, organization=organization)
        )
    except Material.DoesNotExist as exc:
        raise PermissionDenied("مصالح متعلق به این سازمان نیست.") from exc
    stored_unit = stored.unit_of_measure
    if (
        unit_of_measure.organization_id != organization.pk
        or stored.unit_of_measure_id != unit_of_measure.pk
        or not stored.is_active
        or stored.archived_at is not None
        or not stored_unit.is_active
        or stored_unit.archived_at is not None
    ):
        raise PermissionDenied(
            "مصالح و واحد اندازه‌گیری باید رکوردهای فعال این سازمان باشند."
        )
    return stored, stored_unit


def _get_warehouse(
    *, organization: Organization, warehouse: Warehouse | None
) -> Warehouse | None:
    if warehouse is None:
        return None
    try:
        stored = Warehouse.objects.select_for_update().get(
            pk=warehouse.pk,
            organization=organization,
        )
    except Warehouse.DoesNotExist as exc:
        raise PermissionDenied("انبار متعلق به این سازمان نیست.") from exc
    if not stored.is_active or stored.archived_at is not None:
        raise ValueError("انبار بایگانی‌شده یا غیرفعال است.")
    return stored


def _save_validated(instance: object, message: str) -> None:
    try:
        instance.full_clean()
        instance.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError(message) from exc


def _stock_balance_value(
    *, organization: Organization, warehouse: Warehouse, material: Material
) -> Decimal:
    incoming = StockTransaction.objects.filter(
        organization=organization,
        destination_warehouse=warehouse,
        material=material,
        status__in=_LEDGER_STATUSES,
    ).aggregate(total=Sum("quantity"))["total"] or Decimal("0.0000")
    outgoing = StockTransaction.objects.filter(
        organization=organization,
        source_warehouse=warehouse,
        material=material,
        status__in=_LEDGER_STATUSES,
    ).aggregate(total=Sum("quantity"))["total"] or Decimal("0.0000")
    return incoming - outgoing


def _lock_warehouses(transaction_record: StockTransaction) -> None:
    warehouse_ids = sorted(
        {
            warehouse_id
            for warehouse_id in (
                transaction_record.source_warehouse_id,
                transaction_record.destination_warehouse_id,
            )
            if warehouse_id is not None
        },
        key=str,
    )
    locked_warehouses = list(
        Warehouse.objects.select_for_update().filter(
            pk__in=warehouse_ids,
            organization=transaction_record.organization,
        )
    )
    if len(locked_warehouses) != len(warehouse_ids) or any(
        not warehouse.is_active or warehouse.archived_at is not None
        for warehouse in locked_warehouses
    ):
        raise ValueError("تراکنش به انبارهای فعال همین سازمان نیاز دارد.")


def _ensure_available_stock(transaction_record: StockTransaction) -> None:
    if transaction_record.source_warehouse_id is None:
        return
    available = _stock_balance_value(
        organization=transaction_record.organization,
        warehouse=transaction_record.source_warehouse,
        material=transaction_record.material,
    )
    if available < transaction_record.quantity:
        raise ValueError("این تراکنش موجب منفی شدن موجودی انبار می‌شود.")


@transaction.atomic
def create_warehouse(
    *,
    organization: Organization,
    actor: User,
    code: str,
    name: str,
    project: Project | None = None,
    location: str = "",
) -> Warehouse:
    _require_role(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_MANAGE,
        message="اجازه مدیریت انبارهای این سازمان را ندارید.",
    )
    project = _validate_project(organization=organization, project=project)
    warehouse = Warehouse(
        organization=organization,
        project=project,
        code=canonicalize_upper_identifier(code),
        name=name.strip(),
        location=location.strip(),
        created_by=actor,
        updated_by=actor,
    )
    _save_validated(warehouse, "اطلاعات انبار معتبر نیست یا کد آن تکراری است.")
    record_audit_event(
        action=AuditAction.WAREHOUSE_CREATED,
        entity_type="warehouse",
        entity_id=warehouse.pk,
        organization=organization,
        actor=actor,
        metadata={
            "code": warehouse.code,
            "project_id": str(project.pk) if project else None,
        },
    )
    return warehouse


@transaction.atomic
def archive_warehouse(
    *, organization: Organization, actor: User, warehouse: Warehouse
) -> Warehouse:
    _require_role(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_MANAGE,
        message="اجازه مدیریت انبارهای این سازمان را ندارید.",
    )
    try:
        locked = Warehouse.objects.select_for_update().get(
            pk=warehouse.pk,
            organization=organization,
        )
    except Warehouse.DoesNotExist as exc:
        raise PermissionDenied("انبار در این سازمان یافت نشد.") from exc
    if not locked.is_active or locked.archived_at is not None:
        raise ValueError("انبار از قبل بایگانی شده است.")
    if (
        StockTransaction.objects.filter(
            organization=organization,
            status=StockTransactionStatus.DRAFT,
        )
        .filter(Q(source_warehouse=locked) | Q(destination_warehouse=locked))
        .exists()
    ):
        raise ValueError("انبار دارای تراکنش پیش‌نویس قابل بایگانی نیست.")
    material_ids = (
        StockTransaction.objects.filter(
            organization=organization,
        )
        .filter(Q(source_warehouse=locked) | Q(destination_warehouse=locked))
        .values_list("material_id", flat=True)
        .distinct()
    )
    for material in Material.objects.filter(pk__in=material_ids):
        if _stock_balance_value(
            organization=organization,
            warehouse=locked,
            material=material,
        ) != Decimal("0.0000"):
            raise ValueError("انبار دارای موجودی غیرصفر قابل بایگانی نیست.")
    locked.is_active = False
    locked.archived_at = timezone.now()
    locked.updated_by = actor
    locked.save(update_fields=["is_active", "archived_at", "updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.WAREHOUSE_ARCHIVED,
        entity_type="warehouse",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"code": locked.code},
    )
    return locked


@transaction.atomic
def create_stock_transaction(
    *,
    organization: Organization,
    actor: User,
    transaction_number: str,
    transaction_type: str,
    material: Material,
    unit_of_measure: UnitOfMeasure,
    quantity: Decimal,
    occurred_at: datetime,
    source_warehouse: Warehouse | None = None,
    destination_warehouse: Warehouse | None = None,
    project: Project | None = None,
    goods_receipt_item: GoodsReceiptItem | None = None,
    reference: str = "",
    notes: str = "",
) -> StockTransaction:
    """Create an auditable draft movement; posting separately changes stock."""

    _require_role(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_MOVEMENT,
        message="اجازه ایجاد تراکنش انبار در این سازمان را ندارید.",
    )
    if transaction_type not in StockTransactionType.values or (
        transaction_type == StockTransactionType.REVERSAL
    ):
        raise ValueError("نوع تراکنش انبار معتبر نیست.")
    if quantity <= Decimal(0):
        raise ValueError("مقدار باید مثبت باشد.")
    if timezone.is_naive(occurred_at):
        raise ValueError("زمان تراکنش باید دارای منطقه زمانی باشد.")
    project = _validate_project(organization=organization, project=project)
    material, unit_of_measure = _validate_material(
        organization=organization,
        material=material,
        unit_of_measure=unit_of_measure,
    )
    source = _get_warehouse(organization=organization, warehouse=source_warehouse)
    destination = _get_warehouse(
        organization=organization,
        warehouse=destination_warehouse,
    )
    if goods_receipt_item is not None:
        try:
            item_reference = GoodsReceiptItem.objects.only("goods_receipt_id").get(
                pk=goods_receipt_item.pk,
                organization=organization,
            )
        except GoodsReceiptItem.DoesNotExist as exc:
            raise PermissionDenied("ردیف رسید کالا در این سازمان یافت نشد.") from exc
        locked_receipt = GoodsReceipt.objects.select_for_update().get(
            pk=item_reference.goods_receipt_id,
            organization=organization,
        )
        goods_receipt_item = (
            GoodsReceiptItem.objects.select_for_update()
            .select_related("material", "unit_of_measure")
            .get(
                pk=goods_receipt_item.pk,
                organization=organization,
                goods_receipt=locked_receipt,
            )
        )
        goods_receipt_item.goods_receipt = locked_receipt
        if locked_receipt.status != GoodsReceiptStatus.POSTED:
            raise ValueError("فقط رسیدهای کالای نهایی‌شده قابل ورود به انبار هستند.")
    transaction_record = StockTransaction(
        organization=organization,
        transaction_number=canonicalize_upper_identifier(transaction_number),
        transaction_type=transaction_type,
        source_warehouse=source,
        destination_warehouse=destination,
        material=material,
        unit_of_measure=unit_of_measure,
        project=project,
        goods_receipt_item=goods_receipt_item,
        quantity=quantity,
        occurred_at=occurred_at,
        reference=reference.strip(),
        notes=notes.strip(),
        created_by=actor,
        updated_by=actor,
    )
    _save_validated(
        transaction_record,
        "Stock transaction data is invalid or its number/source is in use.",
    )
    record_audit_event(
        action=AuditAction.STOCK_TRANSACTION_CREATED,
        entity_type="stock_transaction",
        entity_id=transaction_record.pk,
        organization=organization,
        actor=actor,
        metadata={
            "transaction_number": transaction_record.transaction_number,
            "transaction_type": transaction_type,
            "quantity": str(quantity),
            "material_id": str(material.pk),
        },
    )
    return transaction_record


@transaction.atomic
def post_stock_transaction(
    *, organization: Organization, actor: User, stock_transaction: StockTransaction
) -> StockTransaction:
    _require_role(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_MOVEMENT,
        message="اجازه نهایی‌سازی تراکنش‌های انبار این سازمان را ندارید.",
    )
    try:
        transaction_record = (
            StockTransaction.objects.select_for_update()
            .select_related(
                "organization",
                "source_warehouse",
                "destination_warehouse",
                "material",
                "unit_of_measure",
                "project",
                "goods_receipt_item__goods_receipt",
            )
            .get(pk=stock_transaction.pk, organization=organization)
        )
    except StockTransaction.DoesNotExist as exc:
        raise PermissionDenied("تراکنش انبار در این سازمان یافت نشد.") from exc
    if transaction_record.status != StockTransactionStatus.DRAFT:
        raise ValueError("فقط تراکنش‌های انبار پیش‌نویس قابل نهایی‌سازی هستند.")
    transaction_record.project = _validate_project(
        organization=organization,
        project=transaction_record.project,
    )
    transaction_record.material, transaction_record.unit_of_measure = (
        _validate_material(
            organization=organization,
            material=transaction_record.material,
            unit_of_measure=transaction_record.unit_of_measure,
        )
    )
    if transaction_record.goods_receipt_item_id:
        source_receipt = GoodsReceipt.objects.select_for_update().get(
            pk=transaction_record.goods_receipt_item.goods_receipt_id,
            organization=organization,
        )
        if source_receipt.status != GoodsReceiptStatus.POSTED:
            raise ValueError("رسید کالای مبدأ دیگر نهایی‌شده نیست.")
    _lock_warehouses(transaction_record)
    _ensure_available_stock(transaction_record)
    transaction_record.status = StockTransactionStatus.POSTED
    transaction_record.posted_at = timezone.now()
    transaction_record.posted_by = actor
    transaction_record.updated_by = actor
    transaction_record.save(
        update_fields=["status", "posted_at", "posted_by", "updated_by", "updated_at"]
    )
    record_audit_event(
        action=AuditAction.STOCK_TRANSACTION_POSTED,
        entity_type="stock_transaction",
        entity_id=transaction_record.pk,
        organization=organization,
        actor=actor,
        metadata={
            "transaction_number": transaction_record.transaction_number,
            "transaction_type": transaction_record.transaction_type,
            "quantity": str(transaction_record.quantity),
        },
    )
    return transaction_record


@transaction.atomic
def reverse_stock_transaction(
    *,
    organization: Organization,
    actor: User,
    stock_transaction: StockTransaction,
    reversal_number: str,
    reason: str,
) -> StockTransaction:
    """Reverse a posted movement with an equal and opposite posted ledger entry."""

    _require_role(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_MANAGE,
        message="اجازه برگشت تراکنش‌های انبار این سازمان را ندارید.",
    )
    try:
        original = (
            StockTransaction.objects.select_for_update()
            .select_related(
                "source_warehouse",
                "destination_warehouse",
                "material",
                "unit_of_measure",
                "project",
            )
            .get(pk=stock_transaction.pk, organization=organization)
        )
    except StockTransaction.DoesNotExist as exc:
        raise PermissionDenied("تراکنش انبار در این سازمان یافت نشد.") from exc
    if original.status != StockTransactionStatus.POSTED:
        raise ValueError("فقط تراکنش‌های انبار نهایی‌شده قابل برگشت هستند.")
    if original.transaction_type == StockTransactionType.REVERSAL:
        raise ValueError("تراکنش برگشتی قابل برگشت مجدد نیست.")
    if not reason.strip():
        raise ValueError("وارد کردن دلیل برگشت الزامی است.")
    original.material, original.unit_of_measure = _validate_material(
        organization=organization,
        material=original.material,
        unit_of_measure=original.unit_of_measure,
    )
    _lock_warehouses(original)
    reversal = StockTransaction(
        organization=organization,
        transaction_number=canonicalize_upper_identifier(reversal_number),
        transaction_type=StockTransactionType.REVERSAL,
        status=StockTransactionStatus.POSTED,
        source_warehouse=original.destination_warehouse,
        destination_warehouse=original.source_warehouse,
        material=original.material,
        unit_of_measure=original.unit_of_measure,
        project=original.project,
        reversal_of=original,
        quantity=original.quantity,
        occurred_at=timezone.now(),
        reference=original.transaction_number,
        notes=reason.strip(),
        posted_at=timezone.now(),
        posted_by=actor,
        created_by=actor,
        updated_by=actor,
    )
    _ensure_available_stock(reversal)
    _save_validated(reversal, "اطلاعات برگشت انبار معتبر نیست یا شماره آن تکراری است.")
    original.status = StockTransactionStatus.REVERSED
    original.reversed_at = timezone.now()
    original.reversed_by = actor
    original.reversal_reason = reason.strip()
    original.updated_by = actor
    original.save(
        update_fields=[
            "status",
            "reversed_at",
            "reversed_by",
            "reversal_reason",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.STOCK_TRANSACTION_REVERSED,
        entity_type="stock_transaction",
        entity_id=original.pk,
        organization=organization,
        actor=actor,
        metadata={
            "transaction_number": original.transaction_number,
            "reversal_id": str(reversal.pk),
            "reversal_number": reversal.transaction_number,
            "reason": reason.strip(),
        },
    )
    return reversal


def get_organization_warehouses(
    *, user: User, organization: Organization, active_only: bool = False
) -> QuerySet[Warehouse]:
    _validate_active_access(organization=organization, user=user)
    queryset = Warehouse.objects.filter(organization=organization).select_related(
        "project", "created_by", "updated_by"
    )
    if active_only:
        queryset = queryset.filter(is_active=True, archived_at__isnull=True)
    return queryset


def get_organization_stock_transactions(
    *, user: User, organization: Organization
) -> QuerySet[StockTransaction]:
    _validate_active_access(organization=organization, user=user)
    return StockTransaction.objects.filter(organization=organization).select_related(
        "source_warehouse",
        "destination_warehouse",
        "material",
        "unit_of_measure",
        "project",
        "goods_receipt_item__goods_receipt",
        "reversal_of",
        "created_by",
        "posted_by",
        "reversed_by",
    )


def get_stock_balance(
    *,
    user: User,
    organization: Organization,
    warehouse: Warehouse,
    material: Material,
) -> Decimal:
    """Derive on-hand quantity from the immutable movement ledger."""

    _validate_active_access(organization=organization, user=user)
    if warehouse.organization_id != organization.pk:
        raise PermissionDenied("انبار در این سازمان یافت نشد.")
    if material.organization_id != organization.pk:
        raise PermissionDenied("مصالح در این سازمان یافت نشد.")
    return _stock_balance_value(
        organization=organization,
        warehouse=warehouse,
        material=material,
    )
