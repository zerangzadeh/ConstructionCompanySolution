from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
)
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode
from core.business_choices import contextual_url
from core.list_filters import (
    apply_table_filters,
    contextual_list_filters,
    paginate_table,
    table_pagination_query,
)
from core.product_surface import capability_exposed, route_exposed

from .commercial_services import (
    commercial_exposure,
    create_compliance_evidence,
    create_compliance_evidence_revision,
    create_guarantee,
    create_guarantee_revision,
    create_retention_release,
    create_retention_release_correction,
    decide_compliance_evidence,
    decide_guarantee,
    decide_retention_release,
    expire_due_compliance_evidence,
    expire_due_guarantees,
    get_compliance_evidence,
    get_guarantees,
    get_retention_releases,
    organization_localdate,
    submit_compliance_evidence,
    submit_guarantee,
    submit_retention_release,
)
from .forms import (
    ClaimSettlementAllocationForm,
    ComplianceEvidenceForm,
    ComplianceEvidenceRevisionForm,
    ContractorComplianceAssessmentForm,
    GuaranteeForm,
    GuaranteeRevisionForm,
    PayableBackChargeForm,
    PayableCertificateCorrectionForm,
    PayableCertificateForm,
    PayableMeasurementForm,
    RetentionReleaseCorrectionForm,
    RetentionReleaseForm,
    StatutorySubmissionForm,
    SubmissionResolutionForm,
    TaxpayerInvoiceForm,
)
from .journey_forms import ClaimCorrectionForm, ClaimDecisionForm
from .journey_views import (
    breadcrumb_contract,
    claim_create_allowed,
    contract_claim_create_allowed,
    journey_breadcrumbs,
)
from .models import (
    ContractComplianceEvidence,
    ContractGuarantee,
    ContractorComplianceAssessment,
    GuaranteeExposureSide,
    GuaranteeType,
    PayableCertificate,
    PayableMeasurement,
    ProgressClaim,
    ProgressRecord,
    ProjectBaseline,
    RetentionRelease,
    RetentionReleaseCorrectionKind,
    StatutorySubmissionEvidence,
    TaxpayerInvoice,
)
from .payable_services import (
    add_payable_back_charge,
    approve_payable_certificate,
    create_payable_certificate,
    create_payable_certificate_correction,
    create_payable_measurement,
    decide_payable_measurement,
    get_payable_certificates,
    get_payable_measurements,
    return_payable_certificate,
    submit_payable_certificate,
    submit_payable_measurement,
)
from .services import (
    allocate_progress_claim_settlement,
    claim_settlements_queryset,
    get_progress_claim_settlement_summary,
    get_progress_claims,
    get_progress_records,
    get_project_baselines,
    reject_progress_record,
    request_progress_verification,
    verify_progress_record,
)
from .statutory_services import (
    create_contractor_compliance_assessment,
    create_taxpayer_invoice,
    decide_contractor_assessment,
    decide_taxpayer_invoice,
    get_contractor_assessments,
    get_taxpayer_invoices,
    reconcile_contractor_assessment,
    reconcile_taxpayer_invoice,
    record_statutory_submission,
    resolve_submission_error,
    submit_contractor_assessment,
    submit_taxpayer_invoice,
)


def _record(request: HttpRequest, record_id: str):
    try:
        return get_progress_records(
            actor=request.user, organization=request.organization
        ).get(pk=record_id)
    except (PermissionDenied, ProgressRecord.DoesNotExist, ValidationError):
        return None


def _baseline(request: HttpRequest, baseline_id: str):
    try:
        return get_project_baselines(
            actor=request.user, organization=request.organization
        ).get(pk=baseline_id)
    except (PermissionDenied, ProjectBaseline.DoesNotExist, ValidationError):
        return None


def _claim(request: HttpRequest, claim_id: str):
    try:
        return get_progress_claims(
            actor=request.user, organization=request.organization
        ).get(pk=claim_id)
    except (PermissionDenied, ProgressClaim.DoesNotExist, ValidationError):
        return None


def _commercial_record(request: HttpRequest, record_id: str, kind: str):
    try:
        if kind == "guarantee":
            return get_guarantees(
                actor=request.user, organization=request.organization
            ).get(pk=record_id)
        if kind == "compliance":
            return get_compliance_evidence(
                actor=request.user, organization=request.organization
            ).get(pk=record_id)
        return get_retention_releases(
            actor=request.user, organization=request.organization
        ).get(pk=record_id)
    except (
        PermissionDenied,
        ValidationError,
        ContractGuarantee.DoesNotExist,
        ContractComplianceEvidence.DoesNotExist,
        RetentionRelease.DoesNotExist,
    ):
        return None


def _payable_certificate(request: HttpRequest, certificate_id: str):
    try:
        return get_payable_certificates(
            actor=request.user, organization=request.organization
        ).get(pk=certificate_id)
    except (PermissionDenied, PayableCertificate.DoesNotExist, ValidationError):
        return None


def _payable_measurement(request: HttpRequest, measurement_id: str):
    try:
        return get_payable_measurements(
            actor=request.user, organization=request.organization
        ).get(pk=measurement_id)
    except (PermissionDenied, PayableMeasurement.DoesNotExist, ValidationError):
        return None


