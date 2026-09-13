from django.core.exceptions import PermissionDenied
from django.http import FileResponse, HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.documents.forms import DocumentArchiveForm, ProjectDocumentForm
from apps.documents.services import (
    archive_project_document,
    get_organization_document,
    get_organization_documents,
    record_document_download,
    upload_project_document,
)
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DOCUMENTS_VIEW)
def document_list(request: HttpRequest) -> HttpResponse:
    documents = get_organization_documents(
        user=request.user,
        organization=request.organization,
    )
    return render(request, "documents/list.html", {"documents": documents})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DOCUMENTS_UPLOAD)
def document_upload(request: HttpRequest) -> HttpResponse:
    form = ProjectDocumentForm(
        request.POST or None,
        request.FILES or None,
        organization=request.organization,
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            upload_project_document(
                organization=request.organization,
                project=data["project"],
                payment=data["payment"],
                actor=request.user,
                document_type=data["document_type"],
                title=data["title"],
                upload=data["file"],
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("documents:list")
    return render(request, "documents/upload.html", {"form": form})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DOCUMENTS_DOWNLOAD)
def document_download(request: HttpRequest, document_id: str) -> FileResponse:
    document = get_organization_document(
        user=request.user,
        organization=request.organization,
        document_id=str(document_id),
    )
    record_document_download(document=document, actor=request.user)
    response = FileResponse(
        document.file.open("rb"),
        as_attachment=True,
        filename=document.original_file_name,
    )
    response["Content-Type"] = document.content_type
    response["X-Content-Type-Options"] = "nosniff"
    return response


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DOCUMENTS_VIEW)
def document_detail(request: HttpRequest, document_id: str) -> HttpResponse:
    document = get_organization_document(
        user=request.user,
        organization=request.organization,
        document_id=str(document_id),
    )
    return render(
        request,
        "documents/detail.html",
        {"document": document, "form": DocumentArchiveForm()},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DOCUMENTS_ARCHIVE)
def document_archive(request: HttpRequest, document_id: str) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)
    document = get_organization_document(
        user=request.user,
        organization=request.organization,
        document_id=str(document_id),
    )
    form = DocumentArchiveForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            "documents/detail.html",
            {"document": document, "form": form},
            status=400,
        )
    try:
        archive_project_document(
            document=document,
            actor=request.user,
            reason=form.cleaned_data["reason"],
        )
    except PermissionDenied as exc:
        form.add_error(None, str(exc))
        return render(
            request,
            "documents/detail.html",
            {"document": document, "form": form},
            status=403,
        )
    except ValueError as exc:
        form.add_error(None, str(exc))
        return render(
            request,
            "documents/detail.html",
            {"document": document, "form": form},
            status=400,
        )
    return redirect("documents:list")
