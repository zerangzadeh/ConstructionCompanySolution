from __future__ import annotations

from urllib.parse import parse_qsl, urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
    require_business_permission,
    scope_queryset,
)
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
    from apps.workforce.field_presentation import presentation_error

    return presentation_error(exc)


def _field_context(request):
    from apps.workforce.field_selectors import resolve_field_context

    return resolve_field_context(
        organization=request.organization,
        user=request.user,
        values=request.GET,
        include_employee=True,
    )


def _entry_form_kwargs(request):
    context = _field_context(request)
    return {
        "initial": {
            name: value
            for name, value in (
                ("project", context.project),
                ("site", context.site),
                ("employee", context.employee),
            )
            if value is not None
        }
    }


def _workbench_url(request):
    return _journey_url(request, "timekeeping:workbench")


def _journey_url(request, route, *args, context=None):
    query = _journey_query(
        request, context if context is not None else _field_context(request)
    )
    url = reverse(route, args=args)
    return f"{url}?{query}" if query else url


def _journey_query(request, context):
    query = dict(parse_qsl(context.query))
    for name in ("date_from", "date_to", "view", "month"):
        if request.GET.get(name):
            query[name] = request.GET[name][:32]
    return urlencode(query)


def _saved_record_url(request, record, kind, permission):
    from apps.workforce.field_selectors import FieldContext

    if has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.ATTENDANCE_VIEW,
        allow_any_scope=True,
    ):
        if has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=permission,
            project=record.project,
            site=record.site,
        ):
            context = FieldContext(
                project=record.project, site=record.site, employee=record.employee
            )
            return _journey_url(
                request, "timekeeping:record_detail", kind, record.pk, context=context
            )
        return _workbench_url(request)
    return reverse("home")


def _add_form_error(form, exc):
    if isinstance(exc, ValidationError) and hasattr(exc, "error_dict"):
        for name, errors in exc.error_dict.items():
            form.add_error(
                name if name in form.fields else None,
                _error_message(ValidationError(errors)),
            )
    else:
        form.add_error(None, _error_message(exc))


def _form_page(
    request: HttpRequest, *, form, title: str, description: str, submit_label=""
) -> HttpResponse:
    context = _field_context(request)
    _add_empty_choice_guidance(request, form, context)
    reference_name = "shift" if isinstance(form, ShiftBreakForm) else "calendar"
    reference_field = form.fields.get(reference_name)
    missing_reference = (
        reference_name
        if reference_field and not reference_field.queryset.exists()
        else None
    )
    return render(
        request,
        "timekeeping/compact_form.html"
        if request.resolver_match.url_name
        in {"calendar_create", "shift_create", "holiday_create", "shift_break_create"}
        else "timekeeping/form.html",
        {
            "form": form,
            "title": title,
            "description": description,
            "submit_label": submit_label,
            "missing_reference": missing_reference,
            "field_context": context,
            "back_url": _workbench_url(request)
            if has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.ATTENDANCE_VIEW,
                allow_any_scope=True,
            )
            else reverse("home"),
        },
    )


def _add_empty_choice_guidance(request, form, context):
    from apps.workforce.field_forms import choice_value
    from apps.workforce.field_presentation import timekeeping_empty_choice_action
    from apps.workforce.field_selectors import FieldContext

    if "employee" not in form.fields:
        return
    fields = ["employee", "shift"] if isinstance(form, AttendanceForm) else ["employee"]
    for name in fields:
        form.fields[name].widget.attrs["data-choice-purpose"] = "timekeeping"
    if form.is_bound:
        form.is_valid()  # Validate the submitted parents before using them in any link.
        parents = {name: form.cleaned_data.get(name) for name in ("project", "site")}
        if any(
            choice_value(form, name) and not parent
            for name, parent in parents.items() if name in form.fields
        ):
            return
        if "project" in form.fields:
            context = FieldContext(**parents)
    for name in fields:
        if name == "shift" and not getattr(form, "cleaned_data", {}).get("calendar"):
            continue
        field = form.fields[name]
        if not field.queryset.exists():
            field.widget.empty_notice = {
                "message": field.widget.attrs["data-empty-choices"],
                "action": timekeeping_empty_choice_action(request, name, context),
            }


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
    from apps.workforce.field_selectors import resolve_field_context

    from .field_history import history_context

    context = resolve_field_context(
        organization=request.organization,
        user=request.user,
        values=request.GET,
        include_employee=True,
    )
    data = history_context(request, context)
    if request.GET.get("format") == "xlsx":
        from .xlsx_exports import history_download

        return history_download(
            data, timezone_name=request.organization.settings.timezone
        )
    from core.list_filters import build_filter_bar

    history_form = data["history_form"]
    if not history_form.is_bound:
        history_form.cleaned_data = {}
    data["history_filter_bar"] = build_filter_bar(
        request,
        form=history_form,
        search_field="employee",
        quick_fields=("project", "site"),
        secondary_fields=("date_from", "date_to"),
        result_count=sum(
            data[key]["page"].paginator.count
            for key in (
                "attendance_page",
                "correction_page",
                "leave_page",
                "overtime_page",
                "timesheet_page",
            )
        ),
        result_label="سابقه",
        context={
            key: request.GET[key] for key in ("view", "month") if request.GET.get(key)
        },
    )
    data["history_query"] = _journey_query(request, context)
    data["calendars"] = WorkCalendar.objects.filter(
        organization=request.organization
    ).prefetch_related("shifts")[:20]
    from apps.workforce.field_presentation import cascade_filter_chips

    cascade_filter_chips(data["history_filter_bar"])
    return render(request, "timekeeping/workbench.html", data)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TIME_CALENDARS_MANAGE)