@active_organization_required
@organization_permission_required(BusinessPermissionCode.BASELINES_VIEW)
@require_GET
def baseline_list(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "billing/baseline_list.html",
        {
            **journey_list_context(
                request,
                get_project_baselines(
                    actor=request.user, organization=request.organization
                ),
                "baselines",
            ),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.BASELINES_VIEW)
@require_GET
def baseline_detail(request: HttpRequest, baseline_id: str) -> HttpResponse:
    baseline = _baseline(request, baseline_id)
    if baseline is None:
        return HttpResponseNotFound("مبنای تجاری یافت نشد.")
    return render(
        request,
        "billing/baseline_detail.html",
        {
            "baseline": baseline,
            "create_url": contextual_url(
                "billing:claim_create", contract=baseline.contract, baseline=baseline
            )
            if baseline.status == "approved" and claim_create_allowed(request)
            else "",
            "page_breadcrumbs": journey_breadcrumbs(
                request,
                "مبنای اندازه‌گیری",
                baseline.contract,
                collection=("مبناهای اندازه‌گیری", "billing:baseline_list"),
            ),
            "baseline_items": baseline.items.select_related("activity", "wbs_node"),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROGRESS_VIEW)
@require_GET
def progress_list(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "billing/progress_list.html",
        {
            **journey_list_context(
                request,
                get_progress_records(
                    actor=request.user, organization=request.organization
                ),
                "progress_records",
            ),
        },
    )


def journey_list_context(request, records, key):
    from apps.organizations.form_scoping import normalized_uuid

    prefix = "baseline__" if key == "progress_records" else ""
    if prefix:
        records = records.select_related("baseline__contract", "baseline__project")
    contract = request.GET.get("contract")
    if contract:
        value = normalized_uuid(contract)
        records = (
            records.filter(**{f"{prefix}contract_id": value})
            if value
            else records.none()
        )
    records = apply_table_filters(
        records,
        request,
        text_fields={
            "q": tuple(
                f"{prefix}{field}"
                for field in (
                    "contract__title",
                    "contract__contract_number",
                    "project__name",
                )
            )
        },
    )
    page = paginate_table(
        records, request, sort_fields={}, default_ordering=("-created_at", "pk")
    )
    return {
        key: page.object_list,
        "page_obj": page,
        "pagination_query": table_pagination_query(request),
        "pagination_rendered": True,
        **contextual_list_filters(request, keys=("contract",)),
        "page_breadcrumbs": journey_breadcrumbs(
            request,
            "پیشرفت کار" if prefix else "مبناهای اندازه‌گیری",
            breadcrumb_contract(request),
        ),
    }


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROGRESS_VIEW)
@require_GET
def progress_detail(request: HttpRequest, record_id: str) -> HttpResponse:
    record = _record(request, record_id)
    if record is None:
        return HttpResponseNotFound("رکورد پیشرفت یافت نشد.")
    return render(
        request,
        "billing/progress_detail.html",
        {
            "progress_record": record,
            "page_breadcrumbs": journey_breadcrumbs(
                request,
                "جزئیات اندازه‌گیری",
                record.baseline.contract,
                collection=("پیشرفت کار", "billing:progress_list"),
            ),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROGRESS_RECORD)
@require_POST
def progress_submit(request: HttpRequest, record_id: str) -> HttpResponse:
    record = _record(request, record_id)
    if record is None:
        return HttpResponseNotFound("رکورد پیشرفت یافت نشد.")
    try:
        request_progress_verification(
            organization=request.organization, actor=request.user, record=record
        )
        messages.success(request, "رکورد برای راستی‌آزمایی ارسال شد.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("billing:progress_detail", record_id=record.pk)


def _progress_decision(
    request: HttpRequest, record_id: str, *, verified: bool
) -> HttpResponse:
    record = _record(request, record_id)
    if record is None:
        return HttpResponseNotFound("رکورد پیشرفت یافت نشد.")
    reason = request.POST.get("reason", "")
    try:
        service = verify_progress_record if verified else reject_progress_record
        service(
            organization=request.organization,
            actor=request.user,
            record=record,
            reason=reason,
        )
        messages.success(
            request, "پیشرفت راستی‌آزمایی شد." if verified else "پیشرفت رد شد."
        )
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("billing:progress_detail", record_id=record.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROGRESS_VERIFY)
@require_POST
def progress_verify(request: HttpRequest, record_id: str) -> HttpResponse:
    return _progress_decision(request, record_id, verified=True)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROGRESS_VERIFY)
@require_POST
def progress_reject(request: HttpRequest, record_id: str) -> HttpResponse:
    return _progress_decision(request, record_id, verified=False)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CLAIMS_VIEW)
@require_GET
def claim_list(request: HttpRequest) -> HttpResponse:
    from apps.projects.business_hub import filter_project_context

    claims = get_progress_claims(actor=request.user, organization=request.organization)
    claims, selected_project = filter_project_context(request, claims)
    contract_filter = request.GET.get("contract")
    contract_scoped = "contract" in request.GET
    selected_contract = breadcrumb_contract(request, project=selected_project)
    if contract_scoped:
        from apps.organizations.form_scoping import normalized_uuid

        contract_id = normalized_uuid(contract_filter)
        claims = (
            claims.filter(contract_id=contract_id)
            if contract_id and len(request.GET.getlist("contract")) == 1
            else claims.none()
        )
    scoped_has_records = claims.exists()
    claims = apply_table_filters(
        claims,
        request,
        text_fields={}
        if contract_scoped
        else {"q": ("contract__title", "contract__contract_number", "project__name")},
        choice_fields={
            "status": (
                "status",
                tuple(
                    value
                    for value, label in ProgressClaim._meta.get_field("status").choices
                ),
            )
        },
    )
    page = paginate_table(
        claims,
        request,
        sort_fields={
            "number": "claim_number",
            "period": "period_start",
            "amount": "net_amount",
        },
        default_ordering=("-created_at", "pk"),
    )
    can_create_claim = route_exposed("billing:claim_create") and (
        contract_claim_create_allowed(request, selected_contract)
        if contract_scoped
        else not selected_project and claim_create_allowed(request)
    )
    return render(
        request,
        "billing/claim_list.html",
        {
            "claims": page.object_list,
            "scoped_has_records": scoped_has_records,
            "claim_status_choices": ProgressClaim._meta.get_field("status").choices,
            **contextual_list_filters(request),
            "selected_project": selected_project,
            "project_contracts_url": contextual_url(
                "contracts:list", project_id=selected_project.pk
            )
            if selected_project
            and not contract_scoped
            and claim_create_allowed(request)
            and route_exposed("contracts:list")
            and has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.CONTRACTS_VIEW,
                project=selected_project,
            )
            else "",
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "pagination_rendered": True,
            "contract_scoped": contract_scoped,
            "selected_contract": selected_contract,
            "can_create_claim": can_create_claim,
            "create_url": contextual_url(
                "billing:claim_create", contract=contract_filter
            )
            if can_create_claim and contract_scoped
            else reverse("billing:claim_create")
            if can_create_claim
            else "",
            "page_breadcrumbs": journey_breadcrumbs(
                request,
                "صورت‌وضعیت‌ها",
                selected_contract,
                project=selected_project,
            ),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CLAIMS_VIEW)
@require_GET
def claim_detail(request: HttpRequest, claim_id: str) -> HttpResponse:
    return render_claim_detail(request, claim_id)


def render_claim_detail(request, claim_id, action_form=None):
    claim = _claim(request, claim_id)
    if claim is None:
        return HttpResponseNotFound("صورت‌وضعیت یافت نشد.")
    can_view_settlements = capability_exposed("finance") and has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.CLAIM_SETTLEMENTS_VIEW,
    )
    can_allocate_settlements = capability_exposed(
        "finance"
    ) and has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.CLAIM_SETTLEMENTS_ALLOCATE,
    )
    return render(
        request,
        "billing/claim_detail.html",
        {
            "claim": claim,
            **claim_journey_context(request, claim),
            "decision_form": action_form
            if isinstance(action_form, ClaimDecisionForm)
            and not isinstance(action_form, ClaimCorrectionForm)
            else ClaimDecisionForm(),
            "correction_form": action_form
            if isinstance(action_form, ClaimCorrectionForm)
            else ClaimCorrectionForm(),
            "claim_items": claim.items.select_related("baseline_item"),
            "adjustments": claim.adjustments.all(),
            "correction_revisions": claim.correction_claims.order_by("revision_number"),
            "settlements": (
                claim_settlements_queryset(
                    organization=request.organization, claim=claim
                ).select_related("treasury_movement", "created_by__user", "reversal")
                if can_view_settlements
                else ()
            ),
            "settlement_summary": (
                get_progress_claim_settlement_summary(
                    organization=request.organization,
                    actor=request.user,
                    claim=claim,
                )
                if can_view_settlements
                else None
            ),
            "settlement_form": (
                ClaimSettlementAllocationForm(
                    organization=request.organization, claim=claim
                )
                if can_allocate_settlements and claim.status == "approved"
                else None
            ),
        },
    )


