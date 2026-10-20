"""Code-owned SPEC018 framework. Empty policy registry holds monetary activation.

Bindings must validate approved eligibility, immutable MissionVersion/effect IDs,
classification, amount/currency, dates, target configuration and correction policy.
They read source evidence only. No tenant-authored callback or default policy exists.
"""

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction

from apps.accounts.models import User
from apps.expenses.models import ExpenseCategory
from apps.expenses.services import create_expense_draft, void_expense
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization, OrganizationSettings
from apps.payroll.models import (
    PayrollAdjustment,
    PayrollComponent,
    PayrollRun,
    PayrollRunEmployee,
)
from apps.payroll.services import record_adjustment
from apps.treasury.models import TreasuryAdvance, TreasuryMovement
from apps.treasury.services import cancel_payment_request, create_payment_request

from .mission_models import MissionEffect, MissionEffectEvent
from .models import LeaveMissionRequest


class RoutingRejected(ValidationError):
    def __init__(self, code: str):
        super().__init__(code, code=code)


@dataclass(frozen=True)
class PayrollTarget:
    run: PayrollRun
    component: PayrollComponent
    kind: str
    effective_on: date
    original_result: PayrollRunEmployee | None = None


@dataclass(frozen=True)
class ExpenseTarget:
    category: str
    incurred_on: date
    description: str
    expense_category: ExpenseCategory | None = None


@dataclass(frozen=True)
class TreasuryTarget:
    purpose: str


@dataclass(frozen=True)
class EffectSpec:
    effect_id: UUID
    effect_type: str
    route: str
    amount: Decimal
    currency: str
    target: PayrollTarget | ExpenseTarget | TreasuryTarget


@dataclass(frozen=True)
class MissionPlan:
    # Opaque approved producer version, never updated_at or a caller's counter.
    mission_version: str
    approval_reference: str
    effects: tuple[EffectSpec, ...]


@dataclass(frozen=True)
class MissionPolicyBinding:
    read_plan: Callable[..., MissionPlan]
    read_payroll_correction: Callable[..., PayrollTarget | PayrollAdjustment] | None = (
        None
    )


# (Organization UUID, exact policy reference). Free text is not policy approval.
POLICIES: Mapping[tuple[str, str], MissionPolicyBinding] = MappingProxyType({})


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def effect_identity(
    organization_id, mission_id, mission_version, effect_id, effect_type
) -> str:
    return digest(
        [
            str(organization_id),
            str(mission_id),
            mission_version,
            str(effect_id),
            effect_type,
        ]
    )


def _require(
    organization: Organization,
    actor: User,
    mission: LeaveMissionRequest,
    permission: str,
) -> None:
    require_business_permission(
        user=actor,
        organization=organization,
        project=mission.project,
        site=mission.site,
        permission=permission,
        message="Native Mission authority required.",
    )
    if mission.organization_id != organization.pk or mission.kind != "mission":
        raise PermissionDenied("Mission is outside the active source scope.")


def _load(
    organization: Organization, actor: User, mission_id: UUID, permission: str
) -> LeaveMissionRequest:
    Organization.objects.select_for_update().get(pk=organization.pk)
    mission = (
        LeaveMissionRequest.objects.select_for_update()
        .filter(pk=mission_id, organization=organization)
        .first()
    )
    if mission is None:
        raise PermissionDenied("Mission is outside the active tenant.")
    _require(organization, actor, mission, permission)
    return mission


def _mission_snapshot(mission: LeaveMissionRequest) -> dict:
    return {
        key: str(getattr(mission, key))
        for key in (
            "pk",
            "organization_id",
            "employee_id",
            "project_id",
            "site_id",
            "kind",
            "category_code",
            "starts_at",
            "ends_at",
            "reason",
            "policy_reference",
            "state",
            "requested_by_id",
            "reviewed_by_id",
            "reviewed_at",
            "review_reason",
        )
    }


