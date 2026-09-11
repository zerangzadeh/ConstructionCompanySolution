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
from apps.organizations.decorators import active_organization_required
from apps.organizations.forms import (
    OrganizationForm,
    OrganizationMembershipForm,
    OrganizationSettingsForm,
)
from apps.organizations.invitation_forms import OrganizationInvitationForm
from apps.organizations.models import BusinessPermissionCode, OrganizationMembership
from apps.organizations.services import (
    accept_organization_invitation,
    create_organization_by_system_admin,
    create_organization_invitation,
    get_organization_members,
    get_organization_settings,
    get_valid_memberships,
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
    return render(
        request,
        "organizations/select.html",
        {"memberships": memberships},
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
@require_GET
def organization_members(request: HttpRequest) -> HttpResponse:
    """List active members belonging only to the active organization."""

    can_manage_members = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.MEMBERSHIP_MANAGE,
    )
    memberships = get_organization_members(
        user=request.user,
        organization=request.organization,
        include_inactive=can_manage_members,
    )
    return render(
        request,
        "organizations/members.html",
        {
            "memberships": memberships,
            "can_manage_members": can_manage_members,
        },
    )


@active_organization_required
def organization_settings(request: HttpRequest) -> HttpResponse:
    """View and update settings for the resolved active organization."""

    settings_record = get_organization_settings(organization=request.organization)
    if request.method == "POST":
        form = OrganizationSettingsForm(request.POST, instance=settings_record)
        if form.is_valid():
            try:
                update_organization_settings(
                    organization=request.organization,
                    updated_by=request.user,
                    timezone_name=form.cleaned_data["timezone"],
                    currency=form.cleaned_data["currency"],
                    fiscal_year_start_month=form.cleaned_data[
                        "fiscal_year_start_month"
                    ],
                )
            except PermissionDenied as exc:
                return HttpResponseForbidden(str(exc))
            return redirect("organizations:settings")
    else:
        form = OrganizationSettingsForm(instance=settings_record)

    return render(request, "organizations/settings.html", {"form": form})


@active_organization_required
def invite_member(request: HttpRequest) -> HttpResponse:
    """Create an invitation for an existing user."""

    if not has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.MEMBERSHIP_MANAGE,
    ):
        return HttpResponseForbidden("اجازه دعوت عضو به این شرکت را ندارید.")

    if request.method == "POST":
        form = OrganizationInvitationForm(request.POST)
        if form.is_valid():
            try:
                invitation, raw_token = create_organization_invitation(
                    organization=request.organization,
                    invited_by=request.user,
                    invitee=form.cleaned_data["invitee_username"],
                    role=form.cleaned_data["role"],
                )
            except (PermissionDenied, ValueError) as exc:
                form.add_error(None, str(exc))
            else:
                return render(
                    request,
                    "organizations/invitation_created.html",
                    {
                        "invitation": invitation,
                        "token": raw_token,
                    },
                )
    else:
        form = OrganizationInvitationForm()

    return render(
        request,
        "organizations/invite.html",
        {"form": form},
    )


@active_organization_required
def update_member(request: HttpRequest, membership_id: str) -> HttpResponse:
    """Update a tenant membership through the audited authorization service."""

    if not has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.MEMBERSHIP_MANAGE,
    ):
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
    allow_owner_role = actor_membership.role_definition.is_owner
    if membership.role_definition.is_owner and not allow_owner_role:
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
                messages.success(request, "عضویت کاربر با موفقیت به‌روزرسانی شد.")
                return redirect("organizations:members")
    else:
        form = OrganizationMembershipForm(
            instance=membership,
            allow_owner_role=allow_owner_role,
        )
    return render(
        request,
        "organizations/member_form.html",
        {"form": form, "membership": membership},
    )


@login_required
def accept_invitation(request: HttpRequest) -> HttpResponse:
    """Accept an invitation belonging to the authenticated user."""

    token = request.POST.get("token") or request.GET.get("token", "")
    error = None
    if request.method == "POST":
        try:
            membership = accept_organization_invitation(
                token=token,
                user=request.user,
            )
        except (PermissionDenied, ValueError) as exc:
            error = str(exc)
        else:
            set_active_organization(request.session, membership.organization)
            return redirect("organizations:members")

    return render(
        request,
        "organizations/accept_invitation.html",
        {"token": token, "error": error},
    )
