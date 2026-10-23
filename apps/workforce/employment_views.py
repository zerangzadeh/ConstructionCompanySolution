from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.documents.services import get_organization_documents
from apps.organizations.authorization import require_business_permission
from apps.organizations.decorators import active_organization_required
from apps.organizations.models import BusinessPermissionCode as P

from .employment_forms import EmploymentRecordForm
from .employment_services import own_employment_history, record_employment_version
from .models import EmploymentRecord


@active_organization_required
@require_http_methods(["GET", "POST"])
def employment_manage(request):
    # The canonical command requires organization-level authority for both codes.
    for code in (P.EMPLOYMENT_RECORDS_MANAGE, P.EMPLOYEES_VIEW, P.DOCUMENTS_VIEW):
        require_business_permission(
            user=request.user,
            organization=request.organization,
            permission=code,
            message="اطلاعات مجاز در این شرکت یافت نشد.",
        )
    form = EmploymentRecordForm(
        request.POST if request.method == "POST" else None,
        initial={"relationship": request.GET.get("relationship", "")},
        actor=request.user,
        organization=request.organization,
    )
    if request.method == "POST" and form.is_valid():
        try:
            record_employment_version(
                actor=request.user,
                organization=request.organization,
                **form.cleaned_data,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect("workforce:employment_manage")
    documents = get_organization_documents(
        user=request.user, organization=request.organization
    )
    records = (
        EmploymentRecord.objects.filter(
            organization=request.organization,
            relationship__organization=request.organization,
            document_version__document__in=documents,
        )
        .select_related("relationship__person")
        .order_by("-created_at")[:100]
    )
    response = render(
        request,
        "workforce/employment_manage.html",
        {"form": form, "records": records},
        status=400 if request.method == "POST" else 200,
    )
    response["Cache-Control"] = "private, no-store"
    response["Vary"] = "Cookie"
    return response


@active_organization_required
@require_GET
def employment_history(request):
    try:
        history = own_employment_history(
            actor=request.user, organization=request.organization
        )
        response = render(
            request, "workforce/employment_history.html", {"history": history}
        )
    except PermissionDenied:
        response = render(request, "workforce/ess_unavailable.html", status=403)
    except ValidationError:
        response = render(
            request,
            "workforce/employment_history.html",
            {"history_error": True},
            status=400,
        )
    response["Cache-Control"] = "private, no-store"
    response["Vary"] = "Cookie"
    return response
