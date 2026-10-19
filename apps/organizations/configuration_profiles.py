"""Versioned product suggestions; a profile label never changes tenant policy."""

from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.authorization import (
    membership_has_role,
    require_business_permission,
)
from apps.organizations.models import (
    BusinessPermissionCode,
    MembershipRole,
    Organization,
    PlatformPolicyVersion,
    PolicyVersionStatus,
    TenantPolicySelection,
    TenantPolicySelectionStatus,
)
from apps.organizations.policy_services import (
    apply_tenant_policy_selection,
    select_tenant_policy_version,
)
from apps.organizations.policy_specs import (
    PROJECT_BUDGET_OVERRIDE_POLICY_CODE,
    PROJECT_BUDGET_RESPONSE_POLICY_CODE,
    policy_version_is_configuration_ready,
)

# SPEC-001 matrix, resolved by consolidated Human Decision-01 (2026-10-17).
# The matrix archive hash and decision identity together pin this version.
MATRIX_VERSION = (
    "SPEC-001-cf45d1f6db5821084205e3cdf0553cd68c036855cd4c1d5bbe1ee28c7e6693be"
    "-DECISION-01-20261017"
)


@dataclass(frozen=True)
class ProfileSuggestion:
    key: str
    value: str | bool
    policy_code: str | None
    parameter_name: str | None


_SUGGESTIONS = (
    ProfileSuggestion(
        "project_controls.budget_overrun.response",
        "WARNING",
        PROJECT_BUDGET_RESPONSE_POLICY_CODE,
        "response",
    ),
    ProfileSuggestion(
        "project_controls.budget_overrun.override_enabled",
        False,
        PROJECT_BUDGET_OVERRIDE_POLICY_CODE,
        "override_enabled",
    ),
    ProfileSuggestion("leave.accrual_preset", "POLICY_DEFINED", None, None),
)
PROFILE_NAMES = ("Small", "Standard", "Enterprise")


def preview_configuration_profile(profile: str) -> tuple[ProfileSuggestion, ...]:
    """Return only the approved suggestions, with no tenant mutation or grant."""

    if profile not in PROFILE_NAMES:
        raise ValidationError("پروفایل پیکربندی معتبر نیست.")
    return _SUGGESTIONS


@transaction.atomic
def apply_profile_suggestion(
    *, organization: Organization, actor: User, profile: str, key: str, reason: str
) -> TenantPolicySelection:
    """Apply one key through its owning tenant policy version and audit boundary."""

    suggestions = preview_configuration_profile(profile)
    suggestion = next((item for item in suggestions if item.key == key), None)
    if suggestion is None or not reason.strip():
        raise ValidationError("کلید و دلیل اعمال پیکربندی الزامی و معتبر هستند.")
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TENANT_POLICIES_APPLY,
        message="اختیار اعمال سیاست Tenant را ندارید.",
    )
    if not (
        membership_has_role(membership, MembershipRole.TENANT_ADMIN)
        or membership_has_role(membership, MembershipRole.TENANT_OWNER)
    ):
        raise PermissionDenied("نقش داخلی لازم برای اعمال سیاست را ندارید.")
    if suggestion.policy_code is None:
        # A profile cannot select, create or infer a Workforce Leave Policy.
        # Explicit effective source configuration is still required.
        raise ValidationError("نسخه تأییدشده سیاست مرخصی برای این کلید موجود نیست.")

    Organization.objects.select_for_update().get(pk=organization.pk)
    today = timezone.localdate()
    candidates = PlatformPolicyVersion.objects.filter(
        policy__code=suggestion.policy_code,
        policy__is_active=True,
        policy__tenant_selectable=True,
        status=PolicyVersionStatus.PUBLISHED,
        effective_from__lte=today,
    ).select_related("policy")
    versions = [
        version
        for version in candidates
        if (version.effective_to is None or version.effective_to > today)
        and policy_version_is_configuration_ready(version)
        and version.parameters == {suggestion.parameter_name: suggestion.value}
    ]
    if len(versions) != 1:
        raise ValidationError(
            "نسخه یکتای منتشرشده و معتبر برای این پیشنهاد موجود نیست."
        )

    previous = (
        TenantPolicySelection.objects.select_for_update()
        .filter(
            organization=organization,
            policy=versions[0].policy,
            status=TenantPolicySelectionStatus.ACTIVE,
        )
        .select_related("policy_version")
        .first()
    )
    selection = select_tenant_policy_version(
        organization=organization,
        actor=actor,
        policy_version=versions[0],
        reason=reason,
    )
    return apply_tenant_policy_selection(
        organization=organization,
        actor=actor,
        selection=selection,
        profile_audit={
            "matrix_version": MATRIX_VERSION,
            "profile": profile,
            "key": key,
            "old_value": (
                previous.policy_version.parameters.get(suggestion.parameter_name)
                if previous
                else None
            ),
            "new_value": suggestion.value,
            "reason": reason.strip(),
            "actor_id": str(actor.pk),
            "prior_selection_id": str(previous.pk) if previous else None,
        },
    )
