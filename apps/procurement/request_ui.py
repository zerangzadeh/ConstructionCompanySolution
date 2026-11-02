"""Read-only presentation of existing PR authority and continuation prerequisites."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, QuerySet
from django.http import HttpRequest, JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_GET

from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
    membership_has_permission,
)
from apps.organizations.decorators import active_organization_required
from apps.organizations.models import BusinessPermissionCode as P
from apps.workflows.runtime import (
    _active_candidate,
    _assert_live_runtime,
    _candidate_delegation_is_current,
    _check_sod,
    _matching_transition,
)
from core.business_choices import business_label, contextual_url
from core.product_surface import route_exposed

from .forms import PurchaseRequestForm, ReasonForm, RequestItemForm
from .models import PurchaseRequest
from .request_forms import RequestLineForm, material_label


def permitted(request: HttpRequest, code: str, project=None) -> bool:
    return has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=code,
        project=project,
        allow_any_scope=project is None,
    )


def eligible_rfqs(request: HttpRequest) -> QuerySet[PurchaseRequest]:
    """Use the same source/project authority as create_rfq, without a new grant."""
    records = PurchaseRequest.objects.filter(
        organization=request.organization,
        status="approved",
        project__deleted_at__isnull=True,
    ).select_related("project")
    from apps.organizations.authorization import scope_queryset

    membership = get_active_membership(
        user=request.user, organization=request.organization
    )
    if not membership_has_permission(membership, P.RFQS_CREATE):
        return records.none()
    return scope_queryset(records, membership=membership, project_lookup="project_id")


def error_text(exc: Exception) -> str:
    if isinstance(exc, PermissionDenied):
        return "در حال حاضر امکان انجام این اقدام برای شما وجود ندارد؛ مسئول بررسی یا دسترسی را پیگیری کنید."
    if isinstance(exc, ValidationError):
        return "امکان انجام این مرحله فراهم نیست؛ تنظیمات بررسی درخواست را با مسئول شرکت پیگیری کنید."
    return str(exc)


@transaction.atomic
def detail_context(
    request: HttpRequest, record: PurchaseRequest, **overrides: object
) -> dict[str, object]:
    from .workflow import _actor_item

    membership = get_active_membership(
        user=request.user, organization=request.organization
    )
    active = (
        request.organization.status == "active" and record.project.deleted_at is None
    )

    def allowed(code):
        return active and permitted(request, code, record.project)

    owned = record.created_by_id == request.user.pk or membership_has_permission(
        membership,
        P.PURCHASE_REQUESTS_APPROVE,
    )
    decisions = {"approve": False, "reject": False}
    if record.status == "submitted" and allowed(P.WORK_ITEMS_ACT):
        try:
            item = _actor_item(
                organization=request.organization,
                purchase_request=record,
                membership=membership,
            )
            step = item.step_instance.step_definition
            _assert_live_runtime(
                instance=item.instance, step=item.step_instance, item=item
            )
            _check_sod(instance=item.instance, step=step, membership_id=membership.pk)
            candidate = _active_candidate(work_item=item, membership=membership)
            valid_candidate = candidate and _candidate_delegation_is_current(
                candidate=candidate,
                item=item,
                instance=item.instance,
                membership=membership,
            )
            can_take = item.current_assignee_id in (None, membership.pk) and (
                item.status == "claimed" or allowed(P.WORK_ITEMS_CLAIM)
            )
            if item.status == "open" and (
                required := item.required_permission or step.required_permission
            ):
                can_take = can_take and membership_has_permission(membership, required)
            for action, outcome, permission in (
                ("approve", "approved", P.PURCHASE_REQUESTS_APPROVE),
                ("reject", "rejected", P.PURCHASE_REQUESTS_REJECT),
            ):
                try:
                    transition = _matching_transition(
                        step=step,
                        outcome=outcome,
                        subject_context={
                            "project_id": str(record.project_id),
                            "status": record.status,
                            "created_by_id": str(record.created_by_id),
                        },
                    )
                    required = (
                        transition.required_permission
                        or item.required_permission
                        or step.required_permission
                    )
                    decisions[action] = bool(
                        valid_candidate
                        and can_take
                        and allowed(permission)
                        and (
                            not required
                            or membership_has_permission(membership, required)
                        )
                    )
                except (PermissionDenied, ValidationError):
                    pass
        except (PermissionDenied, ValidationError):
            pass
    can_rfq = bool(
        record.status == "approved"
        and active
        and route_exposed("procurement:rfq_create")
        and allowed(P.RFQS_CREATE)
    )
    context = {
        "purchase_request": record,
        "item_form": RequestLineForm(organization=request.organization),
        "approve_form": ReasonForm(prefix="approve"),
        "reject_form": ReasonForm(prefix="reject"),
        "cancel_form": ReasonForm(prefix="cancel"),
        "can_add_item": record.status == "draft"
        and owned
        and allowed(P.PURCHASE_REQUEST_ITEMS_ADD),
        "can_submit": record.status == "draft"
        and owned
        and allowed(P.PURCHASE_REQUESTS_SUBMIT),
        "can_cancel": record.status in ("draft", "submitted")
        and owned
        and allowed(P.PURCHASE_REQUESTS_CANCEL),
        "can_approve": decisions["approve"],
        "can_reject": decisions["reject"],
        "rfq_create_url": contextual_url(
            "procurement:rfq_create", purchase_request=record.pk
        )
        if can_rfq
        else "",
        "rfq_explanation": "برای ادامه استعلام، دسترسی ایجاد استعلام در این پروژه و فعال بودن شرکت و پروژه لازم است.",
        "list_url": contextual_url(
            "procurement:request_list", project_id=record.project_id
        ),
        "project_url": reverse("projects:detail", args=[record.project_id])
        if permitted(request, P.PROJECTS_VIEW, record.project)
        else "",
        "state_description": {
            "draft": "ابتدا اقلام موردنیاز را اضافه کنید، سپس درخواست را برای بررسی بفرستید.",
            "submitted": "درخواست برای بررسی ارسال شده است. تصمیم را مسئول مجاز بررسی ثبت می‌کند.",
            "approved": "درخواست تأیید شده است؛ مرحله بعد ایجاد استعلام خرید است.",
            "rejected": "درخواست رد شده است. دلیل تصمیم را در همین صفحه ببینید.",
            "cancelled": "درخواست لغو شده است و امکان ادامه خرید ندارد.",
        }[record.status],
    }
    # Existing sourced records remain discoverable after the Create handoff.
    if permitted(request, P.RFQS_VIEW, record.project):
        from .rfq_services import get_organization_rfqs

        context["related_rfqs"] = get_organization_rfqs(
            user=request.user, organization=request.organization
        ).filter(purchase_request=record)
    context.update(overrides)
    return context


@active_organization_required
@require_GET
def request_choices(request: HttpRequest, field: str) -> JsonResponse:
    membership = get_active_membership(
        user=request.user, organization=request.organization
    )
    if field == "project":
        if not any(
            permitted(request, p)
            for p in (P.PURCHASE_REQUESTS_CREATE, P.PURCHASE_REQUESTS_VIEW)
        ):
            raise PermissionDenied
        rows = (
            PurchaseRequestForm(
                organization=request.organization, membership=membership
            )
            .fields["project"]
            .queryset
        )
        query = Q(name__icontains=request.GET.get("q", "")) | Q(
            code__icontains=request.GET.get("q", "")
        )
        label = business_label
    elif field == "material":
        if not permitted(request, P.PURCHASE_REQUEST_ITEMS_ADD):
            raise PermissionDenied
        rows = (
            RequestItemForm(organization=request.organization)
            .fields["material"]
            .queryset
        )
        query = Q(name__icontains=request.GET.get("q", "")) | Q(
            code__icontains=request.GET.get("q", "")
        )
        label = material_label
    else:
        raise PermissionDenied
    from django.core.paginator import Paginator

    page = Paginator(rows.filter(query), 40).get_page(request.GET.get("page"))
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
