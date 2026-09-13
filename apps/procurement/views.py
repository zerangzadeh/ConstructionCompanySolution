from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode
from apps.procurement.forms import (
    GoodsReceiptForm,
    OrderItemForm,
    PurchaseOrderForm,
    PurchaseRequestForm,
    ReasonForm,
    ReceiptItemForm,
    RequestItemForm,
)
from apps.procurement.models import GoodsReceipt, PurchaseOrder, PurchaseRequest
from apps.procurement.services import (
    add_goods_receipt_item,
    add_purchase_order_item,
    add_purchase_request_item,
    approve_purchase_request,
    cancel_purchase_order,
    cancel_purchase_request,
    create_goods_receipt,
    create_purchase_order,
    create_purchase_request,
    get_organization_goods_receipt,
    get_organization_goods_receipts,
    get_organization_purchase_order,
    get_organization_purchase_orders,
    get_organization_purchase_request,
    get_organization_purchase_requests,
    issue_purchase_order,
    post_goods_receipt,
    reject_purchase_request,
    submit_purchase_request,
    void_goods_receipt,
)


def _not_found(record: object | None, message: str):
    return record if record is not None else HttpResponseNotFound(message)


def _request_record(
    request: HttpRequest, request_id: str
) -> PurchaseRequest | HttpResponse:
    try:
        return get_organization_purchase_request(
            user=request.user,
            organization=request.organization,
            purchase_request_id=request_id,
        )
    except PermissionDenied:
        return HttpResponseNotFound("درخواست خرید یافت نشد.")


def _order_record(request: HttpRequest, order_id: str) -> PurchaseOrder | HttpResponse:
    try:
        return get_organization_purchase_order(
            user=request.user,
            organization=request.organization,
            purchase_order_id=order_id,
        )
    except PermissionDenied:
        return HttpResponseNotFound("سفارش خرید یافت نشد.")


def _receipt_record(
    request: HttpRequest, receipt_id: str
) -> GoodsReceipt | HttpResponse:
    try:
        return get_organization_goods_receipt(
            user=request.user,
            organization=request.organization,
            goods_receipt_id=receipt_id,
        )
    except PermissionDenied:
        return HttpResponseNotFound("رسید کالا یافت نشد.")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PURCHASE_REQUESTS_VIEW)
@require_GET
def purchase_request_list(request: HttpRequest) -> HttpResponse:
    records = get_organization_purchase_requests(
        user=request.user, organization=request.organization
    )
    return render(request, "procurement/request_list.html", {"requests": records})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PURCHASE_REQUESTS_CREATE)
def purchase_request_create(request: HttpRequest) -> HttpResponse:
    form = PurchaseRequestForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            record = create_purchase_request(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("procurement:request_detail", request_id=record.pk)
    return render(
        request,
        "procurement/form.html",
        {
            "form": form,
            "title": "درخواست خرید جدید",
            "back_url": "procurement:request_list",
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PURCHASE_REQUESTS_VIEW)
@require_GET
def purchase_request_detail(request: HttpRequest, request_id: str) -> HttpResponse:
    record = _request_record(request, request_id)
    if isinstance(record, HttpResponse):
        return record
    return render(
        request,
        "procurement/request_detail.html",
        {
            "purchase_request": record,
            "item_form": RequestItemForm(organization=request.organization),
            "reason_form": ReasonForm(),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PURCHASE_REQUEST_ITEMS_ADD)
@require_POST
def purchase_request_item_add(request: HttpRequest, request_id: str) -> HttpResponse:
    record = _request_record(request, request_id)
    if isinstance(record, HttpResponse):
        return record
    form = RequestItemForm(request.POST, organization=request.organization)
    if form.is_valid():
        try:
            data = form.cleaned_data
            add_purchase_request_item(
                organization=request.organization,
                actor=request.user,
                purchase_request=record,
                unit_of_measure=data["material"].unit_of_measure,
                **data,
            )
            messages.success(request, "ردیف درخواست خرید افزوده شد.")
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "فیلدهای ردیف درخواست را بررسی کنید.")
    return redirect("procurement:request_detail", request_id=request_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PURCHASE_REQUESTS_SUBMIT)
@require_POST
def purchase_request_submit(request: HttpRequest, request_id: str) -> HttpResponse:
    record = _request_record(request, request_id)
    if isinstance(record, HttpResponse):
        return record
    try:
        submit_purchase_request(
            organization=request.organization,
            actor=request.user,
            purchase_request=record,
        )
        messages.success(request, "درخواست خرید ارسال شد.")
    except (PermissionDenied, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("procurement:request_detail", request_id=request_id)


def _request_decision(
    request: HttpRequest, request_id: str, *, approve: bool
) -> HttpResponse:
    record = _request_record(request, request_id)
    if isinstance(record, HttpResponse):
        return record
    form = ReasonForm(request.POST)
    if form.is_valid():
        try:
            service = approve_purchase_request if approve else reject_purchase_request
            service(
                organization=request.organization,
                actor=request.user,
                purchase_request=record,
                **form.cleaned_data,
            )
            messages.success(
                request, "درخواست خرید تأیید شد." if approve else "درخواست خرید رد شد."
            )
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "دلیل را وارد کنید.")
    return redirect("procurement:request_detail", request_id=request_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PURCHASE_REQUESTS_APPROVE)
@require_POST
def purchase_request_approve(request: HttpRequest, request_id: str) -> HttpResponse:
    return _request_decision(request, request_id, approve=True)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PURCHASE_REQUESTS_REJECT)
@require_POST
def purchase_request_reject(request: HttpRequest, request_id: str) -> HttpResponse:
    return _request_decision(request, request_id, approve=False)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PURCHASE_REQUESTS_CANCEL)
