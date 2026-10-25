"""Refresh the current partial CEP079 boundary from measured case artifacts.

Unlike the historical035 handoff helper, this does not restore a fixed old state.
It cannot issue completion, sign-off, production authority or Git integration.
"""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).parent
now = datetime.now(timezone.utc).isoformat()
matrix_path = OUT / "44_CASE_READINESS_MATRIX.json"
matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
rows = matrix["rows"]
s = matrix["uat_execution_summary"]
counts = {k: sum(r["uat_execution_result"] == k for r in rows)
          for k in ("PASS", "FAIL", "BLOCKED", "NOT_EXECUTED")}
assert sum(counts.values()) == 44
assert counts["BLOCKED"] == 1, "Review a different boundary explicitly."
blocked_row = next(r for r in rows if r["uat_execution_result"] == "BLOCKED")
number = int(blocked_row["scenario_id"].split("-")[-1])
blocked_artifact = OUT / f"UAT_CASE_{number:03d}_RUNTIME.json"
trace = json.loads(blocked_artifact.read_text(encoding="utf-8"))["continuation_execution"][-1]
assert trace["result"] == "BLOCKED" and trace["classification"] == "BLOCKER-ENVIRONMENT"
blocker = trace["blocker"]
s.update(updated_at=now, attempted=44-counts["NOT_EXECUTED"],
         terminal_results=44-counts["NOT_EXECUTED"],
         fully_executed=counts["PASS"]+counts["FAIL"],
         **{k.lower(): v for k, v in counts.items()})
for result, key in (("PASS", "satisfied_mappings"), ("BLOCKED", "blocked_mappings"),
                    ("NOT_EXECUTED", "unexecuted_mappings")):
    s[key] = sum(len(r["upstream_imb_ids"]) for r in rows if r["uat_execution_result"] == result)
