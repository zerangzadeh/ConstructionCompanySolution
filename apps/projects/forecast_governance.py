"""Governed forecast versions, with workflow-owned reviewer actions."""

from __future__ import annotations

from hashlib import sha256
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import get_active_membership
from apps.organizations.models import (
    BusinessPermissionCode,
    MembershipStatus,
    Organization,
    OrganizationMembership,
)
from apps.projects.models import (
    ForecastReviewStatus,
    Project,
    ProjectBudgetControl,
    ProjectCostForecast,
    ProjectForecastReview,
    ProjectForecastTransition,
)
from apps.projects.services import _require_budget_access
from apps.workflows.models import (
    WorkflowInstance,
    WorkflowVersion,
    WorkItem,
    WorkItemStatus,
)
from apps.workflows.registry import SubjectSnapshot, registry
from apps.workflows.runtime import start_workflow

WORKFLOW_TYPE_CODE = "projects.forecast_approval"
SUBJECT_TYPE = "projects.project_cost_forecast"


def _locked_review(*, forecast: ProjectCostForecast) -> ProjectForecastReview:
    return (
        ProjectForecastReview.objects.select_for_update(of=("self",))
        .select_related("forecast", "project", "predecessor")
        .get(forecast=forecast, organization=forecast.organization)
    )


def _record_transition(
    *, review: ProjectForecastReview, actor: User, new_status: str, reason: str
) -> None:
    if not reason.strip():
        raise ValidationError("A forecast decision reason is required.")
    previous = review.status
    sequence = (review.transitions.aggregate(value=Max("sequence"))["value"] or 0) + 1
    review.status = new_status
    review._transition_authorized = True
    try:
        review.save(update_fields=["status", "updated_at"])
    finally:
        del review._transition_authorized
    ProjectForecastTransition.objects.create(
        organization=review.organization,
        review=review,
        sequence=sequence,
        previous_status=previous,
        new_status=new_status,
        reason=reason.strip(),
        actor=actor,
    )
    record_audit_event(
        action=AuditAction.PROJECT_COST_FORECAST_TRANSITION,
        entity_type="project_forecast_review",
        entity_id=review.pk,
        organization=review.organization,
        actor=actor,
        metadata={
            "forecast_id": str(review.forecast_id),
            "project_id": str(review.project_id),
            "version": review.forecast.version_number,
            "as_of": review.forecast.cutoff_date.isoformat(),
            "source_watermark": review.forecast.source_watermark,
            "previous_state": previous,
            "new_state": new_status,
            "reason": reason.strip(),
        },
    )


def _assert_source_current(review: ProjectForecastReview) -> None:
    control = ProjectBudgetControl.objects.select_for_update().get(
        organization=review.organization, project=review.project
    )
    if control.governing_budget_id != review.forecast.budget_id:
        raise ValidationError(
            "The governing Budget changed after the forecast snapshot."
        )
    if not review.forecast.assumptions.strip() or not review.forecast.source_watermark:
        raise ValidationError("Forecast source assumptions and watermark are required.")
    current = (
        ProjectForecastReview.objects.select_for_update()
        .filter(
            organization=review.organization,
            project=review.project,
            status=ForecastReviewStatus.APPROVED,
        )
        .first()
    )
    if (current.pk if current else None) != review.predecessor_id:
        raise ValidationError("The previously approved forecast changed.")


@transaction.atomic
def submit_project_cost_forecast(
    *,
    forecast: ProjectCostForecast,
    actor: User,
    workflow_version: WorkflowVersion,
    reason: str,
    idempotency_key: str,
) -> WorkflowInstance:
    """Pin the source and launch a published, tenant-owned review assignment."""
    project = Project.objects.select_for_update().get(pk=forecast.project_id)
    locked = ProjectCostForecast.objects.select_for_update().get(
        pk=forecast.pk, organization=forecast.organization, project=project
    )
    _require_budget_access(
        organization=locked.organization,
        actor=actor,
        project=project,
        permission=BusinessPermissionCode.PROJECT_FORECASTS_PREPARE,
    )
    review = _locked_review(forecast=locked)
    if review.status != ForecastReviewStatus.DRAFT:
        raise ValidationError("Only a draft forecast may be submitted.")
    if (
        workflow_version.organization_id != locked.organization_id
        or workflow_version.definition.workflow_type.code != WORKFLOW_TYPE_CODE
    ):
        raise PermissionDenied("The forecast workflow belongs to another authority.")
    _assert_source_current(review)
    _record_transition(
        review=review,
        actor=actor,
        new_status=ForecastReviewStatus.SUBMITTED,
        reason=reason,
    )
    instance = start_workflow(
        actor=actor,
        organization=locked.organization,
        version_id=workflow_version.pk,
        subject_id=locked.pk,
        idempotency_key=idempotency_key,
    )
    _record_transition(
        review=review,
        actor=actor,
        new_status=ForecastReviewStatus.UNDER_REVIEW,
        reason="Published workflow review started",
    )
    return instance


