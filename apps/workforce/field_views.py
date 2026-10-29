from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
    scope_queryset,
)
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode as P
from apps.projects.models import Project, ProjectSite
from core.forms import normalize_jalali_digits
from core.list_filters import table_pagination_query

from .field_forms import (
    FieldAssignmentForm,
    FieldEmployeeForm,
    FieldFilterForm,
    business_label,
    page_filter_values,
)
from .field_selectors import (
    context_employees,
    current_assignments,
    employee_person,
    field_employees,
    resolve_field_context,
    scoped_employees,
)
from .field_services import assign_field_employee, save_field_employee
from .models import (
    Department,
    Employee,
    EmployeeQualification,
    EmployeeSkillRecord,
    WorkTeam,
)


def _context(request, *, include_employee=False):
    return resolve_field_context(
        organization=request.organization,
        user=request.user,
        values=request.GET,
        include_employee=include_employee,
    )


def _employees(request, context):
    return field_employees(
        organization=request.organization, user=request.user, context=context
    )


def _url(route, context, **kwargs):
    url = reverse(route, kwargs=kwargs)
    return f"{url}?{context.query}" if context.query else url


@active_organization_required
@organization_permission_required(P.EMPLOYEES_VIEW)
@require_GET
def index(request):
    values = page_filter_values(request)
    context = resolve_field_context(
        organization=request.organization, user=request.user, values=values
    )
    employees = _employees(request, context)
    form = FieldFilterForm(
        values or None, organization=request.organization, user=request.user
    )
    if form.is_valid():
        q = form.cleaned_data["q"]
        if q:
            employees = employees.filter(
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(employee_number__icontains=q)
            )
        if form.cleaned_data["status"]:
            employees = employees.filter(status=form.cleaned_data["status"])
    assignments = current_assignments(
        organization=request.organization, user=request.user, context=context
    )
    employees = employees.prefetch_related(
        Prefetch(
            "project_assignments", queryset=assignments, to_attr="field_assignments"
        )
    )
    page = Paginator(employees.order_by("last_name", "first_name", "pk"), 25).get_page(
        request.GET.get("page")
    )
    rows = [
        {
            "employee": employee,
            "url": _url("workforce:field_detail", context, employee_id=employee.pk),
        }
        for employee in page
    ]
    return render(
        request,
        "workforce/field_list.html",
        {
            "rows": rows,
            "form": form,
            "field_context": context,
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "create_url": _url("workforce:field_create", context),
            "timekeeping_url": _url("timekeeping:workbench", context),
        },
    )


@active_organization_required
@organization_permission_required(P.EMPLOYEES_VIEW)
@require_GET
def detail(request, employee_id):
    context = _context(request)
    employee = get_object_or_404(_employees(request, context), pk=employee_id)
    person = employee_person(employee)
    skills, qualifications = (), ()
    if has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=P.WORKFORCE_SKILLS_VIEW,
        allow_any_scope=True,
    ):
        skills = EmployeeSkillRecord.objects.filter(
            organization=request.organization, employee=employee
        ).select_related("skill")[:30]
    if has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=P.WORKFORCE_QUALIFICATIONS_VIEW,
        allow_any_scope=True,
    ):
        qualifications = EmployeeQualification.objects.filter(
            organization=request.organization, employee=employee
        ).prefetch_related("lifecycle_events")[:30]
    from .field_selectors import FieldContext

    worker_context = FieldContext(
        project=context.project, site=context.site, employee=employee
    )
    return render(
        request,
        "workforce/field_detail.html",
        {
            "employee": employee,
            "person": person,
            "field_context": context,
            "assignments": current_assignments(
                organization=request.organization,
                user=request.user,
                employee=employee,
                context=context,
            ),
            "skills": skills,
            "qualifications": qualifications,
            "edit_url": _url("workforce:field_edit", context, employee_id=employee.pk),
            "assignment_url": _url(
                "workforce:field_assign", context, employee_id=employee.pk
            ),
            "timekeeping_url": _url("timekeeping:workbench", worker_context),
            "attendance_url": _url("timekeeping:attendance_create", worker_context),
            "timesheet_url": _url("timekeeping:timesheet_create", worker_context),
            "overtime_url": _url("timekeeping:overtime_create", worker_context),
            "back_url": _url("workforce:field_list", context),
        },
    )


