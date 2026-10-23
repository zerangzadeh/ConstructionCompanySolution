import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.contracts.commercial_review import get_commercial_review
from apps.contracts.contractual_services import (
    create_contractual_record,
    create_contractual_revision,
    decide_contractual_record,
    get_contractual_records,
    submit_contractual_record,
    withdraw_contractual_record,
)
from apps.contracts.forms import (
    ContractForm,
    ContractualDecisionForm,
    ContractualRecordForm,
    ContractualRevisionForm,
    ContractualWithdrawalForm,
)
from apps.contracts.models import ContractStatus
from apps.contracts.services import (
    can_manage_contracts,
    create_contract,
    get_organization_contracts,
)
from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
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
    paginate_table,
    table_pagination_query,
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
    page = paginate_table(
        contracts,
        request,
        sort_fields={
            "number": "contract_number",
            "title": "title",
            "counterparty": "counterparty_name",
            "status": "status",
            "value": "contract_value",
        },
        default_ordering=("title", "pk"),
    )
    return render(
        request,
        "contracts/list.html",
        {
            "contracts": page.object_list,
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
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
    form = ContractForm(
        request.POST or None,
        organization=request.organization,
        membership=get_active_membership(
            user=request.user, organization=request.organization
        ),
    )
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


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CONTRACTS_VIEW)
def commercial_review(request: HttpRequest, contract_id: str) -> HttpResponse:
    """Persian-first advisory P6 timeline, comparison and exception review."""

    try:
        review = get_commercial_review(
            organization=request.organization, actor=request.user, contract_id=contract_id
        )
    except (PermissionDenied, ValidationError):
        raise PermissionDenied("اجازه مشاهده مرور تجاری این قرارداد را ندارید.")
    return render(request, "contracts/commercial_review.html", {"review": review})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CONTRACTUAL_RECORDS_VIEW)
def contractual_record_list(request: HttpRequest) -> HttpResponse:
    records = get_contractual_records(
        actor=request.user, organization=request.organization
    )
    return render(
        request,
        "contracts/contractual_record_list.html",
        {
            "records": records,
            "can_prepare": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.CONTRACTUAL_RECORDS_PREPARE,
                allow_any_scope=True,
            ),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CONTRACTUAL_RECORDS_PREPARE)
def contractual_record_create(request: HttpRequest) -> HttpResponse:
    form = ContractualRecordForm(
        request.POST or None, organization=request.organization
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            record = create_contractual_record(
                organization=request.organization,
                actor=request.user,
                contract=data["contract"],
                kind=data["kind"],
                record_number=data["record_number"],
                title=data["title"],
                description=data["description"],
                notice_reference=data["notice_reference"],
                notice_date=data["notice_date"],
                requested_amount=data["requested_amount"],
                requested_eot_days=data["requested_eot_days"],
                valuation_assumptions=data["valuation_assumptions"],
                cost_impact_assumptions=data["cost_impact_assumptions"],
                schedule_impact_assumptions=data["schedule_impact_assumptions"],
                contract_value_impact_assumptions=data[
                    "contract_value_impact_assumptions"
                ],
                idempotency_key=request.POST.get("idempotency_key")
                or str(uuid.uuid4()),
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("contracts:contractual_detail", record_id=record.pk)
    return render(
        request,
        "contracts/contractual_record_form.html",
        {"form": form, "idempotency_key": str(uuid.uuid4())},
    )


def _contractual_record(request: HttpRequest, record_id: str):
    return get_object_or_404(
        get_contractual_records(
            actor=request.user, organization=request.organization
        ).prefetch_related("evidence_links"),
        pk=record_id,
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CONTRACTUAL_RECORDS_VIEW)
def contractual_record_detail(request: HttpRequest, record_id: str) -> HttpResponse:
    record = _contractual_record(request, record_id)
    return render(
        request,
        "contracts/contractual_record_detail.html",
        {
            "record": record,
            "decision_form": ContractualDecisionForm(),
            "revision_form": ContractualRevisionForm(),
            "withdrawal_form": ContractualWithdrawalForm(),
            "can_submit": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.CONTRACTUAL_RECORDS_SUBMIT,
                project=record.project,
            ),
            "can_approve": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.CONTRACTUAL_RECORDS_APPROVE,
                project=record.project,
            ),
            "can_prepare": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.CONTRACTUAL_RECORDS_PREPARE,
                project=record.project,
            ),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CONTRACTUAL_RECORDS_SUBMIT)
def contractual_record_submit(request: HttpRequest, record_id: str) -> HttpResponse:
    if request.method != "POST":
        raise PermissionDenied("این عملیات فقط با درخواست POST مجاز است.")
    record = _contractual_record(request, record_id)
    submit_contractual_record(
        organization=request.organization, actor=request.user, record=record
    )
    return redirect("contracts:contractual_detail", record_id=record.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CONTRACTUAL_RECORDS_APPROVE)
def contractual_record_decide(request: HttpRequest, record_id: str) -> HttpResponse:
    if request.method != "POST":
        raise PermissionDenied("این عملیات فقط با درخواست POST مجاز است.")
    record = _contractual_record(request, record_id)
    form = ContractualDecisionForm(request.POST)
    if form.is_valid():
        data = form.cleaned_data
        decide_contractual_record(
            organization=request.organization,
            actor=request.user,
            record=record,
            approved=data["outcome"] == "approved",
            reason=data["reason"],
            entitlement_approved=data.get("entitlement_approved"),
            approved_amount=data.get("approved_amount"),
            approved_eot_days=data.get("approved_eot_days"),
            delay_responsibility=data.get("delay_responsibility", ""),
        )
    return redirect("contracts:contractual_detail", record_id=record.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CONTRACTUAL_RECORDS_PREPARE)
def contractual_record_revision(request: HttpRequest, record_id: str) -> HttpResponse:
    if request.method != "POST":
        raise PermissionDenied("این عملیات فقط با درخواست POST مجاز است.")
    record = _contractual_record(request, record_id)
    form = ContractualRevisionForm(request.POST)
    if form.is_valid():
        revised = create_contractual_revision(
            organization=request.organization,
            actor=request.user,
            predecessor=record,
            revision_action=form.cleaned_data["revision_action"],
            reason=form.cleaned_data["reason"],
            title=form.cleaned_data.get("title"),
            description=form.cleaned_data.get("description"),
            idempotency_key=request.POST.get("idempotency_key") or str(uuid.uuid4()),
        )
        return redirect("contracts:contractual_detail", record_id=revised.pk)
    return redirect("contracts:contractual_detail", record_id=record.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CONTRACTUAL_RECORDS_PREPARE)
def contractual_record_withdraw(request: HttpRequest, record_id: str) -> HttpResponse:
    if request.method != "POST":
        raise PermissionDenied("این عملیات فقط با درخواست POST مجاز است.")
    record = _contractual_record(request, record_id)
    form = ContractualWithdrawalForm(request.POST)
    if form.is_valid():
        withdraw_contractual_record(
            organization=request.organization,
            actor=request.user,
            record=record,
            reason=form.cleaned_data["reason"],
        )
    return redirect("contracts:contractual_detail", record_id=record.pk)
