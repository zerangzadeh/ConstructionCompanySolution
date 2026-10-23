from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseNotFound
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.organizations.authorization import (
    get_active_membership,
    require_business_permission,
)
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode
from apps.procurement.custody_services import custody_sealed_quote_evidence
from apps.procurement.forms import (
    GoodsReceiptForm,
    OrderItemForm,
    PurchaseOrderForm,
    PurchaseRequestForm,
    ReasonForm,
    ReceiptItemForm,
    RequestItemForm,
    SealedEvidenceUploadForm,
    SupplierPortalInvitationForm,
    SupplierPortalSubmissionForm,
)
from apps.procurement.models import (
    GoodsReceipt,
    GoodsReceiptStatus,
    PurchaseOrder,
    PurchaseOrderStatus,
    PurchaseRequest,
    PurchaseRequestStatus,
    QuoteRevision,
    RequestForQuotationInvitation,
    SupplierPortalGrant,
    SupplierPortalSubmissionReceipt,
)
from apps.procurement.portal_services import (
    accept_supplier_portal_invitation,
    create_supplier_portal_invitation,
    get_supplier_portal_rfq_context,
    revoke_supplier_portal_grant,
    submit_supplier_portal_quote,
)
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
from core.list_filters import (
    apply_table_filters,
    build_table_filters,
    has_active_table_filters,
    paginate_table,
    table_pagination_query,
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


def _portal_grant(grant_id: str) -> SupplierPortalGrant:
    try:
        return SupplierPortalGrant.objects.get(pk=grant_id)
    except SupplierPortalGrant.DoesNotExist as exc:
        raise Http404("مجوز درگاه یافت نشد.") from exc


def _portal_invitation_for_management(
    request: HttpRequest, invitation_id: str
) -> RequestForQuotationInvitation:
    try:
        invitation = RequestForQuotationInvitation.objects.select_related(
            "rfq_version__rfq__project", "supplier"
        ).get(pk=invitation_id, organization=request.organization)
    except RequestForQuotationInvitation.DoesNotExist as exc:
        raise Http404("دعوت‌نامه استعلام یافت نشد.") from exc
    require_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.SUPPLIER_PORTAL_INVITATIONS_MANAGE,
        project=invitation.rfq_version.rfq.project,
        message="اجازه مدیریت دعوت‌نامه درگاه را ندارید.",
    )
    return invitation


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def supplier_portal_accept(request: HttpRequest) -> HttpResponse:
    """Accept only an existing token-bound invitation; no account provisioning."""
    if request.method == "GET":
        return render(request, "procurement/portal_accept.html")
    token = request.POST.get("token", "")
    try:
        grant = accept_supplier_portal_invitation(actor=request.user, token=token)
    except (PermissionDenied, ValueError) as exc:
        messages.error(request, str(exc))
        return redirect("procurement:portal_accept")
    return redirect("procurement:portal_context", grant_id=grant.pk)


@login_required
@never_cache
@require_GET
def supplier_portal_context(request: HttpRequest, grant_id: str) -> HttpResponse:
    grant = _portal_grant(grant_id)
    try:
        context = get_supplier_portal_rfq_context(actor=request.user, grant=grant)
    except (PermissionDenied, ValueError) as exc:
        raise Http404("زمینه مجاز درگاه یافت نشد.") from exc
    return render(
        request,
        "procurement/portal_context.html",
        {
            "portal": context,
            "grant": grant,
            "submission_form": SupplierPortalSubmissionForm(
                initial={"idempotency_key": str(uuid4())}
            ),
        },
    )


