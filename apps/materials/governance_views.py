"""Permission-aware secondary Materials governance workspace."""

from contextlib import nullcontext
from functools import wraps
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import patch_vary_headers
from django.views.decorators.http import require_GET, require_POST

from apps.organizations.authorization import (
    membership_permission_codes,
    require_business_permission,
)
from apps.organizations.decorators import active_organization_required
from apps.organizations.models import BusinessPermissionCode as P

from . import governance_forms as forms
from . import models as m
from . import services

GOVERNANCE_CODES = frozenset(
    {
        P.MATERIALS_STEWARD,
        P.MATERIALS_MERGE,
        P.MATERIAL_ATTRIBUTE_DEFINITIONS_MANAGE,
        P.MATERIAL_ATTRIBUTES_APPLY,
        P.MATERIAL_RELATIONSHIPS_MANAGE,
        P.MATERIAL_TECHNICAL_SUBMIT,
        P.MATERIAL_TECHNICAL_REVIEW,
        P.MATERIAL_TECHNICAL_APPROVE,
        P.UOM_CONVERSIONS_MANAGE,
        P.UOM_ROUNDING_MANAGE,
    }
)
DENIED = "اطلاعات مجاز حاکمیت مصالح در این شرکت در دسترس نیست."


def private_surface(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            try:
                context = timezone.override(ZoneInfo(request.organization.settings.timezone))
            except ObjectDoesNotExist:
                context = nullcontext()
            with context:
                response = view(request, *args, **kwargs)
        except PermissionDenied:
            response = render(request, "materials/unavailable.html", status=403)
        except (ObjectDoesNotExist, ZoneInfoNotFoundError):
            response = render(request, "materials/unavailable.html", status=503)
        response["Cache-Control"] = "private, no-store"
        patch_vary_headers(response, ["Cookie"])
        return response

    return wrapped


def _codes(request):
    member = require_business_permission(
        user=request.user, organization=request.organization, permission=P.MATERIALS_VIEW, message=DENIED
    )
    codes = membership_permission_codes(member)
    if not codes & GOVERNANCE_CODES:
        raise PermissionDenied(DENIED)
    return codes


def _material(request, material_id):
    return m.Material.objects.filter(
        pk=material_id, organization=request.organization, archived_at__isnull=True
    ).select_related("category", "unit_of_measure").get()


def _context(request, codes, material=None, *, bound=None, action=None):
    organization = request.organization
    materials = m.Material.objects.filter(organization=organization, archived_at__isnull=True).select_related("category", "unit_of_measure").order_by("name", "pk")
    context = {
        "materials": materials,
        "units": m.UnitOfMeasure.objects.filter(organization=organization, archived_at__isnull=True).select_related("family").order_by("name", "pk"),
        "families": m.UnitFamily.objects.filter(organization=organization).select_related("base_unit").order_by("name", "pk"),
        "rounding_policies": m.QuantityRoundingPolicyVersion.objects.filter(organization=organization).order_by("code", "-version"),
        "definitions": m.MaterialAttributeDefinition.objects.filter(organization=organization).select_related("category").prefetch_related("versions").order_by("category__name", "code"),
        "selected": material,
        "codes": codes,
        "forms": {},
    }
    if material:
        context.update({
            "aliases": material.aliases.filter(organization=organization).order_by("-created_at"),
            "relationships": material.relationships_from.filter(organization=organization).select_related("candidate").order_by("-created_at"),
            "approvals": material.technical_approvals.filter(organization=organization).select_related("scope_project").order_by("-revision"),
            "values": material.attribute_values.filter(organization=organization).select_related("definition", "definition_version").order_by("-created_at"),
        })
    catalog = {
        "alias": forms.AliasForm,
        "relationship": forms.RelationshipForm,
        "revision": forms.RevisionForm,
        "transition_review": forms.TransitionForm,
        "transition_decide": forms.TransitionForm,
        "attribute_value": forms.AttributeValueForm,
        "family": forms.FamilyForm,
        "family_assignment": forms.FamilyAssignmentForm,
        "conversion": forms.ConversionVersionForm,
        "rounding": forms.RoundingForm,
        "definition": forms.DefinitionForm,
        "definition_version": forms.DefinitionVersionForm,
    }
    for key, cls in catalog.items():
        context["forms"][key] = bound if key == action else cls(organization=organization, material=material, prefix=key)
    return context


@active_organization_required
@private_surface
@require_GET
def index(request):
    codes = _codes(request)
    material = None
    if material_id := request.GET.get("material"):
        material = _material(request, material_id)
    return render(request, "materials/governance.html", _context(request, codes, material))


ACTION_PERMISSION = {
    "alias": P.MATERIALS_STEWARD, "relationship": P.MATERIAL_RELATIONSHIPS_MANAGE,
    "revision": P.MATERIAL_TECHNICAL_SUBMIT, "transition_review": P.MATERIAL_TECHNICAL_REVIEW,
    "transition_decide": P.MATERIAL_TECHNICAL_APPROVE, "attribute_value": P.MATERIAL_ATTRIBUTES_APPLY,
    "family": P.UOM_CONVERSIONS_MANAGE, "family_assignment": P.UOM_CONVERSIONS_MANAGE,
    "conversion": P.UOM_CONVERSIONS_MANAGE, "rounding": P.UOM_ROUNDING_MANAGE,
    "definition": P.MATERIAL_ATTRIBUTE_DEFINITIONS_MANAGE, "definition_version": P.MATERIAL_ATTRIBUTE_DEFINITIONS_MANAGE,
}


@active_organization_required
@private_surface
@require_POST
def action(request, action):
    codes = _codes(request)
    permission = ACTION_PERMISSION.get(action)
    if permission is None:
        return render(request, "materials/unavailable.html", status=404)
    require_business_permission(user=request.user, organization=request.organization, permission=permission, message=DENIED)
    material = _material(request, request.POST.get("material")) if request.POST.get("material") else None
    catalog = _context(request, codes, material)["forms"]
    form = catalog[action].__class__(request.POST, organization=request.organization, material=material, prefix=action)
    if form.is_valid():
        data = form.cleaned_data.copy()
        try:
            if action == "alias": services.record_material_alias(organization=request.organization, actor=request.user, material=material, **data)
            elif action == "relationship": services.record_material_relationship(organization=request.organization, actor=request.user, source=material, **data)
            elif action == "revision": services.create_material_technical_revision(organization=request.organization, actor=request.user, material=material)
            elif action == "transition_review": services.transition_material_technical_revision(organization=request.organization, actor=request.user, approval=data["approval"], target_status=m.MaterialTechnicalApprovalStatus.REVIEW)
            elif action == "transition_decide": services.transition_material_technical_revision(organization=request.organization, actor=request.user, approval=data["approval"], target_status=request.POST.get("target_status"), reason=data["reason"])
            elif action == "attribute_value": services.record_material_attribute_value(organization=request.organization, actor=request.user, material=material, **data)
            elif action == "family": services.configure_unit_family(organization=request.organization, actor=request.user, **data)
            elif action == "family_assignment": services.assign_unit_to_family(organization=request.organization, actor=request.user, **data)
            elif action == "conversion": services.create_unit_conversion_version(organization=request.organization, actor=request.user, **data)
            elif action == "rounding": services.create_quantity_rounding_policy_version(organization=request.organization, actor=request.user, **data)
            elif action == "definition": services.create_material_attribute_definition(organization=request.organization, actor=request.user, **data)
            elif action == "definition_version": services.create_material_attribute_definition_version(organization=request.organization, actor=request.user, **data)
        except (PermissionDenied, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "اقدام در منبع حاکمیتی ثبت شد.")
            target = reverse("materials:governance")
            if material:
                target += f"?material={material.pk}"
            return redirect(target)
    return render(request, "materials/governance.html", _context(request, codes, material, bound=form, action=action), status=400)
