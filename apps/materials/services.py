from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_UP, Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max, Q, QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.materials.models import (
    Material,
    MaterialAlias,
    MaterialAttributeDefinition,
    MaterialAttributeDefinitionVersion,
    MaterialAttributeImportRow,
    MaterialAttributeImportRun,
    MaterialAttributeValue,
    MaterialAttributeValueType,
    MaterialCategory,
    MaterialDuplicateCandidate,
    MaterialPriceObservation,
    MaterialRelationship,
    MaterialSupersession,
    MaterialTechnicalApproval,
    MaterialTechnicalApprovalStatus,
    QuantityConversionSnapshot,
    QuantityRoundingMode,
    QuantityRoundingPolicyVersion,
    UnitCategory,
    UnitConversionVersion,
    UnitDimension,
    UnitFamily,
    UnitOfMeasure,
)
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import (
    BusinessPermissionCode,
    Organization,
    OrganizationStatus,
)
from core.identifiers import canonicalize_upper_identifier


def _require_active_management_access(
    *,
    organization: Organization,
    actor: User,
    permission: BusinessPermissionCode,
) -> None:
    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied("ورود به حساب کاربری الزامی است.")
    if organization.status != OrganizationStatus.ACTIVE or organization.deleted_at:
        raise PermissionDenied("سازمان فعال نیست.")
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        message="اجازه انجام این عملیات روی اطلاعات مصالح را ندارید.",
    )


@transaction.atomic
def create_unit_of_measure(
    *,
    organization: Organization,
    actor: User,
    code: str,
    name: str,
    symbol: str,
    category: str,
    decimal_places: int = 0,
) -> UnitOfMeasure:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.UNITS_CREATE,
    )
    if category not in UnitCategory.values:
        raise ValueError("دسته‌بندی واحد اندازه‌گیری معتبر نیست.")
    unit = UnitOfMeasure(
        organization=organization,
        code=code,
        name=name.strip(),
        symbol=symbol,
        category=category,
        decimal_places=decimal_places,
        created_by=actor,
        updated_by=actor,
    )
    try:
        unit.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError("واحدی با این کد یا نماد از قبل وجود دارد.") from exc
    family = UnitFamily.objects.create(
        organization=organization,
        code=f"ISO-{unit.pk.hex[:12].upper()}",
        name=f"{unit.name} isolated",
        dimension=(
            category if category in UnitDimension.values else UnitDimension.ISOLATED
        ),
        base_unit=unit,
        created_by=actor,
    )
    UnitOfMeasure.objects.filter(pk=unit.pk).update(family=family)
    unit.family = family
    record_audit_event(
        action=AuditAction.UNIT_OF_MEASURE_CREATED,
        entity_type="unit_of_measure",
        entity_id=unit.pk,
        organization=organization,
        actor=actor,
        metadata={"code": unit.code, "symbol": unit.symbol},
    )
    return unit


@transaction.atomic
def configure_unit_family(
    *,
    organization: Organization,
    actor: User,
    base_unit: UnitOfMeasure,
    code: str,
    name: str,
    dimension: str,
) -> UnitFamily:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.UOM_CONVERSIONS_MANAGE,
    )
    if dimension not in UnitDimension.values or dimension == UnitDimension.ISOLATED:
        raise ValueError("بعد قابل تبدیل معتبر نیست.")
    unit = UnitOfMeasure.objects.select_for_update().get(pk=base_unit.pk)
    if unit.organization_id != organization.pk:
        raise PermissionDenied("واحد مبنا متعلق به این سازمان نیست.")
    family = UnitFamily.objects.select_for_update().get(pk=unit.family_id)
    if family.base_unit_id != unit.pk or family.units.exclude(pk=unit.pk).exists():
        raise ValueError("خانواده موجود دیگر قابل بازپیکربندی نیست.")
    family.code = code
    family.name = name.strip()
    family.dimension = dimension
    family.full_clean()
    family.save(update_fields=["code", "name", "dimension", "updated_at"])
    record_audit_event(
        action=AuditAction.UOM_FAMILY_CONFIGURED,
        entity_type="unit_family",
        entity_id=family.pk,
        organization=organization,
        actor=actor,
        metadata={"code": family.code, "dimension": family.dimension},
    )
    return family


@transaction.atomic
def assign_unit_to_family(
    *,
    organization: Organization,
    actor: User,
    unit: UnitOfMeasure,
    family: UnitFamily,
) -> UnitOfMeasure:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.UOM_CONVERSIONS_MANAGE,
    )
    locked = UnitOfMeasure.objects.select_for_update().get(pk=unit.pk)
    if (
        locked.organization_id != organization.pk
        or family.organization_id != organization.pk
    ):
        raise PermissionDenied("واحد و خانواده متعلق به این سازمان نیستند.")
    old_family = UnitFamily.objects.select_for_update().get(pk=locked.family_id)
    if locked.family_id and (
        old_family.base_unit_id != locked.pk
        or old_family.units.exclude(pk=locked.pk).exists()
        or old_family.conversion_versions.exists()
    ):
        raise ValueError("عضویت فعلی واحد قابل جایگزینی نیست.")
    locked.family = family
    locked.save(update_fields=["family", "updated_at"])
    if old_family.pk != family.pk:
        old_family.delete()
    return locked