@login_required
@never_cache
@require_POST
def supplier_portal_submit(request: HttpRequest, grant_id: str) -> HttpResponse:
    grant = _portal_grant(grant_id)
    form = SupplierPortalSubmissionForm(request.POST, request.FILES)
    if request.FILES and (
        set(request.FILES) != {"upload"} or len(request.FILES.getlist("upload")) != 1
    ):
        form.add_error("upload", "هر ارسال فقط یک اصل PDF یا DOCX می‌پذیرد.")
    if form.is_valid():
        try:
            receipt = submit_supplier_portal_quote(
                actor=request.user, grant=grant, **form.cleaned_data
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("procurement:portal_receipt", receipt_id=receipt.pk)
    try:
        context = get_supplier_portal_rfq_context(actor=request.user, grant=grant)
    except PermissionDenied as exc:
        raise Http404("زمینه مجاز درگاه یافت نشد.") from exc
    return render(
        request,
        "procurement/portal_context.html",
        {"portal": context, "grant": grant, "submission_form": form},
        status=400,
    )


@login_required
@never_cache
@require_GET
def supplier_portal_receipt(request: HttpRequest, receipt_id: str) -> HttpResponse:
    try:
        receipt = SupplierPortalSubmissionReceipt.objects.select_related(
            "grant", "quote_revision"
        ).get(pk=receipt_id)
    except SupplierPortalSubmissionReceipt.DoesNotExist as exc:
        raise Http404("رسید ارسال یافت نشد.") from exc
    try:
        get_supplier_portal_rfq_context(actor=request.user, grant=receipt.grant)
    except PermissionDenied as exc:
        raise Http404("رسید ارسال یافت نشد.") from exc
    return render(request, "procurement/portal_receipt.html", {"receipt": receipt})


@active_organization_required
@organization_permission_required(
    BusinessPermissionCode.SUPPLIER_PORTAL_INVITATIONS_MANAGE
)
def portal_invitation_manage(request: HttpRequest, invitation_id: str) -> HttpResponse:
    invitation = _portal_invitation_for_management(request, invitation_id)
    token = None
    form = SupplierPortalInvitationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            created, token = create_supplier_portal_invitation(
                organization=request.organization,
                actor=request.user,
                rfq_invitation=invitation,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return render(
                request,
                "procurement/portal_invitation_manage.html",
                {
                    "invitation": invitation,
                    "form": SupplierPortalInvitationForm(),
                    "portal_invitation": created,
                    "plaintext_token": token,
                },
            )
    portal_invitations = invitation.portal_invitations.select_related(
        "accepted_principal__user"
    ).prefetch_related("grants__revocation")
    return render(
        request,
        "procurement/portal_invitation_manage.html",
        {
            "invitation": invitation,
            "form": form,
            "portal_invitations": portal_invitations,
            "plaintext_token": token,
        },
    )


@active_organization_required
@organization_permission_required(
    BusinessPermissionCode.SUPPLIER_PORTAL_INVITATIONS_MANAGE
)
@require_POST
def portal_grant_revoke(
    request: HttpRequest, invitation_id: str, grant_id: str
) -> HttpResponse:
    invitation = _portal_invitation_for_management(request, invitation_id)
    try:
        grant = SupplierPortalGrant.objects.get(pk=grant_id, rfq_invitation=invitation)
        revoke_supplier_portal_grant(
            organization=request.organization,
            actor=request.user,
            grant=grant,
            reason=request.POST.get("reason", ""),
        )
        messages.success(request, "مجوز درگاه لغو شد.")
    except (SupplierPortalGrant.DoesNotExist, PermissionDenied, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("procurement:portal_invitation_manage", invitation_id=invitation.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.RFQS_CUSTODY_SEALED_EVIDENCE)
def sealed_evidence_custody(request: HttpRequest, revision_id: str) -> HttpResponse:
    try:
        revision = QuoteRevision.objects.get(
            pk=revision_id, organization=request.organization
        )
    except QuoteRevision.DoesNotExist as exc:
        raise Http404("نسخه پیشنهاد یافت نشد.") from exc
    form = SealedEvidenceUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            custody_sealed_quote_evidence(
                organization=request.organization,
                actor=request.user,
                quote_revision=revision,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(
                request,
                "شاهد مهروموم‌شده در نگهداری قرنطینه ثبت شد؛ محتوا قابل مشاهده نیست.",
            )
            return redirect(
                "procurement:sealed_evidence_custody", revision_id=revision.pk
            )
    return render(
        request,
        "procurement/sealed_evidence_custody.html",
        {"revision": revision, "form": form},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PURCHASE_REQUESTS_VIEW)
@require_GET
def purchase_request_list(request: HttpRequest) -> HttpResponse:
    records = get_organization_purchase_requests(
        user=request.user, organization=request.organization
    )
    records = apply_table_filters(
        records,
        request,
        text_fields={
            "request": ("request_number", "title"),
            "project": ("project__name",),
        },
        choice_fields={"status": ("status", PurchaseRequestStatus.values)},
        date_fields={"required_by": "required_by"},
    )
    page = paginate_table(
        records,
        request,
        sort_fields={
            "number": "request_number",
            "title": "title",
            "record": "title",
            "project": "project__name",
            "required_by": "required_by",
            "status": "status",
        },
        default_ordering=("-created_at", "pk"),
    )
    return render(
        request,
        "procurement/request_list.html",
        {
            "requests": page.object_list,
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "filters": build_table_filters(
                request,
                [
                    {"name": "request", "kind": "text", "label": "شماره و عنوان"},
                    {"name": "project", "kind": "text", "label": "پروژه"},
                    {
                        "name": "required_by",
                        "kind": "date_range",
                        "label": "تاریخ نیاز",
                    },
                    {
                        "name": "status",
                        "kind": "select",
                        "label": "وضعیت",
                        "choices": PurchaseRequestStatus.choices,
                    },
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PURCHASE_REQUESTS_CREATE)
def purchase_request_create(request: HttpRequest) -> HttpResponse:
    form = PurchaseRequestForm(
        request.POST or None,
        organization=request.organization,
        membership=get_active_membership(
            user=request.user, organization=request.organization
        ),
    )
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
    except (PermissionDenied, ValidationError, ValueError) as exc:
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
        except (PermissionDenied, ValidationError, ValueError) as exc:
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
        except (PermissionDenied, ValidationError, ValueError) as exc:
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
    records = apply_table_filters(
        records,
        request,
        text_fields={
            "number": ("order_number",),
            "supplier": ("supplier__display_name",),
            "project": ("project__name",),
        },
        choice_fields={"status": ("status", PurchaseOrderStatus.values)},
    )
    page = paginate_table(
        records,
        request,
        sort_fields={
            "number": "order_number",
            "supplier": "supplier__display_name",
            "project": "project__name",
            "status": "status",
        },
        default_ordering=("-created_at", "pk"),
    )
    return render(
        request,
        "procurement/order_list.html",
        {
            "orders": page.object_list,
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "filters": build_table_filters(
                request,
                [
                    {"name": "number", "kind": "text", "label": "شماره سفارش"},
                    {"name": "supplier", "kind": "text", "label": "تأمین‌کننده"},
                    {"name": "project", "kind": "text", "label": "پروژه"},
                    {
                        "name": "status",
                        "kind": "select",
                        "label": "وضعیت",
                        "choices": PurchaseOrderStatus.choices,
                    },
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PURCHASE_ORDERS_CREATE)
def purchase_order_create(request: HttpRequest) -> HttpResponse:
    form = PurchaseOrderForm(
        request.POST or None,
        organization=request.organization,
        membership=get_active_membership(
            user=request.user, organization=request.organization
        ),
    )
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
    records = apply_table_filters(
        records,
        request,
        text_fields={
            "number": ("receipt_number",),
            "order": ("purchase_order__order_number",),
            "project": ("project__name",),
        },
        choice_fields={"status": ("status", GoodsReceiptStatus.values)},
    )
    page = paginate_table(
        records,
        request,
        sort_fields={
            "number": "receipt_number",
            "order": "purchase_order__order_number",
            "project": "project__name",
            "status": "status",
        },
        default_ordering=("-created_at", "pk"),
    )
    return render(
        request,
        "procurement/receipt_list.html",
        {
            "receipts": page.object_list,
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "filters": build_table_filters(
                request,
                [
                    {"name": "number", "kind": "text", "label": "شماره رسید"},
                    {"name": "order", "kind": "text", "label": "سفارش خرید"},
                    {"name": "project", "kind": "text", "label": "پروژه"},
                    {
                        "name": "status",
                        "kind": "select",
                        "label": "وضعیت",
                        "choices": GoodsReceiptStatus.choices,
                    },
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.GOODS_RECEIPTS_CREATE)
def goods_receipt_create(request: HttpRequest) -> HttpResponse:
    form = GoodsReceiptForm(
        request.POST or None,
        organization=request.organization,
        membership=get_active_membership(
            user=request.user, organization=request.organization
        ),
    )
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
