"""Selectors and validation for interval-based Equipment usage."""

from datetime import UTC, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db.models import F, Q
from django.utils import timezone

from apps.equipment.models import EquipmentAssignment, EquipmentAssignmentStatus
from apps.equipment.p8_models import OperatorEquipmentQualification
from apps.organizations.authorization import scope_queryset
from apps.workforce.models import EmployeeStatus, QualificationLifecycleEventKind


def usage_interval(started_at, ended_at, runtime_hours):
    if timezone.is_naive(started_at) or timezone.is_naive(ended_at):
        raise ValidationError(
            {"started_at": "زمان شروع و پایان باید دارای منطقه زمانی باشند."}
        )
    start, end = started_at.astimezone(UTC), ended_at.astimezone(UTC)
    if end <= start:
        raise ValidationError({"ended_at": "پایان کارکرد باید پس از شروع باشد."})
    elapsed = end - start
    seconds = Decimal(elapsed.days * 86400 + elapsed.seconds) + Decimal(
        elapsed.microseconds
    ).scaleb(-6)
    if (
        not runtime_hours.is_finite()
        or runtime_hours <= 0
        or runtime_hours * 3600 > seconds
    ):
        raise ValidationError(
            {
                "runtime_hours": "ساعت کار باید بیشتر از صفر و حداکثر برابر مدت بین شروع و پایان باشد."
            }
        )
    return start, end


def usage_dates(organization, start, end):
    zone = ZoneInfo(organization.settings.timezone)
    return start.astimezone(zone).date(), (end - timedelta(microseconds=1)).astimezone(
        zone
    ).date()


def active_usage_deployments(membership):
    deployments = EquipmentAssignment.objects.filter(
        status=EquipmentAssignmentStatus.ACTIVE,
        equipment__archived_at__isnull=True,
        project__deleted_at__isnull=True,
    ).filter(
        Q(site__isnull=True) | Q(site__is_active=True, site__project_id=F("project_id"))
    )
    return scope_queryset(
        deployments,
        membership=membership,
        project_lookup="project_id",
        site_lookup="site_id",
    ).select_related("equipment", "project", "site")


def operator_qualifications(organization, first_day, last_day):
    return (
        OperatorEquipmentQualification.objects.filter(
            organization=organization,
            revoked_at__isnull=True,
            employee__organization=organization,
            employee__status=EmployeeStatus.ACTIVE,
            employee__archived_at__isnull=True,
            workforce_qualification__organization=organization,
            workforce_qualification__employee_id=F("employee_id"),
            effective_from__lte=first_day,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=last_day))
        .filter(
            Q(workforce_qualification__issued_on__isnull=True)
            | Q(workforce_qualification__issued_on__lte=first_day)
        )
        .filter(
            Q(workforce_qualification__valid_until__isnull=True)
            | Q(workforce_qualification__valid_until__gte=last_day)
        )
        .exclude(
            workforce_qualification__lifecycle_events__kind__in=[
                QualificationLifecycleEventKind.REVOKED,
                QualificationLifecycleEventKind.SUPERSEDED,
            ]
        )
    )
