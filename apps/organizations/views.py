from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
)
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
    require_organization_permission,
)
from apps.organizations.forms import (
    ExistingAccountConnectionForm,
    OrganizationAccountCreateForm,
    OrganizationForm,
    OrganizationMembershipForm,
    OrganizationProfileForm,
    OrganizationSettingsForm,
)
from apps.organizations.models import (
    AccountConnectionRequestStatus,
    BusinessPermissionCode,
    OrganizationAccountConnectionRequest,
    OrganizationMembership,
)
from apps.organizations.services import (
    create_organization_account,
    create_organization_by_system_admin,
    get_organization_members,
    get_organization_settings,
    get_valid_memberships,
    request_existing_account_connection,
    resolve_active_organization,
    set_active_organization,
    update_organization_membership,
    update_organization_settings,
)


@login_required
@require_GET
def select_organization(request: HttpRequest) -> HttpResponse:
    """Render organizations available to the authenticated user."""

    memberships = get_valid_memberships(request.user)
    pending_connection_count = OrganizationAccountConnectionRequest.objects.filter(
        target_user=request.user,
        status=AccountConnectionRequestStatus.PENDING,
    ).count()
    return render(
        request,
        "organizations/select.html",
        {
            "memberships": memberships,
            "pending_connection_count": pending_connection_count,
        },
    )


@login_required
@require_POST
def switch_organization(request: HttpRequest) -> HttpResponse:
    """Set the active organization after validating the user's membership."""

    organization_id = request.POST.get("organization_id")
    organization = resolve_active_organization(request.user, organization_id)
    if organization is None:
        return HttpResponseForbidden("به این سازمان دسترسی ندارید.")

    set_active_organization(request.session, organization)
    return redirect("organizations:select")


@login_required
def create_organization(request: HttpRequest) -> HttpResponse:
    """Allow only the global system administrator to create a tenant."""

    if not request.user.is_superuser:
        return HttpResponseForbidden("فقط ادمین سامانه می‌تواند شرکت جدید ایجاد کند.")

    if request.method == "POST":
        form = OrganizationForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            organization = create_organization_by_system_admin(
                actor=request.user,
                owner=request.user,
                name=data["name"],
                legal_name=data["legal_name"],
                slug=data["slug"],
                registration_number=data["registration_number"],
                national_id=data["national_id"],
                economic_code=data["economic_code"],
                phone=data["phone"],
                email=data["email"],
                website=data["website"],
                province=data["province"],
                city=data["city"],
                address=data["address"],
                postal_code=data["postal_code"],
                timezone_name=data["timezone"],
                currency=data["currency"],
            )
            set_active_organization(request.session, organization)
            return redirect("organizations:select")
    else:
        form = OrganizationForm()

    return render(
        request,
        "organizations/create.html",
        {"form": form},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.MEMBERSHIP_VIEW)
