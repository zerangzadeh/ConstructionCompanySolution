from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.organizations.authorization import has_business_permission
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode

from .forms import ClaimSettlementAllocationForm
from .models import ProgressClaim, ProgressRecord, ProjectBaseline
from .services import (
    allocate_progress_claim_settlement,
    get_progress_claim_settlement_summary,
    get_progress_claims,
    get_progress_records,
    get_project_baselines,
    reject_progress_record,
    request_progress_verification,
    verify_progress_record,
)


def _record(request: HttpRequest, record_id: str):
    try:
        return get_progress_records(
            actor=request.user, organization=request.organization
        ).get(pk=record_id)
    except (PermissionDenied, ProgressRecord.DoesNotExist, ValidationError):
        return None


def _baseline(request: HttpRequest, baseline_id: str):
    try:
        return get_project_baselines(
            actor=request.user, organization=request.organization
        ).get(pk=baseline_id)
    except (PermissionDenied, ProjectBaseline.DoesNotExist, ValidationError):
        return None


def _claim(request: HttpRequest, claim_id: str):
    try:
        return get_progress_claims(
            actor=request.user, organization=request.organization
        ).get(pk=claim_id)
    except (PermissionDenied, ProgressClaim.DoesNotExist, ValidationError):
        return None


@active_organization_required
@organization_permission_required(BusinessPermissionCode.BASELINES_VIEW)
@require_GET
def baseline_list(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "billing/baseline_list.html",
        {
            "baselines": get_project_baselines(
                actor=request.user, organization=request.organization
            )
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.BASELINES_VIEW)
@require_GET
def baseline_detail(request: HttpRequest, baseline_id: str) -> HttpResponse:
    baseline = _baseline(request, baseline_id)
    if baseline is None:
        return HttpResponseNotFound("مبنای تجاری یافت نشد.")
    return render(
        request,
        "billing/baseline_detail.html",
        {
            "baseline": baseline,
            "baseline_items": baseline.items.select_related("activity", "wbs_node"),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROGRESS_VIEW)
@require_GET
def progress_list(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "billing/progress_list.html",
        {
            "progress_records": get_progress_records(
                actor=request.user, organization=request.organization
            )
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROGRESS_VIEW)
@require_GET
def progress_detail(request: HttpRequest, record_id: str) -> HttpResponse:
    record = _record(request, record_id)
    if record is None:
        return HttpResponseNotFound("رکورد پیشرفت یافت نشد.")
    return render(request, "billing/progress_detail.html", {"progress_record": record})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROGRESS_RECORD)
@require_POST
def progress_submit(request: HttpRequest, record_id: str) -> HttpResponse:
    record = _record(request, record_id)
    if record is None:
        return HttpResponseNotFound("رکورد پیشرفت یافت نشد.")
    try:
        request_progress_verification(
            organization=request.organization, actor=request.user, record=record
        )
        messages.success(request, "رکورد برای راستی‌آزمایی ارسال شد.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("billing:progress_detail", record_id=record.pk)


def _progress_decision(
    request: HttpRequest, record_id: str, *, verified: bool
) -> HttpResponse:
    record = _record(request, record_id)
    if record is None:
        return HttpResponseNotFound("رکورد پیشرفت یافت نشد.")
    reason = request.POST.get("reason", "")
    try:
        service = verify_progress_record if verified else reject_progress_record
        service(
            organization=request.organization,
            actor=request.user,
            record=record,
            reason=reason,
        )
        messages.success(
            request, "پیشرفت راستی‌آزمایی شد." if verified else "پیشرفت رد شد."
        )
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("billing:progress_detail", record_id=record.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROGRESS_VERIFY)
@require_POST
def progress_verify(request: HttpRequest, record_id: str) -> HttpResponse:
    return _progress_decision(request, record_id, verified=True)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROGRESS_VERIFY)
@require_POST
def progress_reject(request: HttpRequest, record_id: str) -> HttpResponse:
    return _progress_decision(request, record_id, verified=False)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CLAIMS_VIEW)
@require_GET
def claim_list(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "billing/claim_list.html",
        {
            "claims": get_progress_claims(
                actor=request.user, organization=request.organization
            )
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CLAIMS_VIEW)
@require_GET
def claim_detail(request: HttpRequest, claim_id: str) -> HttpResponse:
    claim = _claim(request, claim_id)
    if claim is None:
        return HttpResponseNotFound("صورت‌وضعیت یافت نشد.")
    can_view_settlements = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.CLAIM_SETTLEMENTS_VIEW,
    )
    can_allocate_settlements = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.CLAIM_SETTLEMENTS_ALLOCATE,
    )
    return render(
        request,
        "billing/claim_detail.html",
        {
            "claim": claim,
            "claim_items": claim.items.select_related("baseline_item"),
            "adjustments": claim.adjustments.all(),
            "settlements": claim.settlement_allocations.select_related(
                "payment_allocation__payment", "created_by", "reversed_by"
            ),
            "settlement_summary": (
                get_progress_claim_settlement_summary(
                    organization=request.organization,
                    actor=request.user,
                    claim=claim,
                )
                if can_view_settlements
                else None
            ),
            "settlement_form": (
                ClaimSettlementAllocationForm(
                    organization=request.organization, claim=claim
                )
                if can_allocate_settlements and claim.status == "approved"
                else None
            ),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CLAIM_SETTLEMENTS_ALLOCATE)
@require_POST
def claim_settlement_allocate(request: HttpRequest, claim_id: str) -> HttpResponse:
    claim = _claim(request, claim_id)
    if claim is None:
        return HttpResponseNotFound("صورت‌وضعیت یافت نشد.")
    form = ClaimSettlementAllocationForm(
        request.POST,
        organization=request.organization,
        claim=claim,
    )
    if form.is_valid():
        try:
            allocate_progress_claim_settlement(
                organization=request.organization,
                actor=request.user,
                claim=claim,
                payment_allocation=form.cleaned_data["payment_allocation"],
                amount=form.cleaned_data["amount"],
                reason=form.cleaned_data["reason"],
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "تسویه صورت‌وضعیت ثبت شد.")
    else:
        messages.error(request, "اطلاعات تسویه معتبر نیست.")
    return redirect("billing:claim_detail", claim_id=claim.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CLAIMS_VIEW)
@require_GET
def recovery_guidance(request: HttpRequest) -> HttpResponse:
    return render(request, "billing/recovery_guidance.html")
