"""Thin, tenant/RFQ-bound UI orchestration of existing buyer lifecycle commands."""

from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
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
from apps.procurement.buyer_ui import action_url, presentation_error, workspace_context
from apps.procurement.models import (
    QuoteRevision,
    RequestForQuotationInvitation,
    SourcingAward,
    SourcingAwardPreparation,
)
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


def buyer_progress(request: HttpRequest, rfq, actions: list[dict]) -> dict:
    """Read-only prerequisites; never invent priority between concurrent commands."""
    can_metadata = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=P.RFQ_QUOTES_VIEW_METADATA,
        project=rfq.project,
    )
    progress = {"primary": None, "quote_count": None, "capture_ready": False}
    if not can_metadata:
        return progress
    revisions = QuoteRevision.objects.filter(
        organization=request.organization,
        envelope__rfq=rfq,
    )
    progress["quote_count"] = revisions.count()
    # _capture_allowed owns these exact RFQ/current-invitation prerequisites.
    progress["capture_ready"] = (
        rfq.status in {"issued", "closed"}
        and RequestForQuotationInvitation.objects.filter(
            organization=request.organization,
            rfq_version__rfq=rfq,
            rfq_version__version_number=rfq.current_version_number,
        )
        .exclude(status__in={"declined", "withdrawn", "expired"})
        .exists()
    )
    # With no revision there is no submission/opening/admissibility/comparison
    # candidate. Capture is the only determinate next buyer action in this state.
    if progress["quote_count"] == 0 and progress["capture_ready"]:
        progress["primary"] = next((a for a in actions if a["code"] == "capture"), None)
    return progress


@active_organization_required
@organization_permission_required(P.RFQS_VIEW)
@never_cache
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
    actions = action_links(request, rfq)
    context = workspace_context(request, rfq)
    comparisons_list = list(
        inputs.select_related(
            "commercial_scope__rfq_version_line__material",
            "commercial_scope__unit_of_measure",
            "commercial_scope__rfq_version",
        ).prefetch_related(
            "inputs__assertion",
            "inputs__admissibility_decision",
            "inputs__evaluations__evaluated_by",
            "evaluator_appointments__membership__user",
            "evaluator_appointments__conflicts",
            "superseded_by",
        )
    )
    allowed_actions = (
        {item["code"] for item in actions}
        if request.organization.status == "active"
        else set()
    )
    for comparison in comparisons_list:
        comparison.ui_actions = []
        comparison.has_successor = bool(list(comparison.superseded_by.all()))
        candidates = (
            ["prepare_award"]
            if comparison.finalized_at
            else []
            if comparison.has_successor
            else ["appoint_evaluator", "finalize_comparison"]
        )
        for code in candidates:
            if code in allowed_actions:
                comparison.ui_actions.append(
                    {
                        "code": code,
                        "title": ACTIONS[code][1],
                        "url": action_url(rfq, code, comparison=comparison.pk),
                    }
                )
        for appointment in comparison.evaluator_appointments.all():
            appointment.ui_actions = []
            if (
                appointment.membership.user_id == request.user.pk
                and not appointment.revoked_at
                and not comparison.finalized_at
                and not comparison.has_successor
            ):
                for code in ("evaluate", "declare_conflict"):
                    if code in allowed_actions:
                        appointment.ui_actions.append(
                            {
                                "title": ACTIONS[code][1],
                                "url": action_url(
                                    rfq, code, appointment=appointment.pk
                                ),
                            }
                        )
            for conflict in appointment.conflicts.all():
                conflict.ui_url = (
                    action_url(rfq, "dispose_conflict", conflict=conflict.pk)
                    if "dispose_conflict" in allowed_actions
                    and conflict.disposition == "proposed"
                    and conflict.declared_by_id != request.user.pk
                    and not conflict.superseded_by.exists()
                    else None
                )
    preparations = list(
        SourcingAwardPreparation.objects.filter(
            organization=request.organization, comparison__in=award_scope
        )
        .select_related("comparison__commercial_scope", "prepared_by", "final_award")
        .prefetch_related(
            "allocations__comparison_input__quote_revision__envelope__supplier"
        )
    )
    for preparation in preparations:
        preparation.ui_url = (
            action_url(rfq, "finalize_award", preparation=preparation.pk)
            if "finalize_award" in allowed_actions
            and not hasattr(preparation, "final_award")
            else None
        )
    # Approved allocation consumption is a separate explicit PO action. The
    # existing confidential comparison scope above still controls this page.
    from .order_ui import award_groups

    awards = list(
        SourcingAward.objects.filter(
            organization=request.organization, comparison__in=award_scope
        )
        .select_related(
            "comparison__commercial_scope__rfq_version__rfq__project", "finalized_by"
        )
        .prefetch_related(
            "allocations__quote_revision__envelope__supplier", "superseded_by"
        )
    )
    can_create_order = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=P.PURCHASE_ORDERS_CREATE,
        project=rfq.project,
    )
    for award in awards:
        award.order_groups = (
            award_groups(request, award)
            if can_create_order
            and award.outcome == "awarded"
            and not list(award.superseded_by.all())
            else []
        )
    return render(
        request,
        "procurement/rfq_buyer_workspace.html",
        {
            "rfq": rfq,
            "actions": actions,
            "progress": buyer_progress(request, rfq, actions),
            **context,
            "comparisons": comparisons_list,
            "award_preparations": preparations,
            "awards": awards,
        },
    )


