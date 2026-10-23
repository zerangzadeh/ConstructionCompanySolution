from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.inventory.models import (
    DownstreamCostSourceEnvelope,
    InventoryLot,
    InventorySerial,
    InventoryValuationEvent,
    InventoryValuationPool,
    TraceQualityStatus,
    TransferExceptionCode,
)
from apps.inventory.p8_forms import (
    InventoryCountCreateForm,
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
    mark_transfer_in_transit,
    post_inventory_count,
    record_counted_quantity,
    release_reservation,
    submit_inventory_count,
    valuation_reconciliation,
)
from apps.organizations.authorization import has_business_permission
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode


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


def _transfer(request: HttpRequest, transfer_id: str):
    record = (
        get_inventory_transfers(organization=request.organization, user=request.user)
        .filter(pk=transfer_id)
        .first()
    )
    if record is None:
        raise Http404("انتقال موجودی یافت نشد.")
    return record


@active_organization_required
@organization_permission_required(BusinessPermissionCode.INVENTORY_RECONCILIATIONS_VIEW)
@organization_permission_required(BusinessPermissionCode.INVENTORY_RESERVATIONS_VIEW)
@organization_permission_required(BusinessPermissionCode.INVENTORY_COUNTS_VIEW)
@organization_permission_required(BusinessPermissionCode.INVENTORY_TRANSFERS_VIEW)
@require_GET
def custody_workbench(request: HttpRequest) -> HttpResponse:
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
    return render(
        request,
        "inventory/valuation_workbench.html",
        {
            "pools": InventoryValuationPool.objects.filter(
                organization=request.organization
            ).select_related("material")[:50],
            "events": InventoryValuationEvent.objects.filter(
                organization=request.organization
            )
            .select_related("stock_transaction")
            .order_by("-finalized_at")[:100],
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
    if request.method == "POST":
        try:
            for line in record.lines.select_related("material", "unit_of_measure"):
                raw = request.POST.get(f"quantity_{line.pk}")
                if raw is None:
                    raise ValueError("مقدار همه خطوط شمارش الزامی است.")
                record_counted_quantity(
                    organization=request.organization,
                    actor=request.user,
                    line=line,
                    counted_quantity=Decimal(raw),
                    variance_reason=request.POST.get(f"reason_{line.pk}", ""),
                )
            submit_inventory_count(
                organization=request.organization,
                actor=request.user,
                inventory_count=record,
            )
            messages.success(request, "شمارش برای تأیید مستقل ارسال شد.")
            return redirect("inventory:count_detail", count_id=record.pk)
        except (InvalidOperation, PermissionDenied, ValidationError, ValueError) as exc:
            _service_error(request, exc)
            record.refresh_from_db()
    return render(request, "inventory/count_detail.html", {"inventory_count": record})


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
    return render(
        request,
        "inventory/transfer_detail.html",
        {
            "transfer": _transfer(request, transfer_id),
            "exception_choices": TransferExceptionCode.choices,
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.INVENTORY_TRANSFERS_DISPATCH)
@require_POST
def transfer_dispatch(request: HttpRequest, transfer_id: str) -> HttpResponse:
    record = _transfer(request, transfer_id)
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
    record = _transfer(request, transfer_id)
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
    record = _transfer(request, transfer_id)
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
    return redirect("inventory:transfer_detail", transfer_id=record.pk)
