"""P8-S25–S27 Fixed Assets evidence; deliberately never calls financial consumers."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounting.models import FiscalPeriodStatus
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.fixed_assets.models import (
    AssetBookPolicyVersion,
    AssetReconciliationEvidence,
    AssetSourceReference,
    AssetStatus,
    AssetTransaction,
    AssetTransactionType,
    DepreciationConvention,
    DepreciationLine,
    DepreciationRun,
    DepreciationRunStatus,
    EnvelopeStatus,
    FixedAsset,
    FixedAssetClassVersion,
    FixedAssetEquipmentLink,
    FixedAssetSourceEnvelope,
    PolicyStatus,
    TransactionStatus,
)
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode, Organization


def _require(*, organization, actor, permission, project=None):
    return require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        project=project,
        allow_any_scope=project is None,
        allow_site_parent=True,
        message="اجازه عملیات دارایی ثابت را ندارید.",
    )


@transaction.atomic
def create_asset_class(
    *,
    organization: Organization,
    actor,
    code: str,
    name: str,
    version: int,
    effective_from: date,
    account_mapping_reference: str,
    capitalization_policy_reference: str,
) -> FixedAssetClassVersion:
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.FIXED_ASSET_CLASS_POLICY_MANAGE,
    )
    item = FixedAssetClassVersion(
        organization=organization,
        code=code,
        name=name,
        version=version,
        effective_from=effective_from,
        account_mapping_reference=account_mapping_reference,
        capitalization_policy_reference=capitalization_policy_reference,
        prepared_by=actor,
    )
    item.full_clean()
    item.save()
    return item


@transaction.atomic
def create_book_policy(
    *,
    organization: Organization,
    actor,
    code: str,
    version: int,
    effective_from: date,
    monetary_policy_code: str,
    monetary_policy_version: str,
    convention: str,
    decimal_places: int = 0,
) -> AssetBookPolicyVersion:
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.FIXED_ASSET_CLASS_POLICY_MANAGE,
    )
    item = AssetBookPolicyVersion(
        organization=organization,
        code=code,
        version=version,
        effective_from=effective_from,
        monetary_policy_code=monetary_policy_code,
        monetary_policy_version=monetary_policy_version,
        convention=convention,
        decimal_places=decimal_places,
        prepared_by=actor,
    )
    item.full_clean()
    item.save()
    return item


@transaction.atomic
def review_policy(*, organization: Organization, actor, policy):
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.FIXED_ASSET_CLASS_POLICY_PUBLISH,
    )
    locked = (
        type(policy)
        .objects.select_for_update()
        .get(pk=policy.pk, organization=organization)
    )
    if locked.status != PolicyStatus.DRAFT or locked.prepared_by_id == actor.pk:
        raise ValueError("بررسی مستقل فقط برای سیاست پیش‌نویس مجاز است.")
    locked.status = PolicyStatus.REVIEWED
    locked.reviewed_by = actor
    locked.save(update_fields=["status", "reviewed_by", "updated_at"])
    _audit_policy(locked, actor)
    return locked


@transaction.atomic
def publish_policy(*, organization: Organization, actor, policy):
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.FIXED_ASSET_CLASS_POLICY_PUBLISH,
    )
    locked = (
        type(policy)
        .objects.select_for_update()
        .get(pk=policy.pk, organization=organization)
    )
    if locked.status != PolicyStatus.REVIEWED or locked.prepared_by_id == actor.pk:
        raise ValueError("انتشار مستقل فقط برای سیاست بررسی‌شده مجاز است.")
    type(policy).objects.filter(
        organization=organization, code=locked.code, status=PolicyStatus.PUBLISHED
    ).exclude(pk=locked.pk).update(status=PolicyStatus.SUPERSEDED)
    locked.status = PolicyStatus.PUBLISHED
    locked.published_by = actor
    locked.published_at = timezone.now()
    locked.save(update_fields=["status", "published_by", "published_at", "updated_at"])
    _audit_policy(locked, actor)
    return locked


def _audit_policy(policy, actor):
    record_audit_event(
        action=AuditAction.FIXED_ASSET_POLICY_TRANSITIONED,
        entity_type=policy._meta.label_lower,
        entity_id=policy.pk,
        organization=policy.organization,
        actor=actor,
        metadata={
            "code": policy.code,
            "version": policy.version,
            "status": policy.status,
        },
    )


@transaction.atomic
def prepare_asset(
    *,
    organization: Organization,
    actor,
    asset_number: str,
    name: str,
    asset_class: FixedAssetClassVersion,
    book_policy: AssetBookPolicyVersion,
    ready_for_use_date: date,
    useful_life_months: int,
    residual_value: Decimal,
    capitalization_basis: Decimal,
    evidence_reference: str,
    project=None,
    site=None,
    cost_center=None,
    parent=None,
) -> FixedAsset:
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.FIXED_ASSET_CANDIDATE_PREPARE,
        project=project,
    )
    if (
        asset_class.organization_id != organization.pk
        or book_policy.organization_id != organization.pk
        or (project is not None and project.organization_id != organization.pk)
    ):
        raise PermissionDenied("منابع دارایی متعلق به این سازمان نیستند.")
    asset = FixedAsset(
        organization=organization,
        asset_number=asset_number,
        name=name,
        asset_class=asset_class,
        book_policy=book_policy,
        parent=parent,
        ready_for_use_date=ready_for_use_date,
        useful_life_months=useful_life_months,
        residual_value=residual_value,
        capitalization_basis=capitalization_basis,
        project=project,
        site=site,
        cost_center=cost_center,
        evidence_reference=evidence_reference,
        prepared_by=actor,
    )
    asset.full_clean()
    asset.save()
    return asset


@transaction.atomic
def add_asset_source(
    *,
    organization: Organization,
    actor,
    asset: FixedAsset,
    source_family: str,
    source_public_id: str,
    source_version: str,
    source_date: date,
    amount: Decimal,
    evidence_reference: str,
    source_line: str = "",
) -> AssetSourceReference:
    locked = FixedAsset.objects.select_for_update().get(
        pk=asset.pk, organization=organization
    )
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.FIXED_ASSET_CANDIDATE_PREPARE,
        project=locked.project,
    )
    source = AssetSourceReference(
        organization=organization,
        asset=locked,
        source_family=source_family,
        source_public_id=source_public_id,
        source_version=source_version,
        source_line=source_line,
        source_date=source_date,
        amount=amount,
        evidence_reference=evidence_reference,
        prepared_by=actor,
    )
    source.full_clean()
    source.save()
    return source


@transaction.atomic
def review_asset_source(
    *, organization: Organization, actor, source: AssetSourceReference
) -> AssetSourceReference:
    locked = AssetSourceReference.objects.select_for_update().get(
        pk=source.pk, organization=organization
    )
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.FIXED_ASSET_CANDIDATE_REVIEW,
        project=locked.asset.project,
    )
    if locked.prepared_by_id == actor.pk:
        raise ValueError("تهیه‌کننده منبع نمی‌تواند آن را بررسی کند.")
    locked.reviewed = True
    locked.reviewed_by = actor
    locked.save(update_fields=["reviewed", "reviewed_by", "updated_at"])
    return locked


@transaction.atomic
def capitalize_asset(
    *,
    organization: Organization,
    actor,
    asset: FixedAsset,
    source: AssetSourceReference,
    occurrence_key: str,
) -> AssetTransaction:
    locked = FixedAsset.objects.select_for_update().get(
        pk=asset.pk, organization=organization
    )
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.FIXED_ASSET_CAPITALIZE,
        project=locked.project,
    )
    source = AssetSourceReference.objects.select_for_update().get(
        pk=source.pk, organization=organization, asset=locked
    )
    existing = AssetTransaction.objects.filter(
        organization=organization, occurrence_key=occurrence_key
    ).first()
    if existing:
        if (
            existing.asset_id == locked.pk
            and existing.source_id == source.pk
            and existing.transaction_type == AssetTransactionType.CAPITALIZATION
            and existing.amount == source.amount
        ):
            return existing
        raise ValueError("کلید سرمایه‌ای‌کردن با محتوای متفاوت تکرار شده است.")
    if (
        locked.status != AssetStatus.CANDIDATE
        or locked.prepared_by_id == actor.pk
        or not source.reviewed
        or source.reviewed_by_id == actor.pk
    ):
        raise ValueError("سرمایه‌ای‌کردن مستقل به نامزد و منبع بررسی‌شده نیاز دارد.")
    if source.amount != locked.capitalization_basis:
        raise ValueError("مبلغ منبع باید با مبنای سرمایه‌ای برابر باشد.")
    tx = AssetTransaction(
        organization=organization,
        asset=locked,
        source=source,
        transaction_type=AssetTransactionType.CAPITALIZATION,
        status=TransactionStatus.FINALIZED,
        occurred_on=locked.ready_for_use_date,
        amount=source.amount,
        occurrence_key=occurrence_key,
        reason="source-backed capitalization",
        prepared_by=locked.prepared_by,
        reviewed_by=actor,
        finalized_at=timezone.now(),
    )
    tx.full_clean()
    tx.save()
    locked.status = AssetStatus.ACTIVE
    locked.reviewed_by = actor
    locked.reviewed_at = timezone.now()
    locked.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
    _audit_asset(locked, actor, "capitalized")
    return tx


@transaction.atomic
def link_equipment(
    *,
    organization: Organization,
    actor,
    asset: FixedAsset,
    equipment,
    effective_from: date,
    reason: str,
    is_primary: bool = True,
) -> FixedAssetEquipmentLink:
    locked = FixedAsset.objects.select_for_update().get(
        pk=asset.pk, organization=organization
    )
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.FIXED_ASSETS_MANAGE,
        project=locked.project,
    )
    if equipment.organization_id != organization.pk:
        raise PermissionDenied("تجهیز متعلق به این سازمان نیست.")
    if (
        is_primary
        and FixedAssetEquipmentLink.objects.filter(
            asset=locked, is_primary=True, effective_to__isnull=True
        ).exists()
    ):
        raise ValueError("دارایی یک پیوند اصلی فعال دارد.")
    link = FixedAssetEquipmentLink(
        organization=organization,
        asset=locked,
        equipment=equipment,
        effective_from=effective_from,
        is_primary=is_primary,
        reason=reason,
        linked_by=actor,
    )
    link.full_clean()
    link.save()
    return link


def _permission_for_transaction(kind):
    return {
        AssetTransactionType.IMPAIRMENT: BusinessPermissionCode.FIXED_ASSET_IMPAIR,
        AssetTransactionType.TRANSFER: BusinessPermissionCode.FIXED_ASSET_TRANSFER,
        AssetTransactionType.DISPOSAL: BusinessPermissionCode.FIXED_ASSET_DISPOSE,
        AssetTransactionType.RETIREMENT: BusinessPermissionCode.FIXED_ASSET_DISPOSE,
    }.get(kind, BusinessPermissionCode.FIXED_ASSET_TRANSACTION_PREPARE)


@transaction.atomic
def prepare_asset_transaction(
    *,
    organization: Organization,
    actor,
    asset: FixedAsset,
    transaction_type: str,
    occurred_on: date,
    amount: Decimal,
    occurrence_key: str,
    reason: str,
    source: AssetSourceReference | None = None,
    target_project=None,
    target_site=None,
    target_cost_center=None,
) -> AssetTransaction:
    locked = FixedAsset.objects.select_for_update().get(
        pk=asset.pk, organization=organization
    )
    _require(
        organization=organization,
        actor=actor,
        permission=_permission_for_transaction(transaction_type),
        project=locked.project,
    )
    if locked.status != AssetStatus.ACTIVE:
        raise ValueError("رویداد فقط برای دارایی فعال مجاز است.")
    existing = AssetTransaction.objects.filter(
        organization=organization, occurrence_key=occurrence_key
    ).first()
    if existing:
        if (
            existing.asset_id == locked.pk
            and existing.transaction_type == transaction_type
            and existing.amount == amount
            and existing.occurred_on == occurred_on
            and existing.reason == reason
            and existing.source_id == getattr(source, "pk", None)
            and existing.source_dimensions_captured
            == (transaction_type == AssetTransactionType.TRANSFER)
            and existing.source_project_id
            == (
                locked.project_id
                if transaction_type == AssetTransactionType.TRANSFER
                else None
            )
            and existing.source_site_id
            == (
                locked.site_id
                if transaction_type == AssetTransactionType.TRANSFER
                else None
            )
            and existing.source_cost_center_id
            == (
                locked.cost_center_id
                if transaction_type == AssetTransactionType.TRANSFER
                else None
            )
            and existing.target_project_id == getattr(target_project, "pk", None)
            and existing.target_site_id == getattr(target_site, "pk", None)
            and existing.target_cost_center_id
            == getattr(target_cost_center, "pk", None)
        ):
            return existing
        raise ValueError("کلید رخداد دارایی با محتوای متفاوت تکرار شده است.")
    tx = AssetTransaction(
        organization=organization,
        asset=locked,
        source=source,
        transaction_type=transaction_type,
        occurred_on=occurred_on,
        amount=amount,
        occurrence_key=occurrence_key,
        reason=reason,
        source_dimensions_captured=(transaction_type == AssetTransactionType.TRANSFER),
        source_project=locked.project
        if transaction_type == AssetTransactionType.TRANSFER
        else None,
        source_site=locked.site
        if transaction_type == AssetTransactionType.TRANSFER
        else None,
        source_cost_center=(
            locked.cost_center
            if transaction_type == AssetTransactionType.TRANSFER
            else None
        ),
        target_project=target_project,
        target_site=target_site,
        target_cost_center=target_cost_center,
        prepared_by=actor,
    )
    tx.full_clean()
    tx.save()
    return tx


@transaction.atomic
def finalize_asset_transaction(
    *, organization: Organization, actor, transaction_record: AssetTransaction
) -> AssetTransaction:
    locked = AssetTransaction.objects.select_for_update().get(
        pk=transaction_record.pk, organization=organization
    )
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.FIXED_ASSET_TRANSACTION_REVIEW,
        project=locked.asset.project,
    )
    if locked.status != TransactionStatus.PREPARED or locked.prepared_by_id == actor.pk:
        raise ValueError("بررسی مستقل فقط برای رویداد تهیه‌شده مجاز است.")
    if locked.transaction_type == AssetTransactionType.IMPAIRMENT:
        gross, impairment = _finalized_transaction_totals(locked.asset)
        accumulated = DepreciationLine.objects.filter(
            asset=locked.asset, run__status=DepreciationRunStatus.FINALIZED
        ).aggregate(total=Sum("depreciation_amount"))["total"] or Decimal(0)
        if locked.amount > gross - impairment - accumulated:
            raise ValueError("کاهش ارزش نمی‌تواند ارزش دفتری را منفی کند.")
    locked.status = TransactionStatus.FINALIZED
    locked.reviewed_by = actor
    locked.finalized_at = timezone.now()
    locked.save(update_fields=["status", "reviewed_by", "finalized_at", "updated_at"])
    asset = locked.asset
    if locked.transaction_type in {
        AssetTransactionType.DISPOSAL,
        AssetTransactionType.RETIREMENT,
    }:
        asset.status = (
            AssetStatus.DISPOSED
            if locked.transaction_type == AssetTransactionType.DISPOSAL
            else AssetStatus.RETIRED
        )
        asset.save(update_fields=["status", "updated_at"])
    elif locked.transaction_type == AssetTransactionType.TRANSFER:
        asset.project = locked.target_project
        asset.site = locked.target_site
        asset.cost_center = locked.target_cost_center
        asset.save(update_fields=["project", "site", "cost_center", "updated_at"])
    record_audit_event(
        action=AuditAction.FIXED_ASSET_TRANSACTION_RECORDED,
        entity_type="fixed_asset_transaction",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={
            "asset_id": str(asset.pk),
            "type": locked.transaction_type,
            "amount": str(locked.amount),
        },
    )
    return locked


@transaction.atomic
def reverse_asset_transaction(
    *,
    organization: Organization,
    actor,
    transaction_record: AssetTransaction,
    occurrence_key: str,
    reason: str,
) -> AssetTransaction:
    locked = AssetTransaction.objects.select_for_update().get(
        pk=transaction_record.pk, organization=organization
    )
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.FIXED_ASSET_TRANSACTION_REVERSE,
        project=locked.asset.project,
    )
    existing = AssetTransaction.objects.filter(
        organization=organization, occurrence_key=occurrence_key
    ).first()
    if existing:
        if existing.reversal_of_id == locked.pk and existing.reason == reason.strip():
            return existing
        raise ValueError("کلید برگشت رویداد با محتوای متفاوت تکرار شده است.")
    if (
        locked.status != TransactionStatus.FINALIZED
        or locked.reviewed_by_id == actor.pk
        or not reason.strip()
    ):
        raise ValueError("برگشت مستقل رویداد نهایی همراه علت الزامی است.")
    reversal = AssetTransaction(
        organization=organization,
        asset=locked.asset,
        transaction_type=AssetTransactionType.REVERSAL,
        status=TransactionStatus.FINALIZED,
        occurred_on=timezone.localdate(),
        amount=locked.amount,
        occurrence_key=occurrence_key,
        reason=reason.strip(),
        reversal_of=locked,
        prepared_by=actor,
        reviewed_by=actor,
        finalized_at=timezone.now(),
    )
    reversal.full_clean()
    reversal.save()
    asset = locked.asset
    if locked.transaction_type in {
        AssetTransactionType.DISPOSAL,
        AssetTransactionType.RETIREMENT,
    }:
        asset.status = AssetStatus.ACTIVE
        asset.save(update_fields=["status", "updated_at"])
    elif locked.transaction_type == AssetTransactionType.TRANSFER:
        if not locked.source_dimensions_captured:
            raise ValueError("برگشت انتقال بدون ابعاد مبدأ ذخیره‌شده مجاز نیست.")
        asset.project = locked.source_project
        asset.site = locked.source_site
        asset.cost_center = locked.source_cost_center
        asset.save(update_fields=["project", "site", "cost_center", "updated_at"])
    locked.status = TransactionStatus.REVERSED
    locked.save(update_fields=["status", "updated_at"])
    record_audit_event(
        action=AuditAction.FIXED_ASSET_TRANSACTION_RECORDED,
        entity_type="fixed_asset_transaction",
        entity_id=reversal.pk,
        organization=organization,
        actor=actor,
        metadata={
            "asset_id": str(locked.asset_id),
            "type": "reversal",
            "reversal_of": str(locked.pk),
        },
    )
    return reversal


def _finalized_transaction_totals(
    asset, *, occurred_through=None, finalized_through=None
):
    rows = AssetTransaction.objects.filter(
        asset=asset, status=TransactionStatus.FINALIZED
    )
    if occurred_through is not None:
        rows = rows.filter(occurred_on__lte=occurred_through)
    if finalized_through is not None:
        rows = rows.filter(finalized_at__lte=finalized_through)
    positive = rows.filter(
        transaction_type__in=[
            AssetTransactionType.OPENING,
            AssetTransactionType.CAPITALIZATION,
            AssetTransactionType.ADDITION,
            AssetTransactionType.IMPAIRMENT_REVERSAL,
        ]
    ).aggregate(total=Sum("amount"))["total"] or Decimal(0)
    negative = rows.filter(transaction_type=AssetTransactionType.IMPAIRMENT).aggregate(
        total=Sum("amount")
    )["total"] or Decimal(0)
    return positive, negative


def _eligible_fraction(asset, period, convention):
    if asset.ready_for_use_date > period.ends_on:
        return Decimal(0)
    if (
        convention == DepreciationConvention.NEXT_MONTH
        and asset.ready_for_use_date >= period.starts_on
    ):
        return Decimal(0)
    if (
        convention != DepreciationConvention.DAILY_PRORATA
        or asset.ready_for_use_date <= period.starts_on
    ):
        return Decimal(1)
    eligible_start = max(asset.ready_for_use_date, period.starts_on)
    eligible_days = (period.ends_on - eligible_start).days + 1
    total_days = (period.ends_on - period.starts_on).days + 1
    return Decimal(eligible_days) / Decimal(total_days)


@transaction.atomic
def preview_depreciation(
    *,
    organization: Organization,
    actor,
    book_policy: AssetBookPolicyVersion,
    fiscal_period,
    occurrence_key: str,
) -> DepreciationRun:
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.FIXED_ASSET_DEPRECIATION_PREVIEW,
    )
    policy = AssetBookPolicyVersion.objects.select_for_update().get(
        pk=book_policy.pk, organization=organization, status=PolicyStatus.PUBLISHED
    )
    period = (
        type(fiscal_period)
        .objects.select_for_update()
        .get(pk=fiscal_period.pk, organization=organization)
    )
    if period.status != FiscalPeriodStatus.OPEN:
        raise ValueError("استهلاک فقط برای دوره حسابداری باز قابل تهیه است.")
    existing = DepreciationRun.objects.filter(
        organization=organization, occurrence_key=occurrence_key
    ).first()
    if existing:
        if (
            existing.book_policy_id == policy.pk
            and existing.fiscal_period_id == period.pk
        ):
            return existing
        raise ValueError("کلید اجرای استهلاک با محتوای متفاوت تکرار شده است.")
    if DepreciationRun.objects.filter(
        organization=organization,
        book_policy=policy,
        fiscal_period=period,
        status=DepreciationRunStatus.FINALIZED,
    ).exists():
        raise ValueError("برای این کتاب و دوره اجرای نهایی فعال وجود دارد.")
    if DepreciationRun.objects.filter(
        organization=organization,
        book_policy=policy,
        status=DepreciationRunStatus.FINALIZED,
        fiscal_period__ends_on__gt=period.ends_on,
    ).exists():
        raise ValueError(
            "استهلاک نمی‌تواند پس از نهایی‌شدن دوره بعدی به دوره قبل بازگردد."
        )
    run = DepreciationRun.objects.create(
        organization=organization,
        book_policy=policy,
        fiscal_period=period,
        occurrence_key=occurrence_key,
        source_watermark=timezone.now(),
        prepared_by=actor,
    )
    quantum = Decimal(1).scaleb(-policy.decimal_places)
    assets = FixedAsset.objects.select_for_update().filter(
        organization=organization, book_policy=policy, status=AssetStatus.ACTIVE
    )
    for asset in assets:
        gross, impairment = _finalized_transaction_totals(
            asset,
            occurred_through=period.ends_on,
            finalized_through=run.source_watermark,
        )
        if gross <= 0:
            continue
        prior = DepreciationLine.objects.filter(
            asset=asset, run__status=DepreciationRunStatus.FINALIZED
        ).aggregate(total=Sum("depreciation_amount"))["total"] or Decimal(0)
        completed_periods = DepreciationLine.objects.filter(
            asset=asset,
            run__status=DepreciationRunStatus.FINALIZED,
            depreciation_amount__gt=0,
        ).count()
        available = max(Decimal(0), gross - impairment - asset.residual_value - prior)
        fraction = _eligible_fraction(asset, period, policy.convention)
        if fraction == 0:
            amount = Decimal(0)
        elif completed_periods + 1 >= asset.useful_life_months:
            amount = available
        else:
            amount = min(
                available,
                (
                    (gross - asset.residual_value)
                    / Decimal(asset.useful_life_months)
                    * fraction
                ),
            )
        amount = amount.quantize(quantum, rounding=ROUND_HALF_UP)
        if amount <= 0:
            continue
        DepreciationLine.objects.create(
            organization=organization,
            run=run,
            asset=asset,
            basis_snapshot=gross,
            residual_snapshot=asset.residual_value,
            useful_life_months_snapshot=asset.useful_life_months,
            prior_accumulated_depreciation=prior,
            depreciation_amount=amount,
            carrying_value_after=gross - impairment - prior - amount,
            convention_snapshot=policy.convention,
        )
    return run


@transaction.atomic
def finalize_depreciation(
    *, organization: Organization, actor, run: DepreciationRun
) -> DepreciationRun:
    locked = (
        DepreciationRun.objects.select_for_update()
        .select_related("fiscal_period")
        .get(pk=run.pk, organization=organization)
    )
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.FIXED_ASSET_DEPRECIATION_FINALIZE,
    )
    if (
        locked.status != DepreciationRunStatus.PREVIEW
        or locked.prepared_by_id == actor.pk
        or locked.fiscal_period.status != FiscalPeriodStatus.OPEN
    ):
        raise ValueError("نهایی‌سازی مستقل فقط برای پیش‌نمایش دوره باز مجاز است.")
    locked.status = DepreciationRunStatus.FINALIZED
    locked.finalized_by = actor
    locked.finalized_at = timezone.now()
    locked.save(update_fields=["status", "finalized_by", "finalized_at", "updated_at"])
    _audit_depreciation(locked, actor)
    return locked


@transaction.atomic
def reverse_depreciation(
    *,
    organization: Organization,
    actor,
    run: DepreciationRun,
    occurrence_key: str,
    reason: str,
) -> DepreciationRun:
    locked = (
        DepreciationRun.objects.select_for_update()
        .prefetch_related("lines")
        .get(pk=run.pk, organization=organization)
    )
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.FIXED_ASSET_DEPRECIATION_REVERSE,
    )
    existing = DepreciationRun.objects.filter(
        organization=organization, occurrence_key=occurrence_key
    ).first()
    if existing:
        if existing.reversal_of_id == locked.pk and existing.reason == reason.strip():
            return existing
        raise ValueError("کلید برگشت استهلاک با محتوای متفاوت تکرار شده است.")
    if (
        locked.status != DepreciationRunStatus.FINALIZED
        or locked.finalized_by_id == actor.pk
        or locked.fiscal_period.status != FiscalPeriodStatus.OPEN
        or not reason.strip()
    ):
        raise ValueError("برگشت مستقل فقط برای اجرای نهایی مجاز است.")
    reversal = DepreciationRun.objects.create(
        organization=organization,
        book_policy=locked.book_policy,
        fiscal_period=locked.fiscal_period,
        status=DepreciationRunStatus.FINALIZED,
        occurrence_key=occurrence_key,
        source_watermark=timezone.now(),
        reason=reason.strip(),
        reversal_of=locked,
        prepared_by=actor,
        finalized_by=actor,
        finalized_at=timezone.now(),
    )
    for line in locked.lines.all():
        DepreciationLine.objects.create(
            organization=organization,
            run=reversal,
            asset=line.asset,
            basis_snapshot=line.basis_snapshot,
            residual_snapshot=line.residual_snapshot,
            useful_life_months_snapshot=line.useful_life_months_snapshot,
            prior_accumulated_depreciation=line.prior_accumulated_depreciation,
            depreciation_amount=-line.depreciation_amount,
            carrying_value_after=line.carrying_value_after + line.depreciation_amount,
            convention_snapshot=line.convention_snapshot,
        )
    locked.status = DepreciationRunStatus.REVERSED
    locked.save(update_fields=["status", "updated_at"])
    _audit_depreciation(reversal, actor)
    return reversal


def _audit_depreciation(run, actor):
    record_audit_event(
        action=AuditAction.FIXED_ASSET_DEPRECIATION_TRANSITIONED,
        entity_type="depreciation_run",
        entity_id=run.pk,
        organization=run.organization,
        actor=actor,
        metadata={
            "period_id": str(run.fiscal_period_id),
            "status": run.status,
            "occurrence_key": run.occurrence_key,
            "reason": run.reason,
        },
    )


@transaction.atomic
def prepare_handoff(
    *,
    organization: Organization,
    actor,
    consumer: str,
    occurrence_key: str,
    asset_transaction: AssetTransaction | None = None,
    depreciation_line: DepreciationLine | None = None,
) -> FixedAssetSourceEnvelope:
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.FIXED_ASSET_HANDOFF_PREPARE,
    )
    if bool(asset_transaction) == bool(depreciation_line):
        raise ValueError("پیشنهاد باید دقیقاً یک منبع داشته باشد.")
    if asset_transaction:
        source = AssetTransaction.objects.get(
            pk=asset_transaction.pk,
            organization=organization,
            status=TransactionStatus.FINALIZED,
        )
        amount = source.amount
    else:
        source = DepreciationLine.objects.select_related("run").get(
            pk=depreciation_line.pk,
            organization=organization,
            run__status=DepreciationRunStatus.FINALIZED,
        )
        amount = source.depreciation_amount
    duplicate_source = FixedAssetSourceEnvelope.objects.filter(
        organization=organization,
        consumer=consumer,
        asset_transaction=source if asset_transaction else None,
        depreciation_line=source if depreciation_line else None,
    ).first()
    if duplicate_source and duplicate_source.occurrence_key != occurrence_key:
        raise ValueError(
            "یک منبع دارایی نمی‌تواند دوباره به همان مصرف‌کننده پیشنهاد شود."
        )
    envelope = FixedAssetSourceEnvelope.objects.filter(
        organization=organization, consumer=consumer, occurrence_key=occurrence_key
    ).first()
    if envelope:
        expected_id = (
            asset_transaction.pk if asset_transaction else depreciation_line.pk
        )
        actual_id = (
            envelope.asset_transaction_id
            if asset_transaction
            else envelope.depreciation_line_id
        )
        if envelope.amount != amount or actual_id != expected_id:
            raise ValueError("کلید پیشنهاد با محتوای متفاوت تکرار شده است.")
        return envelope
    envelope = FixedAssetSourceEnvelope(
        organization=organization,
        consumer=consumer,
        occurrence_key=occurrence_key,
        asset_transaction=source if asset_transaction else None,
        depreciation_line=source if depreciation_line else None,
        amount=amount,
        prepared_by=actor,
    )
    envelope.full_clean()
    envelope.save()
    return envelope


@transaction.atomic
def review_handoff(
    *, organization: Organization, actor, envelope: FixedAssetSourceEnvelope
) -> FixedAssetSourceEnvelope:
    locked = FixedAssetSourceEnvelope.objects.select_for_update().get(
        pk=envelope.pk, organization=organization
    )
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.FIXED_ASSET_HANDOFF_REVIEW,
    )
    if locked.status != EnvelopeStatus.PREPARED or locked.prepared_by_id == actor.pk:
        raise ValueError("بررسی مستقل فقط برای پیشنهاد تهیه‌شده مجاز است.")
    locked.status = EnvelopeStatus.REVIEWED
    locked.reviewed_by = actor
    locked.reviewed_at = timezone.now()
    locked.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
    record_audit_event(
        action=AuditAction.FIXED_ASSET_HANDOFF_TRANSITIONED,
        entity_type="fixed_asset_handoff",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={
            "consumer": locked.consumer,
            "status": locked.status,
            "occurrence_key": locked.occurrence_key,
        },
    )
    return locked


@transaction.atomic
def reconcile_handoff(
    *,
    organization: Organization,
    actor,
    envelope: FixedAssetSourceEnvelope,
    consumer_reference: str,
    consumer_amount: Decimal | None,
    disposition: str = "",
) -> AssetReconciliationEvidence:
    locked = FixedAssetSourceEnvelope.objects.select_for_update().get(
        pk=envelope.pk, organization=organization
    )
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.FIXED_ASSET_HANDOFF_RECONCILE,
    )
    if locked.status not in {
        EnvelopeStatus.REVIEWED,
        EnvelopeStatus.ACKNOWLEDGED,
        EnvelopeStatus.REJECTED,
    }:
        raise ValueError("پیشنهاد هنوز قابل تطبیق نیست.")
    difference = None if consumer_amount is None else locked.amount - consumer_amount
    evidence = AssetReconciliationEvidence(
        organization=organization,
        envelope=locked,
        source_amount=locked.amount,
        consumer_amount=consumer_amount,
        difference=difference,
        consumer_reference=consumer_reference,
        disposition=disposition,
        recorded_by=actor,
    )
    evidence.full_clean()
    evidence.save()
    locked.status = EnvelopeStatus.RECONCILED
    locked.consumer_reference = consumer_reference
    locked.reconciliation_note = disposition
    locked.save(
        update_fields=[
            "status",
            "consumer_reference",
            "reconciliation_note",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.FIXED_ASSET_HANDOFF_TRANSITIONED,
        entity_type="fixed_asset_handoff",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={
            "consumer": locked.consumer,
            "status": locked.status,
            "occurrence_key": locked.occurrence_key,
            "consumer_reference": consumer_reference,
            "source_amount": str(locked.amount),
            "consumer_amount": (
                None if consumer_amount is None else str(consumer_amount)
            ),
            "difference": None if difference is None else str(difference),
            "disposition": disposition,
        },
    )
    return evidence


def _audit_asset(asset, actor, event):
    record_audit_event(
        action=AuditAction.FIXED_ASSET_TRANSITIONED,
        entity_type="fixed_asset",
        entity_id=asset.pk,
        organization=asset.organization,
        actor=actor,
        metadata={
            "asset_number": asset.asset_number,
            "status": asset.status,
            "event": event,
        },
    )
