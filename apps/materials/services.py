from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.materials.models import (
    Material,
    MaterialCategory,
    UnitCategory,
    UnitOfMeasure,
)
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationStatus,
)


def _can_manage_units(user: User, organization: Organization) -> bool:
    return organization.memberships.filter(
        user=user,
        status=MembershipStatus.ACTIVE,
        role__in=[MembershipRole.OWNER, MembershipRole.ADMIN, MembershipRole.MANAGER],
    ).exists()


def _require_active_management_access(
    *, organization: Organization, actor: User
) -> None:
    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied("Authentication is required.")
    if organization.status != OrganizationStatus.ACTIVE or organization.deleted_at:
        raise PermissionDenied("The organization is not active.")
    if not _can_manage_units(actor, organization):
        raise PermissionDenied("You cannot manage units in this organization.")


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
    _require_active_management_access(organization=organization, actor=actor)
    if category not in UnitCategory.values:
        raise ValueError("Invalid unit category.")
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
        raise ValueError("A unit with this code or symbol already exists.") from exc
    record_audit_event(
        action=AuditAction.UNIT_OF_MEASURE_CREATED,
        entity_type="unit_of_measure",
        entity_id=unit.pk,
        organization=organization,
        actor=actor,
        metadata={"code": unit.code, "symbol": unit.symbol},
    )
    return unit


def get_organization_units(
    *, user: User, organization: Organization
) -> QuerySet[UnitOfMeasure]:
    if not organization.memberships.filter(
        user=user, status=MembershipStatus.ACTIVE
    ).exists():
        raise PermissionDenied("You do not have access to this organization.")
    return UnitOfMeasure.objects.filter(
        organization=organization, archived_at__isnull=True
    )


@transaction.atomic
def archive_unit_of_measure(
    *, organization: Organization, actor: User, unit: UnitOfMeasure
) -> UnitOfMeasure:
    _require_active_management_access(organization=organization, actor=actor)
    locked_unit = UnitOfMeasure.objects.select_for_update().get(pk=unit.pk)
    if locked_unit.organization_id != organization.id:
        raise PermissionDenied("The unit does not belong to this organization.")
    if locked_unit.archived_at is not None:
        raise ValueError("The unit is already archived.")
    if locked_unit.materials.filter(archived_at__isnull=True).exists():
        raise ValueError("A unit used by active materials cannot be archived.")
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
            raise ValueError("Material category hierarchy cannot contain a cycle.")
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
    _require_active_management_access(organization=organization, actor=actor)
    if parent and parent.organization_id != organization.id:
        raise PermissionDenied(
            "The parent category does not belong to this organization."
        )
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
        raise ValueError("A material category with this code already exists.") from exc
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
    _require_active_management_access(organization=organization, actor=actor)
    locked_category = MaterialCategory.objects.select_for_update().get(pk=category.pk)
    if locked_category.organization_id != organization.id:
        raise PermissionDenied(
            "The material category does not belong to this organization."
        )
    if locked_category.archived_at is not None:
        raise ValueError("Archived material categories cannot be updated.")
    if parent and parent.organization_id != organization.id:
        raise PermissionDenied(
            "The parent category does not belong to this organization."
        )
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
        raise ValueError("A material category with this code already exists.") from exc
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
    if not organization.memberships.filter(
        user=user, status=MembershipStatus.ACTIVE
    ).exists():
        raise PermissionDenied("You do not have access to this organization.")
    return MaterialCategory.objects.filter(
        organization=organization, archived_at__isnull=True
    )


@transaction.atomic
def archive_material_category(
    *, organization: Organization, actor: User, category: MaterialCategory
) -> MaterialCategory:
    _require_active_management_access(organization=organization, actor=actor)
    locked_category = MaterialCategory.objects.select_for_update().get(pk=category.pk)
    if locked_category.organization_id != organization.id:
        raise PermissionDenied(
            "The material category does not belong to this organization."
        )
    if locked_category.archived_at is not None:
        raise ValueError("The material category is already archived.")
    if (
        locked_category.children.filter(archived_at__isnull=True).exists()
        or locked_category.materials.filter(archived_at__isnull=True).exists()
    ):
        raise ValueError(
            "A category with active child categories or materials cannot be archived."
        )
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
    _require_active_management_access(organization=organization, actor=actor)
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
        raise ValueError(
            "Material data is invalid or its code already exists."
        ) from exc
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
    _require_active_management_access(organization=organization, actor=actor)
    locked_material = Material.objects.select_for_update().get(pk=material.pk)
    if locked_material.organization_id != organization.id:
        raise PermissionDenied("The material does not belong to this organization.")
    if locked_material.archived_at is not None:
        raise ValueError("Archived materials cannot be updated.")
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
        raise ValueError(
            "Material data is invalid or its code already exists."
        ) from exc
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


def get_organization_materials(
    *, user: User, organization: Organization, search: str = ""
) -> QuerySet[Material]:
    if not organization.memberships.filter(
        user=user, status=MembershipStatus.ACTIVE
    ).exists():
        raise PermissionDenied("You do not have access to this organization.")
    queryset = Material.objects.filter(
        organization=organization, archived_at__isnull=True
    ).select_related("category", "unit_of_measure")
    if search.strip():
        from django.db.models import Q

        queryset = queryset.filter(
            Q(code__icontains=search.strip()) | Q(name__icontains=search.strip())
        )
    return queryset


@transaction.atomic
def archive_material(
    *, organization: Organization, actor: User, material: Material
) -> Material:
    _require_active_management_access(organization=organization, actor=actor)
    locked_material = Material.objects.select_for_update().get(pk=material.pk)
    if locked_material.organization_id != organization.id:
        raise PermissionDenied("The material does not belong to this organization.")
    if locked_material.archived_at is not None:
        raise ValueError("The material is already archived.")
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
