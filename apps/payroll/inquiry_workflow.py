"""Bind Payroll communication to registered shared Workflow mechanisms."""

from apps.organizations.models import OrganizationMembership
from apps.workflows.registry import SubjectSnapshot, registry


def load_inquiry(*, organization, subject_id, actor, for_update):
    from .ess_services import get_inquiry
    from .models import PayrollInquiry

    visible = get_inquiry(actor=actor, organization=organization, inquiry_id=subject_id)
    query = (
        PayrollInquiry.objects.select_for_update()
        if for_update
        else PayrollInquiry.objects
    )
    inquiry = query.get(pk=visible.pk, organization=organization)
    owner = OrganizationMembership.objects.get(
        user=inquiry.requested_by, organization=organization
    )
    return SubjectSnapshot(
        subject=inquiry,
        subject_id=str(inquiry.pk),
        organization_id=str(organization.pk),
        attributes={
            "project_id": str(inquiry.project.pk) if inquiry.project else None,
            "site_id": str(inquiry.site.pk) if inquiry.site else None,
            "created_by_id": str(inquiry.requested_by_id),
        },
        creator_membership_id=str(owner.pk),
        submitter_membership_id=str(owner.pk),
        display=inquiry.subject,
    )


def register_inquiry_workflow() -> None:
    from .ess_services import append_workflow_response

    registry.bind_subject_loader("payroll.inquiry", load_inquiry)
    registry.bind_domain_command("payroll.inquiry.respond", append_workflow_response)
