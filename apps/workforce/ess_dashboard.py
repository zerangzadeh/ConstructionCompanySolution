"""Read-only ESS composition over explicit identity and existing source contracts."""

from dataclasses import dataclass
from datetime import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import Organization
from apps.timekeeping.models import (
    AttendanceCorrectionRequest,
    LeaveMissionRequest,
    OvertimeRequest,
)
from apps.workflows.personal_workspaces import RequestWorkspaceRow, build_my_requests

from .ess_services import ESSOwnProfile, get_own_profile


@dataclass(frozen=True)
class ESSDashboard:
    profile: ESSOwnProfile
    requests: tuple[RequestWorkspaceRow, ...]
    requests_state: str
    observed_at: datetime


def build_ess_dashboard(*, user: User, organization: Organization) -> ESSDashboard:
    profile = get_own_profile(user=user, organization=organization)
    rows: tuple[RequestWorkspaceRow, ...] = ()
    state = "unavailable"
    employee_id = profile.relationship.legacy_employee_id
    if employee_id is not None:
        try:
            source_rows = build_my_requests(actor=user, organization=organization)
            # The source read model supports legacy identities too. ESS additionally
            # requires its resolved current Person/WorkRelationship bridge; never
            # expose another legacy employee merely because User happens to match.
            allowed = {}
            for kind, model, field in (
                ("leave", LeaveMissionRequest, "employee_id"),
                ("overtime", OvertimeRequest, "employee_id"),
                ("correction", AttendanceCorrectionRequest, "attendance__employee_id"),
            ):
                allowed[kind] = set(
                    model.objects.filter(
                        organization=organization,
                        requested_by=user,
                        pk__in=[
                            row.source_id
                            for row in source_rows
                            if row.source_type == kind
                        ],
                        **{field: employee_id},
                    ).values_list("pk", flat=True)
                )
            rows = tuple(
                row
                for row in source_rows
                if row.source_id in allowed.get(row.source_type, set())
            )
            state = "ready" if rows else "empty"
        except PermissionDenied:
            state = "unavailable"
        except ValidationError:
            state = "error"
    return ESSDashboard(profile, rows, state, timezone.now())
