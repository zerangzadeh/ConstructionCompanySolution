"""Fail-closed own-data identity and profile services for employee self-service."""

from dataclasses import dataclass
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.authorization import get_active_membership
from apps.organizations.models import Organization
from apps.workforce.models import Person, WorkRelationship

_DENIED = "اطلاعات در این شرکت یافت نشد."


@dataclass(frozen=True)
class ESSSubject:
    person: Person
    current_relationship: WorkRelationship


@dataclass(frozen=True)
class ESSOwnProfile:
    person: Person
    relationship: WorkRelationship
    relationships: tuple[WorkRelationship, ...]
    masked_national_id: str | None


def _mask_identifier(value: str | None) -> str | None:
    """Retain only the final four characters of a sensitive identifier."""

    normalized = (value or "").strip()
    if not normalized:
        return None
    visible = normalized[-4:]
    return f"{'•' * max(len(normalized) - len(visible), 4)}{visible}"


def resolve_ess_subject(*, user: User, organization: Organization) -> ESSSubject:
    """Resolve exactly one active own identity from explicit authoritative links."""

    get_active_membership(user=user, organization=organization)
    people = list(
        Person.objects.filter(organization=organization, user=user).only(
            "id", "organization_id", "user_id", "first_name", "last_name"
        )[:2]
    )
    if len(people) != 1:
        raise PermissionDenied(_DENIED)
    person = people[0]
    today = timezone.localdate(timezone=ZoneInfo(organization.settings.timezone))
    relationships = list(
        WorkRelationship.objects.filter(
            organization=organization,
            person=person,
            effective_start__lte=today,
        )
        .filter(Q(effective_end__isnull=True) | Q(effective_end__gte=today))
        .select_related("person", "legacy_employee")[:2]
    )
    if len(relationships) != 1:
        raise PermissionDenied(_DENIED)
    return ESSSubject(person=person, current_relationship=relationships[0])


def has_ess_subject(*, user: User, organization: Organization) -> bool:
    try:
        resolve_ess_subject(user=user, organization=organization)
    except PermissionDenied:
        return False
    return True


def get_own_profile(
    *,
    user: User,
    organization: Organization,
    relationship_id: str | None = None,
) -> ESSOwnProfile:
    """Return only the actor's relationship and a masked, read-only profile."""

    subject = resolve_ess_subject(user=user, organization=organization)
    today = timezone.localdate(timezone=ZoneInfo(organization.settings.timezone))
    relationships = tuple(
        WorkRelationship.objects.filter(
            organization=organization,
            person=subject.person,
            effective_start__lte=today,
        )
        .select_related("person", "legacy_employee")
        .order_by("-effective_start", "-pk")
    )
    relationship = subject.current_relationship
    if relationship_id is not None:
        relationship = next(
            (
                item
                for item in relationships
                if str(item.pk) == str(relationship_id)
            ),
            None,
        )
        if relationship is None:
            raise PermissionDenied(_DENIED)
    return ESSOwnProfile(
        person=subject.person,
        relationship=relationship,
        relationships=relationships,
        masked_national_id=_mask_identifier(user.national_id),
    )
