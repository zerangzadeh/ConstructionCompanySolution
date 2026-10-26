from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
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
    organization = request.organization
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


@active_organization_required
@organization_permission_required(BusinessPermissionCode.PARTNER_VIEW)
@require_GET
def record_detail(request: HttpRequest, kind: str, record_id: str) -> HttpResponse:
    if kind == "qualification":
        record = get_object_or_404(
            PartnerQualification.objects.filter(
                organization=request.organization,
                profile__organization=request.organization,
                requirement__organization=request.organization,
            ).select_related("profile__party", "requirement"),
            pk=record_id,
        )
        title = record.reference_number
        rows = [
            ("همکار", record.profile.party, "text"),
            ("الزام", record.requirement.title, "text"),
            ("وضعیت", record.get_status_display(), "text"),
            ("شروع اعتبار", record.valid_from, "date"),
            ("پایان اعتبار", record.valid_until, "date"),
            ("دلیل", record.reason, "text"),
        ]
        sections = []
    elif kind == "evaluation":
        record = get_object_or_404(
            scoped_evaluations(organization=request.organization, actor=request.user)
            .filter(profile__organization=request.organization)
            .select_related("profile__party", "project", "site"),
            pk=record_id,
        )
        title = "ارزیابی عملکرد همکار"
        rows = [
            ("همکار", record.profile.party, "text"),
            ("پروژه", record.project, "text"),
            ("کارگاه", record.site, "text"),
            ("شروع دوره", record.period_start, "date"),
            ("پایان دوره", record.period_end, "date"),
            ("امتیاز ثبت‌شده", record.total_score, "number"),
            ("وضعیت", record.get_status_display(), "text"),
        ]
        sections = []
    else:
        raise Http404
    return render(
        request,
        "components/read_only_record_detail.html",
        {
            "detail_title": title,
            "back_url": reverse("partner_qualification:workbench"),
            "detail_rows": rows,
            "detail_sections": sections,
        },
    )