assert s["satisfied_mappings"] + s["blocked_mappings"] + s["unexecuted_mappings"] == 48
matrix_path.write_text(json.dumps(matrix, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

registry = ROOT / "CEP_EXECUTION_REGISTRY.yaml"
source = registry.read_text(encoding="utf-8")
def other_ceps(text):
    return {k: v for k, v in re.findall(
        r"^  (CEP-\d{3}):\n(.*?)(?=^  CEP-\d{3}:\n|^authority_scope:)", text, re.M|re.S)
        if k != "CEP-079"}
before = other_ceps(source)
a = source.index("  CEP-079:\n"); b = source.index("  CEP-080:\n", a)
section = source[a:b]
section = re.sub(r"^      lifecycle: .*", "      lifecycle: BLOCKED_ENVIRONMENT_AFTER_PARTIAL_UAT", section, count=1, flags=re.M)
x = section.index("    blockers:"); y = section.index("    completion_report:", x)
section = section[:x] + (
    f"    blockers:\n    - id: {blocker}\n      type: BLOCKER-ENVIRONMENT\n"
    f"      reason: Chrome extension rejects local file selection at Case{number:03d}; Allow access to file URLs required; no upload occurred.\n"
    f"      evidence: {blocked_artifact.relative_to(ROOT).as_posix()}\n"
    f"      resolution: Human enables extension local-file upload capability; resume{number:03d}, then canonical remaining cases.\n"
    "    remaining_utv:\n    - Case042 create/version/link/download and denied-sensitive-access assertions remain incomplete;043..044 unexecuted.\n"
) + section[y:]
for key in ("attempted", "fully_executed", "pass", "fail", "blocked", "not_executed",
            "defects_discovered", "defects_fixed", "product_defects_discovered",
            "configuration_authority_defects_discovered", "product_defects_fixed"):
    section = re.sub(r"^      "+key+r": .*", f"      {key}: {s[key]}", section, flags=re.M)
section = re.sub(r"^      coverage: .*", f"      coverage: {s['satisfied_mappings']}_OF_48_SATISFIED_{s['blocked_mappings']}_BLOCKED_{s['unexecuted_mappings']}_NOT_EXECUTED", section, flags=re.M)
section = re.sub(r"^      unresolved_environment_blockers: .*", "      unresolved_environment_blockers: 1", section, flags=re.M)
section = re.sub(r"^      focused_validation: .*", "      focused_validation: PRIOR_BILLING5_PROCUREMENT5_SHARED3_MATERIALS_PARTNER8_INVENTORY5_PLUS_TIMEKEEPING6_DOCUMENTS6_AFFECTED_DOCUMENTS3_PASS_RUFF_PASS;ATTRIBUTED_FIXTURE_AND_CONNECTION_TEST_DEBT", section, flags=re.M)
if f"status: BLOCKED_{blocker}" not in section:
    x = section.index("    entry_preparation:")
    section = section[:x] + (
        "    - date: '2026-10-25'\n"
        f"      status: BLOCKED_{blocker}\n"
        "      reason: Continued036..041PASS;042blocked before file selection by extension permission. Finding017 scoped Document form fixed;6focused and3affected regressionsPASS.41PASS/0FAIL/1BLOCKED/2NOT_EXECUTED;45of48mappings satisfied. Entry retained;ENV002 resolved;newENV003. No upload, schema, other CEP or Git writes.\n"
        f"      evidence: {blocked_artifact.relative_to(ROOT).as_posix()}\n"
    ) + section[x:]
source = source[:a] + section + source[b:]
source = re.sub(r"^  current_session_continuation: .*", "  current_session_continuation: BLOCKED_ENV003_BROWSER_FILE_UPLOAD_RESUME042", source, flags=re.M)
source = re.sub(r"^  next_candidate_full_entry_eligibility: .*", "  next_candidate_full_entry_eligibility: CEP079_ENTRY_RETAINED_CURRENT_UPLOAD_CAPABILITY_BLOCKED", source, flags=re.M)
source = re.sub(r"^  boundary_reason: .*", "  boundary_reason: CEP079 actual Case042 file-selection capability blocked;41PASS,1BLOCKED,2NOT_EXECUTED; other CEPs excluded by Human.", source, flags=re.M)
source = re.sub(r"^  resume_cep_after_blocker_resolution: .*", "  resume_cep_after_blocker_resolution: CEP079_CASE042_THEN_CANONICAL043_TO044", source, flags=re.M)
assert len(before) == 85 and before == other_ceps(source)
assert len(re.findall(r"^    execution:\n      status: COMPLETE$", source, re.M)) == 68
assert len(re.findall(r"^    execution:\n      status: PARTIAL$", source, re.M)) == 5
registry.write_text(source, encoding="utf-8")

report = ROOT / "docs/governance/cep/reports/CEP-079_COMPLETION_REPORT.md"
previous = report.read_text(encoding="utf-8")
marker = "<!-- RETAINED_PREVIOUS_REPORT -->"
history = previous.split(marker, 1)[-1] if marker in previous else previous
current = f"""# CEP-079 Completion Report

**EXECUTION PARTIAL — BLOCKED ENVIRONMENT ({blocker})**

As of {now}: **41/44 fully executed; PASS41 / FAIL0 / BLOCKED1 / NOT_EXECUTED2**. Cases001–041 PASS;042 blocked before local file selection;043–044 untouched. **45/48 mappings satisfied;1 blocked;2 unexecuted.** Canonical representative scope only; no exhaustive acceptance or completion claim.

Baseline: main HEAD and local origin/main `5a0a81dafbdd4d6e2142273a87efa45fc9a2c919`; remote freshness not queried. Canonical prompt SHA256 `c02eb0bf068da7a036cf20776fd212be9d5146e994a9e6364ad4ddff9f6fb342` verified. Inherited dirty changes preserved. Entry PASS/GATE09 PASS/EXT0025 READY retained without reassessment. Browser navigation and handoff work; prior ENV002 resolved. Explicit bounded Human Development correction authority retained.

036: ordinary timesheet create/submit; project/activity and site/activity mismatches rejected; exact120minute allocation independently approved and conserved in nonfinancial preview.037: new source-pinned synthetic Payroll run, ordinary lock/calculate/submit, independent review/finalization.038: reverse only new037, equal-opposite2/-2 result, explicit1IRR synthetic correction and independently finalized3IRR replacement; original digests/payslip valid; retry idempotent. Ordinary payslips/history and new2IRR non-posting proposal from retained preparation source reviewed; missing replacement proposal predecessor correctly denied.039: ordinary registered declarative template lifecycle in isolated synthetic project; version1/2 retained and retired.040: actual Chrome1440/1024/390 fa/RTL/layout/keyboard, mobile dependency form/Jalali/Persian validation; no duplicate employee write; viewport reset.041: scoped ProjectA positive, same-tenant ungranted/foreign tenant denial, admin denial, maker approval403, protected dual-control denial with unchanged role count, independent owner approval and Browser readback.

Finding017: Document upload/link form incorrectly used organization-only source-permission checks, leaving project-scoped actor with no target choices. `apps/documents/forms.py` now uses existing scoped permission entry and tenant/object-filtered target querysets. Owning target services and Field Operations capture/draft guards remain authoritative. Focused regression file `apps/documents/test_cep079_form_scope.py`; corrected Browser offers only actor-granted A/B projects and related sources. **17 defects discovered/corrected (11 product,6 configuration/authority);0 unresolved UAT-blocking defects;1 environment blocker.** Prior16 findings and actual corrections remain in case evidence and retained history below.

Validation: Timekeeping6/6 PASS2.257s; new Document scope tests6/6 PASS0.733s, including tenant/object/permission/inactive-membership/contract selection; affected Document upload/version/secure-download PASS and isolated endpoint/link regressions2/2 PASS4.123s. In the initial combined3test run, the passing download test calls response.close(), closing the PostgreSQL test connection; following2failed in setUp before changed form. Both rerun separatelyPASS; no product regression inferred. Prior Billing5/Procurement5/shared Workflow3/MaterialsPartner8/Inventory5 PASS retained; two earlier unrelated fixture failures remain attributed in024. Ruff check/format PASS; Django checks0issues. No broad/full regression claim. Case001–035 retained54 evidence artifacts match precontinuation manifest hashes.

**Stop:** fileChooser.setFiles rejected the exact approved synthetic JPEG because the Chrome ChatGPT extension lacks **Allow access to file URLs**. No file selected, uploaded, or new Document/Version/Link created for042. Ordinary UI assertions cannot be replaced with a service/HTTP-only PASS. Enable that extension option, resume the same042 form, complete version/link/download/negative assertions, then043–044. Tab marked handoff successfully. This is a current execution capability blocker, not an entry reassessment.

Acceptance: AC2/4/5/6 PASS; AC1 NOT_MET; AC3 PARTIAL (**4/6 PASS**). Scoped DoD NOT_MET. Case042 incomplete assertions and043–044 remain UTV. Full completion requires44 executed,48 mappings satisfied, no unresolved blocker, canonical AC and scoped DoD supported. GATE10 PASS, Human Sign-off, Production Certification and Cutover are not issued.

Registry/matrix/manifests/evidence and acceptance mappings synchronized; other85 CEP records unchanged; program summary recomputed and unchanged68 COMPLETE/5 PARTIAL. No next CEP; Human scope is CEP079 only. This continuation changed only the bounded Document form/test plus native synthetic workflows and evidence. No schema changes/migrations, add/commit/push/reset/stash/clean, Production action, Audits01–20 or unrelated refactoring.

The following report sections are retained historical snapshots; the current result above supersedes them.

{marker}
"""
report.write_text(current + history, encoding="utf-8")

evidence = ROOT / "docs/governance/cep/evidence/CEP-079_EVIDENCE_MANIFEST.csv"
with evidence.open(encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f); fields = reader.fieldnames; manifest_rows = list(reader)
known = {r["path"] for r in manifest_rows}
next_id = max(int(r["evidence_id"].split("-")[-1]) for r in manifest_rows) + 1
for file in sorted(OUT.glob("UAT_CASE_*")) + [OUT / "TIMEKEEPING_AFFECTED_VALIDATION.json", OUT / "continuation_closeout.py"]:
    relative = file.relative_to(ROOT).as_posix()
    if relative not in known:
        manifest_rows.append(dict(evidence_id=f"CEP-079-EV-{next_id:03d}", path=relative,
                                  sha256="", kind="Retained actual continuation evidence/helper", result="RECORDED"))
        next_id += 1
for row in manifest_rows:
    file = ROOT / row["path"]
    row["sha256"] = hashlib.sha256(file.read_bytes()).hexdigest()
    if file.name == "44_CASE_READINESS_MATRIX.json": row["result"] = "PARTIAL_BLOCKED_ENVIRONMENT"
    if file.name.startswith("UAT_CASE_"):
        row["result"] = rows[int(file.name.split("_")[2])-1]["uat_execution_result"]
with evidence.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(manifest_rows)

accept = ROOT / "docs/governance/cep/evidence/CEP-079_ACCEPTANCE_MAPPING.csv"
with accept.open(encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f); fields = reader.fieldnames; mapping_rows = list(reader)
for row in mapping_rows:
    row["evidence"] = f"CEP-079-EV-001..{next_id-1:03d}"
    if row["criterion"] == "AC1": row.update(status="NOT_MET", result="41PASS/1BLOCKED/2NOT_EXECUTED;45of48 mappings satisfied;042 actual file-upload capability blocked.")
    if row["criterion"] == "AC3": row.update(status="PARTIAL", result="001..041 actually executed;042 incomplete;043..044 unexecuted. No service-only UI substitution.")
with accept.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(mapping_rows)
status = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, text=True)
with (ROOT / "docs/governance/cep/evidence/CEP-079_CHANGE_MANIFEST.csv").open("w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f); writer.writerow(["path", "change", "purpose"])
    for line in status.splitlines():
        writer.writerow([line[3:], "MODIFIED" if line[:2] != "??" else "ADDED_OR_ADVANCED_EXISTING_UNTRACKED",
                         "Bounded CEP079 correction, validation or retained evidence; inherited changes preserved"])
print(f"Synchronized {s['fully_executed']}/44 executed;{s['satisfied_mappings']}/48 satisfied;{blocker};other85CEPs unchanged")
