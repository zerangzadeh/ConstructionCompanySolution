"""CEP-058 signed operational openings with retained external synthetic provenance.

Local Development only. No fabricated finalized results, statutory rates or posting.
"""

import hashlib
import json
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization, OrganizationSettings
from apps.workforce.leave_opening_import import AUTHORITY, require_development
from apps.workforce.models import Employee, WorkRelationship
from core.tenant_validation import validate_related_organizations

from .models import PayrollComponent, PayrollCumulativeState, PayrollYearInterval
from .opening_preparation import OPERATIONAL_KINDS, _amount
from .services import _scope

MANIFEST = "8afd738bb2ca2b92a20f1b8b7c7a8d4cba0015ede1e135da26c6a03a93b2f8f3"
ASOF = date(2026, 9, 30)
CUTOVER = date(2026, 10, 1)


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()


def validate_opening_state(state: PayrollCumulativeState) -> None:
    """Domain guard for both original external openings and exact compensations."""
    require_development(AUTHORITY)
    validate_related_organizations(
        state,
        year=state.year,
        employee=state.employee,
        work_relationship=state.work_relationship,
        component=state.component,
    )
    ev = state.opening_evidence
    if not isinstance(ev, dict):
        raise ValidationError("Explicit opening provenance required.")
    raw = ev.get("source", {})
    if (
        state.source_line_id
        or state.source_run_id
        or not state.work_relationship_id
        or ev.get("authority") != AUTHORITY
        or ev.get("synthetic") is not True
        or ev.get("manifest") != MANIFEST
        or ev.get("as_of") != str(ASOF)
        or ev.get("cutover_on") != str(CUTOVER)
        or raw.get("included_in_opening") != "YES"
        or raw.get("source_status") != "FINALIZED"
        or not raw.get("source_record_id", "").startswith("DEV-PAY-")
        or raw.get("source_version") != "DEV-PAYROLL-EXPORT-v2"
        or not raw.get("evidence_reference")
        or raw.get("currency") != "IRR"
        or raw.get("source_period") != "2026-YTD-09"
        or state.component_kind not in OPERATIONAL_KINDS
        or state.component_kind != state.component.kind
        or raw.get("external_component_key") != state.component.code
        or state.source_version != raw.get("source_digest")
        or len(state.source_version) != 64
        or state.year.code != "DEV-PY-2026-A"
        or state.year.version != 2
        or state.year.status != "approved"
        or state.year.starts_on != date(2026, 1, 1)
        or state.year.ends_on != date(2026, 12, 31)
        or state.effective_on != ASOF
        or state.work_relationship.legacy_employee_id != state.employee_id
        or state.work_relationship.effective_start > ASOF
        or (
            state.work_relationship.effective_end
            and state.work_relationship.effective_end < ASOF
        )
        or not state.work_relationship.revisions.exists()
        or ev.get("employee_id") != str(state.employee_id)
        or ev.get("relationship_id") != str(state.work_relationship_id)
    ):
        raise ValidationError(
            "External opening must retain its exact approved synthetic context."
        )
    amount = Decimal(raw["signed_amount"])
    _amount(amount)
    key = digest((raw["source_version"], raw["source_record_id"]))
    if ev.get("reverses"):
        original = PayrollCumulativeState.objects.filter(
            pk=ev["reverses"],
            organization=state.organization,
            year=state.year,
            employee=state.employee,
            component=state.component,
            opening_key=key,
        ).first()
        if original is None or original.opening_evidence != {
            k: v for k, v in ev.items() if k != "reverses"
        }:
            raise ValidationError(
                "Opening rollback must pin the exact original history."
            )
        key = digest((key, "rollback"))
        amount = -amount
    if state.opening_key != key or state.delta != amount:
        raise ValidationError("Opening key or signed source amount mismatch.")
    excluded = ev.get("excluded_lineage", [])
    if raw.get("correction_reference"):
        if (
            len(excluded) != 1
            or excluded[0]["source_record_id"] != raw["correction_reference"]
        ):
            raise ValidationError("Correction predecessor evidence is required.")
        predecessor = excluded[0]
        if (
            predecessor["replacement_reference"] != raw["source_record_id"]
            or predecessor["source_status"] != "SUPERSEDED"
            or predecessor["included_in_opening"] != "NO"
            or any(
                predecessor[k] != raw[k]
                for k in (
                    "source_employee_key",
                    "external_component_key",
                    "source_period",
                )
            )
        ):
            raise ValidationError(
                "Correction lineage is not reciprocal within its source bucket."
            )
    elif excluded:
        raise ValidationError("Unexpected excluded lineage.")


