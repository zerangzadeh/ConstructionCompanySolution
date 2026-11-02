"""Discoverability and safe actions over existing Procurement RFQ authority."""

from django.core.exceptions import PermissionDenied
from django.db.models import prefetch_related_objects
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.organizations.authorization import has_business_permission
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode as P
from apps.procurement.models import (
    PurchaseRequest,
    PurchaseRequestItem,
)
from apps.procurement.request_ui import eligible_rfqs, permitted
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
    issue_rfq,
    submit_rfq_for_issue,
)
from apps.procurement.rfq_ui import list_context, preparation_error_text
from core.business_choices import contextual_parent


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
    prefetch_related_objects(
        [rfq],
        "versions__commercial_scope_definition",
        "versions__commercial_scopes__unit_of_measure",
        "versions__lines__material",
        "versions__lines__unit_of_measure",
        "versions__invitations__supplier",
    )
    org = request.organization
    project = rfq.project
    active = org.status == "active" and project.deleted_at is None

    def allowed(code):
        return active and permitted(request, code, project)

    state = rfq.status
    scope = _scope_context(request, rfq)
    lines = list(
        rfq.lines.select_related("material", "unit_of_measure").order_by(
            "sort_order", "created_at"
        )
    )
    return {
        "rfq": rfq,
        "selected_lines": lines,
        "can_view_source": permitted(request, P.PURCHASE_REQUESTS_VIEW, project),
        "can_add_line": state == "draft" and allowed(P.RFQS_CHANGE),
        "can_submit": state == "draft" and allowed(P.RFQS_SUBMIT),
        "can_issue": state == "submitted_for_issue" and allowed(P.RFQS_ISSUE),
        "can_close": state == "issued" and allowed(P.RFQS_CLOSE_CUSTODY),
        "can_cancel": state not in ("closed", "cancelled") and allowed(P.RFQS_CANCEL),
        "can_buyer": state in ("issued", "closed")
        and any(
            permitted(request, code, project)
            for code in (
                P.RFQ_QUOTES_VIEW_METADATA,
                P.RFQ_QUOTES_PREPARE_COMPARISON,
                P.RFQ_QUOTES_EVALUATE_COMPARISON,
                P.RFQ_QUOTES_FINALIZE_COMPARISON,
                P.RFQ_QUOTES_PREPARE_SOURCING_AWARD,
                P.RFQ_QUOTES_FINALIZE_SOURCING_AWARD,
            )
        ),
        "state_description": {
            "draft": "اقلام را از درخواست خرید انتخاب کنید، دامنه خرید را صریحاً تعریف کنید و استعلام را برای صدور بفرستید.",
            "submitted_for_issue": "استعلام آماده بررسی برای صدور است. دامنه خرید معتبر و حداقل یک تأمین‌کننده برای صدور لازم است.",
            "issued": "استعلام صادر شده است. اقلام، دامنه خرید، مهلت‌ها و دعوت‌نامه‌های هر نسخه تثبیت شده‌اند؛ تغییر از مسیر الحاقیه انجام می‌شود.",
            "closed": "استعلام بسته شده است. اطلاعات نسخه‌های صادرشده فقط خواندنی است.",
            "cancelled": "استعلام لغو شده است و قابل ادامه نیست. تاریخچه نسخه‌ها حفظ شده است.",
        }[state],
        "line_form": RFQLineForm(rfq=rfq),
        "issue_form": RFQIssueForm(organization=org),
        **scope,
        "close_form": RFQCloseForm(),
        "cancel_form": RFQCancelForm(),
    }