@transaction.atomic
def create_unit_conversion_version(
    *,
    organization: Organization,
    actor: User,
    unit: UnitOfMeasure,
    factor_to_base: Decimal,
    effective_from: datetime,
    source_reference: str,
    effective_until: datetime | None = None,
) -> UnitConversionVersion:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.UOM_CONVERSIONS_MANAGE,
    )
    locked = UnitOfMeasure.objects.select_for_update().get(pk=unit.pk)
    if locked.organization_id != organization.pk or locked.family_id is None:
        raise PermissionDenied("واحد متعلق به خانواده معتبر این سازمان نیست.")
    family = UnitFamily.objects.select_for_update().get(pk=locked.family_id)
    if factor_to_base <= 0:
        raise ValueError("ضریب تبدیل باید مثبت باشد.")
    overlaps = locked.conversion_versions.filter(
        Q(effective_until__isnull=True) | Q(effective_until__gt=effective_from)
    )
    if effective_until is not None:
        overlaps = overlaps.filter(effective_from__lt=effective_until)
    if overlaps.exists():
        raise ValueError("بازه نسخه ضریب تبدیل با نسخه موجود هم‌پوشانی دارد.")
    version_number = (
        locked.conversion_versions.aggregate(latest=Max("version"))["latest"] or 0
    ) + 1
    version = UnitConversionVersion.objects.create(
        organization=organization,
        family=family,
        unit=locked,
        version=version_number,
        factor_to_base=factor_to_base,
        effective_from=effective_from,
        effective_until=effective_until,
        source_reference=source_reference,
        created_by=actor,
    )
    record_audit_event(
        action=AuditAction.UOM_CONVERSION_VERSION_CREATED,
        entity_type="unit_conversion_version",
        entity_id=version.pk,
        organization=organization,
        actor=actor,
        metadata={"unit_id": str(unit.pk), "version": version.version},
    )
    return version


@transaction.atomic
def create_quantity_rounding_policy_version(
    *,
    organization: Organization,
    actor: User,
    code: str,
    scale: int,
    mode: str,
    effective_from: datetime,
    effective_until: datetime | None = None,
) -> QuantityRoundingPolicyVersion:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.UOM_ROUNDING_MANAGE,
    )
    if mode not in QuantityRoundingMode.values or scale < 0 or scale > 12:
        raise ValueError("سیاست گرد کردن کمیت معتبر نیست.")
    normalized_code = canonicalize_upper_identifier(code)
    overlapping = QuantityRoundingPolicyVersion.objects.filter(
        organization=organization,
        code=normalized_code,
    ).filter(Q(effective_until__isnull=True) | Q(effective_until__gt=effective_from))
    if effective_until is not None:
        overlapping = overlapping.filter(effective_from__lt=effective_until)
    if overlapping.exists():
        raise ValueError("بازه سیاست گرد کردن هم‌پوشانی دارد.")
    next_version = (
        QuantityRoundingPolicyVersion.objects.filter(
            organization=organization, code=normalized_code
        ).aggregate(latest=Max("version"))["latest"]
        or 0
    ) + 1
    policy = QuantityRoundingPolicyVersion.objects.create(
        organization=organization,
        code=normalized_code,
        version=next_version,
        scale=scale,
        mode=mode,
        effective_from=effective_from,
        effective_until=effective_until,
        created_by=actor,
    )
    record_audit_event(
        action=AuditAction.UOM_ROUNDING_POLICY_CREATED,
        entity_type="quantity_rounding_policy_version",
        entity_id=policy.pk,
        organization=organization,
        actor=actor,
        metadata={"code": policy.code, "version": policy.version},
    )
    return policy


def _effective_conversion(
    *, unit: UnitOfMeasure, at: datetime
) -> UnitConversionVersion | None:
    if unit.family.base_unit_id == unit.pk:
        return None
    version = (
        unit.conversion_versions.filter(effective_from__lte=at)
        .filter(Q(effective_until__isnull=True) | Q(effective_until__gt=at))
        .order_by("-effective_from")
        .first()
    )
    if version is None:
        raise ValueError("نسخه مؤثر ضریب تبدیل واحد موجود نیست.")
    return version


ROUNDING_MAP = {
    QuantityRoundingMode.HALF_UP: ROUND_HALF_UP,
    QuantityRoundingMode.HALF_EVEN: ROUND_HALF_EVEN,
    QuantityRoundingMode.DOWN: ROUND_DOWN,
    QuantityRoundingMode.UP: ROUND_UP,
}


