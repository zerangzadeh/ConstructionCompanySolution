from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, models, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.inventory.models import InventoryValuationPool
from apps.organizations.authorization import (
    has_business_permission,
    require_business_permission,
    scope_queryset,
)
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.procurement.models import GoodsReceipt, GoodsReceiptStatus
from apps.projects.models import (
    BudgetAllocation,
    BudgetVersionStatus,
    Project,
    ProjectCostFact,
    ProjectCostFactKind,
)
from apps.reporting.models import (
    MetricDefinitionVersion,
    MetricExportManifest,
    MetricFreshness,
    MetricRefreshRun,
    MetricResult,
    MetricResultReview,
    MetricRunStatus,
    MetricVersionStatus,
)
from apps.treasury.models import TreasuryMovementClearing, TreasuryMovementKind

# Closed P10 catalogue: keeping all codes explicit here also makes permission
# enforcement ownership mechanically auditable without granting any default role.
REPORTING_PERMISSION_CATALOGUE = (
    BusinessPermissionCode.REPORTING_METRIC_CATALOG_VIEW,
    BusinessPermissionCode.REPORTING_METRIC_DEFINITION_PREPARE,
    BusinessPermissionCode.REPORTING_METRIC_DEFINITION_REVIEW,
    BusinessPermissionCode.REPORTING_METRIC_DEFINITION_PUBLISH,
    BusinessPermissionCode.REPORTING_METRIC_RESULT_VIEW,
    BusinessPermissionCode.REPORTING_METRIC_RESULT_VIEW_SENSITIVE,
    BusinessPermissionCode.REPORTING_PORTFOLIO_VIEW,
    BusinessPermissionCode.REPORTING_METRIC_REFRESH_RUN,
    BusinessPermissionCode.REPORTING_METRIC_REFRESH_REVIEW,
    BusinessPermissionCode.REPORTING_SOURCE_DRILLTHROUGH_VIEW,
    BusinessPermissionCode.REPORTING_SAVED_VIEW_MANAGE_OWN,
    BusinessPermissionCode.REPORTING_SAVED_VIEW_MANAGE_SHARED,
    BusinessPermissionCode.REPORTING_EXPORT_CREATE,
    BusinessPermissionCode.REPORTING_EXPORT_DOWNLOAD,
    BusinessPermissionCode.REPORTING_EXPORT_SENSITIVE,
    BusinessPermissionCode.REPORTING_AUDIT_VIEW,
)


def _json_default(value: object) -> str:
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def _hash(payload: object) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=_json_default
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _advisory_lock(*parts: object) -> None:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode()).digest()
    lock_id = int.from_bytes(digest[:8], byteorder="big", signed=True)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_id])


def _allowed_projects(*, user: User, organization: Organization):
    membership = require_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.REPORTING_METRIC_RESULT_VIEW,
        message="اجازه مشاهده نتیجه شاخص را ندارید.",
        allow_any_scope=True,
    )
    return scope_queryset(
        Project.objects.filter(organization=organization, deleted_at__isnull=True),
        membership=membership,
        project_lookup="pk",
        include_site_parent=True,
    )


def _project_ids(projects) -> list[str]:
    return [
        str(value) for value in projects.order_by("pk").values_list("pk", flat=True)
    ]


@dataclass(frozen=True, slots=True)
class Calculation:
    value: dict[str, str | int | None]
    currency: str
    unit: str
    coverage: dict[str, object]
    sources: dict[str, object]


def _budget(
    organization: Organization, projects, *, as_of: datetime | None = None
) -> Calculation:
    as_of = as_of or timezone.now()
    rows = BudgetAllocation.objects.filter(
        organization=organization,
        manifest_line__manifest__budget__status=BudgetVersionStatus.ACCEPTED,
        manifest_line__manifest__budget__accepted_at__lte=as_of,
        manifest_line__manifest__budget__governing_for__project__in=projects,
        created_at__lte=as_of,
    )
    lines = list(
        rows.order_by("pk").values_list(
            "pk",
            "amount",
            "manifest_line__manifest__budget_id",
            "manifest_line__manifest__budget__version_number",
            "manifest_line__manifest__budget__currency",
            "manifest_line__manifest__budget__project_id",
        )
    )
    currencies = {line[4] for line in lines}
    total = sum((line[1] for line in lines), Decimal("0.00"))
    covered_projects = len({line[5] for line in lines})
    eligible_projects = projects.count()
    complete = (
        bool(lines)
        and len(currencies) == 1
        and covered_projects == eligible_projects
    )
    return Calculation(
        {"amount": format(total, "f") if complete else None},
        next(iter(currencies)) if len(currencies) == 1 else "",
        "money",
        {
            "complete": complete,
            "source_count": len(lines),
            "covered_projects": covered_projects,
            "eligible_projects": eligible_projects,
        },
        {
            "model": "projects.BudgetAllocation",
            "ids": [str(line[0]) for line in lines],
            "budget_versions": sorted(
                {f"{line[2]}:v{line[3]}" for line in lines}
            ),
        },
    )


