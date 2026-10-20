"""CEP-057 bounded synthetic Development opening producer, never Production."""

import json
from collections.abc import Iterable
from dataclasses import asdict
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction

from apps.accounts.models import User
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization

from .leave_models import LeaveBalanceEntry, LeaveEntryKind
from .leave_opening_preparation import (
    OpeningBalanceDataset,
    _fingerprint,
    prepare_leave_opening_import,
)
from .leave_services import _access, _append
from .models import WorkRelationship

AUTHORITY = "DEV-SYNTHETIC-DATA-AUTH-20261020-V2"


def require_development(authority: str) -> None:
    if (
        settings.SETTINGS_MODULE != "config.settings.development"
        or connection.settings_dict["HOST"] not in {"127.0.0.1", "localhost", "::1"}
        or authority != AUTHORITY
    ):
        raise PermissionDenied(
            "Synthetic opening is authorized only in local Development."
        )


@transaction.atomic
def import_leave_opening(
    *, organization: Organization, actor: User, dataset: OpeningBalanceDataset
) -> dict:
    require_development(dataset.approval_reference)
    organization = _access(organization, actor, P.LEAVE_BALANCES_MANAGE)
    if dataset.cutover_on != dataset.as_of + timedelta(days=1):
        raise ValidationError("Opening coverage must end immediately before cutover.")
    canonical = asdict(dataset)
    canonical["rows"] = sorted(canonical["rows"], key=lambda r: r["source_id"])
    canonical["expected_totals"] = sorted(
        canonical["expected_totals"], key=lambda r: str((r["policy_id"], r["unit"]))
    )
    fingerprint = _fingerprint(canonical)
    keys = {
        r.source_id: "cep057:" + _fingerprint((dataset.source_reference, r.source_id))
        for r in dataset.rows
    }
    previous = {
        e.source_key: e
        for e in LeaveBalanceEntry.objects.filter(
            organization=organization, source_key__in=keys.values()
        )
    }
    if previous and len(previous) != len(dataset.rows):
        raise ValidationError(
            "Partial target population requires explicit reconciliation."
        )
    preview = prepare_leave_opening_import(
        organization=organization, actor=actor, dataset=dataset
    )
    for row in preview["mapping"]:
        if previous:
            row["errors"] = [
                e
                for e in row["errors"]
                if e != "EXISTING_HISTORY_REQUIRES_CUTOFF_RECONCILIATION"
            ]
    exceptions = [r for r in preview["mapping"] if r["errors"]]
    if exceptions or not all(r["matched"] for r in preview["reconciliation"]):
        raise ValidationError(
            json.dumps(
                {"exceptions": exceptions, "reconciliation": preview["reconciliation"]}
            )
        )
    targets = []
    for row in sorted(dataset.rows, key=lambda r: r.source_id):
        relationship = WorkRelationship.objects.get(
            pk=row.relationship_id, organization=organization
        )
        reason = json.dumps(
            {
                "synthetic": True,
                "authority": AUTHORITY,
                "process_version": 1,
                "dataset": fingerprint,
                "source": asdict(row),
                "as_of": str(dataset.as_of),
                "cutover_on": str(dataset.cutover_on),
            },
            default=str,
            sort_keys=True,
        )
        from .leave_models import LeavePolicyVersion

        policy = LeavePolicyVersion.objects.get(
            pk=row.policy_id, organization=organization
        )
        entry = _append(
            organization=organization,
            actor=actor,
            relationship=relationship,
            policy=policy,
            effective_on=dataset.as_of,
            kind=LeaveEntryKind.OPENING,
            quantity=row.quantity,
            reserved_quantity=Decimal(0),
            source_key=keys[row.source_id],
            evidence_reference=row.evidence_reference,
            reason=reason,
        )
        if LeaveBalanceEntry.objects.filter(reverses=entry).exists():
            raise ValidationError("A reversed opening cannot be silently reactivated.")
        targets.append(
            {
                "source_id": row.source_id,
                "target_id": str(entry.pk),
                "quantity": format(entry.quantity, ".4f"),
                "policy_id": str(entry.policy_id),
                "relationship_id": str(entry.relationship_id),
            }
        )
    return {
        "fingerprint": fingerprint,
        "source_count": len(dataset.rows),
        "created": 0 if previous else len(targets),
        "mapping": targets,
        "reconciliation": preview["reconciliation"],
        "exceptions": [],
        "synthetic_only": True,
        "production_cutover": False,
    }


@transaction.atomic
def reverse_leave_opening(
    *, organization: Organization, actor: User, entries: Iterable[LeaveBalanceEntry]
) -> tuple[LeaveBalanceEntry, ...]:
    """Compensate an unused opening; any subsequent movement requires reconciliation."""
    require_development(AUTHORITY)
    organization = _access(organization, actor, P.LEAVE_BALANCES_MANAGE)
    result = []
    for supplied in entries:
        source = (
            LeaveBalanceEntry.objects.select_for_update()
            .filter(
                pk=supplied.pk, organization=organization, kind=LeaveEntryKind.OPENING
            )
            .first()
        )
        if source is None or json.loads(source.reason).get("authority") != AUTHORITY:
            raise PermissionDenied(
                "Only this tenant's synthetic openings may be reversed."
            )
        if (
            LeaveBalanceEntry.objects.filter(
                organization=organization,
                relationship=source.relationship,
                policy__category_code=source.policy.category_code,
            )
            .exclude(pk=source.pk)
            .exclude(reverses=source)
            .exists()
        ):
            raise ValidationError(
                "Subsequent history requires explicit recovery reconciliation."
            )
        result.append(
            _append(
                organization=organization,
                actor=actor,
                relationship=source.relationship,
                policy=source.policy,
                effective_on=source.effective_on,
                kind=LeaveEntryKind.REVERSAL,
                quantity=-source.quantity,
                reserved_quantity=Decimal(0),
                source_key=source.source_key + ":rollback",
                evidence_reference=source.evidence_reference,
                reason="Synthetic opening rollback; retained original lineage",
                reverses=source,
            )
        )
    return tuple(result)
