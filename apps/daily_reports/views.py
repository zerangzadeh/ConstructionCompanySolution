from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.forms import BaseForm
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.daily_reports.forms import (
    DailyActivityForm,
    DailyReportEquipmentEntryForm,
    DailyReportLaborEntryForm,
    DailyReportMaterialEntryForm,
    DelayEventForm,
)
from apps.daily_reports.list_presentation import daily_report_list_context
from apps.daily_reports.models import DailyReport
from apps.daily_reports.reference_forms import (
    DailyReportCreateForm,
    DailyReportUploadForm,
)
from apps.daily_reports.references import (
    create_report_with_references,
    reference_choice_page,
    reference_scope,
    report_reference_rows,
)
from apps.daily_reports.services import (
    add_daily_activity,
    add_daily_report_equipment_entry,
    add_daily_report_labor_entry,
    add_daily_report_material_entry,
    add_delay_event,
    approve_daily_report,
    get_organization_daily_report,
    get_organization_daily_reports,
    submit_daily_report,
)
from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
)
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.form_scoping import normalized_uuid
from apps.organizations.models import BusinessPermissionCode
from apps.projects.services import get_organization_project
from apps.workflows.runtime import WorkflowConflict
from core.organization_time import render_in_organization_time
from core.product_surface import surface_profile


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DAILY_REPORTS_VIEW)
@require_GET
def daily_report_list(request: HttpRequest) -> HttpResponse:
    reports = get_organization_daily_reports(
        user=request.user,
        organization=request.organization,
    )
    context = daily_report_list_context(request, reports)
    if request.GET.get("format") == "xlsx":
        from .xlsx_exports import reports_download

        return reports_download(
            context["page_obj"].paginator.object_list,
            timezone_name=request.organization.settings.timezone,
        )
    return render(request, "daily_reports/list.html", context)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DAILY_REPORTS_CREATE)
def daily_report_create(request: HttpRequest) -> HttpResponse:
    initial = {}
    if request.method == "GET" and request.GET.get("project"):
        project = get_organization_project(
            user=request.user,
            organization=request.organization,
            project_id=normalized_uuid(request.GET["project"]),
        )
        initial["project"] = project.pk
    form = DailyReportCreateForm(
        request.POST or None,
        organization=request.organization,
        membership=get_active_membership(
            user=request.user, organization=request.organization
        ),
        initial=initial,
    )
    can_upload = all(
        has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=permission,
            allow_any_scope=True,
        )
        for permission in (
            BusinessPermissionCode.DOCUMENTS_VIEW,
            BusinessPermissionCode.DOCUMENTS_UPLOAD,
            BusinessPermissionCode.DAILY_REPORTS_VIEW,
        )
    )
    upload_form = (
        DailyReportUploadForm(
            request.POST or None, request.FILES or None, prefix="upload"
        )
        if can_upload
        else None
    )
    refresh_choices = request.POST.get("_refresh_choices") == "1"
    if request.method == "POST" and not refresh_choices:
        valid = form.is_valid()
        upload_valid = upload_form.is_valid() if upload_form is not None else True
        if not can_upload and (
            request.FILES or any(name.startswith("upload-") for name in request.POST)
        ):
            form.add_error(None, "اجازه افزودن سند مرتبط را ندارید.")
            valid = False
        if not valid or not upload_valid:
            return render(
                request,
                "daily_reports/create.html",
                {"form": form, "upload_form": upload_form},
            )
        data = form.cleaned_data
        upload_values = None
        if upload_form is not None and upload_form.cleaned_data.get("file"):
            upload_values = {
                "upload": upload_form.cleaned_data["file"],
                "title": upload_form.cleaned_data["title"],
                "document_type": upload_form.cleaned_data["document_type"],
            }
        try:
            report = create_report_with_references(
                organization=request.organization,
                actor=request.user,
                report_values={
                    name: data[name] for name in DailyReportCreateForm.Meta.fields
                },
                safety_ids=[
                    record.pk for record in data.get("linked_safety_incidents", [])
                ],
                quality_ids=[
                    record.pk for record in data.get("linked_quality_issues", [])
                ],
                document_ids=[record.pk for record in data.get("linked_documents", [])],
                upload_values=upload_values,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        except (ValidationError, IntegrityError):
            form.add_error(
                None,
                "اطلاعات گزارش و پیوندها را بررسی کنید؛ ممکن است گزارش این تاریخ قبلاً ثبت شده باشد.",
            )
        except OSError:
            form.add_error(
                None, "ذخیره فایل انجام نشد؛ فایل را دوباره انتخاب و تلاش کنید."
            )
        else:
            return redirect("daily_reports:detail", report_id=report.pk)
    return render(
        request, "daily_reports/create.html", {"form": form, "upload_form": upload_form}
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DAILY_REPORTS_CREATE)
@never_cache
@require_GET
def daily_report_reference_choices(request: HttpRequest, kind: str) -> JsonResponse:
    scope = reference_scope(
        actor=request.user,
        organization=request.organization,
        project_id=request.GET.get("project"),
        site_id=request.GET.get("site"),
        phase_id=request.GET.get("phase"),
    )
    try:
        page = max(1, min(int(request.GET.get("page", "1")), 100000))
    except ValueError:
        return JsonResponse({"results": [], "next": None}, status=400)
    rows, more = reference_choice_page(
        actor=request.user,
        organization=request.organization,
        kind=kind,
        scope=scope,
        query=request.GET.get("q", "").strip()[:200],
        page=page,
    )
    query = request.GET.copy()
    query["page"] = str(page + 1)
    return JsonResponse(
        {
            "results": rows,
            "next": f"{request.path}?{query.urlencode()}" if more else None,
        }
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DAILY_REPORTS_VIEW)
@require_GET
def daily_report_detail(request: HttpRequest, report_id: str) -> HttpResponse:
    report = get_organization_daily_report(
        user=request.user,
        organization=request.organization,
        report_id=report_id,
    )
    if request.GET.get("format") == "print":
        from core.printing import print_response

        from .print_outputs import daily_document

        return print_response(request, daily_document(report))
    return _render_daily_report_detail(request, report)


def _render_daily_report_detail(
    request: HttpRequest, report: DailyReport, **bound_forms: BaseForm
) -> HttpResponse:
    from .revision_views import revision_context

    revision = revision_context(report, request.user)
    return render_in_organization_time(
        request,
        "daily_reports/detail.html",
        {
            "report": report,
            "can_approve_daily_report": (
                (revision["show_return"] if report.submission_hash else
                 (surface_profile() != "MVP" or report.created_by_id != request.user.pk))
                and has_business_permission(
                    user=request.user,
                    organization=request.organization,
                    permission=BusinessPermissionCode.DAILY_REPORTS_APPROVE,
                    project=report.project,
                    site=report.site,
                )
            ),
            "can_view_report_project": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.PROJECTS_VIEW,
                project=report.project,
            ),
            "can_view_report_site": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.PROJECT_SITES_VIEW,
                project=report.project,
                site=report.site,
            ),
            "record_references": report_reference_rows(
                actor=request.user, organization=request.organization, report=report
            ),
            "labor_form": DailyReportLaborEntryForm(auto_id="daily-labor-%s"),
            "equipment_form": DailyReportEquipmentEntryForm(
                auto_id="daily-equipment-%s"
            ),
            "material_form": DailyReportMaterialEntryForm(
                organization_id=request.organization.id, auto_id="daily-material-%s"
            ),
            "daily_activity_form": DailyActivityForm(
                report=report, auto_id="daily-activity-%s"
            ),
            "delay_event_form": DelayEventForm(report=report, auto_id="daily-delay-%s"),
            **revision,
            **bound_forms,
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DAILY_REPORTS_ADD_LABOR)
@require_POST
def daily_report_labor_add(request: HttpRequest, report_id: str) -> HttpResponse:
    form = DailyReportLaborEntryForm(request.POST, auto_id="daily-labor-%s")
    if form.is_valid():
        data = form.cleaned_data
        try:
            add_daily_report_labor_entry(
                organization=request.organization,
                report_id=report_id,
                actor=request.user,
                team_name=data["team_name"],
                operation_key=data["operation_key"],
                worker_count=data["worker_count"],
                hours_worked=data["hours_worked"],
                notes=data["notes"],
            )
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "رکورد نیروی انسانی افزوده شد.")
    else:
        report = get_organization_daily_report(
            user=request.user, organization=request.organization, report_id=report_id
        )
        return _render_daily_report_detail(request, report, labor_form=form)
    return redirect("daily_reports:detail", report_id=report_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DAILY_REPORTS_ADD_EQUIPMENT)