def _cost(
    organization: Organization,
    projects,
    *,
    actual: bool,
    as_of: datetime | None = None,
) -> Calculation:
    as_of = as_of or timezone.now()
    kinds = (
        [ProjectCostFactKind.ACTUAL_RECOGNIZED, ProjectCostFactKind.ACTUAL_REVERSAL]
        if actual
        else [
            ProjectCostFactKind.COMMITMENT_AUTHORIZED,
            ProjectCostFactKind.COMMITMENT_ADJUSTMENT,
            ProjectCostFactKind.COMMITMENT_RELIEF,
        ]
    )
    rows = ProjectCostFact.objects.filter(
        organization=organization,
        project__in=projects,
        kind__in=kinds,
        recognition_date__lte=as_of.date(),
        created_at__lte=as_of,
    )
    facts = list(
        rows.order_by("pk").values_list(
            "pk", "project_id", "kind", "amount", "currency",
            "source_id", "source_version", "source_line_id",
            "contract__producer_key", "contract__version",
        )
    )
    currencies = {fact[4] for fact in facts}
    total = sum(
        (
            -fact[3]
            if fact[2] == ProjectCostFactKind.COMMITMENT_RELIEF
            else fact[3]
            for fact in facts
        ),
        Decimal("0.00"),
    )
    covered_projects = len({fact[1] for fact in facts})
    total_projects = projects.count()
    # Project Controls does not certify complete producer coverage in this phase.
    # Fact presence is evidence of a partial projection, never coverage proof.
    complete = False
    return Calculation(
        {"amount": format(total, "f") if facts and len(currencies) == 1 else None},
        next(iter(currencies)) if len(currencies) == 1 else "",
        "money",
        {
            "complete": complete,
            "covered_projects": covered_projects,
            "eligible_projects": total_projects,
            "source_count": len(facts),
            "coverage_reason": "project_cost_producer_coverage_not_certified",
        },
        {
            "model": "projects.ProjectCostFact",
            "ids": [str(fact[0]) for fact in facts],
            "source_versions": [
                {
                    "fact_id": str(fact[0]),
                    "source_id": fact[5],
                    "source_version": fact[6],
                    "source_line_id": fact[7],
                    "producer_key": fact[8],
                    "contract_version": fact[9],
                }
                for fact in facts
            ],
        },
    )


def _cash(organization: Organization, projects) -> Calculation:
    del projects
    rows = TreasuryMovementClearing.objects.filter(
        organization=organization,
        active=True,
    ).select_related("movement")
    total = Decimal(0)
    ids: list[str] = []
    for clearing in rows.order_by("pk"):
        movement = clearing.movement
        sign = (
            Decimal(1) if movement.kind == TreasuryMovementKind.RECEIPT else Decimal(-1)
        )
        if movement.kind == TreasuryMovementKind.TRANSFER:
            sign = Decimal(0)
        if movement.kind == TreasuryMovementKind.REVERSAL and movement.reverses_id:
            sign = (
                Decimal(-1)
                if movement.reverses.kind == TreasuryMovementKind.RECEIPT
                else Decimal(1)
            )
        total += movement.amount * sign
        ids.append(str(clearing.pk))
    return Calculation(
        {"amount": format(total, "f") if ids else None},
        "IRR",
        "money",
        {"complete": bool(ids), "source_count": len(ids)},
        {"model": "treasury.TreasuryMovementClearing", "ids": ids},
    )


def _procurement(organization: Organization, projects) -> Calculation:
    rows = GoodsReceipt.objects.filter(
        organization=organization,
        project__in=projects,
        status=GoodsReceiptStatus.POSTED,
        purchase_order__purchase_request__submitted_at__isnull=False,
    ).select_related("purchase_order__purchase_request")
    durations: list[int] = []
    ids: list[str] = []
    for receipt in rows.order_by("pk"):
        start = receipt.purchase_order.purchase_request.submitted_at
        if start and receipt.posted_at and receipt.posted_at >= start:
            durations.append(int((receipt.posted_at - start).total_seconds()))
            ids.append(str(receipt.pk))
    average = sum(durations) // len(durations) if durations else None
    return Calculation(
        {"average_seconds": average, "completed_cycles": len(durations)},
        "",
        "seconds",
        {"complete": bool(ids), "source_count": len(ids)},
        {"model": "procurement.GoodsReceipt", "ids": ids},
    )


