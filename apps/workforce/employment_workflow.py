from apps.organizations.models import OrganizationMembership
from apps.workflows.registry import SubjectSnapshot, registry


def load_offboarding(*, organization, subject_id, actor, for_update):
    from .employment_services import get_case
    from .models import OffboardingCase

    visible = get_case(actor=actor, organization=organization, case_id=subject_id)
    query = (
        OffboardingCase.objects.select_for_update()
        if for_update
        else OffboardingCase.objects
    )
    case = query.get(pk=visible.pk, organization=organization)
    member = OrganizationMembership.objects.get(
        user_id=case.initiated_by_id, organization=organization
    )
    return SubjectSnapshot(
        subject=case,
        subject_id=str(case.pk),
        organization_id=str(organization.pk),
        attributes={
            "created_by_id": str(case.initiated_by_id),
            "project_id": None,
            "site_id": None,
        },
        creator_membership_id=str(member.pk),
        submitter_membership_id=str(member.pk),
        display="بررسی پایان همکاری",
    )


def register_employment_workflow():
    from .employment_services import complete_clearance

    registry.bind_subject_loader("workforce.offboarding", load_offboarding)
    registry.bind_domain_command("workforce.offboarding.complete", complete_clearance)
