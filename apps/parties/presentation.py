"""Permission-aware UI projections over the existing Party master source."""

from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch, Q, QuerySet

from apps.accounts.models import User
from apps.organizations.authorization import (
    membership_permission_codes,
    require_business_permission,
)
from apps.organizations.models import BusinessPermissionCode, Organization

from .models import BusinessParty, PartyRestrictionScope, PartyRole
from .services import get_organization_parties

GOVERNANCE_PERMISSIONS = frozenset(
    {
        BusinessPermissionCode.PARTIES_CREATE,
        BusinessPermissionCode.PARTIES_CHANGE,
        BusinessPermissionCode.PARTIES_ARCHIVE,
        BusinessPermissionCode.PARTIES_MERGE,
        BusinessPermissionCode.PARTY_RESTRICTIONS_MANAGE,
        BusinessPermissionCode.PARTY_GOVERNANCE_MANAGE,
        BusinessPermissionCode.PARTY_ROLES_ASSIGN,
        BusinessPermissionCode.PARTY_CONTACTS_ADD,
    }
)
DENIED = "اطلاعات مجاز طرف تجاری در این شرکت در دسترس نیست."


def governance_permissions(*, user: User, organization: Organization) -> frozenset[str]:
    member = require_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.PARTIES_VIEW,
        message=DENIED,
    )
    codes = membership_permission_codes(member)
    if not (codes & GOVERNANCE_PERMISSIONS):
        raise PermissionDenied(DENIED)
    return codes


def operational_parties(
    *, user: User, organization: Organization
) -> QuerySet[BusinessParty]:
    return get_organization_parties(
        user=user, organization=organization
    ).prefetch_related(
        Prefetch(
            "roles",
            queryset=PartyRole.objects.filter(
                organization=organization, is_active=True
            ),
            to_attr="operational_roles",
        )
    )


def governance_parties(
    *, user: User, organization: Organization
) -> QuerySet[BusinessParty]:
    governance_permissions(user=user, organization=organization)
    return (
        BusinessParty.objects.filter(organization=organization)
        .filter(Q(merged_into__isnull=True) | Q(merged_into__organization=organization))
        .select_related("merged_into")
    )


def governance_party(
    *, user: User, organization: Organization, party_id: object
) -> BusinessParty:
    try:
        return governance_parties(user=user, organization=organization).get(pk=party_id)
    except BusinessParty.DoesNotExist as exc:
        raise PermissionDenied(DENIED) from exc


def governance_history(*, party: BusinessParty, codes: frozenset[str]) -> dict:
    context = {}
    if BusinessPermissionCode.PARTY_GOVERNANCE_MANAGE in codes:
        context.update(
            {
                "identity_history": party.identity_snapshots.filter(
                    organization_id=party.organization_id
                ).order_by("sequence"),
                "aliases": party.aliases.filter(
                    organization_id=party.organization_id
                ).order_by("-created_at", "pk"),
                "classifications": party.classification_assignments.filter(
                    organization_id=party.organization_id,
                    classification__organization_id=party.organization_id,
                )
                .select_related("classification")
                .order_by("-assigned_at", "pk"),
                "representatives": party.representatives.filter(
                    organization_id=party.organization_id
                ).order_by("-effective_from", "pk"),
            }
        )
    if BusinessPermissionCode.PARTY_RESTRICTIONS_MANAGE in codes:
        context["restrictions"] = party.restrictions.filter(
            organization_id=party.organization_id, scope=PartyRestrictionScope.TENANT
        ).order_by("-effective_from", "pk")
    return context
