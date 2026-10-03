import json
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import (
    FileResponse,
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
)
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.models import User
from apps.organizations.access_services import (
    archive_organization_role,
    assign_membership_role,
    create_organization_role,
    create_protected_operation_version,
    grant_membership_scope,
    retire_protected_operation,
    revoke_membership_role,
    revoke_membership_scope,
    update_organization_role,
)
from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
    is_platform_admin,
    membership_has_role,
    membership_is_tenant_owner,
)
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
    require_organization_permission,
)
from apps.organizations.forms import (
    ExistingAccountConnectionForm,
    MembershipRoleAssignmentForm,
    MembershipScopeGrantForm,
    OrganizationAccountCreateForm,
    OrganizationForm,
    OrganizationMemberPasswordResetForm,
    OrganizationMembershipForm,
    OrganizationProfileForm,
    OrganizationRoleCatalogForm,
    OrganizationSettingsForm,
    ProtectedOperationCatalogForm,
)
from apps.organizations.models import (
    AccountConnectionRequestStatus,
    BusinessPermissionCode,
    MembershipRole,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    Organization,
    OrganizationAccountConnectionRequest,
    OrganizationMembership,
    OrganizationRole,
    PlatformPolicy,
    PlatformPolicyVersion,
    PolicySource,
    ProtectedOperation,
)
from apps.organizations.policy_services import (
    apply_tenant_policy_selection,
    create_platform_policy,
    create_platform_policy_version,
    link_policy_version_source,
    list_tenant_policy_selections,
    publish_platform_policy_version,
    record_optional_policy_review,
    record_policy_source,
    retire_platform_policy_version,
    select_tenant_policy_version,
    update_platform_policy_version,
)
from apps.organizations.policy_specs import (
    PLATFORM_POLICY_SPECS,
    policy_version_is_configuration_ready,
)
from apps.organizations.services import (
    create_organization_account,
    create_organization_by_system_admin,
    get_organization_members,
    get_organization_settings,
    get_valid_memberships,
    request_existing_account_connection,
    reset_organization_member_password,
    resolve_active_organization,
    set_active_organization,
    update_organization_membership,
    update_organization_settings,
)
from core.list_filters import apply_table_sorting


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
            "is_platform_admin": is_platform_admin(request.user),
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
    return redirect("financials:dashboard")


