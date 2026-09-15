from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.equipment.forms import (
    EquipmentAssignmentForm,
    EquipmentForm,
    EquipmentStatusForm,
    MaintenanceRecordForm,
    StatusTransitionForm,
)
from apps.equipment.models import (
    Equipment,
    EquipmentAssignmentStatus,
    EquipmentOwnershipType,
    EquipmentStatus,
    MaintenanceStatus,
    MaintenanceType,
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
    return render(
        request,
        "equipment/list.html",
        {
            "equipment": equipment,
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
    return render(
        request,
        "equipment/assignment_list.html",
        {
            "assignments": assignments,
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
    return render(
        request,
        "equipment/maintenance_list.html",
        {
            "records": records,
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
