from collections import defaultdict
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.inventory.forms import ReversalForm, StockTransactionForm, WarehouseForm
from apps.inventory.models import (
    StockTransaction,
    StockTransactionStatus,
    StockTransactionType,
    Warehouse,
)
from apps.inventory.services import (
    archive_warehouse,
    create_stock_transaction,
    create_warehouse,
    get_organization_stock_transactions,
    get_organization_warehouses,
    post_stock_transaction,
    reverse_stock_transaction,
)
from apps.inventory.workflow import (
    request_stock_transaction_posting,
    request_stock_transaction_reversal,
)
from apps.organizations.authorization import get_active_membership
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode
from core.list_filters import (
    apply_table_filters,
    build_table_filters,
    has_active_table_filters,
    paginate_table,
    table_pagination_query,
)


def _warehouse(request: HttpRequest, warehouse_id: str) -> Warehouse | None:
    return (
        get_organization_warehouses(
            user=request.user, organization=request.organization
        )
        .filter(pk=warehouse_id)
        .first()
    )


def _transaction(request: HttpRequest, transaction_id: str) -> StockTransaction | None:
    return (
        get_organization_stock_transactions(
            user=request.user, organization=request.organization
        )
        .filter(pk=transaction_id)
        .first()
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.WAREHOUSES_VIEW)
@require_GET
def warehouse_list(request: HttpRequest) -> HttpResponse:
    warehouses = get_organization_warehouses(
        user=request.user, organization=request.organization
    )
    warehouses = apply_table_filters(
        warehouses,
        request,
        text_fields={
            "warehouse": ("code", "name"),
            "project": ("project__name",),
            "location": ("location",),
        },
    )
    page = paginate_table(
        warehouses,
        request,
        sort_fields={
            "warehouse": ("name", "code"),
            "project": "project__name",
            "location": "location",
            "status": "is_active",
        },
        default_ordering=("name", "pk"),
    )
    return render(
        request,
        "inventory/warehouse_list.html",
        {
            "warehouses": page.object_list,
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "filters": build_table_filters(
                request,
                [
                    {"name": "warehouse", "kind": "text", "label": "کد و نام"},
                    {"name": "project", "kind": "text", "label": "پروژه"},
                    {"name": "location", "kind": "text", "label": "محل"},
                    None,
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.WAREHOUSES_CREATE)
def warehouse_create(request: HttpRequest) -> HttpResponse:
    form = WarehouseForm(
        request.POST or None,
        organization=request.organization,
        membership=get_active_membership(
            user=request.user, organization=request.organization
        ),
    )
    if request.method == "POST" and form.is_valid():
        try:
            warehouse = create_warehouse(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("inventory:warehouse_detail", warehouse_id=warehouse.pk)
    return render(request, "inventory/warehouse_form.html", {"form": form})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.WAREHOUSES_VIEW)
@require_GET
def warehouse_detail(request: HttpRequest, warehouse_id: str) -> HttpResponse:
    warehouse = _warehouse(request, warehouse_id)
    if warehouse is None:
        return HttpResponseNotFound("انبار یافت نشد.")
    transactions = get_organization_stock_transactions(
        user=request.user, organization=request.organization
    ).filter(Q(source_warehouse=warehouse) | Q(destination_warehouse=warehouse))
    balances: dict[object, Decimal] = defaultdict(lambda: Decimal("0.0000"))
    materials: dict[object, object] = {}
    for record in transactions.filter(
        status__in=[StockTransactionStatus.POSTED, StockTransactionStatus.REVERSED]
    ):
        materials[record.material_id] = record.material
        if record.destination_warehouse_id == warehouse.pk:
            balances[record.material_id] += record.quantity
        if record.source_warehouse_id == warehouse.pk:
            balances[record.material_id] -= record.quantity
    balance_rows = [
        {"material": materials[material_id], "quantity": quantity}
        for material_id, quantity in balances.items()
        if quantity != Decimal("0.0000")
    ]
    return render(
        request,
        "inventory/warehouse_detail.html",
        {
            "warehouse": warehouse,
            "transactions": transactions[:20],
            "balance_rows": balance_rows,
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.WAREHOUSES_ARCHIVE)
@require_POST
def warehouse_archive(request: HttpRequest, warehouse_id: str) -> HttpResponse:
    warehouse = _warehouse(request, warehouse_id)
    if warehouse is None:
        return HttpResponseNotFound("انبار یافت نشد.")
    try:
        archive_warehouse(
            organization=request.organization, actor=request.user, warehouse=warehouse
        )
    except (PermissionDenied, ValueError) as exc:
        messages.error(request, str(exc))
        return redirect("inventory:warehouse_detail", warehouse_id=warehouse.pk)
    messages.success(request, "انبار بایگانی شد.")
    return redirect("inventory:warehouse_list")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.STOCK_TRANSACTIONS_VIEW)
@require_GET
def transaction_list(request: HttpRequest) -> HttpResponse:
    transactions = get_organization_stock_transactions(
        user=request.user, organization=request.organization
    )
    transactions = apply_table_filters(
        transactions,
        request,
        text_fields={
            "number": ("transaction_number",),
            "material": ("material__code", "material__name"),
            "warehouse": ("source_warehouse__name", "destination_warehouse__name"),
        },
        choice_fields={
            "transaction_type": ("transaction_type", StockTransactionType.values),
            "status": ("status", StockTransactionStatus.values),
        },
        date_fields={"occurred_at": "occurred_at__date"},
    )
    page = paginate_table(
        transactions,
        request,
        sort_fields={
            "number": "transaction_number",
            "material": "material__name",
            "warehouse": "source_warehouse__name",
            "type": "transaction_type",
            "quantity": "quantity",
            "occurred_at": "occurred_at",
            "status": "status",
        },
        default_ordering=("-occurred_at", "-created_at", "pk"),
    )
    return render(
        request,
        "inventory/transaction_list.html",
        {
            "transactions": page.object_list,
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "filters": build_table_filters(
                request,
                [
                    {"name": "number", "kind": "text", "label": "شماره"},
                    {
                        "name": "transaction_type",
                        "kind": "select",
                        "label": "نوع",
                        "choices": StockTransactionType.choices,
                    },
                    {"name": "material", "kind": "text", "label": "مصالح"},
                    {"name": "warehouse", "kind": "text", "label": "مبدأ یا مقصد"},
                    None,
                    {
                        "name": "status",
                        "kind": "select",
                        "label": "وضعیت",
                        "choices": StockTransactionStatus.choices,
                    },
                    None,
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.STOCK_TRANSACTIONS_VIEW)
@require_GET
def transaction_detail(request: HttpRequest, transaction_id: str) -> HttpResponse:
    record = _transaction(request, transaction_id)
    if record is None:
        return HttpResponseNotFound("تراکنش انبار یافت نشد.")
    return render(request, "inventory/transaction_detail.html", {"transaction": record})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.STOCK_TRANSACTIONS_CREATE)
def transaction_create(request: HttpRequest) -> HttpResponse:
    form = StockTransactionForm(
        request.POST or None,
        organization=request.organization,
        membership=get_active_membership(
            user=request.user, organization=request.organization
        ),
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            create_stock_transaction(
                organization=request.organization,
                actor=request.user,
                unit_of_measure=data["material"].unit_of_measure,
                **data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("inventory:transaction_list")
    return render(request, "inventory/transaction_form.html", {"form": form})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.STOCK_TRANSACTIONS_POST)
@require_POST
def transaction_post(request: HttpRequest, transaction_id: str) -> HttpResponse:
    record = _transaction(request, transaction_id)
    if record is None:
        return HttpResponseNotFound("تراکنش انبار یافت نشد.")
    try:
        post_stock_transaction(
            organization=request.organization,
            actor=request.user,
            stock_transaction=record,
        )
        messages.success(request, "تراکنش انبار ثبت نهایی شد.")
    except (PermissionDenied, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("inventory:transaction_list")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.STOCK_TRANSACTIONS_POST)
@require_POST
def transaction_request_posting(
    request: HttpRequest, transaction_id: str
) -> HttpResponse:
    record = _transaction(request, transaction_id)
    if record is None:
        return HttpResponseNotFound("تراکنش انبار یافت نشد.")
    try:
        request_stock_transaction_posting(
            organization=request.organization,
            actor=request.user,
            stock_transaction=record,
        )
        messages.success(request, "درخواست ثبت نهایی برای تخصیص به کارتابل ارسال شد.")
    except (PermissionDenied, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("inventory:transaction_detail", transaction_id=record.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.STOCK_TRANSACTIONS_REVERSE)
def transaction_reverse(request: HttpRequest, transaction_id: str) -> HttpResponse:
    record = _transaction(request, transaction_id)
    if record is None:
        return HttpResponseNotFound("تراکنش انبار یافت نشد.")
    form = ReversalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reverse_stock_transaction(
                organization=request.organization,
                actor=request.user,
                stock_transaction=record,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "تراکنش برگشت داده شد.")
            return redirect("inventory:transaction_list")
    return render(
        request, "inventory/reversal_form.html", {"form": form, "transaction": record}
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.STOCK_TRANSACTIONS_REVERSE)
@require_POST
def transaction_request_reversal(
    request: HttpRequest, transaction_id: str
) -> HttpResponse:
    record = _transaction(request, transaction_id)
    if record is None:
        return HttpResponseNotFound("تراکنش انبار یافت نشد.")
    try:
        request_stock_transaction_reversal(
            organization=request.organization,
            actor=request.user,
            stock_transaction=record,
        )
        messages.success(request, "درخواست برگشت برای تخصیص به کارتابل ارسال شد.")
    except (PermissionDenied, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("inventory:transaction_detail", transaction_id=record.pk)
