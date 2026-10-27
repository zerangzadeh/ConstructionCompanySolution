"""Verify measured package evidence, then update only its governed closeout."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
RUNTIME = OUT / "runtime"
AUTHORITY = "docs/governance/cep/supporting/BONIRA-PE-NP-01_HUMAN_APPROVAL_20261027.md"
PREFIX = "docs/governance/cep/evidence/SHARED_TARGET_APPROVED_20261027"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def main(phase):
    cep = "CEP-" + phase
    assert phase in {"070", "074", "075"}
    entry = load(OUT / "ENTRY.json")
    assert sha(ROOT / AUTHORITY) == entry["authority_sha256"]
    assert (
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        == entry["head"]
    )
    freeze = load(OUT / "SOURCE_FREEZE.json")
    assert all(sha(ROOT / path) == expected for path, expected in freeze.items())
    prompt = ROOT / "docs/governance/cep/PROMPTS" / (cep + "_EXECUTION_PROMPT.md")
    assert sha(prompt) == entry["canonical"][cep]["sha256"]
    result = load(RUNTIME / (phase + "_RESULT.json"))
    assert result["execution"] == "COMPLETE" and len(result["ac"]) == 6
    assert all(
        status == "PASS_APPROVED_NONPRODUCTION_TARGET"
        for status in result["ac"].values()
    )
    assert result["dod"] == "MET_APPROVED_NONPRODUCTION_SCOPE"
    if phase in {"070", "074"}:
        identity = load(RUNTIME / (phase + "_IDENTITY.json"))
        assert identity["python"] == "3.11.17" and identity["pq_impl"] == "python"
        assert identity["django"] == "5.2.17" and identity["psycopg"] == "3.3.5"
        assert 'VERSION_ID="12"' in identity["os_release"]
        assert identity["schema"]["nodes"] == 437 and identity["role_not_superuser"]
        assert (
            identity["settings"] == "config.settings.production"
            and not identity["dotenv_loaded"]
        )
        assert identity["source_files"] == len(freeze)
        assert "PostgreSQL 18.6" in identity["postgresql"]
        restoration = result["restore"]
        assert restoration["result"] == "PASS"
        assert restoration["rpo_seconds"] <= 900 and restoration["rto_seconds"] <= 3600
        assert 0 < result["capture_interval_seconds"] <= 900
        source = load(RUNTIME / (phase + "_SOURCE_FINGERPRINT.json"))
        target = load(RUNTIME / (phase + "_RESTORED_FINGERPRINT.json"))
        after = load(RUNTIME / (phase + "_SOURCE_AFTER_FINGERPRINT.json"))
        assert source == target == after
        assert len(target["tables"]) == restoration["tables"] == 525
        assert target["constraints_count"] == restoration["constraints"] == 9507
        validation = load(RUNTIME / (phase + "_VALIDATION.json"))
        assert validation["result"] == "PASS" and all(
            c["status"] == "PASS" for c in validation["checks"]
        )
        assert sum("cross-tenant read" in c["check"] for c in validation["checks"]) == 4
        assert (
            sum(
                "cross-tenant version write" in c["check"] for c in validation["checks"]
            )
            == 2
        )
        capture = load(RUNTIME / (phase + "_CAPTURE.json"))
        assert set(capture["capture"]["classes"]) == {
            "transactional_database",
            "document_media",
            "configuration_metadata",
            "audit_operational",
        }
        assert capture["capture"]["source_revision"] == entry["head"]
        details = (
            f"{restoration['tables']} tables / {restoration['rows']:,} complete rows / "
            f"{restoration['constraints']:,} constraints / {restoration['sequences']} sequences; "
            f"RPO {restoration['rpo_seconds']}s, RTO {restoration['rto_seconds']:.3f}s; "
            f"actual capture-start interval {result['capture_interval_seconds']:.3f}s"
        )
    else:
        assert len(result["steps"]) == 7
        for name in ["PREVIOUS", "CANDIDATE", "ROLLBACK", "RETURN_CANDIDATE"]:
            http = load(RUNTIME / ("075_" + name + "_HTTP.json"))
            assert http["result"] == "PASS" and all(
                c["result"] == "PASS" for c in http["checks"]
            )
        assert load(RUNTIME / "075_BEFORE_HISTORY.json") == load(
            RUNTIME / "075_AFTER_HISTORY.json"
        )
        assert load(RUNTIME / "previous_STATIC.json") == load(
            RUNTIME / "candidate_STATIC.json"
        )
        details = "Seven actual deployment/failure/rollback/return/preservation steps; four HTTPS/security scenarios, including real synthetic login and cross-tenant private-download denial; 437 migration-history nodes unchanged"

    registry_path = ROOT / "CEP_EXECUTION_REGISTRY.yaml"
    raw = registry_path.read_text(encoding="utf-8")
    before = yaml.safe_load(raw)
    if phase == "074":
        assert before["ceps"]["CEP-070"]["execution"]["status"] == "COMPLETE"
    if phase == "075":
        assert before["ceps"]["CEP-071"]["execution"]["status"] == "COMPLETE"
    assert before["ceps"][cep]["execution"]["status"] != "COMPLETE", (
        "Never reclose a completed CEP"
    )
    now = datetime.now(UTC).isoformat()
    evidence = PREFIX + "/runtime/" + phase + "_RESULT.json"

    def replace(pattern, change, indent=True):
        nonlocal raw
        match = re.search(pattern, raw)
        assert match
        content = yaml.safe_load(match.group())
        change(content)
        rendered = yaml.safe_dump(
            content, allow_unicode=True, sort_keys=False, width=140
        )
        if indent:
            rendered = "".join(
                "  " + line if line.strip() else line
                for line in rendered.splitlines(keepends=True)
            )
        raw = raw[: match.start()] + rendered + raw[match.end() :]

    def update_cep(doc):
        item = doc[cep]
        item["dependency_status"] = "SATISFIED_APPROVED_REFERENCE_SCOPE"
        item["eligibility_status"] = (
            "EXECUTED_APPROVED_PRODUCTION_EQUIVALENT_NONPRODUCTION"
        )
        item["execution"] = {
            "status": "COMPLETE",
            "lifecycle": "EXECUTION_COMPLETE_APPROVED_NONPRODUCTION_REFERENCE",
            "advisor_review": "NOT_REQUIRED_CURRENT_GOVERNANCE",
        }
        item["acceptance"] = {
            "passed": 6,
            "total": 6,
            "status": "PASS_APPROVED_PRODUCTION_EQUIVALENT_NONPRODUCTION_SCOPE",
        }
        item["dod"] = "MET_APPROVED_NONPRODUCTION_SCOPE"
        item["blockers"] = []
        item["remaining_utv"] = [
            "Actual Production installation/policy/storage/key custody/activation/final certification and Human Sign-off not executed",
            "Future elapsed retention/restore drill/continuous operation not inferred;no Production SLA/capacity/HA claim",
        ]
        item["completion_report"] = {
            "path": "docs/governance/cep/reports/" + cep + "_COMPLETION_REPORT.md",
            "evidence_presence": "VERIFIED_FRESH_APPROVED_LINUX_REFERENCE_RUNTIME",
        }
        item["last_execution"] = {
            "branch": "main",
            "sha": entry["head"],
            "at": now,
            "profile": "BONIRA-PE-NP-01",
        }
        item["git"]["current_execution_committed"] = False
        item["git"]["current_session_changes_committed"] = False
        item["git"]["current_execution_integrated"] = False
        item["history"].append(
            {
                "date": "2026-10-27",
                "status": "COMPLETE",
                "reason": details
                + "; canonical implementation AC6/6 and scoped DoD MET on approved Linux reference. No final Production Certification/Human Sign-off/Git write.",
                "evidence": evidence,
            }
        )
        item["shared_target_profile"].update(
            {
                "reference_design": "APPROVED_BOUNDED_NONPRODUCTION",
                "candidate_controls": "QUALIFIED_EXECUTED_APPROVED_LINUX_REFERENCE",
                "evidence": evidence,
                "proposed_linux_runtime": "PROVISIONED_AND_EXECUTED",
            }
        )
        item["frontier_review"].update(
            {
                "at": now,
                "evidence": evidence,
                "result": "COMPLETE_NO_IN_SCOPE_BLOCKER",
                "blocker_classes": [],
                "smallest_remaining_prerequisite": "NONE_FOR_APPROVED_NONPRODUCTION_SCOPE",
            }
        )

    replace(r"(?ms)^  " + re.escape(cep) + r":\n.*?(?=^  CEP-|^[a-z_]+:)", update_cep)

    if phase == "070":

        def enable074(doc):
            item = doc["CEP-074"]
            item["dependency_status"] = (
                "SATISFIED_CEP070_APPROVED_LINUX_REFERENCE_COMPLETE"
            )
            item["eligibility_status"] = (
                "ELIGIBLE_APPROVED_REFERENCE_FRESH_RESTORE_VERIFICATION"
            )
            item["blockers"] = []
            item["history"].append(
                {
                    "date": "2026-10-27",
                    "status": "BLOCKER_RESOLVED",
                    "reason": "Mandatory CEP070 approved Linux reference outcome closed AC6/6/scoped DoD;EXT0020 policy/owner approved and target qualified. Fresh074 execution now eligible.",
                    "evidence": evidence,
                }
            )

        replace(r"(?ms)^  CEP-074:\n.*?(?=^  CEP-|^[a-z_]+:)", enable074)

    for gate in ["GATE-08", "GATE-11"]:

        def update_gate(doc, gate=gate):
            item = doc[gate]
            if phase in {"074", "075"}:
                imb = "IMB-0104" if phase == "074" else "IMB-0105"
                item["required_imb_status"][imb] = (
                    "PASS_APPROVED_LINUX_NONPRODUCTION_REFERENCE"
                )
                item.setdefault("contributor_evidence", {})[cep] = evidence
            if phase == "070" and gate == "GATE-11":
                item["required_imb_status"]["IMB-0098"] = (
                    "PASS_APPROVED_LINUX_NONPRODUCTION_CONTROL_PRODUCTION_NOT_CERTIFIED"
                )
            if gate == "GATE-08" and phase == "075":
                required = [
                    "IMB-0103",
                    "IMB-0104",
                    "IMB-0105",
                    "IMB-0106",
                    "IMB-0107",
                    "IMB-0108",
                    "IMB-0109",
                ]
                assert all(
                    item["required_imb_status"][code].startswith("PASS")
                    for code in required
                )
                for path in item["contributor_evidence"].values():
                    assert (ROOT / path).is_file()
                item["status"] = "PASS"
                item["source"] = (
                    "OBJECTIVE_EXECUTED_NONPRODUCTION_VERIFICATION_EVIDENCE_SET"
                )
                item["scope"] = (
                    "APPROVED_NONPRODUCTION_EVIDENCE_SET_EACH_CONTRIBUTOR_RETAINS_ITS_ACTUAL_ENVIRONMENT_AND_LIMITS"
                )
                item["note"] = (
                    "All seven canonical verification items have executed accepted non-production evidence. Fresh074/075 use one approved Linux reference;073/076/077/078 accepted evidence retained without rerun or retargeting/capacity inference. No Production Certification/Human Sign-off."
                )
            else:
                item["status"] = "NOT_PASSED"
                item["note"] = (
                    "070/074/075 scoped Linux contributions advance only from actual executed evidence. "
                    "Remaining verification contribution pending;no global readiness inference."
                    if gate == "GATE-08"
                    else "Approved Linux recovery/deployment contributions retained. CEP069/statutory and required actual Production external evidence/final certification remain unavailable/outside authority;no Production PASS."
                )
            item["evidence"] = evidence
            item["history"].append(
                {
                    "date": "2026-10-27",
                    "status": item["status"],
                    "reason": cep
                    + " AC6/6/scoped DoD qualified on approved Linux reference;other contributor scopes preserved;no Production/Human authority inferred.",
                    "evidence": evidence,
                }
            )

        replace(r"(?ms)^  " + gate + r":\n.*?(?=^  GATE-|^[a-z_]+:)", update_gate)

    def update_frontier(doc):
        frontier = doc["execution_frontier"]
        next_cep = (
            "CEP-074" if phase == "070" else "CEP-075" if phase == "074" else None
        )
        frontier["verified_build_eligible_unblocked"] = []
        frontier["verified_verification_eligible_unblocked"] = (
            [next_cep] if next_cep else []
        )
        frontier["next_executable_frontier"] = [next_cep] if next_cep else []
        frontier["next_autonomous_cep"] = next_cep
        frontier["current_session_continuation"] = (
            "CONTINUE_" + next_cep
            if next_cep
            else "REQUESTED_THREE_CEPS_COMPLETE_CLEAN_OPERATIONAL_STOP"
        )
        frontier["next_candidate_full_entry_eligibility"] = (
            "VERIFIED_APPROVED_REFERENCE"
            if next_cep
            else "NO_REMAINING_EXECUTABLE_CURRENT_GOVERNED_CEP"
        )
        frontier["boundary_reason"] = (
            cep
            + " approved Linux reference AC6/6/scoped DoD MET;continue actual eligible chain"
            if next_cep
            else "070/074/075 COMPLETE on one approved Linux reference.069 still requires external statutory/Production evidence;PostV1 deferred. No required in-scope Development/reproducible work remains."
        )
        frontier["reconciliation_evidence"] = evidence
        for code in ["CEP-070", "CEP-074", "CEP-075"]:
            if code == cep or (phase == "075"):
                frontier["unblock_conditions"].pop(code, None)
        if phase == "075":
            frontier["dependency_ready_current_governed"] = ["CEP-069"]
            frontier["resume_cep_after_blocker_resolution"] = "CEP-069"
        else:
            frontier["dependency_ready_current_governed"] = (
                ["CEP-069", "CEP-074", "CEP-075"]
                if phase == "070"
                else ["CEP-069", "CEP-075"]
            )

    replace(r"(?ms)^execution_frontier:\n.*\Z", update_frontier, indent=False)
    records = yaml.safe_load(raw)["ceps"]
    counts = Counter(
        v["execution"]["status"] for key, v in records.items() if int(key[-3:]) <= 79
    )

    def update_summary(doc):
        summary = doc["summary"]
        current = [v for key, v in records.items() if int(key[-3:]) <= 79]
        blocked = sum(
            v["execution"]["status"] == "NOT_STARTED" and bool(v["blockers"])
            for v in current
        )
        summary.update(
            execution_state_complete=counts["COMPLETE"],
            partial_current=counts["PARTIAL"],
            in_progress=counts["IN_PROGRESS"],
            blocked_current=blocked,
            not_started_other_current_governed=counts["NOT_STARTED"] - blocked,
            authorized_not_started=sum(
                v["execution"]["status"] == "NOT_STARTED"
                and v["authorization"]["status"].startswith("AUTHORIZED")
                for v in current
            ),
            eligible_under_standing_authority=0 if phase == "075" else 1,
            last_updated="2026-10-27",
        )

    replace(r"(?ms)^summary:\n.*?(?=^[a-z_]+:)", update_summary, indent=False)
    after = yaml.safe_load(raw)
    allowed = {cep} | ({"CEP-074"} if phase == "070" else set())
    assert all(
        after["ceps"][code] == value
        for code, value in before["ceps"].items()
        if code not in allowed
    )

    reports = ROOT / "docs/governance/cep/reports"
    report_path = reports / (cep + "_COMPLETION_REPORT.md")
    if report_path.exists():
        before_path = OUT / (phase + "_REPORT_BEFORE_CLOSEOUT.md")
        assert not before_path.exists()
        before_path.write_bytes(report_path.read_bytes())
    proof = f"../evidence/SHARED_TARGET_APPROVED_20261027/runtime/{phase}_RESULT.json"
    text = f"""# {cep} completion report — approved Linux reference

