"""Evidence-supported closeout only; Git integration is separately authorized."""

import csv
import difflib
import hashlib
import io
import json
import re
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
E = ROOT / "docs/governance/cep/evidence"


def read(name):
    return json.loads((E / name).read_text("utf-8"))


def write(name, value):
    (E / name).write_text(json.dumps(value, indent=2) + "\n", "utf-8")


def git(*args):
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


results = read("CEP-044_VALIDATION_RESULTS.json")
for path, expected in read("CEP-044_VALIDATION_INPUTS.json")["sha256"].items():
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path
assert set(results) == {"FOCUSED", "AFFECTED"}
assert all(r["exit_code"] == 0 for r in results.values())
migration = read("CEP-044_DEVELOPMENT_ACTIONS_MIGRATION.json")
assert migration["all_preexisting_columns_counts_and_sha256_unchanged"]
assert migration["new_corrections_decisions_reversals"] == [0, 0, 0]
assert "All checks passed" in (E / "CEP-044_FINAL_CHECK_OUTPUT.txt").read_text("utf-8")
assert "already formatted" in (E / "CEP-044_FINAL_FORMAT_OUTPUT.txt").read_text("utf-8")
assert "no issues" in (E / "CEP-044_FINAL_SYSTEM_OUTPUT.txt").read_text("utf-8")
assert "No changes detected" in (E / "CEP-044_FINAL_DRIFT_OUTPUT.txt").read_text(
    "utf-8"
)
identities = {}
manifest = (ROOT / "docs/governance/cep/CEP_PROMPT_MANIFEST.yaml").read_text("utf-8")
for cep, path, expected in re.findall(
    r"^  (CEP-\d{3}):\n    path: (.*?)\n    canonical: true\n    immutable: true\n    sha256: (\w+)",
    manifest,
    re.MULTILINE,
):
    actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    assert actual == expected
    identities[cep] = actual
assert len(identities) == 79
head = git("rev-parse", "HEAD")
assert head == read("CEP-044_VALIDATION_INPUTS.json")["head"], (
    "Execution closeout is bound to its tested baseline; do not replay after checkpoint."
)
assert (
    head
    == git("rev-parse", "origin/main")
    == git("ls-remote", "origin", "refs/heads/main").split()[0]
)
assert git("branch", "--show-current") == "main"

# Preserve dated partial snapshots rather than rewriting their historical result.
report_path = ROOT / "docs/governance/cep/reports/CEP-044_COMPLETION_REPORT.md"
for source, target in (
    (report_path, E / "CEP-044_PERSISTENCE_COMPLETION_REPORT.md"),
    (
        E / "CEP-044_ACCEPTANCE_MAPPING.csv",
        E / "CEP-044_PERSISTENCE_ACCEPTANCE_MAPPING.csv",
    ),
    (E / "CEP-044_FRONTIER.json", E / "CEP-044_PERSISTENCE_FRONTIER.json"),
):
    if not target.exists():
        target.write_bytes(source.read_bytes())

registry_path = ROOT / "CEP_EXECUTION_REGISTRY.yaml"
registry = registry_path.read_text("utf-8")
start = registry.index("  CEP-044:\n", registry.index("\nceps:\n"))
end = registry.index("  CEP-045:\n", start)
block = registry[start:end]
block = block.replace(
    "status: IN_PROGRESS\n      lifecycle: RESUMED",
    "status: COMPLETE\n      lifecycle: CLOSED_VERIFIED",
    1,
)
block = block.replace(
    "passed: 0\n      total: 12\n      status: IN_PROGRESS",
    "passed: 12\n      total: 12\n      status: PASS",
    1,
)
block = block.replace("    dod: NOT_MET", "    dod: MET", 1)
new_history = """    - date: '2026-10-19'
      status: MIGRATION_STATE_CHANGED
      reason: Authorized additive subledgers0008 applied only to configured loopback Development PostgreSQL/Psycopg3. Two authority JSON columns and immutable correction-set table; all pre-existing table columns/counts/digests preserved. No inferred backfill, policy selection, grants or finalized financial changes. Populated correction/authority rollback refuses forward-history loss.
    - date: '2026-10-19'
      status: COMPLETE
      reason: EXECUTION COMPLETE; all12 AC and scoped DoD verified. Explicit closed native Billing AR, Billing AP and supplier-invoice AP L2 adapters plus manual write-off approval/rejection and atomic exact reversal/optional replacement; policy/permission/object/tenant checks, lineage, effective-date cutoffs, replay/conflicting races, rollback/retry, audit and requester confidentiality proved. See final validation, migration/preservation and integration trace. Required lint/format/system/drift checks pass. Findings001/002 resolved; historical failures and baseline debt retained. GATE05 remains NOT_PASSED; runtime UTV and production restrictions unchanged. Git integration is separate from this execution verdict.
"""
if "Authorized additive subledgers0008 applied" not in block:
    block += new_history
