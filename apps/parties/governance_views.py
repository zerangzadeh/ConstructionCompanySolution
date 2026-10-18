from contextlib import nullcontext
from dataclasses import dataclass
from functools import wraps
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.cache import patch_vary_headers
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.organizations.authorization import require_business_permission
from apps.organizations.decorators import active_organization_required
from apps.organizations.models import BusinessPermissionCode
from core.list_filters import (
    apply_table_filters,
    paginate_table,
    table_pagination_query,
)

from . import governance_forms as forms
from . import services
from .forms import BusinessPartyForm, PartyContactForm, PartyRoleForm
from .models import BusinessParty, PartyKind
from .presentation import (
    governance_history,
    governance_parties,
    governance_party,
    governance_permissions,
)


def private_party_surface(view=None, *, tenant_time=False):
    def decorate(function):
        @wraps(function)
        def wrapped(request, *args, **kwargs):
            try:
                context = nullcontext()
                if tenant_time:
                    # Match the repository's governed tenant/legacy timezone seam.
                    try:
                        zone = request.organization.settings.timezone
                    except ObjectDoesNotExist:
                        zone = request.organization.timezone
                    context = timezone.override(ZoneInfo(zone))
                with context:
                    response = function(request, *args, **kwargs)
            except PermissionDenied:
                response = render(request, "parties/unavailable.html", status=403)
            except (ObjectDoesNotExist, ZoneInfoNotFoundError):
                response = render(request, "parties/unavailable.html", status=503)
            response["Cache-Control"] = "private, no-store"
            patch_vary_headers(response, ["Cookie"])
            return response

        return wrapped

    return decorate(view) if view else decorate


@dataclass(frozen=True)
class Action:
    title: str
    permission: BusinessPermissionCode
    form_class: type[forms.ScopedSourceForm]
    requires_active: bool = True


ACTIONS = {
    "alias": Action(
        "ثبت نام یا شناسه جایگزین",
        BusinessPermissionCode.PARTY_GOVERNANCE_MANAGE,
        forms.AliasForm,
    ),
    "classification_create": Action(
        "ایجاد واژگان دسته یا برچسب",
        BusinessPermissionCode.PARTY_GOVERNANCE_MANAGE,
        forms.ClassificationForm,
        False,
    ),
    "classification_assign": Action(
        "انتساب دسته یا برچسب",
        BusinessPermissionCode.PARTY_GOVERNANCE_MANAGE,
        forms.ClassificationAssignmentForm,
    ),
    "classification_revoke": Action(
        "لغو انتساب با حفظ سابقه",
        BusinessPermissionCode.PARTY_GOVERNANCE_MANAGE,
        forms.RevokeClassificationForm,
        False,
    ),
    "representative": Action(
        "ثبت مدرک نماینده یا امضادار",
        BusinessPermissionCode.PARTY_GOVERNANCE_MANAGE,
        forms.RepresentativeForm,
    ),
    "representative_revoke": Action(
        "لغو اختیار ثبت‌شده با حفظ سابقه",
        BusinessPermissionCode.PARTY_GOVERNANCE_MANAGE,
        forms.RevokeRepresentativeForm,
        False,
    ),
    "restriction": Action(
        "ثبت محدودیت شرکتی",
        BusinessPermissionCode.PARTY_RESTRICTIONS_MANAGE,
        forms.RestrictionForm,
    ),
    "restriction_revoke": Action(
        "لغو محدودیت شرکتی",
        BusinessPermissionCode.PARTY_RESTRICTIONS_MANAGE,
        forms.RevokeRestrictionForm,
        False,
    ),
    "merge": Action(
        "ثبت ادغام غیرمخرب", BusinessPermissionCode.PARTIES_MERGE, forms.MergeForm
    ),
}


def _render_detail(
    request,
    party,
    *,
    status=200,
    bound_action=None,
    bound_form=None,
    identity_form=None,
):
    codes = governance_permissions(user=request.user, organization=request.organization)
    active = party.archived_at is None and party.merged_into_id is None
    actions = []
    for key, spec in ACTIONS.items():
        if spec.permission not in codes or (spec.requires_active and not active):
            continue
        form = (
            bound_form
            if key == bound_action
            else spec.form_class(
                organization=request.organization, party=party, prefix=key
            )
        )
        actions.append({"key": key, "title": spec.title, "form": form})
    context = {
        "party": party,
        "party_governance_surface": True,
        "party_source_active": active,
        "can_edit": active and BusinessPermissionCode.PARTIES_CHANGE in codes,
        "can_archive": active and BusinessPermissionCode.PARTIES_ARCHIVE in codes,
        "can_assign_role": active
        and BusinessPermissionCode.PARTY_ROLES_ASSIGN in codes,
        "can_add_contact": active
        and BusinessPermissionCode.PARTY_CONTACTS_ADD in codes,
        "can_merge_history": bool(
            codes
            & {
                BusinessPermissionCode.PARTIES_MERGE,
                BusinessPermissionCode.PARTY_GOVERNANCE_MANAGE,
            }
        ),
        "form": identity_form or BusinessPartyForm(instance=party),
        "role_form": PartyRoleForm(),
        "contact_form": PartyContactForm(),
        "actions": actions,
        "roles": party.roles.filter(organization=request.organization, is_active=True),
        "contacts": party.contacts.filter(
            organization=request.organization, archived_at__isnull=True
        ),
        **governance_history(party=party, codes=codes),
    }
    if context["can_merge_history"]:
        context["merged_sources"] = BusinessParty.objects.filter(
            organization=request.organization, merged_into=party
        ).order_by("display_name", "pk")
    return render(request, "parties/governance_detail.html", context, status=status)


