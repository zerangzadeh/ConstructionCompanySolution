"""Scoped HTTP adapters; Procurement services retain receipt mutation authority."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.organizations.authorization import (
    get_active_membership,
)
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode as P
from apps.parties.models import BusinessParty
from apps.procurement import models as m
from apps.procurement.buyer_ui import presentation_error
from apps.procurement.forms import ReasonForm
from apps.procurement.order_forms import order_label
from apps.procurement.receipt_actions import prepare_receipt, prepare_receipt_line
from apps.procurement.receipt_forms import (
    ReceiptCreateForm,
    ReceiptFilterForm,
    ReceiptLineForm,
)
from apps.procurement.receipt_ui import (
    quantity_rows,
    receipt_context,
    receipt_orders,
    receipt_readiness,
)
from apps.procurement.request_ui import permitted
from apps.procurement.services import (
    get_organization_goods_receipts,
    post_goods_receipt,
    void_goods_receipt,
)
from apps.projects.models import Project
from core.business_choices import business_label, contextual_parent
from core.list_filters import (
    apply_table_filters,
    build_filter_bar,
    paginate_table,
    table_pagination_query,
)


def _receipt(request, receipt_id):
    return get_object_or_404(
        get_organization_goods_receipts(
            user=request.user, organization=request.organization
        ).select_related(
            "purchase_order__supplier",
            "purchase_order__current_version",
            "purchase_order_version",
        ),
        pk=receipt_id,
    )


def _detail(request, receipt, **overrides):
    context = receipt_context(request, receipt)
    context.update(
        item_form=ReceiptLineForm(receipt=receipt, rows=context["quantity_rows"]),
        reason_form=ReasonForm(),
    )
    return {**context, **overrides}


@active_organization_required
@organization_permission_required(P.GOODS_RECEIPTS_VIEW)
@never_cache
@require_GET
def receipt_list(request):
    records = get_organization_goods_receipts(
        user=request.user, organization=request.organization
    ).select_related("purchase_order__supplier")
    has_records = records.exists()
    projects = Project.objects.filter(
        organization=request.organization, pk__in=records.values("project_id")
    ).order_by("name")
    suppliers = BusinessParty.objects.filter(
        organization=request.organization,
        pk__in=records.values("purchase_order__supplier_id"),
    ).order_by("display_name")
    form = ReceiptFilterForm(request.GET, projects=projects, suppliers=suppliers)
    if not form.is_valid():
        records = records.none()
    else:
        if form.cleaned_data["project"]:
            records = records.filter(project=form.cleaned_data["project"])
        if form.cleaned_data["supplier"]:
            records = records.filter(
                purchase_order__supplier=form.cleaned_data["supplier"]
            )
    records = apply_table_filters(
        records,
        request,
        text_fields={
            "q": (
                "receipt_number",
                "purchase_order__order_number",
                "project__name",
                "purchase_order__supplier__display_name",
            )
        },
        choice_fields={"status": ("status", m.GoodsReceiptStatus.values)},
        date_fields={"date": "received_at__date"},
    )
    sorts = {
        "number": "receipt_number",
        "order": "purchase_order__order_number",
        "supplier": "purchase_order__supplier__display_name",
        "project": "project__name",
        "date": "received_at",
        "status": "status",
    }
    page = paginate_table(
        records, request, sort_fields=sorts, default_ordering=("-received_at", "pk")
    )
    if request.GET.get("format") == "xlsx":
        from apps.procurement.xlsx_exports import procurement_download

        return procurement_download(
            "receipt", page.paginator.object_list, organization=request.organization
        )

    bar = build_filter_bar(
        request,
        form=form,
        quick_fields=("status", "project"),
        secondary_fields=("supplier", "date_from", "date_to"),
        result_count=page.paginator.count,
        result_label="رسید کالا",
    )
    return render(
        request,
        "procurement/receipt_list.html",
        {
            "receipts": page.object_list,
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "filter_bar": bar,
            "scoped_has_records": has_records,
            "clear_filters_url": bar["clear_url"],
            "create_url": reverse("procurement:receipt_create")
            if request.organization.status == "active"
            and permitted(request, P.GOODS_RECEIPTS_CREATE)
            else "",
            "list_sort": {
                "label": {
                    "number": "شماره رسید",
                    "order": "سفارش خرید",
                    "supplier": "تأمین‌کننده",
                    "project": "پروژه",
                    "date": "تاریخ دریافت",
                    "status": "وضعیت",
                }.get(request.GET.get("sort"), "جدیدترین دریافت"),
                "descending": request.GET.get("direction") == "desc"
                or request.GET.get("sort") not in sorts,
            },
        },
    )


@active_organization_required
@organization_permission_required(P.GOODS_RECEIPTS_CREATE)
@never_cache
@require_http_methods(["GET", "POST"])
def receipt_create(request):
    orders = receipt_orders(request)
    source = contextual_parent(request, "purchase_order", orders)
    form = ReceiptCreateForm(
        request.POST or None,
        organization=request.organization,
        membership=get_active_membership(
            user=request.user, organization=request.organization
        ),
        orders=orders,
        source_order=source,
    )
    error = receipt_readiness(source) if source else ""
    if request.method == "POST" and form.is_valid():
        try:
            receipt = prepare_receipt(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError, ValidationError, IntegrityError) as exc:
            form.add_error(
                None,
                presentation_error(exc)
                if not isinstance(exc, IntegrityError)
                else "شماره رسید قبلاً ثبت شده است؛ فهرست رسیدها را بررسی کنید.",
            )
        else:
            return redirect("procurement:receipt_detail", receipt_id=receipt.pk)
    return render(
        request,
        "procurement/receipt_create.html",
        {
            "form": form,
            "source_order": source,
            "source_error": error,
            "quantity_rows": quantity_rows(source) if source else [],
        },
        status=400 if request.method == "POST" else 200,
    )


@active_organization_required
@organization_permission_required(P.GOODS_RECEIPTS_VIEW)
@never_cache
@require_GET
def receipt_detail(request, receipt_id):
    return render(
        request,
        "procurement/receipt_detail.html",
        _detail(request, _receipt(request, receipt_id)),
    )


@active_organization_required
@organization_permission_required(P.GOODS_RECEIPT_ITEMS_ADD)
@never_cache
@require_POST
def receipt_item_add(request, receipt_id):
    receipt = _receipt(request, receipt_id)
    form = ReceiptLineForm(
        request.POST,
        receipt=receipt,
        rows=quantity_rows(receipt.purchase_order, receipt=receipt),
    )
    if form.is_valid():
        try:
            prepare_receipt_line(
                organization=request.organization,
                actor=request.user,
                goods_receipt=receipt,
                **form.cleaned_data,
            )
            return redirect("procurement:receipt_detail", receipt_id=receipt.pk)
        except (PermissionDenied, ValueError, ValidationError, IntegrityError) as exc:
            form.add_error(
                None,
                presentation_error(exc)
                if not isinstance(exc, IntegrityError)
                else "این ردیف قبلاً به رسید افزوده شده است.",
            )
    return render(
        request,
        "procurement/receipt_detail.html",
        _detail(request, receipt, item_form=form),
        status=400,
    )


@active_organization_required
@organization_permission_required(P.GOODS_RECEIPTS_POST)
@never_cache
@require_POST
def receipt_post(request, receipt_id):
    receipt = _receipt(request, receipt_id)
    try:
        post_goods_receipt(
            organization=request.organization, actor=request.user, goods_receipt=receipt
        )
    except (PermissionDenied, ValueError, ValidationError) as exc:
        receipt.refresh_from_db()
        return render(
            request,
            "procurement/receipt_detail.html",
            _detail(request, receipt, action_error=presentation_error(exc)),
            status=400,
        )
    return redirect("procurement:receipt_detail", receipt_id=receipt.pk)


@active_organization_required
@organization_permission_required(P.GOODS_RECEIPTS_VOID)
@never_cache
@require_POST
def receipt_void(request, receipt_id):
    receipt = _receipt(request, receipt_id)
    form = ReasonForm(request.POST)
    if form.is_valid():
        try:
            void_goods_receipt(
                organization=request.organization,
                actor=request.user,
                goods_receipt=receipt,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError, ValidationError) as exc:
            form.add_error(None, presentation_error(exc))
        else:
            return redirect("procurement:receipt_detail", receipt_id=receipt.pk)
    return render(
        request,
        "procurement/receipt_detail.html",
        _detail(request, receipt, reason_form=form),
        status=400,
    )


@active_organization_required
@never_cache
@require_GET
def receipt_choices(request, purpose, field):
    if purpose == "create" and field == "purchase_order":
        records = (
            receipt_orders(request)
            .filter(
                status="issued",
                current_version__isnull=False,
                current_version__lines__isnull=False,
            )
            .distinct()
        )
        columns = ("order_number", "supplier__display_name", "project__name")
        label = order_label
    elif purpose == "filter" and field in ("project", "supplier"):
        receipts = get_organization_goods_receipts(
            user=request.user, organization=request.organization
        )
        records = (
            Project.objects.filter(
                organization=request.organization, pk__in=receipts.values("project_id")
            )
            if field == "project"
            else BusinessParty.objects.filter(
                organization=request.organization,
                pk__in=receipts.values("purchase_order__supplier_id"),
            )
        )
        columns = ("name", "code") if field == "project" else ("display_name",)
        label = business_label
    else:
        raise PermissionDenied
    query = Q()
    for column in columns:
        query |= Q(**{column + "__icontains": request.GET.get("q", "").strip()})
    page = Paginator(records.filter(query).order_by("pk"), 40).get_page(
        request.GET.get("page")
    )
    params = request.GET.copy()
    if page.has_next():
        params["page"] = page.next_page_number()
    return JsonResponse(
        {
            "results": [{"value": str(row.pk), "label": label(row)} for row in page],
            "next": request.path + "?" + params.urlencode()
            if page.has_next()
            else None,
        }
    )
