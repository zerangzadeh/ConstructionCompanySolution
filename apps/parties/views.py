from django.core.exceptions import PermissionDenied, ValidationError
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
)
from apps.organizations.models import BusinessPermissionCode
from apps.parties import governance_views
from apps.parties.forms import BusinessPartyForm, PartyContactForm, PartyRoleForm
from apps.parties.governance_views import private_party_surface
from apps.parties.models import BusinessParty, PartyKind
from apps.parties.presentation import operational_parties
from apps.parties.services import (
    add_party_contact,
    archive_business_party,
    assign_party_role,
    create_business_party,
)
from core.list_filters import (
    apply_table_filters,
    build_table_filters,
    has_active_table_filters,
    paginate_table,
    table_pagination_query,
)


def _get_active_party(request: HttpRequest, party_id: str) -> BusinessParty | None:
    return BusinessParty.objects.filter(
        pk=party_id, organization=request.organization, archived_at__isnull=True
    ).first()


@active_organization_required
@private_party_surface
@organization_permission_required(BusinessPermissionCode.PARTIES_VIEW)
def party_list(request: HttpRequest) -> HttpResponse:
    parties = operational_parties(
        user=request.user, organization=request.organization
    )
    parties = apply_table_filters(
        parties,
        request,
        text_fields={"name": ("display_name", "legal_name"), "tax_id": ("tax_identifier",)},
        choice_fields={"kind": ("party_kind", PartyKind.values)},
    )
    page = paginate_table(
        parties,
        request,
        sort_fields={"name": "display_name", "kind": "party_kind", "tax_id": "tax_identifier"},
        default_ordering=("display_name", "pk"),
    )
    return render(
        request,
        "parties/list.html",
        {
            "parties": page.object_list,
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "filters": build_table_filters(
                request,
                [
                    {"name": "name", "kind": "text", "label": "نام نمایشی"},
                    {
                        "name": "kind",
                        "kind": "select",
                        "label": "نوع",
                        "choices": PartyKind.choices,
                    },
                    None,
                    {"name": "tax_id", "kind": "text", "label": "شناسه مالیاتی"},
                    None,
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
        },
    )


@active_organization_required
@private_party_surface
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
        except (ValueError, ValidationError):
            form.add_error(None, "ثبت اطلاعات ممکن نشد؛ ورودی و وضعیت منبع را بررسی کنید.")
        else:
            if has_business_permission(user=request.user, organization=request.organization, permission=BusinessPermissionCode.PARTIES_VIEW):
                return redirect("parties:governance_detail", party_id=party.pk)
            return redirect("parties:create")
    return render(request, "parties/form.html", {"form": form, "party": None, "party_governance_surface": True}, status=400 if form.is_bound else 200)


@active_organization_required
@private_party_surface
@organization_permission_required(BusinessPermissionCode.PARTIES_VIEW)
def party_detail(request: HttpRequest, party_id: str) -> HttpResponse:
    if request.method == "POST":
        return governance_views.detail(request, party_id=party_id)
    party = _get_active_party(request, party_id)
    if party is None:
        return HttpResponseNotFound("طرف تجاری یافت نشد.")
    return render(
        request,
        "parties/detail.html",
        {
            "party": party,
            "roles": party.roles.filter(organization=request.organization, is_active=True),
            "contacts": party.contacts.filter(organization=request.organization, archived_at__isnull=True),
        },
    )


@active_organization_required
@private_party_surface
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
    return redirect("parties:governance")


@active_organization_required
@private_party_surface
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
    return redirect("parties:governance_detail", party_id=party.pk)


@active_organization_required
@private_party_surface
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
    return redirect("parties:governance_detail", party_id=party.pk)
