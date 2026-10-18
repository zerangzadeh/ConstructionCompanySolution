"""PD-017/SPEC-022/032: source-controlled import and explicit pinned mappings."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from io import StringIO

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.materials.models import UnitOfMeasure
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization

from .models import (
    Estimate,
    EstimateItem,
    EstimatePriceBookMapping,
    EstimateRevisionStatus,
    PriceBook,
    PriceBookActivation,
    PriceBookRow,
    PriceBookVersion,
)


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def parse_price_book_csv(content: str) -> tuple[dict[str, str], ...]:
    """Fixed internal interchange profile; no guessed official column mapping."""
    if not content.strip() or len(content.encode()) > 5_000_000:
        raise ValidationError("محتوای ورودی خالی یا بیش از حد مجاز است.")
    reader = csv.DictReader(StringIO(content))
    columns = ("code", "chapter", "description", "unit", "value")
    if tuple(reader.fieldnames or ()) != columns:
        raise ValidationError("نگاشت ستون‌های ورودی معتبر نیست.")
    rows = []
    seen = set()
    for row in reader:
        if set(row) != set(columns) or any(v is None for v in row.values()):
            raise ValidationError("تعداد ستون‌های ردیف معتبر نیست.")
        row = {k: v.strip() for k, v in row.items()}
        if any(not v or v.startswith(("=", "+", "@")) for v in row.values()):
            raise ValidationError("مقدار خالی یا فرمول در ورودی مجاز نیست.")
        try:
            value = Decimal(row["value"])
            if not value.is_finite() or value < 0 or value >= Decimal("1e14"):
                raise ValueError
            if value != value.quantize(Decimal(".0001")):
                raise ValueError
        except (InvalidOperation, ValueError) as exc:
            raise ValidationError("مقدار عددی ردیف معتبر نیست.") from exc
        row["value"] = format(value, ".4f")
        row["code"], row["unit"] = row["code"].upper(), row["unit"].upper()
        if row["code"] in seen:
            raise ValidationError("کد ردیف تکراری است.")
        seen.add(row["code"])
        rows.append(row)
    if not rows:
        raise ValidationError("حداقل یک ردیف لازم است.")
    return tuple(sorted(rows, key=lambda row: row["code"]))


def _authorize(organization: Organization, actor: User, permission: str, project=None):
    locked = Organization.objects.select_for_update().get(pk=organization.pk)
    if not locked.is_active:
        raise PermissionDenied("سازمان فعال نیست.")
    membership = require_business_permission(
        user=actor,
        organization=locked,
        permission=permission,
        project=project,
        message="اختیار لازم برای فهرست‌بها را ندارید.",
    )
    return locked, membership


@transaction.atomic
def create_price_book(
    *,
    organization: Organization,
    actor: User,
    code: str,
    name: str,
    source_authority: str,
) -> PriceBook:
    organization, membership = _authorize(organization, actor, P.PRICE_BOOKS_MANAGE)
    return PriceBook.objects.create(
        organization=organization,
        created_by=membership,
        code=code,
        name=name.strip(),
        source_authority=source_authority.strip(),
    )


@transaction.atomic
def import_price_book_version(
    *,
    organization: Organization,
    actor: User,
    book: PriceBook,
    version: str,
    publication_year: str,
    publication_reference: str,
    effective_from: date,
    effective_to: date,
    currency: str,
    source_reference: str,
    artifact_sha256: str,
    content: str,
    idempotency_key: str,
    supersedes: PriceBookVersion | None = None,
) -> PriceBookVersion:
    organization, membership = _authorize(organization, actor, P.PRICE_BOOKS_MANAGE)
    try:
        book = PriceBook.objects.get(pk=book.pk, organization=organization)
    except PriceBook.DoesNotExist as exc:
        raise PermissionDenied("منبع متعلق به این سازمان نیست.") from exc
    rows = parse_price_book_csv(content)
    attributes = {
        "book": book,
        "version": version.strip(),
        "publication_year": publication_year.strip(),
        "publication_reference": publication_reference.strip(),
        "effective_from": effective_from,
        "effective_to": effective_to,
        "currency": currency.strip(),
        "source_reference": source_reference.strip(),
        "artifact_sha256": artifact_sha256,
        "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
        "rows_sha256": _digest(rows),
        "supersedes": supersedes,
    }
    prior = PriceBookVersion.objects.filter(
        organization=organization, idempotency_key=idempotency_key.strip()
    ).first()
    if prior:
        if any(getattr(prior, k) != v for k, v in attributes.items()):
            raise ValidationError("کلید واردسازی با محتوای متفاوت استفاده شده است.")
        return prior
    units = {
        u.code: u
        for u in UnitOfMeasure.objects.filter(
            organization=organization,
            is_active=True,
            archived_at__isnull=True,
            code__in={row["unit"] for row in rows},
        )
    }
    if any(row["unit"] not in units for row in rows):
        raise ValidationError("واحد مصوب و فعال برای تمام ردیف‌ها الزامی است.")
    imported = PriceBookVersion.objects.create(
        organization=organization,
        created_by=membership,
        idempotency_key=idempotency_key.strip(),
        **attributes,
    )
    for row in rows:
        PriceBookRow.objects.create(
            organization=organization,
            created_by=membership,
            version=imported,
            code=row["code"],
            chapter=row["chapter"],
            description=row["description"],
            unit_of_measure=units[row["unit"]],
            value=Decimal(row["value"]),
        )
    record_audit_event(
        organization=organization,
        actor=actor,
        action=AuditAction.PRICE_BOOK_IMPORTED,
        entity_type="estimates.PriceBookVersion",
        entity_id=imported.pk,
        metadata={
            "book_id": str(book.pk),
            "content_sha256": imported.content_sha256,
            "rows_sha256": imported.rows_sha256,
            "rows": len(rows),
        },
    )
    return imported


@transaction.atomic
def activate_price_book_version(
    *,
    organization: Organization,
    actor: User,
    version: PriceBookVersion,
    approval_reference: str,
    reviewed_artifact_sha256: str,
    reviewed_content_sha256: str,
) -> PriceBookActivation:
    """Retain explicit authorized source approval; absence of evidence fails closed.

    This records the source reviewer’s attestation over the exact evidence hashes.
    It does not independently certify a publisher or obtain official content.
    """
    organization, membership = _authorize(organization, actor, P.PRICE_BOOKS_ACTIVATE)
    try:
        version = PriceBookVersion.objects.select_for_update().get(
            pk=version.pk, organization=organization
        )
    except PriceBookVersion.DoesNotExist as exc:
        raise PermissionDenied("نسخه متعلق به این سازمان نیست.") from exc
    rows = tuple(
        {
            "code": row.code,
            "chapter": row.chapter,
            "description": row.description,
            "unit": row.unit_of_measure.code,
            "value": format(row.value, ".4f"),
        }
        for row in version.rows.select_related("unit_of_measure").order_by("code")
    )
    if not rows or _digest(rows) != version.rows_sha256:
        raise ValidationError("محتوای نسخه با واردسازی ثبت‌شده هم‌خوان نیست.")
    attributes = {
        "approval_reference": approval_reference.strip(),
        "reviewed_artifact_sha256": reviewed_artifact_sha256,
        "reviewed_content_sha256": reviewed_content_sha256,
    }
    prior = PriceBookActivation.objects.filter(version=version).first()
    if prior:
        if any(getattr(prior, k) != v for k, v in attributes.items()):
            raise ValidationError("تأیید قبلی با شواهد متفاوت جایگزین نمی‌شود.")
        return prior
    activation = PriceBookActivation.objects.create(
        organization=organization,
        created_by=membership,
        version=version,
        **attributes,
    )
    record_audit_event(
        organization=organization,
        actor=actor,
        action=AuditAction.PRICE_BOOK_ACTIVATED,
        entity_type="estimates.PriceBookActivation",
        entity_id=activation.pk,
        metadata={"version_id": str(version.pk), **attributes},
    )
    return activation


def item_snapshot(item: EstimateItem) -> dict[str, str]:
    return {
        "item_id": str(item.pk),
        "revision_id": str(item.revision_id),
        "quantity": format(item.quantity, ".4f"),
        "unit_id": str(item.unit_of_measure_id),
        "unit_price": format(item.unit_price, ".2f"),
        "description": item.description,
    }


def validate_item_mapping(item: EstimateItem) -> None:
    if item.price_book_mapping_id:
        mapping = item.price_book_mapping
        if (
            mapping.source_item_id != item.pk
            or mapping.source_revision_id != item.revision_id
            or mapping.organization_id != item.organization_id
            or mapping.source_snapshot != item_snapshot(item)
        ):
            raise ValidationError(
                "شواهد ردیف تغییر کرده است؛ نگاشت صریح جدید لازم است."
            )


def _bind_mapping(
    *,
    item: EstimateItem,
    row: PriceBookRow,
    effective_date: date,
    evidence_reference: str,
    membership,
    actor: User,
) -> EstimatePriceBookMapping:
    prior = item.price_book_mapping
    attributes = {
        "organization": item.organization,
        "created_by": membership,
        "source_item": item,
        "source_revision": item.revision,
        "row": row,
        "effective_date": effective_date,
        "evidence_reference": evidence_reference,
        "source_snapshot": item_snapshot(item),
        "version": prior.version + 1 if prior else 1,
        "supersedes": prior,
    }
    if prior:
        attributes["identity"] = prior.identity
    mapping = EstimatePriceBookMapping.objects.create(**attributes)
    item.price_book_mapping = mapping
    item.save(update_fields=["price_book_mapping", "updated_at"])
    record_audit_event(
        organization=item.organization,
        actor=actor,
        action=AuditAction.PRICE_BOOK_MAPPED,
        entity_type="estimates.EstimatePriceBookMapping",
        entity_id=mapping.pk,
        metadata={
            "source_item_id": str(item.pk),
            "source_revision_id": str(item.revision_id),
            "row_id": str(row.pk),
            "book_version_id": str(row.version_id),
            "mapping_identity": str(mapping.identity),
            "mapping_version": mapping.version,
            "predecessor_id": str(prior.pk) if prior else None,
        },
    )
    return mapping


@transaction.atomic
def map_estimate_price_book(
    *,
    organization: Organization,
    actor: User,
    item: EstimateItem,
    row: PriceBookRow,
    effective_date: date,
    evidence_reference: str,
) -> EstimatePriceBookMapping:
    # Match revision service lock order: estimate before source-item/pointer mutation.
    try:
        reference = EstimateItem.objects.get(pk=item.pk, organization=organization)
    except EstimateItem.DoesNotExist as exc:
        raise PermissionDenied("ردیف متعلق به این سازمان نیست.") from exc
    organization, membership = _authorize(
        organization, actor, P.PRICE_BOOK_MAPPINGS_MANAGE, reference.estimate.project
    )
    estimate = Estimate.objects.select_for_update().get(
        pk=reference.estimate_id, organization=organization
    )
    item = EstimateItem.objects.select_for_update().get(
        pk=reference.pk, organization=organization
    )
    if (
        not item.revision_id
        or item.revision.status != EstimateRevisionStatus.DRAFT
        or estimate.current_revision_id != item.revision_id
        or estimate.deleted_at
        or estimate.project.deleted_at
    ):
        raise ValidationError("نگاشت فقط در بازنگری جاری و قابل ویرایش مجاز است.")
    try:
        row = PriceBookRow.objects.get(pk=row.pk, organization=organization)
    except PriceBookRow.DoesNotExist as exc:
        raise PermissionDenied("ردیف منبع متعلق به این سازمان نیست.") from exc
    return _bind_mapping(
        item=item,
        row=row,
        effective_date=effective_date,
        evidence_reference=evidence_reference,
        membership=membership,
        actor=actor,
    )


def copy_item_mapping(
    *, source: EstimateItem, copied: EstimateItem, actor: User
) -> None:
    """Called only inside the explicit authorized estimate-revision transaction."""
    validate_item_mapping(source)
    if source.price_book_mapping_id:
        # Preserve exact version selection; revision-copy is not a new source selection.
        prior = source.price_book_mapping
        copied.price_book_mapping = prior
        _bind_mapping(
            item=copied,
            row=prior.row,
            effective_date=prior.effective_date,
            evidence_reference=prior.evidence_reference,
            membership=copied.organization.memberships.get(user=actor),
            actor=actor,
        )


def reconcile_estimate_price_books(
    *, organization: Organization, actor: User, estimate: Estimate
) -> dict:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=P.ESTIMATES_VIEW,
        allow_any_scope=True,
        message="اختیار مشاهده برآورد لازم است.",
    )
    try:
        estimate = Estimate.objects.get(pk=estimate.pk, organization=organization)
    except Estimate.DoesNotExist as exc:
        raise PermissionDenied("برآورد متعلق به این سازمان نیست.") from exc
    require_business_permission(
        user=actor,
        organization=organization,
        permission=P.ESTIMATES_VIEW,
        project=estimate.project,
        message="دامنه پروژه لازم است.",
    )
    rows = []
    for item in estimate.items.select_related(
        "price_book_mapping__row__version__book"
    ).order_by("pk"):
        mapping = item.price_book_mapping
        rows.append(
            {
                "item_id": str(item.pk),
                "revision_id": str(item.revision_id),
                "mapping_id": str(mapping.pk) if mapping else None,
                "mapping_identity": str(mapping.identity) if mapping else None,
                "mapping_version": mapping.version if mapping else None,
                "predecessor_id": str(mapping.supersedes_id)
                if mapping and mapping.supersedes_id
                else None,
                "row_id": str(mapping.row_id) if mapping else None,
                "book_version_id": str(mapping.row.version_id) if mapping else None,
                "book_id": str(mapping.row.version.book_id) if mapping else None,
                "effective_date": str(mapping.effective_date) if mapping else None,
                "source_evidence": mapping.row.version.source_reference
                if mapping
                else None,
                "exception": None if mapping else "NO_AUTHORITATIVE_PRICE_BOOK_MAPPING",
            }
        )
    return {
        "estimate_id": str(estimate.pk),
        "items": rows,
        "evidence_hash": _digest(rows),
    }