@transaction.atomic
def convert_quantity(
    *,
    organization: Organization,
    actor: User,
    quantity: Decimal,
    input_unit: UnitOfMeasure,
    output_unit: UnitOfMeasure,
    context_key: str,
    at: datetime | None = None,
    rounding_policy: QuantityRoundingPolicyVersion | None = None,
) -> QuantityConversionSnapshot:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.UOM_CONVERT,
    )
    converted_at = at or timezone.now()
    units = {
        item.pk: item
        for item in UnitOfMeasure.objects.select_related("family").filter(
            pk__in=[input_unit.pk, output_unit.pk], organization=organization
        )
    }
    if len(units) != len({input_unit.pk, output_unit.pk}):
        raise PermissionDenied("واحدهای تبدیل متعلق به این سازمان نیستند.")
    source, target = units[input_unit.pk], units[output_unit.pk]
    if source.family_id is None or source.family_id != target.family_id:
        raise ValueError("تبدیل فقط در یک خانواده و بعد سازگار مجاز است.")
    source_version = _effective_conversion(unit=source, at=converted_at)
    target_version = _effective_conversion(unit=target, at=converted_at)
    source_factor = source_version.factor_to_base if source_version else Decimal(1)
    target_factor = target_version.factor_to_base if target_version else Decimal(1)
    unrounded = quantity * source_factor / target_factor
    result = unrounded
    if rounding_policy is not None:
        if (
            rounding_policy.organization_id != organization.pk
            or rounding_policy.effective_from > converted_at
            or (
                rounding_policy.effective_until
                and rounding_policy.effective_until <= converted_at
            )
        ):
            raise PermissionDenied("سیاست گرد کردن مؤثر متعلق به این سازمان نیست.")
        quantum = Decimal(1).scaleb(-rounding_policy.scale)
        result = unrounded.quantize(quantum, rounding=ROUNDING_MAP[rounding_policy.mode])
    else:
        normalized = unrounded.normalize()
        required_places = max(0, -normalized.as_tuple().exponent)
        if required_places > target.decimal_places:
            raise ValueError("سیاست گرد کردن موردنیاز تنظیم نشده است.")
    snapshot = QuantityConversionSnapshot.objects.create(
        organization=organization,
        context_key=context_key.strip(),
        input_unit=source,
        output_unit=target,
        input_conversion_version=source_version,
        output_conversion_version=target_version,
        rounding_policy_version=rounding_policy,
        input_quantity=quantity,
        unrounded_result=unrounded,
        output_quantity=result,
        converted_at=converted_at,
        created_by=actor,
    )
    record_audit_event(
        action=AuditAction.UOM_CONVERSION_APPLIED,
        entity_type="quantity_conversion_snapshot",
        entity_id=snapshot.pk,
        organization=organization,
        actor=actor,
        metadata={
            "context_key": snapshot.context_key,
            "input_unit_id": str(source.pk),
            "output_unit_id": str(target.pk),
        },
    )
    return snapshot


@transaction.atomic
def create_material_attribute_definition(
    *,
    organization: Organization,
    actor: User,
    category: MaterialCategory,
    code: str,
    name: str,
    value_type: str,
    allowed_operators: list[str],
    effective_from: datetime,
    choice_values: list[str] | None = None,
) -> MaterialAttributeDefinition:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.MATERIAL_ATTRIBUTE_DEFINITIONS_MANAGE,
    )
    if category.organization_id != organization.pk:
        raise PermissionDenied("دسته‌بندی ویژگی متعلق به این سازمان نیست.")
    definition = MaterialAttributeDefinition.objects.create(
        organization=organization,
        category=category,
        code=code,
        name=name,
        created_by=actor,
    )
    create_material_attribute_definition_version(
        organization=organization,
        actor=actor,
        definition=definition,
        value_type=value_type,
        allowed_operators=allowed_operators,
        effective_from=effective_from,
        choice_values=choice_values or [],
    )
    return definition


@transaction.atomic
def create_material_attribute_definition_version(
    *,
    organization: Organization,
    actor: User,
    definition: MaterialAttributeDefinition,
    value_type: str,
    allowed_operators: list[str],
    effective_from: datetime,
    choice_values: list[str] | None = None,
    effective_until: datetime | None = None,
) -> MaterialAttributeDefinitionVersion:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.MATERIAL_ATTRIBUTE_DEFINITIONS_MANAGE,
    )
    locked = MaterialAttributeDefinition.objects.select_for_update().get(
        pk=definition.pk
    )
    if locked.organization_id != organization.pk:
        raise PermissionDenied("تعریف ویژگی متعلق به این سازمان نیست.")
    if value_type not in MaterialAttributeValueType.values:
        raise ValueError("نوع تعریف ویژگی معتبر نیست.")
    overlaps = locked.versions.filter(
        Q(effective_until__isnull=True) | Q(effective_until__gt=effective_from)
    )
    if effective_until is not None:
        overlaps = overlaps.filter(effective_from__lt=effective_until)
    if overlaps.exists():
        raise ValueError("بازه نسخه تعریف ویژگی با نسخه موجود هم‌پوشانی دارد.")
    version_number = (locked.versions.aggregate(latest=Max("version"))["latest"] or 0) + 1
    version = MaterialAttributeDefinitionVersion.objects.create(
        definition=locked,
        version=version_number,
        value_type=value_type,
        allowed_operators=allowed_operators,
        choice_values=choice_values or [],
        effective_from=effective_from,
        effective_until=effective_until,
        created_by=actor,
    )
    record_audit_event(
        action=AuditAction.MATERIAL_ATTRIBUTE_DEFINITION_VERSION_CREATED,
        entity_type="material_attribute_definition_version",
        entity_id=version.pk,
        organization=organization,
        actor=actor,
        metadata={"definition_id": str(locked.pk), "version": version.version},
    )
    return version


def _effective_attribute_definition_version(
    *, definition: MaterialAttributeDefinition, at: datetime
) -> MaterialAttributeDefinitionVersion:
    version = (
        definition.versions.filter(effective_from__lte=at)
        .filter(Q(effective_until__isnull=True) | Q(effective_until__gt=at))
        .order_by("-effective_from")
        .first()
    )
    if version is None:
        raise ValueError("نسخه مؤثر تعریف ویژگی مصالح موجود نیست.")
    return version