def claim_journey_context(request, claim):
    from django.db.models import Q

    from apps.contracts.services import get_organization_contracts
    from apps.workflows.models import WorkItem, WorkItemStatus

    def permitted(code, *, object_scope=False):
        return has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=code,
            project=claim.project if object_scope else None,
        )

    membership = get_active_membership(
        user=request.user, organization=request.organization
    )
    decision_items = WorkItem.objects.filter(
        organization=request.organization,
        instance__subject_type="billing.progress_claim",
        instance__subject_id=claim.pk,
        instance__status="active",
        status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
        candidates__membership=membership,
        candidates__is_active=True,
    ).filter(Q(current_assignee__isnull=True) | Q(current_assignee=membership))
    if not permitted(BusinessPermissionCode.WORK_ITEMS_CLAIM):
        decision_items = decision_items.filter(
            status=WorkItemStatus.CLAIMED, current_assignee=membership
        )
    can_decide = (
        claim.status == "submitted"
        and all(
            permitted(code)
            for code in (
                BusinessPermissionCode.CLAIMS_APPROVE,
                BusinessPermissionCode.WORK_ITEMS_ACT,
            )
        )
        and decision_items.exists()
    )
    contract_visible = (
        permitted(BusinessPermissionCode.CONTRACTS_VIEW, object_scope=True)
        and get_organization_contracts(
            user=request.user, organization=request.organization
        )
        .filter(pk=claim.contract_id)
        .exists()
    )
    return {
        "claim_title": f"صورت‌وضعیت {claim.claim_number} · نسخه {claim.revision_number}",
        "project_detail_url": reverse("projects:detail", args=[claim.project_id])
        if permitted(BusinessPermissionCode.PROJECTS_VIEW, object_scope=True)
        else "",
        "page_breadcrumbs": journey_breadcrumbs(
            request,
            f"صورت‌وضعیت {claim.claim_number}",
            claim.contract if contract_visible else None,
            project=claim.project,
            collection=("صورت‌وضعیت‌ها", "billing:claim_list"),
        ),
        "contract_visible": contract_visible,
        "baseline_visible": permitted(
            BusinessPermissionCode.BASELINES_VIEW, object_scope=True
        ),
        "progress_visible": permitted(
            BusinessPermissionCode.PROGRESS_VIEW, object_scope=True
        ),
        "can_recalculate": claim.status == "draft"
        and permitted(BusinessPermissionCode.CLAIMS_REVISE),
        "can_submit_claim": claim.status == "draft"
        and permitted(BusinessPermissionCode.CLAIMS_SUBMIT),
        "can_decide_claim": can_decide,
        "can_correct_claim": claim.status == "approved"
        and permitted(BusinessPermissionCode.CLAIMS_REVISE),
    }


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CLAIM_SETTLEMENTS_ALLOCATE)
@require_POST
def claim_settlement_allocate(request: HttpRequest, claim_id: str) -> HttpResponse:
    claim = _claim(request, claim_id)
    if claim is None:
        return HttpResponseNotFound("صورت‌وضعیت یافت نشد.")
    form = ClaimSettlementAllocationForm(
        request.POST,
        organization=request.organization,
        claim=claim,
    )
    if form.is_valid():
        try:
            allocate_progress_claim_settlement(
                organization=request.organization,
                actor=request.user,
                claim=claim,
                movement=form.cleaned_data["movement"],
                effective_date=form.cleaned_data["effective_date"],
                idempotency_key=form.cleaned_data["idempotency_key"],
                amount=form.cleaned_data["amount"],
                reason=form.cleaned_data["reason"],
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "تسویه صورت‌وضعیت ثبت شد.")
    else:
        messages.error(request, "اطلاعات تسویه معتبر نیست.")
    return redirect("billing:claim_detail", claim_id=claim.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CLAIMS_VIEW)
@require_GET
def recovery_guidance(request: HttpRequest) -> HttpResponse:
    return render(request, "billing/recovery_guidance.html")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYABLE_CERTIFICATES_VIEW)
