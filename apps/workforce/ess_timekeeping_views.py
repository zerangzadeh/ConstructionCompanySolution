"""Thin own-data views; all mutations delegate to the authoritative source."""

from functools import wraps
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.organizations.authorization import require_business_permission
from apps.organizations.decorators import active_organization_required
from apps.organizations.models import BusinessPermissionCode as P

from . import ess_timekeeping as service
from .ess_timekeeping_forms import CorrectionForm, EntryForm, LeaveForm, TimesheetForm


def private(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except PermissionDenied:
            return render(request, "workforce/ess_unavailable.html", status=403)
        except ValidationError:
            return render(
                request,
                "workforce/ess_timekeeping_form.html",
                {"error": True, "heading": "درخواست قابل انجام نیست"},
                status=400,
            )

    return wrapped


@active_organization_required
@require_GET
@private
def index(request):
    service.subject(actor=request.user, organization=request.organization)
    panels = []
    for kind, label in [
        ("leave", "درخواست‌های مرخصی من"),
        ("attendance", "سوابق حضور من"),
        ("correction", "درخواست‌های اصلاح حضور من"),
        ("timesheet", "کارکرد من"),
    ]:
        try:
            rows = list(
                service.own_rows(
                    actor=request.user, organization=request.organization, kind=kind
                )
            )
        except PermissionDenied:
            panels.append({"kind": kind, "label": label, "state": "unavailable"})
        else:
            panels.append(
                {
                    "kind": kind,
                    "label": label,
                    "state": "ready" if rows else "empty",
                    "rows": rows,
                }
            )
    try:
        balances = service.own_balances(
            actor=request.user, organization=request.organization
        )
    except PermissionDenied:
        balances = None
    return render(
        request,
        "workforce/ess_timekeeping.html",
        {"panels": panels, "balances": balances, "observed_at": timezone.now()},
    )


@active_organization_required
@require_http_methods(["GET", "POST"])
@private
def create(request, kind):
    forms = {
        "leave": (LeaveForm, P.LEAVE_MISSION_REQUEST, "درخواست مرخصی"),
        "timesheet": (TimesheetForm, P.TIMESHEETS_PREPARE, "کارکرد جدید"),
    }
    if kind not in forms:
        raise PermissionDenied(service.DENIED)
    form_type, permission, heading = forms[kind]
    require_business_permission(
        user=request.user,
        organization=request.organization,
        permission=permission,
        message=service.DENIED,
    )
    service.subject(actor=request.user, organization=request.organization)
    with timezone.override(ZoneInfo(request.organization.settings.timezone)):
        form = form_type(
            request.POST or None, organization=request.organization, actor=request.user
        )
        if request.method == "POST" and form.is_valid():
            try:
                record = (
                    service.create_own_leave
                    if kind == "leave"
                    else service.create_own_timesheet
                )(
                    actor=request.user,
                    organization=request.organization,
                    **form.cleaned_data,
                )
            except ValidationError:
                form.add_error(
                    None,
                    "اطلاعات درخواست با سیاست یا وضعیت منبع سازگار نیست؛ تنظیمات و مقادیر را بررسی کنید.",
                )
            else:
                return redirect(
                    "workforce:ess_timekeeping_detail", kind=kind, record_id=record.pk
                )
    return render(
        request,
        "workforce/ess_timekeeping_form.html",
        {"form": form, "heading": heading},
        status=400 if request.method == "POST" else 200,
    )


@active_organization_required
@require_GET
@private
def detail(request, kind, record_id):
    record = service.own_record(
        actor=request.user,
        organization=request.organization,
        kind=kind,
        record_id=record_id,
    )
    entries = record.entries.all() if kind == "timesheet" else ()
    return render(
        request,
        "workforce/ess_timekeeping_detail.html",
        {"record": record, "kind": kind, "entries": entries},
    )


@active_organization_required
@require_POST
@private
def submit(request, kind, record_id):
    service.submit_own(
        actor=request.user,
        organization=request.organization,
        kind=kind,
        record_id=record_id,
    )
    return redirect("workforce:ess_timekeeping_detail", kind=kind, record_id=record_id)


@active_organization_required
@require_http_methods(["GET", "POST"])
@private
def edit_source(request, kind, record_id):
    if kind not in ("attendance", "timesheet"):
        raise PermissionDenied(service.DENIED)
    record = service.own_record(
        actor=request.user,
        organization=request.organization,
        kind=kind,
        record_id=record_id,
    )
    permission = P.ATTENDANCE_CORRECT if kind == "attendance" else P.TIMESHEETS_PREPARE
    require_business_permission(
        user=request.user,
        organization=request.organization,
        permission=permission,
        message=service.DENIED,
        project=record.project if kind == "attendance" else None,
        site=record.site if kind == "attendance" else None,
    )
    form_type = CorrectionForm if kind == "attendance" else EntryForm
    with timezone.override(ZoneInfo(request.organization.settings.timezone)):
        form = form_type(
            request.POST or None, organization=request.organization, actor=request.user
        )
        if request.method == "POST" and form.is_valid():
            try:
                result = (
                    service.correct_own_attendance
                    if kind == "attendance"
                    else service.add_own_entry
                )(
                    actor=request.user,
                    organization=request.organization,
                    record_id=record_id,
                    **form.cleaned_data,
                )
            except ValidationError:
                form.add_error(
                    None,
                    "اطلاعات با وضعیت منبع سازگار نیست؛ تاریخ و مقادیر را بررسی کنید.",
                )
            else:
                return redirect(
                    "workforce:ess_timekeeping_detail",
                    kind="correction" if kind == "attendance" else "timesheet",
                    record_id=result.pk if kind == "attendance" else record_id,
                )
    return render(
        request,
        "workforce/ess_timekeeping_form.html",
        {
            "form": form,
            "heading": "درخواست اصلاح حضور" if kind == "attendance" else "ردیف کارکرد",
        },
        status=400 if request.method == "POST" else 200,
    )