def _scope_context(request, rfq):
    from .commercial_scope_forms import source_signature
    from .commercial_scope_services import latest_definition, source_lines

    definition = latest_definition(rfq, rfq.current_version_number + 1)
    return {
        "prepared_scope": definition,
        "scope_ready": bool(
            definition
            and definition.payload["source_fingerprint"]
            == source_signature(source_lines(rfq, rfq.current_version_number + 1))
        ),
        "can_manage_scope": request.organization.status == "active"
        and rfq.status in ("draft", "submitted_for_issue", "issued")
        and has_business_permission(
            user=request.user,
            organization=request.organization,
            project=rfq.project,
            permission=P.RFQS_ADDENDUM if rfq.current_version_number else P.RFQS_CHANGE,
        ),
        "can_addendum": request.organization.status == "active"
        and rfq.status == "issued"
        and has_business_permission(
            user=request.user,
            organization=request.organization,
            project=rfq.project,
            permission=P.RFQS_ADDENDUM,
        ),
    }


@active_organization_required
@organization_permission_required(P.RFQS_VIEW)
@require_GET
def rfq_list(request: HttpRequest) -> HttpResponse:
    return render(request, "procurement/rfq_list.html", list_context(request))


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
    requests = eligible_rfqs(request)
    source = contextual_parent(request, "purchase_request", requests)
    form = RFQCreateForm(
        request.POST if request.method == "POST" else None,
        requests=requests,
        source=source,
        initial={"title": source.title} if source else None,
    )
    if request.method == "POST" and form.is_valid():
        try:
            purchase_request = form.cleaned_data["purchase_request_id"]
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
                else preparation_error_text(exc),
            )
        else:
            return redirect("procurement:rfq_detail", rfq_id=rfq.pk)
    return render(
        request,
        "procurement/rfq_form.html",
        {
            "form": form,
            "source_request": source,
            "can_view_source": source is not None
            and permitted(request, P.PURCHASE_REQUESTS_VIEW, source.project),
        },
        status=400 if request.method == "POST" else 200,
    )


@active_organization_required
@organization_permission_required(P.RFQS_CHANGE)
@require_POST
def rfq_line_add(request: HttpRequest, rfq_id: str) -> HttpResponse:
    rfq = _rfq(request, rfq_id)
    context = _context(request, rfq)
    form = RFQLineForm(request.POST, rfq=rfq)
    context["line_form"] = form
    if form.is_valid():
        try:
            item = form.cleaned_data["purchase_request_item_id"]
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
                else preparation_error_text(exc),
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
        context["action_error"] = preparation_error_text(exc)
        return render(request, "procurement/rfq_detail.html", context, status=400)
    return redirect("procurement:rfq_detail", rfq_id=rfq.pk)


@active_organization_required
@organization_permission_required(P.RFQS_ISSUE)
@require_POST
def rfq_issue(request: HttpRequest, rfq_id: str) -> HttpResponse:
    rfq = _rfq(request, rfq_id)
    context = _context(request, rfq)
    form = RFQIssueForm(request.POST, organization=request.organization)
    context["issue_form"] = form
    if form.is_valid():
        try:
            suppliers = list(form.cleaned_data["supplier_ids"])
            issue_rfq(
                organization=request.organization,
                actor=request.user,
                rfq=rfq,
                suppliers=suppliers,
                idempotency_key=form.cleaned_data["idempotency_key"],
            )
        except (ValueError, PermissionDenied) as exc:
            form.add_error(None, preparation_error_text(exc))
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
    context["open_action"] = "close"
    if form.is_valid():
        try:
            close_rfq(
                organization=request.organization,
                actor=request.user,
                rfq=rfq,
                idempotency_key=form.cleaned_data["idempotency_key"],
            )
        except (ValueError, PermissionDenied) as exc:
            form.add_error(None, preparation_error_text(exc))
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
    context["open_action"] = "cancel"
    if form.is_valid():
        try:
            cancel_rfq(
                organization=request.organization,
                actor=request.user,
                rfq=rfq,
                reason=form.cleaned_data["reason"],
            )
        except (ValueError, PermissionDenied) as exc:
            form.add_error(None, preparation_error_text(exc))
        else:
            return redirect("procurement:rfq_detail", rfq_id=rfq.pk)
    return render(request, "procurement/rfq_detail.html", context, status=400)
