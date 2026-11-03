"""Thin customer-journey adapters over the existing Inventory services."""

from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.inventory import services
from apps.inventory.journey_forms import (
    MovementFilterForm,
    MovementReversalForm,
    OtherMovementForm,
    ReceiptEntryForm,
    SourceSelectionForm,
)
from apps.inventory.journey_ui import (
    compatible_warehouses,
    inventory_error,
    movement_context,
    receipt_sources,
    source_label,
    warehouse_label,
)
from apps.inventory.models import (
    StockTransactionStatus,
    StockTransactionType,
    Warehouse,
)
from apps.organizations.authorization import get_active_membership
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode as P
from apps.procurement.request_ui import permitted
from apps.projects.models import Project
from core.business_choices import business_label, contextual_parent
from core.list_filters import (
    apply_table_filters,
    build_filter_bar,
    paginate_table,
    table_pagination_query,
)


def _movement(request, transaction_id):
    return get_object_or_404(
        services.get_organization_stock_transactions(
            user=request.user, organization=request.organization
        ).select_related(
            "reversal_of__goods_receipt_item__goods_receipt__project",
            "goods_receipt_item__goods_receipt__project",
            "goods_receipt_item__unit_of_measure",
            "goods_receipt_item__material",
        ),
        pk=transaction_id,
    )


def _masters(request, records):
    return (
        Project.objects.filter(
            organization=request.organization, pk__in=records.values("project_id")
        ).order_by("name"),
        Warehouse.objects.filter(organization=request.organization)
        .filter(
            Q(pk__in=records.values("source_warehouse_id"))
            | Q(pk__in=records.values("destination_warehouse_id"))
        )
        .select_related("project")
        .order_by("name"),
    )


@active_organization_required
@organization_permission_required(P.STOCK_TRANSACTIONS_VIEW)
@never_cache
@require_GET
def transaction_list(request):
    records = services.get_organization_stock_transactions(
        user=request.user, organization=request.organization
    )
    projects, warehouses = _masters(request, records)
    form = MovementFilterForm(request.GET, projects=projects, warehouses=warehouses)
    has_records = records.exists()
    if not form.is_valid():
        records = records.none()
    else:
        if form.cleaned_data["project"]:
            records = records.filter(project=form.cleaned_data["project"])
        if form.cleaned_data["warehouse"]:
            warehouse = form.cleaned_data["warehouse"]
            records = records.filter(
                Q(source_warehouse=warehouse) | Q(destination_warehouse=warehouse)
            )
    records = apply_table_filters(
        records,
        request,
        text_fields={
            "q": (
                "transaction_number",
                "reference",
                "material__name",
                "material__code",
                "project__name",
                "source_warehouse__name",
                "destination_warehouse__name",
                "goods_receipt_item__goods_receipt__receipt_number",
            )
        },
        choice_fields={
            "status": ("status", StockTransactionStatus.values),
            "transaction_type": ("transaction_type", StockTransactionType.values),
        },
        date_fields={"date": "occurred_at__date"},
    )
    sorts = {
        "number": "transaction_number",
        "material": "material__name",
        "project": "project__name",
        "warehouse": ("destination_warehouse__name", "source_warehouse__name"),
        "quantity": "quantity",
        "date": "occurred_at",
        "status": "status",
    }
    page = paginate_table(
        records, request, sort_fields=sorts, default_ordering=("-occurred_at", "pk")
    )
    if request.GET.get("format") == "xlsx":
        from apps.inventory.xlsx_exports import movements_download

        return movements_download(
            page.paginator.object_list, organization=request.organization
        )

    bar = build_filter_bar(
        request,
        form=form,
        quick_fields=("status", "warehouse"),
        secondary_fields=("project", "transaction_type", "date_from", "date_to"),
        result_count=page.paginator.count,
        result_label="گردش انبار",
    )
    return render(
        request,
        "inventory/transaction_list.html",
        {
            "transactions": page.object_list,
            "page_obj": page,
            "filter_bar": bar,
            "scoped_has_records": has_records,
            "pagination_query": table_pagination_query(request),
            "clear_filters_url": bar["clear_url"],
            "create_url": reverse("inventory:transaction_create")
            if request.organization.status == "active"
            and permitted(request, P.STOCK_TRANSACTIONS_CREATE)
            else "",
            "list_sort": {
                "label": {
                    "number": "شماره گردش",
                    "material": "مصالح",
                    "project": "پروژه",
                    "warehouse": "انبار",
                    "quantity": "مقدار",
                    "date": "تاریخ گردش",
                    "status": "وضعیت",
                }.get(request.GET.get("sort"), "جدیدترین گردش"),
                "descending": request.GET.get("direction") == "desc"
                or request.GET.get("sort") not in sorts,
            },
        },
    )


def _source(request):
    records = receipt_sources(request)
    if "goods_receipt_item" in request.GET:
        return contextual_parent(request, "goods_receipt_item", records)
    if request.method == "POST" and request.POST.get("goods_receipt_item"):
        values = request.POST.getlist("goods_receipt_item")
        try:
            if len(values) != 1:
                raise ValueError
            identifier = UUID(values[0])
        except (ValueError, TypeError, AttributeError) as exc:
            raise Http404 from exc
        return get_object_or_404(records, pk=identifier)
    return None