@transaction.atomic
def import_payroll_opening(
    *,
    organization: Organization,
    actor: User,
    year: PayrollYearInterval,
    rows: list[dict[str, str]],
    identities: dict[str, dict[str, str]],
    components: dict[str, UUID],
    totals: dict[str, Decimal],
    authority: str = AUTHORITY,
) -> dict:
    require_development(authority)
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    _scope(P.PAYROLL_FINALIZE, organization=organization, actor=actor)
    year = (
        PayrollYearInterval.objects.select_for_update()
        .filter(pk=year.pk, organization=organization)
        .first()
    )
    if year is None:
        raise PermissionDenied("Payroll year is outside the active tenant.")
    if (
        year.status != "approved"
        or year.code != "DEV-PY-2026-A"
        or year.version != 2
        or year.starts_on != date(2026, 1, 1)
        or year.ends_on != date(2026, 12, 31)
        or not OrganizationSettings.objects.filter(
            organization=organization, currency="IRR"
        ).exists()
    ):
        raise ValidationError(
            "Approved synthetic year/version/currency binding required, including on retry."
        )
    if not rows or len({r["source_record_id"] for r in rows}) != len(rows):
        raise ValidationError("Explicit unique external opening sources required.")
    selected = [r for r in rows if r["included_in_opening"] == "YES"]
    excluded = [r for r in rows if r["included_in_opening"] != "YES"]
    by_id = {r["source_record_id"]: r for r in rows}
    if any(
        r["included_in_opening"] != "NO"
        or r["source_status"] != "SUPERSEDED"
        or r["replacement_reference"] not in by_id
        or by_id[r["replacement_reference"]]["correction_reference"]
        != r["source_record_id"]
        for r in excluded
    ):
        raise ValidationError("Unresolved excluded source lineage.")
    computed = {}
    for r in selected:
        value = Decimal(r["signed_amount"])
        _amount(value)
        key = r["external_component_key"]
        computed[key] = computed.get(key, Decimal(0)) + value
    if computed != totals:
        raise ValidationError("Opening per-component signed controls do not reconcile.")
    mapping = []
    created = 0
    for raw in sorted(selected, key=lambda r: r["source_record_id"]):
        identity = identities.get(raw["source_employee_key"], {})
        relationship = (
            WorkRelationship.objects.select_for_update()
            .filter(
                pk=identity.get("relationship_id"),
                organization=organization,
                legacy_employee_id=identity.get("employee_id"),
            )
            .first()
        )
        component = PayrollComponent.objects.filter(
            pk=components.get(raw["external_component_key"]),
            organization=organization,
            is_active=True,
            is_statutory_reserved=False,
        ).first()
        if relationship is None or component is None:
            raise PermissionDenied(
                "Explicit opening identity/component is outside the active tenant."
            )
        employee = Employee.objects.select_for_update().get(
            pk=relationship.legacy_employee_id, organization=organization
        )
        key = digest((raw["source_version"], raw["source_record_id"]))
        evidence = {
            "authority": authority,
            "synthetic": True,
            "manifest": MANIFEST,
            "as_of": str(ASOF),
            "cutover_on": str(CUTOVER),
            "source": raw,
            "employee_id": str(employee.pk),
            "relationship_id": str(relationship.pk),
            "excluded_lineage": [by_id[raw["correction_reference"]]]
            if raw["correction_reference"]
            else [],
        }
        existing = PayrollCumulativeState.objects.filter(
            year=year, opening_key=key
        ).first()
        if existing:
            if (
                existing.opening_evidence != evidence
                or existing.employee_id != employee.pk
                or existing.component_id != component.pk
                or existing.work_relationship_id != relationship.pk
                or existing.delta != Decimal(raw["signed_amount"])
            ):
                raise ValidationError(
                    "Existing opening key has different source facts."
                )
            if PayrollCumulativeState.objects.filter(
                year=year, opening_key=digest((key, "rollback"))
            ).exists():
                raise ValidationError(
                    "Reversed opening cannot be silently reactivated."
                )
            state = existing
        else:
            if PayrollCumulativeState.objects.filter(
                year=year, employee=employee, component=component
            ).exists():
                raise ValidationError(
                    "Existing bucket history requires cutoff reconciliation."
                )
            state = PayrollCumulativeState.objects.create(
                organization=organization,
                year=year,
                employee=employee,
                work_relationship=relationship,
                component=component,
                component_kind=component.kind,
                state_version=1,
                source_version=raw["source_digest"],
                effective_on=ASOF,
                delta=Decimal(raw["signed_amount"]),
                balance=Decimal(raw["signed_amount"]),
                opening_key=key,
                opening_evidence=evidence,
            )
            _audit(state, actor)
            created += 1
        mapping.append(
            {
                "source_id": raw["source_record_id"],
                "target_id": str(state.pk),
                "component": component.code,
                "kind": component.kind,
                "amount": format(state.delta, ".2f"),
                "employee_id": str(employee.pk),
                "relationship_id": str(relationship.pk),
            }
        )
    return {
        "source_count": len(rows),
        "included_count": len(selected),
        "excluded_count": len(excluded),
        "excluded": excluded,
        "created": created,
        "mapping": mapping,
        "totals": {k: str(v) for k, v in computed.items()},
        "exceptions": [],
        "synthetic_only": True,
        "production_cutover": False,
    }


