"""Evidence-supported CEP072 closeout, then separately grounded CEP076 entry."""

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
NOW = datetime.now(UTC).isoformat()
SHA = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
assert SHA == "79f6a1e8b264b09f7a3177d5a9a95b6e49dd7ce4"
assert "20 passed, 5 subtests passed" in (OUT / "QUALIFICATION_FINAL.txt").read_text()
scenario = json.loads((OUT / "SCENARIO.json").read_text())
assert scenario["result"] == "PASS" and len(scenario["steps"]) == 8
assert scenario["acl_after"]["status"] == "PASS"

FILES = ["core/operations.py", "tests/test_operations.py",
         "scripts/cep072_operations_runtime.py", "scripts/cep072_qualification_scenarios.py"]
for name, args in (("LINT", ["check"]), ("FORMAT", ["format", "--check"])):
    result = subprocess.run([str(ROOT / ".venv-2/Scripts/python.exe"), "-m", "ruff",
                             *args, *FILES], capture_output=True, text=True, check=False)
    (OUT / f"{name}.txt").write_text(result.stdout + result.stderr)
    assert result.returncode == 0
assert "no issues" in (OUT / "DJANGO_CHECK.txt").read_text()

def write_json(path, value):
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")

def replace_block(text, name, value, indent=0):
    prefix = " " * indent
    pattern = rf"(?ms)^{prefix}{re.escape(name)}:\n.*?(?=^ {{0,{indent}}}\S|\Z)"
    dumped = yaml.safe_dump({name: value}, sort_keys=False, allow_unicode=True, width=135)
    if indent:
        dumped = "\n".join(prefix+line if line else line for line in dumped.splitlines())+"\n"
    updated, count = re.subn(pattern, lambda _: dumped, text, count=1)
    assert count == 1, name
    return updated

registry_path = ROOT / "CEP_EXECUTION_REGISTRY.yaml"
original = registry_path.read_text(encoding="utf-8")
before = yaml.safe_load(original)
assert before == yaml.safe_load((OUT / "REGISTRY_BEFORE.yaml").read_text(encoding="utf-8"))
registry = copy.deepcopy(before)
item = registry["ceps"]["CEP-072"]
item["authorization"] = {"status": "AUTHORIZED", "authorization_id": "EXT-0022-HUMAN-20261027",
                         "source": "docs/governance/cep/supporting/EXT-0022_HUMAN_APPROVAL_20261027.md",
                         "scope": "DEVELOPMENT_NON_PRODUCTION_ONLY"}
item["execution"].update(status="COMPLETE", lifecycle="CLOSED_VERIFIED_NONPRODUCTION")
item["eligibility_status"] = "COMPLETE_APPROVED_DEVELOPMENT_OUTCOME"
item["acceptance"] = {"passed": 12, "total": 12, "status": "PASS_APPROVED_DEVELOPMENT_TARGET_ONLY",
                      "production_certification": "NOT_EXECUTED"}
item["dod"] = "MET_APPROVED_DEVELOPMENT_SCOPE"
item["blockers"] = []
item["remaining_utv"] = ["Production operations activation, network destination, production-equivalent readiness and final Production certification NOT_EXECUTED",
                         "Thirty-day elapsed retention/future operation unverified; durable files and retain-until metadata verified now; no purge or unattended service",
                         "Additional financial/integration signals absent supported producer contracts remain fail closed"]
item["completion_report"]["evidence_presence"] = "VERIFIED_20_TESTS_5_SUBTESTS_ACTUAL_DEVELOPMENT_SCENARIO"
item["last_execution"] = {"branch": "main", "sha": SHA}
item["updated_at"] = "2026-10-27"
item["git"]["current_session_changes_committed"] = False
for status, reason in [
    ("AUTHORIZED", "Direct EXT0022 Human decision approves Development owner/runbooks/signals/restricted sink/30-day retention and activation/acceptance policy; no Production or Git authority."),
    ("RESUMED", "Canonical072 identity, no prerequisites, existing foundation and safe dirty-tree overlap verified before implementation in ENTRY."),
    ("BLOCKER_RESOLVED", "Named operating/incident/escalation/revocation oversight and runbook policy supplied. Durable local sink closes disposable-lifecycle gap; actual scenario and receipt evidence verified."),
    ("COMPLETE", "12/12 AC and IMB0100/0101 scoped DoD MET for the explicitly approved Development target.20tests/5subtests and actual eight-step qualification PASS; failed retention-clock attempt preserved and repaired. No financial/integration producer invented; Production certification and global GATE11 remain ungranted."),
    ("CLOSED_VERIFIED", "Same-session report/mappings/evidence synchronized; DEP0110 configured alert/runbook/access outcome available for076. This operational outcome requires no production-equivalence waiver; external Production phase remains closed."),
]:
    item["history"].append({"date": "2026-10-27", "status": status, "reason": reason,
                            "evidence": REL + "/RESULT072.json"})
