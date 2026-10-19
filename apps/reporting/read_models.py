"""Read-only reporting layers over the closed, source-owned metric catalogue."""

from dataclasses import dataclass
from datetime import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import F, Q, Window
from django.db.models.functions import RowNumber
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.authorization import (
    has_business_permission,
    require_business_permission,
    scope_queryset,
)
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization
from apps.projects.models import Project

from .catalog import METRIC_SPECS
from .models import (
    MetricFreshness,
    MetricResult,
    MetricResultReview,
    MetricRunStatus,
    MetricVersionStatus,
)

DENIED = "نتیجه شاخص در دسترس نیست."


@dataclass(frozen=True)
class MetricCard:
    result: MetricResult
    reviewed: bool
    usable: bool
    can_drillthrough: bool


@dataclass(frozen=True)
class ReportingLayer:
    code: str
    title: str
    description: str
    cards: tuple[MetricCard, ...]
    available: bool = True


@dataclass(frozen=True)
class ReportingReadModel:
    as_of: datetime
    observed_at: datetime
    layers: tuple[ReportingLayer, ...]


def _visible(
    *, result: MetricResult, organization: Organization, actor: User, projects: dict
) -> bool:
    """Check the whole retained source scope before any grouping or display."""
    definition = result.run.metric_version.definition
    if (
        result.organization_id != organization.pk
        or result.run.organization_id != organization.pk
        or result.project_id != result.run.project_id
        or result.metric_code != definition.code
        or result.metric_code not in METRIC_SPECS
        or definition.source_permission
        != METRIC_SPECS[result.metric_code]["source_permission"]
    ):
        return False
    permissions = [P.REPORTING_METRIC_RESULT_VIEW, definition.source_permission]
    if definition.sensitivity != "normal":
        permissions.append(P.REPORTING_METRIC_RESULT_VIEW_SENSITIVE)
    manifest = result.source_manifest
    if manifest.get("scope_kind") == "organization":
        return all(
            has_business_permission(
                user=actor, organization=organization, permission=permission
            )
            for permission in permissions
        )
    ids = manifest.get("scope_project_ids")
    if (
        manifest.get("scope_kind") != "project_set"
        or not isinstance(ids, list)
        or any(not isinstance(value, str) or value not in projects for value in ids)
        or (result.project_id and set(ids) != {str(result.project_id)})
    ):
        return False
    # An empty result still requires source permission and explicit active scope.
    return all(
        has_business_permission(
            user=actor,
            organization=organization,
            permission=permission,
            project=projects[project_id] if project_id else None,
            allow_any_scope=project_id is None,
        )
        for permission in permissions
        for project_id in (ids or [None])
    )


def _projects(*, organization: Organization, actor: User) -> dict:
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=P.REPORTING_METRIC_RESULT_VIEW,
        message=DENIED,
        allow_any_scope=True,
    )
    # A site grant cannot expose an aggregate for its entire parent project.
    return {
        str(project.pk): project
        for project in scope_queryset(
            Project.objects.filter(organization=organization, deleted_at__isnull=True),
            membership=membership,
            project_lookup="pk",
        )
    }


def reporting_layers(
    *, organization: Organization, actor: User, as_of: datetime | None = None
) -> ReportingReadModel:
    observed_at = timezone.now()
    as_of = as_of or observed_at
    if timezone.is_naive(as_of) or as_of > observed_at:
        raise ValidationError("زمان مبنا باید معتبر و حداکثر زمان مشاهده باشد.")
    projects = _projects(organization=organization, actor=actor)
    rows = (
        MetricResult.objects.filter(
            organization=organization,
            run__organization=organization,
            metric_code__in=METRIC_SPECS,
            run__status=MetricRunStatus.SUCCEEDED,
            run__metric_version__status=MetricVersionStatus.PUBLISHED,
            run__metric_version__definition__is_active=True,
            created_at__lte=as_of,
            as_of__lte=as_of,
            run__finished_at__lte=as_of,
        )
        .filter(Q(project__isnull=True) | Q(project_id__in=projects))
        .annotate(
            latest_row=Window(
                expression=RowNumber(),
                partition_by=[F("metric_code"), F("project_id")],
                order_by=[F("created_at").desc(), F("pk").desc()],
            )
        )
        .filter(latest_row=1)
        .select_related("project", "run__metric_version__definition")
        .order_by("-created_at", "-pk")
    )
    selected = {}
    for result in rows:
        if not _visible(
            result=result, organization=organization, actor=actor, projects=projects
        ):
            continue
        # Retained snapshots are alternatives, never additive source facts.
        selected.setdefault((result.metric_code, result.project_id), result)
    reviewed = set(
        MetricResultReview.objects.filter(
            organization=organization,
            result_id__in=[result.pk for result in selected.values()],
            created_at__lte=as_of,
        ).values_list("result_id", flat=True)
    )
    cards = []
    for result in selected.values():
        definition = result.run.metric_version.definition
        reviewed_result = (
            not definition.requires_independent_review or result.pk in reviewed
        )
        cards.append(
            MetricCard(
                result=result,
                reviewed=reviewed_result,
                usable=reviewed_result
                and result.freshness == MetricFreshness.FRESH
                and result.coverage.get("complete") is True,
                can_drillthrough=has_business_permission(
                    user=actor,
                    organization=organization,
                    permission=P.REPORTING_SOURCE_DRILLTHROUGH_VIEW,
                    project=result.project,
                    allow_any_scope=result.project_id is None
                    and result.source_manifest.get("scope_kind") != "organization",
                ),
            )
        )
    cards = tuple(
        sorted(
            cards,
            key=lambda card: (card.result.metric_code, str(card.result.project_id)),
        )
    )
    usable = tuple(card for card in cards if card.usable)
    portfolio = has_business_permission(
        user=actor,
        organization=organization,
        permission=P.REPORTING_PORTFOLIO_VIEW,
        allow_any_scope=True,
    )
    return ReportingReadModel(
        as_of=as_of,
        observed_at=observed_at,
        layers=(
            ReportingLayer(
                "operational", "عملیاتی", "وضعیت آخرین شواهد مجاز و مسیر منبع", cards
            ),
            ReportingLayer(
                "exception",
                "استثناها",
                "شواهد ناقص، قدیمی یا در انتظار بررسی؛ بدون مقدار قابل اتکا",
                tuple(card for card in cards if not card.usable),
            ),
            ReportingLayer(
                "management",
                "مدیریتی",
                "نتایج کامل و به‌روز با بررسی لازم؛ هر دامنه جداگانه",
                usable,
            ),
            ReportingLayer(
                "executive",
                "اجرایی و سبد پروژه",
                "همان نتایج مجاز در دامنه سبد؛ بدون جمع‌زدن اسنپ‌شات‌ها",
                usable if portfolio else (),
                portfolio,
            ),
        ),
    )


def require_result_scope(
    *, organization: Organization, actor: User, result: MetricResult
) -> None:
    """Retained drill-through rechecks full source scope, including history."""
    if not _visible(
        result=result,
        organization=organization,
        actor=actor,
        projects=_projects(organization=organization, actor=actor),
    ):
        raise PermissionDenied(DENIED)