@require_POST
def purchase_request_cancel(request: HttpRequest, request_id: str) -> HttpResponse:
    record = _request_record(request, request_id)
    if isinstance(record, HttpResponse):
        return record
    form = ReasonForm(request.POST)
    if form.is_valid():
        try:
            cancel_purchase_request(
                organization=request.organization,
                actor=request.user,
                purchase_request=record,
                **form.cleaned_data,
            )
            messages.success(request, "درخواست خرید لغو شد.")
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "دلیل لغو را وارد کنید.")
    return redirect("procurement:request_detail", request_id=request_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PURCHASE_ORDERS_VIEW)
@require_GET
def purchase_order_list(request: HttpRequest) -> HttpResponse:
    records = get_organization_purchase_orders(
        user=request.user, organization=request.organization
    )
    return render(request, "procurement/order_list.html", {"orders": records})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PURCHASE_ORDERS_CREATE)
def purchase_order_create(request: HttpRequest) -> HttpResponse:
    form = PurchaseOrderForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            record = create_purchase_order(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("procurement:order_detail", order_id=record.pk)
    return render(
        request,
        "procurement/form.html",
        {
            "form": form,
            "title": "سفارش خرید جدید",
            "back_url": "procurement:order_list",
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PURCHASE_ORDERS_VIEW)
@require_GET
def purchase_order_detail(request: HttpRequest, order_id: str) -> HttpResponse:
    record = _order_record(request, order_id)
    if isinstance(record, HttpResponse):
        return record
    return render(
        request,
        "procurement/order_detail.html",
        {
            "purchase_order": record,
            "item_form": OrderItemForm(
                organization=request.organization, purchase_order=record
            ),
            "reason_form": ReasonForm(),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PURCHASE_ORDER_ITEMS_ADD)
@require_POST
def purchase_order_item_add(request: HttpRequest, order_id: str) -> HttpResponse:
    record = _order_record(request, order_id)
    if isinstance(record, HttpResponse):
        return record
    form = OrderItemForm(
        request.POST, organization=request.organization, purchase_order=record
    )
    if form.is_valid():
        try:
            data = form.cleaned_data
            add_purchase_order_item(
                organization=request.organization,
                actor=request.user,
                purchase_order=record,
                unit_of_measure=data["material"].unit_of_measure,
                **data,
            )
            messages.success(request, "ردیف سفارش خرید افزوده شد.")
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "فیلدهای ردیف سفارش را بررسی کنید.")
    return redirect("procurement:order_detail", order_id=order_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PURCHASE_ORDERS_ISSUE)
@require_POST
def purchase_order_issue(request: HttpRequest, order_id: str) -> HttpResponse:
    record = _order_record(request, order_id)
    if isinstance(record, HttpResponse):
        return record
    try:
        issue_purchase_order(
            organization=request.organization, actor=request.user, purchase_order=record
        )
        messages.success(request, "سفارش خرید صادر شد.")
    except (PermissionDenied, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("procurement:order_detail", order_id=order_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PURCHASE_ORDERS_CANCEL)
@require_POST
def purchase_order_cancel(request: HttpRequest, order_id: str) -> HttpResponse:
    record = _order_record(request, order_id)
    if isinstance(record, HttpResponse):
        return record
    form = ReasonForm(request.POST)
    if form.is_valid():
        try:
            cancel_purchase_order(
                organization=request.organization,
                actor=request.user,
                purchase_order=record,
                **form.cleaned_data,
            )
            messages.success(request, "سفارش خرید لغو شد.")
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "دلیل لغو را وارد کنید.")
    return redirect("procurement:order_detail", order_id=order_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.GOODS_RECEIPTS_VIEW)
@require_GET
def goods_receipt_list(request: HttpRequest) -> HttpResponse:
    records = get_organization_goods_receipts(
        user=request.user, organization=request.organization
    )
    return render(request, "procurement/receipt_list.html", {"receipts": records})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.GOODS_RECEIPTS_CREATE)
def goods_receipt_create(request: HttpRequest) -> HttpResponse:
    form = GoodsReceiptForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            record = create_goods_receipt(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("procurement:receipt_detail", receipt_id=record.pk)
    return render(
        request,
        "procurement/form.html",
        {
            "form": form,
            "title": "رسید کالای جدید",
            "back_url": "procurement:receipt_list",
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.GOODS_RECEIPTS_VIEW)
@require_GET
def goods_receipt_detail(request: HttpRequest, receipt_id: str) -> HttpResponse:
    record = _receipt_record(request, receipt_id)
    if isinstance(record, HttpResponse):
        return record
    return render(
        request,
        "procurement/receipt_detail.html",
        {
            "goods_receipt": record,
            "item_form": ReceiptItemForm(purchase_order=record.purchase_order),
            "reason_form": ReasonForm(),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.GOODS_RECEIPT_ITEMS_ADD)
@require_POST
def goods_receipt_item_add(request: HttpRequest, receipt_id: str) -> HttpResponse:
    record = _receipt_record(request, receipt_id)
    if isinstance(record, HttpResponse):
        return record
    form = ReceiptItemForm(request.POST, purchase_order=record.purchase_order)
    if form.is_valid():
        try:
            add_goods_receipt_item(
                organization=request.organization,
                actor=request.user,
                goods_receipt=record,
                **form.cleaned_data,
            )
            messages.success(request, "ردیف رسید کالا افزوده شد.")
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "فیلدهای ردیف رسید را بررسی کنید.")
    return redirect("procurement:receipt_detail", receipt_id=receipt_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.GOODS_RECEIPTS_POST)
@require_POST
def goods_receipt_post(request: HttpRequest, receipt_id: str) -> HttpResponse:
    record = _receipt_record(request, receipt_id)
    if isinstance(record, HttpResponse):
        return record
    try:
        post_goods_receipt(
            organization=request.organization, actor=request.user, goods_receipt=record
        )
        messages.success(request, "رسید کالا ثبت نهایی شد.")
    except (PermissionDenied, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("procurement:receipt_detail", receipt_id=receipt_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.GOODS_RECEIPTS_VOID)
@require_POST
def goods_receipt_void(request: HttpRequest, receipt_id: str) -> HttpResponse:
    record = _receipt_record(request, receipt_id)
    if isinstance(record, HttpResponse):
        return record
    form = ReasonForm(request.POST)
    if form.is_valid():
        try:
            void_goods_receipt(
                organization=request.organization,
                actor=request.user,
                goods_receipt=record,
                **form.cleaned_data,
            )
            messages.success(request, "رسید کالا باطل شد.")
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "دلیل ابطال را وارد کنید.")
    return redirect("procurement:receipt_detail", receipt_id=receipt_id)
