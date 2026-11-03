"""Contract-local navigation over existing authorized sources; no domain authority."""

from urllib.parse import urlencode

from django.http import Http404, HttpRequest
from django.urls import reverse

from apps.organizations.form_scoping import normalized_uuid
from core.list_filters import paginate_table, table_pagination_query
from core.product_surface import route_exposed

from .models import Contract


def contract_hub(
    request: HttpRequest, contract: Contract, workspace: dict, baselines
) -> dict:
    """Use only the view's scoped contract and baseline queryset."""
    root = reverse("contracts:detail", args=[contract.pk])
    quantities = root + "?section=quantities"
    selected = request.GET.get("section") == "quantities"
    basis_allowed = baselines is not None and route_exposed("billing:baseline_detail")
    pane = request.GET.get("pane", "items") if selected else "items"
    if pane not in ("items", "basis") or (pane == "basis" and not basis_allowed):
        raise Http404("بخش درخواستی در دسترس نیست.")
    history_route = (
        "billing:progress_list"
        if workspace["receivable"]
        else "billing:payable_measurement_list"
    )
    history_url = (
        reverse(history_route) + "?" + urlencode({"contract": contract.pk})
        if workspace["show_progress"] and route_exposed(history_route)
        else ""
    )
    hub = {
        "quantities": selected,
        "root": root,
        "url": quantities,
        "pane": pane,
        "basis_allowed": basis_allowed,
        "history_url": history_url,
        "baseline": None,
        "versions": [],
    }
    if not selected:
        return hub
    if pane == "basis":
        scoped = baselines.filter(
            organization=request.organization,
            project=contract.project,
            contract=contract,
        ).select_related("approved_by")
        if "baseline" in request.GET:
            values = request.GET.getlist("baseline")
            identifier = normalized_uuid(values[0]) if len(values) == 1 else None
            baseline = scoped.filter(pk=identifier).first() if identifier else None
            if baseline is None:
                raise Http404("نسخه مبنا در محدوده این قرارداد یافت نشد.")
        else:
            baseline = scoped.filter(status="approved").order_by("-version").first()
            baseline = baseline or scoped.order_by("-version").first()
        hub["baseline"] = baseline
        hub["versions"] = scoped.order_by("-version")[:20]
        records = (
            baseline.items.filter(organization=request.organization)
            if baseline
            else None
        )
    else:
        records = contract.items.filter(
            organization=request.organization
        ).select_related("unit_of_measure")
    if records is not None:
        hub["page"] = paginate_table(
            records,
            request,
            sort_fields={},
            default_ordering=("sort_order", "created_at", "pk"),
        )
        hub["pagination_query"] = table_pagination_query(request)
    return hub
