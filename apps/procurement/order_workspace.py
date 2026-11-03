"""PO journey adapters; existing Procurement services remain mutation authority."""

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
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
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization
from apps.parties.models import BusinessParty
from apps.procurement import models as m
from apps.procurement.buyer_ui import presentation_error
from apps.procurement.forms import ReasonForm
from apps.procurement.order_forms import (
    AwardOrderForm,
    OrderCreateForm,
    OrderFilterForm,
    OrderLineForm,
    request_label,
)
from apps.procurement.order_ui import (
    allocation_rows,
    award_groups,
    order_context,
    scoped_awards,
)
from apps.procurement.request_ui import permitted
from apps.procurement.services import (
    add_purchase_order_item,
    cancel_purchase_order,
    create_purchase_order_from_award,
    get_organization_purchase_order,
    get_organization_purchase_orders,
    issue_purchase_order,
)
from apps.projects.models import Project
from core.business_choices import business_label, contextual_parent
from core.identifiers import canonicalize_upper_identifier
from core.list_filters import (
    apply_table_filters,
    build_filter_bar,
    paginate_table,
    table_pagination_query,
)


def _order(request, order_id):
    try:
        return get_organization_purchase_order(
            user=request.user,
            organization=request.organization,
            purchase_order_id=order_id,
        )
    except PermissionDenied as exc:
        raise Http404("سفارش خرید مجاز یافت نشد.") from exc


def _detail_context(request, order, **kwargs):
    return order_context(
        request,
        order,
        item_form=OrderLineForm(
            organization=request.organization, purchase_order=order
        ),
        reason_form=ReasonForm(),
        **kwargs,
    )


@active_organization_required
@organization_permission_required(P.PURCHASE_ORDERS_VIEW)
@never_cache
@require_GET
def order_list(request):
    records = get_organization_purchase_orders(
        user=request.user, organization=request.organization
    ).select_related("source_award__comparison__commercial_scope__rfq_version__rfq")
    projects = Project.objects.filter(
        organization=request.organization, pk__in=records.values("project_id")
    ).order_by("name")
    suppliers = BusinessParty.objects.filter(
        organization=request.organization, pk__in=records.values("supplier_id")
    ).order_by("display_name")
    form = OrderFilterForm(request.GET, projects=projects, suppliers=suppliers)
    has_records = records.exists()
    if not form.is_valid():
        records = records.none()
    else:
        for field in ("project", "supplier"):
            if form.cleaned_data[field]:
                records = records.filter(**{field: form.cleaned_data[field]})
        if form.cleaned_data["lineage"] == "sourced":
            records = records.filter(source_award__isnull=False)
        elif form.cleaned_data["lineage"] == "direct":
            records = records.filter(source_award__isnull=True)
    records = apply_table_filters(
        records,
        request,
        text_fields={
            "q": (
                "order_number",
                "supplier__display_name",
                "project__name",
                "source_award__comparison__commercial_scope__rfq_version__rfq__rfq_number",
            )
        },
        choice_fields={"status": ("status", m.PurchaseOrderStatus.values)},
        date_fields={"date": "order_date"},
    )
    sorts = {
        "number": "order_number",
        "supplier": "supplier__display_name",
        "project": "project__name",
        "date": "order_date",
        "status": "status",
    }
    page = paginate_table(
        records, request, sort_fields=sorts, default_ordering=("-created_at", "pk")
    )
    if request.GET.get("format") == "xlsx":
        from apps.procurement.xlsx_exports import procurement_download

        return procurement_download(
            "order", page.paginator.object_list, organization=request.organization
        )

    bar = build_filter_bar(
        request,
        form=form,
        quick_fields=("status", "project"),
        secondary_fields=("supplier", "lineage", "date_from", "date_to"),
        result_count=page.paginator.count,
        result_label="سفارش خرید",
    )
    labels = {
        "number": "شماره سفارش",
        "supplier": "تأمین‌کننده",
        "project": "پروژه",
        "date": "تاریخ سفارش",
        "status": "وضعیت",
    }
    return render(
        request,
        "procurement/order_list.html",
        {
            "orders": page.object_list,
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "filter_bar": bar,
            "scoped_has_records": has_records,
            "clear_filters_url": bar["clear_url"],
            "create_url": reverse("procurement:order_create")
            if request.organization.status == "active"
            and permitted(request, P.PURCHASE_ORDERS_CREATE)
            else "",
            "list_sort": {
                "label": labels.get(request.GET.get("sort"), "جدیدترین سفارش"),
                "descending": request.GET.get("direction") == "desc"
                or request.GET.get("sort") not in sorts,
            },
        },
    )


@active_organization_required
@organization_permission_required(P.PURCHASE_ORDERS_VIEW)
@never_cache
@require_GET
def order_detail(request, order_id):
    order = _order(request, order_id)
    if request.GET.get("format") == "print":
        from core.printing import print_response

        from .print_outputs import order_document

        return print_response(request, order_document(order))
    return render(
        request, "procurement/order_detail.html", _detail_context(request, order)
    )


