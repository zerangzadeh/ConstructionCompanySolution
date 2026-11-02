"""Read-only PO source projections and presentation selectors; no posting authority."""

from decimal import Decimal
from urllib.parse import urlencode

from django.db.models import Sum
from django.urls import reverse

from apps.organizations.authorization import require_business_permission, scope_queryset
from apps.organizations.models import BusinessPermissionCode as P
from apps.procurement import models as m
from apps.procurement.request_ui import permitted

ACTIVE_CONSUMPTION = ("draft", "issued", "completed")


def scoped_awards(request):
    membership = require_business_permission(
        user=request.user,
        organization=request.organization,
        permission=P.PURCHASE_ORDERS_CREATE,
        allow_any_scope=True,
        message="مجوز ایجاد سفارش خرید از انتخاب نهایی را ندارید.",
    )
    return scope_queryset(
        m.SourcingAward.objects.filter(
            organization=request.organization,
            comparison__commercial_scope__rfq_version__rfq__project__deleted_at__isnull=True,
        ),
        membership=membership,
        project_lookup="comparison__commercial_scope__rfq_version__rfq__project_id",
    ).select_related(
        "comparison__commercial_scope__rfq_version__rfq__project",
        "comparison__commercial_scope__rfq_version__rfq__purchase_request",
        "finalized_by",
    )


def allocation_rows(award):
    """Mirror the existing consumer's readiness, never allocate or alter quantities."""
    allocations = list(
        award.allocations.select_related(
            "quote_revision__envelope__supplier",
            "comparison_input__assertion__commercial_scope__rfq_version_line__material",
            "comparison_input__assertion__commercial_scope__unit_of_measure",
        )
    )
    consumed = dict(
        m.PurchaseOrderItem.objects.filter(
            organization=award.organization,
            source_award_allocation__in=allocations,
            purchase_order__status__in=ACTIVE_CONSUMPTION,
        )
        .values("source_award_allocation_id")
        .annotate(total=Sum("quantity"))
        .values_list("source_award_allocation_id", "total")
    )
    current = award.outcome == "awarded" and not award.superseded_by.exists()
    rows = []
    for allocation in allocations:
        assertion = allocation.comparison_input.assertion
        scope = assertion.commercial_scope
        supplier = allocation.quote_revision.envelope.supplier
        used = consumed.get(allocation.pk, Decimal(0))
        reason = ""
        if not current:
            reason = "این تصمیم نهایی برنده و حاکم نیست."
        elif (
            supplier.archived_at
            or not supplier.roles.filter(
                organization=award.organization, role="supplier", is_active=True
            ).exists()
        ):
            reason = "نقش تأمین‌کننده فعال نیست."
        elif scope.rfq_version_line_id is None:
            reason = "این بسته نگاشت ردیف صریح برای سفارش خرید ندارد."
        elif assertion.unit_price is None:
            reason = "قیمت واحد صریح منبع برای سفارش لازم است."
        elif assertion.unit_price != assertion.unit_price.quantize(Decimal("0.01")):
            reason = "دقت قیمت منبع با دقت مجاز سفارش سازگار نیست."
        elif used:
            reason = "این تخصیص قبلاً در سفارش فعال مصرف شده است؛ مصرف دوباره یا جزء دیگری از آن مجاز نیست."
        rows.append(
            {
                "allocation": allocation,
                "supplier": supplier,
                "material": scope.rfq_version_line.material
                if scope.rfq_version_line_id
                else None,
                "scope": scope,
                "quantity": allocation.quantity,
                "consumed": used,
                "remaining": allocation.quantity - used,
                "unit_price": assertion.unit_price,
                "currency": assertion.currency,
                "reason": reason,
                "eligible": not reason,
            }
        )
    return rows


def award_groups(request, award):
    groups = {}
    for row in allocation_rows(award):
        group = groups.setdefault(
            row["supplier"].pk,
            {"supplier": row["supplier"], "rows": [], "can_create": False},
        )
        group["rows"].append(row)
        group["can_create"] |= row["eligible"]
    rfq = award.comparison.commercial_scope.rfq_version.rfq
    authorized = request.organization.status == "active" and permitted(
        request, P.PURCHASE_ORDERS_CREATE, rfq.project
    )
    for group in groups.values():
        group["url"] = (
            reverse("procurement:order_from_award", args=[award.pk])
            + "?"
            + urlencode({"supplier": str(group["supplier"].pk)})
            if authorized and group["can_create"]
            else ""
        )
        group["orders"] = []
        if permitted(request, P.PURCHASE_ORDERS_VIEW, rfq.project):
            from .services import get_organization_purchase_orders

            group["orders"] = get_organization_purchase_orders(
                user=request.user, organization=request.organization
            ).filter(source_award=award, supplier=group["supplier"])
    return list(groups.values())


def source_label(award):
    version = award.comparison.commercial_scope.rfq_version
    return f"{version.rfq.rfq_number} · نسخه {version.version_number} · تصمیم {award.finalized_at:%Y-%m-%d}"


def order_context(request, order, **overrides):
    active = (
        request.organization.status == "active" and order.project.deleted_at is None
    )
    can = lambda code: active and permitted(request, code, order.project)
    versions = list(
        order.versions.select_related("created_by")
        .prefetch_related(
            "lines__material",
            "lines__unit_of_measure",
            "lines__award_allocation__quote_revision__envelope__supplier",
        )
        .order_by("-version_number")
    )
    current = next((v for v in versions if v.pk == order.current_version_id), None)
    items = list(
        order.items.select_related(
            "material",
            "unit_of_measure",
            "purchase_request_item",
            "source_award_allocation__quote_revision__envelope__supplier",
        ).order_by("sort_order", "created_at")
    )
    display = (
        list(current.lines.all()) if current and order.status != "draft" else items
    )
    for line in display:
        line.ui_allocation = (
            line.award_allocation
            if current and order.status != "draft"
            else line.source_award_allocation
        )
    source = order.source_award
    rfq = source.comparison.commercial_scope.rfq_version.rfq if source else None
    return {
        "purchase_order": order,
        "order_items": items,
        "issued_lines": list(current.lines.all()) if current else [],
        "display_lines": display,
        "versions": versions,
        "source_award": source,
        "source_rfq": rfq,
        "can_view_request": bool(order.purchase_request_id)
        and permitted(request, P.PURCHASE_REQUESTS_VIEW, order.project),
        "can_view_rfq": bool(rfq) and permitted(request, P.RFQS_VIEW, order.project),
        "can_add_item": order.status == "draft"
        and source is None
        and can(P.PURCHASE_ORDER_ITEMS_ADD),
        "can_issue": order.status == "draft"
        and bool(items)
        and can(P.PURCHASE_ORDERS_ISSUE),
        "can_cancel": order.status in ("draft", "issued")
        and can(P.PURCHASE_ORDERS_CANCEL)
        and not order.goods_receipts.filter(status="posted").exists(),
        "can_receive": order.status == "issued"
        and current is not None
        and can(P.GOODS_RECEIPTS_CREATE),
        "receipt_url": reverse("procurement:receipt_create")
        + "?"
        + urlencode({"purchase_order": str(order.pk)}),
        "receipt_history": order.goods_receipts.filter(
            organization=request.organization
        ).select_related("purchase_order_version")
        if permitted(request, P.GOODS_RECEIPTS_VIEW, order.project)
        else [],
        **overrides,
    }
