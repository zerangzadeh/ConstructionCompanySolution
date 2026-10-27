"""Evidence-supported closeout, restricted to the four requested CEP records."""

import copy
import csv
from datetime import UTC, datetime
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess

import yaml

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
REL = OUT.relative_to(ROOT).as_posix()
TODAY = "2026-10-27"
SHA = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
assert SHA == "79f6a1e8b264b09f7a3177d5a9a95b6e49dd7ce4"
validation = json.loads((OUT / "VALIDATION.json").read_text())
assert all(r["exit_code"] == 0 for r in validation.values())
assert "23 passed, 45 subtests passed" in (OUT / "FOCUSED_TESTS.txt").read_text()
registry_path = ROOT / "CEP_EXECUTION_REGISTRY.yaml"
text = registry_path.read_text(encoding="utf-8")
before = yaml.safe_load((OUT / "REGISTRY_BEFORE.yaml").read_text(encoding="utf-8"))
registry = yaml.safe_load(text)
assert registry == before, "Unexpected concurrent Registry change"

product = [
    "config/settings/base.py", "config/settings/development.py",
    "config/settings/production.py", "tests/test_production_configuration.py",
    "core/operations.py", "tests/test_operations.py",
    "apps/support/management/__init__.py",
    "apps/support/management/commands/__init__.py",
    "apps/support/management/commands/operational_health.py",
    "apps/support/test_p9_s16_s20.py", "README.md",
]
supporting = [
    "docs/governance/cep/supporting/CEP-071_DEPLOYMENT_PREPARATION.md",
    "docs/governance/cep/supporting/CEP-072_OPERATIONS_PREPARATION.md",
    "docs/governance/cep/supporting/EXT-0021_DECISION_MATRIX_20261027.md",
    "docs/governance/cep/supporting/EXT-0022_DECISION_MATRIX_20261027.md",
]
for number, detail, disposition in (
    ("071", "Production dotenv boundary, weak/default secret, wildcard/empty host, HTTPS/bool/HSTS/dummy-cache guards and disjoint absolute static/media/private hooks; deployment/recovery process prepared", "DEVELOPMENT_CONFIGURATION_AND_DEPLOYMENT_PREPARATION_COMPLETE_TARGET_CONTRACT_REQUIRED"),
    ("072", "Read-only CLI database/cache signals, discrete failure rules, local-only alert destination, explicit-cutoff diagnostic retention and OP-01..04 draft runbooks; two selected access fixtures repaired without changing product authorization", "DEVELOPMENT_OPERATIONS_PLUMBING_COMPLETE_OPERATING_APPROVAL_REQUIRED"),
):
    cep = "CEP-" + number
    item = registry["ceps"][cep]
    item["eligibility_status"] = disposition
    item["acceptance"]["status"] = "PRODUCTION_CERTIFICATION_UNVERIFIED_DEVELOPMENT_PREREQUISITES_PROVED"
    item["completion_report"]["evidence_presence"] = "VERIFIED_DEVELOPMENT_ONLY_23_TESTS_45_SUBTESTS_DEPLOYMENT_SMOKE_CHECKS_PASS"
    item["last_execution"] = {"branch": "main", "sha": SHA}
    item["updated_at"] = TODAY
    item["git"]["current_session_changes_committed"] = False
    item["history"].extend([
        {"date": TODAY, "status": "RESUMED", "reason": "Explicit current Human instruction to exhaust both independent chains' Development prerequisites; canonical identity/phase semantics verified and dirty tree preserved.", "evidence": REL + "/ENTRY.json"},
        {"date": TODAY, "status": "BLOCKER_RESOLVED", "reason": detail + ". Focused23/23 and45subtests PASS, isolated --deploy/WSGI/ASGI/153static assets PASS; lint/format PASS. No schema, product authorization, Production or Git write.", "evidence": REL + "/VALIDATION.json"},
        {"date": TODAY, "status": "PARTIAL", "reason": "All currently authorized Development/reproducible prerequisite work complete; required target/owner approvals and environment evidence remain unavailable. Canonical AC/DoD remain production-unverified, no Gate PASS inferred.", "evidence": REL + "/RESULT.json"},
    ])
    ext = "EXT-0021" if number == "071" else "EXT-0022"
    item["frontier_review"] = {
        "at": datetime.now(UTC).isoformat(), "head": SHA,
        "evidence": REL + "/RESULT.json",
        "result": "NO_DEVELOPMENT_RESOLVABLE_OR_REPRODUCIBLE_EVIDENCE_WORK_REMAINS",
        "blocker_classes": ["HUMAN_DECISION", "AUTHORITATIVE_EXTERNAL_INPUT", "PRODUCTION_ONLY"],
        "smallest_remaining_prerequisite": f"Only unresolved items in docs/governance/cep/supporting/{ext}_DECISION_MATRIX_20261027.md",
        "development_disposition": disposition,
        "standing_authority": "Development preparation allowed; no missing Production approval used as a generic Build blocker. Target-dependent work awaits exact approved contract.",
    }