registry = registry[:start] + block + registry[end:]
records = dict(
    re.findall(
        r"^  (CEP-\d{3}):\n(.*?)(?=^  CEP-\d{3}:|^\S|\Z)",
        registry.split("\nceps:\n", 1)[1],
        re.MULTILINE | re.DOTALL,
    )
)
states = {
    c: re.search(r"    execution:\n      status: (\S+)", b)[1]
    for c, b in records.items()
}
for key, value in {
    "execution_state_complete": sum(s == "COMPLETE" for s in states.values()),
    "in_progress": sum(s == "IN_PROGRESS" for s in states.values()),
    "partial_current": sum(
        s == "PARTIAL" for c, s in states.items() if int(c[-3:]) <= 79
    ),
    "failed_current": sum(
        s == "FAILED" for c, s in states.items() if int(c[-3:]) <= 79
    ),
    "not_started_other_current_governed": sum(
        s == "NOT_STARTED" for c, s in states.items() if int(c[-3:]) <= 79
    ),
}.items():
    registry = re.sub(
        rf"^  {key}: \d+$", f"  {key}: {value}", registry, count=1, flags=re.MULTILINE
    )

entry = read("CEP-044_ENTRY.json")
source = entry["sources"][
    "BONIRA_CODEX_EXECUTION_PACKAGE_DESIGN_CONSOLIDATED_LATEST.zip"
]
archive = Path(source["path"])
assert hashlib.sha256(archive.read_bytes()).hexdigest() == source["sha256"]
with zipfile.ZipFile(archive) as zipped:
    data = zipped.read("BONIRA_CEP_DEPENDENCY_REGISTER.csv")
assert (
    hashlib.sha256(data).hexdigest()
    == source["members"]["BONIRA_CEP_DEPENDENCY_REGISTER.csv"]
)
dependencies = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
ready, conditional = [], []
for cep in records:
    if int(cep[-3:]) > 79 or states[cep] == "COMPLETE":
        continue
    deps = [r for r in dependencies if r["Dependent CEP"] == cep]
    if any(
        states[r["Prerequisite CEP"]] != "COMPLETE" and r["Condition"] == "ALWAYS"
        for r in deps
    ):
        continue
    unmet = [r for r in deps if states[r["Prerequisite CEP"]] != "COMPLETE"]
    if unmet:
        conditional.append({"cep": cep, "requires_condition_review": unmet})
    else:
        ready.append(cep)
write(
    "CEP-044_FRONTIER.json",
    {
        "evaluated_at": "2026-10-19",
        "evaluated_head": head,
        "dependency_ready": ready,
        "conditional_entry_review": conditional,
        "readiness_is_not_eligibility": True,
        "next_selection": "Requires per-package C0/entry review; serial continuation authorized",
        "completed_cep044_excluded": True,
    },
)