@require_GET
def payable_certificate_list(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "billing/payable_certificate_list.html",
        {
            "certificates": get_payable_certificates(
                actor=request.user, organization=request.organization
            )
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYABLE_CERTIFICATES_CREATE)
@require_http_methods(["GET", "POST"])
def payable_certificate_create(request: HttpRequest) -> HttpResponse:
    form = PayableCertificateForm(
        request.POST or None,
        organization=request.organization,
        membership=get_active_membership(
            user=request.user, organization=request.organization
        ),
    )
    if request.method == "POST" and form.is_valid():
        try:
            certificate = create_payable_certificate(
                organization=request.organization,
                actor=request.user,
                contract=form.cleaned_data["contract"],
                period_start=form.cleaned_data["period_start"],
                period_end=form.cleaned_data["period_end"],
                measurement_cutoff=form.cleaned_data["measurement_cutoff"],
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "پیش‌نویس گواهی پرداخت ایجاد شد.")
            return redirect(
                "billing:payable_certificate_detail", certificate_id=certificate.pk
            )
    return render(
        request,
        "billing/payable_form.html",
        {"form": form, "title": "ایجاد گواهی پرداخت پیمان جزء"},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYABLE_CERTIFICATES_VIEW)
@require_GET
def payable_certificate_detail(
    request: HttpRequest, certificate_id: str
) -> HttpResponse:
    certificate = _payable_certificate(request, certificate_id)
    if certificate is None:
        return HttpResponseNotFound("گواهی پرداخت یافت نشد.")
    return render(
        request,
        "billing/payable_certificate_detail.html",
        {
            "certificate": certificate,
            "certificate_items": certificate.items.select_related(
                "contract_item", "measurement"
            ),
            "adjustments": certificate.adjustments.all(),
            "correction_revisions": certificate.correction_certificates.order_by(
                "revision_number"
            ),
            "back_charge_form": PayableBackChargeForm(),
            "correction_form": PayableCertificateCorrectionForm(),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYABLE_CERTIFICATES_SUBMIT)
@require_POST
def payable_certificate_submit(
    request: HttpRequest, certificate_id: str
) -> HttpResponse:
    certificate = _payable_certificate(request, certificate_id)
    if certificate is None:
        return HttpResponseNotFound("گواهی پرداخت یافت نشد.")
    try:
        submit_payable_certificate(
            organization=request.organization,
            actor=request.user,
            certificate=certificate,
        )
        messages.success(request, "گواهی پرداخت برای تأیید ارسال شد.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("billing:payable_certificate_detail", certificate_id=certificate.pk)


def _payable_certificate_decision(
    request: HttpRequest, certificate_id: str, *, approved: bool
) -> HttpResponse:
    certificate = _payable_certificate(request, certificate_id)
    if certificate is None:
        return HttpResponseNotFound("گواهی پرداخت یافت نشد.")
    reason = request.POST.get("reason", "")
    try:
        service = (
            approve_payable_certificate if approved else return_payable_certificate
        )
        service(
            organization=request.organization,
            actor=request.user,
            certificate=certificate,
            reason=reason,
        )
        messages.success(
            request,
            "گواهی پرداخت تأیید شد."
            if approved
            else "گواهی پرداخت برای اصلاح بازگردانده شد.",
        )
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("billing:payable_certificate_detail", certificate_id=certificate.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYABLE_CERTIFICATES_APPROVE)
@require_POST
def payable_certificate_approve(
    request: HttpRequest, certificate_id: str
) -> HttpResponse:
    return _payable_certificate_decision(request, certificate_id, approved=True)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYABLE_CERTIFICATES_APPROVE)
@require_POST
def payable_certificate_return(
    request: HttpRequest, certificate_id: str
) -> HttpResponse:
    return _payable_certificate_decision(request, certificate_id, approved=False)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYABLE_CERTIFICATES_REVISE)
@require_POST
def payable_certificate_back_charge(
    request: HttpRequest, certificate_id: str
) -> HttpResponse:
    certificate = _payable_certificate(request, certificate_id)
    if certificate is None:
        return HttpResponseNotFound("گواهی پرداخت یافت نشد.")
    form = PayableBackChargeForm(request.POST)
    if form.is_valid():
        try:
            add_payable_back_charge(
                organization=request.organization,
                actor=request.user,
                certificate=certificate,
                amount=form.cleaned_data["amount"],
                description=form.cleaned_data["description"],
                evidence=form.cleaned_data["evidence"],
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "کسر هزینه مستند افزوده شد.")
    else:
        messages.error(request, "اطلاعات کسر هزینه معتبر نیست.")
    return redirect("billing:payable_certificate_detail", certificate_id=certificate.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYABLE_CERTIFICATES_REVISE)
@require_POST
def payable_certificate_correct(
    request: HttpRequest, certificate_id: str
) -> HttpResponse:
    certificate = _payable_certificate(request, certificate_id)
    if certificate is None:
        return HttpResponseNotFound("گواهی پرداخت یافت نشد.")
    form = PayableCertificateCorrectionForm(request.POST)
    if form.is_valid():
        try:
            correction = create_payable_certificate_correction(
                organization=request.organization,
                actor=request.user,
                certificate=certificate,
                correction_kind=form.cleaned_data["correction_kind"],
                reason=form.cleaned_data["reason"],
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "نسخه اصلاحی پیوندخورده ایجاد شد.")
            return redirect(
                "billing:payable_certificate_detail", certificate_id=correction.pk
            )
    return redirect("billing:payable_certificate_detail", certificate_id=certificate.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYABLE_MEASUREMENTS_VIEW)
@require_GET
def payable_measurement_list(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "billing/payable_measurement_list.html",
        {
            "measurements": get_payable_measurements(
                actor=request.user, organization=request.organization
            )
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYABLE_MEASUREMENTS_RECORD)
@require_http_methods(["GET", "POST"])
def payable_measurement_create(request: HttpRequest) -> HttpResponse:
    form = PayableMeasurementForm(
        request.POST or None,
        organization=request.organization,
        membership=get_active_membership(
            user=request.user, organization=request.organization
        ),
    )
    if request.method == "POST" and form.is_valid():
        try:
            measurement = create_payable_measurement(
                organization=request.organization,
                actor=request.user,
                contract_item=form.cleaned_data["contract_item"],
                measured_on=form.cleaned_data["measured_on"],
                period_quantity=form.cleaned_data["period_quantity"],
                cumulative_quantity=form.cleaned_data["cumulative_quantity"],
                evidence_reference=form.cleaned_data["evidence_reference"],
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "اندازه‌گیری پیمان جزء ثبت شد.")
            return redirect(
                "billing:payable_measurement_detail", measurement_id=measurement.pk
            )
    return render(
        request,
        "billing/payable_form.html",
        {"form": form, "title": "ثبت اندازه‌گیری پیمان جزء"},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYABLE_MEASUREMENTS_VIEW)
@require_GET
def payable_measurement_detail(
    request: HttpRequest, measurement_id: str
) -> HttpResponse:
    measurement = _payable_measurement(request, measurement_id)
    if measurement is None:
        return HttpResponseNotFound("اندازه‌گیری یافت نشد.")
    return render(
        request,
        "billing/payable_measurement_detail.html",
        {"measurement": measurement},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYABLE_MEASUREMENTS_RECORD)
@require_POST
def payable_measurement_submit(
    request: HttpRequest, measurement_id: str
) -> HttpResponse:
    measurement = _payable_measurement(request, measurement_id)
    if measurement is None:
        return HttpResponseNotFound("اندازه‌گیری یافت نشد.")
    try:
        submit_payable_measurement(
            organization=request.organization,
            actor=request.user,
            measurement=measurement,
        )
        messages.success(request, "اندازه‌گیری برای راستی‌آزمایی ارسال شد.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("billing:payable_measurement_detail", measurement_id=measurement.pk)


def _payable_measurement_decision(
    request: HttpRequest, measurement_id: str, *, approved: bool
) -> HttpResponse:
    measurement = _payable_measurement(request, measurement_id)
    if measurement is None:
        return HttpResponseNotFound("اندازه‌گیری یافت نشد.")
    try:
        decide_payable_measurement(
            organization=request.organization,
            actor=request.user,
            measurement=measurement,
            approved=approved,
            reason=request.POST.get("reason", ""),
        )
        messages.success(
            request, "اندازه‌گیری تأیید شد." if approved else "اندازه‌گیری رد شد."
        )
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("billing:payable_measurement_detail", measurement_id=measurement.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYABLE_MEASUREMENTS_VERIFY)
@require_POST
def payable_measurement_verify(
    request: HttpRequest, measurement_id: str
) -> HttpResponse:
    return _payable_measurement_decision(request, measurement_id, approved=True)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYABLE_MEASUREMENTS_VERIFY)
@require_POST
def payable_measurement_reject(
    request: HttpRequest, measurement_id: str
) -> HttpResponse:
    return _payable_measurement_decision(request, measurement_id, approved=False)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.GUARANTEES_VIEW)
@require_GET
def commercial_control_dashboard(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "billing/commercial_control_dashboard.html",
        {
            "exposure_side_choices": GuaranteeExposureSide.choices,
            "guarantee_type_choices": GuaranteeType.choices,
            "exposure": commercial_exposure(
                actor=request.user, organization=request.organization
            ),
            "guarantees": get_guarantees(
                actor=request.user, organization=request.organization
            ).order_by("-created_at")[:50],
            "compliance_evidence": get_compliance_evidence(
                actor=request.user, organization=request.organization
            ).order_by("-created_at")[:50],
            "retention_releases": get_retention_releases(
                actor=request.user, organization=request.organization
            ).order_by("-created_at")[:50],
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.GUARANTEES_MANAGE)
@require_http_methods(["GET", "POST"])
def guarantee_create(request: HttpRequest) -> HttpResponse:
    form = GuaranteeForm(
        request.POST or None,
        organization=request.organization,
        membership=get_active_membership(
            user=request.user, organization=request.organization
        ),
        actor=request.user,
    )
    if request.method == "POST" and form.is_valid():
        try:
            guarantee = create_guarantee(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "پیش‌نویس ضمانت‌نامه ایجاد شد.")
            return redirect("billing:guarantee_detail", guarantee_id=guarantee.pk)
    return render(
        request,
        "billing/commercial_form.html",
        {"form": form, "title": "ثبت ضمانت‌نامه قراردادی"},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.GUARANTEES_VIEW)
@require_GET
def guarantee_detail(request: HttpRequest, guarantee_id: str) -> HttpResponse:
    guarantee = _commercial_record(request, guarantee_id, "guarantee")
    if guarantee is None:
        return HttpResponseNotFound("ضمانت‌نامه یافت نشد.")
    return render(
        request,
        "billing/commercial_record_detail.html",
        {
            "kind": "guarantee",
            "record": guarantee,
            "title": "ضمانت‌نامه قراردادی",
            "revision_form": GuaranteeRevisionForm(organization=request.organization),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.GUARANTEES_MANAGE)
@require_POST
def guarantee_revise(request: HttpRequest, guarantee_id: str) -> HttpResponse:
    guarantee = _commercial_record(request, guarantee_id, "guarantee")
    if guarantee is None:
        return HttpResponseNotFound("ضمانت‌نامه یافت نشد.")
    form = GuaranteeRevisionForm(request.POST, organization=request.organization)
    if form.is_valid():
        try:
            revised = create_guarantee_revision(
                organization=request.organization,
                actor=request.user,
                guarantee=guarantee,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "نسخه پیوندخورده ضمانت‌نامه ایجاد شد.")
            return redirect("billing:guarantee_detail", guarantee_id=revised.pk)
    else:
        messages.error(request, "اطلاعات نسخه ضمانت‌نامه معتبر نیست.")
    return redirect("billing:guarantee_detail", guarantee_id=guarantee.pk)


def _commercial_submit(request: HttpRequest, record_id: str, kind: str) -> HttpResponse:
    record = _commercial_record(request, record_id, kind)
    if record is None:
        return HttpResponseNotFound("رکورد کنترل قراردادی یافت نشد.")
    services = {
        "guarantee": submit_guarantee,
        "compliance": submit_compliance_evidence,
        "release": submit_retention_release,
    }
    keywords = {
        "guarantee": "guarantee",
        "compliance": "evidence",
        "release": "release",
    }
    try:
        services[kind](
            organization=request.organization,
            actor=request.user,
            **{keywords[kind]: record},
        )
        messages.success(request, "رکورد برای تأیید ارسال شد.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    route = {
        "guarantee": "billing:guarantee_detail",
        "compliance": "billing:compliance_evidence_detail",
        "release": "billing:retention_release_detail",
    }[kind]
    return redirect(route, **{f"{keywords[kind]}_id": record.pk})


def _commercial_decision(
    request: HttpRequest, record_id: str, kind: str, *, approved: bool
) -> HttpResponse:
    record = _commercial_record(request, record_id, kind)
    if record is None:
        return HttpResponseNotFound("رکورد کنترل قراردادی یافت نشد.")
    services = {
        "guarantee": decide_guarantee,
        "compliance": decide_compliance_evidence,
        "release": decide_retention_release,
    }
    keywords = {
        "guarantee": "guarantee",
        "compliance": "evidence",
        "release": "release",
    }
    try:
        services[kind](
            organization=request.organization,
            actor=request.user,
            approved=approved,
            reason=request.POST.get("reason", ""),
            **{keywords[kind]: record},
        )
        messages.success(request, "تصمیم ثبت شد.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    route = {
        "guarantee": "billing:guarantee_detail",
        "compliance": "billing:compliance_evidence_detail",
        "release": "billing:retention_release_detail",
    }[kind]
    return redirect(route, **{f"{keywords[kind]}_id": record.pk})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.GUARANTEES_SUBMIT)
@require_POST
def guarantee_submit(request: HttpRequest, guarantee_id: str) -> HttpResponse:
    return _commercial_submit(request, guarantee_id, "guarantee")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.GUARANTEES_APPROVE)
@require_POST
def guarantee_approve(request: HttpRequest, guarantee_id: str) -> HttpResponse:
    return _commercial_decision(request, guarantee_id, "guarantee", approved=True)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.GUARANTEES_APPROVE)
