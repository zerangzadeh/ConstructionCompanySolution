"""IMB-0065: authorized native facts and one retained slice per exact grain."""

from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import Organization
from apps.projects.models import Project

from .models import SubledgerReconciliationAccountSlice
from .services import (
    _amounts_as_of,
    _canonical_hash,
    _source_reversed_amount_as_of,
    obligation_queryset,
)


@transaction.atomic
def settlement_reconciliation(
    *,
    organization: Organization,
    actor: User,
    as_of_date: date,
    project: Project | None = None,
) -> dict[str, object]:
    """Never create a run, journal, settlement, write-off or source correction."""
    if type(as_of_date) is not date:
        raise ValidationError("An exact business-date cutoff is required.")
    if project is not None and project.organization_id != organization.pk:
        raise PermissionDenied("Project is outside the active organization.")
    obligations = obligation_queryset(organization=organization, actor=actor).filter(
        recognized_on__lte=as_of_date
    )
    if project is not None:
        obligations = obligations.filter(project=project)
    rows = []
    for obligation in obligations.select_related("control_account_mapping").order_by(
        "pk"
    ):
        settled, written_off = _amounts_as_of(obligation, as_of_date)
        reversed_amount = _source_reversed_amount_as_of(obligation, as_of_date)
        outstanding = (
            obligation.original_amount - settled - written_off - reversed_amount
        )
        state = (
            "reversed"
            if reversed_amount
            else "written_off"
            if written_off and not outstanding
            else "settled"
            if settled and not outstanding
            else "open"
        )
        issues = []
        if (
            not obligation.control_account_id
            or not obligation.control_account_mapping_id
        ):
            issues.append("CONTROL_MAPPING_NOT_APPROVED")
        current = (
            SubledgerReconciliationAccountSlice.objects.filter(
                organization=organization,
                direction=obligation.direction,
                as_of_date=as_of_date,
                control_account_id=obligation.control_account_id,
                invalidation__isnull=True,
            )
            .order_by("-grain_revision")
            .first()
            if obligation.control_account_id
            else None
        )
        retained = (
            current.obligation_evidence.filter(
                organization=organization, obligation=obligation
            ).first()
            if current
            else None
        )
        journal_rows = []
        gl = None
        if retained is None:
            issues.append("CURRENT_NATIVE_EVIDENCE_MISSING")
        else:
            if (
                retained.source_kind != obligation.source_kind
                or retained.source_uuid != obligation.source_uuid
                or retained.source_version != obligation.source_version
                or retained.source_hash != obligation.source_hash
                or retained.outstanding_amount != outstanding
            ):
                issues.append("CURRENT_NATIVE_EVIDENCE_STALE")
            for item in current.journal_line_evidence.filter(
                organization=organization, obligation=obligation
            ).select_related("journal", "journal_line"):
                journal_rows.append(
                    {
                        "journal": str(item.journal_id),
                        "line": str(item.journal_line_id),
                        "source": str(item.journal_source_uuid),
                        "version": item.journal_source_version,
                        "debit": str(item.debit),
                        "credit": str(item.credit),
                    }
                )
                if (
                    item.journal.status != "posted"
                    or item.journal.accounting_date > as_of_date
                    or item.journal.source_uuid != item.journal_source_uuid
                    or item.journal.source_version != item.journal_source_version
                    or item.journal_line.account_id != obligation.control_account_id
                    or item.journal_line.debit != item.debit
                    or item.journal_line.credit != item.credit
                ):
                    issues.append("UNVERIFIED_JOURNAL_EVIDENCE")
                    continue
                value = (
                    item.debit - item.credit
                    if obligation.direction == "receivable"
                    else item.credit - item.debit
                )
                gl = (gl or Decimal(0)) + value
            if gl is None:
                issues.append("POSTED_CONTROL_ACCOUNT_EVIDENCE_MISSING")
            elif gl != outstanding:
                issues.append("CONTROL_ACCOUNT_DIFFERENCE")
        allocations = [
            {
                "id": str(x.pk),
                "movement": str(x.treasury_movement_id),
                "amount": str(x.amount),
                "effective_date": x.effective_date.isoformat(),
                "reversal": str(x.reversal.pk) if hasattr(x, "reversal") else None,
            }
            for x in obligation.settlement_allocations.filter(
                effective_date__lte=as_of_date
            ).select_related("reversal")
        ]
        row = {
            "obligation": str(obligation.pk),
            "project": str(obligation.project_id) if obligation.project_id else None,
            "source_kind": obligation.source_kind,
            "source": str(obligation.source_uuid),
            "source_version": obligation.source_version,
            "source_hash": obligation.source_hash,
            "direction": obligation.direction,
            "state": state,
            "original": str(obligation.original_amount),
            "settled": str(settled),
            "written_off": str(written_off),
            "reversed": str(reversed_amount),
            "outstanding": str(outstanding),
            "gl": str(gl) if gl is not None else None,
            "control_account": str(obligation.control_account_id)
            if obligation.control_account_id
            else None,
            "mapping": str(obligation.control_account_mapping_id)
            if obligation.control_account_mapping_id
            else None,
            "native_slice": str(current.pk) if current else None,
            "native_revision": current.grain_revision if current else None,
            "native_evidence_hash": current.evidence_hash if current else None,
            "journal_evidence": journal_rows,
            "settlement_evidence": allocations,
            "issues": sorted(set(issues)),
        }
        # Economic-source fingerprint is independent of repeated native snapshots.
        row["economic_hash"] = _canonical_hash(
            {
                k: row[k]
                for k in (
                    "obligation",
                    "source",
                    "source_version",
                    "source_hash",
                    "original",
                    "settled",
                    "written_off",
                    "reversed",
                    "outstanding",
                )
            }
        )
        rows.append(row)
    return {
        "organization": str(organization.pk),
        "project": str(project.pk) if project else None,
        "as_of_date": as_of_date.isoformat(),
        "observed_at": timezone.now().isoformat(),
        "source_watermark": _canonical_hash(rows),
        "rows": rows,
        "outstanding_total": str(
            sum((Decimal(x["outstanding"]) for x in rows), Decimal(0))
        ),
        "projection_only": True,
    }