def _employee_form(request, employee=None):
    context = _context(request)
    person = employee_person(employee) if employee else None
    initial = {}
    if employee:
        initial = {
            name: getattr(employee, name)
            for name in (
                "employee_number",
                "first_name",
                "last_name",
                "phone_number",
                "work_team",
            )
        }
        initial.update(
            national_id=person.national_id if person else "",
            start_date=employee.hire_date,
        )
    form = FieldEmployeeForm(
        request.POST if request.method == "POST" else None,
        organization=request.organization,
        employee=employee,
        person=person,
        initial=initial,
    )
    if employee is None and context.project:
        form.fields["assign_here"] = forms.BooleanField(
            label="این نیرو با تاریخ آغاز همکاری به همین پروژه و کارگاه تخصیص داده شود.",
            required=True,
            widget=forms.CheckboxInput(
                attrs={"class": "size-4 rounded border-slate-300"}
            ),
        )
    if (
        request.method == "POST"
        and request.POST.get("_refresh_choices") != "1"
        and form.is_valid()
    ):
        try:
            data = form.cleaned_data.copy()
            assign_here = data.pop("assign_here", False)
            with transaction.atomic():
                saved = save_field_employee(
                    organization=request.organization,
                    actor=request.user,
                    employee=employee,
                    **data,
                )
                if assign_here:
                    assign_field_employee(
                        organization=request.organization,
                        actor=request.user,
                        employee=saved,
                        project=context.project,
                        site=context.site,
                        start_date=data["start_date"],
                    )
        except (IntegrityError, ValidationError, ValueError):
            form.add_error(
                None,
                "اطلاعات نیروی کار یا کد ملی تکراری یا ناسازگار است؛ ورودی‌ها را بررسی کنید.",
            )
        else:
            messages.success(request, "اطلاعات نیروی کار ثبت شد.")
            return redirect(
                _url("workforce:field_detail", context, employee_id=saved.pk)
            )
    return render(
        request,
        "workforce/field_form.html",
        {
            "form": form,
            "field_context": context,
            "title": "ویرایش نیروی کار" if employee else "افزودن نیروی کار",
            "back_url": _url("workforce:field_list", context),
        },
    )


@active_organization_required
@organization_permission_required(P.EMPLOYEES_CREATE)
@require_http_methods(["GET", "POST"])
def create(request):
    return _employee_form(request)


@active_organization_required
@organization_permission_required(P.EMPLOYEES_CHANGE_OPERATIONAL)
@require_http_methods(["GET", "POST"])
def edit(request, employee_id):
    employee = get_object_or_404(_employees(request, _context(request)), pk=employee_id)
    return _employee_form(request, employee)


@active_organization_required
@organization_permission_required(P.PROJECT_ASSIGNMENTS_CREATE)
@require_http_methods(["GET", "POST"])
def assign(request, employee_id):
    context = _context(request)
    employee = get_object_or_404(_employees(request, context), pk=employee_id)
    form = FieldAssignmentForm(
        request.POST if request.method == "POST" else None,
        organization=request.organization,
        user=request.user,
        context=context,
        initial={"project": context.project, "site": context.site},
    )
    if (
        request.method == "POST"
        and request.POST.get("_refresh_choices") != "1"
        and form.is_valid()
    ):
        try:
            assign_field_employee(
                organization=request.organization,
                actor=request.user,
                employee=employee,
                **form.cleaned_data,
            )
        except (IntegrityError, ValidationError, ValueError) as exc:
            form.add_error(
                None,
                "؛ ".join(exc.messages)
                if isinstance(exc, ValidationError)
                else str(exc),
            )
        else:
            messages.success(request, "تخصیص نیروی کار ثبت شد.")
            return redirect(
                _url("workforce:field_detail", context, employee_id=employee.pk)
            )
    return render(
        request,
        "workforce/field_form.html",
        {
            "form": form,
            "title": "تخصیص جدید",
            "assignment_employee": employee,
            "field_context": context,
            "back_url": _url(
                "workforce:field_detail", context, employee_id=employee.pk
            ),
        },
    )