@login_required
def create_organization(request: HttpRequest) -> HttpResponse:
    """Allow only the global system administrator to create a tenant."""

    if not is_platform_admin(request.user):
        return HttpResponseForbidden("فقط ادمین پلتفرم می‌تواند شرکت جدید ایجاد کند.")

    if request.method == "POST":
        form = OrganizationForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            owner = User.objects.get(
                username=data["initial_owner_username"], is_active=True
            )
            create_organization_by_system_admin(
                actor=request.user,
                owner=owner,
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
    actor_membership = get_active_membership(
        user=request.user, organization=request.organization
    )
    memberships = get_organization_members(
        user=request.user,
        organization=request.organization,
        include_inactive=can_change_statuses,
    )
    memberships = apply_table_sorting(
        memberships,
        request,
        sort_fields={
            "user": ("user__last_name", "user__first_name"),
            "username": "user__username",
            "role": "role_definition__name",
            "status": "status",
        },
        default_ordering=("user__username", "pk"),
    )
    return render(
        request,
        "organizations/members.html",
        {
            "memberships": memberships,
            "can_manage_members": can_change_roles or can_change_statuses,
            "can_create_accounts": can_create_accounts,
            "can_manage_role_catalog": membership_has_role(
                actor_membership, MembershipRole.TENANT_ADMIN
            ),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.MEMBERSHIP_VIEW)
@require_GET
def member_profile_image(request: HttpRequest, membership_id: str) -> FileResponse:
    """Serve a member avatar only within the viewer's active organization."""

    try:
        membership = OrganizationMembership.objects.select_related("user").get(
            pk=membership_id,
            organization=request.organization,
        )
    except OrganizationMembership.DoesNotExist as exc:
        raise Http404 from exc

    if not membership.user.profile_image:
        raise Http404
    try:
        image = membership.user.profile_image.open("rb")
    except (FileNotFoundError, OSError) as exc:
        raise Http404 from exc

    extension = "." + membership.user.profile_image.name.lower().rsplit(".", 1)[-1]
    content_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(extension)
    if content_type is None:
        image.close()
        raise Http404

    response = FileResponse(image, content_type=content_type)
    response["Cache-Control"] = "private, max-age=300"
    response["X-Content-Type-Options"] = "nosniff"
    return response


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
        organization=request.organization,
        prefix="create",
    )
    connection_form = ExistingAccountConnectionForm(
        request.POST if action == "connect" else None,
        allow_owner_role=allow_owner_role,
        organization=request.organization,
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

    actor_membership = get_active_membership(
        user=request.user,
        organization=request.organization,
    )
    allow_owner_role = membership_is_tenant_owner(actor_membership)
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
    form.fields["role_definition"].disabled = True
    form.fields[
        "role_definition"
    ].help_text = "نقش سازگار فقط نمایش داده می‌شود؛ نقش‌های مستقل از مسیر نقش‌ها و دامنه‌ها مدیریت می‌شوند."
    if not can_change_status:
        form.fields["status"].disabled = True
    return render(
        request,
        "organizations/member_form.html",
        {
            "form": form,
            "membership": membership,
            "can_reset_member_password": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.ACCOUNTS_RESET_PASSWORD,
            ),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.MEMBERSHIP_VIEW)
def member_authorization(request: HttpRequest, membership_id: str) -> HttpResponse:
    """Manage independent roles and object scopes without compatibility writes."""

    if not (
        has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=BusinessPermissionCode.AUTHORIZATION_ROLES_VIEW,
        )
        or has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=BusinessPermissionCode.AUTHORIZATION_GRANTS_VIEW,
        )
    ):
        return HttpResponseForbidden("اجازه مشاهده کنترل‌های مجوزدهی را ندارید.")
    membership = (
        OrganizationMembership.objects.select_related("user")
        .filter(
            pk=membership_id,
            organization=request.organization,
        )
        .first()
    )
    if membership is None:
        raise PermissionDenied("عضویت موردنظر در این شرکت یافت نشد.")
    actor_membership = get_active_membership(
        user=request.user, organization=request.organization
    )
    form_kwargs = {
        "organization": request.organization,
        "actor_membership": actor_membership,
        "target_membership": membership,
    }
    role_form = MembershipRoleAssignmentForm(prefix="role", **form_kwargs)
    scope_form = MembershipScopeGrantForm(prefix="scope", **form_kwargs)
    if request.method == "POST":
        action = request.POST.get("action", "")
        try:
            if action == "assign_role":
                role_form = MembershipRoleAssignmentForm(
                    request.POST, prefix="role", **form_kwargs
                )
                if role_form.is_valid():
                    assign_membership_role(
                        organization=request.organization,
                        actor=request.user,
                        membership_id=membership.pk,
                        role=role_form.cleaned_data["role"],
                        approver_membership_id=role_form.cleaned_data[
                            "approver_membership"
                        ].pk,
                        reason=role_form.cleaned_data["reason"],
                        ends_at=role_form.cleaned_data["ends_at"],
                    )
                    messages.success(request, "نقش مستقل ثبت شد.")
                    return redirect(
                        "organizations:member_authorization",
                        membership_id=membership.pk,
                    )
            elif action == "grant_scope":
                scope_form = MembershipScopeGrantForm(
                    request.POST, prefix="scope", **form_kwargs
                )
                if scope_form.is_valid():
                    grant_membership_scope(
                        organization=request.organization,
                        actor=request.user,
                        membership_id=membership.pk,
                        scope_type=scope_form.cleaned_data["scope_type"],
                        project=scope_form.cleaned_data["project"],
                        site=scope_form.cleaned_data["site"],
                        approver_membership_id=scope_form.cleaned_data[
                            "approver_membership"
                        ].pk,
                        reason=scope_form.cleaned_data["reason"],
                        ends_at=scope_form.cleaned_data["ends_at"],
                    )
                    messages.success(request, "دامنه دسترسی ثبت شد.")
                    return redirect(
                        "organizations:member_authorization",
                        membership_id=membership.pk,
                    )
            elif action == "revoke_role":
                revoke_membership_role(
                    organization=request.organization,
                    actor=request.user,
                    assignment_id=request.POST.get("assignment_id"),
                    approver_membership_id=request.POST.get("approver_membership_id"),
                    reason=request.POST.get("reason", ""),
                )
                messages.success(request, "نقش لغو شد.")
                return redirect(
                    "organizations:member_authorization", membership_id=membership.pk
                )
            elif action == "revoke_scope":
                revoke_membership_scope(
                    organization=request.organization,
                    actor=request.user,
                    grant_id=request.POST.get("grant_id"),
                    approver_membership_id=request.POST.get("approver_membership_id"),
                    reason=request.POST.get("reason", ""),
                )
                messages.success(request, "دامنه دسترسی لغو شد.")
                return redirect(
                    "organizations:member_authorization", membership_id=membership.pk
                )
        except (
            PlatformPolicy.DoesNotExist,
            PlatformPolicyVersion.DoesNotExist,
            PolicySource.DoesNotExist,
            PermissionDenied,
            ValidationError,
            ValueError,
            KeyError,
            json.JSONDecodeError,
        ) as exc:
            if action in {"assign_role", "revoke_role"}:
                role_form.add_error(None, str(exc))
            else:
                scope_form.add_error(None, str(exc))
    return render(
        request,
        "organizations/member_authorization.html",
        {
            "membership": membership,
            "role_form": role_form,
            "scope_form": scope_form,
            "role_assignments": MembershipRoleAssignment.objects.filter(
                organization=request.organization,
                membership=membership,
            ).select_related("role", "assigned_by__user", "approved_by__user"),
            "scope_grants": MembershipScopeGrant.objects.filter(
                organization=request.organization,
                membership=membership,
            ).select_related(
                "project", "site", "granted_by__user", "approved_by__user"
            ),
            "approvers": OrganizationMembership.objects.filter(
                organization=request.organization,
                status="active",
                user__is_active=True,
            )
            .exclude(pk__in=(actor_membership.pk, membership.pk))
            .select_related("user"),
        },
    )


