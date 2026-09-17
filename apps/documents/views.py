from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.documents.forms import (
    DocumentArchiveForm,
    DocumentCreateForm,
    DocumentLinkForm,
    DocumentVersionForm,
)
from apps.documents.models import DocumentType
from apps.documents.services import (
    add_document_link,
    add_document_version,
    archive_document,
    create_document,
    get_document_version_for_download,
    get_organization_document,
    get_organization_documents,
    record_document_download,
)
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode
from core.list_filters import (
    apply_table_filters,
    build_table_filters,
    has_active_table_filters,
    paginate_table,
    table_pagination_query,
)


def _detail_context(request: HttpRequest, document: object, **extra: object) -> dict:
    context = {
        "document": document,
        "archive_form": DocumentArchiveForm(),
        "version_form": DocumentVersionForm(),
        "link_form": DocumentLinkForm(
            organization=request.organization,
            user=request.user,
            document=document,
        ),
    }
    context.update(extra)
    return context


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DOCUMENTS_VIEW)
def document_list(request: HttpRequest) -> HttpResponse:
    documents = get_organization_documents(
        user=request.user,
        organization=request.organization,
    )
    documents = apply_table_filters(
        documents,
        request,
        text_fields={
            "document": ("title", "reference"),
            "version": ("current_version__original_file_name",),
        },
        choice_fields={"document_type": ("document_type", DocumentType.values)},
    )
    page = paginate_table(
        documents,
        request,
        sort_fields={
            "document": "title",
            "document_type": "document_type",
            "version": "current_version__version_number",
            "created_at": "created_at",
        },
        default_ordering=("-created_at", "pk"),
    )
    return render(
        request,
        "documents/list.html",
        {
            "documents": page.object_list,
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "filters": build_table_filters(
                request,
                [
                    {"name": "document", "kind": "text", "label": "سند"},
                    None,
                    {
                        "name": "document_type",
                        "kind": "select",
                        "label": "نوع",
                        "choices": DocumentType.choices,
                    },
                    {"name": "version", "kind": "text", "label": "نسخه جاری"},
                    None,
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DOCUMENTS_UPLOAD)
def document_upload(request: HttpRequest) -> HttpResponse:
    form = DocumentCreateForm(
        request.POST or None,
        request.FILES or None,
        organization=request.organization,
        user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            document = create_document(
                organization=request.organization,
                actor=request.user,
                document_type=data["document_type"],
                title=data["title"],
                reference=data["reference"],
                description=data["description"],
                upload=data["file"],
                target=form.selected_target(),
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("documents:detail", document_id=document.pk)
    return render(request, "documents/upload.html", {"form": form})


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
        _detail_context(request, document),
    )


def _download_response(version: object) -> FileResponse:
    response = FileResponse(
        version.file.open("rb"),
        as_attachment=True,
        filename=version.original_file_name,
    )
    response["Content-Type"] = version.content_type
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Disposition"] = response["Content-Disposition"].replace(
        "inline", "attachment"
    )
    return response


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DOCUMENTS_DOWNLOAD)
def document_download(request: HttpRequest, document_id: str) -> FileResponse:
    document = get_organization_document(
        user=request.user,
        organization=request.organization,
        document_id=str(document_id),
    )
    version = get_document_version_for_download(
        document=document,
        version_id=str(document.current_version_id),
        actor=request.user,
    )
    record_document_download(version=version, actor=request.user)
    return _download_response(version)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DOCUMENTS_DOWNLOAD)
def document_version_download(
    request: HttpRequest, document_id: str, version_id: str
) -> FileResponse:
    document = get_organization_document(
        user=request.user,
        organization=request.organization,
        document_id=str(document_id),
    )
    version = get_document_version_for_download(
        document=document,
        version_id=str(version_id),
        actor=request.user,
    )
    record_document_download(version=version, actor=request.user)
    return _download_response(version)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DOCUMENTS_UPLOAD)
def document_version_add(request: HttpRequest, document_id: str) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)
    document = get_organization_document(
        user=request.user,
        organization=request.organization,
        document_id=str(document_id),
    )
    form = DocumentVersionForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            add_document_version(
                document=document,
                actor=request.user,
                upload=form.cleaned_data["file"],
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("documents:detail", document_id=document.pk)
    return render(
        request,
        "documents/detail.html",
        _detail_context(request, document, version_form=form),
        status=400,
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.DOCUMENTS_UPLOAD)
def document_link_add(request: HttpRequest, document_id: str) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)
    document = get_organization_document(
        user=request.user,
        organization=request.organization,
        document_id=str(document_id),
    )
    form = DocumentLinkForm(
        request.POST,
        organization=request.organization,
        user=request.user,
        document=document,
    )
    if form.is_valid():
        try:
            add_document_link(
                document=document,
                actor=request.user,
                target=form.selected_target(),
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("documents:detail", document_id=document.pk)
    return render(
        request,
        "documents/detail.html",
        _detail_context(request, document, link_form=form),
        status=400,
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
    if form.is_valid():
        try:
            archive_document(
                document=document,
                actor=request.user,
                reason=form.cleaned_data["reason"],
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("documents:list")
    return render(
        request,
        "documents/detail.html",
        _detail_context(request, document, archive_form=form),
        status=400,
    )