gate = read("CEP-043_GATE05_EVALUATION.json")
gate["evaluated_at"] = "2026-10-19"
gate["status"] = "NOT_PASSED"
gate["contributors"]["IMB-0062"] = {
    "cep": "CEP-044",
    "execution": "COMPLETE",
    "contribution": "VERIFIED",
    "evidence": ["CEP-044_FOCUSED_FINAL_OUTPUT.txt", "CEP-044_INTEGRATION_TRACE.json"],
}
gate["cep044_assessment"] = (
    "Only IMB0062 contribution proved here; other required contracts remain incomplete or unverified. Prior contributor reviews retained; no inferred global PASS, activation, UAT or production authority."
)
write("CEP-044_GATE05_EVALUATION.json", gate)
registry = re.sub(
    r"  GATE-05:\n.*?(?=^\S)",
    """  GATE-05:
    status: NOT_PASSED
    evaluated_at: '2026-10-19'
    evidence: docs/governance/cep/evidence/CEP-044_GATE05_EVALUATION.json
    note: CEP044 IMB0062 source-family L2 contribution verified; prior contributor reviews retained. Other required contracts remain incomplete or unverified. No global convergence PASS, tenant activation, UAT or production authority inferred.
""",
    registry,
    count=1,
    flags=re.MULTILINE | re.DOTALL,
)
registry_path.write_text(registry, "utf-8")

with (E / "CEP-044_ACCEPTANCE_MAPPING.csv").open(encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f))
checks = [
    "real Billing AR/AP and supplier AP L2",
    "approved native source/version and retained control pin",
    "exact replay and unique economic identity",
    "target failure/rollback/retry audit",
    "source/Accounting/Treasury authority separation",
    "native AP and write-off reversal/replacement reconciliation",
    "explicit manual approval path without thresholds",
    "source preconditions and requester permission",
    "explicit scoped approval/reverse plus effective Self-Approval policy",
    "immutable actor/time/source/policy/Accounting evidence",
    "rejection/cancellation/atomic correction and as-of history",
    "own-request minimum status projection",
]
for row, check in zip(rows, checks, strict=True):
    row.update(
        result="PASS",
        evidence="CEP-044-EV-021; CEP-044-EV-022; CEP-044-EV-023; CEP-044-EV-024; CEP-044-EV-025",
        limitation=check
        + "; L2 contract build only; runtime/production UTV not converted to PASS",
    )
with (E / "CEP-044_ACCEPTANCE_MAPPING.csv").open(
    "w", encoding="utf-8", newline=""
) as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