@require_GET
def organization_members(request: HttpRequest) -> HttpResponse:
    """List active members belonging only to the active organization."""

    can_change_roles = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.MEMBERSHIP_CHANGE_ROLE,
    )
    can_change_statuses = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.MEMBERSHIP_CHANGE_STATUS,
    )
    can_create_accounts = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.ACCOUNTS_CREATE,
    )
    memberships = get_organization_members(
        user=request.user,
        organization=request.organization,
        include_inactive=can_change_statuses,
    )
    return render(
        request,
        "organizations/members.html",
        {
            "memberships": memberships,
            "can_manage_members": can_change_roles or can_change_statuses,
            "can_create_accounts": can_create_accounts,
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTS_CREATE)
def organization_account_create(request: HttpRequest) -> HttpResponse:
    """Create a tenant account or request consent from an existing identity."""

    actor_membership = get_active_membership(
        user=request.user, organization=request.organization
    )
    allow_owner_role = actor_membership.role_definition.is_owner
    action = request.POST.get("action") if request.method == "POST" else None
    create_form = OrganizationAccountCreateForm(
        request.POST if action == "create" else None,
        allow_owner_role=allow_owner_role,
        prefix="create",
    )
    connection_form = ExistingAccountConnectionForm(
        request.POST if action == "connect" else None,
        allow_owner_role=allow_owner_role,
        prefix="connect",
    )
    if action == "create" and create_form.is_valid():
        data = create_form.cleaned_data
        try:
            create_organization_account(
                organization=request.organization,
                actor=request.user,
                username=data["username"],
                temporary_password=data["temporary_password"],
                role=data["role_definition"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                email=data["email"],
                phone_number=data["phone_number"],
                national_id=data["national_id"],
            )
        except (PermissionDenied, ValueError) as exc:
            create_form.add_error(None, str(exc))
        else:
            messages.success(
                request,
                "حساب ساخته شد؛ کاربر در نخستین ورود باید گذرواژه خود را تغییر دهد.",
            )
            return redirect("organizations:members")
    elif action == "connect" and connection_form.is_valid():
        data = connection_form.cleaned_data
        try:
            request_existing_account_connection(
                organization=request.organization,
                actor=request.user,
                username=data["username"],
                role=data["role_definition"],
            )
        except (PermissionDenied, ValueError) as exc:
            connection_form.add_error(None, str(exc))
        else:
            messages.success(
                request,
                "اگر حساب واردشده واجد شرایط باشد، درخواست اتصال برای صاحب آن ثبت می‌شود.",
            )
            return redirect("organizations:members")
    return render(
        request,
        "organizations/account_create.html",
        {"create_form": create_form, "connection_form": connection_form},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.COMPANY_SETTINGS_VIEW)
def organization_settings(request: HttpRequest) -> HttpResponse:
    """View and update settings for the resolved active organization."""

    can_change_settings = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.COMPANY_SETTINGS_CHANGE,
    )
    settings_record = get_organization_settings(organization=request.organization)
    if request.method == "POST":
        require_organization_permission(
            request,
            BusinessPermissionCode.COMPANY_SETTINGS_CHANGE,
            "اجازه ویرایش تنظیمات این شرکت را ندارید.",
        )
        profile_form = OrganizationProfileForm(
            request.POST,
            instance=request.organization,
            prefix="profile",
        )
        settings_form = OrganizationSettingsForm(
            request.POST,
            request.FILES,
            instance=settings_record,
            prefix="settings",
        )
        profile_is_valid = profile_form.is_valid()
        settings_are_valid = settings_form.is_valid()
        if profile_is_valid and settings_are_valid:
            try:
                update_organization_settings(
                    organization=request.organization,
                    updated_by=request.user,
                    timezone_name=settings_form.cleaned_data["timezone"],
                    currency=settings_form.cleaned_data["currency"],
                    fiscal_year_start_month=settings_form.cleaned_data[
                        "fiscal_year_start_month"
                    ],
                    fiscal_year_start_day=settings_form.cleaned_data[
                        "fiscal_year_start_day"
                    ],
                    language=settings_form.cleaned_data["language"],
                    project_code_prefix=settings_form.cleaned_data[
                        "project_code_prefix"
                    ],
                    contract_code_prefix=settings_form.cleaned_data[
                        "contract_code_prefix"
                    ],
                    site_code_prefix=settings_form.cleaned_data["site_code_prefix"],
                    document_code_prefix=settings_form.cleaned_data[
                        "document_code_prefix"
                    ],
                    logo=settings_form.cleaned_data["logo"],
                    profile_data=profile_form.cleaned_data,
                )
            except PermissionDenied as exc:
                return HttpResponseForbidden(str(exc))
            messages.success(request, "اطلاعات و تنظیمات شرکت ذخیره شد.")
            return redirect("organizations:settings")
    else:
        profile_form = OrganizationProfileForm(
            instance=request.organization,
            prefix="profile",
        )
        settings_form = OrganizationSettingsForm(
            instance=settings_record,
            prefix="settings",
        )

    if not can_change_settings:
        for form in (profile_form, settings_form):
            for field in form.fields.values():
                field.disabled = True

    return render(
        request,
        "organizations/settings.html",
        {
            "profile_form": profile_form,
            "settings_form": settings_form,
            "can_change_settings": can_change_settings,
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.MEMBERSHIP_VIEW)
def update_member(request: HttpRequest, membership_id: str) -> HttpResponse:
    """Update a tenant membership through the audited authorization service."""

    can_change_role = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.MEMBERSHIP_CHANGE_ROLE,
    )
    can_change_status = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.MEMBERSHIP_CHANGE_STATUS,
    )
    if not (can_change_role or can_change_status):
        return HttpResponseForbidden("اجازه مدیریت اعضای این شرکت را ندارید.")
    try:
        membership = OrganizationMembership.objects.select_related(
            "user", "role_definition"
        ).get(pk=membership_id, organization=request.organization)
    except OrganizationMembership.DoesNotExist as exc:
        raise PermissionDenied("عضویت موردنظر در این شرکت یافت نشد.") from exc

    actor_membership = None
    if not request.user.is_superuser:
        actor_membership = get_active_membership(
            user=request.user,
            organization=request.organization,
        )
    allow_owner_role = request.user.is_superuser or bool(
        actor_membership and actor_membership.role_definition.is_owner
    )
    if (
        membership.role_definition_id is not None
        and membership.role_definition.is_owner
        and not allow_owner_role
    ):
        return HttpResponseForbidden("فقط مالک شرکت می‌تواند عضویت مالک را مدیریت کند.")

    if request.method == "POST":
        form = OrganizationMembershipForm(
            request.POST,
            instance=membership,
            allow_owner_role=allow_owner_role,
        )
        if form.is_valid():
            try:
                update_organization_membership(
                    organization=request.organization,
                    actor=request.user,
                    membership=membership,
                    role=form.cleaned_data["role_definition"],
                    status=form.cleaned_data["status"],
                )
            except (PermissionDenied, ValueError) as exc:
                form.add_error(None, str(exc))
            else:
                if membership.status == "pending_role":
                    success_message = "نقش تعیین و دسترسی کاربر فعال شد."
                else:
                    success_message = "عضویت کاربر با موفقیت به‌روزرسانی شد."
                messages.success(request, success_message)
                return redirect("organizations:members")
    else:
        form = OrganizationMembershipForm(
            instance=membership,
            allow_owner_role=allow_owner_role,
        )
    if not can_change_role:
        form.fields["role_definition"].disabled = True
    if not can_change_status:
        form.fields["status"].disabled = True
    return render(
        request,
        "organizations/member_form.html",
        {"form": form, "membership": membership},
    )