**EXECUTION COMPLETE; AC 6/6 PASS; scoped DoD MET.** IMB-{"0098" if phase == "070" else "0104" if phase == "074" else "0105"}.
2026-10-27; main `{entry["head"]}`; one shared `BONIRA-PE-NP-01`.
[Executed result]({proof}); [Human authority](../supporting/BONIRA-PE-NP-01_HUMAN_APPROVAL_20261027.md).

Actual environment: Debian12 isolated QEMU guest; exact approved CPython3.11.17
base image; Django5.2.17, pure Psycopg3.3.5/system libpq; PostgreSQL18.6-bookworm
with verified TLS; Nginx HTTPS → private Unix socket → Gunicorn26.2.0 synchronous
WSGI; production settings, DEBUG/personas false, private single-host shared cache,
disjoint protected files and per-target synthetic secrets. No Production system
or configured business database is used. Current source hashes are preserved.

{details}.

"""
    if phase in {"070", "074"}:
        text += """A fresh committed document revision is captured in this package's own new
snapshot and restored into its own empty target database/file trees. All complete
row hashes, schema constraints and sequence states match; all three file classes
match. Actual authorized document/version bytes, exact Decimal project budgets,
four cross-tenant read denials and two cross-tenant version-write denials pass.
Validation leaves complete restored state unchanged. Reconciliation is performed
through existing domain services under production settings, not raw-read inference.
Populated business scenarios are DMS/project/tenant records; other domains are
preserved as present. No populated financial/statutory recovery claim is made.

