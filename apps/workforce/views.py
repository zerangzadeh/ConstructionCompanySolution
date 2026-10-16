from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import (
    FileResponse,
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseNotFound,
)
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.documents.models import DocumentConfidentiality
from apps.documents.services import create_document
from apps.organizations.authorization import has_business_permission
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode
from apps.projects.models import ProjectSite
from apps.workforce.ess_services import get_own_profile
from apps.workforce.forms import (
    AssignmentStatusTransitionForm,
    DepartmentForm,
    EmployeeAccountLinkForm,
    EmployeeAssignmentForm,
    EmployeeForm,
    EmployeePositionAssignmentForm,
    EmployeePositionEndForm,
    EmployeeProfileImageForm,
    EmployeeQualificationForm,
    EmployeeSkillRecordForm,
    EmployeeTrainingRecordForm,
    LaborRateVersionForm,
    PerformanceEvaluationForm,
    PositionForm,
    QualificationRevocationForm,
    StatusTransitionForm,
    TrainingRequirementForm,
    WorkforceCatalogueForm,
    WorkforceEvidenceUploadForm,
    WorkTeamForm,
)
from apps.workforce.models import (
    AssignmentStatus,
    Department,
    EmployeePositionAssignment,
    EmployeeQualification,
    EmployeeStatus,
    EmployeeTrainingRecord,
    PerformanceEvaluation,
    Position,
    TrainingRequirement,
)
from apps.workforce.services import (
    archive_department,
    archive_employee,
    archive_position,
    archive_work_team,
    assign_employee_position,
    assign_employee_to_project,
    create_competency,
    create_department,
    create_employee,
    create_employee_from_member,
    create_position,
    create_skill,
    create_training_requirement,
    create_work_team,
    end_employee_position,
    get_active_department_position_assignments,
    get_employee_position_assignments,
    get_employee_qualifications,
    get_employee_training_records,
    get_labor_rate_versions,
    get_organization_departments,
    get_organization_employees,
    get_organization_positions,
    get_organization_project_assignments,
    get_organization_work_teams,
    get_performance_evaluations,
    get_workforce_competencies,
    get_workforce_skills,
    link_employee_account,
    record_employee_qualification,
    record_employee_skill,
    record_employee_training,
    record_labor_rate_version,
    record_performance_evaluation,
    revoke_employee_qualification,
    transition_employee_status,
    transition_project_assignment_status,
    unlink_employee_account,
    update_department,
    update_employee_profile_image,
    update_position,
)
from core.list_filters import (
    apply_table_filters,
    apply_table_sorting,
    build_table_filters,
    has_active_table_filters,
    paginate_table,
    table_pagination_query,
)

_IMAGE_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


@active_organization_required
@require_GET
def ess_profile(
    request: HttpRequest, relationship_id: str | None = None
) -> HttpResponse:
    profile = get_own_profile(
        user=request.user,
        organization=request.organization,
        relationship_id=relationship_id,
    )
    return render(request, "workforce/ess_profile.html", {"profile": profile})


def _employee(request: HttpRequest, employee_id: str):
    return (
        get_organization_employees(user=request.user, organization=request.organization)
        .filter(pk=employee_id)
        .first()
    )


