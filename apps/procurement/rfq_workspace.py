"""Discoverability and safe actions over existing Procurement RFQ authority."""

from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.organizations.authorization import has_business_permission
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode as P
from apps.parties.models import BusinessParty
from apps.procurement.models import (
    CommercialComparison,
    PurchaseRequest,
    PurchaseRequestItem,
    QuoteRevision,
    SourcingAward,
)
from apps.procurement.rfq_forms import (
    RFQCancelForm,
    RFQCloseForm,
    RFQCreateForm,
    RFQIssueForm,
    RFQLineForm,
)
from apps.procurement.rfq_services import (
    add_rfq_line,
    cancel_rfq,
    close_rfq,
    create_rfq,
    get_organization_rfq,
    get_organization_rfqs,
    issue_rfq,
    submit_rfq_for_issue,
)


def _rfq(request: HttpRequest, rfq_id: str):
    try:
        return get_organization_rfq(
            user=request.user,
            organization=request.organization,
            rfq_id=rfq_id,
        )
    except PermissionDenied as exc:
        raise Http404("استعلام مجاز یافت نشد.") from exc


def _context(request: HttpRequest, rfq):
    org = request.organization
    project = rfq.project
    can_quotes = has_business_permission(
        user=request.user,
        organization=org,
        permission=P.RFQ_QUOTES_VIEW_METADATA,
        project=project,
    )
    can_compare = any(
        has_business_permission(
            user=request.user,
            organization=org,
            permission=code,
            project=project,
        )
        for code in (
            P.RFQ_QUOTES_PREPARE_COMPARISON,
            P.RFQ_QUOTES_EVALUATE_COMPARISON,
            P.RFQ_QUOTES_FINALIZE_COMPARISON,
        )
    )
    can_award = any(
        has_business_permission(
            user=request.user,
            organization=org,
            permission=code,
            project=project,
        )
        for code in (
            P.RFQ_QUOTES_PREPARE_SOURCING_AWARD,
            P.RFQ_QUOTES_FINALIZE_SOURCING_AWARD,
        )
    )
    revisions = (
        list(
            QuoteRevision.objects.filter(
                organization=org,
                envelope__rfq=rfq,
            )
            .select_related("envelope__supplier")
            .order_by("-created_at")
        )
        if can_quotes
        else []
    )
    comparisons = (
        list(
            CommercialComparison.objects.filter(
                organization=org,
                commercial_scope__rfq_version__rfq=rfq,
            )
            .select_related("commercial_scope")
            .order_by("-created_at")
        )
        if can_compare
        else []
    )
    awards = (
        list(
            SourcingAward.objects.filter(
                organization=org,
                comparison__commercial_scope__rfq_version__rfq=rfq,
            )
            .select_related("comparison")
            .order_by("-created_at")
        )
        if can_award
        else []
    )
    return {
        "rfq": rfq,
        "quote_revisions": revisions,
        "comparisons": comparisons,
        "awards": awards,
        "can_quotes": can_quotes,
        "can_compare": can_compare,
        "can_award": can_award,
        "line_form": RFQLineForm(),
        "issue_form": RFQIssueForm(),
        "close_form": RFQCloseForm(),
        "cancel_form": RFQCancelForm(),
    }


@active_organization_required
@organization_permission_required(P.RFQS_VIEW)
@require_GET
def rfq_list(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "procurement/rfq_list.html",
        {
            "rfqs": get_organization_rfqs(
                user=request.user, organization=request.organization
            ).order_by("-created_at")[:100],
        },
    )


@active_organization_required
@organization_permission_required(P.RFQS_VIEW)
@require_GET
def rfq_detail(request: HttpRequest, rfq_id: str) -> HttpResponse:
    rfq = _rfq(request, rfq_id)
    return render(request, "procurement/rfq_detail.html", _context(request, rfq))


@active_organization_required
@organization_permission_required(P.RFQS_CREATE)
@require_http_methods(["GET", "POST"])
def rfq_create(request: HttpRequest) -> HttpResponse:
    form = RFQCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            purchase_request = PurchaseRequest.objects.select_related("project").get(
                pk=form.cleaned_data["purchase_request_id"],
                organization=request.organization,
            )
            rfq = create_rfq(
                organization=request.organization,
                actor=request.user,
                project=purchase_request.project,
                purchase_request=purchase_request,
                rfq_number=form.cleaned_data["rfq_number"],
                title=form.cleaned_data["title"],
                closing_at=form.cleaned_data["closing_at"],
                earliest_opening_at=form.cleaned_data["earliest_opening_at"],
                terms=form.cleaned_data["terms"],
            )
        except (PurchaseRequest.DoesNotExist, PermissionDenied, ValueError) as exc:
            form.add_error(
                None,
                "درخواست خرید مجاز یافت نشد یا داده استعلام نامعتبر است."
                if isinstance(exc, PurchaseRequest.DoesNotExist)
                else str(exc),
            )
        else:
            return redirect("procurement:rfq_detail", rfq_id=rfq.pk)
    return render(
        request,
        "procurement/rfq_form.html",
        {"form": form},
        status=400 if request.method == "POST" else 200,
    )


