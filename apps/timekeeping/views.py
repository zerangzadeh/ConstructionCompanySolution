from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.organizations.authorization import get_active_membership, scope_queryset
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode

from . import services
from .forms import (
    AttendanceCorrectionForm,
    AttendanceForm,
    CalendarForm,
    HolidayForm,
    ImportForm,
    LeaveMissionForm,
    OvertimeForm,
    ShiftBreakForm,
    ShiftForm,
    TimesheetEntryForm,
    TimesheetForm,
)
from .models import (
    AttendanceCorrectionRequest,
    AttendanceRecord,
    LeaveMissionRequest,
    OvertimeRequest,
    Timesheet,
    WorkCalendar,
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
        "timekeeping/form.html",
        {"form": form, "title": title, "description": description},
    )


def _scoped(queryset, request: HttpRequest):
    membership = get_active_membership(
        user=request.user, organization=request.organization
    )
    return scope_queryset(
        queryset,
        membership=membership,
        project_lookup="project_id",
        site_lookup="site_id",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ATTENDANCE_VIEW)
@require_GET
def workbench(request: HttpRequest) -> HttpResponse:
    organization = request.organization
    attendance = _scoped(
        AttendanceRecord.objects.filter(organization=organization).select_related(
            "employee", "project", "site"
        ),
        request,
    )[:30]
    leave_mission = _scoped(
        LeaveMissionRequest.objects.filter(organization=organization).select_related(
            "employee", "project", "site"
        ),
        request,
    )[:20]
    overtime = _scoped(
        OvertimeRequest.objects.filter(organization=organization).select_related(
            "employee", "project", "site"
        ),
        request,
    )[:20]
    membership = get_active_membership(user=request.user, organization=organization)
    sheets = scope_queryset(
        Timesheet.objects.filter(organization=organization)
        .filter(entries__isnull=False)
        .select_related("employee")
        .distinct(),
        membership=membership,
        project_lookup="entries__project_id",
        site_lookup="entries__site_id",
    )[:20]
    corrections = scope_queryset(
        AttendanceCorrectionRequest.objects.filter(
            organization=organization, status="pending"
        ).select_related("attendance", "attendance__employee", "requested_by"),
        membership=membership,
        project_lookup="attendance__project_id",
        site_lookup="attendance__site_id",
    )[:20]
    return render(
        request,
        "timekeeping/workbench.html",
        {
            "calendars": WorkCalendar.objects.filter(organization=organization)[:20],
            "attendance_records": attendance,
            "correction_requests": corrections,
            "leave_mission_requests": leave_mission,
            "overtime_requests": overtime,
            "timesheets": sheets,
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TIME_CALENDARS_MANAGE)
def calendar_create(request: HttpRequest) -> HttpResponse:
    form = CalendarForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            services.create_work_calendar(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(request, "تقویم کاری ثبت شد.")
            return redirect("timekeeping:workbench")
    return _form_page(
        request,
        form=form,
        title="تقویم کاری جدید",
        description="روزهای کاری و بازه اعتبار تقویم را مشخص کنید. منطقه زمانی از تنظیمات شرکت خوانده می‌شود؛ تعطیلات قانونی به‌صورت پیش‌فرض ثبت نمی‌شوند.",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TIME_CALENDARS_MANAGE)
def shift_create(request: HttpRequest) -> HttpResponse:
    form = ShiftForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            services.create_shift(
                organization=request.organization,
                actor=request.user,
                breaks=(),
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(
                request,
                "شیفت کاری ثبت شد؛ دوره‌های استراحت باید از سرویس کنترل‌شده ثبت شوند.",
            )
            return redirect("timekeeping:workbench")
    return _form_page(
        request,
        form=form,
        title="شیفت کاری جدید",
        description="عبور از نیمه‌شب باید صریح باشد. دوره‌های استراحت به‌صورت رکورد مستقل و قطعی نگهداری می‌شوند.",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TIME_CALENDARS_MANAGE)
def holiday_create(request: HttpRequest) -> HttpResponse:
    form = HolidayForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            services.add_calendar_holiday(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(request, "روز تقویمی با منبع و دلیل ثبت شد.")
            return redirect("timekeeping:workbench")
    return _form_page(
        request,
        form=form,
        title="تعطیلی یا روز کاری جایگزین",
        description="هیچ تعطیلی قانونی به‌صورت پیش‌فرض استنباط نمی‌شود؛ منبع و دلیل در تاریخچه می‌ماند.",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TIME_CALENDARS_MANAGE)
def shift_break_create(request: HttpRequest) -> HttpResponse:
    form = ShiftBreakForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            services.add_shift_break(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(request, "بازه استراحت صریح ثبت شد.")
            return redirect("timekeeping:workbench")
    return _form_page(
        request,
        form=form,
        title="بازه استراحت شیفت",
        description="بازه باید کاملاً داخل شیفت باشد؛ پرداخت‌شونده بودن فقط تنظیم سیاست است و محاسبه حقوق ایجاد نمی‌کند.",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ATTENDANCE_CAPTURE)
def attendance_create(request: HttpRequest) -> HttpResponse:
    form = AttendanceForm(
        request.POST or None, organization=request.organization, user=request.user
    )
    if request.method == "POST" and form.is_valid():
        try:
            services.capture_attendance(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(request, "حضور برای بررسی ثبت شد.")
            return redirect("timekeeping:workbench")
    return _form_page(
        request,
        form=form,
        title="ثبت دستی حضور",
        description="ثبت دستی کنترل‌شده است و حضور قطعی فقط توسط بررسی‌کننده مستقل ایجاد می‌شود.",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ATTENDANCE_IMPORT)
def attendance_import(request: HttpRequest) -> HttpResponse:
    form = ImportForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data.copy()
        data["rows"] = data.pop("rows_json")
        try:
            batch = services.import_attendance(
                organization=request.organization, actor=request.user, **data
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(request, f"ورودی نگهداری شد: {batch.get_state_display()}")
            return redirect("timekeeping:workbench")
    return _form_page(
        request,
        form=form,
        title="درون‌ریزی حضور",
        description="این قرارداد فقط ردیف‌های نرمال‌شده و idempotent را می‌پذیرد؛ هیچ اتصال زنده دستگاه یا فراهم‌کننده‌ای فعال نیست.",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ATTENDANCE_REVIEW)
@require_POST
def attendance_finalize(request: HttpRequest, record_id) -> HttpResponse:
    record = get_object_or_404(
        AttendanceRecord, pk=record_id, organization=request.organization
    )
    try:
        services.finalize_attendance(
            organization=request.organization,
            actor=request.user,
            attendance=record,
            reconciliation_reason=request.POST.get("reason", ""),
        )
        messages.success(request, "حضور قطعی شد.")
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, _error_message(exc))
    return redirect("timekeeping:workbench")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ATTENDANCE_CORRECT)
def attendance_correction_create(request: HttpRequest, record_id) -> HttpResponse:
    record = get_object_or_404(
        AttendanceRecord, pk=record_id, organization=request.organization
    )
    form = AttendanceCorrectionForm(
        request.POST or None, organization=request.organization
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        replacement_values = {
            "work_date": data.get("replacement_work_date") or record.work_date,
            "check_in_at": data.get("replacement_check_in_at") or record.check_in_at,
            "check_out_at": data.get("replacement_check_out_at") or record.check_out_at,
        }
        try:
            services.request_attendance_correction(
                organization=request.organization,
                requester=request.user,
                attendance=record,
                reason=data["reason"],
                reversal=data["kind"] == "reversal",
                replacement_values=replacement_values,
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(request, "درخواست اصلاح برای بررسی مستقل ثبت شد.")
            return redirect("timekeeping:workbench")
    return _form_page(
        request,
        form=form,
        title="درخواست اصلاح حضور",
        description="اصل قطعی تغییر نمی‌کند؛ تأییدکننده مستقل رکورد جایگزین یا برگشت را ایجاد می‌کند.",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ATTENDANCE_CORRECT)
@require_POST
def attendance_correction_review(request: HttpRequest, correction_id) -> HttpResponse:
    correction = get_object_or_404(
        AttendanceCorrectionRequest,
        pk=correction_id,
        organization=request.organization,
    )
    try:
        services.review_attendance_correction(
            organization=request.organization,
            approver=request.user,
            correction_request=correction,
            approve=request.POST.get("decision") == "approve",
            review_reason=request.POST.get("reason", ""),
        )
        messages.success(request, "درخواست اصلاح تعیین تکلیف شد.")
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, _error_message(exc))
    return redirect("timekeeping:workbench")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.LEAVE_MISSION_REQUEST)
def leave_mission_create(request: HttpRequest) -> HttpResponse:
    form = LeaveMissionForm(
        request.POST or None, organization=request.organization, user=request.user
    )
    if request.method == "POST" and form.is_valid():
        try:
            services.create_leave_mission_request(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(request, "پیش‌نویس درخواست ثبت شد.")
            return redirect("timekeeping:workbench")
    return _form_page(
        request,
        form=form,
        title="درخواست مرخصی یا مأموریت",
        description="سامانه entitlement، ذخیره مرخصی یا حکم قانونی را استنباط نمی‌کند؛ تأیید به مرجع سیاست مصوب نیاز دارد.",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.LEAVE_MISSION_REQUEST)
@require_POST
def leave_mission_submit(request: HttpRequest, request_id) -> HttpResponse:
    item = get_object_or_404(
        LeaveMissionRequest, pk=request_id, organization=request.organization
    )
    try:
        services.submit_time_request(
            organization=request.organization, actor=request.user, request=item
        )
        messages.success(request, "درخواست ارسال شد.")
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, _error_message(exc))
    return redirect("timekeeping:workbench")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.LEAVE_MISSION_REVIEW)
@require_POST
def leave_mission_review(request: HttpRequest, request_id) -> HttpResponse:
    item = get_object_or_404(
        LeaveMissionRequest, pk=request_id, organization=request.organization
    )
    try:
        services.review_time_request(
            organization=request.organization,
            actor=request.user,
            request=item,
            approve=request.POST.get("decision") == "approve",
            reason=request.POST.get("reason", ""),
        )
        messages.success(request, "درخواست تعیین تکلیف شد.")
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, _error_message(exc))
    return redirect("timekeeping:workbench")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.OVERTIME_REQUEST)
def overtime_create(request: HttpRequest) -> HttpResponse:
    form = OvertimeForm(
        request.POST or None, organization=request.organization, user=request.user
    )
    if request.method == "POST" and form.is_valid():
        try:
            services.create_overtime_request(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(request, "پیش‌نویس اضافه‌کاری ثبت شد.")
            return redirect("timekeeping:workbench")
    return _form_page(
        request,
        form=form,
        title="درخواست اضافه‌کاری",
        description="هیچ ضریب، سقف، گردکردن یا اثر حقوقی/مالی بدون سیاست مصوب محاسبه نمی‌شود.",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.OVERTIME_REQUEST)
@require_POST
def overtime_submit(request: HttpRequest, request_id) -> HttpResponse:
    item = get_object_or_404(
        OvertimeRequest, pk=request_id, organization=request.organization
    )
    try:
        services.submit_time_request(
            organization=request.organization, actor=request.user, request=item
        )
        messages.success(request, "درخواست ارسال شد.")
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, _error_message(exc))
    return redirect("timekeeping:workbench")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.OVERTIME_REVIEW)
@require_POST
def overtime_review(request: HttpRequest, request_id) -> HttpResponse:
    item = get_object_or_404(
        OvertimeRequest, pk=request_id, organization=request.organization
    )
    try:
        services.review_time_request(
            organization=request.organization,
            actor=request.user,
            request=item,
            approve=request.POST.get("decision") == "approve",
            reason=request.POST.get("reason", ""),
        )
        messages.success(request, "درخواست تعیین تکلیف شد.")
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, _error_message(exc))
    return redirect("timekeeping:workbench")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TIMESHEETS_PREPARE)