item["frontier_review"] = {"at": NOW, "head": SHA, "result": "COMPLETE_DEVELOPMENT_DEP0110_OUTCOME",
                           "evidence": REL + "/RESULT072.json", "production_authorized": False}

mapping = [
    "Actual HTTP503/200 structured correlation, discrete alert and live PostgreSQL/cache probes",
    "Established six technical signals only; no threshold/SLA/topology or recovery objective invented",
    "Human authority plus target runbook and restricted activation configuration recorded before next-package activation",
    "Genuine unavailable-port and sink-path failures retain diagnostics; nonzero probe; response preservation; no false Production readiness",
    "Actual environment-specific WSGI/PostgreSQL/cache/log/alert evidence exists; Production remains NOT_VALIDATED",
    "Unsupported business signals rejected; no new domain/posting/permission behavior",
    "Named accountable owner and OP01..04 instantiated; existing independently approved access, revocation and real UTC expiry executed",
    "Only approved operational control; existing recovery/deployment procedures referenced without new production topology or objectives",
    "Owner, authority, runbook, sink ACL, retention and exact code references explicit",
    "Delivery outage fallback and dependency failure/recovery auditable; actual support audit trace retained before test rollback",
    "Restricted receipt readback/hash/reopen evidence supports only approved Development operations PASS",
    "Existing support permissions, independence and scope contracts retained; no invented financial/integration authority",
]
result072 = {"at": NOW, "client_date": "2026-10-27", "head": SHA, "branch": "main",
             "cep": "CEP-072", "execution_state": "EXECUTION COMPLETE",
             "scope": "APPROVED_DEVELOPMENT_NON_PRODUCTION_ONLY", "imbs": ["IMB-0100", "IMB-0101"],
             "ac": {f"AC{i}": {"status": "PASS_APPROVED_TARGET", "proof": proof}
                    for i, proof in enumerate(mapping, 1)},
             "dod": "MET_APPROVED_DEVELOPMENT_SCOPE", "scenario": "SCENARIO.json",
             "validation": {"focused_and_actual_scenario": "20 passed, 5 subtests passed",
                            "lint": "PASS", "format": "PASS", "django_check": "PASS"},
             "resolved_findings": ["CEP-072-FINDING-001 owner/runbook/target policy now approved by EXT0022",
                                   "Disposable alert lifecycle insufficient for30-day retention: durable restricted receipts added",
                                   "QUALIFICATION_ATTEMPT_01 FAILED: Windows clock-source rounding caused1microsecond shortfall; retention now based on recorded event timestamp; regression assertion added"],
             "failed_attempts_retained": ["QUALIFICATION_ATTEMPT_01.txt"],
             "other_attempts": ["QUALIFICATION_ATTEMPT_02.txt PASS", "QUALIFICATION_FINAL.txt PASS with retained audit trace"],
             "production_certification": "NOT_EXECUTED", "production_actions": "NOT_EXECUTED",
             "human_signoff": "NOT_EXECUTED", "git_writes": "NOT_EXECUTED", "migration": "NONE",
             "remaining_utv": item["remaining_utv"],
             "downstream": "DEP0110 actual configured alerting/runbook/access outcome satisfied; fresh CEP076 execution required",
             "scope_interpretation": "072 approved target outcome and scoped DoD complete; final production certification belongs to GATE11. DEP0110 requires configured observability/runbooks/access, unlike production-equivalent recovery/deployment edges. No canonical scope, dependency or AC text changed."}