@transaction.atomic
def record_material_attribute_value(
    *,
    organization: Organization,
    actor: User,
    material: Material,
    definition: MaterialAttributeDefinition,
    definition_version: MaterialAttributeDefinitionVersion,
    value: object,
    source_reference: str = "",
) -> MaterialAttributeValue:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.MATERIAL_ATTRIBUTES_APPLY,
    )
    locked_material = Material.objects.select_for_update().get(pk=material.pk)
    if (
        locked_material.organization_id != organization.pk
        or definition.organization_id != organization.pk
        or definition_version.definition_id != definition.pk
    ):
        raise PermissionDenied("مصالح و تعریف ویژگی متعلق به این سازمان نیستند.")
    value_record = MaterialAttributeValue.objects.create(
        organization=organization,
        material=locked_material,
        definition=definition,
        definition_version=definition_version,
        value=value,
        normalized_value="",
        source_reference=source_reference.strip(),
        created_by=actor,
    )
    record_audit_event(
        action=AuditAction.MATERIAL_ATTRIBUTE_VALUE_RECORDED,
        entity_type="material_attribute_value",
        entity_id=value_record.pk,
        organization=organization,
        actor=actor,
        metadata={
            "material_id": str(locked_material.pk),
            "definition_id": str(definition.pk),
            "definition_version": definition_version.version,
        },
    )
    return value_record


@transaction.atomic
def import_material_attribute_rows(
    *,
    organization: Organization,
    actor: User,
    idempotency_key: str,
    source_label: str,
    rows: Iterable[Mapping[str, object]],
) -> MaterialAttributeImportRun:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.MATERIAL_ATTRIBUTES_IMPORT,
    )
    key = idempotency_key.strip()
    if not key or not source_label.strip():
        raise ValueError("کلید تکرارنشدنی و منبع درون‌ریزی الزامی است.")
    existing = MaterialAttributeImportRun.objects.filter(
        organization=organization, idempotency_key=key
    ).first()
    if existing is not None:
        return existing
    run = MaterialAttributeImportRun.objects.create(
        organization=organization,
        idempotency_key=key,
        source_label=source_label.strip(),
        created_by=actor,
    )
    now = timezone.now()
    for row_number, row in enumerate(rows, start=1):
        material_identifier = str(row.get("material_identifier", "")).strip()
        definition_code = str(row.get("definition_code", "")).strip()
        supplied_value = row.get("value")
        error = ""
        accepted_value = None
        try:
            material = resolve_material_identifier(
                organization=organization, identifier=material_identifier
            )
            definition = MaterialAttributeDefinition.objects.get(
                organization=organization,
                category=material.category,
                code=canonicalize_upper_identifier(definition_code),
                is_active=True,
                archived_at__isnull=True,
            )
            version = _effective_attribute_definition_version(definition=definition, at=now)
            accepted_value = record_material_attribute_value(
                organization=organization,
                actor=actor,
                material=material,
                definition=definition,
                definition_version=version,
                value=supplied_value,
                source_reference=f"import:{key}:{row_number}",
            )
        except (Material.DoesNotExist, MaterialAttributeDefinition.DoesNotExist, ValueError, ValidationError, PermissionDenied) as exc:
            error = str(exc)
        MaterialAttributeImportRow.objects.create(
            run=run,
            row_number=row_number,
            material_identifier=material_identifier,
            definition_code=definition_code,
            supplied_value=supplied_value,
            accepted_value=accepted_value,
            error=error,
        )
        run.total_rows += 1
        if accepted_value is None:
            run.rejected_rows += 1
        else:
            run.accepted_rows += 1
    run.save(update_fields=["total_rows", "accepted_rows", "rejected_rows", "updated_at"])
    record_audit_event(
        action=AuditAction.MATERIAL_ATTRIBUTE_IMPORT_RECORDED,
        entity_type="material_attribute_import_run",
        entity_id=run.pk,
        organization=organization,
        actor=actor,
        metadata={"accepted": run.accepted_rows, "rejected": run.rejected_rows},
    )
    return run


@transaction.atomic
def record_material_price_observation(
    *,
    organization: Organization,
    actor: User,
    material: Material,
    unit: UnitOfMeasure,
    amount: Decimal,
    currency: str,
    source_reference: str,
    observed_at: datetime,
    effective_from: datetime,
    effective_until: datetime | None = None,
) -> MaterialPriceObservation:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.MATERIAL_PRICE_OBSERVATIONS_RECORD,
    )
    if material.organization_id != organization.pk or unit.organization_id != organization.pk:
        raise PermissionDenied("مصالح و واحد مشاهده قیمت متعلق به این سازمان نیستند.")
    observation = MaterialPriceObservation.objects.create(
        organization=organization,
        material=material,
        unit=unit,
        amount=amount,
        currency=currency,
        source_reference=source_reference,
        observed_at=observed_at,
        effective_from=effective_from,
        effective_until=effective_until,
        created_by=actor,
    )
    record_audit_event(
        action=AuditAction.MATERIAL_PRICE_OBSERVATION_RECORDED,
        entity_type="material_price_observation",
        entity_id=observation.pk,
        organization=organization,
        actor=actor,
        metadata={"material_id": str(material.pk), "currency": observation.currency},
    )
    return observation


