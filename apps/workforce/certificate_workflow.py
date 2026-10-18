from apps.organizations.models import OrganizationMembership
from apps.workflows.registry import SubjectSnapshot, registry


def load_certificate(*, organization, subject_id, actor, for_update):
    from .certificate_services import get_request
    from .models import HRCertificateRequest

    visible = get_request(actor=actor, organization=organization, request_id=subject_id)
    query = (
        HRCertificateRequest.objects.select_for_update()
        if for_update
        else HRCertificateRequest.objects
    )
    item = query.get(pk=visible.pk, organization=organization)
    member = OrganizationMembership.objects.get(
        user_id=item.requested_by_id, organization=organization
    )
    return SubjectSnapshot(
        subject=item,
        subject_id=str(item.pk),
        organization_id=str(organization.pk),
        attributes={
            "created_by_id": str(item.requested_by_id),
            "project_id": None,
            "site_id": None,
        },
        creator_membership_id=str(member.pk),
        submitter_membership_id=str(member.pk),
        display="درخواست گواهی منابع انسانی",
    )


def register_certificate_workflow():
    from .certificate_services import (
        accept_review,
        cancel_review_command,
        reject_review,
    )

    registry.bind_subject_loader("workforce.hr_certificate_review", load_certificate)
    for action, executor in (
        ("accept", accept_review),
        ("reject", reject_review),
        ("cancel", cancel_review_command),
    ):
        registry.bind_domain_command(
            "workforce.hr_certificate_review." + action, executor
        )