def _role_catalog_response(
    request: HttpRequest, *, platform_mode: bool
) -> HttpResponse:
    """Render and mutate the role catalogue through audited services only."""

    if platform_mode:
        if not is_platform_admin(request.user):
            return HttpResponseForbidden("فقط Platform Admin به این بخش دسترسی دارد.")
        catalog_organization = None
        organization_id = request.GET.get("organization") or request.POST.get(
            "catalog_organization"
        )
        if organization_id:
            catalog_organization = Organization.objects.filter(
                pk=organization_id, status="active", archived_at__isnull=True
            ).first()
            if catalog_organization is None:
                return HttpResponseForbidden("Tenant معتبر نیست.")
        roles = OrganizationRole.objects.filter(organization=catalog_organization)
    else:
        catalog_organization = request.organization
        actor_membership = get_active_membership(
            user=request.user, organization=catalog_organization
        )
        if not membership_has_role(actor_membership, MembershipRole.TENANT_ADMIN):
            return HttpResponseForbidden(
                "فقط Tenant Admin می‌تواند نقش‌های این Tenant را مدیریت کند."
            )
        roles = OrganizationRole.objects.filter(organization=catalog_organization)

    selected_role = None
    selected_role_id = request.GET.get("edit") or request.POST.get("role_id")
    if selected_role_id:
        selected_role = roles.filter(pk=selected_role_id).first()
        if selected_role is None:
            return HttpResponseForbidden("نقش در دامنه مجاز شما نیست.")

    form = OrganizationRoleCatalogForm(
        request.POST or None,
        platform_mode=platform_mode,
        organization=catalog_organization,
        role=selected_role,
    )
    if request.method == "POST":
        action = request.POST.get("action", "save")
        try:
            if action == "archive":
                if selected_role is None:
                    raise ValidationError("نقش برای بایگانی انتخاب نشده است.")
                archive_organization_role(
                    actor=request.user,
                    role_id=selected_role.pk,
                    reason=request.POST.get("reason", ""),
                )
                messages.success(request, "نقش سفارشی بایگانی شد.")
            elif form.is_valid():
                data = form.cleaned_data
                if selected_role is None:
                    create_organization_role(
                        actor=request.user,
                        organization=data.get("organization")
                        if platform_mode
                        else catalog_organization,
                        code=data["code"],
                        name=data["name"],
                        description=data["description"],
                        permissions=[item.code for item in data["permissions"]],
                        reason=data["reason"],
                    )
                    messages.success(request, "نقش سفارشی ایجاد شد.")
                else:
                    update_organization_role(
                        actor=request.user,
                        role_id=selected_role.pk,
                        name=data["name"],
                        description=data["description"],
                        permissions=[item.code for item in data["permissions"]],
                        reason=data["reason"],
                    )
                    messages.success(request, "نقش به‌روزرسانی شد.")
            else:
                return render(
                    request,
                    "organizations/role_catalog.html",
                    _role_catalog_context(
                        form, roles, selected_role, platform_mode, catalog_organization
                    ),
                )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect(
                "organizations:platform_role_catalog"
                if platform_mode
                else "organizations:role_catalog"
            )

    return render(
        request,
        "organizations/role_catalog.html",
        _role_catalog_context(
            form, roles, selected_role, platform_mode, catalog_organization
        ),
    )


