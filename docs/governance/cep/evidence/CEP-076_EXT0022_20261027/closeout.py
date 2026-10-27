"""Close only the executed CEP076 and its objective gate contributions."""

import copy
import csv
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
import subprocess

import yaml

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
REL = OUT.relative_to(ROOT).as_posix()
PRE = ROOT/"docs/governance/cep/evidence/EXT0022_DEVELOPMENT_20261027"
NOW = datetime.now(UTC)
entry = json.loads((OUT/"ENTRY.json").read_text())
sources = json.loads((ROOT/entry["source_manifest"]).read_text())
assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in sources.items())
assert "1 passed" in (OUT/"RUNTIME_ATTEMPT_01.txt").read_text()
scenario = json.loads((OUT/"SCENARIO.json").read_text())
assert scenario["result"] == "PASS"
assert len(scenario["steps"]) == 8
assert all(step["result"]=="PASS" for step in scenario["steps"])
assert scenario["acl_after"]["status"]=="PASS"
assert len(scenario["synthetic_access_audit_trace"])==5
assert scenario["incident_id"]!=json.loads((PRE/"SCENARIO.json").read_text())["incident_id"]

# Verify receipt bytes, process-exit persistence and recursive ACLs now, outside
# the pytest process. The failed072 attempt is preserved under a new retention
# hold receipt, never silently changed into a passing scenario.
import sys
sys.path.insert(0,str(ROOT))
from scripts.cep070_recovery_controls import verify_private_tree

sink = Path(scenario["sink"])
assert sink.parent==Path("E:/BONIRA_Operations/EXT0022")
assert all(hashlib.sha256((sink/n).read_bytes()).hexdigest()==h
           for n,h in scenario["receipt_hashes"].items())
assert (sink/"incident.json").read_bytes()==(OUT/"SCENARIO.json").read_bytes()
acl=verify_private_tree(sink)
retained=[]
start=datetime.fromisoformat(json.loads((PRE/"ENTRY.json").read_text())["at"])
for directory in sink.parent.iterdir():
    if not directory.is_dir() or directory.stat().st_ctime < start.timestamp():
        continue
    verified=verify_private_tree(directory)
    records={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.glob("*.json")}
    hold={"authority":"EXT-0022-HUMAN-20261027","created_at":NOW.isoformat(),
          "minimum_retain_until":(NOW+timedelta(days=30)).isoformat(),
          "records":records,"classification":"qualification-attempt-evidence; original attempt verdict unchanged",
          "purge_authorized":False}
    with (directory/"qualification-retention-hold.json").open("x",encoding="utf-8") as stream:
        stream.write(json.dumps(hold,indent=2))
        stream.flush()
        import os
        os.fsync(stream.fileno())
    retained.append({"directory":str(directory),"records":len(records),"acl":verified,
                     "retain_until":hold["minimum_retain_until"],"successful_incident_present":(directory/"incident.json").exists()})

claims = [
    "Fresh actual eight-step runtime drill proves logging/alerts/runbooks/existing access governance",
    "Exact scenario/target, Python/Django/Psycopg/pytest runtime and1214 source hashes retained in entry",
    "Executed live loopback WSGI, real unavailable sink/DB port, isolated PostgreSQL services and real elapsed grant expiry",
    "Timestamped PASS steps, fixed-field receipts, five source-linked audit events and process-exit persistence retained",
    "072 failed retention attempt remains FAILED and repaired before076 entry;076 has zero failed runtime attempts",
    "Only executed target is PASS; Production, equivalence and future30-day elapsed retention remain UTV",
]
result={"at":NOW.isoformat(),"client_date":"2026-10-27","cep":"CEP-076",
        "execution_state":"EXECUTION COMPLETE","imbs":["IMB-0106"],
        "branch":"main","head":entry["head"],"scope":"EXT0022_APPROVED_DEVELOPMENT_ONLY",
        "ac":{f"AC{i}":{"status":"PASS_APPROVED_TARGET","proof":proof} for i,proof in enumerate(claims,1)},
        "dod":"MET_ACTUAL_EXECUTION_EVIDENCE","scenario_steps":8,
        "scenario_seconds":round((datetime.fromisoformat(scenario["ended_at"])-datetime.fromisoformat(scenario["started_at"])).total_seconds(),6),
        "runtime_command":".venv-2/Scripts/python.exe -m pytest scripts/cep072_qualification_scenarios.py --reuse-db -q --disable-warnings",
        "runtime_result":"1 passed; eight actual runtime steps PASS",
        "source_freeze":{"files":len(sources),"before":"PASS","after":"PASS","product_changes_during076":0},
        "post_process_receipt_verification":"PASS","post_process_acl":acl,
        "retained_attempts":retained,"open_in_scope_findings":[],
        "remaining_utv":["Production operations/equivalence, destination and certification are not established by this approved Development scenario",
                         "Actual30-day elapsed retention/future operation remains unverified; durable restricted copies retained with explicit hold receipts",
                         "Browser/performance/load outside this CEP's approved scenario not exercised"],
        "production_actions":"NOT_EXECUTED","production_certification":"NOT_EXECUTED",
        "human_signoff":"NOT_EXECUTED","human_post_run_review":"NOT_INFERRED_FROM_POLICY_APPROVAL",
        "migration":"NONE","git_writes":"NOT_EXECUTED",
        "gate08":"NOT_PASSED;074/075 required contributions remain unexecuted",
        "gate11":"NOT_PASSED;required Production readiness and external evidence incomplete",
        "next_executable_frontier":[]}
