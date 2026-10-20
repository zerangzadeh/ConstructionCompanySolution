"""Reproducible Development-only execution/recovery evidence for the supplied package."""

import json
import os
import sys
from collections import defaultdict
from contextlib import contextmanager
from datetime import date
from decimal import Decimal as D
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.organizations.models import Organization
from apps.workforce.leave_models import LeaveBalanceEntry, LeavePolicyVersion
from apps.workforce.leave_opening_import import (
    AUTHORITY,
    import_leave_opening,
    require_development,
    reverse_leave_opening,
)
from apps.workforce.leave_opening_preparation import (
    OpeningBalanceDataset,
    OpeningBalanceRow,
    OpeningBalanceTotal,
)
from apps.workforce.leave_services import record_policy
from scripts.cep057_058_package import validate

ROOT = Path("docs/governance/cep/supporting/synthetic-dev-v2")
EVIDENCE = Path("docs/governance/cep/evidence")


def context():
    require_development(AUTHORITY)
    package = validate(ROOT)
    grounded = json.loads(
        (EVIDENCE / "CEP-057_058_SYNTHETIC_GROUNDING.json").read_text()
    )
    return package, {
        r["source_employee_key"]: r for r in grounded["identity_resolution"]
    }


def actor_for(org):
    # Resolve the already-governed shared owner, never add a grant or use superuser bypass.
    return User.objects.get(
        pk="26c1e6d4-7035-4c70-a4d7-c120ba7507a5",
        organization_memberships__organization=org,
    )


@contextmanager
def development_operator(permissions):
    """Bounded fixture authorization via the existing Platform Admin catalog service.

    Hold the role lock and restore the exact permission set BEFORE committing.
    Other connections never see an added grant. Both changes remain audited.
    No default grant, membership, role assignment or security rule is changed.
    """
    from apps.organizations.access_services import update_organization_role
    from apps.organizations.models import OrganizationRole

    require_development(AUTHORITY)
    admin = User.objects.get(pk="26c1e6d4-7035-4c70-a4d7-c120ba7507a5")
    with transaction.atomic():
        role = OrganizationRole.objects.select_for_update().get(code="tenant_owner")
        original = set(role.permissions.values_list("code", flat=True))
        args = {
            "actor": admin,
            "role_id": role.pk,
            "name": role.name,
            "description": role.description,
        }
        update_organization_role(
            **args,
            permissions=original | set(permissions),
            reason=AUTHORITY
            + "; transaction-local synthetic fixture operator; restore before commit",
        )
        receipt = {
            "service": "apps.organizations.access_services.update_organization_role",
            "role_id": str(role.pk),
            "temporary_fixture_permissions": sorted(set(permissions) - original),
            "persistent_grant_changes": 0,
            "restored_exactly": False,
        }
        yield receipt
        update_organization_role(
            **args,
            permissions=original,
            reason=AUTHORITY + "; restore exact original permissions before commit",
        )
        assert set(role.permissions.values_list("code", flat=True)) == original
        receipt["restored_exactly"] = True