def _role_catalog_context(
    form: OrganizationRoleCatalogForm,
    roles: object,
    selected_role: OrganizationRole | None,
    platform_mode: bool,
    catalog_organization: Organization | None,
) -> dict[str, object]:
    return {
        "form": form,
        "roles": roles.prefetch_related("permissions").order_by("name"),
        "selected_role": selected_role,
        "platform_mode": platform_mode,
        "catalog_organization": catalog_organization,
        "organizations": Organization.objects.filter(
            status="active", archived_at__isnull=True
        ).order_by("name")
        if platform_mode
        else None,
    }


@login_required
@require_http_methods(["GET", "POST"])
def platform_role_catalog(request: HttpRequest) -> HttpResponse:
    return _role_catalog_response(request, platform_mode=True)


@login_required
@require_http_methods(["GET", "POST"])
def protected_operation_catalog(request: HttpRequest) -> HttpResponse:
    """Manage immutable protected-operation versions under Platform Admin control."""

    if not is_platform_admin(request.user):
        return HttpResponseForbidden("فقط Platform Admin به این بخش دسترسی دارد.")
    form = ProtectedOperationCatalogForm(request.POST or None)
    if request.method == "POST":
        action = request.POST.get("action", "create")
        try:
            if action == "retire":
                retire_protected_operation(
                    actor=request.user,
                    code=request.POST.get("code", ""),
                    reason=request.POST.get("reason", ""),
                )
                messages.success(request, "نسخه فعال عملیات حفاظت‌شده بازنشسته شد.")
            elif form.is_valid():
                create_protected_operation_version(
                    actor=request.user,
                    code=form.cleaned_data["code"],
                    name=form.cleaned_data["name"],
                    description=form.cleaned_data["description"],
                    reason=form.cleaned_data["reason"],
                )
                messages.success(request, "نسخه جدید عملیات حفاظت‌شده ثبت شد.")
            else:
                return render(
                    request,
                    "organizations/protected_operation_catalog.html",
                    {
                        "form": form,
                        "operations": ProtectedOperation.objects.select_related(
                            "created_by", "retired_by"
                        ),
                    },
                )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("organizations:protected_operation_catalog")
    return render(
        request,
        "organizations/protected_operation_catalog.html",
        {
            "form": form,
            "operations": ProtectedOperation.objects.select_related(
                "created_by", "retired_by"
            ),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def platform_policy_catalog(request: HttpRequest) -> HttpResponse:
    """Platform Admin lifecycle UI for closed, versioned policy contracts."""

    if not is_platform_admin(request.user):
        return HttpResponseForbidden("فقط Platform Admin به این بخش دسترسی دارد.")
    if request.method == "POST":
        try:
            action = request.POST.get("action", "create_definition")
            if action == "create_definition":
                create_platform_policy(
                    actor=request.user,
                    code=request.POST.get("code", ""),
                    reason=request.POST.get(
                        "reason", "ثبت تعریف کد-محور سیاست Platform."
                    ),
                )
            elif action in {"create_version", "update_version"}:
                version = (
                    PlatformPolicyVersion.objects.select_related("policy").get(
                        pk=request.POST["policy_version_id"]
                    )
                    if action == "update_version"
                    else None
                )
                policy = (
                    version.policy
                    if version is not None
                    else PlatformPolicy.objects.get(pk=request.POST["policy_id"])
                )
                supersedes_id = request.POST.get("supersedes_id")
                supersedes = (
                    PlatformPolicyVersion.objects.get(pk=supersedes_id)
                    if supersedes_id
                    else None
                )
                kwargs = {
                    "actor": request.user,
                    "parameters": json.loads(request.POST["parameters"]),
                    "effective_from": date.fromisoformat(
                        request.POST["effective_from"]
                    ),
                    "effective_to": (
                        date.fromisoformat(request.POST["effective_to"])
                        if request.POST.get("effective_to")
                        else None
                    ),
                    "source_basis": request.POST["source_basis"],
                    "supersedes": supersedes,
                    "reason": request.POST["reason"],
                }
                if version is None:
                    create_platform_policy_version(
                        policy=policy,
                        version=int(request.POST["version"]),
                        **kwargs,
                    )
                else:
                    update_platform_policy_version(policy_version=version, **kwargs)
            elif action == "record_source":
                record_policy_source(
                    actor=request.user,
                    issuer=request.POST["issuer"],
                    title=request.POST["title"],
                    source_identifier=request.POST["source_identifier"],
                    version=request.POST["source_version"],
                    applicability=request.POST["applicability"],
                    reason=request.POST["reason"],
                    source_location=request.POST.get("source_location", ""),
                )
            elif action == "link_source":
                link_policy_version_source(
                    actor=request.user,
                    policy_version=PlatformPolicyVersion.objects.get(
                        pk=request.POST["policy_version_id"]
                    ),
                    source=PolicySource.objects.get(pk=request.POST["source_id"]),
                    reason=request.POST["reason"],
                )
            elif action == "record_review":
                record_optional_policy_review(
                    actor=request.user,
                    policy_version=PlatformPolicyVersion.objects.get(
                        pk=request.POST["policy_version_id"]
                    ),
                    reviewer_identity=request.POST["reviewer_identity"],
                    qualification_summary=request.POST["qualification_summary"],
                    independence_statement=request.POST["independence_statement"],
                    evidence_reference=request.POST["evidence_reference"],
                    reviewed_on=date.fromisoformat(request.POST["reviewed_on"]),
                    review_scope=request.POST["review_scope"],
                    disposition=request.POST["disposition"],
                    conditions=request.POST.get("conditions", ""),
                )
            elif action == "publish":
                publish_platform_policy_version(
                    actor=request.user,
                    policy_version=PlatformPolicyVersion.objects.get(
                        pk=request.POST["policy_version_id"]
                    ),
                    reason=request.POST["reason"],
                )
            elif action == "retire":
                retire_platform_policy_version(
                    actor=request.user,
                    policy_version=PlatformPolicyVersion.objects.get(
                        pk=request.POST["policy_version_id"]
                    ),
                    reason=request.POST["reason"],
                )
            else:
                raise ValidationError("عملیات سیاست معتبر نیست.")
        except (PermissionDenied, ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "عملیات چرخهٔ سیاست پلتفرم ثبت شد.")
        return redirect("organizations:platform_policy_catalog")

    policies = {
        policy.code: policy
        for policy in PlatformPolicy.objects.filter(code__in=PLATFORM_POLICY_SPECS)
    }
    versions = (
        PlatformPolicyVersion.objects.filter(policy__code__in=PLATFORM_POLICY_SPECS)
        .select_related("policy")
        .prefetch_related("source_links__source", "review_evidence")
    )
    versions_by_code: dict[str, list[PlatformPolicyVersion]] = {
        code: [] for code in PLATFORM_POLICY_SPECS
    }
    for version in versions:
        version.parameters_json = json.dumps(version.parameters, ensure_ascii=False)
        versions_by_code[version.policy.code].append(version)
    return render(
        request,
        "organizations/platform_policy_catalog.html",
        {
            "policy_entries": [
                {
                    "spec": spec,
                    "policy": policies.get(code),
                    "versions": versions_by_code[code],
                }
                for code, spec in PLATFORM_POLICY_SPECS.items()
            ],
            "policy_sources": PolicySource.objects.all(),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.TENANT_POLICIES_VIEW)
@require_http_methods(["GET", "POST"])
def tenant_policy_configuration(request: HttpRequest) -> HttpResponse:
    """Allow only selection/application of ready, published Platform versions."""

    organization = request.organization
    if request.method == "POST":
        try:
            if request.POST.get("action") == "select":
                version = PlatformPolicyVersion.objects.select_related("policy").get(
                    pk=request.POST.get("policy_version_id"),
                    policy__code__in=PLATFORM_POLICY_SPECS,
                )
                select_tenant_policy_version(
                    organization=organization,
                    actor=request.user,
                    policy_version=version,
                    reason=request.POST.get("reason", ""),
                )
                messages.success(request, "نسخه سیاست انتخاب شد؛ برای اعمال آماده است.")
            elif request.POST.get("action") == "apply":
                selection = list_tenant_policy_selections(
                    organization=organization, actor=request.user
                ).get(pk=request.POST.get("selection_id"))
                apply_tenant_policy_selection(
                    organization=organization, actor=request.user, selection=selection
                )
                messages.success(request, "نسخه سیاست اعمال شد.")
            else:
                raise ValidationError("عملیات سیاست معتبر نیست.")
        except (
            PlatformPolicyVersion.DoesNotExist,
            PermissionDenied,
            ValidationError,
        ) as exc:
            messages.error(request, str(exc))
        return redirect("organizations:tenant_policy_configuration")

    selections = list_tenant_policy_selections(
        organization=organization, actor=request.user
    )
    today = timezone.localdate()
    published_versions = PlatformPolicyVersion.objects.filter(
        policy__code__in=PLATFORM_POLICY_SPECS,
        status="published",
        policy__is_active=True,
        policy__tenant_selectable=True,
    ).select_related("policy")
    ready_versions = [
        version
        for version in published_versions
        if (
            version.effective_from <= today
            and (version.effective_to is None or version.effective_to > today)
            and policy_version_is_configuration_ready(version)
        )
    ]
    upcoming_versions = [
        version
        for version in published_versions
        if version.effective_from > today
        and policy_version_is_configuration_ready(version)
    ]
    return render(
        request,
        "organizations/tenant_policy_configuration.html",
        {
            "selections": selections,
            "ready_versions": ready_versions,
            "upcoming_versions": upcoming_versions,
        },
    )


@active_organization_required
@require_http_methods(["GET", "POST"])
def role_catalog(request: HttpRequest) -> HttpResponse:
    return _role_catalog_response(request, platform_mode=False)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTS_RESET_PASSWORD)
@require_http_methods(["GET", "POST"])
def reset_member_password(request: HttpRequest, membership_id: str) -> HttpResponse:
    """Let an authorized tenant owner issue a member's temporary password."""

    try:
        membership = OrganizationMembership.objects.select_related("user").get(
            pk=membership_id,
            organization=request.organization,
        )
    except OrganizationMembership.DoesNotExist as exc:
        raise PermissionDenied("عضویت موردنظر در این شرکت یافت نشد.") from exc

    form = OrganizationMemberPasswordResetForm(
        user=membership.user,
        data=request.POST or None,
    )
    if request.method == "POST" and form.is_valid():
        try:
            reset_organization_member_password(
                organization=request.organization,
                actor=request.user,
                membership=membership,
                temporary_password=form.cleaned_data["new_password1"],
            )
        except PermissionDenied as exc:
            return HttpResponseForbidden(str(exc))
        messages.success(
            request,
            "گذرواژه موقت عضو تنظیم شد؛ او در ورود بعدی باید آن را تغییر دهد.",
        )
        return redirect("organizations:members")
    return render(
        request,
        "organizations/member_password_reset.html",
        {"form": form, "membership": membership},
    )