write_json(OUT / "RESULT072.json", result072)

for gate in ("GATE-08", "GATE-11"):
    registry["gates"][gate]["evaluated_at"] = "2026-10-27"
    registry["gates"][gate]["history"].append({"date": "2026-10-27", "status": "NOT_PASSED",
        "reason": "072 approved Development implementation outcome now qualified.076 not yet executed; other required contributors/external Production evidence unresolved. Global Gate not passed.",
        "evidence": REL + "/RESULT072.json"})
registry["gates"]["GATE-11"]["relevant_implementation_convergence"] = {
    "CEP-076": {"status": "PASS_APPROVED_DEVELOPMENT_DEP0110_ONLY", "evidence": REL+"/RESULT072.json",
                "global_gate_pass_inferred": False, "production_authorized": False}}
for imb in ("IMB-0100", "IMB-0101"):
    registry["gates"]["GATE-11"]["required_imb_status"][imb] = "PASS_APPROVED_DEVELOPMENT_ONLY_PRODUCTION_UNQUALIFIED"

next_item = registry["ceps"]["CEP-076"]
next_item["authorization"] = {"status": "AUTHORIZED", "authorization_id": "EXT-0022-HUMAN-20261027",
                              "source": item["authorization"]["source"], "scope": "APPROVED_NONPRODUCTION_DRILL_ONLY"}
next_item["dependency_status"] = "SATISFIED_CEP072_REQUIRED_OUTCOME_AND_EXT0022_DEVELOPMENT_VERIFICATION"
next_item["eligibility_status"] = "ELIGIBLE_APPROVED_DEVELOPMENT_SCENARIO"
next_item["execution"].update(lifecycle="ENTRY_VERIFIED", advisor_review="NOT_REQUIRED_CURRENT_GOVERNANCE")
next_item["blockers"] = []
next_item["history"].append({"date": "2026-10-27", "status": "AUTHORIZED",
    "reason": "Direct Human instruction to execute076 when eligible; bounded EXT0022 policy supplied. No Production/Git authority.", "evidence": item["authorization"]["source"]})
next_item["history"].append({"date": "2026-10-27", "status": "ENTRY_VERIFIED",
    "reason": "Canonical prompt hash verified;07212of12 scoped outcome COMPLETE; DEP0110 configured alert/runbook/access contract proved; EXT0022 exact local target approved. No global GATE11 requirement or production equivalence invented.", "evidence": REL+"/RESULT072.json"})

summary = registry["summary"]
summary.update(execution_state_complete=73, partial_current=3, blocked_current=2,
               eligible_under_standing_authority=1, not_started_other_current_governed=1)
frontier = registry["execution_frontier"]
frontier["dependency_ready_current_governed"] = ["CEP-069", "CEP-070", "CEP-071", "CEP-076"]
frontier["verified_verification_eligible_unblocked"] = ["CEP-076"]
frontier["next_autonomous_cep"] = "CEP-076"
frontier["next_executable_frontier"] = ["CEP-076"]
frontier["current_session_continuation"] = "CONTINUE_CEP076_ENTRY_VERIFIED"
frontier["current_session_cep_range"] = "CEP072_THEN_CEP076_EXT0022_APPROVED_DEVELOPMENT"
frontier["next_candidate_full_entry_eligibility"] = "CEP076_APPROVED_DEVELOPMENT_ENTRY_PASS"
frontier["boundary_reason"] = "072 approved Development operational outcome complete;076 entry verified against exact EXT0022 target. Other independent chains remain outside this instruction. Production gates remain closed."
frontier["unblock_conditions"].pop("CEP-072", None)
frontier["unblock_conditions"].pop("CEP-076", None)
frontier["independent_candidates_entry_status"] = "069_070_071_PARTIAL;074_075_BLOCKED;076_ELIGIBLE;073_077_079_COMPLETE_NOT_RERUN"
frontier["reconciliation_evidence"] = REL+"/RESULT072.json"

text = original
for name in ("summary", "execution_frontier"):
    text = replace_block(text, name, registry[name])
for name in ("CEP-072", "CEP-076"):
    text = replace_block(text, name, registry["ceps"][name], 2)
for name in ("GATE-08", "GATE-11"):
    text = replace_block(text, name, registry["gates"][name], 2)