def _inventory(organization: Organization, projects) -> Calculation:
    del projects
    rows = InventoryValuationPool.objects.filter(organization=organization)
    totals = rows.aggregate(quantity=Sum("quantity"), value=Sum("value_amount"))
    ids = list(rows.order_by("pk").values_list("pk", flat=True))
    currencies = list(rows.values_list("currency", flat=True).distinct())
    currency = currencies[0] if len(currencies) == 1 else ""
    complete = bool(ids) and len(currencies) == 1
    return Calculation(
        {
            "quantity": (
                format(totals["quantity"], "f")
                if totals["quantity"] is not None
                else None
            ),
            "value_amount": (
                format(totals["value"], "f") if totals["value"] is not None else None
            ),
        },
        currency,
        "quantity_and_money",
        {"complete": complete, "source_count": len(ids)},
        {"model": "inventory.InventoryValuationPool", "ids": [str(v) for v in ids]},
    )


CALCULATORS: dict[str, Callable[[Organization, Any], Calculation]] = {
    "approved_budget": _budget,
    "committed_cost": lambda organization, projects: _cost(
        organization, projects, actual=False
    ),
    "actual_cost_coverage": lambda organization, projects: _cost(
        organization, projects, actual=True
    ),
    "cleared_cash_position": _cash,
    "procurement_cycle_time": _procurement,
    "inventory_quantity_value": _inventory,
}


@transaction.atomic
def refresh_metric(
    *,
    organization: Organization,
    actor: User,
    metric_code: str,
    idempotency_key: str,
    project: Project | None = None,
) -> MetricResult:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.REPORTING_METRIC_REFRESH_RUN,
        message="اجازه اجرای شاخص را ندارید.",
        project=project,
        allow_any_scope=project is None,
    )
    if project is None:
        require_business_permission(
            user=actor,
            organization=organization,
            permission=BusinessPermissionCode.REPORTING_PORTFOLIO_VIEW,
            message="اجازه مشاهده سبد پروژه را ندارید.",
            allow_any_scope=True,
        )
    elif project.organization_id != organization.pk:
        raise PermissionDenied("پروژه متعلق به این شرکت نیست.")
    _advisory_lock("reporting-refresh", organization.pk, idempotency_key)
    projects = _allowed_projects(user=actor, organization=organization)
    if project is not None:
        projects = projects.filter(pk=project.pk)
        if not projects.exists():
            raise PermissionDenied("پروژه خارج از دامنه مجاز است.")
    version = (
        MetricDefinitionVersion.objects.select_for_update()
        .select_related("definition")
        .get(
            definition__code=metric_code,
            definition__is_active=True,
            status=MetricVersionStatus.PUBLISHED,
        )
    )
    organization_wide = metric_code in {
        "cleared_cash_position",
        "inventory_quantity_value",
    }
    require_business_permission(
        user=actor,
        organization=organization,
        permission=version.definition.source_permission,
        message="مجوز دامنه منبع برای اجرای شاخص وجود ندارد.",
        project=project,
        allow_any_scope=project is None and not organization_wide,
    )
    fingerprint = _hash(
        {
            "metric_version": str(version.pk),
            "organization": str(organization.pk),
            "project": str(project.pk) if project else None,
            "projects": _project_ids(projects),
        }
    )
    existing = (
        MetricRefreshRun.objects.select_for_update()
        .filter(organization=organization, idempotency_key=idempotency_key)
        .first()
    )
    if existing:
        if existing.request_fingerprint != fingerprint:
            raise ValidationError("کلید تکرار با درخواست متفاوت استفاده شده است.")
        if existing.status == MetricRunStatus.SUCCEEDED:
            return existing.result
        raise ValidationError("اجرای قبلی این کلید نهایی نشده است.")
    now = timezone.now()
    run = MetricRefreshRun.objects.create(
        organization=organization,
        metric_version=version,
        project=project,
        status=MetricRunStatus.BUILDING,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        requested_by=actor,
        started_at=now,
    )
    if metric_code == "approved_budget":
        calculation = _budget(organization, projects, as_of=now)
    elif metric_code in {"committed_cost", "actual_cost_coverage"}:
        calculation = _cost(
            organization,
            projects,
            actual=metric_code == "actual_cost_coverage",
            as_of=now,
        )
    else:
        calculation = CALCULATORS[metric_code](organization, projects)
    sources = {
        **calculation.sources,
        "scope_kind": "organization" if organization_wide else "project_set",
        "scope_project_ids": _project_ids(projects),
    }
    source_watermark = _hash(sources)
    calculation_payload = {
        "metric": metric_code,
        "version": version.version,
        "value": calculation.value,
        "coverage": calculation.coverage,
        "sources": sources,
        "project": str(project.pk) if project else None,
    }
    previous = (
        MetricResult.objects.filter(
            organization=organization, metric_code=metric_code, project=project
        )
        .order_by("-created_at")
        .first()
    )
    if previous is not None:
        MetricResult.objects.filter(pk=previous.pk).update(
            freshness=MetricFreshness.STALE
        )
    result = MetricResult.objects.create(
        organization=organization,
        run=run,
        project=project,
        metric_code=metric_code,
        value=calculation.value,
        currency=calculation.currency,
        unit=calculation.unit,
        as_of=now,
        freshness=(
            MetricFreshness.FRESH
            if bool(calculation.coverage.get("complete"))
            else MetricFreshness.INCOMPLETE
        ),
        coverage=calculation.coverage,
        source_manifest=sources,
        calculation_hash=_hash(calculation_payload),
        replaces=previous,
    )
    MetricRefreshRun.objects.filter(pk=run.pk).update(
        status=MetricRunStatus.SUCCEEDED,
        source_watermark=source_watermark,
        finished_at=timezone.now(),
    )
    record_audit_event(
        action=AuditAction.REPORTING_METRIC_REFRESHED,
        entity_type="reporting.MetricResult",
        entity_id=str(result.pk),
        organization=organization,
        actor=actor,
        metadata={
            "metric_code": metric_code,
            "project_id": str(project.pk) if project else "",
        },
    )
    return result


