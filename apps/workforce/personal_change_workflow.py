"""Bind registered source commands; shared engine retains assignment/state."""

from apps.organizations.models import OrganizationMembership
from apps.workflows.registry import SubjectSnapshot, registry


def load_request(*, organization, subject_id, actor, for_update):
    from .models import PersonalDataRequest
    from .personal_change_services import get_request

    item = get_request(actor=actor, organization=organization, request_id=subject_id)
    query = (
        PersonalDataRequest.objects.select_for_update()
        if for_update
        else PersonalDataRequest.objects
    )
    item = query.get(pk=item.pk, organization=organization)
    member = OrganizationMembership.objects.get(
        user_id=item.requested_by_id, organization=organization
    )
    return SubjectSnapshot(
        subject=item,
        subject_id=str(item.pk),
        organization_id=str(organization.pk),
        attributes={
            "project_id": None,
            "site_id": None,
            "created_by_id": str(item.requested_by_id),
        },
        creator_membership_id=str(member.pk),
        submitter_membership_id=str(member.pk),
        display="درخواست تغییر اطلاعات شخصی",
    )


def register_personal_change():
    from .personal_change_services import (
        accept_change,
        cancel_change_command,
        reject_change,
    )

    registry.bind_subject_loader("workforce.personal_data_change", load_request)
    for action, executor in (
        ("accept", accept_change),
        ("reject", reject_change),
        ("cancel", cancel_change_command),
    ):
        registry.bind_domain_command(
            "workforce.personal_data_change." + action, executor
        )
