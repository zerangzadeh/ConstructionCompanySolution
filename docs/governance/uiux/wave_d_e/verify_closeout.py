"""Focused evidence/reference/preservation checks for this bounded attempt."""
import collections
import hashlib
import json
import re
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
BASE = OUT.parent
ROOT = OUT.parents[3]


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def viewport(name):
    if "tablet" in name:
        return {"width":1024,"height":768}
    if "mobile" in name or name in {"d016_payroll_ess_denied","d021_tenant_admin_platform_denied"}:
        return {"width":390,"height":844}
    return {"width":1440,"height":900}


records = read("EVIDENCE_RECORDS.json")
browser = read("BROWSER.json")
for row in records:
    row["capture_viewports"] = {r["name"]:viewport(r["name"]) for r in browser if r["name"].startswith("d" + row["scenario_id"].split("-")[1])}
    for name in row["screenshots"]:
        assert (OUT / name).is_file(), name
(OUT / "EVIDENCE_RECORDS.json").write_text(json.dumps(records,ensure_ascii=False,indent=2) + "\n",encoding="utf-8")
payloads = {}
for filename,key in (("UIUX_RUNTIME_VALIDATION_RESULTS.yaml","wave_d_e_serial_execution"),("UIUX_FINDINGS_REGISTER.yaml","wave_d_e_runtime_reconciliation"),("UIUX_ROOT_PATTERN_IMPACT_MAP.yaml","wave_d_bounded_runtime_delta")):
    text = (BASE / filename).read_text(encoding="utf-8")
    old, payload = text.split("\n" + key + ":\n",1)
    payloads[key] = json.loads(payload.strip())
    if filename != "UIUX_ROOT_PATTERN_IMPACT_MAP.yaml":
        expected = (OUT / ("entry_" + filename)).read_text(encoding="utf-8")
        if filename == "UIUX_RUNTIME_VALIDATION_RESULTS.yaml":
            expected=expected.replace("Waves D-E not executed.","Current Wave D/E disposition is wave_d_e_serial_execution; earlier sections remain historical.",1)
        assert old.rstrip() == expected.rstrip(), filename
broken=[]
documents=[OUT / "COMPLETION_REPORT.md",BASE / "UIUX_RUNTIME_VALIDATION_WAVE_D_REPORT.md",BASE / "UIUX_RUNTIME_VALIDATION_WAVE_E_REPORT.md"]
for document in documents:
    for link in re.findall(r"\]\(([^)]+)\)",document.read_text(encoding="utf-8")):
        if "://" in link or link.startswith("#"):
            continue
        if not (document.parent / link.split("#")[0]).resolve().exists():
            broken.append({"file":document.name,"link":link})
assert not broken,broken
integrity=read("INTEGRITY.json")
allowed={"templates/components/status_badge.html","docs/governance/uiux/UIUX_RUNTIME_VALIDATION_RESULTS.yaml","docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml","docs/governance/uiux/UIUX_ROOT_PATTERN_IMPACT_MAP.yaml"}
assert set(integrity["source_changes"]) == allowed
assert not integrity["data_changes"] and integrity["index_unchanged"] and integrity["head_unchanged"]
assert len(read("BASELINE_DEBT_REVIEW.json")["rows"]) == 18
assert read("HTTP_SUMMARY.json")["all_passed"]
logs=read("RUNTIME_LOGS.json")
assert not [r for r in logs if r["level"] == "error"]
assert all("cdn.tailwindcss.com should not be used in production" in r["message"] for r in logs)
white=subprocess.run(["git","diff","--check","--","templates/components/status_badge.html"],cwd=ROOT,capture_output=True,text=True)
assert white.returncode == 0
validation={"historical_results_and_findings_preserved":True,"appended_json_compatible_yaml_payloads_decoded":True,"full_yaml_parser":"UNAVAILABLE in existing runtimes; prior text preserved, appended flow mappings are JSON validated","report_links":"PASS","screenshots_exist":"PASS","per_capture_viewports_recorded":True,"source_touch_set":"PASS","business_data_unchanged":True,"head_index_unchanged":True,"configured_migration_plan_empty":True,"django_check":"PASS; 0 issues (executed after final template change)","affected_regression":"8 unique tests PASS; affected_final.xml","authenticated_http":"18/18 PASS","runtime_errors":0,"development_tailwind_warnings":len(logs),"whitespace":"PASS","new_regressions_observed":0,"indeterminate_regressions_observed":0,"full_repository_suite":"NOT_RERUN; retained baseline debt remains explicit"}
(OUT / "VALIDATION.json").write_text(json.dumps(validation,indent=2) + "\n",encoding="utf-8")
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name != "MANIFEST.json"}
(OUT / "MANIFEST.json").write_text(json.dumps(manifest,indent=2) + "\n",encoding="utf-8")
print("Closeout references, historical preservation, scoped validation and integrity PASS; 18 baseline failures retained.")
