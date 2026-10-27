from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode

from .closing_forms import YearEndConfigurationForm, YearEndPairForm, YearEndReopenForm
from .closing_models import FiscalYearClosing
from .closing_services import (
    approve_year_end,
    cancel_year_end,
    configure_year_end,
    inspect_year_end,
    prepare_year_end,
    reopen_year_end,
    roll_forward_year_end,
)
from .forms import ReasonForm


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_YEAR_END_VIEW)
@require_http_methods(["GET", "POST"])
def year_end_list(request):
    form = YearEndPairForm(request.POST or None, organization=request.organization)
    readiness = None
    if request.method == "POST" and form.is_valid():
        try:
            args = {
                "organization": request.organization,
                "actor": request.user,
                **form.cleaned_data,
            }
            if request.POST.get("action") == "prepare":
                closing = prepare_year_end(**args)
                return redirect("accounting:year_end_detail", closing_id=closing.pk)
            args.pop("reason")
            readiness = inspect_year_end(**args)
        except PermissionDenied:
            raise
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(
        request,
        "accounting/year_end_list.html",
        {
            "form": form,
            "readiness": readiness,
            "closings": FiscalYearClosing.objects.filter(
                organization=request.organization
            ).select_related("source_year", "target_year"),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_YEAR_END_CONFIGURE)
@require_http_methods(["GET", "POST"])
def year_end_configuration(request):
    form = YearEndConfigurationForm(
        request.POST or None, organization=request.organization
    )
    if request.method == "POST" and form.is_valid():
        try:
            configure_year_end(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "حساب‌های بستن سال ثبت شدند.")
            return redirect("accounting:year_end_list")
    return render(
        request,
        "accounting/form.html",
        {"form": form, "title": "حساب‌های بستن سال مالی"},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_YEAR_END_VIEW)
@require_GET
def year_end_detail(request, closing_id):
    closing = get_object_or_404(
        FiscalYearClosing.objects.select_related(
            "source_year",
            "target_year",
            "closing_journal",
            "opening_journal",
            "initiated_by__user",
            "close_approved_by__user",
            "opening_approved_by__user",
            "configuration__result_account",
            "configuration__retained_account",
        ),
        organization=request.organization,
        pk=closing_id,
    )
    return render(
        request,
        "accounting/year_end_detail.html",
        {
            "closing": closing,
            "reason_form": ReasonForm(auto_id="year_end_approval_%s"),
            "cancel_form": ReasonForm(auto_id="year_end_withdrawal_%s"),
            "reopen_form": YearEndReopenForm(
                organization=request.organization, auto_id="year_end_reopen_%s"
            ),
            "events": closing.events.select_related("actor__user"),
            "discrepancy_count": len(closing.reconciliation.get("discrepancies", [])),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_YEAR_END_APPROVE)
@require_POST
def year_end_approve(request, closing_id):
    return _act(request, closing_id, approve_year_end)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_YEAR_END_APPROVE)
@require_POST
def year_end_roll_forward(request, closing_id):
    return _act(request, closing_id, roll_forward_year_end)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_YEAR_END_REOPEN)
@require_POST
def year_end_reopen(request, closing_id):
    return _act(request, closing_id, reopen_year_end, reopen=True)


def _act(request, closing_id, service, *, reopen=False):
    closing = get_object_or_404(
        FiscalYearClosing, organization=request.organization, pk=closing_id
    )
    form = (
        YearEndReopenForm(request.POST, organization=request.organization)
        if reopen
        else ReasonForm(request.POST)
    )
    if form.is_valid():
        try:
            service(
                organization=request.organization,
                actor=request.user,
                closing=closing,
                **form.cleaned_data,
            )
        except ValidationError as exc:
            messages.error(request, "؛ ".join(exc.messages))
        else:
            messages.success(request, "مرحله با موفقیت انجام و شواهد بررسی ثبت شد.")
    else:
        messages.error(request, "دلیل و اطلاعات درخواست را تکمیل کنید.")
    return redirect("accounting:year_end_detail", closing_id=closing.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_YEAR_END_VIEW)
@require_GET
def year_end_evidence(request, closing_id):
    closing = get_object_or_404(
        FiscalYearClosing, organization=request.organization, pk=closing_id
    )
    return JsonResponse(
        {
            "version": closing.version,
            "status": closing.status,
            "reconciliation": closing.reconciliation,
            "events": list(
                closing.events.values(
                    "sequence",
                    "created_at",
                    "previous_status",
                    "new_status",
                    "reason",
                    "evidence",
                    "evidence_hash",
                )
            ),
        },
        json_dumps_params={"ensure_ascii": False},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_YEAR_END_PREPARE)
@require_POST
def year_end_cancel(request, closing_id):
    return _act(request, closing_id, cancel_year_end)