def leave():
    package, mapping = context()
    groups = defaultdict(list)
    for row in package["leave"]:
        groups[mapping[row["source_employee_key"]]["organization_id"]].append(row)
    proof = {
        "authority": AUTHORITY,
        "synthetic_only": True,
        "real_history_applicability": "N/A — ZERO AUTHORITATIVE DEVELOPMENT HISTORY",
        "manifest_sha256": package["manifest_sha256"],
        "tenants": [],
        "repairs": [],
    }
    with development_operator(
        ["leave_policies.manage", "leave_balances.manage", "leave_balances.view"]
    ) as operator_receipt:
        proof["operator_authorization"] = operator_receipt
        for org_id, rows in sorted(groups.items()):
            org = Organization.objects.get(pk=org_id)
            actor = actor_for(org)
            policies = {}
            for category, floor, cap, expiry in (
                ("ANNUAL_LEAVE", "-2", "9", "following synthetic policy year end"),
                ("TIME_OFF_IN_LIEU", "0", "3", "90 days after synthetic earning event"),
            ):
                args = {
                    "organization": org,
                    "actor": actor,
                    "category_code": category,
                    "effective_from": date(2026, 1, 1),
                    "effective_to": date(2027, 1, 1),
                    "unit": "days",
                    "accrual_preset": "POLICY_DEFINED",
                    "entitlement_rule_reference": "DEV-LEAVE-POLICY-v2; rounding 0.25 day",
                    "accrual_rule_reference": "DEV-LEAVE-POLICY-v2",
                    "negative_balance_threshold": D(floor),
                    "carry_forward_limit": D(cap),
                    "expiry_rule_reference": "DEV-LEAVE-POLICY-v2: " + expiry,
                    "evidence_reference": AUTHORITY,
                    "reason": "Synthetic Development-only policy fixture; no statutory meaning",
                }
                policy = LeavePolicyVersion.objects.filter(
                    organization=org, category_code=category
                ).first()
                if policy:
                    assert all(getattr(policy, k) == v for k, v in args.items())
                else:
                    policy = record_policy(**args)
                policies[category] = policy
            typed = tuple(
                OpeningBalanceRow(
                    r["source_record_id"],
                    r["source_version"],
                    r["evidence_reference"],
                    UUID(mapping[r["source_employee_key"]]["employee_id"]),
                    UUID(mapping[r["source_employee_key"]]["relationship_id"]),
                    policies[r["leave_category"]].pk,
                    "days",
                    D(r["signed_quantity"]),
                )
                for r in rows
            )
            totals = defaultdict(D)
            for r in typed:
                totals[r.policy_id] += r.quantity
            ds = OpeningBalanceDataset(
                "DEV-LEAVE-EXPORT-v2",
                "2",
                AUTHORITY,
                date(2026, 9, 30),
                date(2026, 10, 1),
                len(typed),
                tuple(
                    OpeningBalanceTotal(k, "days", v) for k, v in sorted(totals.items())
                ),
                typed,
            )
            initial_count = LeaveBalanceEntry.objects.filter(organization=org).count()
            # Actual insert and rollback, then recover by rerunning the same source keys.
            with transaction.atomic():
                import_leave_opening(organization=org, actor=actor, dataset=ds)
                transaction.set_rollback(True)
            assert (
                LeaveBalanceEntry.objects.filter(organization=org).count()
                == initial_count
            )
            applied = import_leave_opening(organization=org, actor=actor, dataset=ds)
            repeated = import_leave_opening(organization=org, actor=actor, dataset=ds)
            assert (
                applied["mapping"] == repeated["mapping"] and repeated["created"] == 0
            )
            originals = list(
                LeaveBalanceEntry.objects.filter(
                    pk__in=[r["target_id"] for r in applied["mapping"]]
                )
            )
            with transaction.atomic():
                inverses = reverse_leave_opening(
                    organization=org, actor=actor, entries=originals
                )
                assert sum((r.quantity for r in originals + list(inverses)), D(0)) == 0
                transaction.set_rollback(True)
            assert not LeaveBalanceEntry.objects.filter(reverses__in=originals).exists()
            from dataclasses import replace

            try:
                import_leave_opening(
                    organization=org,
                    actor=actor,
                    dataset=replace(
                        ds,
                        expected_totals=(
                            replace(ds.expected_totals[0], quantity=D(999999)),
                        ),
                    ),
                )
            except ValidationError as exc:
                exception = exc.messages
            else:
                raise AssertionError("Bad controls unexpectedly accepted")
            proof["tenants"].append(
                {
                    "organization_id": org_id,
                    "policy_ids": {k: str(v.pk) for k, v in policies.items()},
                    "policy_native_version": 1,
                    "source_document_version": 2,
                    "result": applied,
                    "retry_created": repeated["created"],
                    "transaction_rollback_recovery": "PASS",
                    "compensating_rollback_recovery": "PASS",
                    "exception_test": exception,
                }
            )
        proof["target_count"] = sum(
            len(t["result"]["mapping"]) for t in proof["tenants"]
        )
        proof["target_total_days"] = str(
            sum(
                D(r["quantity"])
                for t in proof["tenants"]
                for r in t["result"]["mapping"]
            )
        )
        assert proof["target_count"] == 17 and D(proof["target_total_days"]) == D(
            "74.50"
        )
    (EVIDENCE / "CEP-057_SYNTHETIC_EXECUTION.json").write_text(
        json.dumps(proof, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "CEP-057": "EXECUTED",
                "targets": proof["target_count"],
                "total_days": proof["target_total_days"],
            }
        )
    )


