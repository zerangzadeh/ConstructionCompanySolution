from django.core.exceptions import PermissionDenied
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotFound,
)
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.organizations.authorization import has_business_permission
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
    require_organization_permission,
)
from apps.organizations.models import BusinessPermissionCode
from apps.parties.forms import BusinessPartyForm, PartyContactForm, PartyRoleForm
from apps.parties.models import BusinessParty
from apps.parties.services import (
    add_party_contact,
    archive_business_party,
    assign_party_role,
    create_business_party,
    get_organization_parties,
    update_business_party,
)


def _get_active_party(request: HttpRequest, party_id: str) -> BusinessParty | None:
    return BusinessParty.objects.filter(
        pk=party_id, organization=request.organization, archived_at__isnull=True
    ).first()


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PARTIES_VIEW)
def party_list(request: HttpRequest) -> HttpResponse:
    parties = get_organization_parties(
        user=request.user, organization=request.organization
    )
    return render(request, "parties/list.html", {"parties": parties})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PARTIES_CREATE)
def party_create(request: HttpRequest) -> HttpResponse:
    form = BusinessPartyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            party = create_business_party(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("parties:detail", party_id=party.pk)
    return render(request, "parties/form.html", {"form": form, "party": None})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PARTIES_VIEW)
def party_detail(request: HttpRequest, party_id: str) -> HttpResponse:
    if request.method == "POST":
        require_organization_permission(
            request,
            BusinessPermissionCode.PARTIES_CHANGE,
            "اجازه ویرایش طرف تجاری را ندارید.",
        )
    party = _get_active_party(request, party_id)
    if party is None:
        return HttpResponseNotFound("طرف تجاری یافت نشد.")
    form = BusinessPartyForm(request.POST or None, instance=party)
    if request.method == "GET" and not has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.PARTIES_CHANGE,
    ):
        for field in form.fields.values():
            field.disabled = True
    if request.method == "POST" and form.is_valid():
        try:
            party = update_business_party(
                organization=request.organization,
                actor=request.user,
                party=party,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("parties:detail", party_id=party.pk)
    return render(
        request,
        "parties/detail.html",
        {
            "party": party,
            "form": form,
            "role_form": PartyRoleForm(),
            "contact_form": PartyContactForm(),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PARTIES_ARCHIVE)
@require_POST
def party_archive(request: HttpRequest, party_id: str) -> HttpResponse:
    party = _get_active_party(request, party_id)
    if party is None:
        return HttpResponseNotFound("طرف تجاری یافت نشد.")
    try:
        archive_business_party(
            organization=request.organization, actor=request.user, party=party
        )
    except PermissionDenied as exc:
        return HttpResponseForbidden(str(exc))
    return redirect("parties:list")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PARTY_ROLES_ASSIGN)
@require_POST
def party_role_create(request: HttpRequest, party_id: str) -> HttpResponse:
    party = _get_active_party(request, party_id)
    if party is None:
        return HttpResponseNotFound("طرف تجاری یافت نشد.")
    form = PartyRoleForm(request.POST)
    if not form.is_valid():
        return HttpResponseForbidden("نقش طرف تجاری معتبر نیست.")
    try:
        assign_party_role(
            organization=request.organization,
            actor=request.user,
            party=party,
            **form.cleaned_data,
        )
    except (PermissionDenied, ValueError) as exc:
        return HttpResponseForbidden(str(exc))
    return redirect("parties:detail", party_id=party.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PARTY_CONTACTS_ADD)
@require_POST
def party_contact_create(request: HttpRequest, party_id: str) -> HttpResponse:
    party = _get_active_party(request, party_id)
    if party is None:
        return HttpResponseNotFound("طرف تجاری یافت نشد.")
    form = PartyContactForm(request.POST)
    if not form.is_valid():
        return HttpResponseForbidden("اطلاعات تماس طرف تجاری معتبر نیست.")
    try:
        add_party_contact(
            organization=request.organization,
            actor=request.user,
            party=party,
            **form.cleaned_data,
        )
    except (PermissionDenied, ValueError) as exc:
        return HttpResponseForbidden(str(exc))
    return redirect("parties:detail", party_id=party.pk)