def _read_plan(
    organization: Organization, actor: User, mission: LeaveMissionRequest
) -> tuple[MissionPolicyBinding, MissionPlan]:
    if (
        mission.state != "approved"
        or not mission.reviewed_by_id
        or mission.reviewed_by_id == mission.requested_by_id
        or mission.reviewed_at is None
        or not mission.review_reason.strip()
    ):
        raise RoutingRejected("APPROVED_INDEPENDENT_MISSION_REQUIRED")
    binding = POLICIES.get((str(organization.pk), mission.policy_reference))
    if binding is None:
        raise RoutingRejected("APPROVED_MISSION_POLICY_REQUIRED")
    plan = binding.read_plan(organization=organization, actor=actor, mission=mission)
    if (
        not isinstance(plan, MissionPlan)
        or not plan.mission_version.strip()
        or len(plan.mission_version) > 100
        or not plan.approval_reference.strip()
    ):
        raise RoutingRejected("APPROVED_MISSION_VERSION_AND_POLICY_EVIDENCE_REQUIRED")
    seen = set()
    currency = OrganizationSettings.objects.get(organization=organization).currency
    for spec in plan.effects:
        if not isinstance(spec, EffectSpec):
            raise RoutingRejected("TYPED_APPROVED_EFFECT_REQUIRED")
        key = (spec.effect_id, spec.effect_type)
        if (
            not isinstance(spec, EffectSpec)
            or not isinstance(spec.effect_id, UUID)
            or not spec.effect_type.strip()
            or key in seen
            or not isinstance(spec.amount, Decimal)
            or not spec.amount.is_finite()
            or spec.amount <= 0
            or spec.currency != currency
        ):
            raise RoutingRejected("INVALID_OR_DUPLICATE_APPROVED_EFFECT")
        seen.add(key)
        target_type = {
            "payroll": PayrollTarget,
            "expense": ExpenseTarget,
            "treasury": TreasuryTarget,
        }.get(spec.route)
        if target_type is None or not isinstance(spec.target, target_type):
            raise RoutingRejected("ONE_APPROVED_TYPED_ROUTE_REQUIRED")
    return binding, plan


def _snapshot(
    mission: LeaveMissionRequest, plan: MissionPlan, spec: EffectSpec
) -> dict:
    target = {
        field.name: str(
            getattr(spec.target, field.name).pk
            if isinstance(getattr(spec.target, field.name), models.Model)
            else getattr(spec.target, field.name)
        )
        for field in fields(spec.target)
    }
    return {
        "mission": _mission_snapshot(mission),
        "mission_version": plan.mission_version,
        "policy_approval": plan.approval_reference,
        "effect_id": str(spec.effect_id),
        "effect_type": spec.effect_type,
        "route": spec.route,
        "amount": str(spec.amount),
        "currency": spec.currency,
        "target_contract": target,
    }


def _spec(plan: MissionPlan, effect_id: UUID, effect_type: str) -> EffectSpec:
    matches = [
        x
        for x in plan.effects
        if x.effect_id == effect_id and x.effect_type == effect_type
    ]
    if len(matches) != 1:
        raise RoutingRejected("EXACT_APPROVED_EFFECT_REQUIRED")
    return matches[0]


def _native_permission(
    effect: MissionEffect, organization: Organization, actor: User
) -> None:
    code = {
        "payroll": P.PAYROLL_ADJUST,
        "expense": P.EXPENSES_CREATE,
        "treasury": P.TREASURY_PAYMENT_REQUESTS_CREATE,
    }[effect.route]
    _require(organization, actor, effect.mission, code)


