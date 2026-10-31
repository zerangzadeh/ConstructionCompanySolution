import uuid

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

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
    ContractInsuranceClassificationForm,
    ContractualDecisionForm,
    ContractualRecordForm,
    ContractualRevisionForm,
    ContractualWithdrawalForm,
)
from apps.contracts.list_filters import ContractListFilterForm
from apps.contracts.models import (
    ContractDirection,
    ContractStatus,
    ContractTermVersionStatus,
)
from apps.contracts.services import (
    can_manage_contracts,
    create_contract,
    get_organization_contracts,
    select_contract_insurance_classification,
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
from apps.projects.business_hub import filter_project_context
from apps.projects.services import get_organization_projects
from core.business_choices import business_label, contextual_parent, contextual_url
from core.list_filters import (
    apply_table_filters,
    build_filter_bar,
    contextual_list_filters,
    paginate_table,
    table_pagination_query,
)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CONTRACTS_VIEW)
def contract_list(request: HttpRequest) -> HttpResponse:
    from apps.billing.journey_views import journey_breadcrumbs

    contracts = get_organization_contracts(
        user=request.user,
        organization=request.organization,
    )
    if request.GET.get("filter_options") == "project":
        from apps.projects.models import Project

        projects = Project.objects.filter(pk__in=contracts.values("project_id"))
        query = request.GET.get("q", "").strip()[:200]
        if query:
            from django.db.models import Q

            projects = projects.filter(
                Q(name__icontains=query) | Q(code__icontains=query)
            )
        try:
            number = max(1, min(int(request.GET.get("page", 1)), 100000))
        except (TypeError, ValueError):
            number = 1
        rows = list(
            projects.order_by("name", "pk")[(number - 1) * 40 : number * 40 + 1]
        )
        params = request.GET.copy()
        params["page"] = number + 1
        response = JsonResponse(
            {
                "results": [
                    {"value": str(row.pk), "label": business_label(row)}
                    for row in rows[:40]
                ],
                "next": f"{request.path}?{params.urlencode()}"
                if len(rows) > 40
                else None,
            }
        )
        response["Cache-Control"] = "private, no-store"
        return response
    contracts, selected_project = filter_project_context(request, contracts)
    scoped_has_records = contracts.exists()
    filter_form = ContractListFilterForm(
        request.GET, contracts=contracts, project_scoped=selected_project is not None
    )
    valid_filters = filter_form.is_valid()
    contracts = apply_table_filters(
        contracts,
        request,
        text_fields={
            "q": (
                "contract_number",
                "title",
                "project__name",
                "counterparty_name",
                "party__display_name",
            ),
            "number": ("contract_number",),
            "title": ("title", "project__name"),
            "counterparty": ("counterparty_name", "party__display_name"),
        },
        choice_fields={
            "status": ("status", ContractStatus.values),
            "side": ("direction", ContractDirection.values),
        },
    )
    if not valid_filters:
        contracts = contracts.none()
    elif project := filter_form.cleaned_data.get("project"):
        contracts = contracts.filter(project=project)
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
    filter_bar = build_filter_bar(
        request,
        form=filter_form,
        quick_fields=("status", "side", "project"),
        secondary_fields=("number", "title", "counterparty"),
        context={"project_id": str(selected_project.pk)} if selected_project else {},
        result_count=page.paginator.count,
        result_label="قرارداد",
    )
    return render(
        request,
        "contracts/list.html",
        {
            "contracts": page.object_list,
            "scoped_has_records": scoped_has_records,
            **contextual_list_filters(request, keys=("project_id",)),
            "filter_bar": filter_bar,
            "clear_filters_url": filter_bar["clear_url"],
            "selected_project": selected_project,
            "create_url": contextual_url(
                "contracts:create", project=selected_project.pk
            )
            if selected_project
            else reverse("contracts:create"),
            "page_breadcrumbs": journey_breadcrumbs(
                request, "قراردادها", project=selected_project
            ),
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "can_manage_contracts": can_manage_contracts(
                request.user, request.organization
            ),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CONTRACTS_CREATE)
def contract_create(request: HttpRequest) -> HttpResponse:
    if "estimate" in request.GET:
        from apps.estimates.services import get_organization_estimates

        estimate = contextual_parent(
            request,
            "estimate",
            get_organization_estimates(
                user=request.user, organization=request.organization
            ),
        )
        if "estimate" in request.POST and request.POST["estimate"] != str(estimate.pk):
            raise PermissionDenied("زمینه برآورد با درخواست هم‌خوان نیست.")
        if "project" in request.GET and request.GET["project"] != str(
            estimate.project_id
        ):
            raise PermissionDenied("زمینه پروژه با برآورد هم‌خوان نیست.")
        if estimate.contract_id:
            contract = get_object_or_404(
                get_organization_contracts(
                    user=request.user, organization=request.organization
                ),
                pk=estimate.contract_id,
                project_id=estimate.project_id,
            )
            return redirect("contracts:detail", contract_id=contract.pk)
        messages.info(
            request,
            "این برآورد به قراردادی متصل نیست؛ ایجاد و اتصال قرارداد به برآورد از این مسیر پشتیبانی نمی‌شود.",
        )
        return redirect("estimates:detail", estimate_id=estimate.pk)
    if "estimate" in request.POST:
        raise PermissionDenied("ایجاد رابطه برآورد از این مسیر پشتیبانی نمی‌شود.")
    context_project = (
        contextual_parent(
            request,
            "project",
            get_organization_projects(
                user=request.user, organization=request.organization
            ),
        )
        if "project" in request.GET
        else None
    )
    form = ContractForm(
        request.POST if request.method == "POST" else None,
        organization=request.organization,
        membership=get_active_membership(
            user=request.user, organization=request.organization
        ),
        context_project=context_project,
        initial={
            "project": request.GET.get("project")
            or getattr(request.active_project, "pk", None)
        },
    )
    if (
        request.method == "POST"
        and request.POST.get("_refresh_choices") != "1"
        and form.is_valid()
    ):
        data = form.cleaned_data
        try:
            contract = create_contract(
                organization=request.organization,
                project=data["project"],
                actor=request.user,
                contract_number=data["contract_number"],
                title=data["title"],
                counterparty_name=data["party"].display_name,
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
            return redirect("contracts:detail", contract_id=contract.pk)
    from apps.billing.journey_views import journey_breadcrumbs

    return render(
        request,
        "contracts/create.html",
        {
            "form": form,
            "cancel_url": reverse("projects:detail", args=[context_project.pk])
            if context_project
            else reverse("contracts:list"),
            "page_breadcrumbs": journey_breadcrumbs(
                request,
                "قرارداد جدید",
                collection=("قراردادها", "contracts:list"),
                project=context_project,
            ),
        },
    )


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
    terms = list(
        contract.term_versions.filter(organization=request.organization).select_related(
            "insurance_classification"
        )
    )
    can_select = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.CONTRACT_TERMS_MANAGE,
        project=contract.project,
    )
    for term in terms:
        if can_select and term.status == ContractTermVersionStatus.DRAFT:
            term.insurance_form = ContractInsuranceClassificationForm(
                on_date=term.effective_from, prefix=str(term.pk)
            )
    from apps.billing.journey_views import (
        contract_claim_create_allowed,
        journey_breadcrumbs,
    )
    from apps.billing.services import get_progress_claims, get_project_baselines
    from apps.estimates.services import get_organization_estimates

    def permitted(permission):
        return has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=permission,
            project=contract.project,
        )

    related_estimates = (
        get_organization_estimates(
            user=request.user, organization=request.organization
        ).filter(contract=contract)
        if permitted(BusinessPermissionCode.ESTIMATES_VIEW)
        else None
    )
    is_receivable = contract.direction == ContractDirection.RECEIVABLE
    related_claims = (
        get_progress_claims(
            actor=request.user, organization=request.organization
        ).filter(contract=contract)
        if is_receivable and permitted(BusinessPermissionCode.CLAIMS_VIEW)
        else None
    )
    related_baselines = (
        get_project_baselines(
            actor=request.user, organization=request.organization
        ).filter(contract=contract)
        if is_receivable and permitted(BusinessPermissionCode.BASELINES_VIEW)
        else None
    )
    from apps.organizations.form_scoping import normalized_uuid

    context_estimate = None
    if related_estimates is not None and len(request.GET.getlist("estimate")) == 1:
        identifier = normalized_uuid(request.GET["estimate"])
        if identifier:
            context_estimate = related_estimates.filter(
                pk=identifier, project=contract.project
            ).first()
    return render(
        request,
        "contracts/detail.html",
        {
            "contract": contract,
            "project_detail_url": reverse("projects:detail", args=[contract.project_id])
            if has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.PROJECTS_VIEW,
                project=contract.project,
            )
            else "",
            "page_breadcrumbs": journey_breadcrumbs(
                request,
                contract.title,
                collection=None
                if context_estimate is not None
                else ("قراردادها", "contracts:list"),
                project=contract.project,
                estimate=context_estimate,
            ),
            "related_estimates": related_estimates,
            "is_receivable": is_receivable,
            "related_claims": related_claims,
            "related_baselines": related_baselines,
            "estimate_list_url": contextual_url("estimates:list", contract=contract),
            "baseline_list_url": contextual_url(
                "billing:baseline_list", contract=contract
            ),
            "claim_list_url": contextual_url("billing:claim_list", contract=contract),
            "claim_create_url": contextual_url(
                "billing:claim_create", contract=contract
            )
            if contract_claim_create_allowed(request, contract)
            else "",
            "term_versions": terms,
            "can_review_commercial": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.CONTRACTUAL_RECORDS_VIEW,
                project=contract.project,
            ),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CONTRACTS_VIEW)
def commercial_review(request: HttpRequest, contract_id: str) -> HttpResponse:
    """Persian-first advisory P6 timeline, comparison and exception review."""

    try:
        review = get_commercial_review(
            organization=request.organization,
            actor=request.user,
            contract_id=contract_id,
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


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CONTRACT_TERMS_MANAGE)
@require_POST
def contract_term_insurance_select(
    request: HttpRequest, contract_id: str, term_id: str
) -> HttpResponse:
    contract = get_object_or_404(
        get_organization_contracts(
            user=request.user, organization=request.organization
        ),
        pk=contract_id,
    )
    term = get_object_or_404(
        contract.term_versions.filter(organization=request.organization), pk=term_id
    )
    form = ContractInsuranceClassificationForm(
        request.POST, on_date=term.effective_from, prefix=str(term.pk)
    )
    if form.is_valid():
        try:
            select_contract_insurance_classification(
                organization=request.organization,
                actor=request.user,
                term_version=term,
                **form.cleaned_data,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect("contracts:detail", contract_id=contract.pk)
    return render(
        request,
        "contracts/insurance_classification_form.html",
        {"form": form, "contract": contract},
        status=400,
    )
