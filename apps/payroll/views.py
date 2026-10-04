from __future__ import annotations

import json

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.audit.models import AuditEvent
from apps.organizations.authorization import (
    get_active_membership,
    membership_has_permission,
    scope_queryset,
)
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import (
    BusinessPermissionCode,
    PlatformPolicy,
    PlatformPolicyVersion,
)
from apps.organizations.policy_specs import (
    EMPLOYEE_INSURANCE_OUTPUT_SCHEMA_POLICY_CODE,
    EMPLOYEE_INSURANCE_REGULATORY_POLICY_CODE,
    PAYROLL_TAX_OUTPUT_SCHEMA_POLICY_CODE,
    PAYROLL_TAX_REGULATORY_POLICY_CODE,
)

from . import financial_handoff_services, services, statutory_services
from .forms import (
    AdjustmentForm,
    ComponentForm,
    EmploymentConfigurationForm,
    FinancialHandoffPrepareForm,
    FinancialHandoffReviewForm,
    InputForm,
    PeriodForm,
    ReversalForm,
    RuleForm,
    RunForm,
    StatutoryCalculationForm,
    StatutoryExportForm,
    StatutoryIdentityForm,
    StatutoryOutputForm,
    StatutoryResolutionForm,
    StatutoryReviewForm,
)
from .models import (
    EmploymentPayConfiguration,
    FinancialHandoffFamily,
    FinancialHandoffProposal,
    PayrollComponent,
    PayrollException,
    PayrollPeriod,
    PayrollRule,
    PayrollRun,
    PayrollRunEmployee,
    Payslip,
    StatutoryCalculation,
    StatutoryExportEvidence,
    StatutoryOutput,
)


def _error_message(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return "؛ ".join(exc.messages)
    return str(exc)


def _form_page(
    request: HttpRequest, *, form, title: str, description: str
) -> HttpResponse:
    return render(
        request,
        "payroll/form.html",
        {"form": form, "title": title, "description": description},
    )


def _scoped_results(request: HttpRequest):
    membership = get_active_membership(
        user=request.user, organization=request.organization
    )
    return scope_queryset(
        PayrollRunEmployee.objects.filter(
            organization=request.organization
        ).select_related("run", "run__period", "employee", "project", "site"),
        membership=membership,
        project_lookup="project_id",
        site_lookup="site_id",
    )


def _require_any_statutory_permission(request: HttpRequest):
    membership = get_active_membership(
        user=request.user, organization=request.organization
    )
    allowed = (
        BusinessPermissionCode.PAYROLL_STATUTORY_PREPARE,
        BusinessPermissionCode.PAYROLL_STATUTORY_REVIEW,
        BusinessPermissionCode.PAYROLL_STATUTORY_OUTPUT_GENERATE,
        BusinessPermissionCode.PAYROLL_STATUTORY_EXPORT,
        BusinessPermissionCode.PAYROLL_STATUTORY_CORRECT,
        BusinessPermissionCode.PAYROLL_STATUTORY_AUDIT_VIEW,
    )
    if not any(membership_has_permission(membership, code) for code in allowed):
        raise PermissionDenied("اجازه مشاهده عملیات حساس مقرراتی حقوق را ندارید.")
    return membership


def _require_any_financial_handoff_permission(request: HttpRequest):
    membership = get_active_membership(
        user=request.user, organization=request.organization
    )
    allowed = (
        BusinessPermissionCode.PAYROLL_LIABILITY_HANDOFF_PREPARE,
        BusinessPermissionCode.PAYROLL_LIABILITY_HANDOFF_REVIEW,
        BusinessPermissionCode.PAYROLL_ACCOUNTING_HANDOFF_PREPARE,
        BusinessPermissionCode.PAYROLL_ACCOUNTING_HANDOFF_REVIEW,
        BusinessPermissionCode.PAYROLL_PAYMENT_HANDOFF_PREPARE,
        BusinessPermissionCode.PAYROLL_PAYMENT_HANDOFF_REVIEW,
        BusinessPermissionCode.PAYROLL_PROJECT_COST_HANDOFF_PREPARE,
        BusinessPermissionCode.PAYROLL_PROJECT_COST_HANDOFF_REVIEW,
        BusinessPermissionCode.PAYROLL_HANDOFF_RECONCILIATION_PREPARE,
        BusinessPermissionCode.PAYROLL_HANDOFF_RECONCILIATION_REVIEW,
    )
    if not any(membership_has_permission(membership, code) for code in allowed):
        raise PermissionDenied("اجازه مشاهده تحویل مالی حقوق را ندارید.")
    return membership


def _allowed_financial_handoff_families(request: HttpRequest) -> set[str]:
    membership = _require_any_financial_handoff_permission(request)
    if any(
        membership_has_permission(membership, permission)
        for permission in (
            BusinessPermissionCode.PAYROLL_HANDOFF_RECONCILIATION_PREPARE,
            BusinessPermissionCode.PAYROLL_HANDOFF_RECONCILIATION_REVIEW,
        )
    ):
        return set(FinancialHandoffFamily.values)
    return {
        family
        for family in FinancialHandoffFamily.values
        if any(
            membership_has_permission(membership, permission)
            for permission in (
                financial_handoff_services.PREPARE_PERMISSIONS[family],
                financial_handoff_services.REVIEW_PERMISSIONS[family],
            )
        )
    }


def _require_financial_handoff_family(request: HttpRequest, family: str) -> None:
    if family not in _allowed_financial_handoff_families(request):
        raise PermissionDenied("اجازه مشاهده این خانواده تحویل مالی حقوق را ندارید.")


def _require_financial_handoff_review(request: HttpRequest, family: str) -> None:
    membership = _require_any_financial_handoff_permission(request)
    if not membership_has_permission(
        membership, financial_handoff_services.REVIEW_PERMISSIONS[family]
    ):
        raise PermissionDenied("اجازه بررسی این خانواده تحویل مالی حقوق را ندارید.")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYROLL_RESULTS_VIEW)
