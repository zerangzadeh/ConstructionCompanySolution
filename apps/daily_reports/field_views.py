from __future__ import annotations

import uuid

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.daily_reports.field_forms import (
    LOCATION_FIELDS,
    FieldObservationEvidenceForm,
    FieldObservationForm,
    FieldProposalForm,
    FieldReviewForm,
    field_time_zone,
)
from apps.daily_reports.field_models import FieldDownstreamProposal
from apps.daily_reports.field_services import (
    attach_field_evidence,
    create_field_observation,
    create_field_proposal,
    get_field_observation,
    list_field_observations,
    review_field_observation,
    review_field_proposal,
    start_field_observation_review,
    submit_field_observation,
    submit_field_proposal,
    update_field_observation,
)
from apps.organizations.authorization import has_business_permission
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode


def _operation_key(value: object) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError("کلید تکرار معتبر نیست.") from exc


def _review_action(value: str) -> bool:
    if value == "accept":
        return True
    if value == "reject":
        return False
    raise ValidationError("تصمیم بررسی معتبر نیست.")


@never_cache
@active_organization_required
@organization_permission_required(BusinessPermissionCode.FIELD_OBSERVATIONS_VIEW)
@require_GET
def field_observation_list(request: HttpRequest) -> HttpResponse:
    observations = list_field_observations(
        organization=request.organization, actor=request.user
    )
    can_capture = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.FIELD_OBSERVATIONS_CAPTURE,
        allow_any_scope=True,
    )
    with timezone.override(field_time_zone(request.organization)):
        return render(
            request,
            "daily_reports/field_observation_list.html",
            {"observations": observations, "can_capture": can_capture},
        )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.FIELD_OBSERVATIONS_CAPTURE)
def field_observation_create(request: HttpRequest) -> HttpResponse:
    form = FieldObservationForm(
        request.POST or None,
        organization=request.organization,
        user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            observation = create_field_observation(
                organization=request.organization,
                actor=request.user,
                project=data["project"],
                site=data["site"],
                phase=data["phase"],
                activity=data["activity"],
                kind=data["kind"],
                title=data["title"],
                summary=data["summary"],
                structured_payload=data["structured_payload_text"],
                manual_context=data["manual_context"],
                captured_at=data["captured_at"],
                effective_at=data["effective_at"],
                location_permission=data["location_permission"],
                latitude=data["latitude"],
                longitude=data["longitude"],
                horizontal_accuracy_meters=data["horizontal_accuracy_meters"],
                location_captured_at=data["location_captured_at"],
                location_mismatch_note=data["location_mismatch_note"],
                operation_key=data["operation_key"],
            )
        except ValidationError as exc:
            form.add_error(None, ValidationError(exc.messages))
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "مشاهده میدانی در پیش‌نویس ذخیره شد.")
            return redirect(
                "daily_reports:field_observation_detail", observation_id=observation.pk
            )
    return render(
        request,
        "daily_reports/field_observation_form.html",
        {"form": form, "title": "مشاهده میدانی جدید"},
    )