after = yaml.safe_load(text)
if after != registry:
    def differences(left, right, path=""):
        if isinstance(left, dict) and isinstance(right, dict):
            for key in left.keys() | right.keys():
                if key not in left or key not in right:
                    print("KEY_DIFFERENCE", path, key)
                else:
                    differences(left[key], right[key], path+"/"+str(key))
        elif left != right:
            print("VALUE_DIFFERENCE", path, repr(left)[:250], repr(right)[:250])
    differences(after, registry)
assert after == registry
for cep in before["ceps"]:
    if cep not in ("CEP-072", "CEP-076"):
        assert before["ceps"][cep] == after["ceps"][cep], cep
registry_path.write_text(text, encoding="utf-8")

manifest = ROOT/"docs/governance/cep/manifests/CEP-072_EXECUTION_MANIFEST.md"
with manifest.open("a", encoding="utf-8") as stream:
    stream.write(f"\n## EXT-0022 approved Development execution, 2026-10-27\n\nActual pre-mutation touch set, canonical/source identities and dirty-tree grounding: [ENTRY](../evidence/{OUT.name}/ENTRY.json). Durable sink/handler and runtime driver added under072; no migrations, UI or product authorization changes. IMB0100 telemetry contract stabilized before0101 alert/owner/access qualification. Approved target/runbooks: [runbook](../supporting/EXT-0022_DEVELOPMENT_RUNBOOK_20261027.md). Failed retention-clock attempt preserved, corrected before final validation. [Closeout](../evidence/{OUT.name}/RESULT072.json):20tests/5subtests;8actual scenario steps PASS.12/12AC and scoped DoD MET; final Production certification and GATE11 remain separate.\n")
report = ROOT/"docs/governance/cep/reports/CEP-072_COMPLETION_REPORT.md"
old = report.read_text(encoding="utf-8")
report.write_text("# CEP-072 Completion Report\n\n**Latest: EXECUTION COMPLETE — approved Development / non-production scope, 2026-10-27.**\n\n[Current evidence and every AC](../evidence/"+OUT.name+"/RESULT072.json).12/12AC PASS;IMB0100/0101 scoped DoD MET. Main`"+SHA+"`; existing dirty work preserved. EXT0022 owner/runbooks/technical signals/local sink/30-day retention approval recorded. Durable restricted fixed-field logging and correlated alert receipts persist after executor exit. Actual loopback HTTP503→200, delivery outage/fallback, PostgreSQL probe failure/recovery, existing audited access revocation and actual UTC expiry denial executed.20tests plus5subtests PASS;Ruff/format/Django check PASS. Initial1microsecond retention defect and failed attempt retained; repaired under072 with regression assertion. No remaining in-scope defect. Production equivalence/final certification, future elapsed retention and financial/integration producer activation remain unverified. No migration, business-data, permission or UI mutation; no Git write. CEP076 entry now eligible under DEP0110; fresh verification required. Gates08/11 NOT_PASSED; Human Sign-off/Production Certification/Cutover NOT_EXECUTED. Evidence EV008..010 and actual touch set in manifest.\n\n## Historical reports below — prior partial dispositions superseded only for the approved target\n\n"+old.split("\n",1)[1], encoding="utf-8")
ac = ROOT/"docs/governance/cep/evidence/CEP-072_ACCEPTANCE_MAPPING.csv"
with ac.open("w",newline="",encoding="utf-8") as stream:
    writer=csv.writer(stream);writer.writerow(["criterion","status","evidence"])
    for i in range(1,13):writer.writerow([f"AC{i}","PASS_APPROVED_DEVELOPMENT_ONLY",f"{OUT.name}/RESULT072.json;{OUT.name}/SCENARIO.json"])
with (ROOT/"docs/governance/cep/evidence/CEP-072_EVIDENCE_MANIFEST.csv").open("a",newline="",encoding="utf-8") as stream:
    writer=csv.writer(stream)
    for number,kind,file in [(8,"HUMAN_AUTHORITY_ENTRY", "ENTRY.json"),(9,"ACTUAL_DEVELOPMENT_SCENARIO","SCENARIO.json"),(10,"AC_DOD_CLOSEOUT","RESULT072.json")]:
        writer.writerow([f"CEP-072-EV-{number:03}",kind,f"{OUT.name}/{file}","PASS_APPROVED_DEVELOPMENT_ONLY"])
