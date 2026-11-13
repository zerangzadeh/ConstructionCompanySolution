from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Literal
from zoneinfo import ZoneInfo

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.inventory.models import (
    DownstreamCostSourceEnvelope,
    InventoryCountStatus,
    InventoryLot,
    InventorySerial,
    InventoryTransferLine,
    InventoryTransferStatus,
    InventoryValuationEvent,
    InventoryValuationPool,
    TraceQualityStatus,
    TransferExceptionCode,
    Warehouse,
)
from apps.inventory.p8_forms import (
    InboundTransferFilterForm,
    InventoryCountCreateForm,
    InventoryCountSubmissionForm,
    InventoryTransferCreateForm,
    ReservationCreateForm,
)
from apps.inventory.p8_services import (
    TraceAllocationSpec,
    TransferLineSpec,
    accept_inventory_transfer,
    activate_reservation,
    approve_inventory_count,
    create_inventory_count,
    create_inventory_transfer,
    create_reservation,
    dispatch_inventory_transfer,
    freeze_inventory_count,
    get_inventory_counts,
    get_inventory_transfers,
    get_reservations,
    inventory_reconciliation,
    inventory_transfer_receiving_available,
    mark_transfer_in_transit,
    post_inventory_count,
    record_and_submit_inventory_count,
    release_reservation,
    valuation_reconciliation,
)
from apps.inventory.services import get_organization_stock_transactions
from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
    membership_has_permission,
    membership_has_scope,
    scope_queryset,
)
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode, OrganizationMembership
from core.list_filters import build_filter_bar, table_pagination_query

RECEIVING_TABS = {
    "inbound": "انتقال‌های ورودی در انتظار دریافت",
    "transfer-history": "سوابق انتقال‌های ورودی",
}
CUSTODY_SUMMARY_PERMISSIONS = (
    BusinessPermissionCode.INVENTORY_RECONCILIATIONS_VIEW,
    BusinessPermissionCode.INVENTORY_RESERVATIONS_VIEW,
    BusinessPermissionCode.INVENTORY_COUNTS_VIEW,
    BusinessPermissionCode.INVENTORY_TRANSFERS_VIEW,
)


def _can_open_custody_summary(membership: OrganizationMembership) -> bool:
    return membership_has_scope(membership) and all(
        membership_has_permission(membership, permission)
        for permission in CUSTODY_SUMMARY_PERMISSIONS
    )


def _receiving_url(tab: str) -> str:
    return reverse("inventory:custody_workbench", query={"tab": tab})


def _service_error(request: HttpRequest, exc: Exception) -> None:
    messages.error(request, str(exc))


def _count(request: HttpRequest, count_id: str):
    record = (
        get_inventory_counts(organization=request.organization, user=request.user)
        .filter(pk=count_id)
        .first()
    )
    if record is None:
        raise Http404("شمارش موجودی یافت نشد.")
    return record


def _transfer(
    request: HttpRequest,
    transfer_id: str,
    *,
    side: Literal["source", "destination"] | None = None,
):
    record = (
        get_inventory_transfers(
            organization=request.organization, user=request.user, side=side
        )
        .filter(pk=transfer_id)
        .first()
    )
    if record is None:
        raise Http404("انتقال موجودی یافت نشد.")
    return record


def _receiving_tab(
    request: HttpRequest,
    tab: str,
    membership: OrganizationMembership,
    can_open_summary: bool,
) -> HttpResponse:
    organization = request.organization
    transfers = get_inventory_transfers(
        organization=organization, user=request.user, side="destination"
    )
    if tab == "inbound":
        transfers = transfers.filter(status=InventoryTransferStatus.IN_TRANSIT).exclude(
            dispatched_by=request.user
        )
    else:
        transfers = transfers.filter(status=InventoryTransferStatus.ACCEPTED)
    destinations = scope_queryset(
        Warehouse.objects.filter(organization=organization),
        membership=membership,
        project_lookup="project_id",
    ).order_by("name", "code")
    form = InboundTransferFilterForm(request.GET, destinations=destinations)
    if not form.is_valid():
        transfers = transfers.none()
    else:
        if query := form.cleaned_data["q"]:
            transfers = transfers.filter(
                Q(transfer_number__icontains=query)
                | Q(source_warehouse__name__icontains=query)
                | Q(destination_warehouse__name__icontains=query)
            )
        if destination := form.cleaned_data["destination"]:
            transfers = transfers.filter(destination_warehouse=destination)
    order = "-dispatched_at" if tab == "inbound" else "-accepted_at"
    lines = (
        InventoryTransferLine.objects.filter(organization=organization)
        .select_related("material", "unit_of_measure")
        .order_by("created_at", "pk")
    )
    page = Paginator(
        transfers.order_by(order, "pk").prefetch_related(
            Prefetch("lines", queryset=lines)
        ),
        20,
    ).get_page(request.GET.get("page"))
    settings_record = getattr(organization, "settings", None)
    zone = ZoneInfo(
        settings_record.timezone if settings_record else organization.timezone
    )
    with timezone.override(zone):
        return render(
            request,
            "inventory/custody_workbench.html",
            {
                "receiving_tab": tab,
                "receiving_title": RECEIVING_TABS[tab],
                "inbound_url": _receiving_url("inbound"),
                "transfer_history_url": _receiving_url("transfer-history"),
                "can_open_summary": can_open_summary,
                "page_obj": page,
                "pagination_query": table_pagination_query(request),
                "filter_bar": build_filter_bar(
                    request,
                    form=form,
                    quick_fields=("destination",),
                    context={"tab": tab},
                    result_count=page.paginator.count,
                    result_label="انتقال",
                ),
            },
        )