def timesheet_create(request: HttpRequest) -> HttpResponse:
    form = TimesheetForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            sheet = services.create_timesheet(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            return redirect("timekeeping:timesheet_detail", timesheet_id=sheet.pk)
    return _form_page(
        request,
        form=form,
        title="کارکرد جدید",
        description="کارکرد محل مصرف زمان را ثبت می‌کند و حضور را تغییر نمی‌دهد.",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TIMESHEETS_VIEW)
def timesheet_detail(request: HttpRequest, timesheet_id) -> HttpResponse:
    membership = get_active_membership(
        user=request.user, organization=request.organization
    )
    scoped = scope_queryset(
        Timesheet.objects.filter(
            organization=request.organization, entries__isnull=False
        ).select_related("employee"),
        membership=membership,
        project_lookup="entries__project_id",
        site_lookup="entries__site_id",
    ).distinct()
    sheet = scoped.filter(pk=timesheet_id).first()
    if sheet is None:
        sheet = get_object_or_404(
            Timesheet,
            pk=timesheet_id,
            organization=request.organization,
            prepared_by=request.user,
            state="draft",
            entries__isnull=True,
        )
    form = TimesheetEntryForm(
        request.POST or None,
        organization=request.organization,
        user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        try:
            services.add_timesheet_entry(
                organization=request.organization,
                actor=request.user,
                timesheet=sheet,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_message(exc))
        else:
            messages.success(request, "ردیف تخصیص زمان ثبت شد.")
            return redirect("timekeeping:timesheet_detail", timesheet_id=sheet.pk)
    return render(
        request,
        "timekeeping/timesheet_detail.html",
        {
            "timesheet": sheet,
            "entries": sheet.entries.select_related("project", "site", "activity"),
            "form": form,
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TIMESHEETS_PREPARE)
@require_POST
def timesheet_submit(request: HttpRequest, timesheet_id) -> HttpResponse:
    sheet = get_object_or_404(
        Timesheet, pk=timesheet_id, organization=request.organization
    )
    try:
        services.submit_timesheet(
            organization=request.organization, actor=request.user, timesheet=sheet
        )
        messages.success(request, "کارکرد با تاریخچه تغییرناپذیر ارسال شد.")
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, _error_message(exc))
    return redirect("timekeeping:timesheet_detail", timesheet_id=sheet.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TIMESHEETS_REVIEW)
@require_POST
def timesheet_review(request: HttpRequest, timesheet_id) -> HttpResponse:
    sheet = get_object_or_404(
        Timesheet, pk=timesheet_id, organization=request.organization
    )
    try:
        services.review_timesheet(
            organization=request.organization,
            actor=request.user,
            timesheet=sheet,
            approve=request.POST.get("decision") == "approve",
            reason=request.POST.get("reason", ""),
        )
        messages.success(request, "کارکرد بررسی شد.")
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, _error_message(exc))
    return redirect("timekeeping:timesheet_detail", timesheet_id=sheet.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TIMESHEETS_PREVIEW)
@require_POST
def timesheet_preview(request: HttpRequest, timesheet_id) -> HttpResponse:
    sheet = get_object_or_404(
        Timesheet, pk=timesheet_id, organization=request.organization
    )
    try:
        services.generate_labor_distribution_preview(
            organization=request.organization, actor=request.user, timesheet=sheet
        )
        messages.success(
            request, "پیش‌نمایش غیرمالی و غیرقابل‌ارسال توزیع زمان نگهداری شد."
        )
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, _error_message(exc))
    return redirect("timekeeping:timesheet_detail", timesheet_id=sheet.pk)
