"""Explicit RFQ scope preparation and version pinning; no award allocation."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.validators import DecimalValidator
from django.db import transaction

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.materials.models import UnitOfMeasure
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization

from .models import (
    PurchaseRequest,
    RequestForQuotation,
    RequestForQuotationVersion,
    RFQCommercialScope,
    RFQCommercialScopeDefinition,
)
from .rfq_services import _locked_rfq, _permission


def fingerprint(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def source_lines(rfq: RequestForQuotation, version_number: int):
    """Addenda inherit the exact previous issued lines, as the existing service does."""
    if rfq.current_version_number:
        number = min(version_number, rfq.current_version_number)
        return (
            rfq.versions.get(version_number=number)
            .lines.select_related(
                "purchase_request_item", "material", "unit_of_measure"
            )
            .order_by("sort_order", "created_at", "purchase_request_item_id")
        )
    return rfq.lines.select_related(
        "purchase_request_item", "material", "unit_of_measure"
    ).order_by("sort_order", "created_at", "purchase_request_item_id")


def latest_definition(rfq: RequestForQuotation, version_number: int):
    return (
        rfq.scope_definitions.filter(version_number=version_number)
        .order_by("-revision_number")
        .first()
    )


def _quantity(value: object) -> Decimal:
    try:
        if isinstance(value, (float, bool)):
            raise TypeError
        number = Decimal(str(value))
        if not number.is_finite() or number <= 0:
            raise ValueError
        DecimalValidator(18, 4)(number)
        return number.quantize(Decimal("0.0001"))
    except (TypeError, ValueError, InvalidOperation, ValidationError) as exc:
        raise ValueError("مقدار باید مثبت و با حداکثر چهار رقم اعشار باشد.") from exc


def normalize_scope_payload(
    *,
    organization: Organization,
    rfq: RequestForQuotation,
    version_number: int,
    scopes: list[dict],
) -> dict:
    """Validate exact chosen source quantities and existing line/lot semantics."""
    pr = PurchaseRequest.objects.select_for_update().get(
        pk=rfq.purchase_request_id, organization=organization
    )
    if pr.status != "approved" or pr.project_id != rfq.project_id:
        raise ValueError("دامنه خرید باید از درخواست خرید تأییدشده همین پروژه باشد.")
    lines = list(source_lines(rfq, version_number))
    by_pr = {str(row.purchase_request_item_id): row for row in lines}
    source = []
    for line in lines:
        item = line.purchase_request_item
        if (
            line.organization_id != organization.pk
            or item.organization_id != organization.pk
            or item.purchase_request_id != pr.pk
            or line.material_id != item.material_id
            or line.unit_of_measure_id != item.unit_of_measure_id
            or line.quantity > item.quantity
        ):
            raise ValueError("ردیف استعلام با درخواست خرید مبنا هم‌خوان نیست.")
        source.append(
            [
                str(item.pk),
                str(line.material_id),
                str(line.unit_of_measure_id),
                str(_quantity(line.quantity)),
                line.description,
                line.sort_order,
            ]
        )
    if not isinstance(scopes, list) or not 1 <= len(scopes) <= 100:
        raise ValueError("حداقل یک دامنه خرید را صریحاً تعریف کنید.")
    normalized, codes = [], set()
    for row in scopes:
        if not isinstance(row, dict):
            raise ValueError("تعریف دامنه خرید معتبر نیست.")  # noqa: TRY004
        code = str(row.get("scope_code", "")).strip()
        kind = row.get("scope_type")
        quantity = _quantity(row.get("required_quantity"))
        if not code or len(code) > 80 or code in codes or kind not in ("line", "lot"):
            raise ValueError("نام دامنه باید یکتا باشد؛ نوع ردیف یا بسته را مشخص کنید.")
        codes.add(code)
        flags = {
            key: row.get(key)
            for key in (
                "independently_awardable",
                "allows_split_award",
                "allows_alternates",
            )
        }
        if any(type(value) is not bool for value in flags.values()):
            raise ValueError(
                "مستقل بودن انتخاب، تقسیم انتخاب و پیشنهاد جایگزین را صریحاً مشخص کنید."
            )
        if (
            kind == "line"
            and flags["allows_split_award"]
            and not flags["independently_awardable"]
        ):
            raise ValueError("تقسیم انتخاب ردیف فقط برای ردیف مستقل مجاز است.")
        selected = row.get("lines")
        if (
            not isinstance(selected, list)
            or not selected
            or (kind == "line" and len(selected) != 1)
        ):
            raise ValueError("برای ردیف یک قلم و برای بسته اقلام عضو را انتخاب کنید.")
        members, seen = [], set()
        for member in selected:
            if not isinstance(member, dict):
                raise ValueError("اقلام دامنه خرید معتبر نیستند.")  # noqa: TRY004
            identifier = str(member.get("purchase_request_item_id", ""))
            line = by_pr.get(identifier)
            amount = _quantity(member.get("quantity"))
            if line is None or identifier in seen or amount > line.quantity:
                raise ValueError(
                    "اقلام باید یکتا، متعلق به همین استعلام و حداکثر به مقدار ردیف استعلام باشند."
                )
            seen.add(identifier)
            members.append(
                {"purchase_request_item_id": identifier, "quantity": str(amount)}
            )
        if kind == "line":
            line = by_pr[members[0]["purchase_request_item_id"]]
            if quantity != Decimal(members[0]["quantity"]):
                raise ValueError(
                    "مقدار دامنه ردیف باید با مقدار انتخاب‌شده همان قلم برابر باشد."
                )
            unit = str(line.unit_of_measure_id)
        else:
            unit = str(row.get("unit_of_measure_id", ""))
            try:
                valid_unit = UnitOfMeasure.objects.filter(
                    pk=unit,
                    organization=organization,
                    is_active=True,
                    archived_at__isnull=True,
                ).exists()
            except (ValueError, ValidationError):
                valid_unit = False
            if not valid_unit:
                raise ValueError("واحد معتبر بسته را از واحدهای همین شرکت انتخاب کنید.")
        normalized.append(
            {
                "scope_code": code,
                "scope_type": kind,
                "required_quantity": str(quantity),
                "unit_of_measure_id": unit,
                "lines": sorted(members, key=lambda x: x["purchase_request_item_id"]),
                **flags,
            }
        )
    return {
        "purchase_request_id": str(pr.pk),
        "version_number": version_number,
        "source_fingerprint": fingerprint(sorted(source, key=lambda row: row[0])),
        "scopes": sorted(normalized, key=lambda x: x["scope_code"]),
    }


@transaction.atomic
def define_rfq_commercial_scope(
    *,
    organization: Organization,
    actor: User,
    rfq: RequestForQuotation,
    version_number: int,
    scopes: list[dict],
    expected_revision: int,
    idempotency_key: str,
    expected_source_fingerprint: str | None = None,
) -> RFQCommercialScopeDefinition:
    locked = _locked_rfq(organization=organization, rfq=rfq)
    _permission(
        organization=organization,
        actor=actor,
        permission=P.RFQS_CHANGE if version_number == 1 else P.RFQS_ADDENDUM,
        project=locked.project,
        message="اجازه تعریف دامنه خرید این استعلام را ندارید.",
    )
    if (
        type(version_number) is not int
        or version_number < 1
        or type(expected_revision) is not int
        or expected_revision < 0
    ):
        raise ValueError("نسخه فرم معتبر نیست؛ صفحه را دوباره باز کنید.")
    key = idempotency_key.strip()
    if not key or len(key) > 128:
        raise ValueError("اطلاعات ثبت فرم معتبر نیست؛ صفحه را دوباره باز کنید.")
    payload = normalize_scope_payload(
        organization=organization,
        rfq=locked,
        version_number=version_number,
        scopes=scopes,
    )
    digest = fingerprint(payload)
    if (
        expected_source_fingerprint is not None
        and expected_source_fingerprint != payload["source_fingerprint"]
    ):
        raise ValueError("اقلام مبنا هم‌زمان تغییر کرده‌اند؛ صفحه را دوباره باز کنید.")
    existing = locked.scope_definitions.filter(idempotency_key=key).first()
    if existing:
        if existing.payload_fingerprint != digest:
            raise ValueError("این ارسال قبلاً با اطلاعات متفاوت ثبت شده است.")
        return existing
    if (
        locked.status not in ("draft", "submitted_for_issue", "issued")
        or version_number != locked.current_version_number + 1
    ):
        raise ValueError("تعریف دامنه فقط برای نسخه صادرنشده بعدی مجاز است.")
    latest = latest_definition(locked, version_number)
    if expected_revision != (latest.revision_number if latest else 0):
        raise ValueError(
            "تعریف دامنه تغییر کرده است؛ صفحه را تازه کنید و دوباره بررسی کنید."
        )
    definition = RFQCommercialScopeDefinition.objects.create(
        organization=organization,
        rfq=locked,
        version_number=version_number,
        revision_number=expected_revision + 1,
        payload=payload,
        payload_fingerprint=digest,
        idempotency_key=key,
        created_by=actor,
    )
    record_audit_event(
        action=AuditAction.RFQ_COMMERCIAL_SCOPE_DEFINED,
        entity_type="rfq_commercial_scope_definition",
        entity_id=definition.pk,
        organization=organization,
        actor=actor,
        metadata={
            "rfq_id": str(locked.pk),
            "version_number": version_number,
            "revision_number": definition.revision_number,
            "fingerprint": digest,
            "previous_definition_id": str(latest.pk) if latest else None,
        },
    )
    return definition


def definition_for_issue(
    *, organization: Organization, rfq: RequestForQuotation, existing=None
):
    definition = (
        existing.commercial_scope_definition
        if existing
        else latest_definition(rfq, rfq.current_version_number + 1)
    )
    if definition is None:
        if rfq.commercial_scope_required:
            raise ValueError(
                "پیش از صدور، دامنه خرید و اقلام آن را صریحاً تعریف و ثبت کنید."
            )
        return None
    payload = normalize_scope_payload(
        organization=organization,
        rfq=rfq,
        version_number=definition.version_number,
        scopes=definition.payload["scopes"],
    )
    if (
        payload != definition.payload
        or fingerprint(payload) != definition.payload_fingerprint
    ):
        raise ValueError(
            "اقلام مبنا تغییر کرده‌اند؛ دامنه خرید را دوباره بررسی و ثبت کنید."
        )
    return definition


def freeze_commercial_scopes(*, version: RequestForQuotationVersion) -> None:
    definition = version.commercial_scope_definition
    if not definition:
        return
    by_pr = {str(line.purchase_request_item_id): line for line in version.lines.all()}
    for row in definition.payload["scopes"]:
        line = (
            by_pr[row["lines"][0]["purchase_request_item_id"]]
            if row["scope_type"] == "line"
            else None
        )
        RFQCommercialScope.objects.create(
            organization_id=version.organization_id,
            rfq_version=version,
            rfq_version_line=line,
            scope_type=row["scope_type"],
            scope_code=row["scope_code"],
            required_quantity=Decimal(row["required_quantity"]),
            unit_of_measure_id=row["unit_of_measure_id"],
            independently_awardable=row["independently_awardable"],
            allows_split_award=row["allows_split_award"],
            allows_alternates=row["allows_alternates"],
            created_by=definition.created_by,
        )