def _audit(state, actor):
    record_audit_event(
        action=AuditAction.PAYROLL_CUMULATIVE_RECORDED,
        entity_type="payroll_cumulative_state",
        entity_id=state.pk,
        organization=state.organization,
        actor=actor,
        metadata={
            "authority": AUTHORITY,
            "synthetic": True,
            "year_id": str(state.year_id),
            "opening_key": state.opening_key,
            "source_id": state.opening_evidence["source"]["source_record_id"],
            "source_version": state.source_version,
            "delta": str(state.delta),
            "reverses": state.opening_evidence.get("reverses"),
        },
    )


@transaction.atomic
def reverse_payroll_opening(
    *,
    organization: Organization,
    actor: User,
    entries: Iterable[PayrollCumulativeState],
) -> tuple[PayrollCumulativeState, ...]:
    require_development(AUTHORITY)
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    _scope(P.PAYROLL_ADJUST, organization=organization, actor=actor)
    result = []
    for supplied in entries:
        source = PayrollCumulativeState.objects.filter(
            pk=supplied.pk, organization=organization, opening_key__isnull=False
        ).first()
        if source is None or source.opening_evidence.get("reverses"):
            raise PermissionDenied("Rollback requires this tenant's original opening.")
        Employee.objects.select_for_update().get(
            pk=source.employee_id, organization=organization
        )
        key = digest((source.opening_key, "rollback"))
        existing = PayrollCumulativeState.objects.filter(
            year=source.year, opening_key=key
        ).first()
        if existing:
            result.append(existing)
            continue
        if (
            PayrollCumulativeState.objects.filter(
                year=source.year, employee=source.employee, component=source.component
            )
            .exclude(pk=source.pk)
            .exists()
        ):
            raise ValidationError(
                "Subsequent history requires explicit recovery reconciliation."
            )
        inverse = PayrollCumulativeState.objects.create(
            organization=organization,
            year=source.year,
            employee=source.employee,
            work_relationship=source.work_relationship,
            component=source.component,
            component_kind=source.component_kind,
            state_version=source.state_version + 1,
            source_version=source.source_version,
            effective_on=source.effective_on,
            delta=-source.delta,
            balance=Decimal(0),
            opening_key=key,
            opening_evidence=source.opening_evidence | {"reverses": str(source.pk)},
        )
        _audit(inverse, actor)
        result.append(inverse)
    return tuple(result)
