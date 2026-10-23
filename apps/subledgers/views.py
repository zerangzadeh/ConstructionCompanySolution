from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.organizations.authorization import has_business_permission
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode
from apps.subledgers.models import (
    AgingRun,
    Obligation,
    ObligationDirection,
    SettlementAllocation,
    SubledgerReconciliationRun,
    SupplierInvoiceMatch,
    WriteOffProposal,
)
from apps.subledgers.services import (
    allocate_settlement,
    obligation_queryset,
    propose_write_off,
    reverse_settlement,
    review_subledger_reconciliation,
    run_aging,
    run_subledger_reconciliation,
    settlement_movement_choices,
    supplier_invoice_match_queryset,
)
from apps.treasury.models import (
    TreasuryMovement,
    TreasuryMovementKind,
    TreasuryMovementStatus,
)


def _date(request: HttpRequest) -> date:
    try:
        return date.fromisoformat(request.POST["effective_date"])
    except (KeyError, ValueError) as exc:
        raise ValidationError("تاریخ معتبر الزامی است.") from exc


def _as_of_date(request: HttpRequest) -> date:
    try:
        return date.fromisoformat(request.POST["as_of_date"])
    except (KeyError, ValueError) as exc:
        raise ValidationError("تاریخ مبنای معتبر الزامی است.") from exc


def _amount(request: HttpRequest) -> Decimal:
    try:
        value = Decimal(request.POST["amount"])
    except (KeyError, InvalidOperation) as exc:
        raise ValidationError("مبلغ معتبر الزامی است.") from exc
    if not value.is_finite():
        raise ValidationError("مبلغ معتبر الزامی است.")
    return value


def _scoped_obligation(request: HttpRequest, obligation_id) -> Obligation:
    return get_object_or_404(
        obligation_queryset(organization=request.organization, actor=request.user),
        pk=obligation_id,
    )


def _direction(request: HttpRequest) -> str:
    direction = request.POST.get("direction", "")
    if direction not in ObligationDirection.values:
        raise ValidationError("نوع قلم دریافتنی یا پرداختنی معتبر نیست.")
    return direction


@active_organization_required
@organization_permission_required(BusinessPermissionCode.SUBLEDGERS_VIEW)
@require_GET
def workbench(request: HttpRequest) -> HttpResponse:
    obligations = obligation_queryset(organization=request.organization, actor=request.user)
    obligation_ids = obligations.values("pk")
    visible_obligations = list(obligations.select_related("project", "contract")[:75])
    for obligation in visible_obligations:
        obligation.allocation_key = str(uuid4())
        try:
            obligation.settlement_choices = settlement_movement_choices(
                organization=request.organization, actor=request.user, obligation=obligation,
            )
        except (PermissionDenied, ValidationError):
            obligation.settlement_choices = ()
    return render(
        request,
        "subledgers/workbench.html",
        {
            "obligations": visible_obligations,
            "allocations": SettlementAllocation.objects.filter(
                organization=request.organization, obligation_id__in=obligation_ids
            ).select_related("obligation", "treasury_movement")[:50],
            "writeoffs": WriteOffProposal.objects.filter(
                organization=request.organization, obligation_id__in=obligation_ids
            ).select_related("obligation")[:30],
            "aging_runs": AgingRun.objects.filter(organization=request.organization)[:12],
            "reconciliation_runs": SubledgerReconciliationRun.objects.filter(
                organization=request.organization
            ).select_related("created_by__user", "review__reviewed_by__user")[:20],
            "can_review_reconciliation": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.SUBLEDGERS_RECONCILIATIONS_REVIEW,
            ),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.INVOICE_MATCHES_VIEW)