def _status_choices(
    current_status: str, transitions: dict[str, tuple[str, ...]], choices
):
    labels = dict(choices)
    return [(status, labels[status]) for status in transitions[current_status]]


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EMPLOYEES_VIEW)
@require_GET
def employee_list(request: HttpRequest) -> HttpResponse:
    employees = get_organization_employees(
        user=request.user, organization=request.organization
    )
    employees = apply_table_filters(
        employees,
        request,
        text_fields={
            "employee": (
                "employee_number",
                "first_name",
                "last_name",
                "email",
                "phone_number",
            ),
            "position": ("department__name", "position__title"),
            "team": ("work_team__name",),
        },
        choice_fields={"status": ("status", EmployeeStatus.values)},
    )
    page = paginate_table(
        employees,
        request,
        sort_fields={
            "employee": ("last_name", "first_name"),
            "position": ("department__name", "position__title"),
            "team": "work_team__name",
            "status": "status",
        },
        default_ordering=("last_name", "first_name", "pk"),
    )
    return render(
        request,
        "workforce/employee_list.html",
        {
            "employees": page.object_list,
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "filters": build_table_filters(
                request,
                [
                    {"name": "employee", "kind": "text", "label": "کارمند"},
                    {"name": "position", "kind": "text", "label": "واحد و سمت"},
                    {"name": "team", "kind": "text", "label": "گروه کاری"},
                    {
                        "name": "status",
                        "kind": "select",
                        "label": "وضعیت",
                        "choices": EmployeeStatus.choices,
                    },
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EMPLOYEES_CREATE)
def employee_create(request: HttpRequest) -> HttpResponse:
    can_link_account = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.EMPLOYEES_LINK_ACCOUNT,
    )
    form = EmployeeForm(
        request.POST or None,
        organization=request.organization,
        can_link_account=can_link_account,
    )

    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data.copy()
        source_type = data.pop("source_type")
        user = data.pop("user")
        try:
            if source_type == EmployeeForm.EXISTING_ACCOUNT:
                for field_name in ("first_name", "last_name", "email", "phone_number"):
                    data.pop(field_name)
                employee = create_employee_from_member(
                    organization=request.organization,
                    actor=request.user,
                    user=user,
                    **data,
                )
            else:
                employee = create_employee(
                    organization=request.organization,
                    actor=request.user,
                    **data,
                )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "پرونده کارمند ایجاد شد.")
            return redirect("workforce:employee_detail", employee_id=employee.pk)
    return render(
        request,
        "workforce/employee_form.html",
        {"form": form, "can_link_account": can_link_account},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EMPLOYEES_CREATE)
@require_GET
def employee_positions(request: HttpRequest) -> HttpResponse:
    department_id = request.GET.get("department")
    positions = Position.objects.filter(
        organization=request.organization,
        archived_at__isnull=True,
        is_active=True,
    )
    if department_id:
        positions = positions.filter(department_id=department_id)
    return render(
        request,
        "workforce/_position_options.html",
        {"positions": positions.order_by("title")},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EMPLOYEES_VIEW)
@require_GET
def employee_detail(request: HttpRequest, employee_id: str) -> HttpResponse:
    employee = _employee(request, employee_id)
    if employee is None:
        return HttpResponseNotFound("کارمند یافت نشد.")
    assignments = []
    if has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.PROJECT_ASSIGNMENTS_VIEW,
    ):
        assignments = get_organization_project_assignments(
            user=request.user, organization=request.organization
        ).filter(employee=employee)
    transitions = _status_choices(
        employee.status,
        {
            EmployeeStatus.ACTIVE: (EmployeeStatus.INACTIVE, EmployeeStatus.TERMINATED),
            EmployeeStatus.INACTIVE: (EmployeeStatus.ACTIVE, EmployeeStatus.TERMINATED),
            EmployeeStatus.TERMINATED: (),
        },
        EmployeeStatus.choices,
    )
    position_assignments = get_employee_position_assignments(
        user=request.user,
        organization=request.organization,
        employee=employee,
    )
    can_change_profile_image = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.EMPLOYEES_CHANGE_PROFILE_IMAGE,
    )
    qualifications = []
    training_records = []
    performance_evaluations = []
    labor_rate_versions = []
    if has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_VIEW,
    ):
        qualifications = get_employee_qualifications(
            organization=request.organization, actor=request.user, employee=employee
        )
        training_records = get_employee_training_records(
            organization=request.organization, actor=request.user, employee=employee
        )
    if has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.WORKFORCE_PERFORMANCE_VIEW,
    ):
        performance_evaluations = get_performance_evaluations(
            organization=request.organization, actor=request.user, employee=employee
        )
    if has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.WORKFORCE_LABOR_RATES_VIEW,
    ):
        labor_rate_versions = get_labor_rate_versions(
            organization=request.organization, actor=request.user, employee=employee
        )
    return render(
        request,
        "workforce/employee_detail.html",
        {
            "employee": employee,
            "assignments": assignments,
            "position_assignments": position_assignments,
            "position_assignment_form": EmployeePositionAssignmentForm(
                organization=request.organization
            ),
            "status_form": StatusTransitionForm(choices=transitions),
            "account_link_form": EmployeeAccountLinkForm(
                organization=request.organization
            ),
            "profile_image_form": (
                EmployeeProfileImageForm(instance=employee)
                if can_change_profile_image
                else None
            ),
            "qualifications": qualifications,
            "training_records": training_records,
            "performance_evaluations": performance_evaluations,
            "labor_rate_versions": labor_rate_versions,
            "can_manage_qualifications": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_MANAGE,
            ),
            "can_revoke_qualifications": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_REVOKE,
            ),
            "can_manage_performance": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.WORKFORCE_PERFORMANCE_MANAGE,
            ),
            "can_upload_documents": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.DOCUMENTS_UPLOAD,
            ),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EMPLOYEES_VIEW)
@require_GET
def employee_profile_image(request: HttpRequest, employee_id: str) -> FileResponse:
    employee = _employee(request, employee_id)
    if employee is None:
        raise Http404
    image_field = employee.profile_image
    if not image_field and employee.user is not None:
        image_field = employee.user.profile_image
    if not image_field:
        raise Http404
    try:
        image = image_field.open("rb")
    except (FileNotFoundError, OSError) as exc:
        raise Http404 from exc
    extension = "." + image_field.name.lower().rsplit(".", maxsplit=1)[-1]
    content_type = _IMAGE_CONTENT_TYPES.get(extension)
    if content_type is None:
        image.close()
        raise Http404
    response = FileResponse(image, content_type=content_type)
    response["Cache-Control"] = "private, max-age=300"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EMPLOYEES_CHANGE_PROFILE_IMAGE)
@require_POST
def employee_profile_image_update(
    request: HttpRequest, employee_id: str
) -> HttpResponse:
    employee = _employee(request, employee_id)
    if employee is None:
        return HttpResponseNotFound("کارمند یافت نشد.")
    form = EmployeeProfileImageForm(request.POST, request.FILES, instance=employee)
    if form.is_valid():
        try:
            update_employee_profile_image(
                organization=request.organization,
                actor=request.user,
                employee=employee,
                data=form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "عکس پرسنلی کارمند به‌روزرسانی شد.")
    else:
        messages.error(request, "عکس انتخاب‌شده معتبر نیست.")
    return redirect("workforce:employee_detail", employee_id=employee.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EMPLOYEES_LINK_ACCOUNT)