@active_organization_required
@private_party_surface(tenant_time=True)
@require_GET
def index(request: HttpRequest) -> HttpResponse:
    query = governance_parties(user=request.user, organization=request.organization)
    query = apply_table_filters(
        query,
        request,
        text_fields={
            "name": ("display_name", "legal_name"),
            "tax_id": ("tax_identifier",),
        },
        choice_fields={"kind": ("party_kind", PartyKind.values)},
    )
    page = paginate_table(
        query,
        request,
        sort_fields={"name": "display_name", "kind": "party_kind"},
        default_ordering=("display_name", "pk"),
    )
    return render(
        request,
        "parties/governance_list.html",
        {
            "parties": page.object_list,
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "party_governance_surface": True,
        },
    )


@active_organization_required
@private_party_surface(tenant_time=True)
@require_http_methods(["GET", "POST"])
def detail(request: HttpRequest, party_id: object) -> HttpResponse:
    # Preserve the existing authorized detail POST through this single source path.
    governance_permissions(user=request.user, organization=request.organization)
    if request.method == "POST":
        require_business_permission(
            user=request.user,
            organization=request.organization,
            permission=BusinessPermissionCode.PARTIES_CHANGE,
            message="اجازه ویرایش طرف تجاری را ندارید.",
        )
    party = governance_party(
        user=request.user, organization=request.organization, party_id=party_id
    )
    if request.method == "GET":
        return _render_detail(request, party)
    form = BusinessPartyForm(request.POST, instance=party)
    if form.is_valid():
        try:
            services.update_business_party(
                actor=request.user,
                organization=request.organization,
                party=party,
                **form.cleaned_data,
            )
        except (ValueError, ValidationError):
            form.add_error(
                None, "ثبت تغییر ممکن نشد؛ ورودی و وضعیت منبع را بررسی کنید."
            )
        else:
            messages.success(request, "نسخه هویت در منبع ثبت شد.")
            return redirect("parties:governance_detail", party_id=party.pk)
    party.refresh_from_db()
    return _render_detail(request, party, identity_form=form, status=400)


def _execute(action, *, actor, organization, party, data):
    # Closed UI wiring only; all business rules/transactions stay in domain services.
    common = {"actor": actor, "organization": organization}
    if action == "alias":
        return services.record_party_alias(**common, party=party, **data)
    if action == "classification_create":
        return services.create_party_classification(**common, **data)
    if action == "classification_assign":
        return services.assign_party_classification(**common, party=party, **data)
    if action == "classification_revoke":
        return services.revoke_party_classification(**common, **data)
    if action == "representative":
        return services.record_party_representative(**common, party=party, **data)
    if action == "representative_revoke":
        return services.revoke_party_representative(**common, **data)
    if action == "restriction":
        return services.create_tenant_party_restriction(**common, party=party, **data)
    if action == "restriction_revoke":
        return services.revoke_tenant_party_restriction(**common, **data)
    if action == "merge":
        data.pop("confirm")
        return services.record_business_party_merge(**common, source=party, **data)
    raise ValidationError("اقدام ثبت‌شده نیست.")


@active_organization_required
@private_party_surface(tenant_time=True)
@require_POST
def action(request: HttpRequest, party_id: object, action: str) -> HttpResponse:
    governance_permissions(user=request.user, organization=request.organization)
    spec = ACTIONS.get(action)
    if spec is None:
        return render(request, "parties/unavailable.html", status=404)
    require_business_permission(
        user=request.user,
        organization=request.organization,
        permission=spec.permission,
        message="اجازه انجام این اقدام را ندارید.",
    )
    party = governance_party(
        user=request.user, organization=request.organization, party_id=party_id
    )
    form = spec.form_class(
        request.POST, organization=request.organization, party=party, prefix=action
    )
    if form.is_valid():
        try:
            _execute(
                action,
                actor=request.user,
                organization=request.organization,
                party=party,
                data=form.cleaned_data.copy(),
            )
        except (ValueError, ValidationError):
            form.add_error(
                None, "ثبت اقدام ممکن نشد؛ ورودی و وضعیت منبع را بررسی کنید."
            )
        else:
            messages.success(request, "اقدام با حفظ سابقه در منبع ثبت شد.")
            return redirect("parties:governance_detail", party_id=party.pk)
    return _render_detail(
        request, party, status=400, bound_action=action, bound_form=form
    )