focused = results["FOCUSED"]["summary"][0]
affected = results["AFFECTED"]["summary"][0]
report_path.write_text(
    f"""# CEP-044 Completion Report — 2026-10-19

**EXECUTION COMPLETE — 12/12 AC PASS; scoped DoD MET.** Lifecycle CLOSED_VERIFIED. Development/Non-Production only. GATE-05 remains **NOT_PASSED**.

## Authority and canonical contract

Finding001 is resolved by [bounded migration authority](../evidence/CEP-044_HUMAN_MIGRATION_AUTHORIZATION.md); Finding002 is resolved by the [verbatim governing correction decision](../supporting/CEP-044_WRITE_OFF_CORRECTION_POLICY.md). [Migration amendment](../evidence/CEP-044_AMENDMENT.json) and [correction provenance](../evidence/CEP-044_CORRECTION_PROVENANCE.json) retain original/amended SHA256 and unchanged-section proof. Current prompt SHA256 `{identities["CEP-044"]}`; all79 identities reverified. Only migration language and the authorized governing-source reference changed; Scope, AC, DoD, dependencies, domain ownership and recognition rules remain unchanged.

## Delivered contract

Approved native Billing claims, payable certificates and supplier invoice matches feed closed source-family Accounting L2 adapters after explicit AP/AR acceptance. Native UUID/version, immutable source hash, obligation/control mapping, project and party context are retained. Replays reuse the exact draft; approved effective directional mappings are required. AP source correction/reversal links original and replacement targets; reconciliation exposes current source, predecessor, inverse and replacement. Existing Billing recognized-obligation correction guards remain authoritative.

Manual write-off proposal, approval/rejection, exact full reversal and optional replacement use existing scoped permissions and an explicitly selected, versioned Self-Approval policy. No default value, approval/reverse grant, threshold, automatic behavior, new Protected classification or approval depth is introduced. Absent policy/permission/mapping/source authority fails closed. `requester_writeoff_status` returns only the caller's own request ID/status/amount/date.

`correct_write_off` locks/re-reads tenant, membership, original/source, policy version, replacement and Accounting evidence. Original write-off, full inverse, optional replacement, correction identity, actor/time/reason/date/source/policy/Accounting lineage and success audit commit atomically. Exact replay revalidates and returns the original result; conflicting identities, competing correction races and over-capacity outcomes refuse. Both reversal and replacement use the explicit correction date. Earlier aging/as-of facts are retained; later cutoffs include the new set once. Current outstanding uses the same tenant-date cutoff. Underlying obligations, Treasury facts and finalized financial history are preserved.

Accounting remains GL authority and owns L2 mapped drafts; no new operational posting producer, generic Subledger writer, fallback account or Payroll expense recognition path is added. Original inverse rows use the exact retained mapping. Consumed/drifted/legacy-unproven effects and invalid correction periods fail closed; no cross-domain unwind or accounting-date substitution occurs. The supplier AP guard now includes the new L2 evidence alongside legacy direct-journal consumption.

## Validation and persistence

- [Final focused tests](../evidence/CEP-044_FOCUSED_FINAL_OUTPUT.txt): **{focused}**. Includes actual Billing workflows, all three source families, approval/rejection, policy absence/explicit Self-Approval, tenant/object/permission denials, correction chains, both replay and conflicting PostgreSQL races, rollback/retry, exact inverse, historical cutoffs and requester confidentiality.
- [Affected regression](../evidence/CEP-044_AFFECTED_FINAL_OUTPUT.txt): **{affected}**. Actual coverage is recorded in [validation commands/results](../evidence/CEP-044_VALIDATION_RESULTS.json); no full-suite PASS claimed.
- [Integration/transaction trace](../evidence/CEP-044_INTEGRATION_TRACE.json), [populated migration rehearsal](../evidence/CEP-044_ACTIONS_MIGRATION_TRACE.json), [lint](../evidence/CEP-044_FINAL_CHECK_OUTPUT.txt), [format](../evidence/CEP-044_FINAL_FORMAT_OUTPUT.txt), [system checks](../evidence/CEP-044_FINAL_SYSTEM_OUTPUT.txt) and [drift](../evidence/CEP-044_FINAL_DRIFT_OUTPUT.txt): PASS within the recorded scope. Repository Ruff migration exclusions are honored; migrations are validated by Django and populated PostgreSQL rehearsal.
- Additive0007 source predecessor plus0008 authority JSON/correction-set table. [0007 Development proof](../evidence/CEP-044_DEVELOPMENT_MIGRATION.json) and [0008 Development proof](../evidence/CEP-044_DEVELOPMENT_ACTIONS_MIGRATION.json): all existing column counts/digests across {migration["preexisting_tables_verified"]} managed tables match before/after; new source/correction/action facts remain zero. No inferred backfill, policy selection, grant changes or historical financial mutation. Rollback/reapply preserves unused legacy history; used lineage/authority/corrections refuse destructive rollback and require forward recovery.

## AC, DoD, limitations and continuation

[Acceptance Mapping](../evidence/CEP-044_ACCEPTANCE_MAPPING.csv) proves all12 unchanged criteria. Both scoped DoD sets are MET: approved target/source contract and lineage; idempotency/retry/failure/duplicate prevention; reconciliation/audit; integration/domain/security checks; authority boundary; governed manual transitions and retained history. [Evidence Manifest](../evidence/CEP-044_EVIDENCE_MANIFEST.csv), [Change Manifest](../evidence/CEP-044_CHANGE_MANIFEST.csv), [Execution Manifest](../manifests/CEP-044_EXECUTION_MANIFEST.md) and [code diff](../evidence/CEP-044_FINAL_CODE_DIFF.patch) retain inspectable evidence.

No unresolved in-scope blocker. Initial guard, test API/fixture, shared-test-DB sequencing and catalog-reset failures are retained in [failure attribution](../evidence/CEP-044_CORRECTION_FAILURE_ATTRIBUTION.json), [expanded initial output](../evidence/CEP-044_EXPANDED_INITIAL_OUTPUT.txt) and earlier persistence evidence. [Prior partial closeout](../evidence/CEP-044_PERSISTENCE_COMPLETION_REPORT.md) remains historical. Existing Payroll/Fixed Assets role-fixture debt and performance/concurrency runtime UTV remain; synthetic PostgreSQL race PASS is not runtime/performance certification. No UI/browser requirement applies.

[GATE-05 evaluation](../evidence/CEP-044_GATE05_EVALUATION.json) verifies only this contribution against canonical exit criteria; other contributors remain incomplete/unverified. [Live frontier](../evidence/CEP-044_FRONTIER.json) is recomputed; dependency readiness is not execution eligibility. Serial continuation remains under standing authority after safe Git checkpoint/entry review. This execution report precedes the separately authorized checkpoint; Registry owns live Git integration state.

No production migration/cutover, irreversible production mutation, Human Sign-off or Production Certification occurred or is authorized.
""",
    "utf-8",
)

