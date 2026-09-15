from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.daily_reports.forms import (
    DailyActivityForm,
    DailyReportEquipmentEntryForm,
    DailyReportForm,
    DailyReportLaborEntryForm,
    DailyReportMaterialEntryForm,
    DelayEventForm,
)
from apps.daily_reports.models import DailyReportStatus
from apps.daily_reports.services import (
    add_daily_activity,
    add_daily_report_equipment_entry,
    add_daily_report_labor_entry,
    add_daily_report_material_entry,
    add_delay_event,
    approve_daily_report,
    create_daily_report,
    get_organization_daily_report,
    get_organization_daily_reports,
    submit_daily_report,
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
@organization_permission_required(BusinessPermissionCode.DAILY_REPORTS_VIEW)
@require_GET
def daily_report_list(request: HttpRequest) -> HttpResponse:
    reports = get_organization_daily_reports(
        user=request.user,
        organization=request.organization,
    )
    reports = apply_table_filters(
        reports,
        request,
        text_fields={
            "project": ("project__name", "site__name"),
            "phase": ("phase__name",),
            "author": ("created_by__username",),
        },
        choice_fields={"status": ("status", DailyReportStatus.values)},
        date_fields={"reporting_date": "reporting_date"},
    )
    return render(
        request,
        "daily_reports/list.html",
        {
            "reports": reports,
            "filters": build_table_filters(
                request,
                [
                    {"name": "project", "kind": "text", "label": "پروژه و کارگاه"},
                    {"name": "phase", "kind": "text", "label": "فاز"},
                    {
                        "name": "reporting_date",
                        "kind": "date_range",
                        "label": "تاریخ گزارش",
                    },
                    {
                        "name": "status",
                        "kind": "select",
                        "label": "وضعیت",
                        "choices": DailyReportStatus.choices,
                    },
                    None,
                    {"name": "author", "kind": "text", "label": "نویسنده"},
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DAILY_REPORTS_CREATE)
def daily_report_create(request: HttpRequest) -> HttpResponse:
    form = DailyReportForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            report = create_daily_report(
                organization=request.organization,
                project=data["project"],
                site=data["site"],
                phase=data["phase"],
                actor=request.user,
                reporting_date=data["reporting_date"],
                work_performed=data["work_performed"],
                weather_conditions=data["weather_conditions"],
                labor_count=data["labor_count"],
                progress_summary=data["progress_summary"],
                issues_and_delays=data["issues_and_delays"],
                safety_notes=data["safety_notes"],
                quality_notes=data["quality_notes"],
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("daily_reports:detail", report_id=report.pk)
    return render(request, "daily_reports/create.html", {"form": form})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DAILY_REPORTS_VIEW)
@require_GET
def daily_report_detail(request: HttpRequest, report_id: str) -> HttpResponse:
    report = get_organization_daily_report(
        user=request.user,
        organization=request.organization,
        report_id=report_id,
    )
    return render(
        request,
        "daily_reports/detail.html",
        {
            "report": report,
            "labor_form": DailyReportLaborEntryForm(),
            "equipment_form": DailyReportEquipmentEntryForm(),
            "material_form": DailyReportMaterialEntryForm(
                organization_id=request.organization.id
            ),
            "daily_activity_form": DailyActivityForm(report=report),
            "delay_event_form": DelayEventForm(report=report),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DAILY_REPORTS_ADD_LABOR)
@require_POST
def daily_report_labor_add(request: HttpRequest, report_id: str) -> HttpResponse:
    form = DailyReportLaborEntryForm(request.POST)
    if form.is_valid():
        data = form.cleaned_data
        try:
            add_daily_report_labor_entry(
                organization=request.organization,
                report_id=report_id,
                actor=request.user,
                team_name=data["team_name"],
                worker_count=data["worker_count"],
                hours_worked=data["hours_worked"],
                notes=data["notes"],
            )
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "رکورد نیروی انسانی افزوده شد.")
    else:
        messages.error(request, "فیلدهای نیروی انسانی را بررسی و دوباره تلاش کنید.")
    return redirect("daily_reports:detail", report_id=report_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DAILY_REPORTS_ADD_EQUIPMENT)
@require_POST
def daily_report_equipment_add(request: HttpRequest, report_id: str) -> HttpResponse:
    form = DailyReportEquipmentEntryForm(request.POST)
    if form.is_valid():
        data = form.cleaned_data
        try:
            add_daily_report_equipment_entry(
                organization=request.organization,
                report_id=report_id,
                actor=request.user,
                equipment_name=data["equipment_name"],
                hours_used=data["hours_used"],
                notes=data["notes"],
            )
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "رکورد تجهیز افزوده شد.")
    else:
        messages.error(request, "فیلدهای تجهیز را بررسی و دوباره تلاش کنید.")
    return redirect("daily_reports:detail", report_id=report_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DAILY_REPORTS_ADD_MATERIAL)
@require_POST
def daily_report_material_add(request: HttpRequest, report_id: str) -> HttpResponse:
    form = DailyReportMaterialEntryForm(
        request.POST, organization_id=request.organization.id
    )
    if form.is_valid():
        data = form.cleaned_data
        try:
            add_daily_report_material_entry(
                organization=request.organization,
                report_id=report_id,
                actor=request.user,
                material_name=data["material_name"],
                quantity=data["quantity"],
                unit=data["unit"],
                notes=data["notes"],
                material=data["material"],
                unit_of_measure=data["unit_of_measure"],
            )
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "رکورد مصالح افزوده شد.")
    else:
        messages.error(request, "فیلدهای مصالح را بررسی و دوباره تلاش کنید.")
    return redirect("daily_reports:detail", report_id=report_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DAILY_REPORTS_ADD_ACTIVITY)
@require_POST
def daily_activity_add(request: HttpRequest, report_id: str) -> HttpResponse:
    report = get_organization_daily_report(
        user=request.user, organization=request.organization, report_id=report_id
    )
    form = DailyActivityForm(request.POST, report=report)
    if form.is_valid():
        try:
            add_daily_activity(
                organization=request.organization,
                report_id=report_id,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "رکورد فعالیت افزوده شد.")
    else:
        messages.error(request, "فیلدهای فعالیت را بررسی و دوباره تلاش کنید.")
    return redirect("daily_reports:detail", report_id=report_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DAILY_REPORTS_ADD_DELAY)
@require_POST
def delay_event_add(request: HttpRequest, report_id: str) -> HttpResponse:
    report = get_organization_daily_report(
        user=request.user, organization=request.organization, report_id=report_id
    )
    form = DelayEventForm(request.POST, report=report)
    if form.is_valid():
        try:
            add_delay_event(
                organization=request.organization,
                report_id=report_id,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "رویداد تأخیر افزوده شد.")
    else:
        messages.error(request, "فیلدهای رویداد تأخیر را بررسی و دوباره تلاش کنید.")
    return redirect("daily_reports:detail", report_id=report_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DAILY_REPORTS_SUBMIT)
@require_POST
def daily_report_submit(request: HttpRequest, report_id: str) -> HttpResponse:
    try:
        submit_daily_report(
            organization=request.organization,
            report_id=report_id,
            actor=request.user,
        )
    except (PermissionDenied, ValueError) as exc:
        return HttpResponse(str(exc), status=403)
    return redirect("daily_reports:detail", report_id=report_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DAILY_REPORTS_APPROVE)
@require_POST
def daily_report_approve(request: HttpRequest, report_id: str) -> HttpResponse:
    try:
        approve_daily_report(
            organization=request.organization,
            report_id=report_id,
            actor=request.user,
        )
    except (PermissionDenied, ValueError) as exc:
        return HttpResponse(str(exc), status=403)
    return redirect("daily_reports:detail", report_id=report_id)
