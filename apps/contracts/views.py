from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.contracts.forms import ContractForm
from apps.contracts.models import ContractStatus
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
from core.list_filters import (
    apply_table_filters,
    build_table_filters,
    has_active_table_filters,
)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CONTRACTS_VIEW)
def contract_list(request: HttpRequest) -> HttpResponse:
    contracts = get_organization_contracts(
        user=request.user,
        organization=request.organization,
    )
    contracts = apply_table_filters(
        contracts,
        request,
        text_fields={
            "number": ("contract_number",),
            "title": ("title", "project__name"),
            "counterparty": ("counterparty_name", "party__display_name"),
        },
        choice_fields={"status": ("status", ContractStatus.values)},
    )
    return render(
        request,
        "contracts/list.html",
        {
            "contracts": contracts,
            "can_manage_contracts": can_manage_contracts(
                request.user, request.organization
            ),
            "filters": build_table_filters(
                request,
                [
                    {"name": "number", "kind": "text", "label": "شماره قرارداد"},
                    {"name": "title", "kind": "text", "label": "عنوان و پروژه"},
                    {"name": "counterparty", "kind": "text", "label": "طرف قرارداد"},
                    {
                        "name": "status",
                        "kind": "select",
                        "label": "وضعیت",
                        "choices": ContractStatus.choices,
                    },
                    None,
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
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