@transaction.atomic
def review_metric_result(
    *, result: MetricResult, reviewer: User, reason: str
) -> MetricResultReview:
    require_business_permission(
        user=reviewer,
        organization=result.organization,
        permission=BusinessPermissionCode.REPORTING_METRIC_REFRESH_REVIEW,
        message="اجازه بررسی نتیجه شاخص را ندارید.",
        project=result.project,
        allow_any_scope=result.project_id is None,
    )
    if (
        result.run.metric_version.definition.requires_independent_review
        and result.run.requested_by_id == reviewer.pk
    ):
        raise PermissionDenied("اجراکننده نمی‌تواند نتیجه مالی خود را تأیید کند.")
    review, created = MetricResultReview.objects.get_or_create(
        organization=result.organization,
        result=result,
        defaults={"reviewer": reviewer, "reason": reason.strip()},
    )
    if not created and (
        review.reviewer_id != reviewer.pk or review.reason != reason.strip()
    ):
        raise ValidationError("نتیجه قبلاً با شواهد متفاوت بررسی شده است.")
    return review


def dashboard_results(
    *, organization: Organization, actor: User, include_incomplete: bool = False
) -> list[MetricResult]:
    projects = _allowed_projects(user=actor, organization=organization)
    allowed_ids = list(projects.values_list("pk", flat=True))
    allowed_text_ids = {str(value) for value in allowed_ids}
    organization_scope = has_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.REPORTING_METRIC_RESULT_VIEW,
    )
    rows = (
        MetricResult.objects.filter(organization=organization)
        .filter(models.Q(project__isnull=True) | models.Q(project_id__in=allowed_ids))
        .exclude(
            run__metric_version__definition__requires_independent_review=True,
            review__isnull=True,
        )
    )
    latest: dict[tuple[str, str | None], MetricResult] = {}
    seen: set[tuple[str, str | None]] = set()
    for result in rows.select_related("run__metric_version__definition").order_by(
        "-created_at", "-pk"
    ):
        if result.project_id is None:
            if result.source_manifest.get("scope_kind") == "organization":
                if not organization_scope:
                    continue
            elif not set(result.source_manifest.get("scope_project_ids", [])).issubset(
                allowed_text_ids
            ):
                continue
        key = (
            result.metric_code,
            str(result.project_id) if result.project_id else None,
        )
        if key in seen:
            continue
        seen.add(key)
        definition = result.run.metric_version.definition
        if (
            (
                not include_incomplete
                and (
                    result.freshness != MetricFreshness.FRESH
                    or not result.coverage.get("complete")
                )
            )
            or not definition.is_active
            or result.run.metric_version.status != MetricVersionStatus.PUBLISHED
        ):
            continue
        if not has_business_permission(
            user=actor,
            organization=organization,
            permission=definition.source_permission,
            project=result.project,
            allow_any_scope=result.project_id is None
            and result.source_manifest.get("scope_kind") != "organization",
        ):
            continue
        latest[key] = result
    return sorted(latest.values(), key=lambda item: item.metric_code)