Two actual complete captures are within the approved900-second maximum. Private
retention receipts protect each bundle for30 days, next backup/restore-test due
dates are recorded, cross-process lock exclusion is executed, corruption is
rejected before restore and an actual failed restore remains explicit failure
evidence. No purge or future elapsed30-day/continuous-service PASS is inferred.
Observed RPO/RTO apply only to the controlled quiescent synthetic scenario and
the stated provisioning/reconciliation/service-access boundary, not a Production SLA.

| AC | Executed basis | Result |
| --- | --- | --- |
| AC1 | Four governed classes, fresh coherent snapshot, exact restore and approved objective comparisons | PASS |
| AC2 | Explicit approved target/scenario/runtime/source; no invented policy/topology | PASS |
| AC3 | Actual target-specific capture/restore/service execution | PASS |
| AC4 | Timestamped measured output, immutable bundle receipts and explicit failure records | PASS |
| AC5 | Failed/corrupt inputs rejected; no unavailable environment or Production readiness promoted | PASS |
| AC6 | Source/authority boundaries preserved; unexecuted Production/future behavior remains unqualified | PASS |

DoD: implementation/control or actual verification outcome, exact environment and
scenario, executable procedure, responsibility/evidence hooks and actual pass/fail
evidence are satisfied for the explicitly approved non-production scope.
"""
    else:
        text += """Previous and candidate are separately packaged copies of the exact current
