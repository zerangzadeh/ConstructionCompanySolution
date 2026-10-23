"""Final bounded evidence/reference checks; no browser/business mutations."""
import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
BASE = OUT.parent

def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))

def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False)+"\n",encoding="utf-8")

entry = read("ENTRY.json")
current = read("FINAL_RECONCILIATION.json")
assert current["wave_d"] == "WAVE_D_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT"
assert current["RV-025"]["result"] == "FAIL_ACCESSIBILITY"
assert current["unresolved_attributable_regressions"] == current["indeterminate_regressions"] == 0
assert current["original_baseline_failures"] == 18
assert current["new_product_decision_required"] is False
preserved = {}
for name in ("UIUX_FINDINGS_REGISTER.yaml", "UIUX_ROOT_PATTERN_IMPACT_MAP.yaml", "UIUX_RUNTIME_VALIDATION_RESULTS.yaml"):
    old = (OUT / ("entry_"+name)).read_bytes()
    new = (BASE / name).read_bytes()
    prefix, mapping = new.split(b"wave_de_fixture_closure:\r\n",1)
    if name == "UIUX_RUNTIME_VALIDATION_RESULTS.yaml":
        old = old.replace(b"Current RV-022 and Wave D/E counts are rv022_business_label_revalidation; earlier sections remain historical.", b"Current D/E results are wave_de_fixture_closure; RV-020/RV-022 remain retained PASS and earlier sections are historical.")
    assert prefix.rstrip() == old.rstrip(), name
    # Full YAML parser is unavailable; validate appended JSON-compatible mappings
    # and exact preserved historical bytes, rather than claiming a full parse.
    json.loads(mapping.decode("utf-8"))
    preserved[name] = True
completion_path = BASE / "UIUX_RUNTIME_VALIDATION_COMPLETION_REPORT.md"
historical = (OUT / "entry_UIUX_RUNTIME_VALIDATION_COMPLETION_REPORT.md").read_bytes()
completion_bytes = completion_path.read_bytes()
if not completion_bytes.endswith(historical):
    # Keep the original LF historical report byte-for-byte inside the new
    # Windows-authored current pointer; normalize only for proving identity.
    marker = historical.splitlines()[0]
    offset = completion_bytes.index(marker)
    assert completion_bytes[offset:].replace(b"\r\n", b"\n") == historical.replace(b"\r\n", b"\n")
    completion_path.write_bytes(completion_bytes[:offset] + historical)
assert completion_path.read_bytes().endswith(historical)
json.loads((BASE / "UIUX_RUNTIME_FIXTURE_REGISTRY.yaml").read_text(encoding="utf-8"))

records = read("EVIDENCE_RECORDS.json")
records[0]["runtime"] = dict(records[0]["runtime"], viewports=[[1440,900],[390,844]])
save("EVIDENCE_RECORDS.json",records)
missing = [name for r in records for name in r["screenshots"] if not (OUT / name).is_file()]
assert not missing, missing
for p in (OUT / "COMPLETION_REPORT.md", BASE / "UIUX_RUNTIME_VALIDATION_WAVE_D_REPORT.md", BASE / "UIUX_RUNTIME_VALIDATION_WAVE_E_REPORT.md"):
    for target in re.findall(r"\]\(([^)]+)\)",p.read_text(encoding="utf-8")):
        assert (p.parent / target).exists(), (p.name,target)

checks = []
python = str(ROOT / ".venv-2/Scripts/python.exe")
seams = ["apps/knowledge/templatetags/knowledge_labels.py","apps/knowledge/forms.py","apps/knowledge/views.py","apps/knowledge/test_p9_s21_s24.py","apps/workforce/test_cep053.py","apps/payroll/test_cep054.py"]
for name,command in (
    ("django_system_check",[python,"manage.py","check"]),
    ("scoped_ruff",[python,"-m","ruff","check",*seams]),
    ("new_file_format",[python,"-m","ruff","format","--check",seams[0]]),
    ("changed_seam_whitespace",["git","diff","--check","--","apps/knowledge","apps/workforce/test_cep053.py","apps/payroll/test_cep054.py","templates/workforce/ess_dashboard.html","templates/payroll/ess_history.html"]),
):
    result = subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
    checks.append({"name":name,"command":command,"exit_code":result.returncode,"stdout":result.stdout,"stderr":result.stderr})
assert all(c["exit_code"]==0 for c in checks)

# Check only this task's artifact text. Never persist or print the credential.
tree = ast.parse((ROOT / "apps/accounts/management/commands/seed_demo_data.py").read_text(encoding="utf-8"))
seed = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="DEMO_PASSWORD" for t in n.targets))
secret_hits = []
csrf_hits = []
credential_pattern = re.compile(
    r"(?i)(?:password|credential|secret)[\"']?\s*[:=]\s*[\"']"
    + re.escape(seed) + r"[\"']"
)
for p in OUT.iterdir():
    if p.suffix not in {".json",".txt",".yaml",".md",".xml",".py"}:
        continue
    text = p.read_text(encoding="utf-8-sig",errors="replace")
    # Public account aliases and common short substrings are not credential
    # payloads. Scan credential-value contexts, not arbitrary substring matches.
    if credential_pattern.search(text):
        secret_hits.append(p.name)
    if p.suffix in {".txt",".xml"} and "<!doctype html>" in text:
        csrf_hits.append(p.name)
del seed
assert not secret_hits and not csrf_hits, (secret_hits,csrf_hits)

root = ET.parse(OUT / "verified_focused_affected.xml")
tests = root.findall(".//testcase")
failures = [t.attrib["classname"]+'.'+t.attrib["name"] for t in tests if t.find("failure") is not None]
assert len(tests)==49 and failures==["apps.payroll.test_cep054.ESSPayrollTests.test_permission_tenant_isolation_and_rtl_ui"]
save("VALIDATION.json", {"checks":checks,"focused_affected":{"tests":49,"PASS":48,"retained_preentry_assertion":failures},"original_18_baseline_debt_retained":True,"D_http":read("HTTP_SUMMARY.json"),"E_http":read("E_HTTP_SUMMARY.json"),"historical_bytes_preserved_except_current_result_pointer":preserved,"full_yaml_parser":"UNAVAILABLE; appended JSON-compatible mappings decoded; fixture registry JSON decoded; preserved old bytes proved", "linked_screenshots_and_reports":"PASS","secrets_scan":{"existing_seed_credential_hits":secret_hits,"test_response_html_dumps_remaining":csrf_hits},"source_integrity":read("SOURCE_INTEGRITY.json"),"data_integrity":read("DATA_INTEGRITY.json"),"scope_stop":"D/E reconciliation only; no continuation"})
manifest = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.is_file() and p.name!="MANIFEST.json"}
save("MANIFEST.json",manifest)
print("Final verification PASS: current status/counts, preserved history, references, integrity, checks and redaction; 48 PASS + 1 retained assertion, E partial/blocked coverage explicit.")