@transaction.atomic
def record_material_relationship(*, organization: Organization, actor: User, source: Material, candidate: Material, relationship_type: str, reason: str) -> MaterialRelationship:
    _require_active_management_access(organization=organization, actor=actor, permission=BusinessPermissionCode.MATERIAL_RELATIONSHIPS_MANAGE)
    if source.organization_id != organization.pk or candidate.organization_id != organization.pk:
        raise PermissionDenied("رابطه مصالح باید Tenant-local باشد.")
    relation = MaterialRelationship.objects.create(organization=organization, source=source, candidate=candidate, relationship_type=relationship_type, reason=reason, created_by=actor)
    record_audit_event(action=AuditAction.MATERIAL_RELATIONSHIP_RECORDED, entity_type="material_relationship", entity_id=relation.pk, organization=organization, actor=actor, metadata={"source_id": str(source.pk), "candidate_id": str(candidate.pk)})
    return relation


@transaction.atomic
def create_material_technical_revision(*, organization: Organization, actor: User, material: Material, scope_project=None) -> MaterialTechnicalApproval:
    _require_active_management_access(organization=organization, actor=actor, permission=BusinessPermissionCode.MATERIAL_TECHNICAL_SUBMIT)
    if material.organization_id != organization.pk or (scope_project and scope_project.organization_id != organization.pk):
        raise PermissionDenied("مصالح و دامنه بررسی فنی باید Tenant-local باشند.")
    revision = (material.technical_approvals.aggregate(latest=Max("revision"))["latest"] or 0) + 1
    item = MaterialTechnicalApproval.objects.create(organization=organization, material=material, revision=revision, status=MaterialTechnicalApprovalStatus.DRAFT, scope_project=scope_project)
    record_audit_event(action=AuditAction.MATERIAL_TECHNICAL_STATUS_CHANGED, entity_type="material_technical_approval", entity_id=item.pk, organization=organization, actor=actor, metadata={"status": item.status, "revision": revision})
    return item


@transaction.atomic
def transition_material_technical_revision(*, organization: Organization, actor: User, approval: MaterialTechnicalApproval, target_status: str, reason: str = "") -> MaterialTechnicalApproval:
    permission_by_target = {MaterialTechnicalApprovalStatus.REVIEW: BusinessPermissionCode.MATERIAL_TECHNICAL_REVIEW, MaterialTechnicalApprovalStatus.APPROVED: BusinessPermissionCode.MATERIAL_TECHNICAL_APPROVE, MaterialTechnicalApprovalStatus.REJECTED: BusinessPermissionCode.MATERIAL_TECHNICAL_APPROVE}
    if target_status not in permission_by_target:
        raise ValueError("گذار بررسی فنی معتبر نیست.")
    _require_active_management_access(organization=organization, actor=actor, permission=permission_by_target[target_status])
    locked = MaterialTechnicalApproval.objects.select_for_update().get(pk=approval.pk)
    if locked.organization_id != organization.pk:
        raise PermissionDenied("بررسی فنی متعلق به این سازمان نیست.")
    valid = {MaterialTechnicalApprovalStatus.DRAFT: {MaterialTechnicalApprovalStatus.REVIEW}, MaterialTechnicalApprovalStatus.REVIEW: {MaterialTechnicalApprovalStatus.APPROVED, MaterialTechnicalApprovalStatus.REJECTED}}
    if target_status not in valid.get(locked.status, set()):
        raise ValueError("گذار وضعیت بررسی فنی مجاز نیست.")
    if (
        target_status in {MaterialTechnicalApprovalStatus.APPROVED, MaterialTechnicalApprovalStatus.REJECTED}
        and locked.submitted_by_id == actor.pk
    ):
        raise PermissionDenied("تصمیم فنی نیازمند عضو مجاز متفاوت از ارسال‌کننده است.")
    if target_status in {MaterialTechnicalApprovalStatus.APPROVED, MaterialTechnicalApprovalStatus.REJECTED} and not reason.strip():
        raise ValueError("دلیل تصمیم فنی الزامی است.")
    superseded_count = 0
    if target_status == MaterialTechnicalApprovalStatus.APPROVED:
        superseded_count = MaterialTechnicalApproval.objects.filter(
            material=locked.material,
            scope_project_id=locked.scope_project_id,
            status=MaterialTechnicalApprovalStatus.APPROVED,
        ).exclude(pk=locked.pk).update(status=MaterialTechnicalApprovalStatus.SUPERSEDED)
    MaterialTechnicalApproval.objects.filter(pk=locked.pk).update(status=target_status, submitted_by=actor if target_status == MaterialTechnicalApprovalStatus.REVIEW else locked.submitted_by, reviewed_by=actor if target_status == MaterialTechnicalApprovalStatus.REVIEW else locked.reviewed_by, decided_by=actor if target_status in {MaterialTechnicalApprovalStatus.APPROVED, MaterialTechnicalApprovalStatus.REJECTED} else locked.decided_by, reason=reason.strip())
    locked.refresh_from_db()
    record_audit_event(action=AuditAction.MATERIAL_TECHNICAL_STATUS_CHANGED, entity_type="material_technical_approval", entity_id=locked.pk, organization=organization, actor=actor, metadata={"status": target_status, "reason": reason.strip(), "superseded_revision_count": superseded_count})
    return locked


def get_organization_units(
    *, user: User, organization: Organization
) -> QuerySet[UnitOfMeasure]:
    require_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.UNITS_VIEW,
        message="اجازه مشاهده واحدهای اندازه‌گیری این سازمان را ندارید.",
    )
    return UnitOfMeasure.objects.filter(
        organization=organization, archived_at__isnull=True
    )


