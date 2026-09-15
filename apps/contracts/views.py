from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.contracts.forms import ContractForm
from apps.contracts.services import (
    can_manage_contracts,
    create_contract,
    get_organization_contracts,
)
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CONTRACTS_VIEW)
def contract_list(request: HttpRequest) -> HttpResponse:
    contracts = get_organization_contracts(
        user=request.user,
        organization=request.organization,
    )
    return render(
        request,
        "contracts/list.html",
        {
            "contracts": contracts,
            "can_manage_contracts": can_manage_contracts(
                request.user, request.organization
            ),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CONTRACTS_CREATE)
def contract_create(request: HttpRequest) -> HttpResponse:
    form = ContractForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            create_contract(
                organization=request.organization,
                project=data["project"],
                actor=request.user,
                contract_number=data["contract_number"],
                title=data["title"],
                counterparty_name=data["counterparty_name"],
                party=data["party"],
                direction=data["direction"] or None,
                contract_type=data["contract_type"] or None,
                status=data["status"],
                contract_value=data["contract_value"],
                signed_at=data["signed_at"],
                start_date=data["start_date"],
                end_date=data["end_date"],
                notes=data["notes"],
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("contracts:list")
    return render(request, "contracts/create.html", {"form": form})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CONTRACTS_VIEW)
def contract_detail(request: HttpRequest, contract_id: str) -> HttpResponse:
    """Render one contract from the active organization only."""

    contract = get_object_or_404(
        get_organization_contracts(
            user=request.user,
            organization=request.organization,
        ).prefetch_related("items__unit_of_measure", "amendments"),
        pk=contract_id,
    )
    return render(request, "contracts/detail.html", {"contract": contract})