@active_organization_required
@organization_permission_required(P.PURCHASE_ORDER_ITEMS_ADD)
@never_cache
@require_POST
def order_item_add(request, order_id):
    order = _order(request, order_id)
    form = OrderLineForm(
        request.POST, organization=request.organization, purchase_order=order
    )
    context = _detail_context(request, order)
    context["item_form"] = form
    if order.source_award_id:
        context["action_error"] = (
            "اقلام این سفارش از تخصیص مصوب دریافت شده‌اند؛ افزودن ردیف مستقیم به سفارش منتخب مجاز نیست."
        )
    elif form.is_valid():
        try:
            add_purchase_order_item(
                organization=request.organization,
                actor=request.user,
                purchase_order=order,
                unit_of_measure=form.cleaned_data["material"].unit_of_measure,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError, ValidationError) as exc:
            form.add_error(None, presentation_error(exc))
        else:
            return redirect("procurement:order_detail", order_id=order.pk)
    return render(request, "procurement/order_detail.html", context, status=400)


@active_organization_required
@organization_permission_required(P.PURCHASE_ORDERS_ISSUE)
@never_cache
@require_POST
def order_issue(request, order_id):
    order = _order(request, order_id)
    try:
        issue_purchase_order(
            organization=request.organization, actor=request.user, purchase_order=order
        )
    except (PermissionDenied, ValueError, ValidationError) as exc:
        context = _detail_context(request, order, action_error=presentation_error(exc))
        return render(request, "procurement/order_detail.html", context, status=400)
    return redirect("procurement:order_detail", order_id=order.pk)


@active_organization_required
@organization_permission_required(P.PURCHASE_ORDERS_CANCEL)
@never_cache
@require_POST
def order_cancel(request, order_id):
    order = _order(request, order_id)
    form = ReasonForm(request.POST)
    if form.is_valid():
        try:
            cancel_purchase_order(
                organization=request.organization,
                actor=request.user,
                purchase_order=order,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError, ValidationError) as exc:
            form.add_error(None, presentation_error(exc))
        else:
            return redirect("procurement:order_detail", order_id=order.pk)
    context = _detail_context(request, order)
    context.update(reason_form=form, open_cancel=True)
    return render(request, "procurement/order_detail.html", context, status=400)


def _source(request, award_id):
    try:
        award = scoped_awards(request).get(pk=award_id)
    except (m.SourcingAward.DoesNotExist, ValidationError, ValueError) as exc:
        raise Http404("انتخاب مجاز یافت نشد.") from exc
    rfq = award.comparison.commercial_scope.rfq_version.rfq
    require_business_permission(
        user=request.user,
        organization=request.organization,
        permission=P.PURCHASE_ORDERS_CREATE,
        project=rfq.project,
        message="مجوز ایجاد سفارش خرید برای این پروژه را ندارید.",
    )
    return award, rfq


def _replay(request, award, supplier):
    if request.method != "POST":
        return None
    number = canonicalize_upper_identifier(request.POST.get("order_number", ""))
    return m.PurchaseOrder.objects.filter(
        organization=request.organization,
        source_award=award,
        supplier=supplier,
        order_number=number,
    ).first()


def _exact_replay(order, data):
    if order is None:
        return
    expected = {
        str(pk)
        for pk in order.items.values_list("source_award_allocation_id", flat=True)
    }
    if (
        expected != {str(a.pk) for a in data["allocations"]}
        or order.order_date != data["order_date"]
        or order.expected_delivery_date != data["expected_delivery_date"]
        or order.notes != data["notes"].strip()
    ):
        raise ValueError(
            "این شماره سفارش قبلاً با اطلاعات دیگری ثبت شده است؛ سفارش موجود را بررسی کنید."
        )


