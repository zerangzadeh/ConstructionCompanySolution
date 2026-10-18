"""INT-R04 retained comparison evidence; Inventory remains stock authority."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.procurement.models import GoodsReceipt, GoodsReceiptItem, GoodsReceiptStatus

from .models import StockTransaction

CONTRACT = "procurement.goods_receipt_item.v1"


def fingerprint(payload: object) -> str:
    """Normalize numeric and datetime representation without losing precision."""

    def encode(value: object) -> str:
        if isinstance(value, Decimal):
            return format(value.normalize(), "f") if value else "0"
        if isinstance(value, datetime):
            return value.astimezone(UTC).isoformat()
        if isinstance(value, UUID):
            return str(value)
        raise TypeError(f"Unsupported fingerprint type: {type(value).__name__}")

    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), default=encode
        ).encode()
    ).hexdigest()


def receipt_evidence(target: StockTransaction) -> dict[str, object]:
    """Called after locked source, material, warehouse and scope validation."""
    item = target.goods_receipt_item
    receipt = item.goods_receipt
    version = receipt.purchase_order_version
    if (
        receipt.status != GoodsReceiptStatus.POSTED
        or not receipt.posted_at
        or not receipt.posted_by_id
        or version is None
        or version.organization_id != target.organization_id
        or version.purchase_order_id != receipt.purchase_order_id
    ):
        raise ValidationError(
            "Approved receipt occurrence and pinned version required."
        )
    source = source_snapshot(item)
    return {
        "contract": CONTRACT,
        "source": source,
        "source_fingerprint": fingerprint(source),
        "request_fingerprint": target_fingerprint(target),
    }


def source_snapshot(item: GoodsReceiptItem) -> dict[str, object]:
    receipt = item.goods_receipt
    version = receipt.purchase_order_version
    return {
        "receipt_id": str(receipt.pk),
        "receipt_item_id": str(item.pk),
        "purchase_order_id": str(receipt.purchase_order_id),
        "purchase_order_version_id": str(version.pk) if version else None,
        "purchase_order_version": version.version_number if version else None,
        "purchase_order_hash": version.payload_hash if version else None,
        "posted_at": receipt.posted_at.isoformat() if receipt.posted_at else None,
        "posted_by_id": str(receipt.posted_by_id),
        "received_at": receipt.received_at.isoformat(),
        "project_id": str(receipt.project_id),
        "material_id": str(item.material_id),
        "unit_id": str(item.unit_of_measure_id),
        "quantity": format(item.quantity.normalize(), "f"),
    }


def target_fingerprint(target: StockTransaction) -> str:
    return fingerprint(
        {
            name: getattr(target, name)
            for name in (
                "organization_id",
                "transaction_number",
                "transaction_type",
                "source_warehouse_id",
                "destination_warehouse_id",
                "material_id",
                "unit_of_measure_id",
                "project_id",
                "goods_receipt_item_id",
                "quantity",
                "occurred_at",
                "reference",
                "notes",
            )
        }
    )


def retained_receipt_target(
    *, candidate: StockTransaction, evidence: dict[str, object], actor: User
) -> StockTransaction | None:
    """Replay retains original state, including reversal; never reactivates stock."""
    targets = list(
        StockTransaction.objects.select_for_update().filter(
            organization_id=candidate.organization_id,
            goods_receipt_item_id=candidate.goods_receipt_item_id,
        )
    )
    events = AuditEvent.objects.filter(
        organization_id=candidate.organization_id,
        action=AuditAction.STOCK_TRANSACTION_CREATED,
        entity_type="stock_transaction",
        metadata__receipt_contract__contract=CONTRACT,
        metadata__receipt_contract__source__receipt_item_id=str(
            candidate.goods_receipt_item_id
        ),
    )
    if not targets and not events.exists():
        return None
    if len(targets) != 1 or events.count() != 1:
        raise ValidationError("Receipt history lacks one retained contract occurrence.")
    target = targets[0]
    event = events.first()
    if (
        event.entity_id != str(target.pk)
        or event.metadata["receipt_contract"] != evidence
        or target_fingerprint(target) != evidence["request_fingerprint"]
    ):
        raise ValidationError(
            "Receipt occurrence payload or original evidence differs."
        )
    record_audit_event(
        organization=candidate.organization,
        actor=actor,
        action=AuditAction.STOCK_RECEIPT_RETRIED,
        entity_type="stock_transaction",
        entity_id=target.pk,
        metadata={"receipt_contract": evidence, "retained_status": target.status},
    )
    return target


@transaction.atomic
def reconcile_goods_receipt_inventory(
    *, organization: Organization, actor: User, receipt: GoodsReceipt
) -> dict[str, object]:
    """Source/target projection including legacy gaps and Inventory reversals."""
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.STOCK_TRANSACTIONS_VIEW,
        allow_any_scope=True,
        message="Inventory receipt reconciliation permission required.",
    )
    try:
        receipt = GoodsReceipt.objects.select_for_update().get(
            pk=receipt.pk, organization=organization
        )
    except GoodsReceipt.DoesNotExist as exc:
        raise PermissionDenied("Receipt belongs to another tenant.") from exc
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.STOCK_TRANSACTIONS_VIEW,
        project=receipt.project,
        message="Inventory receipt project scope required.",
    )
    rows = []
    for item in receipt.items.filter(organization=organization).order_by("pk"):
        current_source = source_snapshot(item)
        targets = []
        for target in StockTransaction.objects.filter(
            organization=organization, goods_receipt_item=item
        ).order_by("created_at", "pk"):
            event = AuditEvent.objects.filter(
                organization=organization,
                action=AuditAction.STOCK_TRANSACTION_CREATED,
                entity_type="stock_transaction",
                entity_id=str(target.pk),
            ).first()
            retained = event.metadata.get("receipt_contract") if event else None
            reversal = StockTransaction.objects.filter(
                organization=organization, reversal_of=target
            ).first()
            targets.append(
                {
                    "target_id": str(target.pk),
                    "status": target.status,
                    "quantity": str(target.quantity),
                    "retained_contract": retained,
                    "source_payload_matches": bool(
                        retained
                        and retained["source_fingerprint"]
                        == fingerprint(current_source)
                    ),
                    "target_payload_matches": bool(
                        retained
                        and retained["request_fingerprint"]
                        == target_fingerprint(target)
                    ),
                    "reversal_id": str(reversal.pk) if reversal else None,
                    "reversal_quantity": str(reversal.quantity) if reversal else None,
                }
            )
        rows.append(
            {
                "source_item_id": str(item.pk),
                "current_source": current_source,
                "targets": targets,
            }
        )
    result = {
        "receipt_id": str(receipt.pk),
        "source_status": receipt.status,
        "active_order_version_id": str(receipt.purchase_order_version_id),
        "items": rows,
    }
    result["evidence_hash"] = fingerprint(result)
    return result
