from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.organizations.forms import OrganizationProfileForm
from apps.organizations.models import OrganizationSettings, OrganizationStatus
from apps.organizations.platform_companies import (
    change_company_status,
    company_activity,
    company_governors,
    filter_company_activity,
    incomplete_company_onboarding,
    platform_companies,
    retry_company_onboarding,
    update_platform_company,
)
from apps.organizations.platform_forms import (
    ActivitySearchForm,
    CompanyChangeForm,
    CompanySearchForm,
    CompanyStatusForm,
    PlatformCompanySettingsForm,
)
from core.list_filters import paginate_table


@login_required
@require_GET
def company_list(request: HttpRequest) -> HttpResponse:
    companies = platform_companies(actor=request.user)
    form = CompanySearchForm(request.GET)
    if form.is_valid():
        search = form.cleaned_data["q"]
        companies = companies.filter(
            Q(name__icontains=search)
            | Q(legal_name__icontains=search)
            | Q(slug__icontains=search)
        )
        if form.cleaned_data["status"]:
            companies = companies.filter(status=form.cleaned_data["status"])
    else:
        companies = companies.none()
    page = paginate_table(
        companies, request, sort_fields={}, default_ordering=("name", "pk")
    )
    return render(
        request,
        "organizations/platform_company_list.html",
        {
            "companies": page.object_list,
            "platform_workspace": True,
            "page_obj": page,
            "search_form": form,
            "pagination_rendered": True,
        },
    )


@login_required
@require_GET
def company_detail(request: HttpRequest, organization_id) -> HttpResponse:
    organization = get_object_or_404(
        platform_companies(actor=request.user), pk=organization_id
    )
    events = company_activity(actor=request.user, organization=organization)
    owners, tenant_admins = company_governors(organization)
    form = ActivitySearchForm(request.GET)
    if form.is_valid():
        events = filter_company_activity(events, search=form.cleaned_data["q"])
    else:
        events = events.none()
    page = paginate_table(
        events, request, sort_fields={}, default_ordering=("-created_at", "-pk")
    )
    target = (
        OrganizationStatus.SUSPENDED
        if organization.status == OrganizationStatus.ACTIVE
        else OrganizationStatus.ACTIVE
    )
    status_form = CompanyStatusForm(
        initial={
            "expected_updated_at": organization.updated_at.isoformat(),
            "target_status": target,
        }
    )
    return render(
        request,
        "organizations/platform_company_detail.html",
        {
            "company": organization,
            "platform_workspace": True,
            "platform_target": organization,
            "owners": owners,
            "tenant_admins": tenant_admins,
            "onboarding_incomplete": organization.is_active
            and incomplete_company_onboarding(organization),
            "events": page.object_list,
            "page_obj": page,
            "search_form": form,
            "status_form": status_form,
            "can_change": organization.status
            in {OrganizationStatus.ACTIVE, OrganizationStatus.SUSPENDED}
            and organization.deleted_at is None
            and organization.archived_at is None,
            "suspending": target == OrganizationStatus.SUSPENDED,
            "pagination_rendered": True,
        },
    )


@login_required
@require_POST
def company_status(request: HttpRequest, organization_id) -> HttpResponse:
    get_object_or_404(platform_companies(actor=request.user), pk=organization_id)
    form = CompanyStatusForm(request.POST)
    if form.is_valid():
        try:
            change_company_status(
                actor=request.user, organization_id=organization_id, **form.cleaned_data
            )
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, "وضعیت شرکت به‌روزرسانی شد.")
    else:
        messages.error(request, "وضعیت، دلیل و نسخه اطلاعات شرکت را بررسی کنید.")
    return redirect(
        "organizations:platform_company_detail", organization_id=organization_id
    )


@login_required
@require_POST
def company_onboarding(request: HttpRequest, organization_id) -> HttpResponse:
    get_object_or_404(platform_companies(actor=request.user), pk=organization_id)
    try:
        retry_company_onboarding(actor=request.user, organization_id=organization_id)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "گردش‌کارهای اولیه بررسی و تکمیل شدند.")
    return redirect(
        "organizations:platform_company_detail", organization_id=organization_id
    )


@login_required
@require_http_methods(["GET", "POST"])
def company_edit(request: HttpRequest, organization_id) -> HttpResponse:
    organization = get_object_or_404(
        platform_companies(actor=request.user), pk=organization_id
    )
    data = request.POST if request.method == "POST" else None
    profile_form = OrganizationProfileForm(
        data, instance=organization, prefix="profile"
    )
    settings_form = PlatformCompanySettingsForm(
        data,
        instance=get_object_or_404(OrganizationSettings, organization=organization),
        prefix="settings",
    )
    change_form = CompanyChangeForm(
        data, initial={"expected_updated_at": organization.updated_at.isoformat()}
    )
    if request.method == "POST":
        valid = [form.is_valid() for form in (profile_form, settings_form, change_form)]
        if all(valid):
            try:
                update_platform_company(
                    actor=request.user,
                    organization_id=organization_id,
                    profile_data=profile_form.cleaned_data,
                    settings_data=settings_form.cleaned_data,
                    **change_form.cleaned_data,
                )
            except ValidationError as exc:
                change_form.add_error(None, ValidationError(exc.messages))
            except IntegrityError:
                change_form.add_error(None, "اطلاعات ثبتی با یک شرکت دیگر تداخل دارد.")
            else:
                messages.success(request, "مشخصات و تنظیمات شرکت ذخیره شد.")
                return redirect(
                    "organizations:platform_company_detail",
                    organization_id=organization_id,
                )
    return render(
        request,
        "organizations/platform_company_edit.html",
        {
            "company": organization,
            "platform_workspace": True,
            "platform_target": organization,
            "profile_form": profile_form,
            "settings_form": settings_form,
            "change_form": change_form,
        },
    )