def _execute(action: str, *, organization, actor, data: dict, rows: list[dict]):
    common = {"organization": organization, "actor": actor}
    if action == "capture":
        # Receipt metadata is derived from actual source bytes, without creating
        # custody or processing evidence before the existing close gate.
        from apps.procurement.custody_services import _stage_upload

        staged = _stage_upload(data.pop("source_file"))
        try:
            return quotes.capture_quote_revision(
                **common, integrity_fingerprint=staged.sha256, **data
            )
        finally:
            staged.path.unlink(missing_ok=True)
    if action == "attach_evidence":
        from apps.procurement.custody_services import custody_sealed_quote_evidence

        return custody_sealed_quote_evidence(
            **common, evidence_slot="attachment-" + data["idempotency_key"], **data
        )
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
@never_cache
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
        request.FILES if request.method == "POST" else None,
        rfq=rfq,
        actor=request.user,
        action=action,
        context=request.GET,
    )
    factory = {
        "prepare_comparison": ComparisonInputs,
        "prepare_award": AwardAllocations,
    }.get(action)
    row_kwargs = {"rfq": rfq, "actor": request.user}
    if action == "prepare_award":
        selected = (
            request.POST.get("comparison")
            if request.method == "POST"
            else request.GET.get("comparison")
        )
        try:
            row_kwargs["comparison"] = (
                form.fields["comparison"].queryset.filter(pk=selected).first()
                if selected
                else None
            )
        except (ValueError, ValidationError):
            row_kwargs["comparison"] = None
    rows = (
        factory(
            request.POST if request.method == "POST" else None,
            prefix="rows",
            form_kwargs=row_kwargs,
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
                    request.POST,
                    request.FILES,
                    rfq=rfq,
                    actor=request.user,
                    action=action,
                    context=request.GET,
                )
                locked_rows = (
                    factory(
                        request.POST,
                        prefix="rows",
                        form_kwargs=row_kwargs,
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
                else presentation_error(exc)
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
            "context_objects": form.context_objects,
        },
        status=400 if request.method == "POST" else 200,
    )


@active_organization_required
@organization_permission_required(P.RFQS_VIEW)
@never_cache
@require_GET
def buyer_document(request: HttpRequest, rfq_id: str, evidence_id: str) -> HttpResponse:
    from apps.procurement.models import QuoteRevisionEvidence

    rfq = _rfq(request, rfq_id)
    try:
        evidence = QuoteRevisionEvidence.objects.select_related("quote_revision").get(
            pk=evidence_id,
            organization=request.organization,
            quote_revision__envelope__rfq=rfq,
        )
    except QuoteRevisionEvidence.DoesNotExist as exc:
        raise Http404("مدرک مجاز یافت نشد.") from exc
    try:
        delivery = opening.deliver_quote_confidential_document(
            organization=request.organization,
            actor=request.user,
            quote_revision=evidence.quote_revision,
            evidence=evidence,
        )
    except (PermissionDenied, ValueError, ObjectDoesNotExist):
        return HttpResponse(
            "مشاهده این مدرک به گشایش معتبر، سلامت فایل و دسترسی فعال همین نسخه نیاز دارد.",
            status=403,
            content_type="text/plain; charset=utf-8",
        )
    response = HttpResponse(delivery.content, content_type=delivery.content_type)
    response["Content-Disposition"] = delivery.content_disposition
    response["X-Content-Type-Options"] = "nosniff"
    return response
