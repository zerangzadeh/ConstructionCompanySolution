"""Read-only workspace selectors over retained financial/operational relationships."""

from django.core.exceptions import PermissionDenied
from django.db.models import Q

from apps.accounting.recognition_models import SourceRecognitionDraft
from apps.equipment.services import get_organization_equipment
from apps.organizations.authorization import (
    has_business_permission,
    require_business_permission,
    scope_queryset,
)
from apps.organizations.models import BusinessPermissionCode as P

from .models import FixedAsset, FixedAssetEquipmentLink


def visible_assets(*, organization, actor):
    # Preserve the current Fixed Assets UI's explicit organization scope. This
    # selector does not add scope types or grant project/site access implicitly.
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=P.FIXED_ASSETS_VIEW,
        message="اجازه مشاهدهٔ دارایی‌های ثابت این شرکت را ندارید.",
    )
    return scope_queryset(
        FixedAsset.objects.filter(organization=organization),
        membership=membership,
        project_lookup="project_id",
        site_lookup="site_id",
    )


def equipment_financial_links(*, organization, actor, equipment):
    if equipment.organization_id != organization.pk:
        raise PermissionDenied("Equipment is outside the active organization.")
    try:
        assets = visible_assets(organization=organization, actor=actor)
    except PermissionDenied:
        return FixedAssetEquipmentLink.objects.none()
    # Retained links are evidence, including historical links; no current-active
    # or identity-equivalence rule is inferred from dates, numbers or names.
    return FixedAssetEquipmentLink.objects.filter(
        organization=organization, equipment=equipment, asset__in=assets
    ).select_related("asset")


def asset_operational_links(*, organization, actor, asset):
    visible_assets(organization=organization, actor=actor).get(pk=asset.pk)
    if not all(
        has_business_permission(
            user=actor, organization=organization, permission=permission
        )
        for permission in (P.EQUIPMENT_ASSIGNMENTS_VIEW, P.MAINTENANCE_RECORDS_VIEW)
    ):
        return FixedAssetEquipmentLink.objects.none()
    try:
        equipment = get_organization_equipment(user=actor, organization=organization)
    except PermissionDenied:
        return FixedAssetEquipmentLink.objects.none()
    return FixedAssetEquipmentLink.objects.filter(
        organization=organization, asset=asset, equipment__in=equipment
    ).select_related("equipment")


def asset_accounting_targets(*, organization, actor, asset):
    visible_assets(organization=organization, actor=actor).get(pk=asset.pk)
    if not all(
        has_business_permission(
            user=actor, organization=organization, permission=permission
        )
        for permission in (P.ACCOUNTING_VIEW, P.ACCOUNTING_RECOGNITION_VIEW)
    ):
        return SourceRecognitionDraft.objects.none()
    transactions = asset.transactions.filter(organization=organization).values("pk")
    runs = asset.depreciation_lines.filter(organization=organization).values("run_id")
    return (
        SourceRecognitionDraft.objects.filter(
            organization=organization,
            journal__organization=organization,
            mapping__organization=organization,
        )
        .filter(
            Q(source_kind="asset", source_uuid__in=transactions)
            | Q(source_kind="depreciation", source_uuid__in=runs)
        )
        .select_related("journal", "mapping")
        .order_by("created_at")
    )