source, with distinct release/config/static roots. No fictitious older revision
is claimed. Actual invalid-config startup and unavailable-dependency readiness
controls reject activation; previous verified build/config/static is reactivated
and revalidated, then the candidate is returned and revalidated. Real synthetic
TLS login, Secure cookies, CSRF/Host/proxy-header checks, authorized private bytes
and cross-tenant HTTP denial pass. Protected bytes, source and437 migration-history
entries remain unchanged. No schema migration/reversal or destructive data rollback.

All six canonical criteria pass: approved config/assets/readiness/rollback outcome;
exact environment/scenario/version; actual execution; measured timestamped results;
explicit failed-candidate rejection; remaining UTV retained. DoD is satisfied by
actual deployment/rollback/return execution, not preparation or static inference.
"""
    text += f"""
Tests: focused actual package scenario PASS; active qualification-tool Ruff/format
and final artifact/source/Registry checks are recorded separately in the same
evidence directory. No broad audit/full regression or unrelated COMPLETE CEP rerun.
No product/schema/permission/migration implementation change was required. Target
startup/path/permission harness defects were repaired and failed attempts retained.

Remaining UTV: future elapsed retention/drill/continuous operation; Production
policy/storage/key custody, installation, HA/capacity/SLA, actual activation/cutover
and final certification. These are not passed, waived or prerequisites invented
for completed bounded non-production work. Human Sign-off / final Production
Certification / Production Cutover: **NOT EXECUTED**. No Git writes; new evidence
and closeout remain uncommitted. Historical checkpoint metadata is preserved.