@transaction.atomic
def decide_project_cost_forecast(
    *, forecast: ProjectCostForecast, actor: User, approved: bool, reason: str
) -> ProjectForecastReview:
    """Domain command called only by the workflow runtime after work-item checks."""
    project = Project.objects.select_for_update().get(pk=forecast.project_id)
    locked = ProjectCostForecast.objects.select_for_update().get(
        pk=forecast.pk, organization=forecast.organization, project=project
    )
    _require_budget_access(
        organization=locked.organization,
        actor=actor,
        project=project,
        permission=BusinessPermissionCode.PROJECT_FORECASTS_REVIEW,
    )
    review = _locked_review(forecast=locked)
    if review.status != ForecastReviewStatus.UNDER_REVIEW:
        raise ValidationError("Only a forecast under review may be decided.")
    membership = get_active_membership(user=actor, organization=locked.organization)
    if (
        not WorkItem.objects.select_for_update()
        .filter(
            organization=locked.organization,
            instance__subject_type=SUBJECT_TYPE,
            instance__subject_id=locked.pk,
            instance__status="active",
            status=WorkItemStatus.CLAIMED,
            current_assignee=membership,
            candidates__membership=membership,
            candidates__is_active=True,
        )
        .exists()
    ):
        raise PermissionDenied("An active assigned forecast work item is required.")
    if actor.pk == locked.created_by_id:
        raise PermissionDenied("A forecast preparer cannot review their own version.")
    _assert_source_current(review)
    if approved and review.predecessor_id:
        predecessor = ProjectForecastReview.objects.select_for_update().get(
            pk=review.predecessor_id,
            organization=locked.organization,
            project=project,
            status=ForecastReviewStatus.APPROVED,
        )
        _record_transition(
            review=predecessor,
            actor=actor,
            new_status=ForecastReviewStatus.SUPERSEDED,
            reason=f"Superseded by forecast {locked.pk}",
        )
    _record_transition(
        review=review,
        actor=actor,
        new_status=(
            ForecastReviewStatus.APPROVED if approved else ForecastReviewStatus.REJECTED
        ),
        reason=reason,
    )
    return review


def requester_forecast_status(
    *, forecast: ProjectCostForecast, actor: User
) -> dict[str, object]:
    """Return public lifecycle facts without candidates, reviewers or routing data."""
    _require_budget_access(
        organization=forecast.organization,
        actor=actor,
        project=forecast.project,
        permission=BusinessPermissionCode.PROJECT_COSTS_VIEW,
    )
    review = ProjectForecastReview.objects.get(
        forecast=forecast, organization=forecast.organization
    )
    return {
        "forecast_id": str(forecast.pk),
        "version": forecast.version_number,
        "as_of": forecast.cutoff_date,
        "status": review.status,
    }


def load_forecast_subject(
    *, organization: Organization, subject_id: UUID, actor: User, for_update: bool
) -> SubjectSnapshot:
    project_id = (
        ProjectCostForecast.objects.filter(pk=subject_id, organization=organization)
        .values_list("project_id", flat=True)
        .first()
    )
    if project_id is None:
        raise PermissionDenied("Forecast not found in this organization.")
    project_query = Project.objects
    if for_update:
        project_query = project_query.select_for_update()
    project = project_query.get(pk=project_id, organization=organization)
    _require_budget_access(
        organization=organization,
        actor=actor,
        project=project,
        permission=BusinessPermissionCode.PROJECT_COSTS_VIEW,
    )
    forecast_query = ProjectCostForecast.objects.select_related("review")
    if for_update:
        forecast_query = forecast_query.select_for_update(of=("self",))
    forecast = forecast_query.get(pk=subject_id, organization=organization)
    creator_membership_id = (
        OrganizationMembership.objects.filter(
            organization=organization,
            user_id=forecast.created_by_id,
            status=MembershipStatus.ACTIVE,
        )
        .values_list("pk", flat=True)
        .first()
    )
    submitter_membership = get_active_membership(user=actor, organization=organization)
    return SubjectSnapshot(
        subject=forecast,
        subject_id=str(forecast.pk),
        organization_id=str(organization.pk),
        attributes={
            "project_id": str(project.pk),
            "status": forecast.review.status,
            "created_by_id": str(forecast.created_by_id),
        },
        creator_membership_id=(
            str(creator_membership_id) if creator_membership_id else None
        ),
        submitter_membership_id=str(submitter_membership.pk),
        display=f"Forecast version {forecast.version_number}",
    )


def _approve_command(
    *,
    subject: ProjectCostForecast,
    actor: User,
    context: dict[str, object],
    **_: object,
) -> ProjectForecastReview:
    return decide_project_cost_forecast(
        forecast=subject,
        actor=actor,
        approved=True,
        reason=str(context.get("reason", "")),
    )


def _reject_command(
    *,
    subject: ProjectCostForecast,
    actor: User,
    context: dict[str, object],
    **_: object,
) -> ProjectForecastReview:
    return decide_project_cost_forecast(
        forecast=subject,
        actor=actor,
        approved=False,
        reason=str(context.get("reason", "")),
    )


def register_forecast_workflow() -> None:
    registry.bind_subject_loader(SUBJECT_TYPE, load_forecast_subject)
    registry.bind_domain_command("projects.forecast.approve", _approve_command)
    registry.bind_domain_command("projects.forecast.reject", _reject_command)


def forecast_submission_key(forecast: ProjectCostForecast) -> str:
    return sha256(
        f"forecast:{forecast.pk}:v{forecast.version_number}".encode()
    ).hexdigest()