@transaction.atomic
def archive_unit_of_measure(
    *, organization: Organization, actor: User, unit: UnitOfMeasure
) -> UnitOfMeasure:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.UNITS_ARCHIVE,
    )
    locked_unit = UnitOfMeasure.objects.select_for_update().get(pk=unit.pk)
    if locked_unit.organization_id != organization.id:
        raise PermissionDenied("واحد اندازه‌گیری متعلق به این سازمان نیست.")
    if locked_unit.archived_at is not None:
        raise ValueError("واحد اندازه‌گیری از قبل بایگانی شده است.")
    if locked_unit.materials.filter(archived_at__isnull=True).exists():
        raise ValueError("واحد مورد استفاده مصالح فعال قابل بایگانی نیست.")
    locked_unit.archived_at = timezone.now()
    locked_unit.is_active = False
    locked_unit.updated_by = actor
    locked_unit.save(
        update_fields=["archived_at", "is_active", "updated_by", "updated_at"]
    )
    record_audit_event(
        action=AuditAction.UNIT_OF_MEASURE_ARCHIVED,
        entity_type="unit_of_measure",
        entity_id=locked_unit.pk,
        organization=organization,
        actor=actor,
        metadata={"code": locked_unit.code},
    )
    return locked_unit


def _validate_category_parent(category: MaterialCategory) -> None:
    parent = category.parent
    while parent is not None:
        if parent.pk == category.pk:
            raise ValueError("ساختار دسته‌بندی مصالح نمی‌تواند شامل چرخه باشد.")
        parent = parent.parent


@transaction.atomic
def create_material_category(
    *,
    organization: Organization,
    actor: User,
    code: str,
    name: str,
    parent: MaterialCategory | None = None,
) -> MaterialCategory:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.MATERIAL_CATEGORIES_CREATE,
    )
    if parent and parent.organization_id != organization.id:
        raise PermissionDenied("دسته‌بندی والد متعلق به این سازمان نیست.")
    category = MaterialCategory(
        organization=organization,
        code=code,
        name=name,
        parent=parent,
        created_by=actor,
        updated_by=actor,
    )
    try:
        category.full_clean()
        _validate_category_parent(category)
        category.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError("دسته‌بندی مصالح با این کد از قبل وجود دارد.") from exc
    record_audit_event(
        action=AuditAction.MATERIAL_CATEGORY_CREATED,
        entity_type="material_category",
        entity_id=category.pk,
        organization=organization,
        actor=actor,
        metadata={"code": category.code},
    )
    return category


@transaction.atomic
def update_material_category(
    *,
    organization: Organization,
    actor: User,
    category: MaterialCategory,
    code: str,
    name: str,
    parent: MaterialCategory | None = None,
) -> MaterialCategory:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.MATERIAL_CATEGORIES_CHANGE,
    )
    locked_category = MaterialCategory.objects.select_for_update().get(pk=category.pk)
    if locked_category.organization_id != organization.id:
        raise PermissionDenied("دسته‌بندی مصالح متعلق به این سازمان نیست.")
    if locked_category.archived_at is not None:
        raise ValueError("دسته‌بندی مصالح بایگانی‌شده قابل به‌روزرسانی نیست.")
    if parent and parent.organization_id != organization.id:
        raise PermissionDenied("دسته‌بندی والد متعلق به این سازمان نیست.")
    locked_category.code, locked_category.name, locked_category.parent = (
        code,
        name,
        parent,
    )
    locked_category.updated_by = actor
    try:
        locked_category.full_clean()
        _validate_category_parent(locked_category)
        locked_category.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError("دسته‌بندی مصالح با این کد از قبل وجود دارد.") from exc
    record_audit_event(
        action=AuditAction.MATERIAL_CATEGORY_UPDATED,
        entity_type="material_category",
        entity_id=locked_category.pk,
        organization=organization,
        actor=actor,
        metadata={"code": locked_category.code},
    )
    return locked_category


def get_organization_material_categories(
    *, user: User, organization: Organization
) -> QuerySet[MaterialCategory]:
    require_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.MATERIAL_CATEGORIES_VIEW,
        message="اجازه مشاهده دسته‌بندی‌های مصالح این سازمان را ندارید.",
    )
    return MaterialCategory.objects.filter(
        organization=organization, archived_at__isnull=True
    )


@transaction.atomic
def archive_material_category(
    *, organization: Organization, actor: User, category: MaterialCategory
) -> MaterialCategory:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.MATERIAL_CATEGORIES_ARCHIVE,
    )
    locked_category = MaterialCategory.objects.select_for_update().get(pk=category.pk)
    if locked_category.organization_id != organization.id:
        raise PermissionDenied("دسته‌بندی مصالح متعلق به این سازمان نیست.")
    if locked_category.archived_at is not None:
        raise ValueError("دسته‌بندی مصالح از قبل بایگانی شده است.")
    if (
        locked_category.children.filter(archived_at__isnull=True).exists()
        or locked_category.materials.filter(archived_at__isnull=True).exists()
    ):
        raise ValueError("دسته‌ای که زیرمجموعه یا مصالح فعال دارد قابل بایگانی نیست.")
    (
        locked_category.archived_at,
        locked_category.is_active,
        locked_category.updated_by,
    ) = timezone.now(), False, actor
    locked_category.save(
        update_fields=["archived_at", "is_active", "updated_by", "updated_at"]
    )
    record_audit_event(
        action=AuditAction.MATERIAL_CATEGORY_ARCHIVED,
        entity_type="material_category",
        entity_id=locked_category.pk,
        organization=organization,
        actor=actor,
        metadata={"code": locked_category.code},
    )
    return locked_category