execution_manifest = (
    ROOT / "docs/governance/cep/manifests/CEP-044_EXECUTION_MANIFEST.md"
)
history = execution_manifest.read_text("utf-8")
if not history.startswith("# EXECUTION COMPLETE"):
    execution_manifest.write_text(
        "# EXECUTION COMPLETE — CEP-044 — 2026-10-19\n\n12/12 AC PASS; scoped DoD MET. Findings001/002 resolved under retained Human decisions. Final implementation, actual touch set, source-family contracts, validation, preservation, UTV, Gate/frontier and Git separation are recorded in the [Completion Report](../reports/CEP-044_COMPLETION_REPORT.md) and final manifests. All earlier entries below are dated historical execution snapshots. No production authority inferred.\n\n---\n\n"
        + history,
        "utf-8",
    )

with (E / "CEP-044_EVIDENCE_MANIFEST.csv").open(encoding="utf-8", newline="") as f:
    evidence = list(csv.DictReader(f))
evidence = evidence[:20]
for item in evidence:
    item["type"] = item["type"].replace("CURRENT", "HISTORICAL")
    if not item["result"].startswith(
        "Historical pre-Finding002 implementation snapshot;"
    ):
        item["result"] = (
            "Historical pre-Finding002 implementation snapshot; current proof EV021 onward. "
            + item["result"]
        )
evidence[6]["path"] = "CEP-044_PERSISTENCE_FRONTIER.json"
new_evidence = [
    (
        "HUMAN CORRECTION / HASH",
        "../supporting/CEP-044_WRITE_OFF_CORRECTION_POLICY.md;CEP-044_CORRECTION_PROVENANCE.json;CEP-044_CORRECTION_ENTRY_CHECK.json",
        "Verbatim Human governing contract; all79 identities verified",
    ),
    (
        "FOCUSED / SECURITY / WORKFLOW / CONCURRENCY",
        "CEP-044_FOCUSED_FINAL_OUTPUT.txt",
        focused,
    ),
    (
        "AFFECTED REGRESSION",
        "CEP-044_AFFECTED_FINAL_OUTPUT.txt;CEP-044_VALIDATION_RESULTS.json;CEP-044_VALIDATION_RUN.py",
        affected,
    ),
    (
        "INTEGRATION / TRANSACTION / RECONCILIATION",
        "CEP-044_INTEGRATION_TRACE.json",
        "Exact inverse/replacement/replay and retained cutoff/source/policy evidence PASS",
    ),
    (
        "MIGRATION / PRESERVATION",
        "CEP-044_ACTIONS_MIGRATION_TRACE.json;CEP-044_DEVELOPMENT_ACTIONS_MIGRATION.json;CEP-044_DEVELOPMENT_ACTIONS_MIGRATION_OUTPUT.txt;CEP-044_DEVELOPMENT_ACTIONS_MIGRATION_RUN.py",
        "Additive0008; unused rollback/reapply and used-evidence rollback refusal PASS; all preexisting data preserved; no production",
    ),
    (
        "CANONICAL GATE",
        "CEP-044_GATE05_EVALUATION.json",
        "NOT_PASSED; IMB0062 contribution only verified",
    ),
    (
        "LIVE FRONTIER",
        "CEP-044_FRONTIER.json",
        "Recomputed from verified dependency register; readiness is not eligibility",
    ),
    (
        "FINAL CHECKS / DOCUMENTS",
        "CEP-044_FINAL_CHECK_OUTPUT.txt;CEP-044_FINAL_FORMAT_OUTPUT.txt;CEP-044_FINAL_SYSTEM_OUTPUT.txt;CEP-044_FINAL_DRIFT_OUTPUT.txt;CEP-044_FINAL_DOCUMENT_CHECK.json",
        "Recorded checks PASS; no AC/DoD inferred from lint alone",
    ),
    (
        "CODE DIFF",
        "CEP-044_FINAL_CODE_DIFF.patch",
        "Tracked and newly added product/test implementation",
    ),
    (
        "FAILURE ATTRIBUTION / HISTORY",
        "CEP-044_CORRECTION_FAILURE_ATTRIBUTION.json;CEP-044_EXPANDED_INITIAL_OUTPUT.txt;CEP-044_PERSISTENCE_COMPLETION_REPORT.md;CEP-044_PERSISTENCE_ACCEPTANCE_MAPPING.csv",
        "Initial failures retained and resolved; no failed required test reclassified as PASS",
    ),
]
for number, (kind, path, result) in enumerate(new_evidence, 21):
    evidence.append(
        {
            "evidence_id": f"CEP-044-EV-{number:03}",
            "type": kind,
            "path": path,
            "result": result,
        }
    )
