"""Explicit leave source history and as-of projection. No inferred policy values.

Approved policy rule references and quantities are required source inputs. This
module does not interpret unregistered formulas, execute tenant code, calculate
statutory rates, convert days to minutes, or infer credits from request history.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization
from apps.timekeeping.models import LeaveMissionRequest, RequestKind, RequestState

from .leave_models import LeaveBalanceEntry, LeavePolicyVersion
from .leave_models import LeaveEntryKind as K
from .models import WorkRelationship


def _access(organization: Organization, actor: User, permission: P) -> Organization:
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        message="Explicit leave authority is required.",
    )
    return organization


def _quantity(value: Decimal) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValidationError("An explicit finite Decimal quantity is required.")
    try:
        rounded = value.quantize(Decimal("0.0001"))
    except InvalidOperation as exc:
        raise ValidationError("Invalid leave quantity.") from exc
    if value != rounded:
        raise ValidationError("Quantity precision exceeds the authoritative unit.")
    return value


def _relationship(organization, relationship):
    try:
        return WorkRelationship.objects.select_for_update().get(
            pk=relationship.pk, organization=organization
        )
    except WorkRelationship.DoesNotExist as exc:
        raise PermissionDenied(
            "Workforce subject is outside the active tenant."
        ) from exc


def _policy(organization, category_code, on, recorded_before=None):
    candidates = LeavePolicyVersion.objects.filter(
        organization=organization,
        category_code=category_code,
        effective_from__lte=on,
        effective_to__gt=on,
    )
    if recorded_before is not None:
        candidates = candidates.filter(created_at__lte=recorded_before)
    policy = candidates.order_by("-version").first()
    if policy is None:
        raise ValidationError("UNSPECIFIED LEAVE POLICY — DO NOT INVENT")
    return policy


@transaction.atomic
def record_policy(
    *,
    organization: Organization,
    actor: User,
    category_code: str,
    effective_from: date,
    effective_to: date,
    unit: str,
    accrual_preset: str,
    entitlement_rule_reference: str,
    accrual_rule_reference: str,
    negative_balance_threshold: Decimal,
    carry_forward_limit: Decimal | None,
    expiry_rule_reference: str,
    evidence_reference: str,
    reason: str,
    supersedes: LeavePolicyVersion | None = None,
) -> LeavePolicyVersion:
    organization = _access(organization, actor, P.LEAVE_POLICIES_MANAGE)
    _quantity(negative_balance_threshold)
    if carry_forward_limit is not None:
        _quantity(carry_forward_limit)
    versions = LeavePolicyVersion.objects.filter(
        organization=organization, category_code=category_code
    )
    previous = None
    if supersedes is not None:
        previous = versions.filter(pk=supersedes.pk).first()
        if previous is None:
            raise PermissionDenied("Policy replacement is outside its source family.")
        if versions.filter(supersedes=previous).exists():
            raise ValidationError("Policy has already been replaced.")
        if (effective_from, effective_to) != (
            previous.effective_from,
            previous.effective_to,
        ):
            raise ValidationError(
                "Correction must retain the original effective interval."
            )
    overlapping = versions.filter(
        effective_from__lt=effective_to, effective_to__gt=effective_from
    )
    if previous:
        # Only the correction chain of this exact interval may overlap.
        overlapping = overlapping.exclude(
            effective_from=previous.effective_from, effective_to=previous.effective_to
        )
    if overlapping.exists():
        raise ValidationError("Independent policy intervals may not overlap.")
    latest = versions.order_by("-version").first()
    version = latest.version + 1 if latest else 1
    if previous and previous.version != version - 1:
        raise ValidationError("Only the latest policy version may be corrected.")
    policy = LeavePolicyVersion.objects.create(
        organization=organization,
        actor=actor,
        category_code=category_code,
        version=version,
        effective_from=effective_from,
        effective_to=effective_to,
        unit=unit,
        accrual_preset=accrual_preset,
        entitlement_rule_reference=entitlement_rule_reference,
        accrual_rule_reference=accrual_rule_reference,
        negative_balance_threshold=negative_balance_threshold,
        carry_forward_limit=carry_forward_limit,
        expiry_rule_reference=expiry_rule_reference,
        evidence_reference=evidence_reference,
        reason=reason,
        supersedes=previous,
    )
    for relationship in WorkRelationship.objects.filter(
        organization=organization, leave_entries__policy__category_code=category_code
    ).distinct():
        _validate_history(organization, relationship, policy)
    return policy


@dataclass(frozen=True)
class LeaveBalance:
    relationship_id: object
    policy_id: object
    unit: str
    as_of: date
    quantity: Decimal
    reserved: Decimal
    available: Decimal
    source_ids: tuple


def _entries(organization, relationship, category_code, recorded_before=None):
    entries = LeaveBalanceEntry.objects.filter(
        organization=organization,
        relationship=relationship,
        policy__category_code=category_code,
    )
    if recorded_before is not None:
        entries = entries.filter(created_at__lte=recorded_before)
    return entries.order_by("effective_on", "created_at", "pk")


@transaction.atomic
def balance_as_of(
    *,
    organization: Organization,
    actor: User,
    relationship: WorkRelationship,
    category_code: str,
    as_of: date,
    recorded_before: datetime | None = None,
) -> LeaveBalance:
    organization = _access(organization, actor, P.LEAVE_BALANCES_VIEW)
    relationship = _relationship(organization, relationship)
    policy = _policy(organization, category_code, as_of, recorded_before)
    entries = list(
        _entries(organization, relationship, category_code, recorded_before).filter(
            effective_on__lte=as_of
        )
    )
    if not entries:
        raise ValidationError(
            "No evidenced source balance exists for this subject/cutoff."
        )
    if any(e.policy.unit != policy.unit for e in entries):
        raise ValidationError("Leave units require an explicitly governed conversion.")
    quantity = sum((e.quantity for e in entries), Decimal(0))
    reserved = sum((e.reserved_quantity for e in entries), Decimal(0))
    if reserved < 0 or quantity - reserved < policy.negative_balance_threshold:
        raise ValidationError("As-of balance breaches its explicit effective policy.")
    return LeaveBalance(
        relationship.pk,
        policy.pk,
        policy.unit,
        as_of,
        quantity,
        reserved,
        quantity - reserved,
        tuple(e.pk for e in entries),
    )


def _append(
    *,
    organization,
    actor,
    relationship,
    policy,
    effective_on,
    kind,
    quantity,
    reserved_quantity,
    source_key,
    evidence_reference,
    reason,
    request=None,
    reverses=None,
):
    _quantity(quantity)
    _quantity(reserved_quantity)
    data = {
        "organization": organization,
        "actor": actor,
        "relationship": relationship,
        "policy": policy,
        "effective_on": effective_on,
        "kind": kind,
        "quantity": quantity,
        "reserved_quantity": reserved_quantity,
        "source_key": source_key,
        "evidence_reference": evidence_reference,
        "reason": reason,
        "request": request,
        "reverses": reverses,
        "request_snapshot": _request_snapshot(request) if request else {},
    }
    existing = LeaveBalanceEntry.objects.filter(
        organization=organization, source_key=source_key
    ).first()
    if existing:
        if any(getattr(existing, k) != v for k, v in data.items()):
            raise ValidationError(
                "Idempotency key was used with different source facts."
            )
        return existing
    if effective_on < relationship.effective_start or (
        relationship.effective_end is not None
        and effective_on > relationship.effective_end
    ):
        raise ValidationError(
            "Leave source falls outside its evidenced employment episode."
        )
    entry = LeaveBalanceEntry.objects.create(**data)
    _validate_history(organization, relationship, policy)
    return entry


def _validate_history(organization, relationship, policy):
    total = reserved = Decimal(0)
    # Recheck every chronological prefix, including future reservations, so a
    # backdated correction cannot silently invalidate a later accepted balance.
    for row in _entries(
        organization, relationship, policy.category_code
    ).select_related("policy"):
        if row.policy.unit != policy.unit:
            raise ValidationError("Leave unit conversion has no governed contract.")
        total += row.quantity
        reserved += row.reserved_quantity
        floor = _policy(
            organization, policy.category_code, row.effective_on
        ).negative_balance_threshold
        if reserved < 0 or total - reserved < floor:
            raise ValidationError(
                "Leave source would breach explicit balance/reservation policy."
            )
    for start in (
        LeavePolicyVersion.objects.filter(
            organization=organization, category_code=policy.category_code
        )
        .values_list("effective_from", flat=True)
        .distinct()
    ):
        prior = list(
            _entries(organization, relationship, policy.category_code).filter(
                effective_on__lte=start
            )
        )
        if prior:
            available = sum(
                (e.quantity - e.reserved_quantity for e in prior), Decimal(0)
            )
            if (
                available
                < _policy(
                    organization, policy.category_code, start
                ).negative_balance_threshold
            ):
                raise ValidationError(
                    "Policy interval would invalidate an existing source balance."
                )


@transaction.atomic
def record_credit(
    *,
    organization: Organization,
    actor: User,
    relationship: WorkRelationship,
    category_code: str,
    effective_on: date,
    kind: str,
    quantity: Decimal,
    rule_reference: str,
    source_key: str,
    evidence_reference: str,
    reason: str,
) -> LeaveBalanceEntry:
    """Record an explicitly evidenced rule outcome, never calculate an absent rate.

    Opening-balance production is deliberately unavailable here (CEP-057).
    Repeated periodic inputs require their own stable source evidence/key.
    """
    organization = _access(organization, actor, P.LEAVE_BALANCES_MANAGE)
    relationship = _relationship(organization, relationship)
    policy = _policy(organization, category_code, effective_on)
    _quantity(quantity)
    if kind not in {K.ENTITLEMENT, K.ACCRUAL, K.CARRY_FORWARD, K.EXPIRY, K.ADJUSTMENT}:
        raise ValidationError(
            "Unsupported leave source; opening import belongs to CEP-057."
        )
    expected_rule = policy.entitlement_rule_reference
    if kind == K.ACCRUAL:
        if policy.accrual_preset != "POLICY_DEFINED":
            raise ValidationError(
                "This explicit preset does not permit periodic accrual."
            )
        expected_rule = policy.accrual_rule_reference
    if kind == K.CARRY_FORWARD and (
        policy.carry_forward_limit is None or quantity > policy.carry_forward_limit
    ):
        raise ValidationError(
            "Carry forward requires an explicit limit and eligible source evidence."
        )
    if kind == K.EXPIRY:
        expected_rule = policy.expiry_rule_reference
    if not expected_rule.strip() or rule_reference != expected_rule:
        raise ValidationError("The approved effective rule reference is required.")
    if (kind in {K.ENTITLEMENT, K.ACCRUAL, K.CARRY_FORWARD} and quantity <= 0) or (
        kind == K.EXPIRY and quantity >= 0
    ):
        raise ValidationError("Leave credit/expiry direction is invalid.")
    return _append(
        organization=organization,
        actor=actor,
        relationship=relationship,
        policy=policy,
        effective_on=effective_on,
        kind=kind,
        quantity=quantity,
        reserved_quantity=Decimal(0),
        source_key=source_key,
        evidence_reference=evidence_reference,
        reason=reason,
    )


@transaction.atomic
def reverse_credit(
    *,
    organization: Organization,
    actor: User,
    source: LeaveBalanceEntry,
    effective_on: date,
    source_key: str,
    evidence_reference: str,
    reason: str,
) -> LeaveBalanceEntry:
    organization = _access(organization, actor, P.LEAVE_BALANCES_MANAGE)
    try:
        source = LeaveBalanceEntry.objects.select_for_update().get(
            pk=source.pk, organization=organization
        )
    except LeaveBalanceEntry.DoesNotExist as exc:
        raise PermissionDenied("Leave source is outside the active tenant.") from exc
    if (
        source.kind
        not in {K.ENTITLEMENT, K.ACCRUAL, K.CARRY_FORWARD, K.EXPIRY, K.ADJUSTMENT}
        or effective_on < source.effective_on
    ):
        raise ValidationError(
            "Only original source credits may be corrected, at/after source date."
        )
    relationship = _relationship(organization, source.relationship)
    return _append(
        organization=organization,
        actor=actor,
        relationship=relationship,
        policy=source.policy,
        effective_on=effective_on,
        kind=K.REVERSAL,
        quantity=-source.quantity,
        reserved_quantity=Decimal(0),
        source_key=source_key,
        evidence_reference=evidence_reference,
        reason=reason,
        reverses=source,
    )


def _request(organization, actor, request, permission):
    try:
        request = LeaveMissionRequest.objects.select_for_update().get(
            pk=request.pk, organization=organization
        )
    except LeaveMissionRequest.DoesNotExist as exc:
        raise PermissionDenied("Leave request is outside the active tenant.") from exc
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        project=request.project,
        site=request.site,
        message="Leave request permission/object scope is required.",
    )
    if request.kind != RequestKind.LEAVE:
        raise ValidationError(
            "Only a native leave request may use the leave authority."
        )
    return request


def _local_date(organization, moment):
    return moment.astimezone(ZoneInfo(organization.settings.timezone)).date()


def _request_snapshot(request):
    return {
        "employee_id": str(request.employee_id),
        "category_code": request.category_code,
        "kind": request.kind,
        "starts_at": request.starts_at.isoformat(),
        "ends_at": request.ends_at.isoformat(),
        "project_id": str(request.project_id) if request.project_id else None,
        "site_id": str(request.site_id) if request.site_id else None,
        "policy_reference": request.policy_reference,
    }


@transaction.atomic
def reserve_request(
    *,
    organization: Organization,
    actor: User,
    relationship: WorkRelationship,
    request: LeaveMissionRequest,
    quantity: Decimal,
    effective_on: date,
    source_key: str,
    evidence_reference: str,
    reason: str,
    own_subject: bool = False,
) -> LeaveBalanceEntry:
    organization = _access(
        organization,
        actor,
        P.LEAVE_MISSION_REQUEST if own_subject else P.LEAVE_BALANCES_MANAGE,
    )
    if own_subject:
        from .ess_services import resolve_ess_subject

        subject = resolve_ess_subject(user=actor, organization=organization)
        if subject.current_relationship.pk != relationship.pk:
            raise PermissionDenied(
                "Leave reservation requires the actor's explicit own subject."
            )
    relationship = _relationship(organization, relationship)
    request = _request(organization, actor, request, P.LEAVE_MISSION_REQUEST)
    if request.state != RequestState.DRAFT or request.requested_by_id != actor.pk:
        raise PermissionDenied("Only the author may reserve a draft leave request.")
    _quantity(quantity)
    if quantity <= 0 or effective_on > _local_date(organization, request.starts_at):
        raise ValidationError("Reservation quantity/date is invalid.")
    _validate_request_episode(organization, relationship, request)
    policy = _policy(organization, request.category_code, effective_on)
    end_policy = _policy(
        organization, request.category_code, _local_date(organization, request.ends_at)
    )
    if policy.pk != end_policy.pk:
        raise ValidationError(
            "Cross-policy requests require explicit separate source allocation."
        )
    if (
        not _entries(organization, relationship, request.category_code)
        .filter(effective_on__lte=effective_on)
        .exists()
    ):
        raise ValidationError(
            "An evidenced initial entitlement/opening source is required."
        )
    return _append(
        organization=organization,
        actor=actor,
        relationship=relationship,
        policy=policy,
        effective_on=effective_on,
        kind=K.RESERVATION,
        quantity=Decimal(0),
        reserved_quantity=quantity,
        source_key=source_key,
        evidence_reference=evidence_reference,
        reason=reason,
        request=request,
    )


def _require_reservation(*, organization, request):
    """Internal guard, called only after native service authorization/locking."""
    reserve = (
        LeaveBalanceEntry.objects.filter(
            organization=organization,
            request=request,
            kind=K.RESERVATION,
        )
        .select_related("policy", "relationship")
        .first()
    )
    if (
        reserve is None
        or LeaveBalanceEntry.objects.filter(request=request, kind=K.RELEASE).exists()
    ):
        raise ValidationError("An active authoritative leave reservation is required.")
    current = _policy(organization, request.category_code, reserve.effective_on)
    if reserve.request_snapshot != _request_snapshot(request):
        raise ValidationError("Request facts changed after authoritative allocation.")
    _validate_request_episode(organization, reserve.relationship, request)
    if current.pk != reserve.policy_id:
        raise ValidationError(
            "Policy changed; the source allocation requires governed review."
        )
    return reserve


def _validate_request_episode(organization, relationship, request):
    start = _local_date(organization, request.starts_at)
    end = _local_date(organization, request.ends_at)
    if relationship.legacy_employee_id != request.employee_id or (
        start < relationship.effective_start
        or (relationship.effective_end is not None and end > relationship.effective_end)
    ):
        raise ValidationError(
            "Request must retain its explicit employed identity/episode."
        )


def _release(
    organization, actor, request, reserve, effective_on, evidence_reference, reason
):
    return _append(
        organization=organization,
        actor=actor,
        relationship=reserve.relationship,
        policy=reserve.policy,
        effective_on=effective_on,
        kind=K.RELEASE,
        quantity=Decimal(0),
        reserved_quantity=-reserve.reserved_quantity,
        source_key=f"request:{request.pk}:release",
        evidence_reference=evidence_reference,
        reason=reason,
        request=request,
        reverses=reserve,
    )


def _release_rejected_request(*, organization, actor, request, reason):
    """Internal native review seam; transaction/authorization owned by caller."""
    reserve = LeaveBalanceEntry.objects.filter(
        organization=organization, request=request, kind=K.RESERVATION
    ).first()
    if reserve is not None:
        _release(
            organization,
            actor,
            request,
            reserve,
            reserve.effective_on,
            f"native-rejection:{request.pk}",
            reason,
        )


@transaction.atomic
def consume_approved_occurrence(
    *,
    organization: Organization,
    actor: User,
    request: LeaveMissionRequest,
    occurred_on: date,
    evidence_reference: str,
    reason: str,
) -> LeaveBalanceEntry:
    organization = _access(organization, actor, P.LEAVE_BALANCES_MANAGE)
    request = _request(organization, actor, request, P.LEAVE_MISSION_REVIEW)
    if request.state != RequestState.APPROVED:
        raise ValidationError("Consumption requires an approved leave occurrence.")
    if request.requested_by_id == actor.pk:
        raise PermissionDenied("Self consumption approval is forbidden.")
    if request.ends_at > timezone.now() or occurred_on != _local_date(
        organization, request.ends_at
    ):
        raise ValidationError(
            "Occurrence evidence must match completed approved leave."
        )
    existing = LeaveBalanceEntry.objects.filter(
        organization=organization, request=request, kind=K.CONSUMPTION
    ).first()
    if existing:
        if (
            existing.evidence_reference != evidence_reference
            or existing.reason != reason
        ):
            raise ValidationError("Occurrence retry changed its evidence.")
        return existing
    reserve = _require_reservation(organization=organization, request=request)
    _release(
        organization, actor, request, reserve, occurred_on, evidence_reference, reason
    )
    return _append(
        organization=organization,
        actor=actor,
        relationship=reserve.relationship,
        policy=reserve.policy,
        effective_on=occurred_on,
        kind=K.CONSUMPTION,
        quantity=-reserve.reserved_quantity,
        reserved_quantity=Decimal(0),
        source_key=f"request:{request.pk}:consumption",
        evidence_reference=evidence_reference,
        reason=reason,
        request=request,
    )


@transaction.atomic
def cancel_request(
    *,
    organization: Organization,
    actor: User,
    request: LeaveMissionRequest,
    effective_on: date,
    evidence_reference: str,
    reason: str,
) -> LeaveBalanceEntry:
    organization = _access(organization, actor, P.LEAVE_BALANCES_MANAGE)
    request = _request(organization, actor, request, P.LEAVE_MISSION_REVIEW)
    if actor.pk == request.requested_by_id:
        raise PermissionDenied(
            "Cancellation requires an independent authorized reviewer."
        )
    source = LeaveBalanceEntry.objects.filter(
        organization=organization, request=request, kind=K.CONSUMPTION
    ).first()
    if source:
        kind = K.REINSTATEMENT
    else:
        source = LeaveBalanceEntry.objects.filter(
            organization=organization, request=request, kind=K.RESERVATION
        ).first()
        kind = K.RELEASE
    if source is None or effective_on < source.effective_on:
        raise ValidationError("Cancellation requires dated source allocation evidence.")
    if request.state not in {
        RequestState.SUBMITTED,
        RequestState.APPROVED,
        RequestState.CANCELLED,
    }:
        raise ValidationError("Request is not eligible for cancellation.")
    result = _append(
        organization=organization,
        actor=actor,
        relationship=source.relationship,
        policy=source.policy,
        effective_on=effective_on,
        kind=kind,
        quantity=-source.quantity,
        reserved_quantity=-source.reserved_quantity,
        source_key=f"request:{request.pk}:cancellation",
        evidence_reference=evidence_reference,
        reason=reason,
        request=request,
        reverses=source,
    )
    LeaveMissionRequest.objects.filter(pk=request.pk).update(
        state=RequestState.CANCELLED
    )
    return result