@require_POST
def employee_account_link(request: HttpRequest, employee_id: str) -> HttpResponse:
    employee = _employee(request, employee_id)
    if employee is None:
        return HttpResponseNotFound("کارمند یافت نشد.")
    form = EmployeeAccountLinkForm(request.POST, organization=request.organization)
    if form.is_valid():
        try:
            link_employee_account(
                organization=request.organization,
                actor=request.user,
                employee=employee,
                user=form.cleaned_data["user"],
            )
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "حساب کاربری به پرونده کارمند متصل شد.")
    else:
        messages.error(request, "حساب انتخاب‌شده معتبر نیست.")
    return redirect("workforce:employee_detail", employee_id=employee.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EMPLOYEES_LINK_ACCOUNT)
@require_POST
def employee_account_unlink(request: HttpRequest, employee_id: str) -> HttpResponse:
    employee = _employee(request, employee_id)
    if employee is None:
        return HttpResponseNotFound("کارمند یافت نشد.")
    try:
        unlink_employee_account(
            organization=request.organization, actor=request.user, employee=employee
        )
    except (PermissionDenied, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "اتصال حساب کاربری از پرونده کارمند قطع شد.")
    return redirect("workforce:employee_detail", employee_id=employee.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EMPLOYEE_POSITIONS_ASSIGN)
@require_POST
def employee_position_assign(request: HttpRequest, employee_id: str) -> HttpResponse:
    employee = _employee(request, employee_id)
    if employee is None:
        return HttpResponseNotFound("کارمند یافت نشد.")
    form = EmployeePositionAssignmentForm(
        request.POST,
        organization=request.organization,
    )
    if form.is_valid():
        try:
            assign_employee_position(
                organization=request.organization,
                actor=request.user,
                employee=employee,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "سمت شغلی به کارمند تخصیص یافت.")
    else:
        messages.error(request, "اطلاعات تخصیص سمت معتبر نیست.")
    return redirect("workforce:employee_detail", employee_id=employee.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EMPLOYEE_POSITIONS_END)
@require_POST
def employee_position_end(
    request: HttpRequest, employee_id: str, assignment_id: str
) -> HttpResponse:
    employee = _employee(request, employee_id)
    if employee is None:
        return HttpResponseNotFound("کارمند یافت نشد.")
    assignment = EmployeePositionAssignment.objects.filter(
        pk=assignment_id,
        organization=request.organization,
        employee=employee,
    ).first()
    if assignment is None:
        return HttpResponseNotFound("تخصیص سمت یافت نشد.")
    form = EmployeePositionEndForm(request.POST)
    if form.is_valid():
        try:
            end_employee_position(
                organization=request.organization,
                actor=request.user,
                assignment=assignment,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "تخصیص سمت پایان یافت.")
    else:
        messages.error(request, "تاریخ پایان تخصیص سمت معتبر نیست.")
    return redirect("workforce:employee_detail", employee_id=employee.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EMPLOYEES_CHANGE_STATUS)
@require_POST
def employee_status_change(request: HttpRequest, employee_id: str) -> HttpResponse:
    employee = _employee(request, employee_id)
    if employee is None:
        return HttpResponseNotFound("کارمند یافت نشد.")
    choices = _status_choices(
        employee.status,
        {
            EmployeeStatus.ACTIVE: (EmployeeStatus.INACTIVE, EmployeeStatus.TERMINATED),
            EmployeeStatus.INACTIVE: (EmployeeStatus.ACTIVE, EmployeeStatus.TERMINATED),
            EmployeeStatus.TERMINATED: (),
        },
        EmployeeStatus.choices,
    )
    form = StatusTransitionForm(request.POST, choices=choices)
    if form.is_valid():
        try:
            transition_employee_status(
                organization=request.organization,
                actor=request.user,
                employee=employee,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "وضعیت کارمند به‌روزرسانی شد.")
    else:
        messages.error(request, "اطلاعات وضعیت کارمند معتبر نیست.")
    return redirect("workforce:employee_detail", employee_id=employee.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EMPLOYEES_ARCHIVE)
@require_POST
def employee_archive(request: HttpRequest, employee_id: str) -> HttpResponse:
    employee = _employee(request, employee_id)
    if employee is None:
        return HttpResponseNotFound("کارمند یافت نشد.")
    try:
        archive_employee(
            organization=request.organization, actor=request.user, employee=employee
        )
    except (PermissionDenied, ValueError) as exc:
        messages.error(request, str(exc))
        return redirect("workforce:employee_detail", employee_id=employee.pk)
    messages.success(request, "کارمند بایگانی شد.")
    return redirect("workforce:employee_list")


def _master_list(
    request: HttpRequest,
    service,
    template_name: str,
    context_name: str,
    *,
    text_fields: dict[str, tuple[str, ...]],
    filters: list[dict[str, object] | None],
    sort_fields: dict[str, str | tuple[str, ...]],
    default_ordering: tuple[str, ...],
) -> HttpResponse:
    records = apply_table_filters(
        service(user=request.user, organization=request.organization),
        request,
        text_fields=text_fields,
    )
    page = paginate_table(
        records,
        request,
        sort_fields=sort_fields,
        default_ordering=default_ordering,
    )
    return render(
        request,
        template_name,
        {
            context_name: page.object_list,
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "filters": build_table_filters(request, filters),
            "has_active_filters": has_active_table_filters(request),
        },
    )


def _build_department_tree(departments) -> list[dict[str, object]]:
    nodes = {
        department.pk: {
            "department": department,
            "children": [],
            "work_teams": [],
            "employees": [],
        }
        for department in departments
    }
    roots: list[dict[str, object]] = []
    for department in departments:
        node = nodes[department.pk]
        parent = nodes.get(department.parent_id)
        if parent is None:
            roots.append(node)
        else:
            parent["children"].append(node)
    return roots