@transaction.atomic
def create_material(
    *,
    organization: Organization,
    actor: User,
    code: str,
    name: str,
    unit_of_measure: UnitOfMeasure,
    category: MaterialCategory | None = None,
    specifications: str = "",
) -> Material:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.MATERIALS_CREATE,
    )
    material = Material(
        organization=organization,
        code=code,
        name=name,
        category=category,
        unit_of_measure=unit_of_measure,
        specifications=specifications,
        created_by=actor,
        updated_by=actor,
    )
    try:
        material.full_clean()
        material.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError("اطلاعات مصالح معتبر نیست یا کد آن از قبل وجود دارد.") from exc
    record_audit_event(
        action=AuditAction.MATERIAL_CREATED,
        entity_type="material",
        entity_id=material.pk,
        organization=organization,
        actor=actor,
        metadata={
            "code": material.code,
            "unit_of_measure": material.unit_of_measure.code,
        },
    )
    return material


@transaction.atomic
def update_material(
    *,
    organization: Organization,
    actor: User,
    material: Material,
    code: str,
    name: str,
    unit_of_measure: UnitOfMeasure,
    category: MaterialCategory | None = None,
    specifications: str = "",
) -> Material:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.MATERIALS_CHANGE,
    )
    locked_material = Material.objects.select_for_update().get(pk=material.pk)
    if locked_material.organization_id != organization.id:
        raise PermissionDenied("مصالح متعلق به این سازمان نیست.")
    if locked_material.archived_at is not None:
        raise ValueError("مصالح بایگانی‌شده قابل به‌روزرسانی نیست.")
    if canonicalize_upper_identifier(code) != locked_material.code:
        _require_active_management_access(
            organization=organization,
            actor=actor,
            permission=BusinessPermissionCode.MATERIALS_STEWARD,
        )
    locked_material.code, locked_material.name = code, name
    locked_material.category, locked_material.unit_of_measure = (
        category,
        unit_of_measure,
    )
    locked_material.specifications, locked_material.updated_by = specifications, actor
    try:
        locked_material.full_clean()
        locked_material.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError("اطلاعات مصالح معتبر نیست یا کد آن از قبل وجود دارد.") from exc
    record_audit_event(
        action=AuditAction.MATERIAL_UPDATED,
        entity_type="material",
        entity_id=locked_material.pk,
        organization=organization,
        actor=actor,
        metadata={
            "code": locked_material.code,
            "unit_of_measure": locked_material.unit_of_measure.code,
        },
    )
    return locked_material


def resolve_canonical_material(material: Material) -> Material:
    """Follow preserved supersession lineage and fail on any unexpected cycle."""

    current = material
    visited: set[object] = set()
    while MaterialSupersession.objects.filter(source=current).exists():
        if current.pk in visited:
            raise ValueError("زنجیره جایگزینی مصالح نامعتبر است.")
        visited.add(current.pk)
        current = MaterialSupersession.objects.select_related("survivor").get(
            source=current
        ).survivor
    return current


def resolve_material_identifier(
    *, organization: Organization, identifier: str
) -> Material:
    normalized = canonicalize_upper_identifier(identifier)
    material = Material.objects.filter(
        organization=organization, code=normalized
    ).first()
    if material is None:
        alias = (
            MaterialAlias.objects.select_related("material")
            .filter(organization=organization, code=normalized)
            .first()
        )
        if alias is None:
            raise ValueError("شناسه مصالح یافت نشد.")
        material = alias.material
    return resolve_canonical_material(material)


@transaction.atomic
def record_material_alias(
    *,
    organization: Organization,
    actor: User,
    material: Material,
    code: str,
    reason: str,
    label: str = "",
) -> MaterialAlias:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.MATERIALS_STEWARD,
    )
    if material.organization_id != organization.pk:
        raise PermissionDenied("مصالح متعلق به این سازمان نیست.")
    normalized = canonicalize_upper_identifier(code)
    if Material.objects.filter(organization=organization, code=normalized).exists():
        raise ValueError("کد جایگزین با کد اصلی مصالح تداخل دارد.")
    alias = MaterialAlias.objects.create(
        organization=organization,
        material=resolve_canonical_material(material),
        code=normalized,
        label=label,
        created_by=actor,
        reason=reason,
    )
    record_audit_event(
        action=AuditAction.MATERIAL_ALIAS_RECORDED,
        entity_type="material_alias",
        entity_id=alias.pk,
        organization=organization,
        actor=actor,
        metadata={"material_id": str(alias.material_id), "code": alias.code},
    )
    return alias


@transaction.atomic
def record_material_duplicate_candidate(
    *,
    organization: Organization,
    actor: User,
    left: Material,
    right: Material,
    evidence: dict[str, object] | None = None,
) -> MaterialDuplicateCandidate:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.MATERIALS_STEWARD,
    )
    if left.organization_id != organization.pk or right.organization_id != organization.pk:
        raise PermissionDenied("نامزدهای تکراری متعلق به این سازمان نیستند.")
    if left.pk == right.pk:
        raise ValueError("دو رکورد متفاوت برای بررسی تکرار الزامی است.")
    ordered = sorted((left, right), key=lambda item: item.pk.hex)
    candidate, _ = MaterialDuplicateCandidate.objects.get_or_create(
        organization=organization,
        left=ordered[0],
        right=ordered[1],
        defaults={"evidence": evidence or {}},
    )
    return candidate