with (ROOT/"docs/governance/cep/evidence/CEP-072_CHANGE_MANIFEST.csv").open("a",newline="",encoding="utf-8") as stream:
    writer=csv.writer(stream)
    for file in FILES+[REL+"/", "docs/governance/cep/supporting/EXT-0022_HUMAN_APPROVAL_20261027.md", "docs/governance/cep/supporting/EXT-0022_DEVELOPMENT_RUNBOOK_20261027.md"]:
        writer.writerow([file,"ADDED_OR_UPDATED","EXT0022_APPROVED_DEVELOPMENT_ONLY"])

# Freeze actual source identity before separate076 verification, including dirty
# product changes. Canonical contract is checked again, not inferred from072.
names = subprocess.check_output(["git","ls-files","--cached","--others","--exclude-standard","-z"],text=True).split("\0")
source_files = {n for n in names if n.endswith(".py") and n.startswith(("apps/","core/","config/","scripts/","tests/"))}
source_files.update(FILES+["manage.py","pytest.ini","conftest.py","requirements.txt"])
sources={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in sorted(source_files) if (ROOT/n).is_file()}
write_json(OUT/"FROZEN_SOURCES.json",sources)
verify_out=ROOT/"docs/governance/cep/evidence/CEP-076_EXT0022_20261027"
verify_out.mkdir(exist_ok=False)
prompt=ROOT/"docs/governance/cep/PROMPTS/CEP-076_EXECUTION_PROMPT.md"
prompt_hash=hashlib.sha256(prompt.read_bytes()).hexdigest()
assert prompt_hash=="2d93e72adae5830ffeca0e3fe2cc711baecd0f313078620d4cd21717be50c2aa"
write_json(verify_out/"ENTRY.json",{"at":datetime.now(UTC).isoformat(),"branch":"main","head":SHA,
    "prompt_sha256":prompt_hash,"dependency":"CEP072 COMPLETE approved Development required outcome; DEP0110 SATISFIED",
    "external":"EXT0022 approved exact local verification target/owner/runbooks/retention",
    "entry_gate":"PASS_SCOPED_IMPLEMENTATION_CONVERGENCE; global GATE11 NOT_REQUIRED_FOR_THIS_DRILL",
    "source_manifest":REL+"/FROZEN_SOURCES.json","source_files":len(sources),
    "mutations_permitted":"Evidence/report/registry only; frozen product/scenario/config unchanged",
    "scenario":"scripts/cep072_qualification_scenarios.py; OP01..04 eight steps; actual live loopback/PostgreSQL/cache/access audit/expiry",
    "migration":"NONE","production_authorized":False,"git_writes":False})
(ROOT/"docs/governance/cep/manifests/CEP-076_EXECUTION_MANIFEST.md").write_text(
    "# CEP-076 execution manifest\n\n2026-10-27;main`"+SHA+"`;IMB0106. [Verified entry](../evidence/CEP-076_EXT0022_20261027/ENTRY.json) recorded before verification. Canonical prompt hash verified; DEP0110 configured operational outcome and EXT0022 verification condition satisfied by072 completion and direct Human approval. Relevant implementation convergence PASS only for approved Development. Global Gate11 is a Production exit gate, not a required Production approval for this bounded drill.\n\nExecute a fresh actual eight-step OP01..04 scenario with exact frozen product and driver sources. Loopback HTTP failure/recovery, real local sink outage/fallback, isolated PostgreSQL dependency failure/recovery, existing service access revoke/audit and actual elapsed expiry, durable receipts/retention/DACL reopen. Touch set: new076evidence, this manifest,076AC/evidence/change/report and relevant Registry/gate/frontier fields only. No product/config/schema/permission change. No new service, network sink or Production action. Any failed scenario remains failed; remediation must return to separately recorded072 implementation authority. No Git writes.\n",encoding="utf-8")
print("CEP072 COMPLETE12/12 scoped; gates reconciled; CEP076 ENTRY PASS; frozen",len(sources),"source files")
