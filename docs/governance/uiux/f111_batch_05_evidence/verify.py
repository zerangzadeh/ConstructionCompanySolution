"""Verify exact BATCH-05 boundaries and evidence before resolved closeout."""
import ast
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
import yaml

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
def read(name):return json.loads((OUT/name).read_text(encoding="utf-8"))
def save(name,data):(OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def boundary(source,name):
 tree=ast.parse(source)
 if name=="forms":
  cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="StockTransactionForm")
  cls.body=[n for n in cls.body if not isinstance(n,ast.FunctionDef) or n.name!="__init__"]
 else:tree.body=[n for n in tree.body if not isinstance(n,ast.FunctionDef) or n.name!="transaction_create"]
 extra={"apps.organizations.authorization","apps.organizations.models"} if name=="forms" else {"apps.organizations.authorization"}
 tree.body=[n for n in tree.body if not isinstance(n,ast.ImportFrom) or n.module not in extra]
 return ast.dump(tree,include_attributes=False)

def main():
 baseline=read("ENTRY_BASELINE.json")
 expected={"apps/inventory/forms.py","apps/inventory/views.py","docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml"}
 changed=[n for n,h in baseline["hashes"].items() if hashlib.sha256((ROOT/n).read_bytes()).hexdigest()!=h]
 assert set(changed)==expected,changed
 for name in ("forms","views"):
  assert boundary((ROOT/f"apps/inventory/{name}.py").read_text(encoding="utf-8"),name)==boundary((OUT/f"{name}_entry.txt").read_text(encoding="utf-8"),name)
 register=(ROOT/"docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml").read_text(encoding="utf-8")
 pattern=r"- finding_id: UIUX-F-118\n.*?(?=- finding_id: UIUX-F-119\n)"
 assert re.sub(pattern,"",register,flags=re.S)==re.sub(pattern,"",(OUT/"register_entry.txt").read_text(encoding="utf-8"),flags=re.S)
 assert yaml.safe_load(register)
 entry=re.search(pattern,register,re.S).group(0)
 assert "finding_status: RESOLVED" in entry and "status: RUNTIME_VERIFIED_RESOLVED" in entry and "decision: BATCH_05_RUNTIME_VERIFIED_RESOLVED" in entry
 for name in ("focused","regression"):
  xml=ET.parse(OUT/(name+".xml")).getroot()
  assert not xml.findall(".//failure") and not xml.findall(".//error")
 assert "12 passed, 43 subtests passed" in (OUT/"focused.txt").read_text(encoding="utf-8")
 assert "76 passed, 77 subtests passed" in (OUT/"regression.txt").read_text(encoding="utf-8")
 for filename,token in (("django_check.txt","no issues"),("migration_check.txt","No changes detected"),("ruff.txt","All checks passed"),("ruff_format.txt","files already formatted")):
  assert token in (OUT/filename).read_text(encoding="utf-8"),filename
 http=read("RUNTIME_HTTP.json");assert len(http)==41 and all(r["status"]==200 and not r["forbidden_metadata"] and set(r["model_deltas"])<={"sessions.Session","audit.AuditEvent"} for r in http)
 assert all(r["errors"] for r in http if r["method"]=="POST")
 assert len(read("DIRECT_SERVICE.json"))==8 and all(r["denied"] and not r["mutations"] for r in read("DIRECT_SERVICE.json"))
 browser=read("RUNTIME_BROWSER.json");assert len(browser)==5
 assert browser[1]["errors"] and browser[2]["errors"]
 for i in range(5):
  actor="uiux.reference.batch03.site-only" if i==3 else "uiux.persona.tenant-admin" if i==4 else "uiux.persona.project-manager"
  comparison=next(r for r in http if r["method"]=="GET" and r["actor"]==actor)
  for f,options in browser[i]["options"].items():
   assert [{k:o[k] for k in ("value","label")} for o in options]==comparison["options"][f]
 integrity=read("RUNTIME_INTEGRITY.json")
 assert not integrity["preexisting_rows_changed"] and integrity["authority_unchanged"] and not integrity["unauthorized_mutations"] and not integrity["posted_stock_or_value_changes"]
 assert len(read("RUNTIME_POSITIVE.json"))==2
 assert read("PREFLIGHT_RECOVERY.json")["exact_recovery"]
 assert not read("SERVER_CLEANUP.json")["listener_remaining"]
 check=subprocess.run(["git","diff","--check"],cwd=ROOT,capture_output=True,text=True)
 (OUT/"whitespace.txt").write_text(check.stdout+check.stderr,encoding="utf-8");assert check.returncode==0
 report=OUT.parent/"UIUX_F111_BATCH_05_REMEDIATION_REPORT.md"
 for link in re.findall(r"\]\(([^)]+)\)",report.read_text(encoding="utf-8")):
  target=report.parent/link.split("#")[0];assert target.exists() or target in {OUT/"VERIFICATION.json",OUT/"INDEX.json"},link
 for path in [ROOT/"tests/test_uiux_f111_pattern_stock_scope.py",report,*OUT.glob("*.py")]:
  assert all(line==line.rstrip() for line in path.read_text(encoding="utf-8").splitlines()),path
 summary={"decision":"BATCH_05_RUNTIME_VERIFIED_RESOLVED","finding":"UIUX-F-118","status":"RUNTIME_VERIFIED_RESOLVED","baseline_files_compared":len(baseline["hashes"]),"changed_existing_files":changed,"final_source_sha256":{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ("apps/inventory/forms.py","apps/inventory/views.py","tests/test_uiux_f111_pattern_stock_scope.py","docs/governance/uiux/UIUX_F111_BATCH_05_REMEDIATION_REPORT.md","docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml")},"product_ast_boundaries_only":True,"other_findings_prior_batches_graph_registry_roadmap_preserved":True,"focused":{"tests":12,"subtests":43,"status":"PASS"},"regression":{"tests":76,"subtests":77,"status":"PASS","attribution":"No failures; no baseline waiver or replay required"},"http_observations":41,"browser_observations":5,"direct_service_denials":8,"authorized_live_drafts":2,"integrity":integrity,"migrations":"NO","batch06_to09":"NOT_EXECUTED","wave_c":"NOT_STARTED","production_cep078_079_git_writes":"NOT_EXECUTED"}
 save("VERIFICATION.json",summary)
 save("INDEX.json",{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!="INDEX.json"})
 print("BATCH-05 bounded verification PASS; prior work preserved")

if __name__=="__main__":main()
