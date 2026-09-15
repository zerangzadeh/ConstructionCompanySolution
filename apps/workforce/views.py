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

from apps.organizations.authorization import has_business_permission
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode
from apps.projects.models import ProjectSite
from apps.workforce.forms import (
    AssignmentStatusTransitionForm,
    DepartmentForm,
    EmployeeAccountLinkForm,
    EmployeeAssignmentForm,
    EmployeeForm,
    EmployeePositionAssignmentForm,
    EmployeePositionEndForm,
    EmployeeProfileImageForm,
    PositionForm,
    StatusTransitionForm,
    WorkTeamForm,
)
from apps.workforce.models import (
    AssignmentStatus,
    Department,
    EmployeePositionAssignment,
    EmployeeStatus,
    Position,
)
from apps.workforce.services import (
    archive_department,
    archive_employee,
    archive_position,
    archive_work_team,
    assign_employee_position,
    assign_employee_to_project,
    create_department,
    create_employee,
    create_employee_from_member,
    create_position,
    create_work_team,
    end_employee_position,
    get_active_chief_executive,
    get_active_department_position_assignments,
    get_employee_position_assignments,
    get_organization_departments,
    get_organization_employees,
    get_organization_positions,
    get_organization_project_assignments,
    get_organization_work_teams,
    link_employee_account,
    transition_employee_status,
    transition_project_assignment_status,
    unlink_employee_account,
    update_department,
    update_employee_profile_image,
    update_position,
)
from core.list_filters import (
    apply_table_filters,
    build_table_filters,
    has_active_table_filters,
)

_IMAGE_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


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
    return render(
        request,
        "workforce/employee_list.html",
        {
            "employees": employees,
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
) -> HttpResponse:
    records = apply_table_filters(
        service(user=request.user, organization=request.organization),
        request,
        text_fields=text_fields,
    )
    return render(
        request,
        template_name,
        {
            context_name: records,
            "filters": build_table_filters(request, filters),
            "has_active_filters": has_active_table_filters(request),
        },
    )


def _build_department_tree(departments) -> list[dict[str, object]]:
    nodes = {
        department.pk: {
            "department": department,
            "children": [],
            "positions": [],
            "work_teams": [],
            "employees": [],
            "position_holders": [],
            "employees_without_unit_position": [],
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
    departments = list(
        get_organization_departments(
            user=request.user, organization=request.organization
        )
    )
    tree = _build_department_tree(departments)
    nodes = {node["department"].pk: node for node in _walk_department_tree(tree)}

    can_view_positions = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.POSITIONS_VIEW,
    )
    if can_view_positions:
        for position in get_organization_positions(
            user=request.user, organization=request.organization
        ):
            if position.department_id in nodes:
                nodes[position.department_id]["positions"].append(position)
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
    unassigned_employees = []
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
            elif employee.department_id is None:
                unassigned_employees.append(employee)

    for node in nodes.values():
        node["employees_without_unit_position"] = list(node["employees"])

    chief_executive = None
    if can_view_employees and can_view_positions:
        chief_executive = get_active_chief_executive(
            user=request.user, organization=request.organization
        )
        if chief_executive in unassigned_employees:
            unassigned_employees.remove(chief_executive)
        holders_by_department: dict[object, dict[object, dict[str, object]]] = {}
        for assignment in get_active_department_position_assignments(
            user=request.user, organization=request.organization
        ):
            department_id = assignment.position.department_id
            if department_id not in nodes:
                continue
            department_holders = holders_by_department.setdefault(department_id, {})
            holder = department_holders.setdefault(
                assignment.employee_id,
                {"employee": assignment.employee, "positions": []},
            )
            holder["positions"].append(assignment.position)

        for department_id, department_holders in holders_by_department.items():
            node = nodes[department_id]
            node["position_holders"] = list(department_holders.values())
            holder_ids = set(department_holders)
            node["employees_without_unit_position"] = [
                employee
                for employee in node["employees"]
                if employee.pk not in holder_ids
            ]

    _annotate_department_tree(tree, depth=1)

    return render(
        request,
        "workforce/department_list.html",
        {
            "organization": request.organization,
            "departments": departments,
            "department_tree": tree,
            "chief_executive": chief_executive,
            "organization_employee_count": len(employees),
            "can_view_employees": can_view_employees,
            "can_view_chief_executive": can_view_employees and can_view_positions,
            "unassigned_employees": unassigned_employees,
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


@active_organization_required
@organization_permission_required(BusinessPermissionCode.POSITIONS_VIEW)
@require_GET
def position_list(request: HttpRequest) -> HttpResponse:
    return _master_list(
        request,
        get_organization_positions,
        "workforce/position_list.html",
        "positions",
        text_fields={
            "position": ("code", "title"),
            "department": ("department__name",),
        },
        filters=[
            {"name": "position", "kind": "text", "label": "کد و عنوان"},
            {"name": "department", "kind": "text", "label": "واحد شرکتی"},
            None,
            None,
            None,
        ],
    )


def _position_form_initial(position: Position) -> dict[str, object]:
    return {
        "code": position.code,
        "title": position.title,
        "department": position.department_id,
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
    form = PositionForm(request.POST, organization=request.organization)
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
    return render(
        request,
        "workforce/assignment_list.html",
        {
            "assignments": assignments,
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