@require_GET
def supplier_invoice_match_review(
    request: HttpRequest, match_id=None
) -> HttpResponse:
    """Read immutable match evidence; this endpoint has no override or mutation path."""

    matches = supplier_invoice_match_queryset(
        organization=request.organization,
        actor=request.user,
    ).select_related(
        "invoice_version__invoice__supplier",
        "invoice_version__invoice__project",
        "tolerance_policy",
        "matched_by",
        "supersedes",
    )
    selected: SupplierInvoiceMatch | None = None
    if match_id is not None:
        selected = get_object_or_404(
            matches.prefetch_related(
                "lines__invoice_line",
                "lines__discrepancies",
            ),
            pk=match_id,
        )
    return render(
        request,
        "subledgers/supplier_invoice_match_review.html",
        {
            "matches": matches.order_by("-matched_at")[:75],
            "selected_match": selected,
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.SUBLEDGERS_SETTLEMENTS_ALLOCATE)
@require_POST
def allocate(request: HttpRequest, obligation_id) -> HttpResponse:
    obligation = _scoped_obligation(request, obligation_id)
    try:
        movement_id = UUID(str(request.POST.get("treasury_movement_id", "")))
    except ValueError as exc:
        raise Http404("تراکنش قطعی معتبر انتخاب نشده است.") from exc
    movement = get_object_or_404(
        TreasuryMovement.objects.filter(
            organization=request.organization,
            status=TreasuryMovementStatus.POSTED,
            kind=(TreasuryMovementKind.RECEIPT if obligation.direction == ObligationDirection.RECEIVABLE else TreasuryMovementKind.DISBURSEMENT),
        ),
        pk=movement_id,
    )
    try:
        allocate_settlement(
            organization=request.organization, actor=request.user, obligation=obligation,
            movement=movement, amount=_amount(request), effective_date=_date(request),
            reason=request.POST.get("reason", ""),
            idempotency_key=request.POST.get("idempotency_key") or str(uuid4()),
        )
        messages.success(request, "تخصیص به حرکت قطعی خزانه ثبت شد؛ هیچ حساب نقدی انتخاب نشد.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("subledgers:workbench")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.SUBLEDGERS_SETTLEMENTS_REVERSE)
@require_POST
def reverse_allocation(request: HttpRequest, allocation_id) -> HttpResponse:
    allocation = get_object_or_404(
        SettlementAllocation.objects.filter(
            organization=request.organization,
            obligation__in=obligation_queryset(organization=request.organization, actor=request.user),
        ), pk=allocation_id
    )
    try:
        reverse_settlement(
            organization=request.organization, actor=request.user, allocation=allocation,
            effective_date=_date(request), reason=request.POST.get("reason", ""),
            idempotency_key=request.POST.get("idempotency_key") or str(uuid4()),
        )
        messages.success(request, "برگشت تخصیص ثبت شد؛ سابقه تغییرناپذیر حفظ شد.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("subledgers:workbench")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.SUBLEDGERS_WRITEOFFS_PROPOSE)
@require_POST
def propose_writeoff(request: HttpRequest, obligation_id) -> HttpResponse:
    obligation = _scoped_obligation(request, obligation_id)
    try:
        propose_write_off(
            organization=request.organization, actor=request.user, obligation=obligation,
            amount=_amount(request), effective_date=_date(request), reason=request.POST.get("reason", ""),
            idempotency_key=request.POST.get("idempotency_key") or str(uuid4()),
        )
        messages.success(request, "پیشنهاد حذف حسابداری مانده ثبت شد؛ تأیید و برگشت هنوز فعال نیست.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("subledgers:workbench")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.SUBLEDGERS_AGING_RUN)
@require_POST
def aging(request: HttpRequest) -> HttpResponse:
    try:
        run_aging(
            organization=request.organization, actor=request.user, direction=_direction(request),
            as_of_date=_as_of_date(request), idempotency_key=request.POST.get("idempotency_key") or str(uuid4()),
        )
        messages.success(request, "گزارش سنی دقیق و بدون بازه‌بندی ثبت شد.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("subledgers:workbench")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.SUBLEDGERS_RECONCILIATIONS_RUN)
@require_POST
def reconcile(request: HttpRequest) -> HttpResponse:
    try:
        run_subledger_reconciliation(
            organization=request.organization, actor=request.user, direction=_direction(request),
            as_of_date=_as_of_date(request), idempotency_key=request.POST.get("idempotency_key") or str(uuid4()),
        )
        messages.success(request, "تطبیق حساب‌های دریافتنی و پرداختنی اجرا و موارد نیازمند بررسی ثبت شد.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("subledgers:workbench")


@active_organization_required
@organization_permission_required(
    BusinessPermissionCode.SUBLEDGERS_RECONCILIATIONS_REVIEW
)
@require_POST
def review_reconciliation(request: HttpRequest, run_id) -> HttpResponse:
    run = get_object_or_404(
        SubledgerReconciliationRun,
        pk=run_id,
        organization=request.organization,
    )
    try:
        review_subledger_reconciliation(
            organization=request.organization,
            actor=request.user,
            run=run,
            reason=request.POST.get("reason", ""),
        )
        messages.success(request, "بررسی مستقل تطبیق دریافتنی‌ها و پرداختنی‌ها ثبت شد.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("subledgers:workbench")
