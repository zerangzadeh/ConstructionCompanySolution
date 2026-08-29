from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.organizations.decorators import active_organization_required
from apps.organizations.forms import OrganizationForm
from apps.organizations.invitation_forms import OrganizationInvitationForm
from apps.organizations.models import MembershipStatus, OrganizationMembership
from apps.organizations.services import (
    accept_organization_invitation,
    create_organization_invitation,
    create_organization_with_owner,
    get_valid_memberships,
    resolve_active_organization,
    set_active_organization,
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
        return HttpResponseForbidden("You do not have access to this organization.")

    set_active_organization(request.session, organization)
    return redirect("organizations:select")


@login_required
def create_organization(request: HttpRequest) -> HttpResponse:
    """Create an organization owned by the authenticated user."""

    if request.method == "POST":
        form = OrganizationForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            organization = create_organization_with_owner(
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

    memberships = (
        OrganizationMembership.objects.filter(
            organization=request.organization,
            status=MembershipStatus.ACTIVE,
        )
        .select_related("user")
        .order_by("user__username")
    )
    return render(
        request,
        "organizations/members.html",
        {"memberships": memberships},
    )


@active_organization_required
def invite_member(request: HttpRequest) -> HttpResponse:
    """Create an invitation for an existing user."""

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
