"""Thin, tenant/RFQ-bound UI orchestration of existing buyer lifecycle commands."""

from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.organizations.authorization import (
    has_business_permission,
    require_business_permission,
)
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization
from apps.procurement import admissibility_services as admissibility
from apps.procurement import comparison_services as commercial
from apps.procurement import opening_services as opening
from apps.procurement import quote_services as quotes
from apps.procurement.models import SourcingAward, SourcingAwardPreparation
from apps.procurement.rfq_action_forms import (
    ACTIONS,
    AwardAllocations,
    ComparisonInputs,
    RFQActionForm,
    comparison_records,
)
from apps.procurement.rfq_workspace import _rfq


def action_links(request: HttpRequest, rfq) -> list[dict[str, str]]:
    return [
        {"code": code, "title": title}
        for code, (permission, title) in ACTIONS.items()
        if has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=permission,
            project=rfq.project,
        )
    ]


@active_organization_required
@organization_permission_required(P.RFQS_VIEW)
@require_GET
def buyer_workspace(request: HttpRequest, rfq_id: str) -> HttpResponse:
    rfq = _rfq(request, rfq_id)
    comparisons = comparison_records(rfq=rfq, actor=request.user)
    can_read = any(
        has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=permission,
            project=rfq.project,
        )
        for permission in (
            P.RFQ_QUOTES_PREPARE_COMPARISON,
            P.RFQ_QUOTES_EVALUATE_COMPARISON,
            P.RFQ_QUOTES_FINALIZE_COMPARISON,
        )
    )
    # No confidential values are read unless both stage and exact grants apply.
    inputs = (
        comparisons.prefetch_related("inputs__quote_revision__envelope__supplier")
        if can_read
        else comparisons.none()
    )
    can_award = any(
        has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=permission,
            project=rfq.project,
        )
        for permission in (
            P.RFQ_QUOTES_PREPARE_SOURCING_AWARD,
            P.RFQ_QUOTES_FINALIZE_SOURCING_AWARD,
        )
    )
    award_scope = comparisons if can_award else comparisons.none()
    return render(
        request,
        "procurement/rfq_buyer_workspace.html",
        {
            "rfq": rfq,
            "actions": action_links(request, rfq),
            "comparisons": inputs,
            "award_preparations": SourcingAwardPreparation.objects.filter(
                organization=request.organization, comparison__in=award_scope
            )
            .select_related("comparison__commercial_scope")
            .prefetch_related("allocations"),
            "awards": SourcingAward.objects.filter(
                organization=request.organization, comparison__in=award_scope
            )
            .select_related("comparison__commercial_scope")
            .prefetch_related("allocations__quote_revision__envelope__supplier"),
        },
    )


def _execute(action: str, *, organization, actor, data: dict, rows: list[dict]):
    common = {"organization": organization, "actor": actor}
    if action == "capture":
        return quotes.capture_quote_revision(**common, **data)
    if action in {"submit", "withdraw"}:
        data["revision"] = data.pop("quote_revision")
        command = (
            quotes.submit_quote_revision
            if action == "submit"
            else quotes.withdraw_quote_revision
        )
        return command(**common, **data)
    if action == "request_opening":
        return opening.request_quote_opening(**common, **data)
    if action == "approve_opening":
        return opening.approve_quote_opening(**common, **data)
    if action == "grant_access":
        return opening.grant_quote_confidential_access(**common, **data)
    if action == "revoke_access":
        return opening.revoke_quote_confidential_access(**common, **data)
    if action == "prepare_admissibility":
        return admissibility.prepare_quote_admissibility(**common, **data)
    if action == "approve_admissibility":
        return admissibility.approve_quote_admissibility(**common, **data)
    if action == "prepare_comparison":
        for row in rows:
            row["quote_revision_id"] = str(row["quote_revision_id"].pk)
        return commercial.prepare_comparison(**common, assertions=rows, **data)
    if action == "appoint_evaluator":
        return commercial.appoint_evaluator(**common, **data)
    if action == "declare_conflict":
        return commercial.declare_evaluator_conflict(**common, **data)
    if action == "dispose_conflict":
        return commercial.dispose_evaluator_conflict(**common, **data)
    if action == "evaluate":
        return commercial.evaluate_comparison(**common, **data)
    if action == "finalize_comparison":
        return commercial.finalize_comparison(**common, **data)
    if action == "prepare_award":
        for row in rows:
            row["comparison_input_id"] = str(row["comparison_input_id"].pk)
        return commercial.prepare_sourcing_award(**common, allocations=rows, **data)
    if action == "finalize_award":
        return commercial.finalize_sourcing_award(**common, **data)
    raise Http404