@require_POST
def guarantee_return(request: HttpRequest, guarantee_id: str) -> HttpResponse:
    return _commercial_decision(request, guarantee_id, "guarantee", approved=False)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.COMPLIANCE_EVIDENCE_MANAGE)
@require_http_methods(["GET", "POST"])
def compliance_evidence_create(request: HttpRequest) -> HttpResponse:
    form = ComplianceEvidenceForm(
        request.POST or None,
        organization=request.organization,
        membership=get_active_membership(
            user=request.user, organization=request.organization
        ),
        actor=request.user,
    )
    if request.method == "POST" and form.is_valid():
        try:
            evidence = create_compliance_evidence(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "پیش‌نویس شاهد قراردادی ایجاد شد.")
            return redirect(
                "billing:compliance_evidence_detail", evidence_id=evidence.pk
            )
    return render(
        request,
        "billing/commercial_form.html",
        {"form": form, "title": "ثبت شاهد بیمه یا مفاصاحساب"},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.COMPLIANCE_EVIDENCE_VIEW)
@require_GET
def compliance_evidence_detail(request: HttpRequest, evidence_id: str) -> HttpResponse:
    evidence = _commercial_record(request, evidence_id, "compliance")
    if evidence is None:
        return HttpResponseNotFound("شاهد قراردادی یافت نشد.")
    return render(
        request,
        "billing/commercial_record_detail.html",
        {
            "kind": "compliance",
            "record": evidence,
            "title": "شاهد بیمه یا مفاصاحساب",
            "revision_form": ComplianceEvidenceRevisionForm(
                organization=request.organization
            ),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.COMPLIANCE_EVIDENCE_MANAGE)
@require_POST
def compliance_evidence_revise(request: HttpRequest, evidence_id: str) -> HttpResponse:
    evidence = _commercial_record(request, evidence_id, "compliance")
    if evidence is None:
        return HttpResponseNotFound("شاهد قراردادی یافت نشد.")
    form = ComplianceEvidenceRevisionForm(
        request.POST, organization=request.organization
    )
    if form.is_valid():
        try:
            revised = create_compliance_evidence_revision(
                organization=request.organization,
                actor=request.user,
                evidence=evidence,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "نسخه پیوندخورده شاهد ایجاد شد.")
            return redirect(
                "billing:compliance_evidence_detail", evidence_id=revised.pk
            )
    else:
        messages.error(request, "اطلاعات نسخه شاهد معتبر نیست.")
    return redirect("billing:compliance_evidence_detail", evidence_id=evidence.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.COMPLIANCE_EVIDENCE_SUBMIT)
@require_POST
def compliance_evidence_submit(request: HttpRequest, evidence_id: str) -> HttpResponse:
    return _commercial_submit(request, evidence_id, "compliance")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.COMPLIANCE_EVIDENCE_APPROVE)
