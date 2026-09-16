from __future__ import annotations

from collections.abc import Callable

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.organizations.decorators import (
    active_organization_required,
    require_organization_permission,
)
from apps.organizations.models import BusinessPermissionCode

from .runtime import (
    WorkflowConflict,
    claim_work_item,
    complete_work_item,
    release_work_item,
)
from .workbench import build_workbench, decorate_work_items, get_workbench_item


@active_organization_required
def workbench(request: HttpRequest) -> HttpResponse:
    require_organization_permission(request, BusinessPermissionCode.WORK_ITEMS_VIEW)
    data = build_workbench(
        actor=request.user, organization=request.organization, params=request.GET
    )
    paginator = Paginator(data.queryset, 25)
    page = paginator.get_page(request.GET.get("page"))
    page.object_list = list(page.object_list)
    decorate_work_items(
        page.object_list,
        membership=data.membership,
        permission_codes=data.permission_codes,
    )
    query = request.GET.copy()
    query.pop("page", None)
    return render(
        request,
        "workflows/workbench.html",
        {
            "page_obj": page,
            "work_items": page.object_list,
            "counts": data.counts,
            "filter_choices": data.filters,
            "selected_filters": request.GET,
            "pagination_query": query.urlencode(),
            "is_rtl": True,
            "responsive_table": True,
        },
    )


def _operation_key(request: HttpRequest) -> str:
    value = request.POST.get("idempotency_key", "").strip()
    if not value or len(value) > 128:
        raise ValidationError("شناسه معتبر عملیات الزامی است.")
    return value


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
                response = HttpResponse("")
                response["HX-Trigger"] = "workbenchUpdated"
                return response
            return render(request, "workflows/_work_item_row.html", {"item": item})
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