def drillthrough_manifest(
    *, organization: Organization, actor: User, result_id: str
) -> MetricResult:
    result = (
        MetricResult.objects.select_related(
            "project", "run__metric_version__definition"
        )
        .filter(organization=organization, pk=result_id)
        .first()
    )
    if result is None:
        raise PermissionDenied("نتیجه شاخص در دسترس نیست.")
    organization_wide = result.source_manifest.get("scope_kind") == "organization"
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.REPORTING_METRIC_RESULT_VIEW,
        message="اجازه مشاهده نتیجه شاخص را ندارید.",
        project=result.project,
        allow_any_scope=result.project_id is None and not organization_wide,
    )
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.REPORTING_SOURCE_DRILLTHROUGH_VIEW,
        message="اجازه مشاهده منبع شاخص را ندارید.",
        project=result.project,
        allow_any_scope=result.project_id is None and not organization_wide,
    )
    require_business_permission(
        user=actor,
        organization=organization,
        permission=result.run.metric_version.definition.source_permission,
        message="مجوز دامنه منبع برای مشاهده جزئیات وجود ندارد.",
        project=result.project,
        allow_any_scope=result.project_id is None and not organization_wide,
    )
    if result.project_id is None and not organization_wide:
        allowed = {
            str(value)
            for value in _allowed_projects(
                user=actor, organization=organization
            ).values_list("pk", flat=True)
        }
        if not set(result.source_manifest.get("scope_project_ids", [])).issubset(
            allowed
        ):
            raise PermissionDenied("دامنه فعلی همه منابع این نتیجه را پوشش نمی‌دهد.")
    return result


@transaction.atomic
def export_dashboard_csv(
    *,
    organization: Organization,
    actor: User,
    idempotency_key: str,
    purpose: str,
) -> tuple[MetricExportManifest, bytes]:
    for permission in (
        BusinessPermissionCode.REPORTING_EXPORT_CREATE,
        BusinessPermissionCode.REPORTING_EXPORT_DOWNLOAD,
    ):
        require_business_permission(
            user=actor,
            organization=organization,
            permission=permission,
            message="اجازه ایجاد یا دریافت خروجی شاخص را ندارید.",
            allow_any_scope=True,
        )
    _advisory_lock("reporting-export", organization.pk, idempotency_key)
    # Exports retain explicit freshness/coverage evidence; incomplete values are
    # suppressed only from KPI cards, not from the governed audit export.
    results = dashboard_results(
        organization=organization, actor=actor, include_incomplete=True
    )
    result_ids = [str(item.pk) for item in results]
    fingerprint = _hash({"result_ids": result_ids, "purpose": purpose.strip()})
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "metric_code",
            "persian_name",
            "value",
            "currency",
            "unit",
            "as_of",
            "freshness",
        ]
    )
    for item in results:
        writer.writerow(
            [
                item.metric_code,
                item.run.metric_version.definition.persian_name,
                json.dumps(item.value, ensure_ascii=False, sort_keys=True),
                item.currency,
                item.unit,
                item.as_of.isoformat(),
                item.freshness,
            ]
        )
    content = output.getvalue().encode("utf-8-sig")
    content_hash = hashlib.sha256(content).hexdigest()
    manifest = MetricExportManifest.objects.filter(
        organization=organization, idempotency_key=idempotency_key
    ).first()
    if manifest:
        if (
            manifest.request_fingerprint != fingerprint
            or manifest.content_hash != content_hash
        ):
            raise ValidationError("کلید تکرار خروجی با محتوای متفاوت استفاده شده است.")
        return manifest, content
    manifest = MetricExportManifest.objects.create(
        organization=organization,
        created_by=actor,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        metric_codes=[item.metric_code for item in results],
        result_ids=result_ids,
        content_hash=content_hash,
        purpose=purpose.strip(),
        expires_at=timezone.now() + timedelta(hours=1),
    )
    record_audit_event(
        action=AuditAction.REPORTING_EXPORTED,
        entity_type="reporting.MetricExportManifest",
        entity_id=str(manifest.pk),
        organization=organization,
        actor=actor,
        metadata={"result_count": len(result_ids)},
    )
    return manifest, content
