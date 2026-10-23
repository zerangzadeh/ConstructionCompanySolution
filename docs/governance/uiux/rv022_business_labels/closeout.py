"""Verify and append the approved RV-022 presentation delta; no business writes."""
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path(__file__).resolve().parent
BASE = OUT.parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(BASE / "rv007_controlled_time"))
from support import guard, snapshot, REAL_NOW
from apps.organizations.models import OrganizationMembership
from apps.organizations.authorization import effective_scope_grants, membership_permission_codes


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def append(path, key, data):
    text = path.read_text(encoding="utf-8")
    assert "\n" + key + ":" not in text
    (OUT / ("entry_" + path.name)).write_bytes(path.read_bytes())
    value = json.dumps(data, ensure_ascii=False, indent=2)
    path.write_text(text.rstrip() + "\n\n" + key + ":\n" + "\n".join("  " + s for s in value.splitlines()) + "\n", encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8").split("\n" + key + ":\n", 1)[1]) == data


guard()
assert not (OUT / "FINAL_RECONCILIATION.json").exists()
tests = ET.parse(OUT / "focused_final.xml").getroot().find("testsuite")
assert tests.attrib["tests"] == "12" and tests.attrib["failures"] == "0" and tests.attrib["errors"] == "0"
observations = read("BROWSER.json")
assert len(observations) == 5
for row in observations:
    facts = row["facts"]
    assert facts["mainCount"] == 1 and facts["h1"] == 1 and not facts["duplicateIds"]
    assert facts["pageWidth"] <= facts["clientWidth"]
    assert "legacy_approval" not in facts["primaryText"]
    assert "legacy_approval" in facts["advancedText"]
    assert "تأیید گزارش روزانه" in facts["primaryText"]
assert observations[-1]["facts"]["advancedOpen"]
assert observations[-1]["facts"]["table"]["scrollLeft"] == -40
assert not [r for r in read("RUNTIME_LOGS_FINAL.json") if r["level"] == "error"]
membership = OrganizationMembership.objects.get(user__username="uiux.persona.tenant-admin", organization__slug="demo-construction-01")
save("ACTOR.json", {"alias":membership.user.username,"membership_status":membership.status,"organization":str(membership.organization_id),"permissions":sorted(membership_permission_codes(membership)),"scopes":list(effective_scope_grants(membership).values("scope_type","project_id","site_id"))})
before, after = read("DATA_BEFORE.json"), snapshot()
changed = {key: {"before_count":len(before.get(key,{})),"after_count":len(after.get(key,{}))} for key in before.keys() | after.keys() if before.get(key,{}) != after.get(key,{})}
assert not changed, changed
entry = read("ENTRY.json")
prior_changes = [p for p,h in entry["hashes"].items() if p.startswith("docs/governance/uiux/wave_d_e/") and (not (ROOT/p).is_file() or hashlib.sha256((ROOT/p).read_bytes()).hexdigest() != h)]
assert not prior_changes,prior_changes
save("EVIDENCE_RECORD.json", {"evidence_id":"RV-EV-057","scenario_id":"RV-022","result":"PASS","decision":"PD-WD-022 APPROVED OPTION 1","authority":"PRODUCT_DECISION.md","environment":"Development / Non-Production","build":entry["head"],"dirty_source":"ENTRY.json + SOURCE_BASELINE_SUPPLEMENT.json","browser":"ChatGPT in-app Browser, retained browser id 2","browser_version":"Prior selected-browser reduced User-Agent Chromium 155.0.0.0; full engine build not exposed; no fresh version echo in this delta","actor":"ACTOR.json","viewports":[r["viewport"] for r in observations],"preconditions":["Retained actual Tenant Admin and organization scope; existing published Workflow version","Existing registered names/outcomes and original configuration only; no fixture/grant creation"],"steps":["Normal sign-in with existing DPAPI credential","Read populated published version at desktop/tablet/mobile","Verify business names replace primary keys while advanced disclosure retains exact technical values","Use ArrowLeft on focused transition region and Enter to open/close advanced disclosure","Check foreign-tenant identifier fails with Development 404"],"expected":"Approved information priority only; immutable configuration and authorization remain unchanged","actual":"Business-labelled process overview, step list and source/target/outcome table primary; technical identifiers/configuration secondary; mobile table scroll contained; no page overflow, duplicate IDs or unexpected console errors","screenshots":[r["name"]+".jpg" for r in observations]+["review_final_desktop.jpg"],"keyboard":"KEYBOARD.json","browser_observations":"BROWSER.json","tenant_boundary":"cross_tenant_denied.ax.txt; existing automated cross-tenant/permission tests PASS","findings":["UIUX-F-048"],"business_mutation":False,"schema_migration":"NONE"})
summary = {"recorded_on":"2026-10-23","decision":"PD-WD-022 APPROVED OPTION 1; implemented and runtime-verified","RV-022":"PASS","UIUX-F-048":"RUNTIME_VERIFIED_RESOLVED_WITHIN_APPROVED_INFORMATION_PRIORITY","evidence":"rv022_business_labels/EVIDENCE_RECORD.json","report":"rv022_business_labels/COMPLETION_REPORT.md","product_decision":"rv022_business_labels/PRODUCT_DECISION.md","supersedes":"Only prior RV-022/F-048 BLOCKED_PRODUCT_DECISION; prior artifacts retained","wave_d":"WAVE_D_BLOCKED_AUTHORIZATION_FIXTURE_AND_TEST_DATA","wave_d_counts":{"PASS":2,"BLOCKED":2,"PARTIAL":0},"remaining":{"RV-016":"BLOCKED_AUTHORIZATION_FIXTURE","RV-021":"BLOCKED_TEST_DATA"},"unresolved_product_decisions":0,"wave_e":"WAVE_E_NOT_STARTED_DUE_TO_WAVE_D_DEPENDENCY","tests":"12 PASS: 2 focused presentation cases + 10 existing administration regressions","baseline_debt":"18 BASELINE_PREEXISTING retained; no rerun/reclassification","new_observed_attributable_or_indeterminate_regressions":0,"business_rules_authorization_identifiers_execution":"UNCHANGED","schema_migration":"NONE","production":"UNTOUCHED","human_signoff":"NOT_EXECUTED; this approval is a bounded Product Decision only","cep_registry_roadmap":"UNCHANGED","cep078079":"NOT_EXECUTED","git_writes":"NOT_EXECUTED","next_action":"STOP; Wave E gate still fails separate fixture prerequisites"}
append(BASE / "UIUX_RUNTIME_VALIDATION_RESULTS.yaml", "rv022_business_label_revalidation", summary)
append(BASE / "UIUX_FINDINGS_REGISTER.yaml", "rv022_business_label_resolution", {"recorded_on":"2026-10-23","finding":"UIUX-F-048","current_disposition":"RUNTIME_VERIFIED_RESOLVED_WITHIN_APPROVED_INFORMATION_PRIORITY","decision":"rv022_business_labels/PRODUCT_DECISION.md","report":summary["report"],"evidence":summary["evidence"],"historical_finding_and_pending_decision_evidence":"PRESERVED_UNCHANGED","new_findings":0,"other_findings":"UNCHANGED; prior F-090 partial closure and ESS/Knowledge blockers retained"})
append(BASE / "UIUX_ROOT_PATTERN_IMPACT_MAP.yaml", "rv022_approved_business_review_delta", {"recorded_on":"2026-10-23","finding":"UIUX-F-048","patterns":["RP-C01-TECHNICAL-LANGUAGE-LEAK","RP-C02-MODEL-REPRESENTATION-EXPOSED","RP-C17-CONFIGURATION-NOT-VISUALIZED"],"scope":"Registered business names and read-only labelled transition paths on Workflow version review; no graphical designer or authoring/runtime semantics changed","evidence":summary["evidence"],"report":summary["report"]})
path=BASE / "UIUX_RUNTIME_VALIDATION_RESULTS.yaml"
text=path.read_text(encoding="utf-8")
old="Current Wave D/E disposition is wave_d_e_serial_execution; earlier sections remain historical."
assert old in text
path.write_text(text.replace(old,"Current RV-022 and Wave D/E counts are rv022_business_label_revalidation; earlier sections remain historical.",1),encoding="utf-8")
for name in ("UIUX_RUNTIME_VALIDATION_WAVE_D_REPORT.md","UIUX_RUNTIME_VALIDATION_WAVE_E_REPORT.md"):
    path=BASE/name
    (OUT/("entry_"+name)).write_bytes(path.read_bytes())
    if "WAVE_D" in name:
        content="# Wave D current runtime disposition — 2026-10-23\n\n**WAVE_D_BLOCKED_AUTHORIZATION_FIXTURE_AND_TEST_DATA**: **2 PASS, 2 BLOCKED**.\n\nRV-022 is now PASS following the approved PD-WD-022 information-priority change.\nF-048 is resolved within that bounded scope; no Product Decision remains pending.\nRV-020 remains PASS. RV-016 and RV-021 remain blocked by their separate fixtures.\n\nCurrent follow-up: [RV-022 completion report](rv022_business_labels/COMPLETION_REPORT.md).\nPrior serial-attempt evidence and the remaining blockers:\n[historical Wave D/E report](wave_d_e/COMPLETION_REPORT.md).\nWave E entry gate still fails. No CEP or Production authority is issued.\n"
    else:
        content="# Wave E current entry gate — 2026-10-23\n\n**WAVE_E_NOT_STARTED_DUE_TO_WAVE_D_DEPENDENCY**. RV-025: **0 executed, 1 not started**.\n\nPD-WD-022 is approved and RV-022 now PASS. That removes only the Workflow Product\nDecision blocker. Wave D still has RV-016 authorization-fixture and RV-021\nKnowledge test-data/platform-session blockers, so neither permitted entry state\n(complete D, or partial D due solely to independent Product Decisions) is reached.\n\nNo Wave E representative sweep or responsive coverage is claimed. The 18 retained\nbaseline failures remain explicit and are not the cause of this gate rejection.\n\n[Current RV-022 follow-up](rv022_business_labels/COMPLETION_REPORT.md);\n[prior Wave D/E evidence](wave_d_e/COMPLETION_REPORT.md).\nNo Production, CEP, grant, migration or Git-write authority is inferred. **STOP**.\n"
    path.write_text(content,encoding="utf-8")
save("FINAL_RECONCILIATION.json",summary)
changed_sources=[p for p,h in entry["hashes"].items() if (ROOT/p).is_file() and hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
allowed={"apps/workflows/administration_views.py","apps/workflows/test_cep046_administration.py","templates/workflows/administration/detail.html","docs/governance/uiux/UIUX_RUNTIME_VALIDATION_RESULTS.yaml","docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml","docs/governance/uiux/UIUX_ROOT_PATTERN_IMPACT_MAP.yaml","docs/governance/uiux/UIUX_RUNTIME_VALIDATION_WAVE_D_REPORT.md","docs/governance/uiux/UIUX_RUNTIME_VALIDATION_WAVE_E_REPORT.md"}
assert set(changed_sources) <= allowed,changed_sources
index_unchanged=hashlib.sha256((ROOT/".git/index").read_bytes()).hexdigest()==entry["index_sha256"]
head_unchanged=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()==entry["head"]
staged_content_unchanged = subprocess.run(["git","diff","--cached","--quiet"],cwd=ROOT).returncode == 0 and not [s for s in entry["status"].splitlines() if s and s[0] not in {" ","?"}]
assert head_unchanged and staged_content_unchanged
save("INTEGRITY.json",{"at":str(REAL_NOW()),"business_data_changes":changed,"prior_wave_d_e_artifact_changes":prior_changes,"changed_source_paths_since_late_entry":changed_sources,"prechange_source_limitation":"SOURCE_BASELINE_SUPPLEMENT.json; original source matches accepted baseline via read-only HEAD and Git working-tree line endings","new_product_file":"apps/workflows/administration_presentation.py","index_bytes_unchanged":index_unchanged,"index_staged_content_unchanged":staged_content_unchanged,"index_note":"Index bytes differ; entry and closeout both have no staged changes relative to the unchanged HEAD. Consistent with stat-cache metadata refresh during allowed read-only inspection; exact writer not established. No index-byte preservation claim.","head_unchanged":head_unchanged,"branch":"main","configured_development_migration_plan_empty":True,"production":"UNTOUCHED","git_write_operations":"add/commit/push/merge/rebase/reset/clean/stash/branch/worktree NOT_EXECUTED"})
print("RV-022 PASS; F-048 resolved within approved scope; Wave D 2 PASS / 2 BLOCKED; Wave E not started.")