(OUT/"RESULT.json").write_text(json.dumps(result,indent=2),encoding="utf-8")

registry_path=ROOT/"CEP_EXECUTION_REGISTRY.yaml"
original=registry_path.read_text(encoding="utf-8")
before=yaml.safe_load(original)
registry=copy.deepcopy(before)
item=registry["ceps"]["CEP-076"]
assert item["dependency_status"].startswith("SATISFIED_")
assert registry["ceps"]["CEP-072"]["execution"]["status"]=="COMPLETE"
item["execution"].update(status="COMPLETE",lifecycle="CLOSED_VERIFIED_NONPRODUCTION")
item["eligibility_status"]="COMPLETE_APPROVED_DEVELOPMENT_DRILL"
item["acceptance"]={"passed":6,"total":6,"status":"PASS_ACTUAL_APPROVED_TARGET"}
item["dod"]="MET_ACTUAL_EXECUTION_EVIDENCE"
item["blockers"]=[]
item["remaining_utv"]=result["remaining_utv"]
item["completion_report"]={"path":"docs/governance/cep/reports/CEP-076_COMPLETION_REPORT.md",
                           "evidence_presence":"VERIFIED_FRESH_RUNTIME_8_STEPS_SOURCE_FREEZE_RECEIPTS_AUDIT"}
item["last_execution"]={"branch":"main","sha":entry["head"]}
item["git"].update(committed=False,pushed=False,merged_to_main=False,current_session_changes_committed=False,
                   remote_main_evidence="CURRENT_WORK_UNCOMMITTED_NO_REMOTE_CLAIM")
item["updated_at"]="2026-10-27"
item["frontier_review"]={"at":NOW.isoformat(),"head":entry["head"],"result":"COMPLETE_APPROVED_TARGET",
                         "evidence":REL+"/RESULT.json","production_authorized":False}
for status,reason in [
    ("STARTED","Fresh bounded runtime scenario executed after canonical identity,072 completion,EXT0022 and source freeze entry PASS; no product/config changes."),
    ("COMPLETE","Actual eight-step WSGI/alert/fallback/dependency recovery/access revoke+audit/real UTC expiry/retention scenario PASS.6of6AC and actual-evidence DoD MET.1214frozen sources unchanged; five synthetic source audit events retained before rollback; all receipts persist after process exit. No Production equivalence inferred."),
    ("CLOSED_VERIFIED","Report,mappings,manifests and Registry synchronized; scoped IMB0106 contribution PASS; global08/11 remain NOT_PASSED. No in-scope failure; requested chain complete; frontier empty.")]:
    item["history"].append({"date":"2026-10-27","status":status,"reason":reason,"evidence":REL+"/RESULT.json"})

for gate in ("GATE-08","GATE-11"):
    g=registry["gates"][gate]
    assert g["status"]=="NOT_PASSED"
    g["evidence"]=REL+"/RESULT.json"
    g["required_imb_status"]["IMB-0106"]="PASS_APPROVED_DEVELOPMENT_CEP076_PRODUCTION_UNQUALIFIED"
    g["history"].append({"date":"2026-10-27","status":"NOT_PASSED",
        "reason":"076 IMB0106 actual approved Development contribution PASS.074/075 unexecuted; Production readiness/external evidence incomplete. Prior073/077/078/079 results retained without rerun; no global Gate/Production/Human Sign-off inference.","evidence":REL+"/RESULT.json"})
