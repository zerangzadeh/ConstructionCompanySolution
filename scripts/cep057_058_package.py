"""Validate the immutable Human-supplied synthetic Development fixture package.

This is data tooling, not a grant of runtime or Production authority.
"""

import csv
import hashlib
import json
from decimal import Decimal as D
from pathlib import Path

AUTHORITY = "DEV-SYNTHETIC-DATA-AUTH-20261020-V2"
PACKAGE = "BONIRA-CEP057-058-SYNTHETIC-DEV-CLOSURE-V2"
MANIFEST_SHA256 = "8afd738bb2ca2b92a20f1b8b7c7a8d4cba0015ede1e135da26c6a03a93b2f8f3"
SCHEMAS = {
    "CEP057_LEAVE_OPENING_SYNTHETIC.csv": "source_record_id,source_version,source_status,included_in_opening,source_employee_key,evidence_reference,leave_category,signed_quantity,unit,policy_version_reference,as_of,cutover_on,coverage_definition,overlap_treatment,exception_reference",
    "CEP057_RECONCILIATION_CONTROL_SYNTHETIC.csv": "control_group,policy_version,leave_category,unit,source_row_count,included_row_count,signed_quantity_total,excluded_row_count,exception_row_count,control_report_reference,approval_reference,notes",
    "CEP058_PAYROLL_YTD_SOURCE_SYNTHETIC.csv": "source_record_id,source_version,source_status,included_in_opening,source_employee_key,source_period,result_reference,line_reference,external_component_key,signed_amount,currency,correction_reference,reversal_reference,replacement_reference,evidence_reference,source_digest",
    "CEP058_COMPONENT_CROSSWALK_SYNTHETIC.csv": "external_component_key,source_component_description,target_component_code,target_resolution_action,approved_operational_kind,source_sign_convention,source_document_reference,ambiguity_status,human_ruling_reference,notes",
    "CEP058_RECONCILIATION_CONTROL_SYNTHETIC.csv": "control_group,payroll_year_code,component_key,operational_kind,currency,source_row_count,eligible_source_count,signed_amount_total,superseded_count,reversed_count,excluded_count,exception_count,control_report_reference,approval_reference,notes",
    "SHARED_IDENTITY_MAPPING.csv": "source_employee_key,mapping_rule,target_work_relationship,target_employee,target_person,effective_from,effective_to,mapping_authority,notes",
}


def read_csv(root: Path, name: str) -> list[dict]:
    with (root / "data" / name).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != SCHEMAS[name].split(","):
            raise ValueError(f"CSV columns differ from the approved schema: {name}")
        rows = list(reader)
        if not rows or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f"Invalid CSV schema: {name}")
        if any(None in row or None in row.values() for row in rows):
            raise ValueError(f"Ragged CSV: {name}")
        return rows