def _build_position_tree(positions, assignments) -> list[dict[str, object]]:
    """Build a hierarchy using only tenant-scoped, prefetched chart records."""
    nodes = {
        position.pk: {"position": position, "children": [], "holders": []}
        for position in positions
    }
    for position in positions:
        parent = nodes.get(position.parent_position_id)
        if parent is not None:
            parent["children"].append(nodes[position.pk])
    for assignment in assignments:
        node = nodes.get(assignment.position_id)
        if node is not None:
            node["holders"].append(assignment.employee)
    return [
        node
        for node in nodes.values()
        if node["position"].parent_position_id not in nodes
    ]


def _annotate_position_tree(nodes: list[dict[str, object]], *, depth: int = 0) -> None:
    """Attach a presentation depth without changing position authority."""
    for node in nodes:
        node["depth"] = depth
        _annotate_position_tree(node["children"], depth=depth + 1)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.POSITIONS_VIEW)
@require_GET
def position_list(request: HttpRequest) -> HttpResponse:
    """Render the primary, position-centric organization chart."""
    all_positions = get_organization_positions(
        user=request.user,
        organization=request.organization,
    )
    chart_positions = list(all_positions.filter(is_active=True))
    filtered_positions = apply_table_filters(
        all_positions,
        request,
        text_fields={
            "position": ("code", "title"),
            "department": ("department__name",),
        },
    )
    page = paginate_table(
        filtered_positions,
        request,
        sort_fields={
            "position": ("title", "code"),
            "department": "department__name",
            "holder_type": "is_single_holder",
            "description": "description",
        },
        default_ordering=("title", "pk"),
    )
    list_positions = page.object_list
    can_view_employees = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.EMPLOYEES_VIEW,
    )
    active_assignments = []
    if can_view_employees:
        active_assignments = list(
            get_active_department_position_assignments(
                user=request.user,
                organization=request.organization,
            )
        )
    holders_by_position: dict[object, list[object]] = {
        position.pk: [] for position in list_positions
    }
    for assignment in active_assignments:
        holders_by_position.setdefault(assignment.position_id, []).append(
            assignment.employee
        )
    position_tree = _build_position_tree(chart_positions, active_assignments)
    _annotate_position_tree(position_tree)
    position_departments = sorted(
        {position.department for position in chart_positions if position.department_id},
        key=lambda department: (department.name, department.pk),
    )
    return render(
        request,
        "workforce/position_chart.html",
        {
            "organization": request.organization,
            "position_tree": position_tree,
            "position_rows": [
                {"position": position, "holders": holders_by_position[position.pk]}
                for position in list_positions
            ],
            "position_departments": position_departments,
            "can_view_employees": can_view_employees,
            "filters": build_table_filters(
                request,
                [
                    {"name": "position", "kind": "text", "label": "کد و عنوان"},
                    {"name": "department", "kind": "text", "label": "واحد شرکتی"},
                    None,
                    None,
                    None,
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "show_list_view": request.GET.get("view") == "list",
        },
    )


def _annotate_department_tree(nodes: list[dict[str, object]], *, depth: int = 0) -> int:
    """Add presentation-only aggregates without weakening tenant-scoped reads."""
    themes = ("emerald", "amber", "sky", "violet", "rose")
    total = 0
    for node in nodes:
        employees = node["employees"]
        active_employees = [
            employee
            for employee in employees
            if employee.status == EmployeeStatus.ACTIVE
        ]
        child_total = _annotate_department_tree(node["children"], depth=depth + 1)
        node["depth"] = depth
        node["theme"] = "primary" if depth == 0 else themes[(depth - 1) % len(themes)]
        node["primary_employee"] = (active_employees or employees or [None])[0]
        node["direct_employee_count"] = len(employees)
        node["active_employee_count"] = len(active_employees)
        node["subtree_employee_count"] = len(employees) + child_total
        total += node["subtree_employee_count"]
    return total


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DEPARTMENTS_VIEW)
@require_GET
def department_list(request: HttpRequest) -> HttpResponse:
    departments = apply_table_sorting(
        get_organization_departments(
            user=request.user, organization=request.organization
        ),
        request,
        sort_fields={
            "name": ("name", "code"),
            "parent": "parent__name",
            "status": "is_active",
        },
        default_ordering=("name", "pk"),
    )
    departments = list(departments)
    tree = _build_department_tree(departments)
    nodes = {node["department"].pk: node for node in _walk_department_tree(tree)}

    if has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.WORK_TEAMS_VIEW,
    ):
        for work_team in get_organization_work_teams(
            user=request.user, organization=request.organization
        ):
            if work_team.department_id in nodes:
                nodes[work_team.department_id]["work_teams"].append(work_team)
    employees = []
    can_view_employees = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.EMPLOYEES_VIEW,
    )
    if can_view_employees:
        employees = list(
            get_organization_employees(
                user=request.user, organization=request.organization
            )
        )
        for employee in employees:
            if employee.department_id in nodes:
                nodes[employee.department_id]["employees"].append(employee)

    _annotate_department_tree(tree, depth=1)

    return render(
        request,
        "workforce/department_list.html",
        {
            "organization": request.organization,
            "departments": departments,
            "department_tree": tree,
            "organization_employee_count": len(employees),
            "can_view_employees": can_view_employees,
        },
    )


def _walk_department_tree(nodes):
    for node in nodes:
        yield node
        yield from _walk_department_tree(node["children"])


