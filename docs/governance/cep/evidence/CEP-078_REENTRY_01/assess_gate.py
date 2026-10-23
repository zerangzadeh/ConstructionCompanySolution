"""Evaluate exact GATE-07 build/convergence criteria from existing evidence."""
import csv
import hashlib
import io
import json
import re
import sys
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
ARCHIVES = Path(r"E:\ERP_Construction_Documents\New Version\BONIRA_TRUE_LATEST_STATE_RECONSTRUCTION_20261013\Consolidated_Packages")
entry = json.loads((OUT / "ENTRY.json").read_text(encoding="utf-8"))
prior = json.loads((OUT.parent / "CEP-078_ENTRY_REVIEW.json").read_text(encoding="utf-8"))
test = json.loads((OUT / "GATE07_FOCUSED.json").read_text(encoding="utf-8"))
retry = json.loads((OUT / "GATE07_RETRY.json").read_text(encoding="utf-8"))
assert test["counts"] == {"PASS": 41, "FAIL": 1, "SKIP": 0}
assert retry["exit_code"] == 0
assert next(c for c in test["cases"] if c["result"] == "FAIL")["diagnostic"].startswith("UnicodeEncodeError")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def archive_rows(archive, member):
    p = ARCHIVES / archive
    assert sha(p) == prior["approved_recovery"]["archives"][archive]["sha256"]
    with zipfile.ZipFile(p) as z:
        raw = z.read(member)
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))), {"archive": str(p), "archive_sha256": sha(p), "member": member, "member_sha256": hashlib.sha256(raw).hexdigest()}


gates, gate_source = archive_rows("BONIRA_IMPLEMENTATION_ROADMAP_CONSOLIDATED_LATEST.zip", "BONIRA_IMPLEMENTATION_GATE_REGISTER.csv")
gate = next(r for r in gates if r["Gate ID"] == "GATE-07")
backlog, backlog_source = archive_rows("BONIRA_FINAL_IMPLEMENTATION_MASTER_BACKLOG_CONSOLIDATED_LATEST.zip", "BONIRA_FINAL_IMPLEMENTATION_MASTER_BACKLOG.csv")
ui_gaps, ui_source = archive_rows("BONIRA_UI_WORKSPACE_ARCHITECTURE_CONSOLIDATED_LATEST.zip", "BONIRA_UI_CURRENT_TO_TARGET_GAP_REGISTER.csv")
browser_gap = next(r for r in ui_gaps if r["Gap ID"] == "UIGAP-025")
old_gate = json.loads((OUT.parent / "CEP-056_GATE07.json").read_text(encoding="utf-8"))
owners = old_gate["primary_owners"]
surfaces = {
    "0003": ("core/home.py", "core/test_home.py", "Canonical links only, no business aggregates; permission/scope filtering and safe source-error state"),
    "0004": ("apps/organizations/context.py", "apps/organizations/test_cep016_context.py", "Persistent authorized context; malformed/cross-tenant context denies; context never grants scope"),
    "0005": ("templates/components/navigation_links.html", "core/test_cep017_navigation.py", "43-node target navigation and shared breadcrumbs; no new business actions"),
    "0007": ("apps/workflows/personal_workspaces.py", "apps/workflows/test_cep018_workspaces.py", "Assigned tasks distinct from own source request projection; explicit manager/team scope"),
    "0011": ("apps/workflows/administration_views.py", "apps/workflows/test_cep046_administration.py", "Existing lifecycle services and immutable history; tenant/platform/direct-action boundaries"),
    "0012": ("apps/organizations/context.py", "apps/organizations/test_cep016_context.py", "Choices intersect scope; stale parent choices rejected server-side; cascade endpoint scoped"),
    "0013": ("core/forms.py", "core/test_cep003_localization_accessibility.py", "Jalali UI to Gregorian storage only; RTL/localized primitive contracts retained"),
    "0014": ("core/templatetags/form_accessibility.py", "core/test_cep003_localization_accessibility.py", "Help/error associations preserve existing IDs; runtime conformance remains UTV"),
    "0015": ("templates/base.html", "core/test_cep017_navigation.py", "Shared responsive drawer close/Escape/breadcrumb contract; runtime acceptance remains UTV"),
    "0084": ("apps/workforce/ess_dashboard.py", "apps/workforce/test_cep053.py", "Explicit current identity bridge, source status/deep links and separate unavailable/error states"),
    "0085": ("apps/workforce/ess_timekeeping.py", "apps/workforce/test_cep063.py", "Native leave reservation, attendance correction and timesheet lifecycle; absent policy stays unavailable"),
    "0086": ("apps/payroll/ess_services.py", "apps/payroll/test_cep054.py", "Finalized own artifact/export only; draft/peer/identity denial and immutable source"),
    "0087": ("apps/workforce/personal_change_services.py", "apps/workforce/test_cep055.py", "Own source status adapters hide internal metadata; no source state overwrite"),
    "0088": ("apps/workforce/personal_change_services.py", "apps/workforce/test_cep055.py", "Five governed field families require workflow acceptance; sensitive fields, assignment and tenant denial"),
    "0089": ("apps/workforce/certificate_services.py", "apps/workforce/test_cep056.py", "Missing renderer/activation cannot enable or generate; DMS cannot bypass own certificate case scope"),
    "0090": ("apps/workforce/certificate_services.py", "apps/workforce/test_cep056.py", "Own read-only employment/qualification/assignment evidence; no broad back-office grant"),
    "0091": ("apps/workforce/ess_timekeeping.py", "apps/workforce/test_cep068_mission.py", "Native Mission source lifecycle; unapproved monetary policy denied; routed status projection hides financial/reviewer metadata and GET does not mutate financial models"),
    "0092": ("apps/payroll/ess_services.py", "apps/payroll/test_cep054.py", "Missing category/route creates no orphan; assigned response atomicity/privacy; no financial mutation"),
    "0093": ("apps/workforce/ess_services.py", "apps/workforce/test_cep026_ess_privacy.py", "Only explicit User/Person/current relationship; peer/foreign uniform denial and identifier masking"),
}
# Resolve actual context module from the existing test import rather than invent it.
context_test = (ROOT / "apps/organizations/test_cep016_context.py").read_text(encoding="utf-8")
assert "context" in context_test
context_paths = [p for p in (ROOT / "apps/organizations").glob("*context*.py") if not p.name.startswith("test")]
assert context_paths
for key in ("0004", "0012"):
    _, tests, claim = surfaces[key]
    surfaces[key] = (context_paths[0].relative_to(ROOT).as_posix(), tests, claim)
