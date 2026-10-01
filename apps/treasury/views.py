from __future__ import annotations

from datetime import date
from uuid import uuid4

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
    scope_queryset,
)
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode
from apps.treasury.models import (
    BankReconciliationRun,
    BankStatementImport,
    BankStatementLine,
    StatementMatchProposal,
    TreasuryGLReconciliationRun,
    TreasuryMovement,
    TreasuryMovementClearing,
)
from apps.treasury.services import review_treasury_gl_reconciliation
from apps.treasury.statement_services import (
    confirm_statement_match,
    generate_statement_match_suggestions,
    reject_statement_match,
    reverse_statement_clearing,
    run_bank_reconciliation,
)


def _reason(request: HttpRequest) -> str:
    return request.POST.get("reason", "").strip()


def _date(request: HttpRequest) -> date:
    try:
        return date.fromisoformat(request.POST["as_of_date"])
    except (KeyError, ValueError) as exc:
        raise ValidationError("تاریخ معتبر الزامی است.") from exc


def _tenant_object(model, request: HttpRequest, pk):
    return get_object_or_404(model, pk=pk, organization=request.organization)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TREASURY_VIEW)
@require_GET
def workbench(request: HttpRequest) -> HttpResponse:
    organization = request.organization
    membership = get_active_membership(user=request.user, organization=organization)
    movements = scope_queryset(
        TreasuryMovement.objects.filter(organization=organization),
        membership=membership,
        project_lookup="project_id",
        site_lookup="site_id",
    )
    return render(
        request,
        "treasury/workbench.html",
        {
            "accounts": organization.treasury_accounts.all(),
            "recent_movements": movements.select_related("project", "party")[:30],
            "bank_runs": BankReconciliationRun.objects.filter(
                organization=organization
            ).select_related("account")[:12],
            "gl_runs": TreasuryGLReconciliationRun.objects.filter(
                organization=organization
            ).select_related("run_by__user", "review__reviewed_by__user")[:20],
            "can_review_reconciliation": has_business_permission(
                user=request.user,
                organization=organization,
                permission=BusinessPermissionCode.TREASURY_RECONCILIATIONS_REVIEW,
            ),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TREASURY_VIEW)
@require_GET
def statement_workbench(request: HttpRequest) -> HttpResponse:
    organization = request.organization
    membership = get_active_membership(user=request.user, organization=organization)
    visible_movements = scope_queryset(
        TreasuryMovement.objects.filter(organization=organization),
        membership=membership,
        project_lookup="project_id",
        site_lookup="site_id",
    )
    return render(
        request,
        "treasury/statement_workbench.html",
        {
            "imports": BankStatementImport.objects.filter(organization=organization)
            .select_related("account")
            .prefetch_related("lines")[:25],
            "proposals": StatementMatchProposal.objects.filter(
                organization=organization, movement__in=visible_movements
            ).select_related("statement_line", "movement", "movement_leg")[:50],
            "clearings": TreasuryMovementClearing.objects.filter(
                organization=organization, active=True, movement__in=visible_movements
            ).select_related("statement_line", "movement")[:50],
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TREASURY_STATEMENT_MATCHES_MANAGE)
@require_POST
def suggest_match(request: HttpRequest, line_id) -> HttpResponse:
    line = _tenant_object(BankStatementLine, request, line_id)
    try:
        generate_statement_match_suggestions(
            organization=request.organization,
            actor=request.user,
            statement_line=line,
            idempotency_key=request.POST.get("idempotency_key") or str(uuid4()),
        )
        messages.success(request, "پیشنهادهای تطبیق دقیق ایجاد شد.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("treasury:statement_workbench")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TREASURY_STATEMENT_MATCHES_CLEAR)
@require_POST
def confirm_match(request: HttpRequest, proposal_id) -> HttpResponse:
    proposal = _tenant_object(StatementMatchProposal, request, proposal_id)
    try:
        confirm_statement_match(
            organization=request.organization,
            actor=request.user,
            proposal=proposal,
            reason=_reason(request),
        )
        messages.success(request, "تطبیق بانکی با شواهد دقیق تأیید شد.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("treasury:statement_workbench")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TREASURY_STATEMENT_MATCHES_MANAGE)
@require_POST
def reject_match(request: HttpRequest, proposal_id) -> HttpResponse:
    proposal = _tenant_object(StatementMatchProposal, request, proposal_id)
    try:
        reject_statement_match(
            organization=request.organization,
            actor=request.user,
            proposal=proposal,
            reason=_reason(request),
        )
        messages.success(request, "پیشنهاد تطبیق رد شد؛ سابقه حفظ شد.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("treasury:statement_workbench")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TREASURY_STATEMENT_MATCHES_MANAGE)
@require_POST
def reverse_clearing(request: HttpRequest, clearing_id) -> HttpResponse:
    clearing = _tenant_object(TreasuryMovementClearing, request, clearing_id)
    try:
        reverse_statement_clearing(
            organization=request.organization,
            actor=request.user,
            clearing=clearing,
            reason=_reason(request),
        )
        messages.success(request, "برگشت تطبیق ثبت شد؛ شواهد اصلی حفظ شد.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("treasury:statement_workbench")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TREASURY_BANK_RECONCILIATIONS_RUN)
@require_POST
def bank_reconcile(request: HttpRequest, import_id) -> HttpResponse:
    statement_import = _tenant_object(BankStatementImport, request, import_id)
    try:
        run_bank_reconciliation(
            organization=request.organization,
            actor=request.user,
            statement_import=statement_import,
            as_of_date=_date(request),
            idempotency_key=request.POST.get("idempotency_key") or str(uuid4()),
        )
        messages.success(request, "اجرای تطبیق بانکی تغییرناپذیر نگهداری شد.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("treasury:statement_workbench")


@active_organization_required
@organization_permission_required(
    BusinessPermissionCode.TREASURY_RECONCILIATIONS_REVIEW
)
@require_POST
def review_gl_reconciliation(request: HttpRequest, run_id) -> HttpResponse:
    run = _tenant_object(TreasuryGLReconciliationRun, request, run_id)
    try:
        review_treasury_gl_reconciliation(
            organization=request.organization,
            actor=request.user,
            run=run,
            reason=_reason(request),
        )
        messages.success(request, "بررسی مستقل تطبیق خزانه‌داری ثبت شد.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("treasury:workbench")