def _department_form_initial(department: Department) -> dict[str, object]:
    return {
        "code": department.code,
        "name": department.name,
        "parent": department.parent_id,
        "description": department.description,
    }


def _render_department_detail(
    request: HttpRequest,
    *,
    department: Department,
    department_form: DepartmentForm,
) -> HttpResponse:
    can_view_employees = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.EMPLOYEES_VIEW,
    )
    can_view_positions = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.POSITIONS_VIEW,
    )
    can_view_work_teams = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.WORK_TEAMS_VIEW,
    )
    return render(
        request,
        "workforce/department_detail.html",
        {
            "department": department,
            "department_children": department.children.filter(
                archived_at__isnull=True
            ).order_by("name"),
            "department_employees": (
                get_organization_employees(
                    user=request.user,
                    organization=request.organization,
                ).filter(department=department)
                if can_view_employees
                else []
            ),
            "department_positions": (
                get_organization_positions(
                    user=request.user,
                    organization=request.organization,
                ).filter(department=department)
                if can_view_positions
                else []
            ),
            "department_work_teams": (
                get_organization_work_teams(
                    user=request.user,
                    organization=request.organization,
                ).filter(department=department)
                if can_view_work_teams
                else []
            ),
            "can_view_employees": can_view_employees,
            "can_view_positions": can_view_positions,
            "can_view_work_teams": can_view_work_teams,
            "can_change_department": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.DEPARTMENTS_CHANGE,
            ),
            "department_form": department_form,
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DEPARTMENTS_VIEW)
@require_GET
def department_detail(request: HttpRequest, department_id: str) -> HttpResponse:
    department = (
        get_organization_departments(
            user=request.user,
            organization=request.organization,
        )
        .filter(pk=department_id)
        .first()
    )
    if department is None:
        return HttpResponseNotFound("واحد سازمانی یافت نشد.")
    return _render_department_detail(
        request,
        department=department,
        department_form=DepartmentForm(
            initial=_department_form_initial(department),
            organization=request.organization,
            exclude_department=department,
        ),
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DEPARTMENTS_CHANGE)
@require_POST
def department_update(request: HttpRequest, department_id: str) -> HttpResponse:
    department = Department.objects.filter(
        pk=department_id,
        organization=request.organization,
        archived_at__isnull=True,
    ).first()
    if department is None:
        return HttpResponseNotFound("واحد سازمانی یافت نشد.")
    form = DepartmentForm(
        request.POST,
        organization=request.organization,
        exclude_department=department,
    )
    if form.is_valid():
        try:
            department = update_department(
                organization=request.organization,
                actor=request.user,
                department=department,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "اطلاعات واحد سازمانی به‌روزرسانی شد.")
            return redirect("workforce:department_detail", department_id=department.pk)
    return _render_department_detail(
        request,
        department=department,
        department_form=form,
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DEPARTMENTS_CREATE)
def department_create(request: HttpRequest) -> HttpResponse:
    form = DepartmentForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            create_department(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "واحد سازمانی ایجاد شد.")
            return redirect("workforce:department_list")
    return render(
        request,
        "workforce/form.html",
        {
            "form": form,
            "title": "ثبت واحد سازمانی",
            "back_url": "workforce:department_list",
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DEPARTMENTS_ARCHIVE)
@require_POST
def department_archive(request: HttpRequest, department_id: str) -> HttpResponse:
    department = (
        get_organization_departments(
            user=request.user, organization=request.organization
        )
        .filter(pk=department_id)
        .first()
    )
    if department is None:
        return HttpResponseNotFound("واحد سازمانی یافت نشد.")
    try:
        archive_department(
            organization=request.organization, actor=request.user, department=department
        )
        messages.success(request, "واحد سازمانی بایگانی شد.")
    except (PermissionDenied, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("workforce:department_list")


def _position_form_initial(position: Position) -> dict[str, object]:
    return {
        "code": position.code,
        "title": position.title,
        "department": position.department_id,
        "parent_position": position.parent_position_id,
        "description": position.description,
        "is_single_holder": position.is_single_holder,
    }


def _render_position_detail(
    request: HttpRequest,
    *,
    position: Position,
    position_form: PositionForm,
) -> HttpResponse:
    can_view_employees = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.EMPLOYEES_VIEW,
    )
    position_assignments = []
    if can_view_employees:
        position_assignments = (
            EmployeePositionAssignment.objects.filter(
                organization=request.organization,
                position=position,
            )
            .select_related("employee")
            .order_by("-start_date", "employee__last_name")
        )
    return render(
        request,
        "workforce/position_detail.html",
        {
            "position": position,
            "position_assignments": position_assignments,
            "can_view_employees": can_view_employees,
            "can_change_position": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.POSITIONS_CHANGE,
            ),
            "position_form": position_form,
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.POSITIONS_VIEW)
@require_GET
def position_detail(request: HttpRequest, position_id: str) -> HttpResponse:
    position = (
        get_organization_positions(
            user=request.user,
            organization=request.organization,
        )
        .filter(pk=position_id)
        .first()
    )
    if position is None:
        return HttpResponseNotFound("سمت شغلی یافت نشد.")
    return _render_position_detail(
        request,
        position=position,
        position_form=PositionForm(
            initial=_position_form_initial(position),
            organization=request.organization,
            exclude_position=position,
        ),
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.POSITIONS_CHANGE)
@require_POST
def position_update(request: HttpRequest, position_id: str) -> HttpResponse:
    position = Position.objects.filter(
        pk=position_id,
        organization=request.organization,
        archived_at__isnull=True,
    ).first()
    if position is None:
        return HttpResponseNotFound("سمت شغلی یافت نشد.")
    form = PositionForm(
        request.POST, organization=request.organization, exclude_position=position
    )
    if form.is_valid():
        try:
            position = update_position(
                organization=request.organization,
                actor=request.user,
                position=position,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "اطلاعات سمت شغلی به‌روزرسانی شد.")
            return redirect("workforce:position_detail", position_id=position.pk)
    return _render_position_detail(
        request,
        position=position,
        position_form=form,
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.POSITIONS_CREATE)
def position_create(request: HttpRequest) -> HttpResponse:
    form = PositionForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            create_position(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "سمت شغلی ایجاد شد.")
            return redirect("workforce:position_list")
    return render(
        request,
        "workforce/form.html",
        {"form": form, "title": "ثبت سمت شغلی", "back_url": "workforce:position_list"},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.POSITIONS_ARCHIVE)
@require_POST
def position_archive(request: HttpRequest, position_id: str) -> HttpResponse:
    position = (
        get_organization_positions(user=request.user, organization=request.organization)
        .filter(pk=position_id)
        .first()
    )
    if position is None:
        return HttpResponseNotFound("سمت شغلی یافت نشد.")
    try:
        archive_position(
            organization=request.organization, actor=request.user, position=position
        )
        messages.success(request, "سمت شغلی بایگانی شد.")
    except (PermissionDenied, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("workforce:position_list")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.WORK_TEAMS_VIEW)
@require_GET
def work_team_list(request: HttpRequest) -> HttpResponse:
    return _master_list(
        request,
        get_organization_work_teams,
        "workforce/work_team_list.html",
        "work_teams",
        text_fields={
            "team": ("code", "name"),
            "department": ("department__name",),
            "lead": ("lead__first_name", "lead__last_name"),
        },
        sort_fields={
            "team": ("name", "code"),
            "department": "department__name",
            "lead": ("lead__last_name", "lead__first_name"),
        },
        default_ordering=("name", "pk"),
        filters=[
            {"name": "team", "kind": "text", "label": "کد و نام"},
            {"name": "department", "kind": "text", "label": "واحد شرکتی"},
            {"name": "lead", "kind": "text", "label": "سرپرست"},
            None,
        ],
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.WORK_TEAMS_CREATE)
def work_team_create(request: HttpRequest) -> HttpResponse:
    form = WorkTeamForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            create_work_team(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "گروه کاری ایجاد شد.")
            return redirect("workforce:work_team_list")
    return render(
        request,
        "workforce/form.html",
        {
            "form": form,
            "title": "ثبت گروه کاری",
            "back_url": "workforce:work_team_list",
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.WORK_TEAMS_ARCHIVE)
@require_POST
def work_team_archive(request: HttpRequest, team_id: str) -> HttpResponse:
    team = (
        get_organization_work_teams(
            user=request.user, organization=request.organization
        )
        .filter(pk=team_id)
        .first()
    )
    if team is None:
        return HttpResponseNotFound("گروه کاری یافت نشد.")
    try:
        archive_work_team(
            organization=request.organization, actor=request.user, work_team=team
        )
        messages.success(request, "گروه کاری بایگانی شد.")
    except (PermissionDenied, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("workforce:work_team_list")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROJECT_ASSIGNMENTS_VIEW)
@require_GET
def assignment_list(request: HttpRequest) -> HttpResponse:
    assignments = get_organization_project_assignments(
        user=request.user, organization=request.organization
    )
    assignments = apply_table_filters(
        assignments,
        request,
        text_fields={
            "employee": (
                "employee__employee_number",
                "employee__first_name",
                "employee__last_name",
            ),
            "project": ("project__name", "site__name"),
            "role": ("role_title",),
        },
        choice_fields={"status": ("status", AssignmentStatus.values)},
        date_fields={"start_date": "start_date"},
    )
    page = paginate_table(
        assignments,
        request,
        sort_fields={
            "employee": ("employee__last_name", "employee__first_name"),
            "project": "project__name",
            "role": "role_title",
            "start_date": "start_date",
            "status": "status",
        },
        default_ordering=("-start_date", "pk"),
    )
    return render(
        request,
        "workforce/assignment_list.html",
        {
            "assignments": page.object_list,
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "filters": build_table_filters(
                request,
                [
                    {"name": "employee", "kind": "text", "label": "کارمند"},
                    {"name": "project", "kind": "text", "label": "پروژه و کارگاه"},
                    {"name": "role", "kind": "text", "label": "مسئولیت"},
                    {"name": "start_date", "kind": "date_range", "label": "شروع"},
                    {
                        "name": "status",
                        "kind": "select",
                        "label": "وضعیت",
                        "choices": AssignmentStatus.choices,
                    },
                    None,
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROJECT_ASSIGNMENTS_CREATE)
def assignment_create(request: HttpRequest) -> HttpResponse:
    form = EmployeeAssignmentForm(
        request.POST or None, organization=request.organization
    )
    if request.method == "POST" and form.is_valid():
        try:
            assign_employee_to_project(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "کارمند به پروژه تخصیص یافت.")
            return redirect("workforce:assignment_list")
    return render(request, "workforce/assignment_form.html", {"form": form})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROJECT_ASSIGNMENTS_CREATE)
@require_GET
def assignment_sites(request: HttpRequest) -> HttpResponse:
    project_id = request.GET.get("project")
    sites = []
    if project_id:
        sites = ProjectSite.objects.filter(
            organization=request.organization,
            project_id=project_id,
            project__deleted_at__isnull=True,
            is_active=True,
        ).order_by("name")
    return render(request, "workforce/_site_options.html", {"sites": sites})


@active_organization_required
@organization_permission_required(
    BusinessPermissionCode.PROJECT_ASSIGNMENTS_CHANGE_STATUS
)
@require_POST
def assignment_status_change(request: HttpRequest, assignment_id: str) -> HttpResponse:
    assignment = (
        get_organization_project_assignments(
            user=request.user, organization=request.organization
        )
        .filter(pk=assignment_id)
        .first()
    )
    if assignment is None:
        return HttpResponseNotFound("تخصیص نیرو یافت نشد.")
    choices = _status_choices(
        assignment.status,
        {
            AssignmentStatus.ACTIVE: (
                AssignmentStatus.COMPLETED,
                AssignmentStatus.CANCELLED,
            ),
            AssignmentStatus.COMPLETED: (),
            AssignmentStatus.CANCELLED: (),
        },
        AssignmentStatus.choices,
    )
    form = AssignmentStatusTransitionForm(request.POST, choices=choices)
    if form.is_valid():
        try:
            transition_project_assignment_status(
                organization=request.organization,
                actor=request.user,
                assignment=assignment,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "وضعیت تخصیص به‌روزرسانی شد.")
    else:
        messages.error(request, "اطلاعات وضعیت تخصیص معتبر نیست.")
    return redirect("workforce:assignment_list")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.WORKFORCE_SKILLS_VIEW)
@require_GET
def workforce_foundation(request: HttpRequest) -> HttpResponse:
    """Permission-scoped P7-S01–S05 operational workbench."""

    can_manage_skills = has_business_permission(
        user=request.user, organization=request.organization,
        permission=BusinessPermissionCode.WORKFORCE_SKILLS_MANAGE,
    )
    can_manage_qualifications = has_business_permission(
        user=request.user, organization=request.organization,
        permission=BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_MANAGE,
    )
    can_view_qualifications = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_VIEW,
    )
    return render(
        request,
        "workforce/foundation.html",
        {
            "skills": get_workforce_skills(organization=request.organization, actor=request.user),
            "competencies": get_workforce_competencies(organization=request.organization, actor=request.user),
            "requirements": (
                TrainingRequirement.objects.filter(
                    organization=request.organization, archived_at__isnull=True
                ).select_related("competency", "position", "project")
                if can_view_qualifications
                else []
            ),
            "can_manage_skills": can_manage_skills,
            "can_manage_qualifications": can_manage_qualifications,
            "can_view_performance": has_business_permission(user=request.user, organization=request.organization, permission=BusinessPermissionCode.WORKFORCE_PERFORMANCE_VIEW),
            "can_view_labor_rates": has_business_permission(user=request.user, organization=request.organization, permission=BusinessPermissionCode.WORKFORCE_LABOR_RATES_VIEW),
        },
    )


def _foundation_form(request: HttpRequest, *, form, title: str, description: str, action: str) -> HttpResponse:
    return render(request, "workforce/foundation_form.html", {"form": form, "title": title, "description": description, "action": action})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.WORKFORCE_SKILLS_MANAGE)
def workforce_skill_create(request: HttpRequest) -> HttpResponse:
    form = WorkforceCatalogueForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            create_skill(organization=request.organization, actor=request.user, **form.cleaned_data)
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "مهارت ثبت شد.")
            return redirect("workforce:foundation")
    return _foundation_form(request, form=form, title="ثبت مهارت", description="مهارت فقط یک واقعیت منابع انسانی است و مجوز دسترسی ایجاد نمی‌کند.", action="workforce:skill_create")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.WORKFORCE_SKILLS_MANAGE)