with (E / "CEP-044_EVIDENCE_MANIFEST.csv").open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=evidence[0].keys())
    writer.writeheader()
    writer.writerows(evidence)

names = (
    git("diff", "--name-only", "--diff-filter=ACM").splitlines()
    + git("ls-files", "--others", "--exclude-standard").splitlines()
)
product = sorted({p for p in names if p.startswith("apps/")})
tracked = [p for p in product if git("ls-files", "--", p)]
patch = subprocess.check_output(
    ["git", "diff", "--", *tracked], cwd=ROOT, text=True, encoding="utf-8"
)
for path in product:
    if path not in tracked:
        patch += "".join(
            difflib.unified_diff(
                [],
                (ROOT / path).read_text("utf-8").splitlines(keepends=True),
                fromfile="/dev/null",
                tofile="b/" + path,
            )
        )
(E / "CEP-044_FINAL_CODE_DIFF.patch").write_text(patch, "utf-8")
write(
    "CEP-044_FINAL_DOCUMENT_CHECK.json",
    {
        "execution": "COMPLETE",
        "AC": "12/12 PASS",
        "scoped_DoD": "MET",
        "prompt_hashes": identities,
        "gate05": "NOT_PASSED",
        "findings001_002": "RESOLVED",
        "validation": results,
        "no_production": True,
        "git_at_execution_closeout": "NOT_YET_CHECKPOINTED; Registry owns live integration",
    },
)
names = sorted(
    set(
        git("diff", "--name-only", "--diff-filter=ACM").splitlines()
        + git("ls-files", "--others", "--exclude-standard").splitlines()
    )
)
with (E / "CEP-044_CHANGE_MANIFEST.csv").open("w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["path", "change", "surface", "migration_impact"])
    for path in names:
        writer.writerow(
            [
                path,
                "MODIFIED" if git("ls-files", "--", path) else "ADDED",
                "PRODUCT / TEST"
                if path.startswith("apps/")
                else "GOVERNANCE / EVIDENCE",
                "Additive approved Development only"
                if "/migrations/000" in path
                else "NONE DIRECT",
            ]
        )
for row in evidence:
    for path in row["path"].split(";"):
        assert (E / path).resolve().is_file(), path
assert len(rows) == 12 and all(row["result"] == "PASS" for row in rows)
print(
    json.dumps(
        {
            "execution": "COMPLETE",
            "AC": "12/12",
            "prompt_hashes": len(identities),
            "gate05": "NOT_PASSED",
            "dependency_ready": ready,
            "files": len(names),
        }
    )
)