@active_organization_required
@require_GET
def custody_workbench(request: HttpRequest) -> HttpResponse:
    membership = get_active_membership(
        user=request.user, organization=request.organization
    )
    can_open_summary = _can_open_custody_summary(membership)
    can_receive = inventory_transfer_receiving_available(membership)
    tab = request.GET.get("tab")
    if tab in RECEIVING_TABS or (not tab and can_receive and not can_open_summary):
        if not can_receive:
            raise PermissionDenied("اجازه مشاهده انتقال‌های ورودی را ندارید.")
        return _receiving_tab(request, tab or "inbound", membership, can_open_summary)
    if not can_open_summary:
        raise PermissionDenied("اجازه مشاهده خلاصه کنترل موجودی را ندارید.")
    horizon = timezone.localdate() + timedelta(days=30)
    lots = InventoryLot.objects.filter(
        organization=request.organization,
        status__in=[TraceQualityStatus.AVAILABLE, TraceQualityStatus.QUARANTINED],
        expires_on__lte=horizon,
    ).select_related("material")[:20]
    serials = InventorySerial.objects.filter(
        organization=request.organization,
        status__in=[TraceQualityStatus.AVAILABLE, TraceQualityStatus.QUARANTINED],
        expires_on__lte=horizon,
    ).select_related("material")[:20]
    return render(
        request,
        "inventory/custody_workbench.html",
        {
            "inbound_url": _receiving_url("inbound") if can_receive else "",
            "reservations": get_reservations(
                organization=request.organization, user=request.user
            )[:20],
            "counts": get_inventory_counts(
                organization=request.organization, user=request.user
            )[:20],
            "transfers": get_inventory_transfers(
                organization=request.organization, user=request.user
            )[:20],
            "reconciliation": inventory_reconciliation(
                organization=request.organization, user=request.user
            ),
            "expiry_items": [*lots, *serials],
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.INVENTORY_VALUATION_VIEW)
@require_GET
def valuation_workbench(request: HttpRequest) -> HttpResponse:
    events = list(
        InventoryValuationEvent.objects.filter(organization=request.organization)
        .select_related("stock_transaction__unit_of_measure")
        .order_by("-finalized_at")[:100]
    )
    try:
        visible_transaction_ids = set(
            get_organization_stock_transactions(
                user=request.user, organization=request.organization
            )
            .filter(pk__in=[event.stock_transaction_id for event in events])
            .values_list("pk", flat=True)
        )
    except PermissionDenied:
        visible_transaction_ids = set()
    return render(
        request,
        "inventory/valuation_workbench.html",
        {
            "pools": InventoryValuationPool.objects.filter(
                organization=request.organization
            ).select_related("material__unit_of_measure")[:50],
            "events": events,
            "visible_transaction_ids": visible_transaction_ids,
            "envelopes": DownstreamCostSourceEnvelope.objects.filter(
                organization=request.organization
            ).select_related("valuation_event")[:100],
            "reconciliation": (
                valuation_reconciliation(
                    organization=request.organization, actor=request.user
                )
                if has_business_permission(
                    user=request.user,
                    organization=request.organization,
                    permission=BusinessPermissionCode.INVENTORY_VALUATION_RECONCILE,
                )
                else None
            ),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.INVENTORY_RESERVATIONS_MANAGE)
def reservation_create(request: HttpRequest) -> HttpResponse:
    form = ReservationCreateForm(
        request.POST or None, organization=request.organization, user=request.user
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            with transaction.atomic():
                record = create_reservation(
                    organization=request.organization,
                    actor=request.user,
                    reservation_number=data["reservation_number"],
                    project=data["project"],
                    warehouse=data["warehouse"],
                    material=data["material"],
                    quantity=data["quantity"],
                    need_by=data["need_by"],
                )
                activate_reservation(
                    organization=request.organization,
                    actor=request.user,
                    reservation=record,
                    allocations=[
                        TraceAllocationSpec(
                            quantity=data["quantity"],
                            bin=data["bin"],
                            lot=data["lot"],
                            serial=data["serial"],
                        )
                    ],
                )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "رزرو موجودی فعال شد.")
            return redirect("inventory:custody_workbench")
    return render(
        request,
        "inventory/custody_form.html",
        {"form": form, "title": "رزرو موجودی", "submit_label": "ایجاد و فعال‌سازی"},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.INVENTORY_RESERVATIONS_RELEASE)
@require_POST
def reservation_release(request: HttpRequest, reservation_id: str) -> HttpResponse:
    record = (
        get_reservations(organization=request.organization, user=request.user)
        .filter(pk=reservation_id)
        .first()
    )
    if record is None:
        raise Http404("رزرو موجودی یافت نشد.")
    try:
        release_reservation(
            organization=request.organization,
            actor=request.user,
            reservation=record,
            reason=request.POST.get("reason", "آزادسازی عملیاتی"),
        )
        messages.success(request, "مانده رزرو آزاد شد.")
    except (PermissionDenied, ValidationError, ValueError) as exc:
        _service_error(request, exc)
    return redirect("inventory:custody_workbench")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.INVENTORY_COUNTS_PREPARE)
def count_create(request: HttpRequest) -> HttpResponse:
    form = InventoryCountCreateForm(
        request.POST or None, organization=request.organization, user=request.user
    )
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                record = create_inventory_count(
                    organization=request.organization,
                    actor=request.user,
                    **form.cleaned_data,
                )
                freeze_inventory_count(
                    organization=request.organization,
                    actor=request.user,
                    inventory_count=record,
                )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("inventory:count_detail", count_id=record.pk)
    return render(
        request,
        "inventory/custody_form.html",
        {"form": form, "title": "شمارش موجودی", "submit_label": "ایجاد و انجماد دامنه"},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.INVENTORY_COUNTS_VIEW)
def count_detail(request: HttpRequest, count_id: str) -> HttpResponse:
    record = _count(request, count_id)
    can_prepare = record.status in {
        InventoryCountStatus.FROZEN,
        InventoryCountStatus.COUNTED,
    } and has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.INVENTORY_COUNTS_PREPARE,
        project=record.warehouse.project,
    )
    form = None
    if request.method == "POST" and not can_prepare:
        raise PermissionDenied("اجازه ثبت مقدار برای این شمارش را ندارید.")
    if can_prepare:
        form = InventoryCountSubmissionForm(
            request.POST if request.method == "POST" else None,
            lines=list(record.lines.select_related("material", "unit_of_measure")),
        )
    if form is not None and request.method == "POST" and form.is_valid():
        try:
            record_and_submit_inventory_count(
                organization=request.organization,
                actor=request.user,
                inventory_count=record,
                quantities=form.quantities(),
            )
        except (ValidationError, ValueError) as exc:
            form.add_error(
                None, exc.messages if isinstance(exc, ValidationError) else str(exc)
            )
        else:
            messages.success(request, "شمارش برای تأیید مستقل ارسال شد.")
            return redirect("inventory:count_detail", count_id=record.pk)
    return render(
        request,
        "inventory/count_detail.html",
        {"inventory_count": record, "submission_form": form},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.INVENTORY_COUNTS_APPROVE)
