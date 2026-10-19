from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.equipment.cost_services import (
    create_cost_policy,
    create_cost_rate,
    finalize_cost_allocation,
    prepare_cost_allocation,
    prepare_cost_handoff,
    publish_cost_policy,
    reconcile_cost_handoff,
    reverse_cost_allocation,
    review_cost_handoff,
    review_cost_policy,
)
from apps.equipment.forms import (
    CostAllocationForm,
    CostAllocationReversalForm,
    CostHandoffForm,
    CostPolicyForm,
    CostRateForm,
    CostReconciliationForm,
    DowntimeForm,
    EquipmentAssignmentForm,
    EquipmentForm,
    EquipmentStatusForm,
    FuelForm,
    MaintenancePlanForm,
    MaintenanceRecordForm,
    MeterReadingForm,
    OperatorQualificationForm,
    SpareLinkForm,
    StatusTransitionForm,
    UsageForm,
    WorkOrderEvidenceForm,
    WorkOrderForm,
    WorkOrderTransitionForm,
)
from apps.equipment.models import (
    Equipment,
    EquipmentAssignmentStatus,
    EquipmentOwnershipType,
    EquipmentStatus,
    MaintenanceStatus,
    MaintenanceType,
)
from apps.equipment.p8_models import (
    DowntimeEvent,
    EquipmentCostAllocation,
    EquipmentCostPolicyVersion,
    EquipmentCostRate,
    EquipmentCostSourceEnvelope,
    EquipmentMeter,
    EquipmentUsageLog,
    EquipmentWorkOrder,
    FuelLog,
    MaintenancePlan,
    MeterReading,
    OperatorEquipmentQualification,
)
from apps.equipment.p8_services import (
    add_work_order_evidence,
    create_maintenance_plan,
    create_work_order,
    link_spare_part,
    record_downtime,
    record_fuel,
    record_meter_reading,
    record_operator_qualification,
    record_usage,
    transition_work_order,
)
from apps.equipment.services import (
    archive_equipment,
    assign_equipment,
    create_equipment,
    create_maintenance_record,
    get_organization_equipment,
    get_organization_equipment_assignments,
    get_organization_maintenance_records,
    transition_equipment_assignment_status,
    transition_equipment_status,
    transition_maintenance_status,
)
from apps.fixed_assets.workspace import equipment_financial_links
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


