from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.organizations.decorators import active_organization_required
from apps.projects.forms import ProjectForm
from apps.projects.services import (
    archive_project,
    create_project,
    get_organization_project,
    get_organization_projects,
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