Registry synchronized. GATE-08: `{after["gates"]["GATE-08"]["status"]}`;
GATE-11: `NOT_PASSED`. Exact next_executable_frontier:
`{json.dumps(after["execution_frontier"]["next_executable_frontier"])}`.
"""
    if phase == "070":
        text = text.replace(
            "| AC3 | Actual target-specific capture/restore/service execution | PASS |",
            "| AC3 | Explicit authority, configuration, responsibility and evidence references before activation | PASS |",
        )
        text = text.replace(
            "| AC4 | Timestamped measured output, immutable bundle receipts and explicit failure records | PASS |",
            "| AC4 | Actual failure/corruption controls retain auditable evidence and reject readiness | PASS |",
        )
    report_path.write_text(text, encoding="utf-8")
    criteria = re.findall(
        r"(?m)^([1-6])\. `(IMB-[0-9]+)` — (.+)$", prompt.read_text(encoding="utf-8")
    )
    assert len(criteria) == 6
    ac_path = ROOT / "docs/governance/cep/evidence" / (cep + "_ACCEPTANCE_MAPPING.csv")
    with ac_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["criterion", "imb", "canonical_text", "status", "evidence", "scope_limit"]
        )
        for number, imb, criterion in criteria:
            writer.writerow(
                [
                    "AC" + number,
                    imb,
                    criterion,
                    "PASS_APPROVED_NONPRODUCTION_REFERENCE",
                    evidence,
                    "NO_FINAL_PRODUCTION_CERTIFICATION_OR_HUMAN_SIGNOFF",
                ]
            )
    evidence_manifest = (
        ROOT / "docs/governance/cep/evidence" / (cep + "_EVIDENCE_MANIFEST.csv")
    )
    if evidence_manifest.exists():
        original = evidence_manifest.read_text(encoding="utf-8")
        ids = [
            int(value)
            for value in re.findall(re.escape(cep) + r"-EV-([0-9]+)", original)
        ]
        next_id = max(ids, default=0) + 1
        with evidence_manifest.open("a", encoding="utf-8", newline="") as handle:
            row = (
                [
                    f"{cep}-EV-{next_id:03}",
                    evidence,
                    "AC6OF6_SCOPED_DOD_MET",
                    "NO_FINAL_PRODUCTION_CERTIFICATION",
                ]
                if phase == "070"
                else [
                    f"{cep}-EV-{next_id:03}",
                    "APPROVED_LINUX_RUNTIME_RESULT",
                    evidence,
                    "AC6OF6_SCOPED_DOD_MET_NO_PRODUCTION_CERTIFICATION",
                ]
            )
            csv.writer(handle).writerow(row)
    else:
        with evidence_manifest.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["evidence_id", "type", "path", "result"])
            writer.writerow(
                [
                    cep + "-EV-001",
                    "ACTUAL_APPROVED_REFERENCE_RESTORE",
                    evidence,
                    "AC6OF6_SCOPED_DOD_MET",
                ]
            )
    registry_path.write_text(raw, encoding="utf-8")
    write(
        OUT / (phase + "_CLOSEOUT.json"),
        {
            "at": now,
            "cep": cep,
            "execution": "COMPLETE",
            "ac": "6/6 PASS",
            "dod": "MET_APPROVED_NONPRODUCTION_SCOPE",
            "evidence": evidence,
            "details": details,
            "unrelated_ceps_preserved": len(before["ceps"]) - len(allowed),
            "source_files_preserved": len(freeze),
            "next_executable_frontier": after["execution_frontier"][
                "next_executable_frontier"
            ],
            "gates": {
                key: after["gates"][key]["status"] for key in ["GATE-08", "GATE-11"]
            },
        },
    )
    print(
        cep,
        "AC6/6/scoped DoD verified; Registry synchronized; frontier",
        after["execution_frontier"]["next_executable_frontier"],
    )


if __name__ == "__main__":
    main(sys.argv[1])