def _create(
    organization: Organization,
    actor: User,
    mission: LeaveMissionRequest,
    plan: MissionPlan,
    spec: EffectSpec,
    reason: str,
    predecessor: MissionEffect | None = None,
) -> MissionEffect:
    snapshot = _snapshot(mission, plan, spec)
    identity = effect_identity(
        organization.pk,
        mission.pk,
        plan.mission_version,
        spec.effect_id,
        spec.effect_type,
    )
    prior = MissionEffect.objects.filter(
        organization=organization, identity_hash=identity
    ).first()
    if prior:
        if predecessor is not None:
            raise RoutingRejected("REPLACEMENT_VERSION_ALREADY_USED")
        _native_permission(prior, organization, actor)
        if not _target_matches(prior):
            raise RoutingRejected("NATIVE_TARGET_LINEAGE_MISMATCH")
        if prior.payload_hash != digest(snapshot):
            raise RoutingRejected("IMMUTABLE_EFFECT_PAYLOAD_MISMATCH")
        return prior
    active = MissionEffect.objects.filter(
        organization=organization,
        mission=mission,
        effect_id=spec.effect_id,
        effect_type=spec.effect_type,
    ).exclude(events__kind__in=("cancelled", "replaced"))
    if predecessor:
        active = active.exclude(pk=predecessor.pk)
    if active.exists():
        raise RoutingRejected("PRIOR_EFFECT_REQUIRES_CONTROLLED_RESOLUTION")
    target = spec.target
    links = {}
    if isinstance(target, PayrollTarget):
        if (
            target.original_result is not None
            and target.original_result.employee_id != mission.employee_id
        ):
            raise RoutingRejected("EXACT_PAYROLL_EMPLOYEE_REQUIRED")
        links["payroll_target"] = record_adjustment(
            organization=organization,
            actor=actor,
            run=target.run,
            employee=mission.employee,
            component=target.component,
            kind=target.kind,
            amount=spec.amount,
            effective_on=target.effective_on,
            source_reference="mission:" + identity,
            reason=reason,
            original_result=target.original_result,
            source_payload={"mission_effect_identity": identity, "source": snapshot},
        )
    elif isinstance(target, ExpenseTarget):
        if mission.project is None:
            raise RoutingRejected("EXPLICIT_EXPENSE_PROJECT_REQUIRED")
        links["expense_target"] = create_expense_draft(
            organization=organization,
            actor=actor,
            project=mission.project,
            description=target.description,
            amount=spec.amount,
            incurred_on=target.incurred_on,
            source_reference="mission:" + identity,
            idempotency_key="mission:" + identity,
            category=target.category,
            expense_category=target.expense_category,
            reimbursement_employee=mission.employee,
            replaces=predecessor.expense_target
            if predecessor and predecessor.route == "expense"
            else None,
        )
    else:
        links["treasury_target"] = create_payment_request(
            organization=organization,
            actor=actor,
            kind="employee_advance",
            amount=spec.amount,
            purpose=target.purpose,
            idempotency_key="mission:" + identity,
            employee=mission.employee,
            project=mission.project,
            site=mission.site,
        )
    # Native target services enforce their own permissions, workflow and policy.
    effect = MissionEffect.objects.create(
        organization=organization,
        mission=mission,
        mission_version=plan.mission_version,
        effect_id=spec.effect_id,
        effect_type=spec.effect_type,
        route=spec.route,
        identity_hash=identity,
        payload_hash=digest(snapshot),
        source_snapshot=snapshot,
        policy_reference=mission.policy_reference,
        amount=spec.amount,
        currency=spec.currency,
        recorded_by=actor,
        **links,
    )
    MissionEffectEvent.objects.create(
        organization=organization,
        mission=mission,
        effect=effect,
        identity_hash=identity,
        kind="created",
        actor=actor,
        reason=reason,
    )
    return effect


def _failure(
    organization: Organization,
    actor: User,
    mission_id: UUID,
    effect_id: UUID,
    effect_type: str,
    reason: str,
    error: Exception,
) -> None:
    # Retain only an authorized source identity and a controlled code; never exception/PII text.
    with transaction.atomic():
        mission = _load(organization, actor, mission_id, P.LEAVE_MISSION_REVIEW)
        code = (
            error.code
            if isinstance(error, RoutingRejected)
            else "TARGET_OPERATION_FAILED"
        )
        MissionEffectEvent.objects.create(
            organization=organization,
            mission=mission,
            kind="failed",
            identity_hash=digest([str(mission_id), str(effect_id), effect_type]),
            actor=actor,
            reason=reason,
            error_code=code,
        )


