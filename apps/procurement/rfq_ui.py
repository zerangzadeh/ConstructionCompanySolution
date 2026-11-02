"""Bounded, permission-scoped RFQ list and selector presentation."""

from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_GET

from apps.organizations.decorators import active_organization_required
from apps.organizations.models import BusinessPermissionCode as P
from apps.projects.models import Project
from core.list_filters import (
    apply_table_filters,
    build_filter_bar,
    paginate_table,
    table_pagination_query,
)

from .models import RequestForQuotationStatus
from .request_ui import eligible_rfqs, error_text, permitted
from .rfq_forms import RFQFilterForm, RFQLineForm, line_label, pr_label
from .rfq_services import get_organization_rfqs


def preparation_error_text(exc):
    if "کلید یکتا" in str(exc):
        return "امکان ثبت این ارسال وجود ندارد؛ صفحه استعلام را تازه کنید و وضعیت فعلی را بررسی کنید."
    return error_text(exc)


def list_context(request):
    records = get_organization_rfqs(
        user=request.user, organization=request.organization
    )
    projects = Project.objects.filter(
        organization=request.organization, pk__in=records.values("project_id")
    ).order_by("name")
    form = RFQFilterForm(request.GET, projects=projects)
    has_records = records.exists()
    if not form.is_valid():
        records = records.none()
    elif project := form.cleaned_data.get("project"):
        records = records.filter(project=project)
    records = apply_table_filters(
        records,
        request,
        text_fields={
            "q": (
                "rfq_number",
                "title",
                "project__name",
                "purchase_request__request_number",
            )
        },
        choice_fields={"status": ("status", RequestForQuotationStatus.values)},
        date_fields={"closing": "closing_at__date"},
    )
    sorts = {
        "number": "rfq_number",
        "title": "title",
        "project": "project__name",
        "closing": "closing_at",
        "status": "status",
    }
    labels = {
        "number": "شماره استعلام",
        "title": "عنوان",
        "project": "پروژه",
        "closing": "مهلت دریافت",
        "status": "وضعیت",
    }
    page = paginate_table(
        records, request, sort_fields=sorts, default_ordering=("-created_at", "pk")
    )
    bar = build_filter_bar(
        request,
        form=form,
        quick_fields=("status", "project"),
        secondary_fields=("closing_from", "closing_to"),
        result_count=page.paginator.count,
        result_label="استعلام",
    )
    return {
        "rfqs": page.object_list,
        "page_obj": page,
        "pagination_query": table_pagination_query(request),
        "filter_bar": bar,
        "clear_filters_url": bar["clear_url"],
        "scoped_has_records": has_records,
        "create_url": reverse("procurement:rfq_create")
        if request.organization.status == "active" and permitted(request, P.RFQS_CREATE)
        else "",
        "list_sort": {
            "label": labels.get(request.GET.get("sort"), "جدیدترین استعلام"),
            "descending": request.GET.get("direction") == "desc"
            or request.GET.get("sort") not in sorts,
        },
    }


@active_organization_required
@require_GET
def rfq_choices(request, field):
    query = request.GET.get("q", "").strip()
    if field == "purchase_request_id":
        if not permitted(request, P.RFQS_CREATE):
            raise PermissionDenied
        rows = (
            eligible_rfqs(request)
            .filter(
                Q(request_number__icontains=query)
                | Q(title__icontains=query)
                | Q(project__name__icontains=query)
            )
            .order_by("request_number", "pk")
        )
        label = pr_label
    elif field == "project":
        records = get_organization_rfqs(
            user=request.user, organization=request.organization
        )
        rows = (
            Project.objects.filter(
                organization=request.organization, pk__in=records.values("project_id")
            )
            .filter(Q(name__icontains=query) | Q(code__icontains=query))
            .order_by("name", "pk")
        )
        label = lambda row: f"{row.name} · {row.code}"
    elif field == "purchase_request_item_id":
        from core.business_choices import contextual_parent

        records = get_organization_rfqs(
            user=request.user, organization=request.organization
        )
        rfq = contextual_parent(request, "rfq", records)
        if (
            not rfq
            or rfq.status != "draft"
            or not permitted(request, P.RFQS_CHANGE, rfq.project)
        ):
            raise PermissionDenied
        rows = (
            RFQLineForm(rfq=rfq)
            .fields[field]
            .queryset.filter(
                Q(material__name__icontains=query)
                | Q(material__code__icontains=query)
                | Q(description__icontains=query)
            )
            .order_by("created_at", "pk")
        )
        label = line_label
    else:
        raise PermissionDenied
    page = Paginator(rows, 40).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params["page"] = page.next_page_number() if page.has_next() else 1
    response = JsonResponse(
        {
            "results": [{"value": str(row.pk), "label": label(row)} for row in page],
            "next": f"{request.path}?{params.urlencode()}" if page.has_next() else None,
        }
    )
    response["Cache-Control"] = "private, no-store"
    return response