@never_cache
@active_organization_required
@organization_permission_required(BusinessPermissionCode.FIELD_OBSERVATIONS_VIEW)
@require_GET
def field_observation_detail(request: HttpRequest, observation_id: str) -> HttpResponse:
    observation = get_field_observation(
        organization=request.organization,
        actor=request.user,
        observation_id=observation_id,
    )
    can_view_location = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.FIELD_OBSERVATIONS_LOCATION_VIEW,
        project=observation.project,
        site=observation.site,
    )
    can_review_proposals = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.FIELD_PROPOSALS_REVIEW,
        project=observation.project,
        site=observation.site,
    )
    proposal_rows = []
    for proposal in observation.proposals.all():
        review_form = FieldReviewForm(auto_id=f"proposal-{proposal.pk}-%s")
        review_form.fields["reason"].required = True
        proposal_rows.append(
            {
                "proposal": proposal,
                "review_form": review_form,
                "can_review": (
                    can_review_proposals
                    and proposal.status == "submitted"
                    and request.user.pk not in (
                        proposal.created_by_id, proposal.submitted_by_id
                    )
                ),
            }
        )
    context = {
        "observation": observation,
        "proposal_rows": proposal_rows,
        "can_view_location": can_view_location,
        "evidence_form": FieldObservationEvidenceForm(),
        "review_form": FieldReviewForm(),
        "proposal_form": FieldProposalForm(organization=request.organization),
        "observation_form": FieldObservationForm(
            instance=observation,
            organization=request.organization,
            user=request.user,
            include_location=can_view_location,
        ),
        "can_capture": has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=BusinessPermissionCode.FIELD_OBSERVATIONS_CAPTURE,
            project=observation.project,
            site=observation.site,
        ),
        "can_submit": has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=BusinessPermissionCode.FIELD_OBSERVATIONS_SUBMIT,
            project=observation.project,
            site=observation.site,
        ),
        "can_review": has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=BusinessPermissionCode.FIELD_OBSERVATIONS_REVIEW,
            project=observation.project,
            site=observation.site,
        ),
        "can_prepare_proposal": has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=BusinessPermissionCode.FIELD_PROPOSALS_PREPARE,
            project=observation.project,
            site=observation.site,
        ),
    }
    with timezone.override(field_time_zone(request.organization)):
        return render(request, "daily_reports/field_observation_detail.html", context)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.FIELD_OBSERVATIONS_CAPTURE)
