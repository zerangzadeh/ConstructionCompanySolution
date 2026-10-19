"""CEP-057 read-only opening-source preparation, never approval or migration.

Inputs must come from explicit source evidence. References are retained claims,
not proof of EXT-0015 approval. This module cannot write opening balances, infer
quantities from requests, switch authority, or execute a rollback/cutover.
"""

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization

from .leave_models import LeaveBalanceEntry, LeavePolicyVersion
from .leave_services import _access, _policy, _quantity
from .models import WorkRelationship

PROCESS_VERSION = 1


@dataclass(frozen=True)
class OpeningBalanceRow:
    source_id: str
    source_version: str
    evidence_reference: str
    employee_id: UUID
    relationship_id: UUID
    policy_id: UUID
    unit: str
    quantity: Decimal


@dataclass(frozen=True)
class OpeningBalanceTotal:
    policy_id: UUID
    unit: str
    quantity: Decimal


@dataclass(frozen=True)
class OpeningBalanceDataset:
    source_reference: str
    source_version: str
    approval_reference: str
    as_of: date
    cutover_on: date
    expected_count: int
    expected_totals: tuple[OpeningBalanceTotal, ...]
    rows: tuple[OpeningBalanceRow, ...]


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 255:
        raise ValidationError("Explicit bounded source/version/evidence is required.")


def _amount(value: Decimal) -> None:
    _quantity(value)
    if abs(value) >= Decimal(10000000000):
        raise ValidationError("Opening quantity exceeds the authoritative precision.")


def _shape(dataset: OpeningBalanceDataset) -> None:
    if not isinstance(dataset, OpeningBalanceDataset):
        raise ValidationError("An explicit opening source dataset is required.")
    for value in (
        dataset.source_reference,
        dataset.source_version,
        dataset.approval_reference,
    ):
        _text(value)
    if type(dataset.as_of) is not date or type(dataset.cutover_on) is not date:
        raise ValidationError("Explicit source as-of and cutover dates are required.")
    if (
        type(dataset.expected_count) is not int
        or dataset.expected_count <= 0
        or not isinstance(dataset.rows, tuple)
        or not isinstance(dataset.expected_totals, tuple)
        or not dataset.expected_totals
        or dataset.expected_count != len(dataset.rows)
    ):
        raise ValidationError(
            "Source rows and explicit nonempty counts must reconcile."
        )
    ids = []
    for row in dataset.rows:
        if not isinstance(row, OpeningBalanceRow):
            raise ValidationError("An explicit typed opening source row is required.")
        for value in (row.source_id, row.source_version, row.evidence_reference):
            _text(value)
        if any(
            not isinstance(value, UUID)
            for value in (row.employee_id, row.relationship_id, row.policy_id)
        ):
            raise ValidationError(
                "Explicit UUID source/target identifiers are required."
            )
        _text(row.unit)
        _amount(row.quantity)
        ids.append(row.source_id)
    if len(set(ids)) != len(ids):
        raise ValidationError("Duplicate source identifiers require reconciliation.")
    totals = []
    for total in dataset.expected_totals:
        if not isinstance(total, OpeningBalanceTotal) or not isinstance(
            total.policy_id, UUID
        ):
            raise ValidationError(
                "Explicit per-policy/unit source totals are required."
            )
        _text(total.unit)
        _quantity(total.quantity)
        totals.append((total.policy_id, total.unit))
    if len(set(totals)) != len(totals):
        raise ValidationError("Duplicate control-total groups require reconciliation.")


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