@require_POST
def daily_report_equipment_add(request: HttpRequest, report_id: str) -> HttpResponse:
    form = DailyReportEquipmentEntryForm(request.POST, auto_id="daily-equipment-%s")
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
        report = get_organization_daily_report(
            user=request.user, organization=request.organization, report_id=report_id
        )
        return _render_daily_report_detail(request, report, equipment_form=form)
    return redirect("daily_reports:detail", report_id=report_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DAILY_REPORTS_ADD_MATERIAL)
@require_POST
def daily_report_material_add(request: HttpRequest, report_id: str) -> HttpResponse:
    form = DailyReportMaterialEntryForm(
        request.POST,
        organization_id=request.organization.id,
        auto_id="daily-material-%s",
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
        report = get_organization_daily_report(
            user=request.user, organization=request.organization, report_id=report_id
        )
        return _render_daily_report_detail(request, report, material_form=form)
    return redirect("daily_reports:detail", report_id=report_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DAILY_REPORTS_ADD_ACTIVITY)
@require_POST
def daily_activity_add(request: HttpRequest, report_id: str) -> HttpResponse:
    report = get_organization_daily_report(
        user=request.user, organization=request.organization, report_id=report_id
    )
    form = DailyActivityForm(request.POST, report=report, auto_id="daily-activity-%s")
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
        return _render_daily_report_detail(request, report, daily_activity_form=form)
    return redirect("daily_reports:detail", report_id=report_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DAILY_REPORTS_ADD_DELAY)
@require_POST
def delay_event_add(request: HttpRequest, report_id: str) -> HttpResponse:
    report = get_organization_daily_report(
        user=request.user, organization=request.organization, report_id=report_id
    )
    form = DelayEventForm(request.POST, report=report, auto_id="daily-delay-%s")
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
        return _render_daily_report_detail(request, report, delay_event_form=form)
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
    except PermissionDenied as exc:
        return HttpResponse(str(exc), status=403)
    except (ValueError, ValidationError, WorkflowConflict) as exc:
        return HttpResponse(str(exc), status=409)
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
    except PermissionDenied as exc:
        return HttpResponse(str(exc), status=403)
    except (ValueError, ValidationError, WorkflowConflict) as exc:
        return HttpResponse(str(exc), status=409)
    return redirect("daily_reports:detail", report_id=report_id)