def workforce_competency_create(request: HttpRequest) -> HttpResponse:
    form = WorkforceCatalogueForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            create_competency(organization=request.organization, actor=request.user, **form.cleaned_data)
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "شایستگی ثبت شد.")
            return redirect("workforce:foundation")
    return _foundation_form(request, form=form, title="ثبت شایستگی", description="شایستگی منبع اختیار یا نقش سیستم نیست.", action="workforce:competency_create")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.WORKFORCE_SKILLS_MANAGE)
def workforce_employee_skill_create(request: HttpRequest) -> HttpResponse:
    form = EmployeeSkillRecordForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            record_employee_skill(organization=request.organization, actor=request.user, **form.cleaned_data)
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "سابقه مهارت ثبت شد.")
            return redirect("workforce:employee_detail", employee_id=form.cleaned_data["employee"].pk)
    return _foundation_form(request, form=form, title="ثبت سابقه مهارت", description="سابقه ثبت‌شده تغییرپذیر نیست و اصلاح با سابقه مؤثر جدید انجام می‌شود.", action="workforce:employee_skill_create")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_MANAGE)
def workforce_qualification_create(request: HttpRequest) -> HttpResponse:
    form = EmployeeQualificationForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            qualification = record_employee_qualification(organization=request.organization, actor=request.user, **form.cleaned_data)
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "صلاحیت ثبت شد. شاهد آن را از پرونده کارمند در DMS اضافه کنید.")
            return redirect("workforce:employee_detail", employee_id=qualification.employee_id)
    return _foundation_form(request, form=form, title="ثبت صلاحیت یا گواهی", description="صلاحیت ثبت‌شده تغییرپذیر نیست؛ اعتبار و ابطال آن در سابقه حفظ می‌شود.", action="workforce:qualification_create")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_REVOKE)