registry["gates"]["GATE-08"]["note"]="073/076/077/078 approved scoped contributions PASS.074/075 required runtime evidence remains unexecuted; no global or Production qualification."
registry["gates"]["GATE-11"]["note"]="072/076 approved Development operating outcome/drill PASS; Production operating qualification not inferred.069/070/071 and required074/075/production external evidence remain incomplete. GATE10 retained PASS; final certification and Human Sign-off NOT_EXECUTED."
registry["gates"]["GATE-08"].setdefault("contributor_evidence",{})["CEP-076"]=REL+"/RESULT.json"
summary=registry["summary"]
summary.update(execution_state_complete=74,partial_current=3,blocked_current=2,
               eligible_under_standing_authority=0,not_started_other_current_governed=0,
               last_updated="2026-10-27")
frontier=registry["execution_frontier"]
frontier.update(dependency_ready_current_governed=["CEP-069","CEP-070","CEP-071"],
                verified_verification_eligible_unblocked=[],next_autonomous_cep=None,
                next_executable_frontier=[],current_session_continuation="STOP_REQUESTED_CEP072_076_CHAIN_COMPLETE",
                next_candidate_full_entry_eligibility="NO_FURTHER_ELIGIBLE_REQUESTED_CEP",
                reconciliation_evidence=REL+"/RESULT.json",
                boundary_reason="Requested072→076 approved Development chain complete. No further Development-resolvable in-scope defects/evidence gaps. Independent069/070/071/074/075 require their distinct remaining approved inputs/qualified targets. Production and Human Sign-off remain separately unapproved.",
                independent_candidates_entry_status="069_070_071_PARTIAL;074_075_BLOCKED;072_076_COMPLETE_DEVELOPMENT;073_077_079_COMPLETE_NOT_RERUN")
registry["repository_state"]["pending_checkpoint_scope"] += ";EXT0022_CEP072_076_APPROVED_DEVELOPMENT_UNCOMMITTED"

def replace_block(text,name,value,indent=0):
    prefix=" "*indent
    pattern=rf"(?ms)^{prefix}{re.escape(name)}:\n.*?(?=^ {{0,{indent}}}\S|\Z)"
    dumped=yaml.safe_dump({name:value},sort_keys=False,allow_unicode=True,width=135)
    if indent:dumped="\n".join(prefix+line if line else line for line in dumped.splitlines())+"\n"
    text,count=re.subn(pattern,lambda _:dumped,text,count=1)
    assert count==1,name
    return text

text=original
for name in ("summary","execution_frontier","repository_state"):
    text=replace_block(text,name,registry[name])
text=replace_block(text,"CEP-076",item,2)
for name in ("GATE-08","GATE-11"):
    text=replace_block(text,name,registry["gates"][name],2)
assert yaml.safe_load(text)==registry
for cep in before["ceps"]:
    if cep!="CEP-076":assert before["ceps"][cep]==registry["ceps"][cep],cep
registry_path.write_text(text,encoding="utf-8")

for kind,headers,rows in [
    ("ACCEPTANCE_MAPPING",["criterion","status","evidence"],
     [[f"AC{i}","PASS_APPROVED_TARGET",f"{OUT.name}/RESULT.json;{OUT.name}/SCENARIO.json"] for i in range(1,7)]),
    ("EVIDENCE_MANIFEST",["evidence_id","type","path","result"],
     [["CEP-076-EV-001","CANONICAL_ENTRY_SOURCE_FREEZE",f"{OUT.name}/ENTRY.json","PASS"],
      ["CEP-076-EV-002","ACTUAL_RUNTIME_SCENARIO",f"{OUT.name}/SCENARIO.json","PASS_APPROVED_TARGET"],
      ["CEP-076-EV-003","RUNTIME_TEST_OUTPUT",f"{OUT.name}/RUNTIME_ATTEMPT_01.txt","1_PASS_8_EXECUTED_STEPS"],
      ["CEP-076-EV-004","AC_DOD_SOURCE_RECEIPT_CLOSEOUT",f"{OUT.name}/RESULT.json","PASS_APPROVED_TARGET"]]),
    ("CHANGE_MANIFEST",["path","change","scope"],
     [[REL+"/","ADDED","EVIDENCE_ONLY"],
      ["docs/governance/cep/manifests/CEP-076_EXECUTION_MANIFEST.md","ADDED","EVIDENCE_ONLY"],
      ["docs/governance/cep/reports/CEP-076_COMPLETION_REPORT.md","ADDED","EVIDENCE_ONLY"],
      ["CEP_EXECUTION_REGISTRY.yaml","UPDATED","CEP076_RELEVANT_GATES_SUMMARY_FRONTIER_ONLY"]])]:
    with (ROOT/f"docs/governance/cep/evidence/CEP-076_{kind}.csv").open("w",newline="",encoding="utf-8") as stream:
        writer=csv.writer(stream);writer.writerow(headers);writer.writerows(rows)

