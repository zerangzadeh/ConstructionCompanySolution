"""Read-only historical Payroll/YTD reconciliation; never an opening authority.

EXT-0017 approval is not established by a caller-supplied reference. This module
cannot import balances, synthesize finalized Payroll sources, or switch authority.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, localcontext
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization
from apps.workforce.models import WorkRelationship

from .models import (
    ComponentKind,
    PayrollCumulativeState,
    PayrollResultLine,
    PayrollRunStatus,
    PayrollYearInterval,
    PayrollYearStatus,
    ResultStatus,
)
from .services import _scope

PROCESS_VERSION = 1
OPERATIONAL_KINDS = frozenset(
    {
        ComponentKind.EARNING,
        ComponentKind.ALLOWANCE,
        ComponentKind.DEDUCTION,
        ComponentKind.REIMBURSEMENT,
        ComponentKind.EMPLOYER,
    }
)


@dataclass(frozen=True)
class HistoricalPayrollRow:
    source_id: str
    source_version: str
    evidence_reference: str
    source_line_id: UUID
    employee_id: UUID
    relationship_id: UUID
    component_id: UUID
    component_kind: str
    amount: Decimal


@dataclass(frozen=True)
class HistoricalPayrollTotal:
    component_id: UUID
    component_kind: str
    amount: Decimal


@dataclass(frozen=True)
class HistoricalPayrollDataset:
    source_reference: str
    source_version: str
    approval_reference: str
    year_id: UUID
    as_of: date
    expected_count: int
    expected_totals: tuple[HistoricalPayrollTotal, ...]
    rows: tuple[HistoricalPayrollRow, ...]


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 255:
        raise ValidationError("Explicit bounded source/version/evidence is required.")


def _amount(value: Decimal) -> None:
    if (
        not isinstance(value, Decimal)
        or not value.is_finite()
        or value.copy_abs() >= Decimal("1e22")
        or value.as_tuple().exponent < -2
    ):
        raise ValidationError("An exact signed Payroll amount is required.")


def _shape(dataset: HistoricalPayrollDataset) -> None:
    if not isinstance(dataset, HistoricalPayrollDataset):
        raise ValidationError("An explicit historical Payroll dataset is required.")
    for value in (
        dataset.source_reference,
        dataset.source_version,
        dataset.approval_reference,
    ):
        _text(value)
    if (
        not isinstance(dataset.year_id, UUID)
        or type(dataset.as_of) is not date
        or type(dataset.expected_count) is not int
        or dataset.expected_count <= 0
        or not isinstance(dataset.rows, tuple)
        or not isinstance(dataset.expected_totals, tuple)
        or not dataset.expected_totals
        or len(dataset.rows) != dataset.expected_count
    ):
        raise ValidationError(
            "Explicit year, as-of, rows and control totals are required."
        )
    for row in dataset.rows:
        if not isinstance(row, HistoricalPayrollRow):
            raise ValidationError("A typed historical source row is required.")
        for value in (row.source_id, row.source_version, row.evidence_reference):
            _text(value)
        _text(row.component_kind)
        if not all(
            isinstance(value, UUID)
            for value in (
                row.source_line_id,
                row.employee_id,
                row.relationship_id,
                row.component_id,
            )
        ):
            raise ValidationError("Explicit source and identity UUIDs are required.")
        _amount(row.amount)
    for attr in ("source_id", "source_line_id"):
        if len({getattr(row, attr) for row in dataset.rows}) != len(dataset.rows):
            raise ValidationError(
                "Duplicate historical sources require reconciliation."
            )
    keys = []
    for total in dataset.expected_totals:
        if not isinstance(total, HistoricalPayrollTotal) or not isinstance(
            total.component_id, UUID
        ):
            raise ValidationError("Explicit per-component control totals are required.")
        _amount(total.amount)
        _text(total.component_kind)
        keys.append((total.component_id, total.component_kind))
    if len(set(keys)) != len(keys):
        raise ValidationError("Duplicate control totals require reconciliation.")


@transaction.atomic
def prepare_historical_payroll(
    *, organization: Organization, actor: User, dataset: HistoricalPayrollDataset
) -> dict:
    """Compare supplied evidence to current sources; approval and execution stay false.

    Coverage is the explicitly supplied rows only. No eligible population, cutoff,
    missing source amount, statutory classification or external approval is inferred.
    The result is a preparation snapshot; it is never a mutation authorization.
    """
    _scope(P.PAYROLL_RESULTS_VIEW, organization=organization, actor=actor)
    _shape(dataset)
    year = PayrollYearInterval.objects.filter(
        pk=dataset.year_id, organization=organization
    ).first()
    relationships = {
        obj.pk: obj
        for obj in WorkRelationship.objects.filter(
            organization=organization,
            pk__in={row.relationship_id for row in dataset.rows},
        )
    }
    lines = {
        obj.pk: obj
        for obj in PayrollResultLine.objects.filter(
            organization=organization,
            pk__in={row.source_line_id for row in dataset.rows},
        ).select_related("run__period", "run_employee__employee", "component")
    }
    if (
        year is None
        or set(relationships) != {row.relationship_id for row in dataset.rows}
        or set(lines) != {row.source_line_id for row in dataset.rows}
    ):
        raise PermissionDenied("Historical references are outside the active scope.")
    # Validate every object before disclosing row-level source or target evidence.
    for row in dataset.rows:
        line = lines[row.source_line_id]
        result = line.run_employee
        if (
            result.organization_id != organization.pk
            or line.run.organization_id != organization.pk
            or line.component.organization_id != organization.pk
            or result.employee.organization_id != organization.pk
            or result.run_id != line.run_id
            or result.employee_id != row.employee_id
            or relationships[row.relationship_id].legacy_employee_id != row.employee_id
        ):
            raise PermissionDenied("Explicit Payroll identity linkage is required.")
        _scope(
            P.PAYROLL_RESULTS_VIEW,
            organization=organization,
            actor=actor,
            project=result.project,
            site=result.site,
        )
    targets = {
        state.source_line_id: state
        for state in PayrollCumulativeState.objects.filter(
            organization=organization,
            year=year,
            source_line_id__in=lines,
        )
    }
    totals = defaultdict(Decimal)
    mapping = []
    for row in sorted(dataset.rows, key=lambda item: item.source_id):
        line = lines[row.source_line_id]
        relationship = relationships[row.relationship_id]
        effective_on = line.run.period.ends_on
        errors = []
        if year.status != PayrollYearStatus.APPROVED:
            errors.append("PAYROLL_YEAR_NOT_CURRENT_APPROVED")
        if not (
            year.starts_on
            <= line.run.period.starts_on
            <= effective_on
            <= dataset.as_of
            <= year.ends_on
        ):
            errors.append("SOURCE_OUTSIDE_EXPLICIT_YEAR_OR_ASOF")
        if (
            line.run.status
            not in {PayrollRunStatus.FINALIZED, PayrollRunStatus.REVERSED}
            or line.run_employee.status
            not in {ResultStatus.FINALIZED, ResultStatus.REVERSED}
            or not line.run.calculation_digest
        ):
            errors.append("FINALIZED_VERSIONED_SOURCE_REQUIRED")
        if row.source_version != line.run.calculation_digest:
            errors.append("SOURCE_VERSION_MISMATCH")
        if (
            row.component_kind not in OPERATIONAL_KINDS
            or row.component_kind != line.component_kind
            or row.component_id != line.component_id
            or row.amount != line.amount
        ):
            errors.append("SIGNED_SOURCE_OR_OPERATIONAL_COMPONENT_MISMATCH")
        if effective_on < relationship.effective_start or (
            relationship.effective_end and effective_on > relationship.effective_end
        ):
            errors.append("SOURCE_OUTSIDE_EXPLICIT_WORK_RELATIONSHIP")
        state = targets.get(line.pk)
        if state and (
            state.source_run_id != line.run_id
            or state.source_version != row.source_version
            or state.employee_id != row.employee_id
            or state.work_relationship_id != row.relationship_id
            or state.component_id != row.component_id
            or state.component_kind != row.component_kind
            or state.delta != row.amount
            or state.effective_on != effective_on
        ):
            errors.append("EXISTING_TARGET_REQUIRES_RECONCILIATION")
        with localcontext() as context:
            context.prec = 28 + len(str(dataset.expected_count))
            totals[(row.component_id, row.component_kind)] += row.amount
        mapping.append(
            {
                "source": json.loads(json.dumps(asdict(row), default=str)),
                "source_run_id": str(line.run_id),
                "effective_on": effective_on.isoformat(),
                "target_id": str(state.pk) if state else None,
                "status": "EXCEPTION"
                if errors
                else ("EXISTING_TARGET" if state else "VALIDATED_CANDIDATE"),
                "errors": errors,
            }
        )
    expected = {
        (total.component_id, total.component_kind): total.amount
        for total in dataset.expected_totals
    }
    reconciliation = [
        {
            "component_id": str(key[0]),
            "component_kind": key[1],
            "source_amount": str(totals.get(key, Decimal(0))),
            "expected_amount": str(expected[key]) if key in expected else None,
            "matched": key in totals
            and key in expected
            and totals[key] == expected[key],
        }
        for key in sorted(set(totals) | set(expected), key=str)
    ]
    payload = asdict(dataset)
    payload["rows"] = [row["source"] for row in mapping]
    payload["expected_totals"] = sorted(
        payload["expected_totals"],
        key=lambda item: str((item["component_id"], item["component_kind"])),
    )
    fingerprint = hashlib.sha256(
        json.dumps(payload, default=str, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    exceptions = [row for row in mapping if row["errors"]]
    return {
        "process_version": PROCESS_VERSION,
        "organization_id": str(organization.pk),
        "year_id": str(year.pk),
        "year_version": year.version,
        "as_of": dataset.as_of.isoformat(),
        "source_reference": dataset.source_reference,
        "source_version": dataset.source_version,
        "approval_reference_claim": dataset.approval_reference,
        "approval_verified": False,
        "input_fingerprint": fingerprint,
        "coverage": "SUPPLIED_ROWS_ONLY_NOT_APPROVED_POPULATION",
        "source_count": len(mapping),
        "existing_target_count": len(targets),
        "exception_count": len(exceptions),
        "mapping": mapping,
        "exceptions": exceptions,
        "reconciliation": reconciliation,
        "candidate_validation_passed": not exceptions
        and all(item["matched"] for item in reconciliation),
        "migration_execution_allowed": False,
        "authority_cutover": False,
        "business_writes": 0,
        "target_entries_created": 0,
    }