def workforce_qualification_revoke(
    request: HttpRequest, qualification_id: str
) -> HttpResponse:
    qualification = EmployeeQualification.objects.filter(
        organization=request.organization, pk=qualification_id
    ).first()
    if qualification is None:
        raise Http404
    form = QualificationRevocationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            revoke_employee_qualification(
                organization=request.organization,
                actor=request.user,
                qualification=qualification,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "ابطال صلاحیت با سابقه غیرقابل‌ویرایش ثبت شد.")
            return redirect("workforce:employee_detail", employee_id=qualification.employee_id)
    return _foundation_form(
        request,
        form=form,
        title="ابطال صلاحیت",
        description="صلاحیت حذف یا بازنویسی نمی‌شود؛ علت و تاریخ ابطال به‌عنوان رویداد تاریخی ثبت می‌شود.",
        action="workforce:qualification_revoke",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_MANAGE)
def workforce_training_requirement_create(request: HttpRequest) -> HttpResponse:
    form = TrainingRequirementForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            create_training_requirement(organization=request.organization, actor=request.user, **form.cleaned_data)
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "الزام آموزشی ثبت شد.")
            return redirect("workforce:foundation")
    return _foundation_form(request, form=form, title="ثبت الزام آموزشی", description="الزام آموزشی، صلاحیت یا دسترسی سیستم ایجاد نمی‌کند.", action="workforce:training_requirement_create")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_MANAGE)