report="""# CEP-076 Completion Report

**EXECUTION COMPLETE — approved Development / non-production target, 2026-10-27.**

IMB-0106; main `HEAD_SHA`. [Entry](../evidence/CEP-076_EXT0022_20261027/ENTRY.json)
verifies canonical prompt identity, mandatory CEP-072 approved operational outcome,
DEP-0110 and the direct EXT-0022 target/owner/runbook policy. No dependency waiver
or Production-equivalence assertion. Existing dirty work preserved.

[Fresh actual scenario](../evidence/CEP-076_EXT0022_20261027/SCENARIO.json):
eight steps PASS, `1 passed` runtime test. Real loopback WSGI503→200 and correlated
receipt readback; actual sink-path outage with sanitized fallback and preserved200;
actual PostgreSQL probe unavailable-port failure/nonzero exit and recovery, cache
probe still executed; existing service grant/independent confirmation/use/revoke
with denied invalid/revoked access and five source-linked synthetic audit events;
actual UTC expiry denial; restricted durable receipts,30-day metadata and restart
preservation. Test fixtures roll back; technical evidence is retained separately.

[Closeout](../evidence/CEP-076_EXT0022_20261027/RESULT.json):6/6AC PASS; scoped DoD
MET through actual execution. All1,214frozen source files unchanged before/after;
zero product/configuration changes during076. Actual logs/alerts/incident copies
remain under verified restricted local storage after process exit; receipt hashes
and DACLs independently checked. EV001..004. No076failed attempt or in-scope
blocker. The earlier072failed retention attempt remains FAILED; remediation and
qualification occurred before076entry. Existing072focused/lint/format/system
checks retained; no unrelated broad regression claimed.

Changed:076evidence/manifests/mappings/report and relevant Registry/gate/frontier
metadata. Migration/data movement NONE; no business database, schema, permission,
financial or UI change. Local synthetic actor data is test-only. Git writes and
Production actions NOT_EXECUTED; all changes uncommitted.

Production operation/equivalence/destination/certification, future elapsed30-day
retention and unrelated browser/load remain unverified. Human policy approval
does not fabricate a post-run review. Human Sign-off/Production Certification/
Cutover NOT_EXECUTED. GATE08 NOT_PASSED (074/075 required contributions missing);
GATE11 NOT_PASSED (required Production/external evidence incomplete). Other CEP
results retained without rerun. Registry synchronized:74COMPLETE,3PARTIAL,
2blocked-current,7Post-V1. Requested072→076chain complete; exact next executable
frontier `[]`; no further in-scope Development-resolvable work remains.
""".replace("HEAD_SHA",entry["head"])
(ROOT/"docs/governance/cep/reports/CEP-076_COMPLETION_REPORT.md").write_text(report,encoding="utf-8")
with (ROOT/"docs/governance/cep/manifests/CEP-076_EXECUTION_MANIFEST.md").open("a",encoding="utf-8") as stream:
    stream.write("\nCloseout: [RESULT](../evidence/CEP-076_EXT0022_20261027/RESULT.json), eight actual steps PASS;6/6AC, scoped DoD MET.1214source hashes unchanged. Product/configuration untouched. Gates08/11 remain NOT_PASSED; requested chain complete; frontier empty.\n")
print("CEP076 COMPLETE6/6; source freeze1214PASS; retained receipts/ACL PASS; Gate08/11 NOT_PASSED; frontier[]")