registry["ceps"]["CEP-071"]["blockers"] = [
    "CEP-071-FINDING-001 / BLOCKER-EXTERNAL / HUMAN_DECISION + AUTHORITATIVE_EXTERNAL_INPUT: EXT0021 selected target/topology/process/static-media/secrets and rollback/acceptance ownership remain unapproved; see EXT-0021_DECISION_MATRIX_20261027.md. Existing environment schema and Development mechanics are established, not requested again.",
    "PRODUCTION_ONLY: Actual Production deployment/cutover/final certification remains separately unauthorized; no such action attempted.",
]
registry["ceps"]["CEP-071"]["remaining_utv"] = [
    "Approved target-specific runtime/process/proxy/durable-storage/secret-custody and rollback evidence; synthetic static/config proof does not establish production equivalence",
    "Existing CEP013 signed wheelhouse/production installation qualification retained as release-contract UTV, not re-executed",
    "Production certification, Human Sign-off and cutover NOT_EXECUTED",
]
registry["ceps"]["CEP-072"]["blockers"] = [
    "CEP-072-FINDING-001 / BLOCKER-EXTERNAL / HUMAN_DECISION + AUTHORITATIVE_EXTERNAL_INPUT: EXT0022 named operating/incident/escalation/access owners, runbook approval, target signal/alert/retention and activation/acceptance contracts remain unapproved; see EXT-0022_DECISION_MATRIX_20261027.md. Technical catalogue, local adapters and existing revocation mechanics are already proved.",
    "PRODUCTION_ONLY: Actual Production operations activation/final certification remains separately unauthorized; no such action attempted.",
]
registry["ceps"]["CEP-072"]["remaining_utv"] = [
    "Approved target signal/producer catalogue and real restricted alert destinations/receipt, retention policy and owner-approved OP-01..04 runbooks",
    "Target-specific operating ownership, incident/escalation/access responsibility and drill acceptance; local tests do not approve policy or exercise CEP076",
    "Production operations activation/certification NOT_EXECUTED; no new scheduled job, external alert or access bypass",
]
for number, parent, ext in (("075", "071", "EXT-0021"), ("076", "072", "EXT-0022")):
    item = registry["ceps"]["CEP-" + number]
    assert item["execution"]["status"] == "NOT_STARTED"
    item["updated_at"] = TODAY
    item["history"].append({"date": TODAY, "status": "PREREQUISITE_RECHECKED", "reason": f"CEP{parent} Development prerequisite preparation advanced, canonical required outcome remains PARTIAL and {ext} verification condition unresolved. No drill started, production equivalence invented, dependency waived or AC/DoD/Gate PASS granted.", "evidence": REL + "/RESULT.json"})
    item["frontier_review"] = {
        "at": datetime.now(UTC).isoformat(), "head": SHA,
        "evidence": REL + "/RESULT.json", "result": "NOT_ELIGIBLE_NOT_STARTED",
        "blocker_classes": ["HUMAN_DECISION", "AUTHORITATIVE_EXTERNAL_INPUT"],
        "smallest_remaining_prerequisite": f"Required CEP-{parent} outcome plus approved {ext} designated non-production verification target/scenario",
        "development_disposition": "No independent authorized drill work before canonical entry; preparation is not execution",
    }