def validate(root: Path) -> dict:
    raw = (root / "MANIFEST.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError("The supplied package manifest changed.")
    manifest = json.loads(raw)
    assert manifest["package_id"] == PACKAGE
    assert manifest["decision_id"] == AUTHORITY
    assert manifest["synthetic"] is True and manifest["production_use"] is False
    for name, entry in manifest["files"].items():
        path = (root / name).resolve()
        assert path.is_relative_to(root.resolve())
        content = path.read_bytes()
        assert len(content) == entry["bytes"], name
        assert hashlib.sha256(content).hexdigest() == entry["sha256"], name
    expected = json.loads((root / "VALIDATION_EXPECTATIONS.json").read_text())
    assert expected["real_authoritative_history_population"] == {
        "CEP-057": 0,
        "CEP-058": 0,
    }
    identities = read_csv(root, "SHARED_IDENTITY_MAPPING.csv")
    keys = {f"DEV-HR-{i:03}" for i in range(1, 11)}
    assert {r["source_employee_key"] for r in identities} == keys
    leave = read_csv(root, "CEP057_LEAVE_OPENING_SYNTHETIC.csv")
    pay = read_csv(root, "CEP058_PAYROLL_YTD_SOURCE_SYNTHETIC.csv")
    crosswalk = read_csv(root, "CEP058_COMPONENT_CROSSWALK_SYNTHETIC.csv")
    kinds = {
        r["external_component_key"]: r["approved_operational_kind"] for r in crosswalk
    }
    assert len(kinds) == len(crosswalk) == 8
    assert set(kinds.values()) == {
        "EARNING",
        "ALLOWANCE",
        "DEDUCTION",
        "REIMBURSEMENT",
        "EMPLOYER",
    }
    for rows in (leave, pay):
        assert len({r["source_record_id"] for r in rows}) == len(rows)
        assert {r["source_employee_key"] for r in rows} == keys
        assert all(r["evidence_reference"].startswith("DEV-") for r in rows)
    assert len(leave) == 17 and sum(D(r["signed_quantity"]) for r in leave) == D(
        "74.50"
    )
    for r in leave:
        assert r["included_in_opening"] == "YES" and r["source_status"] == "APPROVED"
        assert (
            r["policy_version_reference"],
            r["as_of"],
            r["cutover_on"],
            r["unit"],
        ) == ("DEV-LEAVE-POLICY-v2", "2026-09-30", "2026-10-01", "days")
        assert D(r["signed_quantity"]) % D("0.25") == 0
    leave_controls = read_csv(root, "CEP057_RECONCILIATION_CONTROL_SYNTHETIC.csv")
    for c in leave_controls:
        rows = [r for r in leave if c["leave_category"] in ("ALL", r["leave_category"])]
        assert len(rows) == int(c["source_row_count"]) == int(c["included_row_count"])
        assert sum(D(r["signed_quantity"]) for r in rows) == D(
            c["signed_quantity_total"]
        )
        assert c["policy_version"] == "DEV-LEAVE-POLICY-v2" and c["unit"] == "days"
        assert int(c["exception_row_count"]) == int(c["excluded_row_count"]) == 0
        assert c["approval_reference"] == AUTHORITY
    included = [r for r in pay if r["included_in_opening"] == "YES"]
    assert len(pay) == 81 and len(included) == 80
    assert sum(D(r["signed_amount"]) for r in included) == D(56574280000)
    by_id = {r["source_record_id"]: r for r in pay}
    for r in pay:
        assert r["currency"] == "IRR" and r["source_period"] == "2026-YTD-09"
        assert r["source_version"] == "DEV-PAYROLL-EXPORT-v2"
        assert len(r["source_digest"]) == 64 and int(r["source_digest"], 16) >= 0
        assert (D(r["signed_amount"]) < 0) == (
            kinds[r["external_component_key"]] == "DEDUCTION"
        )
        if r["source_status"] == "SUPERSEDED":
            replacement = by_id[r["replacement_reference"]]
            assert r["included_in_opening"] == "NO"
            assert replacement["correction_reference"] == r["source_record_id"]
            assert replacement["included_in_opening"] == "YES"
            for field in (
                "source_employee_key",
                "external_component_key",
                "source_period",
            ):
                assert replacement[field] == r[field]
        else:
            assert (
                r["source_status"] == "FINALIZED" and r["included_in_opening"] == "YES"
            )
        assert not r["reversal_reference"]
    controls = read_csv(root, "CEP058_RECONCILIATION_CONTROL_SYNTHETIC.csv")
    for c in controls:
        rows = [
            r
            for r in pay
            if c["component_key"] in ("ALL", r["external_component_key"])
            and c["operational_kind"] in ("ALL", kinds[r["external_component_key"]])
        ]
        eligible = [r for r in rows if r["included_in_opening"] == "YES"]
        assert len(rows) == int(c["source_row_count"])
        assert len(eligible) == int(c["eligible_source_count"])
        assert sum(D(r["signed_amount"]) for r in eligible) == D(
            c["signed_amount_total"]
        )
        assert sum(r["source_status"] == "SUPERSEDED" for r in rows) == int(
            c["superseded_count"]
        )
        assert (
            int(c["reversed_count"])
            == int(c["excluded_count"])
            == int(c["exception_count"])
            == 0
        )
        assert c["currency"] == "IRR" and c["payroll_year_code"] == "DEV-PY-2026-A"
        assert c["approval_reference"] == AUTHORITY
    return {
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "files_verified": len(manifest["files"]),
        "identities": identities,
        "leave": leave,
        "leave_controls": leave_controls,
        "payroll": pay,
        "crosswalk": crosswalk,
        "payroll_controls": controls,
        "expectations": expected,
        "synthetic_only": True,
        "repairs": [],
    }