def payroll():
    from apps.payroll.cumulative_services import (
        approve_payroll_year,
        create_payroll_year_draft,
        cumulative_balances,
    )
    from apps.payroll.models import (
        PayrollComponent,
        PayrollCumulativeState,
        PayrollRun,
        PayrollYearInterval,
    )
    from apps.payroll.opening_import import (
        import_payroll_opening,
        reverse_payroll_opening,
    )
    from apps.payroll.services import create_component
    from apps.workforce.models import Employee

    package, mapping = context()
    groups = defaultdict(list)
    for row in package["payroll"]:
        groups[mapping[row["source_employee_key"]]["organization_id"]].append(row)
    proof = {
        "authority": AUTHORITY,
        "synthetic_only": True,
        "real_history_applicability": "N/A — ZERO AUTHORITATIVE DEVELOPMENT HISTORY",
        "manifest_sha256": package["manifest_sha256"],
        "tenants": [],
        "repairs": [],
    }
    before_runs = PayrollRun.objects.count()
    with development_operator(
        [
            "payroll_configuration.manage",
            "payroll.finalize",
            "payroll.adjust",
            "payroll_results.view",
        ]
    ) as operator_receipt:
        proof["operator_authorization"] = operator_receipt
        for org_id, rows in sorted(groups.items()):
            org = Organization.objects.get(pk=org_id)
            actor = actor_for(org)
            components = {}
            for cross in package["crosswalk"]:
                kind = cross["approved_operational_kind"].lower()
                component = PayrollComponent.objects.filter(
                    organization=org, code=cross["target_component_code"]
                ).first()
                if component is None:
                    component = create_component(
                        organization=org,
                        actor=actor,
                        code=cross["target_component_code"],
                        name=cross["source_component_description"],
                        kind=kind,
                        net_effect="subtract"
                        if kind == "deduction"
                        else ("none" if kind == "employer" else "add"),
                        description=AUTHORITY
                        + "; synthetic Development only; no statutory meaning",
                    )
                assert component.kind == kind and not component.is_statutory_reserved
                components[cross["external_component_key"]] = component.pk
            year = PayrollYearInterval.objects.filter(
                organization=org, code="DEV-PY-2026-A", version=2
            ).first()
            if year is None:
                for version in (1, 2):
                    year = create_payroll_year_draft(
                        organization=org,
                        actor=actor,
                        code="DEV-PY-2026-A",
                        starts_on=date(2026, 1, 1),
                        ends_on=date(2026, 12, 31),
                        reason=AUTHORITY
                        + "; synthetic binding revision "
                        + str(version)
                        + "; no statutory meaning",
                    )
                    assert year.version == version
                year = approve_payroll_year(organization=org, actor=actor, year=year)
            assert year.version == 2 and year.status == "approved"
            totals = defaultdict(D)
            for r in rows:
                if r["included_in_opening"] == "YES":
                    totals[r["external_component_key"]] += D(r["signed_amount"])
            args = {
                "organization": org,
                "actor": actor,
                "year": year,
                "rows": rows,
                "identities": mapping,
                "components": components,
                "totals": dict(totals),
                "authority": AUTHORITY,
            }
            before_count = PayrollCumulativeState.objects.filter(
                organization=org
            ).count()
            with transaction.atomic():
                import_payroll_opening(**args)
                transaction.set_rollback(True)
            assert (
                PayrollCumulativeState.objects.filter(organization=org).count()
                == before_count
            )
            applied = import_payroll_opening(**args)
            repeat = import_payroll_opening(**args)
            assert applied["mapping"] == repeat["mapping"] and repeat["created"] == 0
            originals = list(
                PayrollCumulativeState.objects.filter(
                    pk__in=[r["target_id"] for r in applied["mapping"]]
                )
            )
            with transaction.atomic():
                inverses = reverse_payroll_opening(
                    organization=org, actor=actor, entries=originals
                )
                assert sum((r.delta for r in originals + list(inverses)), D(0)) == 0
                assert all(r.balance == 0 for r in inverses)
                transaction.set_rollback(True)
            assert PayrollCumulativeState.objects.filter(
                organization=org
            ).count() == len(originals)
            views = []
            for employee_id in {r.employee_id for r in originals}:
                balances = cumulative_balances(
                    organization=org,
                    actor=actor,
                    year=year,
                    employee=Employee.objects.get(pk=employee_id, organization=org),
                )
                assert len(balances) == 8
                views.extend(str(r.pk) for r in balances)
            assert set(views) == {str(r.pk) for r in originals}
            try:
                import_payroll_opening(**(args | {"totals": {}}))
            except ValidationError as exc:
                exception = exc.messages
            else:
                raise AssertionError("Bad controls accepted")
            proof["tenants"].append(
                {
                    "organization_id": org_id,
                    "year_id": str(year.pk),
                    "year_version": year.version,
                    "components": {k: str(v) for k, v in components.items()},
                    "result": applied,
                    "retry_created": repeat["created"],
                    "transaction_rollback_recovery": "PASS",
                    "compensating_rollback_recovery": "PASS",
                    "canonical_cumulative_projection": "PASS",
                    "exception_test": exception,
                }
            )
        proof["source_count"] = sum(
            t["result"]["source_count"] for t in proof["tenants"]
        )
        proof["target_count"] = sum(
            t["result"]["included_count"] for t in proof["tenants"]
        )
        proof["target_total_irr"] = str(
            sum(
                D(r["amount"]) for t in proof["tenants"] for r in t["result"]["mapping"]
            )
        )
        assert (
            proof["source_count"] == 81
            and proof["target_count"] == 80
            and D(proof["target_total_irr"]) == D(56574280000)
        )
        assert PayrollRun.objects.count() == before_runs == 0
        proof["fabricated_payroll_runs"] = 0
    (EVIDENCE / "CEP-058_SYNTHETIC_EXECUTION.json").write_text(
        json.dumps(proof, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "CEP-058": "EXECUTED",
                "sources": 81,
                "targets": 80,
                "total_irr": proof["target_total_irr"],
            }
        )
    )


if __name__ == "__main__":
    if sys.argv[1:] == ["057"]:
        leave()
    elif sys.argv[1:] == ["058"]:
        payroll()
    else:
        raise SystemExit("Expected 057 or 058")
