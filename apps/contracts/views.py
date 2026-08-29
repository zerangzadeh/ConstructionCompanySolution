from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.contracts.forms import ContractForm
from apps.contracts.services import create_contract, get_organization_contracts
from apps.organizations.decorators import active_organization_required


@active_organization_required
def contract_list(request: HttpRequest) -> HttpResponse:
    contracts = get_organization_contracts(
        user=request.user,
        organization=request.organization,
    )
    return render(request, "contracts/list.html", {"contracts": contracts})


@active_organization_required
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
