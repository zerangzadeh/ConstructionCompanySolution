"""Update the existing report/manifest; preserve the previous dated preparation."""
import csv
import json
from pathlib import Path

from blocker_closure import ROOT, OUT, digest, write

report_path = OUT / "REPORT.md"
prior = report_path.read_text(encoding="utf-8")
assert prior.startswith("# CEP-079 entry preparation — 2026-10-23")
current = """# CEP-079 entry blocker closure — 2026-10-24

**CEP-079 ENTRY = BLOCKED. GATE-09 NOT_PASSED. EXT-0025 NOT_READY.**
CEP-079 remains **NOT_ELIGIBLE / NOT_STARTED**. All five authorized Tasks were processed serially. No CEP-079 UAT scenario was executed or scored.

**29/30 prerequisites supported; 33/44 starting contexts ready; 11 blocked.**
The prior 32 ready rows and 29 supported prerequisite outcomes were preserved without requalification. UAT-CASE-034 is unchanged. CEP-078 COMPLETE is not an entry requirement.

| Task | Result and evidence |
| --- | --- |
| 1 — CEP-040 / IMB-0039 | BLOCKED. No original acceptance/test proof recovered. Same retained HEAD, no exact report/evidence Git records; prior approved consolidated recovery remains exhausted. `CEP040_RECOVERY.json` and `BLOCKER_CLOSURE_TASKS.json`. No reimplementation. |
| 2 — Workforce | PASS: 6/6 exact keyboard prerequisite cells in Chrome/Edge at 1440×900, 1024×768, 390×844. Template asset version 4→5 loads existing focus/Escape handlers. Focused v4 FAIL→v5 PASS, Django check 0 issues. `WORKFORCE_CLOSURE.json`. Immediate Edge mobile pointer probes had inconsistent results and remain explicit limitations; final keyboard assertions passed. No broader CEP-078 replay or business/permission/schema change. |
| 3 — Treasury / reconciliation | BLOCKED. Existing CASH data cannot approve BANK mappings. No applicable BANK account/mapping in the target context. Independent existing close/reopen actors were identified. Canonical non-empty period-end reconciliation preparation failed retained result-hash verification and rolled back, including statement/run creation. Nine protected source-table fingerprints are unchanged. No close/reopen executed. `TASK3_DISCOVERY.json`, `TASK3_RECONCILIATION_FIXTURE.json`, retry preimages. |
| 4 — Partner / Asset / Compliance | BLOCKED. Current target has no qualification requirement/profile, asset class/book or inspection template/version. Accepted architecture supplies mechanics and requires domain sources. The sole other-tenant inspection template cites P10 calibration, not applicable approved business content. The approved HSE/QA recovery specification explicitly supplies no checklist content or thresholds. `TASK4_GOVERNED_INPUT_DISCOVERY.json`. No policy or fixture invented. |
| 5 — Billing | BLOCKED. All 15 retained recovery archive hashes are unchanged; exhausted source recovery was reused. Current regulatory policy versions, contract terms and target Billing configuration remain absent. `TASK5_AUTHORITY_DELTA.json`. Exact Human/Product-Regulatory requirement, containing only missing inputs, authority/provenance, cases and minimum evidence, is `BILLING_AUTHORITY_DECISION_REQUIREMENT.json`. No rates, zero substitutes, terms or review were fabricated. |

## Exact remaining blockers and minimum action

| ID | Affected case(s) | Minimum action |
| --- | --- | --- |
| CEP079-PREP-B01 | 012 | Recover original authoritative CEP-040/IMB-0039 acceptance/test outputs for Project Cost reconciliation, duplicates/supersession, source/version/cutoff, tenant/object scope and no unauthorized financial writes. |
| CEP079-PREP-B03 | 009, 016 AR branch, 023 | Human/Product-Regulatory authority supplies approved effective tax_rate, tax_basis, insurance_rate, insurance_basis, external source/version/applicability and accepted professional review, applicable approved ContractTermVersion and Billing configuration. Then prepare disposable claim/AR/settlement inputs canonically. |
| CEP079-PREP-B04 | 018 | Separately authorize bounded Accounting reconciliation result-hash defect attribution/correction; then retain and independently verify non-empty period-end reconciliation/statements. Reuse the identified independent close/reopen actors. |
| CEP079-PREP-B05 | 019, 020, 022 | Treasury/Accounting owner supplies applicable approved effective BANK cash/clearing GL mapping and account facts. Then activate an isolated Development account and prepare disposable statement/cleared-cheque inputs canonically. |
| CEP079-PREP-B06 | 029, 044 | Partner owner supplies approved qualification/category requirements, source/version and applicable partner facts/evidence. Then prepare isolated qualification inputs. |
| CEP079-PREP-B07 | 043 | Fixed Assets/Accounting owner supplies approved effective asset class/book, capitalization source and candidate facts. Then prepare a disposable non-posting candidate. |
| CEP079-PREP-B08 | 044 | Compliance owner supplies approved applicable inspection template/checklist, outcome/evidence rules and source references. Then prepare isolated inspection inputs. |

`ENTRY_REASSESSMENT.json` and the existing JSON/CSV matrix contain the current delta. `CLOSEOUT_CHECK.json` proves other 85 CEPs, other gates, authorization/AC/DoD/Git state and the prior ready rows are preserved. Only the template asset version changed among baseline product files. Registry changes are limited to CEP-079 entry preparation, GATE-09 reassessment and the stopped frontier. No migrations, successful new business fixtures, prohibited Git operation, Production action or Human Sign-off occurred.

## Retained preparation record — 2026-10-23 (historical)

The record below describes the earlier preparation. Its 32/44 count and Workforce FAIL are historical; the current delta above supersedes only those changed conclusions. Original runtime failures, fixture provenance, evidence limitations and qualification facts remain retained.

"""
report_path.write_text(current + "\n".join(prior.splitlines()[1:]) + "\n", encoding="utf-8")

# Do not retain incidental bytecode produced only by these session helpers.
cache = OUT / "__pycache__" / "blocker_closure.cpython-311.pyc"
if cache.is_file():
    assert cache.resolve().parent.parent == OUT.resolve()
    cache.unlink()

evidence = [{"path": p.relative_to(ROOT).as_posix(), "sha256": digest(p), "bytes": p.stat().st_size} for p in sorted(OUT.rglob("*")) if p.is_file() and p.name != "EVIDENCE_MANIFEST.csv" and "__pycache__" not in p.parts]
with (OUT / "EVIDENCE_MANIFEST.csv").open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "bytes"])
    writer.writeheader()
    writer.writerows(evidence)
print(json.dumps({"report": str(report_path), "manifest_files": len(evidence)}))
