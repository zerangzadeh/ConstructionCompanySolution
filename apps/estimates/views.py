from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.estimates.forms import EstimateForm, EstimateItemForm
from apps.estimates.models import Estimate
from apps.estimates.services import (
    add_estimate_item,
    approve_estimate,
    create_estimate,
    get_organization_estimates,
)
from apps.organizations.decorators import active_organization_required


@active_organization_required
def estimate_list(request: HttpRequest) -> HttpResponse:
    estimates = get_organization_estimates(
        user=request.user,
        organization=request.organization,
    )
    return render(request, "estimates/list.html", {"estimates": estimates})


@active_organization_required
def estimate_create(request: HttpRequest) -> HttpResponse:
    form = EstimateForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            create_estimate(
                organization=request.organization,
                project=data["project"],
                contract=data["contract"],
                actor=request.user,
                estimate_number=data["estimate_number"],
                title=data["title"],
                notes=data["notes"],
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("estimates:list")
    return render(request, "estimates/create.html", {"form": form})


@active_organization_required
def estimate_detail(request: HttpRequest, estimate_id: str) -> HttpResponse:
    estimate = get_object_or_404(
        Estimate.objects.prefetch_related("items"),
        pk=estimate_id,
        organization=request.organization,
        deleted_at__isnull=True,
        project__deleted_at__isnull=True,
    )
    item_form = EstimateItemForm(request.POST or None)
    if request.method == "POST" and item_form.is_valid():
        data = item_form.cleaned_data
        try:
            add_estimate_item(
                estimate=estimate,
                actor=request.user,
                description=data["description"],
                quantity=data["quantity"],
                unit=data["unit"],
                unit_price=data["unit_price"],
                sort_order=data["sort_order"],
            )
        except (PermissionDenied, ValueError) as exc:
            item_form.add_error(None, str(exc))
        else:
            return redirect(
                "estimates:detail",
                estimate_id=estimate.pk,
            )
    return render(
        request,
        "estimates/detail.html",
        {"estimate": estimate, "item_form": item_form},
    )


@active_organization_required
def estimate_approve(request: HttpRequest, estimate_id: str) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)
    estimate = get_object_or_404(
        Estimate,
        pk=estimate_id,
        organization=request.organization,
        deleted_at__isnull=True,
    )
    try:
        approve_estimate(estimate=estimate, actor=request.user)
    except (PermissionDenied, ValueError) as exc:
        return HttpResponse(str(exc), status=403)
    return redirect("estimates:detail", estimate_id=estimate.pk)