def workforce_training_record_create(request: HttpRequest) -> HttpResponse:
    form = EmployeeTrainingRecordForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            record = record_employee_training(organization=request.organization, actor=request.user, **form.cleaned_data)
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "سابقه آموزش ثبت شد.")
            return redirect("workforce:employee_detail", employee_id=record.employee_id)
    return _foundation_form(request, form=form, title="ثبت سابقه آموزش", description="حضور یا تکمیل آموزش یک واقعیت تاریخی غیرقابل‌ویرایش است.", action="workforce:training_record_create")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.WORKFORCE_PERFORMANCE_MANAGE)
def workforce_performance_create(request: HttpRequest) -> HttpResponse:
    form = PerformanceEvaluationForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            evaluation = record_performance_evaluation(organization=request.organization, actor=request.user, **form.cleaned_data)
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "ارزیابی عملکرد حساس ثبت شد.")
            return redirect("workforce:employee_detail", employee_id=evaluation.employee_id)
    return _foundation_form(request, form=form, title="ثبت ارزیابی عملکرد", description="ارزیابی به‌تنهایی هیچ اثر دسترسی، حقوق، ارتقا یا انضباطی ایجاد نمی‌کند.", action="workforce:performance_create")


_WORKFORCE_EVIDENCE_TARGETS = {
    "employee_qualification": (
        EmployeeQualification,
        BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_MANAGE,
    ),
    "employee_training": (
        EmployeeTrainingRecord,
        BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_MANAGE,
    ),
    "performance_evaluation": (
        PerformanceEvaluation,
        BusinessPermissionCode.WORKFORCE_PERFORMANCE_MANAGE,
    ),
}


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DOCUMENTS_UPLOAD)
def workforce_evidence_upload(
    request: HttpRequest, target_type: str, target_id: str
) -> HttpResponse:
    """Upload immutable DMS evidence for an allowed P7 Workforce fact."""

    target_specification = _WORKFORCE_EVIDENCE_TARGETS.get(target_type)
    if target_specification is None:
        raise Http404
    target_model, required_permission = target_specification
    target = target_model.objects.filter(
        organization=request.organization, pk=target_id
    ).first()
    if target is None:
        raise Http404
    project = getattr(getattr(target, "requirement", None), "project", None)
    if not has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=required_permission,
        project=project,
    ):
        raise PermissionDenied("اجازه ثبت شاهد این سابقه نیروی انسانی را ندارید.")

    form = WorkforceEvidenceUploadForm(
        request.POST or None,
        request.FILES or None,
        organization=request.organization,
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            create_document(
                organization=request.organization,
                actor=request.user,
                document_type=data["document_type"],
                title=data["title"],
                category=data["category"],
                confidentiality=data["confidentiality"]
                or DocumentConfidentiality.INTERNAL,
                access_expires_at=data["access_expires_at"],
                reference=data["reference"],
                description=data["description"],
                upload=data["file"],
                target=target,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "شاهد سندی در DMS ثبت و به سابقه پیوند شد.")
            return redirect("workforce:employee_detail", employee_id=target.employee_id)
    return _foundation_form(
        request,
        form=form,
        title="ثبت شاهد سندی",
        description="فایل در DMS نسخه‌بندی‌شده نگهداری می‌شود و فقط پیوند نوع‌دار به سابقه Workforce ایجاد می‌شود.",
        action="workforce:evidence_upload",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.WORKFORCE_LABOR_RATES_MANAGE)
def workforce_labor_rate_create(request: HttpRequest) -> HttpResponse:
    form = LaborRateVersionForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            version = record_labor_rate_version(organization=request.organization, actor=request.user, **form.cleaned_data)
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "نسخه نرخ حساس ثبت شد.")
            return redirect("workforce:employee_detail", employee_id=version.employee_id)
    return _foundation_form(request, form=form, title="ثبت نسخه نرخ نیروی کار", description="این نرخ صرفاً مرجع Workforce است و اثری در حقوق، پروژه، حسابداری یا تعهد مالی ندارد.", action="workforce:labor_rate_create")