@require_POST
def field_observation_save(request: HttpRequest, observation_id: str) -> HttpResponse:
    observation = get_field_observation(
        organization=request.organization,
        actor=request.user,
        observation_id=observation_id,
    )
    can_view_location = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.FIELD_OBSERVATIONS_LOCATION_VIEW,
        project=observation.project,
        site=observation.site,
    )
    form = FieldObservationForm(
        request.POST,
        organization=request.organization,
        user=request.user,
        instance=observation,
        include_location=can_view_location,
    )
    if form.is_valid():
        data = form.cleaned_data
        try:
            update_field_observation(
                organization=request.organization,
                actor=request.user,
                observation_id=observation_id,
                expected_revision=data["expected_revision"],
                operation_key=data["operation_key"],
                project=data["project"],
                site=data["site"],
                phase=data["phase"],
                activity=data["activity"],
                kind=data["kind"],
                title=data["title"],
                summary=data["summary"],
                structured_payload=data["structured_payload_text"],
                manual_context=data["manual_context"],
                captured_at=data["captured_at"],
                effective_at=data["effective_at"],
                client_context={},
                **{name: data[name] for name in LOCATION_FIELDS if name in data},
            )
        except ValidationError as exc:
            form.add_error(None, ValidationError(exc.messages))
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "پیش‌نویس مشاهده ذخیره شد.")
            return redirect(
                "daily_reports:field_observation_detail", observation_id=observation_id
            )
    return render(
        request,
        "daily_reports/field_observation_form.html",
        {
            "form": form,
            "title": "ویرایش مشاهده میدانی",
            "cancel_url": reverse(
                "daily_reports:field_observation_detail", args=[observation_id]
            ),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.FIELD_OBSERVATIONS_CAPTURE)
@require_POST
def field_observation_evidence_add(
    request: HttpRequest, observation_id: str
) -> HttpResponse:
    form = FieldObservationEvidenceForm(request.POST)
    if form.is_valid():
        try:
            attach_field_evidence(
                organization=request.organization,
                actor=request.user,
                observation_id=observation_id,
                document_version_id=form.cleaned_data["document_version_id"],
                operation_key=form.cleaned_data["operation_key"],
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "نسخه DMS به‌عنوان شاهد مشاهده پیوند خورد.")
    else:
        messages.error(request, "شناسه نسخه DMS را بررسی کنید.")
    return redirect(
        "daily_reports:field_observation_detail", observation_id=observation_id
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.FIELD_OBSERVATIONS_SUBMIT)
@require_POST
def field_observation_submit(request: HttpRequest, observation_id: str) -> HttpResponse:
    try:
        submit_field_observation(
            organization=request.organization,
            actor=request.user,
            observation_id=observation_id,
            operation_key=_operation_key(request.POST.get("operation_key")),
        )
    except (PermissionDenied, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "مشاهده برای بررسی ارسال شد.")
    return redirect(
        "daily_reports:field_observation_detail", observation_id=observation_id
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.FIELD_OBSERVATIONS_REVIEW)
@require_POST
def field_observation_review_start(
    request: HttpRequest, observation_id: str
) -> HttpResponse:
    try:
        start_field_observation_review(
            organization=request.organization,
            actor=request.user,
            observation_id=observation_id,
            operation_key=_operation_key(request.POST.get("operation_key")),
        )
    except (PermissionDenied, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "بررسی مشاهده آغاز شد.")
    return redirect(
        "daily_reports:field_observation_detail", observation_id=observation_id
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.FIELD_OBSERVATIONS_REVIEW)
@require_POST
def field_observation_review_decide(
    request: HttpRequest, observation_id: str, accepted: str
) -> HttpResponse:
    form = FieldReviewForm(request.POST)
    if form.is_valid():
        try:
            review_field_observation(
                organization=request.organization,
                actor=request.user,
                observation_id=observation_id,
                accepted=_review_action(accepted),
                reason=form.cleaned_data["reason"],
                operation_key=form.cleaned_data["operation_key"],
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "تصمیم بررسی مشاهده ثبت شد.")
    else:
        messages.error(request, "دلیل بررسی را بررسی کنید.")
    return redirect(
        "daily_reports:field_observation_detail", observation_id=observation_id
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.FIELD_PROPOSALS_PREPARE)
@require_POST
def field_proposal_create(request: HttpRequest, observation_id: str) -> HttpResponse:
    form = FieldProposalForm(request.POST, organization=request.organization)
    if form.is_valid():
        data = form.cleaned_data
        try:
            create_field_proposal(
                organization=request.organization,
                actor=request.user,
                observation_id=observation_id,
                family=data["family"],
                lines=data["lines_text"],
                effective_at=data["effective_at"],
                operation_key=data["operation_key"],
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                "پیشنهاد تحویل ایجاد شد؛ هنوز هیچ واقعیت دامنه‌ای ایجاد نشده است.",
            )
            return redirect(
                "daily_reports:field_observation_detail", observation_id=observation_id
            )
    else:
        messages.error(request, "داده پیشنهاد را بررسی کنید.")
    return redirect(
        "daily_reports:field_observation_detail", observation_id=observation_id
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.FIELD_PROPOSALS_PREPARE)
@require_POST
def field_proposal_submit(
    request: HttpRequest, proposal_id: str, observation_id: str
) -> HttpResponse:
    try:
        submit_field_proposal(
            organization=request.organization,
            actor=request.user,
            proposal_id=proposal_id,
            operation_key=_operation_key(request.POST.get("operation_key")),
        )
    except (PermissionDenied, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "پیشنهاد برای بررسی مستقل ارسال شد.")
    return redirect(
        "daily_reports:field_observation_detail", observation_id=observation_id
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.FIELD_PROPOSALS_REVIEW)
@require_POST
def field_proposal_review(
    request: HttpRequest, proposal_id: str, observation_id: str, accepted: str
) -> HttpResponse:
    get_object_or_404(
        FieldDownstreamProposal,
        organization=request.organization,
        pk=proposal_id,
        observation_id=observation_id,
    )
    form = FieldReviewForm(request.POST)
    if form.is_valid():
        try:
            review_field_proposal(
                organization=request.organization,
                actor=request.user,
                proposal_id=proposal_id,
                accepted=_review_action(accepted),
                reason=form.cleaned_data["reason"],
                operation_key=form.cleaned_data["operation_key"],
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request, "تصمیم پیشنهاد ثبت شد؛ مصرف‌کننده دامنه‌ای تغییری نکرد."
            )
    else:
        messages.error(request, "دلیل بررسی را بررسی کنید.")
    return redirect(
        "daily_reports:field_observation_detail", observation_id=observation_id
    )