@require_POST
def compliance_evidence_approve(request: HttpRequest, evidence_id: str) -> HttpResponse:
    return _commercial_decision(request, evidence_id, "compliance", approved=True)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.COMPLIANCE_EVIDENCE_APPROVE)
@require_POST
def compliance_evidence_return(request: HttpRequest, evidence_id: str) -> HttpResponse:
    return _commercial_decision(request, evidence_id, "compliance", approved=False)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.RETENTION_RELEASES_CREATE)
@require_http_methods(["GET", "POST"])
def retention_release_create(request: HttpRequest) -> HttpResponse:
    form = RetentionReleaseForm(
        request.POST or None,
        organization=request.organization,
        membership=get_active_membership(
            user=request.user, organization=request.organization
        ),
        actor=request.user,
    )
    if request.method == "POST" and form.is_valid():
        try:
            release = create_retention_release(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "پیش‌نویس آزادسازی کسور تضمین ایجاد شد.")
            return redirect("billing:retention_release_detail", release_id=release.pk)
    return render(
        request,
        "billing/commercial_form.html",
        {"form": form, "title": "آزادسازی کنترل‌شده کسور تضمین"},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.RETENTION_RELEASES_VIEW)
@require_GET
def retention_release_detail(request: HttpRequest, release_id: str) -> HttpResponse:
    release = _commercial_record(request, release_id, "release")
    if release is None:
        return HttpResponseNotFound("آزادسازی یافت نشد.")
    return render(
        request,
        "billing/commercial_record_detail.html",
        {
            "kind": "release",
            "record": release,
            "title": "آزادسازی کسور تضمین",
            "revision_form": RetentionReleaseCorrectionForm(
                organization=request.organization
            ),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.RETENTION_RELEASES_CREATE)
@require_POST
def retention_release_correct(request: HttpRequest, release_id: str) -> HttpResponse:
    release = _commercial_record(request, release_id, "release")
    if release is None:
        return HttpResponseNotFound("آزادسازی یافت نشد.")
    form = RetentionReleaseCorrectionForm(
        request.POST, organization=request.organization
    )
    if form.is_valid():
        data = form.cleaned_data
        if data["correction_kind"] == RetentionReleaseCorrectionKind.CANCELLATION:
            data["amount"] = 0
        try:
            corrected = create_retention_release_correction(
                organization=request.organization,
                actor=request.user,
                release=release,
                **data,
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "اصلاح پیوندخورده آزادسازی ایجاد شد.")
            return redirect("billing:retention_release_detail", release_id=corrected.pk)
    else:
        messages.error(request, "اطلاعات اصلاح آزادسازی معتبر نیست.")
    return redirect("billing:retention_release_detail", release_id=release.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.RETENTION_RELEASES_SUBMIT)
@require_POST
def retention_release_submit(request: HttpRequest, release_id: str) -> HttpResponse:
    return _commercial_submit(request, release_id, "release")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.RETENTION_RELEASES_APPROVE)