def calendar_create(request: HttpRequest) -> HttpResponse:
    form = CalendarForm(request.POST or None, organization=request.organization)
    if (
        request.method == "POST"
        and request.POST.get("_refresh_choices") != "1"
        and form.is_valid()
    ):
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
            return redirect(_workbench_url(request))
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
    if (
        request.method == "POST"
        and request.POST.get("_refresh_choices") != "1"
        and form.is_valid()
    ):
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
            return redirect(_workbench_url(request))
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
    if (
        request.method == "POST"
        and request.POST.get("_refresh_choices") != "1"
        and form.is_valid()
    ):
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
            return redirect(_workbench_url(request))
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
    if (
        request.method == "POST"
        and request.POST.get("_refresh_choices") != "1"
        and form.is_valid()
    ):
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
            return redirect(_workbench_url(request))
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
        request.POST or None,
        organization=request.organization,
        user=request.user,
        **_entry_form_kwargs(request),
    )
    if (
        request.method == "POST"
        and request.POST.get("_refresh_choices") != "1"
        and form.is_valid()
    ):
        try:
            record = services.capture_attendance(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            _add_form_error(form, exc)
        else:
            messages.success(request, "حضور برای بررسی ثبت شد.")
            return redirect(
                _saved_record_url(
                    request,
                    record,
                    "attendance",
                    BusinessPermissionCode.ATTENDANCE_VIEW,
                )
            )
    return _form_page(
        request,
        form=form,
        title="ثبت دستی حضور",
        description="زمان ورود و خروج واقعی نیروی کار را ثبت کنید. سابقه برای بررسی مستقل ذخیره می‌شود.",
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
            return redirect(_workbench_url(request))
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
    return redirect(_workbench_url(request))


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
            return redirect(_workbench_url(request))
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
    return redirect(_workbench_url(request))


@active_organization_required
@organization_permission_required(BusinessPermissionCode.LEAVE_MISSION_REQUEST)
def leave_mission_create(request: HttpRequest) -> HttpResponse:
    form = LeaveMissionForm(
        request.POST or None,
        organization=request.organization,
        user=request.user,
        **_entry_form_kwargs(request),
    )
    if (
        request.method == "POST"
        and request.POST.get("_refresh_choices") != "1"
        and form.is_valid()
    ):
        try:
            record = services.create_leave_mission_request(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            _add_form_error(form, exc)
        else:
            messages.success(request, "پیش‌نویس درخواست ثبت شد.")
            return redirect(
                _saved_record_url(
                    request, record, "leave", BusinessPermissionCode.LEAVE_MISSION_VIEW
                )
            )
    return _form_page(
        request,
        form=form,
        title="درخواست مرخصی یا مأموریت",
        description="نوع درخواست، بازه زمانی و دلیل را وارد کنید و پیش‌نویس را ذخیره کنید.",
        submit_label="ذخیره پیش‌نویس درخواست",
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
    return redirect(_workbench_url(request))


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
    return redirect(_workbench_url(request))


@active_organization_required
@organization_permission_required(BusinessPermissionCode.OVERTIME_REQUEST)
def overtime_create(request: HttpRequest) -> HttpResponse:
    form = OvertimeForm(
        request.POST or None,
        organization=request.organization,
        user=request.user,
        **_entry_form_kwargs(request),
    )
    if (
        request.method == "POST"
        and request.POST.get("_refresh_choices") != "1"
        and form.is_valid()
    ):
        try:
            record = services.create_overtime_request(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            _add_form_error(form, exc)
        else:
            messages.success(request, "پیش‌نویس اضافه‌کاری ثبت شد.")
            return redirect(
                _saved_record_url(
                    request, record, "overtime", BusinessPermissionCode.OVERTIME_VIEW
                )
            )
    return _form_page(
        request,
        form=form,
        title="درخواست اضافه‌کاری",
        description="بازه زمانی و دلیل اضافه‌کاری را برای بررسی ثبت کنید.",
        submit_label="ذخیره پیش‌نویس درخواست",
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
    return redirect(_workbench_url(request))


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
    return redirect(_workbench_url(request))


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TIMESHEETS_PREPARE)
def timesheet_create(request: HttpRequest) -> HttpResponse:
    form = TimesheetForm(
        request.POST or None,
        organization=request.organization,
        user=request.user,
        **_entry_form_kwargs(request),
    )
    if (
        request.method == "POST"
        and request.POST.get("_refresh_choices") != "1"
        and form.is_valid()
    ):
        try:
            sheet = services.create_timesheet(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            _add_form_error(form, exc)
        else:
            messages.success(request, "پیش‌نویس کارکرد ثبت شد.")
            if not has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.TIMESHEETS_VIEW,
                allow_any_scope=True,
            ):
                return redirect("home")
            return redirect(
                _journey_url(request, "timekeeping:timesheet_detail", sheet.pk)
            )
    return _form_page(
        request,
        form=form,
        title="کارکرد جدید",
        description="بازه گزارش و مدت کار را ثبت کنید. در مرحله بعد مدت را به پروژه یا فعالیت تخصیص دهید. کارکرد، حضور را تغییر نمی‌دهد.",
        submit_label="ذخیره و افزودن تخصیص",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TIMESHEETS_VIEW)
def timesheet_detail(request: HttpRequest, timesheet_id) -> HttpResponse:
    from .field_history import fully_scoped_timesheets

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
    sheet = fully_scoped_timesheets(scoped, membership).filter(pk=timesheet_id).first()
    if sheet is None:
        sheet = get_object_or_404(
            Timesheet,
            pk=timesheet_id,
            organization=request.organization,
            prepared_by=request.user,
            state="draft",
            entries__isnull=True,
        )
    form_kwargs = _entry_form_kwargs(request)
    if sheet.period_start == sheet.period_end:
        form_kwargs["initial"]["work_date"] = sheet.period_start
    form = TimesheetEntryForm(
        request.POST or None,
        organization=request.organization,
        user=request.user,
        **form_kwargs,
    )
    if (
        request.method == "POST"
        and request.POST.get("_refresh_choices") != "1"
        and form.is_valid()
    ):
        try:
            services.add_timesheet_entry(
                organization=request.organization,
                actor=request.user,
                timesheet=sheet,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            _add_form_error(form, exc)
        else:
            messages.success(request, "ردیف تخصیص زمان ثبت شد.")
            return redirect(
                _journey_url(request, "timekeeping:timesheet_detail", sheet.pk)
            )
    entries = list(sheet.entries.select_related("project", "site", "activity"))

    def can_act(permission):
        return has_business_permission(
            user=request.user, organization=request.organization, permission=permission
        ) and all(
            has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=permission,
                project=entry.project,
                site=entry.site,
            )
            for entry in entries
        )

    can_prepare = (
        sheet.state == "draft"
        and sheet.prepared_by_id == request.user.pk
        and can_act("timesheets.prepare")
    )
    allocated_minutes = sum(entry.minutes for entry in entries)
    return render(
        request,
        "timekeeping/timesheet_detail.html",
        {
            "timesheet": sheet,
            "entries": entries,
            "form": form,
            "field_context": _field_context(request),
            "history_query": _journey_query(request, _field_context(request)),
            "back_url": _workbench_url(request),
            "can_prepare": can_prepare,
            "can_submit": can_prepare
            and bool(entries)
            and allocated_minutes == sheet.declared_minutes,
            "can_review": sheet.state == "submitted"
            and request.user.pk not in (sheet.prepared_by_id, sheet.submitted_by_id)
            and can_act("timesheets.review"),
            "allocated_minutes": allocated_minutes,
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
    return redirect(
        reverse("timekeeping:timesheet_detail", args=[sheet.pk])
        + (f"?{_field_context(request).query}" if _field_context(request).query else "")
    )


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
    return redirect(
        reverse("timekeeping:timesheet_detail", args=[sheet.pk])
        + (f"?{_field_context(request).query}" if _field_context(request).query else "")
    )


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
    return redirect(
        reverse("timekeeping:timesheet_detail", args=[sheet.pk])
        + (f"?{_field_context(request).query}" if _field_context(request).query else "")
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ATTENDANCE_VIEW)
@require_GET
def record_detail(request: HttpRequest, kind: str, record_id: str) -> HttpResponse:
    # Back-office read access deliberately does not reuse ESS identity routes.
    models = {
        "attendance": AttendanceRecord,
        "correction": AttendanceCorrectionRequest,
        "leave": LeaveMissionRequest,
        "overtime": OvertimeRequest,
    }
    model = models.get(kind)
    if model is None:
        raise Http404
    records = model.objects.filter(organization=request.organization)
    if kind == "correction":
        records = scope_queryset(
            records,
            membership=get_active_membership(
                user=request.user, organization=request.organization
            ),
            project_lookup="attendance__project_id",
            site_lookup="attendance__site_id",
        )
    else:
        records = _scoped(records, request)
    record = get_object_or_404(records, pk=record_id)
    if kind in ("leave", "overtime", "correction"):
        source = record.attendance if kind == "correction" else record
        require_business_permission(
            user=request.user,
            organization=request.organization,
            permission={
                "leave": BusinessPermissionCode.LEAVE_MISSION_VIEW,
                "overtime": BusinessPermissionCode.OVERTIME_VIEW,
                "correction": BusinessPermissionCode.ATTENDANCE_CORRECT,
            }[kind],
            project=source.project,
            site=source.site,
            message="مجوز مشاهده این سابقه را ندارید.",
        )
    if kind == "attendance":
        title = "سابقه حضور"
        rows = [
            ("نیروی کار", record.employee, "text"),
            ("تاریخ", record.work_date, "date"),
            ("ورود", record.check_in_at, "datetime"),
            ("خروج", record.check_out_at, "datetime"),
            ("وضعیت", record.get_state_display(), "text"),
            ("شرح استثنا", record.exception_notes, "text"),
            ("زمان ثبت", record.created_at, "datetime"),
            ("زمان قطعی‌سازی", record.finalized_at, "datetime"),
        ]
    elif kind == "correction":
        title = "درخواست اصلاح حضور"
        rows = [
            ("نیروی کار", record.attendance.employee, "text"),
            ("تاریخ حضور", record.attendance.work_date, "date"),
            ("نوع", record.get_kind_display(), "text"),
            ("وضعیت", record.get_status_display(), "text"),
            ("دلیل درخواست", record.reason, "text"),
            ("تاریخ پیشنهادی", record.replacement_work_date, "date"),
            ("ورود پیشنهادی", record.replacement_check_in_at, "datetime"),
            ("خروج پیشنهادی", record.replacement_check_out_at, "datetime"),
            ("دلیل بررسی", record.review_reason, "text"),
            ("زمان درخواست", record.created_at, "datetime"),
            ("زمان بررسی", record.reviewed_at, "datetime"),
        ]
    else:
        title = record.get_kind_display() if kind == "leave" else "درخواست اضافه‌کاری"
        rows = [
            ("نیروی کار", record.employee, "text"),
            ("پروژه", record.project, "text"),
            ("کارگاه", record.site, "text"),
            ("شروع", record.starts_at, "datetime"),
            ("پایان", record.ends_at, "datetime"),
            ("وضعیت", record.get_state_display(), "text"),
            ("دلیل درخواست", record.reason, "text"),
            ("دلیل بررسی", record.review_reason, "text"),
            ("زمان درخواست", record.created_at, "datetime"),
            ("زمان بررسی", record.reviewed_at, "datetime"),
        ]
    from .presentation import record_actions

    source = record.attendance if kind == "correction" else record
    return render(
        request,
        "timekeeping/record_detail.html",
        {
            "detail_title": title,
            "detail_rows": rows,
            "back_url": _workbench_url(request),
            "record": record,
            "record_kind": kind,
            "source": source,
            "worker_name": f"{source.employee.first_name} {source.employee.last_name}",
            "record_state": record.status if kind == "correction" else record.state,
            "record_state_label": record.get_status_display()
            if kind == "correction"
            else record.get_state_display(),
            "actions": record_actions(request, record, kind),
            "field_context": _field_context(request),
            "history_query": _journey_query(request, _field_context(request)),
        },
    )