@active_organization_required
@organization_permission_required(P.STOCK_TRANSACTIONS_CREATE)
@never_cache
@require_http_methods(["GET", "POST"])
def transaction_create(request):
    source = _source(request)
    membership = get_active_membership(
        user=request.user, organization=request.organization
    )
    other = source is None and (
        request.GET.get("mode") == "other"
        or (
            request.method == "POST"
            and request.POST.get("transaction_type") not in (None, "", "receipt")
        )
    )
    if source:
        # A consumed occurrence is reached from its existing Detail, never reset.
        if request.method == "GET" and source.stock_transactions.exists():
            raise Http404
        form = ReceiptEntryForm(
            request.POST or None,
            source=source,
            warehouses=compatible_warehouses(request, source),
        )
        template = "inventory/transaction_form.html"
    elif other:
        form = OtherMovementForm(
            request.POST or None,
            organization=request.organization,
            membership=membership,
        )
        template = "inventory/other_movement_form.html"
    else:
        form = SourceSelectionForm(
            request.POST or None, sources=receipt_sources(request, unused=True)
        )
        return render(
            request,
            "inventory/receipt_source.html",
            {"form": form},
            status=400 if request.method == "POST" else 200,
        )
    if request.method == "POST" and form.is_valid():
        data = dict(form.cleaned_data)
        if not source:
            data["unit_of_measure"] = data["material"].unit_of_measure
        try:
            record = services.create_stock_transaction(
                organization=request.organization, actor=request.user, **data
            )
        except (PermissionDenied, ValueError, ValidationError, IntegrityError) as exc:
            form.add_error(
                None,
                inventory_error(exc)
                if not isinstance(exc, IntegrityError)
                else "شماره یا منبع این گردش قبلاً ثبت شده است.",
            )
        else:
            return redirect("inventory:transaction_detail", transaction_id=record.pk)
    return render(
        request,
        template,
        {
            "form": form,
            "source_item": source,
            "can_view_grn": bool(source)
            and permitted(request, P.GOODS_RECEIPTS_VIEW, source.goods_receipt.project),
        },
        status=400 if request.method == "POST" else 200,
    )


@active_organization_required
@organization_permission_required(P.STOCK_TRANSACTIONS_VIEW)
@never_cache
@require_GET
def transaction_detail(request, transaction_id):
    return render(
        request,
        "inventory/transaction_detail.html",
        movement_context(request, _movement(request, transaction_id)),
    )


@active_organization_required
@organization_permission_required(P.STOCK_TRANSACTIONS_POST)
@never_cache
@require_POST
def transaction_post(request, transaction_id):
    record = _movement(request, transaction_id)
    try:
        services.post_stock_transaction(
            organization=request.organization,
            actor=request.user,
            stock_transaction=record,
        )
    except (PermissionDenied, ValueError, ValidationError) as exc:
        record.refresh_from_db()
        return render(
            request,
            "inventory/transaction_detail.html",
            movement_context(request, record, action_error=inventory_error(exc)),
            status=400,
        )
    return redirect("inventory:transaction_detail", transaction_id=record.pk)


@active_organization_required
@organization_permission_required(P.STOCK_TRANSACTIONS_REVERSE)
@never_cache
@require_http_methods(["GET", "POST"])
def transaction_reverse(request, transaction_id):
    record = _movement(request, transaction_id)
    form = MovementReversalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reversal = services.reverse_stock_transaction(
                organization=request.organization,
                actor=request.user,
                stock_transaction=record,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError, ValidationError) as exc:
            form.add_error(None, inventory_error(exc))
        else:
            return redirect("inventory:transaction_detail", transaction_id=reversal.pk)
    return render(
        request,
        "inventory/reversal_form.html",
        movement_context(request, record, form=form),
        status=400 if request.method == "POST" else 200,
    )


@active_organization_required
@never_cache
@require_GET
def journey_choices(request, purpose, field):
    if purpose == "source" and field == "goods_receipt_item":
        records = receipt_sources(request, unused=True)
        columns, label = (
            (
                "goods_receipt__receipt_number",
                "material__name",
                "goods_receipt__project__name",
            ),
            source_label,
        )
    elif purpose == "warehouse" and field == "destination_warehouse":
        source = contextual_parent(
            request, "goods_receipt_item", receipt_sources(request)
        )
        if not source:
            raise Http404
        records, columns, label = (
            compatible_warehouses(request, source),
            ("name", "code"),
            warehouse_label,
        )
    elif purpose == "filter" and field in ("project", "warehouse"):
        projects, warehouses = _masters(
            request,
            services.get_organization_stock_transactions(
                user=request.user, organization=request.organization
            ),
        )
        records, columns, label = (
            (projects, ("name", "code"), business_label)
            if field == "project"
            else (warehouses, ("name", "code"), warehouse_label)
        )
    elif purpose == "other" and field in (
        "source_warehouse",
        "destination_warehouse",
        "project",
        "material",
        "goods_receipt_item",
    ):
        if not permitted(request, P.STOCK_TRANSACTIONS_CREATE):
            raise PermissionDenied
        form = OtherMovementForm(
            organization=request.organization,
            membership=get_active_membership(
                user=request.user, organization=request.organization
            ),
        )
        records = form.fields[field].queryset
        columns = (
            ("goods_receipt__receipt_number", "material__name")
            if field == "goods_receipt_item"
            else ("name", "code")
        )
        label = form.fields[field].label_from_instance
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
            "results": [{"value": str(i.pk), "label": label(i)} for i in page],
            "next": request.path + "?" + params.urlencode()
            if page.has_next()
            else None,
        }
    )