@active_organization_required
@organization_permission_required(P.RFQS_CHANGE)
@require_POST
def rfq_line_add(request: HttpRequest, rfq_id: str) -> HttpResponse:
    rfq = _rfq(request, rfq_id)
    context = _context(request, rfq)
    form = RFQLineForm(request.POST)
    context["line_form"] = form
    if form.is_valid():
        try:
            item = PurchaseRequestItem.objects.get(
                pk=form.cleaned_data["purchase_request_item_id"],
                organization=request.organization,
                purchase_request=rfq.purchase_request,
            )
            add_rfq_line(
                organization=request.organization,
                actor=request.user,
                rfq=rfq,
                purchase_request_item=item,
                quantity=form.cleaned_data["quantity"],
                description=form.cleaned_data["description"],
            )
        except (PurchaseRequestItem.DoesNotExist, PermissionDenied, ValueError) as exc:
            form.add_error(
                None,
                "ردیف درخواست خرید مجاز یافت نشد."
                if isinstance(exc, PurchaseRequestItem.DoesNotExist)
                else str(exc),
            )
        else:
            return redirect("procurement:rfq_detail", rfq_id=rfq.pk)
    return render(request, "procurement/rfq_detail.html", context, status=400)


@active_organization_required
@organization_permission_required(P.RFQS_SUBMIT)
@require_POST
def rfq_submit(request: HttpRequest, rfq_id: str) -> HttpResponse:
    rfq = _rfq(request, rfq_id)
    try:
        submit_rfq_for_issue(
            organization=request.organization, actor=request.user, rfq=rfq
        )
    except (PermissionDenied, ValueError) as exc:
        context = _context(request, rfq)
        context["action_error"] = str(exc)
        return render(request, "procurement/rfq_detail.html", context, status=400)
    return redirect("procurement:rfq_detail", rfq_id=rfq.pk)


@active_organization_required
@organization_permission_required(P.RFQS_ISSUE)
@require_POST
def rfq_issue(request: HttpRequest, rfq_id: str) -> HttpResponse:
    rfq = _rfq(request, rfq_id)
    context = _context(request, rfq)
    form = RFQIssueForm(request.POST)
    context["issue_form"] = form
    if form.is_valid():
        try:
            ids = [
                UUID(value.strip())
                for value in form.cleaned_data["supplier_ids"].split(",")
            ]
            suppliers = list(
                BusinessParty.objects.filter(
                    organization=request.organization,
                    pk__in=ids,
                )
            )
            if len(suppliers) != len(ids):
                raise PermissionDenied("تأمین‌کننده مجاز یافت نشد.")
            issue_rfq(
                organization=request.organization,
                actor=request.user,
                rfq=rfq,
                suppliers=suppliers,
                idempotency_key=form.cleaned_data["idempotency_key"],
            )
        except (ValueError, PermissionDenied) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("procurement:rfq_detail", rfq_id=rfq.pk)
    return render(request, "procurement/rfq_detail.html", context, status=400)


@active_organization_required
@organization_permission_required(P.RFQS_CLOSE_CUSTODY)
@require_POST
def rfq_close(request: HttpRequest, rfq_id: str) -> HttpResponse:
    rfq = _rfq(request, rfq_id)
    context = _context(request, rfq)
    form = RFQCloseForm(request.POST)
    context["close_form"] = form
    if form.is_valid():
        try:
            close_rfq(
                organization=request.organization,
                actor=request.user,
                rfq=rfq,
                idempotency_key=form.cleaned_data["idempotency_key"],
            )
        except (ValueError, PermissionDenied) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("procurement:rfq_detail", rfq_id=rfq.pk)
    return render(request, "procurement/rfq_detail.html", context, status=400)


@active_organization_required
@organization_permission_required(P.RFQS_CANCEL)
@require_POST
def rfq_cancel(request: HttpRequest, rfq_id: str) -> HttpResponse:
    rfq = _rfq(request, rfq_id)
    context = _context(request, rfq)
    form = RFQCancelForm(request.POST)
    context["cancel_form"] = form
    if form.is_valid():
        try:
            cancel_rfq(
                organization=request.organization,
                actor=request.user,
                rfq=rfq,
                reason=form.cleaned_data["reason"],
            )
        except (ValueError, PermissionDenied) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("procurement:rfq_detail", rfq_id=rfq.pk)
    return render(request, "procurement/rfq_detail.html", context, status=400)