@active_organization_required
@require_GET
def choices(request, kind):
    permissions = {
        "department": (P.WORK_TEAMS_CREATE,),
        "team_lead": (P.WORK_TEAMS_CREATE,),
        "team": (P.EMPLOYEES_CREATE, P.EMPLOYEES_CHANGE_OPERATIONAL),
        "project": (
            P.EMPLOYEES_VIEW,
            P.ATTENDANCE_VIEW,
            P.ATTENDANCE_CAPTURE,
            P.OVERTIME_REQUEST,
            P.TIMESHEETS_PREPARE,
            P.PROJECT_ASSIGNMENTS_CREATE,
            P.PROJECT_ASSIGNMENTS_VIEW,
            P.LEAVE_MISSION_REQUEST,
        ),
        "site": (
            P.EMPLOYEES_VIEW,
            P.ATTENDANCE_VIEW,
            P.ATTENDANCE_CAPTURE,
            P.OVERTIME_REQUEST,
            P.TIMESHEETS_PREPARE,
            P.PROJECT_ASSIGNMENTS_CREATE,
            P.PROJECT_ASSIGNMENTS_VIEW,
            P.LEAVE_MISSION_REQUEST,
        ),
        "employee": (
            P.ATTENDANCE_VIEW,
            P.ATTENDANCE_CAPTURE,
            P.OVERTIME_REQUEST,
            P.TIMESHEETS_PREPARE,
            P.LEAVE_MISSION_REQUEST,
            P.PROJECT_ASSIGNMENTS_CREATE,
        ),
        "calendar": (P.ATTENDANCE_CAPTURE,),
        "shift": (P.ATTENDANCE_CAPTURE,),
        "activity": (P.TIMESHEETS_PREPARE,),
    }
    if kind == "employee" and request.GET.get("purpose") == "assignment_filter":
        permissions[kind] = (P.PROJECT_ASSIGNMENTS_VIEW,)
    organization_master = kind in {"department", "team_lead"}
    if not any(
        has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=p,
            allow_any_scope=not organization_master,
        )
        for p in permissions.get(kind, ())
    ):
        raise PermissionDenied
    # Team masters are organization-level; page/global Project/Site is irrelevant.
    context = None if organization_master else _context(request)
    membership = get_active_membership(
        user=request.user, organization=request.organization
    )
    if kind == "department":
        records = Department.objects.filter(
            organization=request.organization, is_active=True, archived_at=None
        )
    elif kind == "team_lead":
        records = Employee.objects.filter(
            organization=request.organization, status="active", archived_at=None
        )
    elif kind == "team":
        records = WorkTeam.objects.filter(
            organization=request.organization, is_active=True, archived_at=None
        )
    elif kind == "employee":
        if request.GET.get("purpose") == "assignment":
            # Assignment creation deliberately includes workers without assignments.
            if not has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=P.PROJECT_ASSIGNMENTS_CREATE,
                allow_any_scope=True,
            ):
                raise PermissionDenied
            from .field_selectors import FieldContext

            records = _employees(request, FieldContext()).filter(status="active")
        elif request.GET.get("purpose") == "assignment_filter":
            records = context_employees(
                scoped_employees(
                    organization=request.organization,
                    user=request.user,
                    assigned_only=True,
                ),
                context,
            )
        else:
            records = _employees(request, context)
    elif kind in ("calendar", "shift"):
        from apps.timekeeping.models import ShiftDefinition, WorkCalendar

        records = (
            WorkCalendar if kind == "calendar" else ShiftDefinition
        ).objects.filter(organization=request.organization, is_active=True)
        if kind == "shift":
            try:
                records = (
                    records.filter(calendar_id=request.GET.get("calendar"))
                    if request.GET.get("calendar")
                    else records.none()
                )
            except (ValueError, ValidationError):
                records = records.none()
    elif kind == "activity":
        from apps.projects.models import Activity

        records = scope_queryset(
            Activity.objects.filter(organization=request.organization, is_active=True),
            membership=membership,
            project_lookup="project_id",
            site_lookup="site_id",
        )
        records = (
            records.filter(project=context.project, site=context.site)
            if context.project
            else records.none()
        )
    elif kind == "project":
        records = scope_queryset(
            Project.objects.filter(organization=request.organization, deleted_at=None),
            membership=membership,
            project_lookup="pk",
            include_site_parent=True,
        )
    else:
        records = scope_queryset(
            ProjectSite.objects.filter(
                organization=request.organization, is_active=True
            ),
            membership=membership,
            project_lookup="project_id",
            site_lookup="pk",
        )
        records = (
            records.filter(project=context.project)
            if context.project
            else records.none()
        )
    q = (
        normalize_jalali_digits(request.GET.get("q", "").strip()[:150])
        .replace("ي", "ی")
        .replace("ك", "ک")
    )
    for term in q.split():
        if kind in {"employee", "team_lead"}:
            records = records.filter(
                Q(first_name__icontains=term)
                | Q(last_name__icontains=term)
                | Q(employee_number__icontains=term)
            )
        else:
            records = records.filter(Q(name__icontains=term) | Q(code__icontains=term))
    try:
        page = max(1, min(int(request.GET.get("page", "1")), 10000))
    except ValueError:
        page = 1
    offset = (page - 1) * 40
    batch = list(records.order_by("pk")[offset : offset + 41])
    next_query = request.GET.copy()
    next_query["page"] = page + 1
    response = JsonResponse(
        {
            "results": [
                {"value": str(record.pk), "label": business_label(record)}
                for record in batch[:40]
            ],
            "next": f"{request.path}?{next_query.urlencode()}"
            if len(batch) > 40
            else None,
        }
    )
    response["Cache-Control"] = "private, no-store"
    return response