@require_POST
def retention_release_approve(request: HttpRequest, release_id: str) -> HttpResponse:
    return _commercial_decision(request, release_id, "release", approved=True)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.RETENTION_RELEASES_APPROVE)
@require_POST
def retention_release_return(request: HttpRequest, release_id: str) -> HttpResponse:
    return _commercial_decision(request, release_id, "release", approved=False)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.GUARANTEES_MANAGE)
@require_POST
def commercial_expiry_refresh(request: HttpRequest) -> HttpResponse:
    as_of = organization_localdate(request.organization)
    try:
        if not has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=BusinessPermissionCode.COMPLIANCE_EVIDENCE_MANAGE,
            allow_any_scope=True,
        ):
            raise PermissionDenied(
                "به‌روزرسانی یکپارچه انقضا به هر دو اختیار ضمانت و شواهد نیاز دارد."
            )
        with transaction.atomic():
            guarantees = expire_due_guarantees(
                organization=request.organization, actor=request.user, as_of=as_of
            )
            evidence = expire_due_compliance_evidence(
                organization=request.organization, actor=request.user, as_of=as_of
            )
        messages.success(
            request,
            f"وضعیت انقضا به‌روز شد: {guarantees} ضمانت‌نامه و {evidence} شاهد.",
        )
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("billing:commercial_control_dashboard")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TAXPAYER_INVOICES_VIEW)
@require_GET
def statutory_operations_dashboard(request: HttpRequest) -> HttpResponse:
    try:
        invoices = get_taxpayer_invoices(
            actor=request.user, organization=request.organization
        )
    except (PermissionDenied, ValidationError):
        invoices = TaxpayerInvoice.objects.none()
    try:
        assessments = get_contractor_assessments(
            actor=request.user, organization=request.organization
        )
    except (PermissionDenied, ValidationError):
        assessments = ContractorComplianceAssessment.objects.none()
    submissions = StatutorySubmissionEvidence.objects.filter(
        organization=request.organization
    ).select_related("taxpayer_invoice", "contractor_assessment")[:100]
    return render(
        request,
        "billing/statutory_operations_dashboard.html",
        {
            "invoices": invoices,
            "assessments": assessments,
            "submissions": submissions,
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TAXPAYER_INVOICES_PREPARE)
@require_http_methods(["GET", "POST"])
def taxpayer_invoice_create(request: HttpRequest) -> HttpResponse:
    form = TaxpayerInvoiceForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            invoice = create_taxpayer_invoice(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "پیش‌نویس صورتحساب مؤدیان ایجاد شد.")
            return redirect("billing:taxpayer_invoice_detail", invoice_id=invoice.pk)
    return render(
        request,
        "billing/commercial_form.html",
        {"form": form, "title": "تهیه صورتحساب مؤدیان"},
    )


def _taxpayer_invoice(request: HttpRequest, invoice_id: str):
    try:
        return get_taxpayer_invoices(
            actor=request.user, organization=request.organization
        ).get(pk=invoice_id)
    except (PermissionDenied, ValidationError, TaxpayerInvoice.DoesNotExist):
        return None


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TAXPAYER_INVOICES_VIEW)
@require_GET
def taxpayer_invoice_detail(request: HttpRequest, invoice_id: str) -> HttpResponse:
    invoice = _taxpayer_invoice(request, invoice_id)
    if invoice is None:
        return HttpResponseNotFound("صورتحساب مؤدیان یافت نشد.")
    return render(
        request,
        "billing/statutory_record_detail.html",
        {
            "kind": "invoice",
            "record": invoice,
            "title": "صورتحساب مؤدیان",
            "submission_form": StatutorySubmissionForm(),
            "reconciliation": reconcile_taxpayer_invoice(
                actor=request.user,
                organization=request.organization,
                invoice=invoice,
            ),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TAXPAYER_INVOICES_SUBMIT)
@require_POST
def taxpayer_invoice_submit(request: HttpRequest, invoice_id: str) -> HttpResponse:
    invoice = _taxpayer_invoice(request, invoice_id)
    if invoice is None:
        return HttpResponseNotFound("صورتحساب مؤدیان یافت نشد.")
    try:
        submit_taxpayer_invoice(
            organization=request.organization, actor=request.user, invoice=invoice
        )
        messages.success(request, "صورتحساب برای تأیید ارسال شد.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("billing:taxpayer_invoice_detail", invoice_id=invoice.pk)


def _taxpayer_decision(request, invoice_id, *, approved):
    invoice = _taxpayer_invoice(request, invoice_id)
    if invoice is None:
        return HttpResponseNotFound("صورتحساب مؤدیان یافت نشد.")
    try:
        decide_taxpayer_invoice(
            organization=request.organization,
            actor=request.user,
            invoice=invoice,
            approved=approved,
            reason=request.POST.get("reason", ""),
        )
        messages.success(request, "تصمیم صورتحساب ثبت شد.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("billing:taxpayer_invoice_detail", invoice_id=invoice.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TAXPAYER_INVOICES_APPROVE)
@require_POST
def taxpayer_invoice_approve(request: HttpRequest, invoice_id: str) -> HttpResponse:
    return _taxpayer_decision(request, invoice_id, approved=True)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TAXPAYER_INVOICES_APPROVE)
@require_POST
def taxpayer_invoice_return(request: HttpRequest, invoice_id: str) -> HttpResponse:
    return _taxpayer_decision(request, invoice_id, approved=False)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.STATUTORY_SUBMISSIONS_EXECUTE)
@require_POST
def taxpayer_invoice_export(request: HttpRequest, invoice_id: str) -> HttpResponse:
    invoice = _taxpayer_invoice(request, invoice_id)
    if invoice is None:
        return HttpResponseNotFound("صورتحساب مؤدیان یافت نشد.")
    form = StatutorySubmissionForm(request.POST)
    if form.is_valid():
        try:
            record_statutory_submission(
                organization=request.organization,
                actor=request.user,
                target=invoice,
                **form.cleaned_data,
            )
            messages.success(request, "شاهد خروجی مقرراتی ثبت شد.")
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "شناسه‌های خروجی معتبر نیستند.")
    return redirect("billing:taxpayer_invoice_detail", invoice_id=invoice.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CONTRACTOR_COMPLIANCE_PREPARE)