frontier = registry["execution_frontier"]
frontier["current_session_continuation"] = "STOP_NO_DEVELOPMENT_RESOLVABLE_WORK_REMAINS"
frontier["current_session_cep_range"] = "CEP071_075_AND_CEP072_076_DEVELOPMENT_PREREQUISITES"
frontier["boundary_reason"] = "All currently authorized Development/reproducible work in both requested chains completed; EXT0021 and EXT0022 now have one compact unresolved-only decision matrix each. Required071/072 outcomes remain PARTIAL;075/076 NOT_STARTED. Independent069/070/074 boundaries and completed073/077..079 unchanged."
frontier["unblock_conditions"]["CEP-071"] = "Only unresolved target/topology/process/static-media/secrets and rollback/acceptance choices in EXT-0021_DECISION_MATRIX_20261027.md; existing source/config/preparation facts already established"
frontier["unblock_conditions"]["CEP-072"] = "Only unresolved ownership/runbook/target-signals/destinations/retention and activation/acceptance input in EXT-0022_DECISION_MATRIX_20261027.md; technical catalogue/adapters/revocation already proved"
frontier["next_executable_frontier"] = []
frontier["reconciliation_evidence"] = REL + "/RESULT.json"
registry["repository_state"]["pending_checkpoint_scope"] += ";CEP071_072_DEVELOPMENT_PREPARATION_UNCOMMITTED"

# Replace only selected blocks, preserving unrelated dirty-tree text and history.
for cep in ("CEP-071", "CEP-072", "CEP-075", "CEP-076"):
    replacement = "\n".join("  " + line for line in yaml.safe_dump({cep: registry["ceps"][cep]}, sort_keys=False, allow_unicode=True, width=140).splitlines()) + "\n"
    text, count = re.subn(rf"^  {cep}:\n.*?(?=^  CEP-\d{{3}}:|^authority_scope:)", lambda _: replacement, text, flags=re.M | re.S)
    assert count == 1
for key, following in (("repository_state", "execution_frontier"), ("execution_frontier", None)):
    pattern = rf"^{key}:\n.*?(?=^{following}:)" if following else rf"^{key}:\n.*\Z"
    replacement = yaml.safe_dump({key: registry[key]}, sort_keys=False, allow_unicode=True, width=140)
    text, count = re.subn(pattern, lambda _: replacement, text, flags=re.M | re.S)
    assert count == 1
after = yaml.safe_load(text)
assert after == registry
assert before["gates"] == after["gates"]
assert before["summary"] == after["summary"]
for key in before["ceps"]:
    if key not in {"CEP-071", "CEP-072", "CEP-075", "CEP-076"}:
        assert before["ceps"][key] == after["ceps"][key], key
registry_path.write_text(text, encoding="utf-8")