@active_organization_required
@organization_permission_required(P.RFQS_VIEW)
@require_http_methods(["GET", "POST"])
def buyer_action(request: HttpRequest, rfq_id: str, action: str) -> HttpResponse:
    if action not in ACTIONS:
        raise Http404
    rfq = _rfq(request, rfq_id)
    permission, title = ACTIONS[action]
    require_business_permission(
        user=request.user,
        organization=request.organization,
        permission=permission,
        project=rfq.project,
        message="مجوز انجام این مرحله را ندارید.",
    )
    form = RFQActionForm(
        request.POST if request.method == "POST" else None,
        rfq=rfq,
        actor=request.user,
        action=action,
    )
    factory = {
        "prepare_comparison": ComparisonInputs,
        "prepare_award": AwardAllocations,
    }.get(action)
    rows = (
        factory(
            request.POST if request.method == "POST" else None,
            prefix="rows",
            form_kwargs={"rfq": rfq, "actor": request.user},
        )
        if factory
        else None
    )
    if (
        request.method == "POST"
        and form.is_valid()
        and (rows is None or rows.is_valid())
    ):
        try:
            with transaction.atomic():
                # Rebuild scoped inputs under locks immediately before the domain command.
                org = Organization.objects.select_for_update().get(
                    pk=request.organization.pk, status="active"
                )
                require_business_permission(
                    user=request.user,
                    organization=org,
                    permission=permission,
                    project=rfq.project,
                    message="مجوز و دامنه معتبر لازم است.",
                )
                locked_form = RFQActionForm(
                    request.POST, rfq=rfq, actor=request.user, action=action
                )
                locked_rows = (
                    factory(
                        request.POST,
                        prefix="rows",
                        form_kwargs={"rfq": rfq, "actor": request.user},
                    )
                    if factory
                    else None
                )
                if not locked_form.is_valid() or (
                    locked_rows is not None and not locked_rows.is_valid()
                ):
                    raise PermissionDenied(
                        "مرجع مجاز تغییر کرده است؛ صفحه را بازخوانی کنید."
                    )
                data = locked_form.cleaned_data.copy()
                row_data = (
                    [dict(row.cleaned_data) for row in locked_rows if row.cleaned_data]
                    if locked_rows is not None
                    else []
                )
                # Scope is not a client assertion: every choice is bounded to this RFQ.
                if action == "prepare_comparison" and any(
                    row["quote_revision_id"].rfq_version_id
                    != data["scope"].rfq_version_id
                    for row in row_data
                ):
                    raise PermissionDenied("دامنه و نسخه پیشنهاد باید یکسان باشند.")
                if action == "prepare_award" and any(
                    row["comparison_input_id"].comparison_id != data["comparison"].pk
                    for row in row_data
                ):
                    raise PermissionDenied("تخصیص باید از همان مقایسه باشد.")
                for row in row_data:
                    for key, value in row.items():
                        if isinstance(value, Decimal):
                            row[key] = str(value)
                _execute(
                    action,
                    organization=org,
                    actor=request.user,
                    data=data,
                    rows=row_data,
                )
        except (
            PermissionDenied,
            ObjectDoesNotExist,
            ValidationError,
            ValueError,
        ) as exc:
            # Object lookup failures never reveal a protected record's identity.
            error = (
                "مرجع مجاز یافت نشد یا پیش‌نیاز مرحله برقرار نیست."
                if isinstance(exc, ObjectDoesNotExist)
                else "؛ ".join(exc.messages)
                if isinstance(exc, ValidationError)
                else str(exc)
            )
            form.add_error(None, error)
        else:
            messages.success(request, "عملیات در منبع معتبر ثبت شد.")
            return redirect("procurement:rfq_buyer_workspace", rfq_id=rfq.pk)
    return render(
        request,
        "procurement/rfq_buyer_action.html",
        {
            "rfq": rfq,
            "form": form,
            "rows": rows,
            "action": action,
            "action_title": title,
        },
        status=400 if request.method == "POST" else 200,
    )