@active_organization_required
@organization_permission_required(P.PURCHASE_ORDERS_CREATE)
@never_cache
@require_http_methods(["GET", "POST"])
def order_from_award(request, award_id):
    award, rfq = _source(request, award_id)
    groups = award_groups(request, award)
    supplier = None
    if "supplier" in request.GET:
        try:
            values = request.GET.getlist("supplier")
            if len(values) != 1:
                raise ValueError
            supplier = next(
                g["supplier"] for g in groups if str(g["supplier"].pk) == values[0]
            )
        except (StopIteration, ValueError):
            raise Http404("تأمین‌کننده این انتخاب یافت نشد.") from None
    elif len(groups) == 1:
        supplier = groups[0]["supplier"]
    rows = [
        row
        for row in allocation_rows(award)
        if supplier and row["supplier"].pk == supplier.pk
    ]
    form = (
        AwardOrderForm(
            request.POST if request.method == "POST" else None,
            award=award,
            supplier=supplier,
            rows=rows,
            replay=_replay(request, award, supplier),
        )
        if supplier
        else None
    )
    source_error = ""
    if award.outcome != "awarded" or award.superseded_by.exists():
        source_error = "این تصمیم نهایی برای ایجاد سفارش خرید قابل مصرف نیست."
    if request.method == "POST" and form and form.is_valid() and not source_error:
        try:
            with transaction.atomic():
                org = Organization.objects.select_for_update().get(
                    pk=request.organization.pk, status="active"
                )
                project = Project.objects.get(
                    pk=rfq.project_id, organization=org, deleted_at__isnull=True
                )
                locked = m.SourcingAward.objects.select_for_update().get(
                    pk=award.pk, organization=org
                )
                require_business_permission(
                    user=request.user,
                    organization=org,
                    permission=P.PURCHASE_ORDERS_CREATE,
                    project=project,
                    message="اختیار ایجاد سفارش برای این پروژه تغییر کرده است.",
                )
                current_rows = [
                    row
                    for row in allocation_rows(locked)
                    if row["supplier"].pk == supplier.pk
                ]
                replay = _replay(request, locked, supplier)
                locked_form = AwardOrderForm(
                    request.POST,
                    award=locked,
                    supplier=supplier,
                    rows=current_rows,
                    replay=replay,
                )
                if not locked_form.is_valid():
                    raise ValueError(
                        "تخصیص مجاز تغییر کرده است؛ وضعیت منبع را دوباره بررسی کنید."
                    )
                data = locked_form.cleaned_data
                _exact_replay(replay, data)
                # The existing service owns locks, lineage and whole-allocation conservation.
                order = create_purchase_order_from_award(
                    organization=org,
                    actor=request.user,
                    award=locked,
                    allocation_ids=[str(a.pk) for a in data["allocations"]],
                    order_number=data["order_number"],
                    order_date=data["order_date"],
                    expected_delivery_date=data["expected_delivery_date"],
                    notes=data["notes"],
                )
        except (
            PermissionDenied,
            ValueError,
            ValidationError,
            ObjectDoesNotExist,
            IntegrityError,
        ) as exc:
            form.add_error(
                None,
                presentation_error(exc)
                if not isinstance(exc, (ObjectDoesNotExist, IntegrityError))
                else "منبع مجاز برای این سفارش یافت نشد.",
            )
        else:
            return redirect("procurement:order_detail", order_id=order.pk)
    return render(
        request,
        "procurement/order_source.html",
        {
            "award": award,
            "source_rfq": rfq,
            "supplier": supplier,
            "groups": groups,
            "allocation_rows": rows,
            "form": form,
            "source_error": source_error,
            "source_ready": any(row["eligible"] for row in rows),
            "can_view_rfq": permitted(request, P.RFQS_VIEW, rfq.project),
        },
        status=400 if request.method == "POST" else 200,
    )


@active_organization_required
@require_GET
def order_choices(request, purpose, field):
    org = request.organization
    if purpose == "create":
        if not permitted(request, P.PURCHASE_ORDERS_CREATE):
            raise PermissionDenied
        form = OrderCreateForm(
            organization=org,
            membership=get_active_membership(user=request.user, organization=org),
        )
        if field not in ("project", "supplier", "purchase_request"):
            raise PermissionDenied
        records = form.fields[field].queryset
        if field == "purchase_request" and request.GET.get("project"):
            parent = contextual_parent(
                request, "project", form.fields["project"].queryset
            )
            records = records.filter(project=parent)
        columns = {
            "project": ("name", "code"),
            "supplier": ("display_name",),
            "purchase_request": ("request_number", "title", "project__name"),
        }[field]
        label = request_label if field == "purchase_request" else business_label
    elif purpose == "filter":
        orders = get_organization_purchase_orders(user=request.user, organization=org)
        if field == "project":
            records = Project.objects.filter(
                organization=org, pk__in=orders.values("project_id")
            )
            columns = ("name", "code")
        elif field == "supplier":
            records = BusinessParty.objects.filter(
                organization=org, pk__in=orders.values("supplier_id")
            )
            columns = ("display_name",)
        else:
            raise PermissionDenied
        label = business_label
    elif purpose == "line":
        orders = get_organization_purchase_orders(user=request.user, organization=org)
        order = contextual_parent(request, "order", orders)
        if (
            not order
            or order.source_award_id
            or order.status != "draft"
            or not permitted(request, P.PURCHASE_ORDER_ITEMS_ADD, order.project)
        ):
            raise PermissionDenied
        form = OrderLineForm(organization=org, purchase_order=order)
        if field not in ("material", "purchase_request_item"):
            raise PermissionDenied
        records = form.fields[field].queryset
        label = form.fields[field].label_from_instance
        columns = (
            ("name", "code")
            if field == "material"
            else ("material__name", "material__code")
        )
    else:
        raise PermissionDenied
    query = Q()
    for column in columns:
        query |= Q(**{column + "__icontains": request.GET.get("q", "").strip()})
    records = records.filter(query).order_by("pk")
    page = Paginator(records, 40).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params["page"] = page.next_page_number() if page.has_next() else 1
    response = JsonResponse(
        {
            "results": [{"value": str(row.pk), "label": label(row)} for row in page],
            "next": request.path + "?" + params.urlencode()
            if page.has_next()
            else None,
        }
    )
    response["Cache-Control"] = "private, no-store"
    return response
