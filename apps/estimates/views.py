from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.contracts.services import get_organization_contracts
from apps.estimates.forms import EstimateForm, EstimateItemForm
from apps.estimates.models import EstimateStatus
from apps.estimates.services import (
    add_estimate_item,
    approve_estimate,
    create_estimate,
    get_organization_estimates,
)
from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
)
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
    require_organization_permission,
)
from apps.organizations.models import BusinessPermissionCode
from apps.projects.business_hub import filter_project_context
from core.business_choices import contextual_url
from core.list_filters import (
    apply_table_filters,
    build_table_filters,
    has_active_table_filters,
    paginate_table,
    table_pagination_query,
)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ESTIMATES_VIEW)
def estimate_list(request: HttpRequest) -> HttpResponse:
    from apps.billing.journey_views import journey_breadcrumbs

    estimates = get_organization_estimates(
        user=request.user,
        organization=request.organization,
    )
    estimates, selected_project = filter_project_context(request, estimates)
    if request.GET.get("contract"):
        from apps.organizations.form_scoping import normalized_uuid

        contract_id = normalized_uuid(request.GET["contract"])
        estimates = (
            estimates.filter(contract_id=contract_id)
            if contract_id
            else estimates.none()
        )
    estimates = apply_table_filters(
        estimates,
        request,
        text_fields={
            "number": ("estimate_number",),
            "title": ("title",),
            "project": ("project__name", "phase__name", "contract__contract_number"),
        },
        choice_fields={"status": ("status", EstimateStatus.values)},
    )
    page = paginate_table(
        estimates,
        request,
        sort_fields={
            "number": "estimate_number",
            "title": "title",
            "project": "project__name",
            "status": "status",
            "amount": "total_amount",
        },
        default_ordering=("title", "pk"),
    )
    return render(
        request,
        "estimates/list.html",
        {
            "estimates": page.object_list,
            "selected_project": selected_project,
            "estimate_create_url": contextual_url(
                "estimates:create", project=selected_project.pk
            )
            if selected_project
            else reverse("estimates:create"),
            "page_breadcrumbs": journey_breadcrumbs("برآوردها"),
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "pagination_rendered": True,
            "filters": build_table_filters(
                request,
                [
                    {"name": "number", "kind": "text", "label": "شماره برآورد"},
                    {"name": "title", "kind": "text", "label": "عنوان"},
                    {"name": "project", "kind": "text", "label": "پروژه یا فاز"},
                    {
                        "name": "status",
                        "kind": "select",
                        "label": "وضعیت",
                        "choices": EstimateStatus.choices,
                    },
                    None,
                    None,
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ESTIMATES_CREATE)
def estimate_create(request: HttpRequest) -> HttpResponse:
    membership = get_active_membership(
        user=request.user, organization=request.organization
    )
    form = EstimateForm(
        request.POST or None,
        organization=request.organization,
        membership=membership,
        active_project=request.active_project,
        initial={
            name: request.GET.get(name)
            for name in ("project", "contract")
            if request.GET.get(name)
        },
    )
    if (
        request.method == "POST"
        and request.POST.get("_refresh_choices") != "1"
        and form.is_valid()
    ):
        data = form.cleaned_data
        try:
            estimate = create_estimate(
                organization=request.organization,
                project=data["project"],
                contract=data["contract"],
                phase=data["phase"],
                actor=request.user,
                estimate_number=data["estimate_number"],
                title=data["title"],
                notes=data["notes"],
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("estimates:detail", estimate_id=estimate.pk)
    from apps.billing.journey_views import journey_breadcrumbs

    return render(
        request,
        "estimates/create.html",
        {
            "form": form,
            "page_breadcrumbs": journey_breadcrumbs(
                "برآورد جدید", collection=("برآوردها", "estimates:list")
            ),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ESTIMATES_VIEW)
def estimate_detail(request: HttpRequest, estimate_id: str) -> HttpResponse:
    from apps.billing.journey_views import journey_breadcrumbs

    if request.method == "POST":
        require_organization_permission(
            request,
            BusinessPermissionCode.ESTIMATE_ITEMS_ADD,
            "اجازه افزودن ردیف برآورد را ندارید.",
        )
    estimate = get_object_or_404(
        get_organization_estimates(
            user=request.user,
            organization=request.organization,
        ),
        pk=estimate_id,
    )
    if request.method == "POST" and estimate.status != EstimateStatus.DRAFT:
        messages.error(request, "برآورد تأییدشده قابل تغییر نیست.")
        return redirect("estimates:detail", estimate_id=estimate.pk)

    item_form = EstimateItemForm(
        request.POST or None, organization=request.organization
    )
    if (
        request.method == "POST"
        and request.POST.get("_refresh_choices") != "1"
        and item_form.is_valid()
    ):
        data = item_form.cleaned_data
        try:
            add_estimate_item(
                estimate=estimate,
                actor=request.user,
                description=data["description"],
                quantity=data["quantity"],
                unit=data["unit_of_measure"].symbol,
                unit_of_measure=data["unit_of_measure"],
                unit_price=data["unit_price"],
                sort_order=data["sort_order"],
            )
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
            return redirect("estimates:detail", estimate_id=estimate.pk)
        else:
            return redirect(
                "estimates:detail",
                estimate_id=estimate.pk,
            )
    return render(
        request,
        "estimates/detail.html",
        {
            "estimate": estimate,
            "page_breadcrumbs": journey_breadcrumbs(
                estimate.title, collection=("برآوردها", "estimates:list")
            ),
            "item_form": item_form,
            "related_contract_url": (
                reverse("contracts:detail", args=[estimate.contract_id])
                if estimate.contract_id
                and has_business_permission(
                    user=request.user,
                    organization=request.organization,
                    permission=BusinessPermissionCode.CONTRACTS_VIEW,
                    allow_any_scope=True,
                )
                and get_organization_contracts(
                    user=request.user, organization=request.organization
                )
                .filter(pk=estimate.contract_id)
                .exists()
                else ""
            ),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ESTIMATES_APPROVE)
def estimate_approve(request: HttpRequest, estimate_id: str) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)
    estimate = get_object_or_404(
        get_organization_estimates(
            user=request.user,
            organization=request.organization,
        ),
        pk=estimate_id,
    )
    try:
        approve_estimate(estimate=estimate, actor=request.user)
    except (PermissionDenied, ValueError) as exc:
        return HttpResponse(str(exc), status=403)
    return redirect("estimates:detail", estimate_id=estimate.pk)