def route_mission_effect(
    *,
    organization: Organization,
    actor: User,
    mission_id: UUID,
    effect_id: UUID,
    effect_type: str,
    reason: str,
) -> MissionEffect:
    if not reason.strip():
        raise ValidationError("Mission routing reason required.")
    authorized = False
    try:
        with transaction.atomic():
            mission = _load(organization, actor, mission_id, P.LEAVE_MISSION_REVIEW)
            authorized = True
            _binding, plan = _read_plan(organization, actor, mission)
            spec = _spec(plan, effect_id, effect_type)
            before = _snapshot(mission, plan, spec)
            effect = _create(organization, actor, mission, plan, spec, reason)
            mission.refresh_from_db()
            _binding, fresh = _read_plan(organization, actor, mission)
            if (
                _snapshot(mission, fresh, _spec(fresh, effect_id, effect_type))
                != before
            ):
                raise RoutingRejected("APPROVED_SOURCE_CHANGED_DURING_TARGET_OPERATION")
            return effect
    except Exception as exc:
        if authorized:
            _failure(
                organization, actor, mission_id, effect_id, effect_type, reason, exc
            )
        raise


def _reverse(
    organization: Organization,
    actor: User,
    mission: LeaveMissionRequest,
    effect: MissionEffect,
    binding: MissionPolicyBinding,
    reason: str,
) -> dict:
    _native_permission(effect, organization, actor)
    if effect.route == "payroll":
        if binding.read_payroll_correction is None:
            raise RoutingRejected("APPROVED_PAYROLL_CORRECTION_BINDING_REQUIRED")
        target = binding.read_payroll_correction(
            organization=organization, actor=actor, mission=mission, effect=effect
        )
        if isinstance(target, PayrollAdjustment):
            _require(organization, actor, mission, P.PAYROLL_RESULTS_VIEW)
            inverse = PayrollAdjustment.objects.select_related(
                "run", "original_result"
            ).get(pk=target.pk, organization=organization)
            original = effect.payroll_target
            if (
                original.run.status != "finalized"
                or inverse.run.status != "finalized"
                or inverse.employee_id != mission.employee_id
                or inverse.component_id != original.component_id
                or inverse.amount != -effect.amount
                or inverse.run.currency != effect.currency
                or inverse.source_payload.get("reverses_mission_effect")
                != effect.identity_hash
                or inverse.original_result is None
                or inverse.original_result.run_id != original.run_id
                or inverse.original_result.employee_id != mission.employee_id
            ):
                raise RoutingRejected("FINALIZED_NATIVE_PAYROLL_INVERSE_REQUIRED")
            return {"payroll_inverse": inverse}
        if not isinstance(target, PayrollTarget):
            raise RoutingRejected("TYPED_PAYROLL_CORRECTION_REQUIRED")
        if (
            effect.payroll_target.run.status != "draft"
            or target.run.pk != effect.payroll_target.run_id
        ):
            raise RoutingRejected("FINALIZED_NATIVE_PAYROLL_INVERSE_REQUIRED")
        if (
            not isinstance(target, PayrollTarget)
            or target.component.pk != effect.payroll_target.component_id
            or (
                target.original_result is not None
                and target.original_result.employee_id != mission.employee_id
            )
        ):
            raise RoutingRejected("EXACT_PAYROLL_COMPONENT_CORRECTION_REQUIRED")
        inverse = record_adjustment(
            organization=organization,
            actor=actor,
            run=target.run,
            employee=mission.employee,
            component=target.component,
            kind=target.kind,
            amount=-effect.amount,
            effective_on=target.effective_on,
            reason=reason,
            source_reference="mission-reverse:" + effect.identity_hash,
            original_result=target.original_result,
            source_payload={"reverses_mission_effect": effect.identity_hash},
        )
        return {"payroll_inverse": inverse}
    if effect.route == "expense":
        void_expense(expense=effect.expense_target, actor=actor, reason=reason)
        effect.expense_target.refresh_from_db()
        return {}
    request = effect.treasury_target
    request.refresh_from_db()
    if request.status in {"cancelled", "rejected"}:
        return {}
    movement = (
        request.released_movement
        or TreasuryMovement.objects.filter(origin_request=request).first()
    )
    if movement is None:
        cancel_payment_request(
            organization=organization, actor=actor, request=request, reason=reason
        )
        request.refresh_from_db()
        return {}
    # Cash reversal remains a native Treasury operation; routing consumes verified evidence only.
    _require(organization, actor, mission, P.TREASURY_VIEW)
    advance = (
        TreasuryAdvance.objects.filter(
            organization=organization,
            request=request,
            status="reversed",
            issue_movement=movement,
        )
        .select_related("reversal_movement")
        .first()
    )
    if (
        advance is None
        or advance.reversal_movement is None
        or advance.reversal_movement.status != "posted"
    ):
        raise RoutingRejected("NATIVE_TREASURY_ADVANCE_REVERSAL_REQUIRED")
    return {"treasury_reversal": advance.reversal_movement}