def _equipment(request: HttpRequest, equipment_id: str) -> Equipment | None:
    return (
        get_organization_equipment(user=request.user, organization=request.organization)
        .filter(pk=equipment_id)
        .first()
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EQUIPMENT_VIEW)
@require_GET
def equipment_list(request: HttpRequest) -> HttpResponse:
    equipment = get_organization_equipment(
        user=request.user, organization=request.organization
    )
    equipment = apply_table_filters(
        equipment,
        request,
        text_fields={"equipment": ("code", "name"), "category": ("category",)},
        choice_fields={
            "ownership": ("ownership_type", EquipmentOwnershipType.values),
            "status": ("status", EquipmentStatus.values),
        },
    )
    page = paginate_table(
        equipment,
        request,
        sort_fields={
            "equipment": ("name", "code"),
            "category": "category",
            "ownership": "ownership_type",
            "status": "status",
        },
        default_ordering=("name", "pk"),
    )
    return render(
        request,
        "equipment/list.html",
        {
            "equipment": page.object_list,
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "filters": build_table_filters(
                request,
                [
                    {"name": "equipment", "kind": "text", "label": "کد و نام"},
                    {"name": "category", "kind": "text", "label": "دسته"},
                    {
                        "name": "ownership",
                        "kind": "select",
                        "label": "مالکیت",
                        "choices": EquipmentOwnershipType.choices,
                    },
                    {
                        "name": "status",
                        "kind": "select",
                        "label": "وضعیت",
                        "choices": EquipmentStatus.choices,
                    },
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EQUIPMENT_OPERATIONS_VIEW)
@require_GET
def operations_workbench(request: HttpRequest) -> HttpResponse:
    """Read-only, permission-gated operational evidence workbench.

    Mutating command pages are deliberately separate services so normal navigation
    never bypasses the operation-specific permission checks.
    """
    organization = request.organization
    return render(
        request,
        "equipment/operations_workbench.html",
        {
            "meters": EquipmentMeter.objects.filter(
                organization=organization
            ).select_related("equipment"),
            "readings": MeterReading.objects.filter(
                organization=organization
            ).select_related("meter__equipment", "deployment")[:50],
            "qualifications": OperatorEquipmentQualification.objects.filter(
                organization=organization
            ).select_related("equipment", "employee", "workforce_qualification")[:50],
            "usage_logs": EquipmentUsageLog.objects.filter(
                organization=organization
            ).select_related("equipment", "deployment", "operator")[:50],
            "fuel_logs": FuelLog.objects.filter(
                organization=organization
            ).select_related("equipment", "inventory_transaction")[:50],
            "downtime_events": DowntimeEvent.objects.filter(
                organization=organization
            ).select_related("equipment", "deployment")[:50],
            "plans": MaintenancePlan.objects.filter(
                organization=organization
            ).select_related("equipment")[:50],
            "work_orders": EquipmentWorkOrder.objects.filter(organization=organization)
            .select_related("equipment", "plan", "deployment")
            .prefetch_related("spare_part_references__inventory_transaction")[:50],
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EQUIPMENT_COST_POLICY_VIEW)
@organization_permission_required(BusinessPermissionCode.EQUIPMENT_COST_ALLOCATION_VIEW)
@require_GET
def cost_workbench(request: HttpRequest) -> HttpResponse:
    organization = request.organization
    return render(
        request,
        "equipment/cost_workbench.html",
        {
            "policies": EquipmentCostPolicyVersion.objects.filter(
                organization=organization
            ).prefetch_related("rates")[:50],
            "rates": EquipmentCostRate.objects.filter(
                organization=organization
            ).select_related("equipment", "policy")[:50],
            "allocations": EquipmentCostAllocation.objects.filter(
                organization=organization
            ).select_related("usage__equipment", "project", "rate__policy")[:100],
            "envelopes": EquipmentCostSourceEnvelope.objects.filter(
                organization=organization
            ).select_related("allocation__usage__equipment")[:100],
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EQUIPMENT_COST_POLICY_MANAGE)
def cost_policy_create(request: HttpRequest) -> HttpResponse:
    return _operation_form(
        request,
        CostPolicyForm,
        "سیاست هزینه پیشنهادی تجهیز",
        create_cost_policy,
        back_url="equipment:cost_workbench",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EQUIPMENT_COST_POLICY_MANAGE)
def cost_rate_create(request: HttpRequest) -> HttpResponse:
    return _operation_form(
        request,
        CostRateForm,
        "نرخ داخلی تجهیز",
        create_cost_rate,
        back_url="equipment:cost_workbench",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EQUIPMENT_COST_POLICY_PUBLISH)
@require_POST
def cost_policy_transition(
    request: HttpRequest, policy_id: str, action: str
) -> HttpResponse:
    policy = EquipmentCostPolicyVersion.objects.filter(
        pk=policy_id, organization=request.organization
    ).first()
    if policy is None:
        return HttpResponseNotFound("سیاست یافت نشد.")
    service = (
        review_cost_policy
        if action == "review"
        else publish_cost_policy
        if action == "publish"
        else None
    )
    if service is None:
        return HttpResponseNotFound("اقدام معتبر نیست.")
    try:
        service(organization=request.organization, actor=request.user, policy=policy)
    except (PermissionDenied, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("equipment:cost_workbench")


@active_organization_required
@organization_permission_required(
    BusinessPermissionCode.EQUIPMENT_COST_ALLOCATION_PREPARE
)
def cost_allocation_create(request: HttpRequest) -> HttpResponse:
    return _operation_form(
        request,
        CostAllocationForm,
        "تخصیص پیشنهادی هزینه تجهیز",
        prepare_cost_allocation,
        back_url="equipment:cost_workbench",
    )


@active_organization_required
@organization_permission_required(
    BusinessPermissionCode.EQUIPMENT_COST_ALLOCATION_REVIEW
)
@require_POST
def cost_allocation_finalize(request: HttpRequest, allocation_id: str) -> HttpResponse:
    allocation = EquipmentCostAllocation.objects.filter(
        pk=allocation_id, organization=request.organization
    ).first()
    if allocation is None:
        return HttpResponseNotFound("تخصیص یافت نشد.")
    try:
        finalize_cost_allocation(
            organization=request.organization, actor=request.user, allocation=allocation
        )
    except (PermissionDenied, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("equipment:cost_workbench")


@active_organization_required
@organization_permission_required(
    BusinessPermissionCode.EQUIPMENT_COST_ALLOCATION_REVERSE
)
def cost_allocation_reverse(request: HttpRequest, allocation_id: str) -> HttpResponse:
    allocation = EquipmentCostAllocation.objects.filter(
        pk=allocation_id, organization=request.organization
    ).first()
    if allocation is None:
        return HttpResponseNotFound("تخصیص یافت نشد.")
    form = CostAllocationReversalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reverse_cost_allocation(
                organization=request.organization,
                actor=request.user,
                allocation=allocation,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("equipment:cost_workbench")
    return render(
        request,
        "equipment/form.html",
        {
            "form": form,
            "title": "برگشت تخصیص هزینه تجهیز",
            "back_url": "equipment:cost_workbench",
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EQUIPMENT_COST_HANDOFF_PREPARE)
def cost_handoff_create(request: HttpRequest) -> HttpResponse:
    return _operation_form(
        request,
        CostHandoffForm,
        "پیشنهاد منبع هزینه تجهیز",
        prepare_cost_handoff,
        back_url="equipment:cost_workbench",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EQUIPMENT_COST_HANDOFF_REVIEW)
@require_POST
def cost_handoff_review(request: HttpRequest, envelope_id: str) -> HttpResponse:
    envelope = EquipmentCostSourceEnvelope.objects.filter(
        pk=envelope_id, organization=request.organization
    ).first()
    if envelope is None:
        return HttpResponseNotFound("پیشنهاد یافت نشد.")
    try:
        review_cost_handoff(
            organization=request.organization, actor=request.user, envelope=envelope
        )
    except (PermissionDenied, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("equipment:cost_workbench")


@active_organization_required
@organization_permission_required(
    BusinessPermissionCode.EQUIPMENT_COST_HANDOFF_RECONCILE
)
def cost_handoff_reconcile(request: HttpRequest, envelope_id: str) -> HttpResponse:
    envelope = EquipmentCostSourceEnvelope.objects.filter(
        pk=envelope_id, organization=request.organization
    ).first()
    if envelope is None:
        return HttpResponseNotFound("پیشنهاد یافت نشد.")
    form = CostReconciliationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reconcile_cost_handoff(
                organization=request.organization,
                actor=request.user,
                envelope=envelope,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("equipment:cost_workbench")
    return render(
        request,
        "equipment/form.html",
        {
            "form": form,
            "title": "تطبیق پیشنهاد هزینه تجهیز",
            "back_url": "equipment:cost_workbench",
        },
    )


@active_organization_required
@organization_permission_required(
    BusinessPermissionCode.EQUIPMENT_QUALIFICATIONS_MANAGE
)
def operator_qualification_create(request: HttpRequest) -> HttpResponse:
    form = OperatorQualificationForm(
        request.POST or None, organization=request.organization
    )
    if request.method == "POST" and form.is_valid():
        try:
            record_operator_qualification(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("equipment:operations_workbench")
    return render(
        request,
        "equipment/form.html",
        {
            "form": form,
            "title": "صلاحیت اپراتور تجهیز",
            "back_url": "equipment:operations_workbench",
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EQUIPMENT_DOWNTIME_MANAGE)
def downtime_create(request: HttpRequest) -> HttpResponse:
    form = DowntimeForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            record_downtime(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("equipment:operations_workbench")
    return render(
        request,
        "equipment/form.html",
        {
            "form": form,
            "title": "ثبت توقف تجهیز",
            "back_url": "equipment:operations_workbench",
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EQUIPMENT_WORK_ORDERS_MANAGE)
def work_order_evidence_create(
    request: HttpRequest, work_order_id: str
) -> HttpResponse:
    order = EquipmentWorkOrder.objects.filter(
        organization=request.organization, pk=work_order_id
    ).first()
    if order is None:
        return HttpResponseNotFound("دستورکار یافت نشد.")
    form = WorkOrderEvidenceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            add_work_order_evidence(
                organization=request.organization,
                actor=request.user,
                work_order=order,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("equipment:operations_workbench")
    return render(
        request,
        "equipment/form.html",
        {
            "form": form,
            "title": "شاهد اجرای دستورکار",
            "back_url": "equipment:operations_workbench",
        },
    )


def _operation_form(
    request,
    form_class,
    title,
    service,
    *,
    back_url="equipment:operations_workbench",
):
    form = form_class(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            service(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect(back_url)
    return render(
        request,
        "equipment/form.html",
        {"form": form, "title": title, "back_url": back_url},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EQUIPMENT_METERS_RECORD)
def meter_reading_create(request: HttpRequest) -> HttpResponse:
    return _operation_form(
        request, MeterReadingForm, "ثبت یا اصلاح قرائت کنتور", record_meter_reading
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EQUIPMENT_USAGE_RECORD)
def usage_create(request: HttpRequest) -> HttpResponse:
    return _operation_form(request, UsageForm, "ثبت کارکرد تجهیز", record_usage)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EQUIPMENT_FUEL_RECORD)
def fuel_create(request: HttpRequest) -> HttpResponse:
    return _operation_form(request, FuelForm, "ثبت سوخت تجهیز", record_fuel)


@active_organization_required
@organization_permission_required(
    BusinessPermissionCode.EQUIPMENT_MAINTENANCE_PLANS_MANAGE
)
def maintenance_plan_create(request: HttpRequest) -> HttpResponse:
    return _operation_form(
        request, MaintenancePlanForm, "برنامه نگهداری", create_maintenance_plan
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EQUIPMENT_WORK_ORDERS_MANAGE)
def work_order_create(request: HttpRequest) -> HttpResponse:
    return _operation_form(
        request, WorkOrderForm, "دستورکار نگهداری", create_work_order
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EQUIPMENT_WORK_ORDERS_COMPLETE)
def work_order_transition(request: HttpRequest, work_order_id: str) -> HttpResponse:
    order = EquipmentWorkOrder.objects.filter(
        organization=request.organization, pk=work_order_id
    ).first()
    if order is None:
        return HttpResponseNotFound("دستورکار یافت نشد.")
    form = WorkOrderTransitionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            transition_work_order(
                organization=request.organization,
                actor=request.user,
                work_order=order,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("equipment:operations_workbench")
    return render(
        request,
        "equipment/status_form.html",
        {
            "form": form,
            "title": "تغییر وضعیت دستورکار",
            "back_url": "equipment:operations_workbench",
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EQUIPMENT_SPARE_LINKS_MANAGE)
def spare_link_create(request: HttpRequest, work_order_id: str) -> HttpResponse:
    order = EquipmentWorkOrder.objects.filter(
        organization=request.organization, pk=work_order_id
    ).first()
    if order is None:
        return HttpResponseNotFound("دستورکار یافت نشد.")
    form = SpareLinkForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            link_spare_part(
                organization=request.organization,
                actor=request.user,
                work_order=order,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("equipment:operations_workbench")
    return render(
        request,
        "equipment/form.html",
        {
            "form": form,
            "title": "پیوند تراکنش قطعه یدکی",
            "back_url": "equipment:operations_workbench",
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EQUIPMENT_CREATE)
def equipment_create(request: HttpRequest) -> HttpResponse:
    form = EquipmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            equipment = create_equipment(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("equipment:detail", equipment_id=equipment.pk)
    return render(
        request,
        "equipment/form.html",
        {"form": form, "title": "تجهیز جدید", "back_url": "equipment:list"},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EQUIPMENT_VIEW)
@require_GET
def equipment_detail(request: HttpRequest, equipment_id: str) -> HttpResponse:
    equipment = _equipment(request, equipment_id)
    if equipment is None:
        return HttpResponseNotFound("تجهیز یافت نشد.")
    assignments = get_organization_equipment_assignments(
        user=request.user, organization=request.organization, equipment=equipment
    )
    maintenance_records = get_organization_maintenance_records(
        user=request.user, organization=request.organization, equipment=equipment
    )
    return render(
        request,
        "equipment/detail.html",
        {
            "equipment": equipment,
            "assignments": assignments,
            "maintenance_records": maintenance_records,
            "status_form": EquipmentStatusForm(),
            "financial_asset_links": equipment_financial_links(
                organization=request.organization,
                actor=request.user,
                equipment=equipment,
            ),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EQUIPMENT_CHANGE_STATUS)
@require_POST
def equipment_status_change(request: HttpRequest, equipment_id: str) -> HttpResponse:
    equipment = _equipment(request, equipment_id)
    if equipment is None:
        return HttpResponseNotFound("تجهیز یافت نشد.")
    form = EquipmentStatusForm(request.POST)
    if form.is_valid():
        try:
            transition_equipment_status(
                organization=request.organization,
                actor=request.user,
                equipment=equipment,
                **form.cleaned_data,
            )
            messages.success(request, "وضعیت تجهیز تغییر کرد.")
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "وضعیت جدید را انتخاب کنید.")
    return redirect("equipment:detail", equipment_id=equipment_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EQUIPMENT_ARCHIVE)
@require_POST
def equipment_archive(request: HttpRequest, equipment_id: str) -> HttpResponse:
    equipment = _equipment(request, equipment_id)
    if equipment is None:
        return HttpResponseNotFound("تجهیز یافت نشد.")
    try:
        archive_equipment(
            organization=request.organization, actor=request.user, equipment=equipment
        )
        messages.success(request, "تجهیز بایگانی شد.")
        return redirect("equipment:list")
    except (PermissionDenied, ValueError) as exc:
        messages.error(request, str(exc))
        return redirect("equipment:detail", equipment_id=equipment_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EQUIPMENT_ASSIGNMENTS_VIEW)
@require_GET
def assignment_list(request: HttpRequest) -> HttpResponse:
    assignments = get_organization_equipment_assignments(
        user=request.user, organization=request.organization
    )
    assignments = apply_table_filters(
        assignments,
        request,
        text_fields={
            "equipment": ("equipment__code", "equipment__name"),
            "project": ("project__name", "site__name"),
        },
        choice_fields={"status": ("status", EquipmentAssignmentStatus.values)},
        date_fields={"start_date": "start_date"},
    )
    page = paginate_table(
        assignments,
        request,
        sort_fields={
            "equipment": "equipment__name",
            "project": "project__name",
            "start_date": "start_date",
            "status": "status",
        },
        default_ordering=("-start_date", "pk"),
    )
    return render(
        request,
        "equipment/assignment_list.html",
        {
            "assignments": page.object_list,
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "filters": build_table_filters(
                request,
                [
                    {"name": "equipment", "kind": "text", "label": "تجهیز"},
                    {"name": "project", "kind": "text", "label": "پروژه یا کارگاه"},
                    {"name": "start_date", "kind": "date_range", "label": "شروع تخصیص"},
                    {
                        "name": "status",
                        "kind": "select",
                        "label": "وضعیت",
                        "choices": EquipmentAssignmentStatus.choices,
                    },
                    None,
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EQUIPMENT_ASSIGNMENTS_CREATE)
def assignment_create(request: HttpRequest) -> HttpResponse:
    form = EquipmentAssignmentForm(
        request.POST or None, organization=request.organization
    )
    if request.method == "POST" and form.is_valid():
        try:
            assignment = assign_equipment(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "تخصیص تجهیز ثبت شد.")
            return redirect("equipment:detail", equipment_id=assignment.equipment_id)
    return render(
        request,
        "equipment/form.html",
        {"form": form, "title": "تخصیص تجهیز", "back_url": "equipment:assignment_list"},
    )


@active_organization_required
@organization_permission_required(
    BusinessPermissionCode.EQUIPMENT_ASSIGNMENTS_TRANSITION
)
def assignment_status_change(request: HttpRequest, assignment_id: str) -> HttpResponse:
    assignment = (
        get_organization_equipment_assignments(
            user=request.user, organization=request.organization
        )
        .filter(pk=assignment_id)
        .first()
    )
    if assignment is None:
        return HttpResponseNotFound("تخصیص تجهیز یافت نشد.")
    choices = {
        EquipmentAssignmentStatus.SCHEDULED: [
            (EquipmentAssignmentStatus.ACTIVE, "فعال"),
            (EquipmentAssignmentStatus.CANCELLED, "لغوشده"),
        ],
        EquipmentAssignmentStatus.ACTIVE: [
            (EquipmentAssignmentStatus.COMPLETED, "تکمیل‌شده"),
            (EquipmentAssignmentStatus.CANCELLED, "لغوشده"),
        ],
    }.get(assignment.status, [])
    form = StatusTransitionForm(request.POST or None, choices=choices)
    if request.method == "POST" and form.is_valid():
        try:
            transition_equipment_assignment_status(
                organization=request.organization,
                actor=request.user,
                assignment=assignment,
                **form.cleaned_data,
            )
            messages.success(request, "وضعیت تخصیص تغییر کرد.")
            return redirect("equipment:assignment_list")
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
    return render(
        request,
        "equipment/status_form.html",
        {
            "form": form,
            "title": "تغییر وضعیت تخصیص",
            "back_url": "equipment:assignment_list",
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.MAINTENANCE_RECORDS_VIEW)
@require_GET
def maintenance_list(request: HttpRequest) -> HttpResponse:
    records = get_organization_maintenance_records(
        user=request.user, organization=request.organization
    )
    records = apply_table_filters(
        records,
        request,
        text_fields={
            "record": ("record_number", "summary"),
            "equipment": ("equipment__code", "equipment__name"),
        },
        choice_fields={
            "maintenance_type": ("maintenance_type", MaintenanceType.values),
            "status": ("status", MaintenanceStatus.values),
        },
        date_fields={"scheduled_date": "scheduled_date"},
    )
    page = paginate_table(
        records,
        request,
        sort_fields={
            "record": ("record_number", "summary"),
            "equipment": "equipment__name",
            "scheduled_date": "scheduled_date",
            "status": "status",
        },
        default_ordering=("-scheduled_date", "pk"),
    )
    return render(
        request,
        "equipment/maintenance_list.html",
        {
            "records": page.object_list,
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "filters": build_table_filters(
                request,
                [
                    {"name": "record", "kind": "text", "label": "شماره و عنوان"},
                    {"name": "equipment", "kind": "text", "label": "تجهیز"},
                    {"name": "scheduled_date", "kind": "date_range", "label": "تاریخ"},
                    {
                        "name": "status",
                        "kind": "select",
                        "label": "وضعیت",
                        "choices": MaintenanceStatus.choices,
                    },
                    None,
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.MAINTENANCE_RECORDS_CREATE)
def maintenance_create(request: HttpRequest) -> HttpResponse:
    form = MaintenanceRecordForm(
        request.POST or None, organization=request.organization
    )
    if request.method == "POST" and form.is_valid():
        try:
            record = create_maintenance_record(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "سابقه سرویس یا تعمیر ثبت شد.")
            return redirect("equipment:detail", equipment_id=record.equipment_id)
    return render(
        request,
        "equipment/form.html",
        {
            "form": form,
            "title": "سابقه سرویس یا تعمیر",
            "back_url": "equipment:maintenance_list",
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.MAINTENANCE_RECORDS_TRANSITION)
def maintenance_status_change(request: HttpRequest, record_id: str) -> HttpResponse:
    record = (
        get_organization_maintenance_records(
            user=request.user, organization=request.organization
        )
        .filter(pk=record_id)
        .first()
    )
    if record is None:
        return HttpResponseNotFound("سابقه سرویس یا تعمیر یافت نشد.")
    choices = {
        MaintenanceStatus.SCHEDULED: [
            (MaintenanceStatus.IN_PROGRESS, "در حال انجام"),
            (MaintenanceStatus.COMPLETED, "تکمیل‌شده"),
            (MaintenanceStatus.CANCELLED, "لغوشده"),
        ],
        MaintenanceStatus.IN_PROGRESS: [
            (MaintenanceStatus.COMPLETED, "تکمیل‌شده"),
            (MaintenanceStatus.CANCELLED, "لغوشده"),
        ],
    }.get(record.status, [])
    form = StatusTransitionForm(
        request.POST or None, choices=choices, include_cost=True
    )
    if request.method == "POST" and form.is_valid():
        try:
            transition_maintenance_status(
                organization=request.organization,
                actor=request.user,
                record=record,
                **form.cleaned_data,
            )
            messages.success(request, "وضعیت سابقه سرویس تغییر کرد.")
            return redirect("equipment:maintenance_list")
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
    return render(
        request,
        "equipment/status_form.html",
        {
            "form": form,
            "title": "تغییر وضعیت سرویس یا تعمیر",
            "back_url": "equipment:maintenance_list",
        },
    )
