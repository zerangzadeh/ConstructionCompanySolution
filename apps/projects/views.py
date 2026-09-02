from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.organizations.decorators import active_organization_required
from apps.projects.forms import ProjectForm, ProjectPhaseForm, ProjectSiteForm
from apps.projects.services import (
    archive_project,
    create_project,
    create_project_phase,
    create_project_site,
    get_available_phase_statuses,
    get_organization_project,
    get_organization_project_phase,
    get_organization_project_phases,
    get_organization_project_site,
    get_organization_project_sites,
    get_organization_projects,
    transition_project_phase_status,
)


@active_organization_required
@require_GET
def project_list(request: HttpRequest) -> HttpResponse:
    """List non-deleted projects for the active organization."""

    projects = get_organization_projects(
        user=request.user,
        organization=request.organization,
    )
    return render(request, "projects/list.html", {"projects": projects})


@active_organization_required
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
                budget=data["budget"],
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("projects:list")

    return render(request, "projects/create.html", {"form": form})


@active_organization_required
@require_GET
def project_detail(request: HttpRequest, project_id: str) -> HttpResponse:
    project = get_organization_project(
        user=request.user,
        organization=request.organization,
        project_id=project_id,
    )
    return render(request, "projects/detail.html", {"project": project})


@active_organization_required
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
    return render(
        request,
        "projects/site_list.html",
        {"project": project, "sites": sites},
    )


@active_organization_required
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
    return render(request, "projects/phase_list.html", {"site": site, "phases": phases})


@active_organization_required
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
        messages.success(request, "Project phase status updated.")
    return redirect(
        "projects:phase_detail",
        project_id=project_id,
        site_id=site_id,
        phase_id=phase_id,
    )


@active_organization_required
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