def resolve_mission_effect(
    *,
    organization: Organization,
    actor: User,
    effect_id: UUID,
    reason: str,
    replace: bool = False,
) -> MissionEffectEvent:
    if not reason.strip():
        raise ValidationError("Mission correction/cancellation reason required.")
    authorized = False
    old = MissionEffect.objects.filter(pk=effect_id, organization=organization).first()
    if old is None:
        raise PermissionDenied("Effect is outside the active tenant.")
    try:
        with transaction.atomic():
            mission = _load(organization, actor, old.mission_id, P.LEAVE_MISSION_REVIEW)
            authorized = True
            binding, plan = _read_plan(organization, actor, mission)
            old = MissionEffect.objects.select_for_update().get(pk=old.pk)
            _native_permission(old, organization, actor)
            previous = old.events.filter(kind__in=("cancelled", "replaced")).first()
            kind = "replaced" if replace else "cancelled"
            if previous:
                if (
                    previous.kind != kind
                    or previous.actor_id != actor.pk
                    or previous.reason != reason.strip()
                ):
                    raise RoutingRejected("TERMINAL_CORRECTION_REPLAY_MISMATCH")
                return previous
            spec = _spec(plan, old.effect_id, old.effect_type) if replace else None
            if replace and plan.mission_version == old.mission_version:
                raise RoutingRejected("DISTINCT_APPROVED_REPLACEMENT_VERSION_REQUIRED")
            source_before = digest(_mission_snapshot(mission))
            native = _reverse(organization, actor, mission, old, binding, reason)
            new = (
                _create(
                    organization, actor, mission, plan, spec, reason, predecessor=old
                )
                if replace
                else None
            )
            mission.refresh_from_db()
            _fresh_binding, fresh_plan = _read_plan(organization, actor, mission)
            if (
                fresh_plan.mission_version != plan.mission_version
                or fresh_plan.approval_reference != plan.approval_reference
                or (
                    replace
                    and _snapshot(
                        mission,
                        fresh_plan,
                        _spec(fresh_plan, old.effect_id, old.effect_type),
                    )
                    != _snapshot(mission, plan, spec)
                )
            ):
                raise RoutingRejected("APPROVED_POLICY_CHANGED_DURING_CORRECTION")
            if digest(_mission_snapshot(mission)) != source_before:
                raise RoutingRejected("APPROVED_SOURCE_CHANGED_DURING_TARGET_OPERATION")
            return MissionEffectEvent.objects.create(
                organization=organization,
                mission=mission,
                effect=old,
                identity_hash=old.identity_hash,
                kind=kind,
                replacement=new,
                actor=actor,
                reason=reason.strip(),
                **native,
            )
    except Exception as exc:
        if authorized:
            _failure(
                organization,
                actor,
                old.mission_id,
                old.effect_id,
                old.effect_type,
                reason,
                exc,
            )
        raise