@transaction.atomic
def prepare_leave_opening_import(
    *, organization: Organization, actor: User, dataset: OpeningBalanceDataset
) -> dict[str, Any]:
    """Validate an explicit candidate and report every row without business writes.

    The returned report is a point-in-time preview, never a reusable write permit.
    Even a clean preview leaves EXT-0015 approval and migration execution blocked.
    """
    organization = _access(organization, actor, P.LEAVE_BALANCES_MANAGE)
    _shape(dataset)
    relationships = {
        row.pk: row
        for row in WorkRelationship.objects.select_for_update().filter(
            organization=organization,
            pk__in={row.relationship_id for row in dataset.rows},
        )
    }
    policies = {
        row.pk: row
        for row in LeavePolicyVersion.objects.filter(
            organization=organization,
            pk__in={row.policy_id for row in dataset.rows}
            | {total.policy_id for total in dataset.expected_totals},
        )
    }
    # Validate all explicit objects before returning any row-level source evidence.
    if set(relationships) != {row.relationship_id for row in dataset.rows} or set(
        policies
    ) != {row.policy_id for row in dataset.rows} | {
        total.policy_id for total in dataset.expected_totals
    }:
        raise PermissionDenied("Opening references are outside the active tenant.")
    for row in dataset.rows:
        if relationships[row.relationship_id].legacy_employee_id != row.employee_id:
            raise PermissionDenied("Opening source lacks its explicit Employee link.")

    subject_counts = Counter(
        (row.relationship_id, policies[row.policy_id].category_code)
        for row in dataset.rows
    )
    source_totals = defaultdict(Decimal)
    mapping = []
    for row in sorted(dataset.rows, key=lambda item: item.source_id):
        relationship = relationships[row.relationship_id]
        policy = policies[row.policy_id]
        source_totals[(row.policy_id, row.unit)] += row.quantity
        errors = []
        if not relationship.revisions.exists():
            errors.append("IDENTITY_REVISION_EVIDENCE_MISSING")
        if dataset.as_of < relationship.effective_start or (
            relationship.effective_end and dataset.as_of > relationship.effective_end
        ):
            errors.append("ASOF_OUTSIDE_EMPLOYMENT_EPISODE")
        if not policy.effective_from <= dataset.as_of < policy.effective_to:
            errors.append("POLICY_NOT_EFFECTIVE_ASOF")
        elif _policy(organization, policy.category_code, dataset.as_of).pk != policy.pk:
            errors.append("POLICY_VERSION_SUPERSEDED")
        if row.unit != policy.unit:
            errors.append("EXPLICIT_UNIT_MISMATCH")
        if row.quantity == 0:
            errors.append("ZERO_SOURCE_REQUIRES_EXPLICIT_TARGET_DISPOSITION")
        if row.quantity < policy.negative_balance_threshold:
            errors.append("SOURCE_BELOW_EXPLICIT_POLICY_FLOOR")
        if subject_counts[(row.relationship_id, policy.category_code)] != 1:
            errors.append("MULTIPLE_OPENINGS_REQUIRE_SOURCE_RECONCILIATION")
        existing = list(
            LeaveBalanceEntry.objects.filter(
                organization=organization,
                relationship=relationship,
                policy__category_code=policy.category_code,
            )
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        if existing:
            errors.append("EXISTING_HISTORY_REQUIRES_CUTOFF_RECONCILIATION")
        mapping.append(
            {
                "source": json.loads(json.dumps(asdict(row), default=str)),
                "status": "EXCEPTION" if errors else "VALIDATED_CANDIDATE",
                "errors": errors,
                "existing_entry_ids": [str(pk) for pk in existing],
            }
        )
    expected = {
        (total.policy_id, total.unit): total.quantity
        for total in dataset.expected_totals
    }
    reconciliation = [
        {
            "policy_id": str(key[0]),
            "unit": key[1],
            "source_quantity": str(source_totals.get(key, Decimal(0))),
            "expected_quantity": str(expected[key]) if key in expected else None,
            "matched": key in source_totals
            and key in expected
            and source_totals[key] == expected[key],
        }
        for key in sorted(set(source_totals) | set(expected), key=str)
    ]
    exceptions = [row for row in mapping if row["errors"]]
    return {
        "process_version": PROCESS_VERSION,
        "organization_id": str(organization.pk),
        "source_reference": dataset.source_reference,
        "source_version": dataset.source_version,
        "approval_reference_claim": dataset.approval_reference,
        "approval_verified": False,
        "as_of": dataset.as_of.isoformat(),
        "cutover_on": dataset.cutover_on.isoformat(),
        "input_fingerprint": _fingerprint(asdict(dataset)),
        "source_count": len(mapping),
        "validated_count": len(mapping) - len(exceptions),
        "exception_count": len(exceptions),
        "mapping": mapping,
        "exceptions": exceptions,
        "reconciliation": reconciliation,
        "candidate_validation_passed": not exceptions
        and all(row["matched"] for row in reconciliation),
        "migration_execution_allowed": False,
        "authority_cutover": False,
        "business_writes": 0,
        "target_entries_created": 0,
    }