for number in ("071", "072"):
    cep = "CEP-" + number
    total = 6 if number == "071" else 12
    detail = (
        "Production dotenv loading removed; Development dotenv behavior preserved. Weak/default secrets, empty/wildcard hosts, insecure HTTPS/bool values, negative/invalid HSTS and dummy-cache settings fail closed. Explicit absolute disjoint static/media/private roots supplied without selecting a provider. Prepared process/environment/static/secrets/release/rollback/validation contract reuses existing approved Linux build facts. Synthetic Django deployment checks, WSGI/ASGI imports and153static assets pass without dotenv, network or database access."
        if number == "071" else
        "Read-only operator CLI health probes emit sanitized database/cache reachability without a public endpoint or readiness PASS. Actual isolated PostgreSQL/cache command integration passes. Existing technical request/fallback events project to discrete failure alerts through a disposable local file adapter; explicit-cutoff retention defaults to planning and only removes adapter-owned diagnostics. OP-01..04 cover incident/escalation, dependency recovery, existing support grant/expiry/revoke and retention closeout. No production sink, threshold, scheduler or new access authority is activated."
    )
    ext = "EXT-0021" if number == "071" else "EXT-0022"
    report = ROOT / f"docs/governance/cep/reports/{cep}_COMPLETION_REPORT.md"
    with report.open("a", encoding="utf-8") as stream:
        stream.write(f"\n\n## Development prerequisites exhausted — {TODAY}\n\n**EXECUTION PARTIAL; AC0/{total} production-certified; scoped DoD NOT MET.**\nMain `{SHA}`; existing dirty changes preserved. Current explicit Human instruction and canonical/phase identities recorded in [ENTRY](../evidence/CEP-071_072_DEVELOPMENT_20261027/ENTRY.json). No prerequisite CEP for this preparation.\n\n{detail}\n\n[Focused validation](../evidence/CEP-071_072_DEVELOPMENT_20261027/VALIDATION.json): **23/23 tests +45subtests PASS**, Ruff/check-format PASS, isolated deployment smoke PASS. Only two existing support-access cases were exercised; their fixtures lacked explicit current membership role/scope evidence and failed before reaching revocation. Those selected fixtures now supply that evidence; product authorization unchanged. Initial relative-cache smoke fixture and Windows timestamp-granularity retention fixture were corrected. No required failure remains; no broad regression or production-equivalent drill claimed.\n\nActual touch set, source hashes, resolved DEVELOPMENT_RESOLVABLE / REPRODUCIBLE_EVIDENCE items and residual classifications: [RESULT](../evidence/CEP-071_072_DEVELOPMENT_20261027/RESULT.json). Findings outside these boundaries were not absorbed.\n\nRemaining HUMAN_DECISION / AUTHORITATIVE_EXTERNAL_INPUT is confined to the [single {ext} matrix](../supporting/{ext}_DECISION_MATRIX_20261027.md). Actual Production action/certification remains PRODUCTION_ONLY. EXT0020 recovery ownership/retention is not expanded into deployment/operating policy. Downstream075/076 remain NOT_STARTED and ineligible; neither required parent outcome is complete. Gates08/11 remain NOT_PASSED; all Gates unchanged. Registry reconciled; exact next_executable_frontier `[]`.\n\n**NO DEVELOPMENT-RESOLVABLE WORK REMAINS** with current inputs and authority in either requested chain. Future approved target contracts may expose target-dependent work. Schema/migrations, business/domain/workflow/permission semantics unchanged. No new branch/worktree, Git write, Production action, Human Sign-off, Production Certification or Cutover. CEP070/074 not reopened;073/077..079 not re-executed. All session changes uncommitted.\n")
    manifest = ROOT / f"docs/governance/cep/manifests/{cep}_EXECUTION_MANIFEST.md"
    with manifest.open("a", encoding="utf-8") as stream:
        stream.write("\nCloseout: [RESULT](../evidence/CEP-071_072_DEVELOPMENT_20261027/RESULT.json),23tests/45subtests/checks PASS. Development prerequisites exhausted; canonical AC/DoD remain production-unverified. One unresolved-only EXT matrix prepared. No production-equivalent downstream drill, Gate PASS, schema/authorization change or Git write.\n")
    evidence = ROOT / f"docs/governance/cep/evidence/{cep}_EVIDENCE_MANIFEST.csv"
    start = 5
    with evidence.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        for offset, kind, file in ((0, "CANONICAL_ENTRY_AND_DIRTY_TREE", "ENTRY.json"), (1, "FOCUSED_DEVELOPMENT_VALIDATION", "VALIDATION.json"), (2, "PREREQUISITE_CLOSEOUT_AND_DECISION_BOUNDARY", "RESULT.json")):
            writer.writerow([f"{cep}-EV-{start+offset:03}", kind, f"CEP-071_072_DEVELOPMENT_20261027/{file}", "DEVELOPMENT_PASS_CANONICAL_PRODUCTION_UNVERIFIED"])
    ac = ROOT / f"docs/governance/cep/evidence/{cep}_ACCEPTANCE_MAPPING.csv"
    rows = list(csv.DictReader(io.StringIO(ac.read_text(encoding="utf-8"))))
    for row in rows:
        row["evidence"] += ";CEP-071_072_DEVELOPMENT_20261027/VALIDATION.json;CEP-071_072_DEVELOPMENT_20261027/RESULT.json"
    with ac.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["criterion", "status", "evidence"])
        writer.writeheader()
        writer.writerows(rows)
    changes = ROOT / f"docs/governance/cep/evidence/{cep}_CHANGE_MANIFEST.csv"
    paths = (product[:4] + ["README.md"] + supporting[::2]) if number == "071" else (product[4:10] + supporting[1::2])
    with changes.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        for path in paths + [REL + "/", str(manifest.relative_to(ROOT)).replace("\\", "/")]:
            writer.writerow([path, "ADDED_OR_UPDATED", "BOUNDED_DEVELOPMENT_PREPARATION_ONLY"])