@require_GET
def workbench(request: HttpRequest) -> HttpResponse:
    results = _scoped_results(request)
    run_ids = results.values_list("run_id", flat=True)
    runs = (
        PayrollRun.objects.filter(organization=request.organization, pk__in=run_ids)
        .select_related("period", "created_by", "reviewed_by", "finalized_by")
        .distinct()[:30]
    )
    exceptions = PayrollException.objects.filter(
        organization=request.organization,
        run_id__in=run_ids,
        is_resolved=False,
    ).select_related("run", "run_employee", "run_employee__employee")[:30]
    return render(
        request,
        "payroll/workbench.html",
        {
            "runs": runs,
            "results": results[:40],
            "exceptions": exceptions,
            "periods": PayrollPeriod.objects.filter(organization=request.organization)[
                :20
            ],
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYROLL_CONFIGURATION_VIEW)
@require_GET
def configuration(request: HttpRequest) -> HttpResponse:
    organization = request.organization
    membership = get_active_membership(user=request.user, organization=organization)
    employment_configurations = scope_queryset(
        EmploymentPayConfiguration.objects.filter(
            organization=organization
        ).select_related("employee", "project", "site"),
        membership=membership,
        project_lookup="project_id",
        site_lookup="site_id",
    )
    rules = scope_queryset(
        PayrollRule.objects.filter(organization=organization).select_related(
            "component", "basis_component", "project", "site"
        ),
        membership=membership,
        project_lookup="project_id",
        site_lookup="site_id",
    )
    return render(
        request,
        "payroll/configuration.html",
        {
            "employment_configurations": employment_configurations[:50],
            "components": PayrollComponent.objects.filter(organization=organization)[
                :50
            ],
            "rules": rules[:50],
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYROLL_CONFIGURATION_MANAGE)
def employment_configuration_create(request: HttpRequest) -> HttpResponse:
    form = EmploymentConfigurationForm(
        request.POST or None, organization=request.organization
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data.copy()
        data["evidence"] = data.pop("evidence_json")
        try:
            services.create_employment_configuration(
                organization=request.organization, actor=request.user, **data
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(request, "نسخه پیش‌نویس پیکربندی پرداخت ثبت شد.")
            return redirect("payroll:configuration")
    return _form_page(
        request,
        form=form,
        title="پیکربندی پرداخت کارمند",
        description="مدل پرداخت یک دسته پیکربندی کسب‌وکار است و تفسیر قانونی ایجاد نمی‌کند.",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYROLL_CONFIGURATION_MANAGE)
@require_POST
def employment_configuration_activate(
    request: HttpRequest, configuration_id
) -> HttpResponse:
    item = get_object_or_404(
        EmploymentPayConfiguration,
        pk=configuration_id,
        organization=request.organization,
    )
    try:
        services.activate_employment_configuration(
            organization=request.organization, actor=request.user, configuration=item
        )
        messages.success(request, "نسخه پیکربندی پرداخت فعال شد.")
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, _error_message(exc))
    return redirect("payroll:configuration")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYROLL_CONFIGURATION_MANAGE)
def component_create(request: HttpRequest) -> HttpResponse:
    form = ComponentForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            services.create_component(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(request, "جزء حقوق ثبت شد.")
            return redirect("payroll:configuration")
    return _form_page(
        request,
        form=form,
        title="جزء جدید حقوق",
        description="اجزای قانونی رزروشده در Core Payroll قابل فعال‌سازی نیستند.",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYROLL_CONFIGURATION_MANAGE)
def rule_create(request: HttpRequest) -> HttpResponse:
    form = RuleForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data.copy()
        data["evidence"] = data.pop("evidence_json")
        try:
            services.create_rule(
                organization=request.organization, actor=request.user, **data
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(request, "نسخه پیش‌نویس قاعده ثبت شد.")
            return redirect("payroll:configuration")
    return _form_page(
        request,
        form=form,
        title="قاعده جدید حقوق",
        description="فقط روش‌های محدود، نسخه‌دار و قابل بازتولید پذیرفته می‌شوند؛ کد آزاد اجرایی وجود ندارد.",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYROLL_CONFIGURATION_MANAGE)
@require_POST
def rule_activate(request: HttpRequest, rule_id) -> HttpResponse:
    rule = get_object_or_404(PayrollRule, pk=rule_id, organization=request.organization)
    try:
        services.activate_rule(
            organization=request.organization, actor=request.user, rule=rule
        )
        messages.success(request, "نسخه قاعده فعال شد.")
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, _error_message(exc))
    return redirect("payroll:configuration")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYROLL_PREPARE)
def period_create(request: HttpRequest) -> HttpResponse:
    form = PeriodForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            services.create_period(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(request, "دوره حقوق ثبت شد.")
            return redirect("payroll:workbench")
    return _form_page(
        request,
        form=form,
        title="دوره حقوق",
        description="تقویم قانونی یا دوره پیش‌فرض استنباط نمی‌شود؛ شروع، پایان و cutoff صریح‌اند.",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYROLL_PREPARE)
def run_create(request: HttpRequest) -> HttpResponse:
    form = RunForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            run = services.create_run(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(request, "اجرای حقوق با کارکنان صریح ثبت شد.")
            return redirect("payroll:run_detail", run_id=run.pk)
    return _form_page(
        request,
        form=form,
        title="اجرای جدید حقوق",
        description="هیچ کارمند یا ورودی به‌صورت ضمنی انتخاب نمی‌شود.",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYROLL_RESULTS_VIEW)
@require_GET
def run_detail(request: HttpRequest, run_id) -> HttpResponse:
    scoped = _scoped_results(request).filter(run_id=run_id)
    if not scoped.exists():
        raise PermissionDenied("نتیجه‌ای در دامنه مجاز این اجرا وجود ندارد.")
    run = get_object_or_404(
        PayrollRun.objects.select_related(
            "period", "predecessor", "reversal_of", "replaces"
        ),
        pk=run_id,
        organization=request.organization,
    )
    return render(
        request,
        "payroll/run_detail.html",
        {
            "run": run,
            "results": scoped.prefetch_related(
                "lines__component", "exceptions", "payslip"
            ),
            "exceptions": PayrollException.objects.filter(
                run=run, run_employee__in=scoped
            ).select_related("run_employee__employee"),
            "reversal_form": ReversalForm(),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYROLL_PREPARE)
def input_create(request: HttpRequest, run_id) -> HttpResponse:
    run = get_object_or_404(PayrollRun, pk=run_id, organization=request.organization)
    form = InputForm(request.POST or None, organization=request.organization, run=run)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data.copy()
        data["source_payload"] = data.pop("source_payload_json")
        try:
            services.record_input(
                organization=request.organization,
                actor=request.user,
                run=run,
                **data,
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(request, "ورودی صریح حقوق ثبت شد.")
            return redirect("payroll:run_detail", run_id=run.pk)
    return _form_page(
        request,
        form=form,
        title="ورودی حقوق",
        description="فقط منبع صریح با وضعیت تأیید یا قطعی و snapshot کامل پذیرفته می‌شود.",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYROLL_ADJUST)
def adjustment_create(request: HttpRequest, run_id) -> HttpResponse:
    run = get_object_or_404(PayrollRun, pk=run_id, organization=request.organization)
    form = AdjustmentForm(
        request.POST or None, organization=request.organization, run=run
    )
    if request.method == "POST" and form.is_valid():
        try:
            services.record_adjustment(
                organization=request.organization,
                actor=request.user,
                run=run,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(request, "تعدیل صریح ثبت شد؛ تاریخ قطعی پیشین تغییر نکرد.")
            return redirect("payroll:run_detail", run_id=run.pk)
    return _form_page(
        request,
        form=form,
        title="معوقه یا تعدیل",
        description="تعدیل رکورد مستقل و قابل ممیزی است و نتیجه قطعی گذشته را بازنویسی نمی‌کند.",
    )


def _run_action(request: HttpRequest, run_id, action, success: str) -> HttpResponse:
    run = get_object_or_404(PayrollRun, pk=run_id, organization=request.organization)
    try:
        action(organization=request.organization, actor=request.user, run=run)
        messages.success(request, success)
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, _error_message(exc))
    return redirect("payroll:run_detail", run_id=run.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYROLL_PREPARE)
@require_POST
def run_lock(request: HttpRequest, run_id) -> HttpResponse:
    return _run_action(
        request, run_id, services.lock_run_inputs, "ورودی‌ها snapshot و قفل شدند."
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYROLL_PREPARE)
@require_POST
def run_calculate(request: HttpRequest, run_id) -> HttpResponse:
    return _run_action(request, run_id, services.calculate_run, "اجرای حقوق محاسبه شد.")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYROLL_PREPARE)
@require_POST
def run_submit(request: HttpRequest, run_id) -> HttpResponse:
    return _run_action(
        request, run_id, services.submit_run_for_review, "اجرا برای بررسی ارسال شد."
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYROLL_REVIEW)
@require_POST
def run_approve(request: HttpRequest, run_id) -> HttpResponse:
    return _run_action(request, run_id, services.approve_run, "اجرا تأیید شد.")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYROLL_FINALIZE)
@require_POST
def run_finalize(request: HttpRequest, run_id) -> HttpResponse:
    return _run_action(
        request, run_id, services.finalize_run, "اجرا قطعی و فیش‌ها صادر شد."
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYROLL_ADJUST)
@require_POST
def run_reverse(request: HttpRequest, run_id) -> HttpResponse:
    run = get_object_or_404(PayrollRun, pk=run_id, organization=request.organization)
    form = ReversalForm(request.POST)
    if not form.is_valid():
        messages.error(request, "دلیل و کلید تکرارناپذیری معتبر الزامی است.")
        return redirect("payroll:run_detail", run_id=run.pk)
    try:
        reversal = services.reverse_run(
            organization=request.organization,
            actor=request.user,
            original_run=run,
            **form.cleaned_data,
        )
        messages.success(request, "برگشت قطعی و lineage جایگزین ثبت شد.")
        target = reversal.replacement_run or reversal.reversal_run
        return redirect("payroll:run_detail", run_id=target.pk)
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, _error_message(exc))
        return redirect("payroll:run_detail", run_id=run.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYSLIPS_VIEW)
@require_GET
def payslip_detail(request: HttpRequest, payslip_id) -> HttpResponse:
    payslip = get_object_or_404(
        Payslip.objects.select_related(
            "run",
            "run__period",
            "run_employee",
            "run_employee__employee",
            "run_employee__project",
            "run_employee__site",
        ),
        pk=payslip_id,
        organization=request.organization,
    )
    services.view_payslip(
        organization=request.organization, actor=request.user, payslip=payslip
    )
    return render(
        request,
        "payroll/payslip.html",
        {"payslip": payslip, "data": payslip.presentation_snapshot},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYSLIPS_EXPORT)
@require_POST
def payslip_export(request: HttpRequest, payslip_id) -> HttpResponse:
    payslip = get_object_or_404(
        Payslip.objects.select_related("run_employee__project", "run_employee__site"),
        pk=payslip_id,
        organization=request.organization,
    )
    payload = services.export_payslip(
        organization=request.organization, actor=request.user, payslip=payslip
    )
    response = HttpResponse(
        json.dumps(payload, ensure_ascii=False, indent=2),
        content_type="application/json; charset=utf-8",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="payslip-{payslip.number}.json"'
    )
    return response


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYROLL_AUDIT_VIEW)
@require_GET
def audit_history(request: HttpRequest) -> HttpResponse:
    events = AuditEvent.objects.filter(
        organization=request.organization, action__startswith="payroll."
    ).exclude(action__startswith="payroll.statutory_").select_related("actor")[:100]
    return render(request, "payroll/audit_history.html", {"events": events})


@active_organization_required
@organization_permission_required(
    BusinessPermissionCode.PAYROLL_STATUTORY_CONFIGURATION_VIEW
)
@require_GET
def statutory_policies(request: HttpRequest) -> HttpResponse:
    codes = (
        PAYROLL_TAX_REGULATORY_POLICY_CODE,
        EMPLOYEE_INSURANCE_REGULATORY_POLICY_CODE,
        PAYROLL_TAX_OUTPUT_SCHEMA_POLICY_CODE,
        EMPLOYEE_INSURANCE_OUTPUT_SCHEMA_POLICY_CODE,
    )
    policies = PlatformPolicy.objects.filter(code__in=codes)
    versions = PlatformPolicyVersion.objects.filter(
        policy__code__in=codes
    ).select_related("policy", "published_by")
    return render(
        request,
        "payroll/statutory_policies.html",
        {
            "policies": policies,
            "versions": versions,
            "missing_codes": set(codes) - set(policies.values_list("code", flat=True)),
        },
    )


@active_organization_required
@require_GET
def statutory_workbench(request: HttpRequest) -> HttpResponse:
    _require_any_statutory_permission(request)
    visible_run_ids = _scoped_results(request).values_list("run_id", flat=True)
    calculations = (
        StatutoryCalculation.objects.filter(
            organization=request.organization, run_id__in=visible_run_ids
        )
        .select_related(
            "run", "run__period", "policy_version", "prepared_by", "corrects"
        )
        .prefetch_related("employee_results")[:50]
    )
    outputs = (
        StatutoryOutput.objects.filter(
            organization=request.organization,
            calculation__run_id__in=visible_run_ids,
        )
        .select_related("calculation", "schema_version", "corrects", "reconciliation")
        .prefetch_related("export_evidence")[:50]
    )
    return render(
        request,
        "payroll/statutory_workbench.html",
        {"calculations": calculations, "outputs": outputs},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYROLL_STATUTORY_PREPARE)
def statutory_calculation_create(request: HttpRequest) -> HttpResponse:
    form = StatutoryCalculationForm(
        request.POST or None, organization=request.organization
    )
    if request.method == "POST" and form.is_valid():
        try:
            statutory_services.calculate_statutory(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(request, "محاسبه مقرراتی نسخه‌پین‌شده ثبت شد.")
            return redirect("payroll:statutory_workbench")
    return _form_page(
        request,
        form=form,
        title="محاسبه مقرراتی حقوق",
        description="فقط اجرای قطعی و نسخه منتشرشده، منبع‌دار و بازبینی‌شده پلتفرم مصرف می‌شود.",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYROLL_STATUTORY_PREPARE)
def statutory_identity_create(request: HttpRequest) -> HttpResponse:
    form = StatutoryIdentityForm(
        request.POST or None, organization=request.organization
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data.copy()
        data["identifiers"] = data.pop("identifiers_json")
        try:
            statutory_services.record_statutory_identity(
                organization=request.organization,
                actor=request.user,
                **data,
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(request, "شاهد نسخه‌دار شناسه رسمی ثبت شد.")
            return redirect("payroll:statutory_workbench")
    return _form_page(
        request,
        form=form,
        title="ثبت شناسه رسمی کارفرما/کارگاه یا کارمند",
        description="فقط کلیدهایی پذیرفته می‌شوند که نسخه طرح رسمی منتشرشده صریحاً مجاز کرده باشد.",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYROLL_STATUTORY_REVIEW)
def statutory_calculation_review(request: HttpRequest, calculation_id) -> HttpResponse:
    calculation = get_object_or_404(
        StatutoryCalculation,
        pk=calculation_id,
        organization=request.organization,
    )
    form = StatutoryReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            statutory_services.review_statutory_calculation(
                organization=request.organization,
                actor=request.user,
                calculation=calculation,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(request, "شاهد بررسی تغییرناپذیر ثبت شد.")
            return redirect("payroll:statutory_workbench")
    return _form_page(
        request,
        form=form,
        title="بررسی محاسبه مقرراتی",
        description="نتیجه بررسی مستقل از رکورد محاسبه و تغییرناپذیر نگهداری می‌شود.",
    )


@active_organization_required
@organization_permission_required(
    BusinessPermissionCode.PAYROLL_STATUTORY_OUTPUT_GENERATE
)
def statutory_output_generate(request: HttpRequest, calculation_id) -> HttpResponse:
    calculation = get_object_or_404(
        StatutoryCalculation,
        pk=calculation_id,
        organization=request.organization,
    )
    form = StatutoryOutputForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            statutory_services.generate_statutory_output(
                organization=request.organization,
                actor=request.user,
                calculation=calculation,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(request, "خروجی رسمی نسخه‌پین‌شده و تطبیق آن ثبت شد.")
            return redirect("payroll:statutory_workbench")
    return _form_page(
        request,
        form=form,
        title="تولید خروجی مقرراتی",
        description="نبود طرح رسمی منتشرشده یا فیلد الزامی، تولید را fail-closed متوقف می‌کند.",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYROLL_STATUTORY_EXPORT)
def statutory_export_record(request: HttpRequest, output_id) -> HttpResponse:
    output = get_object_or_404(
        StatutoryOutput, pk=output_id, organization=request.organization
    )
    form = StatutoryExportForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            statutory_services.record_export_evidence(
                organization=request.organization,
                actor=request.user,
                output=output,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(request, "شاهد provider-neutral خروجی ثبت شد.")
            return redirect("payroll:statutory_workbench")
    return _form_page(
        request,
        form=form,
        title="ثبت شاهد خروجی/ارسال",
        description="این فرم انتقال زنده انجام نمی‌دهد و فقط شاهد تغییرناپذیر را نگه می‌دارد.",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PAYROLL_STATUTORY_CORRECT)
def statutory_export_resolve(request: HttpRequest, evidence_id) -> HttpResponse:
    evidence = get_object_or_404(
        StatutoryExportEvidence,
        pk=evidence_id,
        organization=request.organization,
    )
    form = StatutoryResolutionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            statutory_services.resolve_export_evidence(
                organization=request.organization,
                actor=request.user,
                evidence=evidence,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(request, "تعیین تکلیف انسانی ثبت شد.")
            return redirect("payroll:statutory_workbench")
    return _form_page(
        request,
        form=form,
        title="تعیین تکلیف خطا یا رد",
        description="حل انسانی append-only است و نتیجه قبلی را بازنویسی نمی‌کند.",
    )


@active_organization_required
@require_GET
def financial_handoff_workbench(request: HttpRequest) -> HttpResponse:
    allowed_families = _allowed_financial_handoff_families(request)
    proposals = (
        FinancialHandoffProposal.objects.filter(
            organization=request.organization, family__in=allowed_families
        )
        .select_related("run", "predecessor", "prepared_by")
        .prefetch_related("reconciliations")
    )
    return render(
        request, "payroll/financial_handoff_workbench.html", {"proposals": proposals}
    )


@active_organization_required
def financial_handoff_prepare(request: HttpRequest) -> HttpResponse:
    allowed_families = _allowed_financial_handoff_families(request)
    form = FinancialHandoffPrepareForm(
        request.POST or None,
        organization=request.organization,
        allowed_families=allowed_families,
    )
    if request.method == "POST" and form.is_valid():
        try:
            proposal = financial_handoff_services.prepare_financial_handoff(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(
                request, "پیشنهاد تغییرناپذیر ثبت شد؛ هیچ اثر مالی پایین‌دست ایجاد نشد."
            )
            return redirect("payroll:financial_handoff_detail", proposal_id=proposal.pk)
    return _form_page(
        request,
        form=form,
        title="تهیه تحویل مالی حقوق",
        description="خروجی فقط پیشنهاد Payroll است و AP، دفترکل، خزانه یا هزینه واقعی پروژه را تغییر نمی‌دهد.",
    )


@active_organization_required
@require_GET
def financial_handoff_detail(request: HttpRequest, proposal_id) -> HttpResponse:
    proposal = get_object_or_404(
        FinancialHandoffProposal.objects.select_related(
            "run", "predecessor", "prepared_by"
        ).prefetch_related("lines__employee", "reconciliations"),
        pk=proposal_id,
        organization=request.organization,
    )
    _require_financial_handoff_family(request, proposal.family)
    return render(
        request, "payroll/financial_handoff_detail.html", {"proposal": proposal}
    )


@active_organization_required
def financial_handoff_review(request: HttpRequest, proposal_id) -> HttpResponse:
    proposal = get_object_or_404(
        FinancialHandoffProposal, pk=proposal_id, organization=request.organization
    )
    _require_financial_handoff_review(request, proposal.family)
    form = FinancialHandoffReviewForm(
        request.POST or None, organization=request.organization
    )
    if request.method == "POST" and form.is_valid():
        try:
            financial_handoff_services.review_financial_handoff(
                organization=request.organization,
                actor=request.user,
                proposal=proposal,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(request, "شاهد بررسی تغییرناپذیر ثبت شد.")
            return redirect("payroll:financial_handoff_detail", proposal_id=proposal.pk)
    return _form_page(
        request,
        form=form,
        title="بررسی پیشنهاد تحویل مالی",
        description="پیشنهاد دارای استثنا fail-closed است و قابل پذیرش نیست.",
    )


@active_organization_required
@organization_permission_required(
    BusinessPermissionCode.PAYROLL_HANDOFF_RECONCILIATION_PREPARE
)
@require_POST
def financial_handoff_reconcile(request: HttpRequest, proposal_id) -> HttpResponse:
    proposal = get_object_or_404(
        FinancialHandoffProposal, pk=proposal_id, organization=request.organization
    )
    try:
        financial_handoff_services.reconcile_financial_handoff(
            organization=request.organization, actor=request.user, proposal=proposal
        )
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, _error_message(exc))
    else:
        messages.success(request, "تطبیق شاهدی ثبت شد؛ هیچ مانده‌ای اصلاح نشد.")
    return redirect("payroll:financial_handoff_detail", proposal_id=proposal.pk)
