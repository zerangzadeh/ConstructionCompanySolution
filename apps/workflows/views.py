from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, QueryDict
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.organizations.decorators import (
    active_organization_required,
    require_organization_permission,
)
from apps.organizations.models import BusinessPermissionCode
from apps.workflows.models import WorkItem
from core.list_filters import table_pagination_query
from core.product_surface import personal_source_exposed, workflow_subject_exposed

from .personal_workspaces import build_manager_workspace, build_my_requests
from .registry import registry
from .runtime import (
    WorkflowConflict,
    claim_work_item,
    complete_work_item,
    release_work_item,
)
from .workbench import build_workbench, decorate_work_items, get_workbench_item


@active_organization_required
@require_GET
def my_requests(request: HttpRequest) -> HttpResponse:
    rows = build_my_requests(actor=request.user, organization=request.organization)
    rows = tuple(row for row in rows if personal_source_exposed(row.source_type))
    return render(request, "workflows/my_requests.html", {"request_rows": rows})


@active_organization_required
@require_GET
def manager_workspace(request: HttpRequest) -> HttpResponse:
    data = build_manager_workspace(
        actor=request.user, organization=request.organization
    )
    rows = tuple(row for row in data.rows if personal_source_exposed(row.source_type))
    data = replace(
        data,
        rows=rows,
        status_counts=tuple(
            (status, label, sum(row.status == status for row in rows))
            for status, label, _ in data.status_counts
            if any(row.status == status for row in rows)
        ),
    )
    return render(request, "workflows/manager_workspace.html", {"manager": data})


@active_organization_required
def workbench(request: HttpRequest) -> HttpResponse:
    require_organization_permission(request, BusinessPermissionCode.WORK_ITEMS_VIEW)
    data = build_workbench(
        actor=request.user,
        organization=request.organization,
        params=request.GET,
        exposed_subject_types=frozenset(
            adapter.subject_type
            for adapter in registry.subject_adapters.values()
            if workflow_subject_exposed(adapter.subject_type, adapter.detail_url_name)
        ),
    )
    paginator = Paginator(data.queryset, 25)
    page = paginator.get_page(request.GET.get("page"))
    page.object_list = list(page.object_list)
    decorate_work_items(
        page.object_list,
        membership=data.membership,
        permission_codes=data.permission_codes,
    )
    pagination_query = table_pagination_query(request)
    query = QueryDict(pagination_query, mutable=True)
    all_positions_query = query.copy()
    all_positions_query.pop("position", None)
    all_positions_query.pop("routing", None)
    role_permission_query = query.copy()
    role_permission_query.pop("position", None)
    role_permission_query["routing"] = "role_permission"
    position_links = []
    for position in data.counts.positions:
        position_query = query.copy()
        position_query.pop("routing", None)
        position_query["position"] = str(position["id"])
        position_links.append(
            {
                **position,
                "url": f"{request.path}?{position_query.urlencode()}",
            }
        )
    return render(
        request,
        "workflows/workbench.html",
        {
            "page_obj": page,
            "work_items": page.object_list,
            "counts": data.counts,
            "filter_choices": data.filters,
            "selected_filters": request.GET,
            "pagination_query": pagination_query,
            "all_positions_url": f"{request.path}?{all_positions_query.urlencode()}"
            if all_positions_query
            else request.path,
            "role_permission_url": (
                f"{request.path}?{role_permission_query.urlencode()}"
            ),
            "position_links": position_links,
            "pagination_rendered": True,
            "is_rtl": True,
            "responsive_table": True,
        },
    )


def _operation_key(request: HttpRequest) -> str:
    value = request.POST.get("idempotency_key", "").strip()
    if not value or len(value) > 128:
        raise ValidationError("شناسه معتبر عملیات الزامی است.")
    return value