rows = []
for imb in gate["Required IMB IDs"].split("; "):
    number = imb[-4:]
    source, tests, proof = surfaces[number]
    assert (ROOT / source).is_file() and (ROOT / tests).is_file()
    item = next(r for r in backlog if r["Backlog ID"] == imb)
    owner = owners[imb]
    report = ROOT / f"docs/governance/cep/reports/{owner}_COMPLETION_REPORT.md"
    assert report.is_file()
    block = re.search(r"^  " + owner + r":\n(.*?)(?=^  CEP-|^authority_scope:)", entry["registry_before"], re.M | re.S).group(1)
    assert "      status: COMPLETE\n" in block
    rows.append({"imb": imb, "title": item["Title"], "canonical_target": item["Target State"], "owner": owner, "current_source": source, "source_sha256": sha(ROOT / source), "test_source": tests, "test_sha256": sha(ROOT / tests), "retained_package_report": report.relative_to(ROOT).as_posix(), "report_sha256": sha(report), "current_convergence_assertions": proof, "current_test_evidence": "GATE07_FOCUSED.json + GATE07_RETRY.json; original business assertions unchanged", "result": "PASS_IMPLEMENTED_AND_CONDITIONAL_UNAVAILABLE_SCOPE", "runtime_browser_result": "UTV"})
assert len(rows) == 19
assessment = {
    "at": datetime.now(timezone(timedelta(hours=3, minutes=30))).isoformat(),
    "gate": gate, "sources": [gate_source, backlog_source, ui_source], "required_imb_assessments": rows,
    "decision": "PASS_FOR_CEP078_DEVELOPMENT_IMPLEMENTED_CAPABILITY_SCOPE",
    "global_gate_status": "NOT_READY_RETAINED; no global activation readiness or Production claim",
    "scope": "All 19 required implemented shared-UI/ESS framework contributions; available source-owned journeys and truthful unavailable/error/denied states. No official certificate generation or actual mission monetary activation.",
    "gate_evidence_classes": {"backend_authorization": "PASS: direct URL, peer/foreign/context, manager/team, sensitive-data guards", "UI_states": "PASS: source state/deep links plus empty/error/unavailable/denied", "Persian_RTL_Jalali": "PASS: existing component/source UI response assertions", "source_authority": "PASS: source services own all state/calculation/financial mutations; ESS read projections cannot widen authority", "final_browser_runtime": "UTV; explicitly not an entry requirement of GATE07 itself"},
    "external_activation_applicability": {
        "EXT-0014": "Effective source Leave Policy remains required for balance/request activation; current test proves normal native reservation under explicit test policy and unavailable state without policy. No live policy or balance invented.",
        "EXT-0016": "Actual Mission monetary activation excluded and denied without policy; real source-only request/status and synthetic approved-binding projection tested. No live monetary routing.",
        "EXT-0019": "Official generation activation excluded and unavailable; current missing renderer/activation test denies enable/generate; no official wording/template/signature assumed.",
    },
    "current_tests": {"distinct_business_cases_pass": 42, "initial": "41 PASS / 1 legacy evidence-export UnicodeEncodeError", "retry": "1/1 PASS with only historical trace export redirected UTF-8; original 41 results not repeated", "remaining_product_or_test_failures_in_selection": 0, "infrastructure_debt": "Original failure and historical trace restoration retained in TEST_EXPORT_RECOVERY.json; not a product fix"},
    "baseline_debt": "Original 18 and separate statutory/Projects assertion debt retained unchanged; no broader regression PASS",
    "prior_finding_001": "RESOLVED_FOR_CEP078_SCOPED_ENTRY_ONLY; global NOT_READY preserved",
    "no_circular_gate": "Runtime browser/UAT PASS is not demanded before entry; no approval, source-authority, scope or legal semantics changed",
    "next": "Establish EXT-0024 exact canonical browser/device/viewport/accessibility matrix and identities, then formal entry; no runtime yet",
    "canonical_browser_gap": browser_gap,
}
(OUT / "GATE07_CONVERGENCE.json").write_text(json.dumps(assessment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
with (OUT / "GATE07_CONVERGENCE.csv").open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
print("GATE07 scoped convergence: 19/19 contributions supported; 42 distinct current tests PASS. Global activation readiness unchanged.")
