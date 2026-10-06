from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode
from apps.partner_qualification.models import (
    PartnerCategoryApproval,
    PartnerProfile,
    PartnerQualification,
    QualificationRequirement,
)
from apps.partner_qualification.services import scoped_evaluations


@require_GET
@active_organization_required
@organization_permission_required(BusinessPermissionCode.PARTNER_VIEW)
def workbench(request):
    organization = request.active_organization
    return render(
        request,
        "partner_qualification/workbench.html",
        {
            "profiles": PartnerProfile.objects.filter(
                organization=organization
            ).select_related("party")[:50],
            "requirements": QualificationRequirement.objects.filter(
                organization=organization
            ).order_by("code", "-version")[:50],
            "qualifications": PartnerQualification.objects.filter(
                organization=organization
            ).select_related("profile__party", "requirement")[:50],
            "evaluations": scoped_evaluations(
                organization=organization, actor=request.user
            )[:50],
            "category_approvals": PartnerCategoryApproval.objects.filter(
                organization=organization
            ).select_related("profile__party")[:50],
        },
    )