result = {
    "client_date": TODAY, "head": SHA, "branch": "main",
    "execution": {"CEP-071": "EXECUTION PARTIAL", "CEP-072": "EXECUTION PARTIAL", "CEP-075": "NOT_ELIGIBLE_NOT_STARTED", "CEP-076": "NOT_ELIGIBLE_NOT_STARTED"},
    "work_completed": [
        "Topology-independent production environment/security/static-media controls and secret-loading boundary",
        "Source-derived deployment/config/process/release-validation/rollback preparation;153synthetic static assets and both runtime entrypoints validated",
        "Read-only CLI health signals verified on isolated test PostgreSQL and cache",
        "Technical event projection, discrete local alerts and explicit-cutoff disposable diagnostic retention; no production rule/destination selected",
        "OP-01..04 drafts and existing governed grant/expiry/revocation evidence; selected current-role/scope test fixtures repaired",
        "One unresolved-only EXT0021 matrix and one unresolved-only EXT0022 matrix; independent chains evaluated to completion of available Development work",
    ],
    "resolved": {
        "DEVELOPMENT_RESOLVABLE": ["Production dotenv/default/host/TLS/bool/HSTS/cache/storage gaps", "Local health/alert/retention plumbing and runbook preparation", "Selected legacy support-access fixture current role/scope evidence", "New retention test clock precision fixture"],
        "REPRODUCIBLE_EVIDENCE": ["23tests and45subtests PASS", "Django --deploy and WSGI/ASGI+153static assets PASS with dotenv/network/DB forbidden", "Read-only health command against isolated Django PostgreSQL test DB and cache PASS", "Two selected support independence/scope/expiry/revocation/audit tests PASS", "Ruff check/format PASS"],
    },
    "remaining": {
        "EXT-0021": {"classes": ["HUMAN_DECISION", "AUTHORITATIVE_EXTERNAL_INPUT"], "matrix": supporting[2]},
        "EXT-0022": {"classes": ["HUMAN_DECISION", "AUTHORITATIVE_EXTERNAL_INPUT"], "matrix": supporting[3]},
        "Production": {"class": "PRODUCTION_ONLY", "status": "NOT_EXECUTED_NOT_AUTHORIZED"},
    },
    "validation": validation,
    "corrected_failed_checks": [
        "Initial new management command was outside an installed app; moved to installed apps.support namespace and discovery test passes",
        "Initial Ruff findings/import ordering fixed; final lint/format PASS",
        "SMOKE_FIXTURE_BASELINE.txt: synthetic relative cache path caused W003; fixture now uses its disposable absolute cache path, no warning suppressed",
        "SUPPORT_FIXTURE_BASELINE.txt: missing scope evidence made old selected fixtures fail closed before new code/revocation; test-only explicit role/scope setup added, product authorization unchanged",
        "RETENTION_CLOCK_FIXTURE_BASELINE.txt: Windows clock granularity made equal timestamps nondeterministic; explicit old/new clock fixtures now test cutoff deterministically",
    ],
    "actual_product_and_preparation_touch_set": product + supporting,
    "source_sha256": {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in product + supporting},
    "unchanged_boundaries": ["Canonical prompts/hash manifest", "All gates", "All CEP records except071/072/075/076", "Schema/migrations", "Product authorization and support services", "Business/financial/domain/workflow semantics", "Unrelated existing Human working-tree changes"],
    "gates": {k: after["gates"][k]["status"] for k in ("GATE-08", "GATE-11")},
    "gate_changes": [], "next_executable_frontier": [],
    "development_work_remaining": [], "reproducible_evidence_work_remaining": [],
    "verdict": "NO DEVELOPMENT-RESOLVABLE WORK REMAINS",
    "git_writes": "NOT_EXECUTED", "production_actions": "NOT_EXECUTED", "human_signoff": "NOT_EXECUTED",
    "limitations": "Development proofs only; no selected production-equivalent target, real alert destination, approved diagnostic retention policy or operational acceptance. No broad regression/audit or073/077..079 rerun;070/074 not reopened.",
}
(OUT / "RESULT.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print("REGISTRY/REPORTS/EVIDENCE RECONCILED; unrelated CEP records and all Gates unchanged; frontier []")