def _require_work_item_surface(request: HttpRequest, work_item_id: object) -> None:
    # Read only tenant-scoped classification. Original runtime authorization,
    # object scope and candidacy checks still govern the mutation transaction;
    # exposure does not add a second permission requirement for visible work.
    item = (
        WorkItem.objects.filter(pk=work_item_id, organization=request.organization)
        .select_related("instance")
        .first()
    )
    if item is None:
        raise PermissionDenied("این صفحه در دسترس نیست.")
    adapter = next(
        (
            value
            for value in registry.subject_adapters.values()
            if value.subject_type == item.instance.subject_type
        ),
        None,
    )
    if adapter is None or not workflow_subject_exposed(
        adapter.subject_type, adapter.detail_url_name
    ):
        raise PermissionDenied("این صفحه در دسترس نیست.")


def _action_response(
    request: HttpRequest,
    work_item_id: object,
    operation: Callable[[], object],
    *,
    success_message: str,
) -> HttpResponse:
    is_htmx = request.headers.get("HX-Request") == "true"
    try:
        operation()
        messages.success(request, success_message)
        if is_htmx:
            try:
                item, _, _ = get_workbench_item(
                    actor=request.user,
                    organization=request.organization,
                    work_item_id=work_item_id,
                )
            except PermissionDenied:
                response = HttpResponse()
                response["HX-Redirect"] = reverse("workflows:workbench")
                return response
            response = render(request, "workflows/_work_item_row.html", {"item": item})
            response["HX-Trigger"] = "workbenchActionSucceeded"
            return response
    except (PermissionDenied, ValidationError, WorkflowConflict, ValueError) as exc:
        if is_htmx:
            response = render(
                request,
                "workflows/_action_error.html",
                {"action_error": str(exc)},
                status=409,
            )
            response["HX-Retarget"] = "#workbench-feedback"
            response["HX-Reswap"] = "innerHTML"
            return response
        messages.error(request, str(exc))
    return redirect("workflows:workbench")


@active_organization_required
@require_POST
def work_item_claim(request: HttpRequest, work_item_id: object) -> HttpResponse:
    def operation() -> object:
        require_organization_permission(
            request, BusinessPermissionCode.WORK_ITEMS_CLAIM
        )
        _require_work_item_surface(request, work_item_id)
        return claim_work_item(
            actor=request.user,
            organization=request.organization,
            work_item_id=work_item_id,
            idempotency_key=_operation_key(request),
        )

    return _action_response(
        request, work_item_id, operation, success_message="کار با موفقیت اخذ شد."
    )


@active_organization_required
@require_POST
def work_item_release(request: HttpRequest, work_item_id: object) -> HttpResponse:
    def operation() -> object:
        require_organization_permission(
            request, BusinessPermissionCode.WORK_ITEMS_CLAIM
        )
        _require_work_item_surface(request, work_item_id)
        return release_work_item(
            actor=request.user,
            organization=request.organization,
            work_item_id=work_item_id,
            idempotency_key=_operation_key(request),
            reason=request.POST.get("reason", ""),
        )

    return _action_response(
        request, work_item_id, operation, success_message="کار آزاد شد."
    )


@active_organization_required
@require_POST
def work_item_action(request: HttpRequest, work_item_id: object) -> HttpResponse:
    def operation() -> object:
        require_organization_permission(request, BusinessPermissionCode.WORK_ITEMS_ACT)
        _require_work_item_surface(request, work_item_id)
        if WorkItem.objects.filter(
            pk=work_item_id,
            organization=request.organization,
            instance__subject_type="safety.safety_incident",
        ).exists():
            raise PermissionDenied("اقدام ایمنی باید از فرم کامل حادثه ثبت شود.")
        outcome = request.POST.get("outcome", "").strip()
        if not outcome or len(outcome) > 100:
            raise ValidationError("نتیجه اقدام معتبر نیست.")
        return complete_work_item(
            actor=request.user,
            organization=request.organization,
            work_item_id=work_item_id,
            outcome=outcome,
            idempotency_key=_operation_key(request),
            command_context={"reason": request.POST.get("reason", "").strip()},
        )

    return _action_response(
        request, work_item_id, operation, success_message="اقدام با موفقیت ثبت شد."
    )