def _target_matches(effect: MissionEffect) -> bool:
    target = effect.payroll_target or effect.expense_target or effect.treasury_target
    contract = effect.source_snapshot["target_contract"]
    if (
        target.organization_id != effect.organization_id
        or target.amount != effect.amount
    ):
        return False
    if effect.route == "payroll":
        return (
            target.employee_id == effect.mission.employee_id
            and target.run.currency == effect.currency
            and str(target.run_id) == contract["run"]
            and str(target.component_id) == contract["component"]
            and target.kind == contract["kind"]
            and str(target.effective_on) == contract["effective_on"]
            and target.source_payload.get("mission_effect_identity")
            == effect.identity_hash
            and target.source_payload.get("source") == effect.source_snapshot
        )
    if target.project_id != effect.mission.project_id:
        return False
    if effect.route == "expense":
        return (
            target.reimbursement_employee_id == effect.mission.employee_id
            and target.source_reference == "mission:" + effect.identity_hash
            and target.classification == "direct"
            and str(target.expense_category_id) == contract["expense_category"]
            and target.category == contract["category"]
            and str(target.incurred_on) == contract["incurred_on"]
            and target.description == contract["description"]
        )
    return (
        target.employee_id == effect.mission.employee_id
        and target.currency == effect.currency
        and target.kind == "employee_advance"
        and target.site_id == effect.mission.site_id
        and target.purpose == contract["purpose"]
        and target.idempotency_key == "mission:" + effect.identity_hash
    )


@transaction.atomic
def reconcile_mission_effects(
    *, organization: Organization, actor: User, mission_id: UUID
) -> dict:
    mission = _load(organization, actor, mission_id, P.LEAVE_MISSION_VIEW)
    try:
        _binding, plan = _read_plan(organization, actor, mission)
        active_version = plan.mission_version
        approved = {(x.effect_id, x.effect_type): x for x in plan.effects}
        policy_status = "approved_binding"
    except RoutingRejected as exc:
        active_version, approved, policy_status = None, {}, exc.code
    rows = []
    for effect in mission.financial_effects.select_related(
        "payroll_target__run", "expense_target", "treasury_target"
    ):
        permission = {
            "payroll": P.PAYROLL_RESULTS_VIEW,
            "expense": P.EXPENSES_VIEW,
            "treasury": P.TREASURY_VIEW,
        }[effect.route]
        _require(organization, actor, mission, permission)
        terminal = (
            effect.events.filter(kind__in=("cancelled", "replaced"))
            .select_related("replacement", "payroll_inverse", "treasury_reversal")
            .first()
        )
        spec = approved.get((effect.effect_id, effect.effect_type))
        source_matches = bool(
            spec
            and effect.mission_version == active_version
            and digest(_snapshot(mission, plan, spec)) == effect.payload_hash
        )
        target = (
            effect.payroll_target or effect.expense_target or effect.treasury_target
        )
        target_matches = _target_matches(effect)
        rows.append(
            {
                "effect": str(effect.pk),
                "identity": effect.identity_hash,
                "mission_version": effect.mission_version,
                "effect_id": str(effect.effect_id),
                "effect_type": effect.effect_type,
                "route": effect.route,
                "target": str(target.pk),
                "target_status": target.run.status
                if effect.route == "payroll"
                else target.status,
                "active_source_version": active_version,
                "source_matches": source_matches,
                "target_matches": target_matches,
                "payroll_inverse_run_status": terminal.payroll_inverse.run.status
                if terminal and terminal.payroll_inverse_id
                else None,
                "state": terminal.kind
                if terminal
                else "active"
                if source_matches and target_matches
                else "target_drift"
                if not target_matches
                else "stale_or_policy_held",
                "replacement": str(terminal.replacement_id)
                if terminal and terminal.replacement_id
                else None,
                "payroll_inverse": str(terminal.payroll_inverse_id)
                if terminal and terminal.payroll_inverse_id
                else None,
                "treasury_reversal": str(terminal.treasury_reversal_id)
                if terminal and terminal.treasury_reversal_id
                else None,
            }
        )
    return {
        "mission": str(mission.pk),
        "active_source_version": active_version,
        "policy_status": policy_status,
        "rows": rows,
        "projection_only": True,
    }