@transaction.atomic
def supersede_material(
    *,
    organization: Organization,
    actor: User,
    source: Material,
    survivor: Material,
    reason: str,
) -> MaterialSupersession:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.MATERIALS_MERGE,
    )
    if not reason.strip():
        raise ValueError("دلیل جایگزینی مصالح الزامی است.")
    locked = {
        item.pk: item
        for item in Material.objects.select_for_update()
        .filter(pk__in=[source.pk, survivor.pk])
        .order_by("pk")
    }
    if len(locked) != 2:
        raise PermissionDenied("مصالح برای جایگزینی یافت نشد.")
    source = locked[source.pk]
    survivor = resolve_canonical_material(locked[survivor.pk])
    if (
        source.organization_id != organization.pk
        or survivor.organization_id != organization.pk
    ):
        raise PermissionDenied("مصالح جایگزین‌شده متعلق به این سازمان نیستند.")
    if source.pk == survivor.pk or hasattr(source, "supersession"):
        raise ValueError("زنجیره جایگزینی مصالح معتبر نیست.")
    supersession = MaterialSupersession.objects.create(
        organization=organization,
        source=source,
        survivor=survivor,
        created_by=actor,
        reason=reason.strip(),
    )
    MaterialAlias.objects.get_or_create(
        organization=organization,
        code=source.code,
        defaults={
            "material": survivor,
            "label": source.name,
            "created_by": actor,
            "reason": reason.strip(),
        },
    )
    source.is_active = False
    source.archived_at = timezone.now()
    source.updated_by = actor
    source.save(update_fields=["is_active", "archived_at", "updated_by", "updated_at"])
    MaterialDuplicateCandidate.objects.filter(
        organization=organization,
        left_id__in=[source.pk, survivor.pk],
        right_id__in=[source.pk, survivor.pk],
    ).update(
        status=MaterialDuplicateCandidate.Status.SUPERSEDED,
        reviewed_by=actor,
        review_reason=reason.strip(),
        updated_at=timezone.now(),
    )
    record_audit_event(
        action=AuditAction.MATERIAL_SUPERSEDED,
        entity_type="material_supersession",
        entity_id=supersession.pk,
        organization=organization,
        actor=actor,
        metadata={
            "source_id": str(source.pk),
            "survivor_id": str(survivor.pk),
            "reason": reason.strip(),
        },
    )
    return supersession


def get_organization_materials(
    *, user: User, organization: Organization, search: str = ""
) -> QuerySet[Material]:
    require_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.MATERIALS_VIEW,
        message="اجازه مشاهده مصالح این سازمان را ندارید.",
    )
    queryset = Material.objects.filter(
        organization=organization, archived_at__isnull=True
    ).exclude(supersession__isnull=False).select_related("category", "unit_of_measure")
    if search.strip():
        from django.db.models import Q

        queryset = queryset.filter(
            Q(code__icontains=search.strip()) | Q(name__icontains=search.strip())
        )
    return queryset


def search_organization_materials(
    *, user: User, organization: Organization, term: str
) -> QuerySet[Material]:
    """Bounded Tenant-local catalogue search, including normalized governed values."""
    queryset = get_organization_materials(user=user, organization=organization)
    normalized_term = term.strip()
    if not normalized_term:
        return queryset
    return queryset.filter(
        Q(code__icontains=normalized_term)
        | Q(name__icontains=normalized_term)
        | Q(attribute_values__normalized_value__icontains=normalized_term)
    ).distinct()


@transaction.atomic
def archive_material(
    *, organization: Organization, actor: User, material: Material
) -> Material:
    _require_active_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.MATERIALS_ARCHIVE,
    )
    locked_material = Material.objects.select_for_update().get(pk=material.pk)
    if locked_material.organization_id != organization.id:
        raise PermissionDenied("مصالح متعلق به این سازمان نیست.")
    if locked_material.archived_at is not None:
        raise ValueError("مصالح از قبل بایگانی شده است.")
    from apps.inventory.models import StockTransactionStatus

    stock_transactions = locked_material.stock_transactions.all()
    if stock_transactions.filter(status=StockTransactionStatus.DRAFT).exists():
        raise ValueError("مصالح دارای تراکنش پیش‌نویس انبار قابل بایگانی نیست.")
    warehouse_balances: defaultdict[object, Decimal] = defaultdict(
        lambda: Decimal("0.0000")
    )
    for source_id, destination_id, quantity in stock_transactions.filter(
        status__in=[
            StockTransactionStatus.POSTED,
            StockTransactionStatus.REVERSED,
        ]
    ).values_list("source_warehouse_id", "destination_warehouse_id", "quantity"):
        if source_id is not None:
            warehouse_balances[source_id] -= quantity
        if destination_id is not None:
            warehouse_balances[destination_id] += quantity
    if any(balance != Decimal("0.0000") for balance in warehouse_balances.values()):
        raise ValueError("مصالح دارای موجودی انبار قابل بایگانی نیست.")
    (
        locked_material.archived_at,
        locked_material.is_active,
        locked_material.updated_by,
    ) = timezone.now(), False, actor
    locked_material.save(
        update_fields=["archived_at", "is_active", "updated_by", "updated_at"]
    )
    record_audit_event(
        action=AuditAction.MATERIAL_ARCHIVED,
        entity_type="material",
        entity_id=locked_material.pk,
        organization=organization,
        actor=actor,
        metadata={"code": locked_material.code},
    )
    return locked_material