@require_http_methods(["GET", "POST"])
def contractor_compliance_create(request: HttpRequest) -> HttpResponse:
    form = ContractorComplianceAssessmentForm(
        request.POST or None, organization=request.organization
    )
    if request.method == "POST" and form.is_valid():
        try:
            assessment = create_contractor_compliance_assessment(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "ارزیابی انطباق پیمانکار ایجاد شد.")
            return redirect(
                "billing:contractor_compliance_detail", assessment_id=assessment.pk
            )
    return render(
        request,
        "billing/commercial_form.html",
        {"form": form, "title": "ارزیابی انطباق بیمه پیمانکار"},
    )


def _contractor_assessment(request: HttpRequest, assessment_id: str):
    try:
        return get_contractor_assessments(
            actor=request.user, organization=request.organization
        ).get(pk=assessment_id)
    except (
        PermissionDenied,
        ValidationError,
        ContractorComplianceAssessment.DoesNotExist,
    ):
        return None


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CONTRACTOR_COMPLIANCE_VIEW)
@require_GET
def contractor_compliance_detail(
    request: HttpRequest, assessment_id: str
) -> HttpResponse:
    assessment = _contractor_assessment(request, assessment_id)
    if assessment is None:
        return HttpResponseNotFound("ارزیابی انطباق یافت نشد.")
    return render(
        request,
        "billing/statutory_record_detail.html",
        {
            "kind": "contractor",
            "record": assessment,
            "title": "ارزیابی انطباق بیمه پیمانکار",
            "submission_form": StatutorySubmissionForm(),
            "reconciliation": reconcile_contractor_assessment(
                actor=request.user,
                organization=request.organization,
                assessment=assessment,
            ),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CONTRACTOR_COMPLIANCE_SUBMIT)
@require_POST
def contractor_compliance_submit(
    request: HttpRequest, assessment_id: str
) -> HttpResponse:
    assessment = _contractor_assessment(request, assessment_id)
    if assessment is None:
        return HttpResponseNotFound("ارزیابی انطباق یافت نشد.")
    try:
        submit_contractor_assessment(
            organization=request.organization,
            actor=request.user,
            assessment=assessment,
        )
        messages.success(request, "ارزیابی برای تأیید ارسال شد.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("billing:contractor_compliance_detail", assessment_id=assessment.pk)


def _contractor_decision(request, assessment_id, *, approved):
    assessment = _contractor_assessment(request, assessment_id)
    if assessment is None:
        return HttpResponseNotFound("ارزیابی انطباق یافت نشد.")
    try:
        decide_contractor_assessment(
            organization=request.organization,
            actor=request.user,
            assessment=assessment,
            approved=approved,
            reason=request.POST.get("reason", ""),
        )
        messages.success(request, "تصمیم ارزیابی ثبت شد.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("billing:contractor_compliance_detail", assessment_id=assessment.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CONTRACTOR_COMPLIANCE_APPROVE)
@require_POST
def contractor_compliance_approve(
    request: HttpRequest, assessment_id: str
) -> HttpResponse:
    return _contractor_decision(request, assessment_id, approved=True)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.CONTRACTOR_COMPLIANCE_APPROVE)
@require_POST
def contractor_compliance_return(
    request: HttpRequest, assessment_id: str
) -> HttpResponse:
    return _contractor_decision(request, assessment_id, approved=False)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.STATUTORY_SUBMISSIONS_EXECUTE)
@require_POST
def contractor_compliance_export(
    request: HttpRequest, assessment_id: str
) -> HttpResponse:
    assessment = _contractor_assessment(request, assessment_id)
    if assessment is None:
        return HttpResponseNotFound("ارزیابی انطباق یافت نشد.")
    form = StatutorySubmissionForm(request.POST)
    if form.is_valid():
        try:
            record_statutory_submission(
                organization=request.organization,
                actor=request.user,
                target=assessment,
                **form.cleaned_data,
            )
            messages.success(request, "شاهد خروجی انطباق پیمانکار ثبت شد.")
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "شناسه‌های خروجی معتبر نیستند.")
    return redirect("billing:contractor_compliance_detail", assessment_id=assessment.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.STATUTORY_SUBMISSIONS_RESOLVE)
@require_POST
def statutory_submission_resolve(
    request: HttpRequest, submission_id: str
) -> HttpResponse:
    submission = StatutorySubmissionEvidence.objects.filter(
        pk=submission_id, organization=request.organization
    ).first()
    if submission is None:
        return HttpResponseNotFound("شاهد ارسال یافت نشد.")
    form = SubmissionResolutionForm(request.POST)
    if form.is_valid():
        try:
            resolve_submission_error(
                organization=request.organization,
                actor=request.user,
                submission=submission,
                **form.cleaned_data,
            )
            messages.success(request, "شاهد حل انسانی ثبت شد.")
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, str(exc))
    return redirect("billing:statutory_operations_dashboard")
