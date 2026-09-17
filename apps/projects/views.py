from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode
from apps.projects.forms import (
    ActivityForm,
    ProjectForm,
    ProjectPhaseForm,
    ProjectSiteForm,
    WBSNodeForm,
)
from apps.projects.models import ProjectPhaseStatus, ProjectStatus
from apps.projects.services import (
    archive_activity,
    archive_project,
    archive_wbs_node,
    create_activity,
    create_project,
    create_project_phase,
    create_project_site,
    create_wbs_node,
    get_available_phase_statuses,
    get_organization_activities,
    get_organization_project,
    get_organization_project_phase,
    get_organization_project_phases,
    get_organization_project_site,
    get_organization_project_sites,
    get_organization_projects,
    get_organization_sites,
    get_organization_wbs_nodes,
    transition_activity_status,
    transition_project_phase_status,
)
from core.list_filters import (
    apply_table_filters,
    build_table_filters,
    has_active_table_filters,
    paginate_table,
    table_pagination_query,
)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROJECTS_VIEW)
@require_GET
def project_list(request: HttpRequest) -> HttpResponse:
    """List non-deleted projects for the active organization."""

    projects = get_organization_projects(
        user=request.user,
        organization=request.organization,
    )
    projects = apply_table_filters(
        projects,
        request,
        text_fields={"code": ("code",), "name": ("name",)},
        choice_fields={"status": ("status", ProjectStatus.values)},
        date_fields={"start_date": "start_date", "end_date": "end_date"},
    )
    page = paginate_table(
        projects,
        request,
        sort_fields={
            "code": "code",
            "name": "name",
            "status": "status",
            "start_date": "start_date",
            "end_date": "end_date",
            "estimated_budget": "estimated_budget",
            "actual_budget": "actual_budget",
        },
        default_ordering=("name", "pk"),
    )
    return render(
        request,
        "projects/list.html",
        {
            "projects": page.object_list,
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "pagination_rendered": True,
            "filters": build_table_filters(
                request,
                [
                    {"name": "code", "kind": "text", "label": "کد پروژه"},
                    {"name": "name", "kind": "text", "label": "نام پروژه"},
                    {
                        "name": "status",
                        "kind": "select",
                        "label": "وضعیت",
                        "choices": ProjectStatus.choices,
                    },
                    {"name": "start_date", "kind": "date_range", "label": "تاریخ شروع"},
                    {"name": "end_date", "kind": "date_range", "label": "تاریخ پایان"},
                    None,
                    None,
                    None,
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROJECTS_CREATE)
def project_create(request: HttpRequest) -> HttpResponse:
    """Create a project for the active organization."""

    form = ProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            create_project(
                organization=request.organization,
                actor=request.user,
                code=data["code"],
                name=data["name"],
                description=data["description"],
                status=data["status"],
                start_date=data["start_date"],
                end_date=data["end_date"],
                estimated_budget=data["estimated_budget"],
                actual_budget=data["actual_budget"],
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("projects:list")

    return render(request, "projects/create.html", {"form": form})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROJECTS_VIEW)
@require_GET
def project_detail(request: HttpRequest, project_id: str) -> HttpResponse:
    project = get_organization_project(
        user=request.user,
        organization=request.organization,
        project_id=project_id,
    )
    return render(request, "projects/detail.html", {"project": project})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROJECT_SITES_VIEW)
@require_GET
def project_site_list(request: HttpRequest, project_id: str) -> HttpResponse:
    project = get_organization_project(
        user=request.user,
        organization=request.organization,
        project_id=project_id,
    )
    sites = get_organization_project_sites(
        user=request.user,
        organization=request.organization,
        project_id=project_id,
    )
    sites = apply_table_filters(
        sites,
        request,
        text_fields={"site": ("code", "name", "address")},
    )
    page = paginate_table(
        sites,
        request,
        sort_fields={"code": "code", "name": "name", "address": "address"},
        default_ordering=("name", "pk"),
    )
    return render(
        request,
        "projects/site_list.html",
        {
            "project": project,
            "sites": page.object_list,
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "filters": build_table_filters(
                request,
                [
                    {"name": "site", "kind": "text", "label": "کد، نام یا نشانی"},
                    None,
                    None,
                    None,
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROJECT_SITES_VIEW)
@require_GET
def site_list(request: HttpRequest) -> HttpResponse:
    """List all worksites belonging to the active organization."""

    sites = get_organization_sites(
        user=request.user,
        organization=request.organization,
    )
    sites = apply_table_filters(
        sites,
        request,
        text_fields={
            "site": ("code", "name", "address"),
            "project": ("project__name",),
        },
    )
    page = paginate_table(
        sites,
        request,
        sort_fields={
            "code": "code",
            "name": "name",
            "project": "project__name",
            "active": "is_active",
            "status": "is_active",
            "address": "address",
        },
        default_ordering=("project__name", "name", "pk"),
    )
    return render(
        request,
        "projects/all_site_list.html",
        {
            "sites": page.object_list,
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "filters": build_table_filters(
                request,
                [
                    {"name": "site", "kind": "text", "label": "کد، نام یا نشانی"},
                    {"name": "project", "kind": "text", "label": "پروژه"},
                    None,
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROJECT_SITES_CREATE)
def project_site_create(request: HttpRequest, project_id: str) -> HttpResponse:
    project = get_organization_project(
        user=request.user,
        organization=request.organization,
        project_id=project_id,
    )
    form = ProjectSiteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            create_project_site(
                organization=request.organization,
                project=project,
                actor=request.user,
                code=data["code"],
                name=data["name"],
                address=data["address"],
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("projects:site_list", project_id=project.pk)
    return render(
        request,
        "projects/site_create.html",
        {"project": project, "form": form},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROJECT_PHASES_VIEW)
@require_GET
def project_phase_list(
    request: HttpRequest,
    project_id: str,
    site_id: str,
) -> HttpResponse:
    site = get_organization_project_site(
        user=request.user,
        organization=request.organization,
        project_id=project_id,
        site_id=site_id,
    )
    phases = get_organization_project_phases(
        user=request.user,
        organization=request.organization,
        project_id=project_id,
        site_id=site_id,
    )
    phases = apply_table_filters(
        phases,
        request,
        text_fields={"phase": ("code", "name")},
        choice_fields={"status": ("status", ProjectPhaseStatus.values)},
        date_fields={
            "planned_start": "planned_start_date",
            "planned_end": "planned_end_date",
        },
    )
    page = paginate_table(
        phases,
        request,
        sort_fields={
            "code": "code",
            "name": "name",
            "status": "status",
            "planned_start": "planned_start_date",
            "planned_end": "planned_end_date",
        },
        default_ordering=("planned_start_date", "name", "pk"),
    )
    return render(
        request,
        "projects/phase_list.html",
        {
            "site": site,
            "phases": page.object_list,
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "filters": build_table_filters(
                request,
                [
                    {"name": "phase", "kind": "text", "label": "کد یا نام فاز"},
                    {
                        "name": "status",
                        "kind": "select",
                        "label": "وضعیت",
                        "choices": ProjectPhaseStatus.choices,
                    },
                    {
                        "name": "planned_start",
                        "kind": "date_range",
                        "label": "شروع برنامه",
                    },
                    {
                        "name": "planned_end",
                        "kind": "date_range",
                        "label": "پایان برنامه",
                    },
                    None,
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROJECT_PHASES_CREATE)
def project_phase_create(
    request: HttpRequest,
    project_id: str,
    site_id: str,
) -> HttpResponse:
    site = get_organization_project_site(
        user=request.user,
        organization=request.organization,
        project_id=project_id,
        site_id=site_id,
    )
    form = ProjectPhaseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            create_project_phase(
                organization=request.organization,
                site=site,
                actor=request.user,
                code=data["code"],
                name=data["name"],
                status=data["status"],
                planned_start_date=data["planned_start_date"],
                planned_end_date=data["planned_end_date"],
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect(
                "projects:phase_list",
                project_id=project_id,
                site_id=site_id,
            )
    return render(request, "projects/phase_create.html", {"site": site, "form": form})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROJECT_PHASES_VIEW)
@require_GET
def project_phase_detail(
    request: HttpRequest,
    project_id: str,
    site_id: str,
    phase_id: str,
) -> HttpResponse:
    phase = get_organization_project_phase(
        user=request.user,
        organization=request.organization,
        project_id=project_id,
        site_id=site_id,
        phase_id=phase_id,
    )
    return render(
        request,
        "projects/phase_detail.html",
        {
            "phase": phase,
            "available_statuses": get_available_phase_statuses(phase),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROJECT_PHASES_TRANSITION)
@require_POST
def project_phase_transition(
    request: HttpRequest,
    project_id: str,
    site_id: str,
    phase_id: str,
) -> HttpResponse:
    try:
        transition_project_phase_status(
            organization=request.organization,
            project_id=project_id,
            site_id=site_id,
            phase_id=phase_id,
            actor=request.user,
            target_status=request.POST.get("status", ""),
        )
    except (PermissionDenied, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "وضعیت فاز پروژه به‌روزرسانی شد.")
    return redirect(
        "projects:phase_detail",
        project_id=project_id,
        site_id=site_id,
        phase_id=phase_id,
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROJECTS_ARCHIVE)
@require_POST
def project_archive(request: HttpRequest, project_id: str) -> HttpResponse:
    try:
        archive_project(
            user=request.user,
            organization=request.organization,
            project_id=project_id,
        )
    except PermissionDenied as exc:
        return HttpResponse(str(exc), status=403)
    return redirect("projects:list")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PROJECT_CONTROLS_VIEW)
def project_controls(request: HttpRequest, project_id: str) -> HttpResponse:
    project = get_organization_project(
        user=request.user, organization=request.organization, project_id=project_id
    )
    return render(
        request,
        "projects/controls.html",
        {
            "project": project,
            "wbs_nodes": get_organization_wbs_nodes(
                user=request.user,
                organization=request.organization,
                project_id=project_id,
            ),
            "activities": get_organization_activities(
                user=request.user,
                organization=request.organization,
                project_id=project_id,
            ),
            "wbs_form": WBSNodeForm(project=project),
            "activity_form": ActivityForm(project=project),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.WBS_NODES_CREATE)
@require_POST
def wbs_node_create(request: HttpRequest, project_id: str) -> HttpResponse:
    project = get_organization_project(
        user=request.user, organization=request.organization, project_id=project_id
    )
    form = WBSNodeForm(request.POST, project=project)
    if form.is_valid():
        try:
            create_wbs_node(
                organization=request.organization,
                project=project,
                actor=request.user,
                **form.cleaned_data,
            )
            messages.success(request, "گره ساختار شکست کار افزوده شد.")
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "فیلدهای ساختار شکست کار را بررسی و دوباره تلاش کنید.")
    return redirect("projects:controls", project_id=project_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACTIVITIES_CREATE)
@require_POST
def activity_create(request: HttpRequest, project_id: str) -> HttpResponse:
    project = get_organization_project(
        user=request.user, organization=request.organization, project_id=project_id
    )
    form = ActivityForm(request.POST, project=project)
    if form.is_valid():
        try:
            create_activity(
                organization=request.organization,
                project=project,
                actor=request.user,
                **form.cleaned_data,
            )
            messages.success(request, "فعالیت افزوده شد.")
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "فیلدهای فعالیت را بررسی و دوباره تلاش کنید.")
    return redirect("projects:controls", project_id=project_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACTIVITIES_TRANSITION)
@require_POST
def activity_transition(
    request: HttpRequest, project_id: str, activity_id: str
) -> HttpResponse:
    activity = (
        get_organization_activities(
            user=request.user, organization=request.organization, project_id=project_id
        )
        .filter(pk=activity_id)
        .first()
    )
    if activity is None:
        return HttpResponse("فعالیت یافت نشد.", status=404)
    try:
        transition_activity_status(
            organization=request.organization,
            actor=request.user,
            activity=activity,
            target_status=request.POST.get("status", ""),
        )
    except (PermissionDenied, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("projects:controls", project_id=project_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACTIVITIES_ARCHIVE)
@require_POST
def activity_archive_view(
    request: HttpRequest, project_id: str, activity_id: str
) -> HttpResponse:
    activity = (
        get_organization_activities(
            user=request.user, organization=request.organization, project_id=project_id
        )
        .filter(pk=activity_id)
        .first()
    )
    if activity is None:
        return HttpResponse("فعالیت یافت نشد.", status=404)
    try:
        archive_activity(
            organization=request.organization, actor=request.user, activity=activity
        )
    except (PermissionDenied, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("projects:controls", project_id=project_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.WBS_NODES_ARCHIVE)
@require_POST
def wbs_node_archive_view(
    request: HttpRequest, project_id: str, node_id: str
) -> HttpResponse:
    node = (
        get_organization_wbs_nodes(
            user=request.user, organization=request.organization, project_id=project_id
        )
        .filter(pk=node_id)
        .first()
    )
    if node is None:
        return HttpResponse("گره WBS یافت نشد.", status=404)
    try:
        archive_wbs_node(
            organization=request.organization, actor=request.user, node=node
        )
    except (PermissionDenied, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("projects:controls", project_id=project_id)