@require_POST
def count_approve(request: HttpRequest, count_id: str) -> HttpResponse:
    record = _count(request, count_id)
    try:
        approve_inventory_count(
            organization=request.organization,
            actor=request.user,
            inventory_count=record,
        )
        messages.success(request, "شمارش تأیید شد.")
    except (PermissionDenied, ValidationError, ValueError) as exc:
        _service_error(request, exc)
    return redirect("inventory:count_detail", count_id=record.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.INVENTORY_COUNTS_POST)
@require_POST
def count_post(request: HttpRequest, count_id: str) -> HttpResponse:
    record = _count(request, count_id)
    try:
        post_inventory_count(
            organization=request.organization,
            actor=request.user,
            inventory_count=record,
        )
        messages.success(request, "تعدیل‌های شمارش با پیوند منبع ثبت شد.")
    except (PermissionDenied, ValidationError, ValueError) as exc:
        _service_error(request, exc)
    return redirect("inventory:count_detail", count_id=record.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.INVENTORY_TRANSFERS_PREPARE)
def transfer_create(request: HttpRequest) -> HttpResponse:
    form = InventoryTransferCreateForm(
        request.POST or None, organization=request.organization, user=request.user
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            record = create_inventory_transfer(
                organization=request.organization,
                actor=request.user,
                transfer_number=data["transfer_number"],
                source_warehouse=data["source_warehouse"],
                destination_warehouse=data["destination_warehouse"],
                lines=[
                    TransferLineSpec(
                        material=data["material"],
                        quantity=data["quantity"],
                        source_bin=data["source_bin"],
                        destination_bin=data["destination_bin"],
                        lot=data["lot"],
                        serial=data["serial"],
                    )
                ],
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("inventory:transfer_detail", transfer_id=record.pk)
    return render(
        request,
        "inventory/custody_form.html",
        {"form": form, "title": "انتقال امانی", "submit_label": "ایجاد پیش‌نویس"},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.INVENTORY_TRANSFERS_VIEW)
@require_GET
def transfer_detail(request: HttpRequest, transfer_id: str) -> HttpResponse:
    transfer = _transfer(request, transfer_id)
    membership = get_active_membership(
        user=request.user, organization=request.organization
    )
    tab = request.GET.get("tab")
    from_receiving_tab = (
        tab in RECEIVING_TABS and inventory_transfer_receiving_available(membership)
    )
    breadcrumb_label = breadcrumb_url = ""
    if from_receiving_tab:
        breadcrumb_label = RECEIVING_TABS[tab]
        breadcrumb_url = _receiving_url(tab)
    elif _can_open_custody_summary(membership):
        breadcrumb_label = "کنترل موجودی"
        breadcrumb_url = reverse("inventory:custody_workbench")
    elif has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.WAREHOUSES_VIEW,
        allow_any_scope=True,
    ):
        breadcrumb_label = "انبارها"
        breadcrumb_url = reverse("inventory:warehouse_list")
    return render(
        request,
        "inventory/transfer_detail.html",
        {
            "transfer": transfer,
            "breadcrumb_label": breadcrumb_label,
            "breadcrumb_url": breadcrumb_url,
            "accept_url": reverse(
                "inventory:transfer_accept",
                args=[transfer.pk],
                query={"tab": tab} if from_receiving_tab else None,
            ),
            "can_dispatch": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.INVENTORY_TRANSFERS_DISPATCH,
                project=transfer.source_warehouse.project,
            ),
            "can_accept": (
                transfer.status == InventoryTransferStatus.IN_TRANSIT
                and request.user.pk != transfer.dispatched_by_id
                and has_business_permission(
                    user=request.user,
                    organization=request.organization,
                    permission=BusinessPermissionCode.INVENTORY_TRANSFERS_ACCEPT,
                    project=transfer.destination_warehouse.project,
                )
            ),
            "exception_choices": TransferExceptionCode.choices,
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.INVENTORY_TRANSFERS_DISPATCH)
@require_POST
def transfer_dispatch(request: HttpRequest, transfer_id: str) -> HttpResponse:
    record = _transfer(request, transfer_id, side="source")
    try:
        dispatch_inventory_transfer(
            organization=request.organization,
            actor=request.user,
            inventory_transfer=record,
        )
        messages.success(request, "انتقال از موجودی مبدأ ارسال شد.")
    except (PermissionDenied, ValidationError, ValueError) as exc:
        _service_error(request, exc)
    return redirect("inventory:transfer_detail", transfer_id=record.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.INVENTORY_TRANSFERS_DISPATCH)
@require_POST
def transfer_in_transit(request: HttpRequest, transfer_id: str) -> HttpResponse:
    record = _transfer(request, transfer_id, side="source")
    try:
        mark_transfer_in_transit(
            organization=request.organization,
            actor=request.user,
            inventory_transfer=record,
        )
    except (PermissionDenied, ValidationError, ValueError) as exc:
        _service_error(request, exc)
    return redirect("inventory:transfer_detail", transfer_id=record.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.INVENTORY_TRANSFERS_ACCEPT)
@require_POST
def transfer_accept(request: HttpRequest, transfer_id: str) -> HttpResponse:
    record = _transfer(request, transfer_id, side="destination")
    try:
        outcomes = {}
        for line in record.lines.all():
            outcomes[line.pk] = (
                Decimal(request.POST.get(f"accepted_{line.pk}", "")),
                request.POST.get(f"exception_{line.pk}", TransferExceptionCode.NONE),
                request.POST.get(f"reason_{line.pk}", ""),
            )
        accept_inventory_transfer(
            organization=request.organization,
            actor=request.user,
            inventory_transfer=record,
            outcomes=outcomes,
        )
        messages.success(request, "نتیجه پذیرش انتقال ثبت شد.")
    except (InvalidOperation, PermissionDenied, ValidationError, ValueError) as exc:
        _service_error(request, exc)
    tab = request.GET.get("tab")
    return redirect(
        reverse(
            "inventory:transfer_detail",
            args=[record.pk],
            query={"tab": tab} if tab in RECEIVING_TABS else None,
        )
    )
