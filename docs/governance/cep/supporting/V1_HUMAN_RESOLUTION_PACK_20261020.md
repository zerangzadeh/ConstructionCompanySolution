# BONIRA V1 Human Resolution Pack — 2026-10-20

Grounded on `main = origin/main = remote main = 14c32ced2eab37a6322cde36b406fff1a929aade`. All three local prompt hashes match the canonical manifest. V1 remains **65 COMPLETE / 2 PARTIAL / 1 entry-BLOCKED**; none of these three packages is executable to completion from available inputs.

Types: **A** factual source data; **B** selection of an existing approved policy; **C** Human business decision. **B/C** means supply the existing approved document if available; approve a new bounded value only when no applicable policy exists. One document can answer several IDs; cite its exact version/section rather than repeat it. Dates should use unambiguous ISO dates with the source calendar conversion identified; timestamps include timezone. CSV, XLSX or JSON plus referenced approval/source documents are acceptable. Formats below describe evidence content, not an already implemented import interface.

Already resolved: CEP-023/025/029 prerequisites; the existing Employee → Person/WorkRelationship authority and [CEP-029 crosswalk](../evidence/CEP-029_SOURCE_TARGET_MAPPING.csv); operational YTD categories and reset mechanism in [Decision-05](CONSOLIDATED_HUMAN_AUTHORIZATION_20261017.txt); finalized-source correction/no-double-counting rules; Treasury as sole actual-cash authority with native posted movement date/version/evidence. No new decisions on these are requested. Read-only loopback Development counts today: 10 WorkRelationships; 0 Leave policies/entries; 0 Payroll years/cumulative states/finalized or reversed runs.

## CEP-057 — Leave opening

Canonical basis: [prompt §§9, 22–24](../PROMPTS/CEP-057_EXECUTION_PROMPT.md), PD-026 / SPEC-011 / IMB-0075, EXT-0015 and [open Finding-002](../evidence/CEP-057_FINDINGS.json).

| CEP | ID | Required input/decision | Type | Exact expected value/format | Canonical reason | Blocking AC/DoD | Human response |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 057 | HR-057-01 | Authoritative opening dataset and approval | A | Tenant and eligible population; source document/system, version and approval evidence; each row: stable source ID/version, evidence reference, source employee key, Leave category, signed quantity and unit. Supply the actual source extract, not reconstructed request history. | EXT-0015 requires approved evidenced openings. Absent: no import or balance creation. | AC1,2,5,6; evidenced target/history DoD | |
| 057 | HR-057-02 | Applicable Leave Policy/version | B/C | Approved policy document/version and effective interval; category; `days` or `minutes`; entitlement rule reference, applicable `FULL_CREDIT` / `ZERO_ACCRUAL` / `POLICY_DEFINED` preset and rule; negative floor, carry-forward and expiry treatment explicitly stated, including explicit non-applicability. Cite existing policy rather than invent values. | PD-026/SPEC-011 require explicit effective policy context. Absent: affected rows cannot qualify for import. | AC1,6; approved target DoD | |
| 057 | HR-057-03 | Dataset-specific identity linkage | A | Source employee key → existing CEP-029 Employee/Person/WorkRelationship mapping reference, including effective employment episode. Supply only linkage missing from the existing crosswalk and authoritative corrections for ambiguous/unmapped rows. | The identity foundation is complete; external row linkage is not established. Absent linkage: row remains an identifiable exception, never inferred from name/email. | AC2,3,5,7; mapping/exception DoD | |
| 057 | HR-057-04 | As-of/cutover and opening coverage | B/C | Exact `as_of` and Development `cutover_on`; source inclusion boundary and approved definition of what the opening quantity includes; treatment of overlap with subsequent target movements. Cite policy for zero, negative or overlapping openings where encountered; otherwise retain exceptions. | Source/as-of context and exclusive authority must be proved. Absent: no execution or affected authority switch. | AC1,6,7; rollback/cutover DoD | |
| 057 | HR-057-05 | Authoritative reconciliation controls | A | Approved source row count and signed quantity totals grouped by policy/category version and unit; source control report/reference; known exclusions/exceptions and their IDs/reasons. Supply factual resolutions where available; unresolved rows remain exceptions. | Before/after counts and stable mappings must reconcile. Absent controls: actual migration cannot be verified or completed. | AC2,3,7; reconciliation DoD | |

## CEP-058 — Payroll/YTD opening

Canonical basis: [prompt §§9, 22–24](../PROMPTS/CEP-058_EXECUTION_PROMPT.md), PD-031 / SPEC-013 / SPEC-030 / IMB-0080, EXT-0017 and [Finding-001](../evidence/CEP-058_FINDINGS.json).

Decision-05 already fixes separate signed `EARNING`, `ALLOWANCE`, `DEDUCTION`, `REIMBURSEMENT`, `EMPLOYER` buckets; `INFORMATIONAL` remains non-monetary. The reset mechanism is an explicitly approved versioned tenant Payroll-year interval. Neither a calendar year nor the Accounting fiscal year is implied. Corrections supersede prior contribution without double inclusion. Taxable/insurable classification and current statutory values are not requested for this operational opening.

| CEP | ID | Required input/decision | Type | Exact expected value/format | Canonical reason | Blocking AC/DoD | Human response |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 058 | HR-058-01 | Authoritative finalized historical/opening source | A | Tenant, eligible population, source/version and approval evidence; rows with stable source IDs, employee keys, finalized period/result/line evidence, component keys, signed Decimal amounts and currency/unit; correction/reversal/replacement links where present. Include native source UUID/digest if genuine; external evidence may use its original stable references. | EXT-0017/IMB-0080 require reconciliation to finalized history. Absent: no backfill. Do not fabricate native finalized runs/lines to represent external openings. | AC1,2,4–6; evidenced target/history DoD | |
| 058 | HR-058-02 | Dataset-specific employee linkage | A | External employee key → existing CEP-029 mapping/WorkRelationship effective for the source period. Reuse established links; provide only missing source-key associations or authoritative ambiguity corrections. | Existing identity mappings do not identify unseen external rows. Missing linkage leaves that row in the exception list. | AC2,3,5,7; mapping/exception DoD | |
| 058 | HR-058-03 | External component crosswalk | A; C only for unresolved business ambiguity | Each external earning/deduction/component key → existing BONIRA component and one already-approved operational kind; source documentation proving meaning/sign. Existing native component/kind mappings need no reapproval. Identify any ambiguous external meaning requiring an explicit bounded business ruling. | Decision-05 fixes categories, not unknown external source meanings. Absent mapping: affected contribution excluded as an explicit exception, never guessed. | AC1–3,6; approved cumulative target DoD | |
| 058 | HR-058-04 | Tenant Payroll-year dates and source cutoff | B/C | Approved tenant Payroll-year code/version, inclusive start/end dates and approval reference; exact as-of and source inclusion/overlap boundary for opening versus later results. Select an existing approved interval if available; otherwise approve these concrete dates. | Reset mechanism is fixed; its tenant dates are not supplied. Absent: no valid year/reset/as-of binding and no execution. | AC1,4,6,7; versioned migration/cutover DoD | |
| 058 | HR-058-05 | Authoritative reconciliation controls | A | Eligible source count and signed totals by mapped component/kind and stated currency/unit; control report/version; evidence identifying superseded/reversed/excluded lines and known exceptions. Unknown rows remain identifiable pending factual correction. | Complete source population and no double inclusion must reconcile. Absent controls: actual migration remains unverified and PARTIAL. | AC2–5,7; reconciliation/repeatability DoD | |

External historical amounts, finalized-history evidence and controls must come from their authoritative source. Internal UUIDs, digests and target mappings may be resolved from genuine existing BONIRA records; they must not be invented. The current YTD target requires native finalized-line lineage, so Codex must review the real supplied source-to-target contract before backfill. This is implementation work, not a request for the Human to design a schema.

## CEP-065 — Forecast/cash-flow

Canonical basis: [prompt §§23–24](../PROMPTS/CEP-065_EXECUTION_PROMPT.md), PD-020 / SPEC-004 `PCM-CASHFLOW` / PDM-004 / E2E-PROJ-046–047 and [Finding-001](../evidence/CEP-065_FINDINGS.json), qualified by the report's [post-retirement re-evaluation](../reports/CEP-065_COMPLETION_REPORT.md).

The existing model is versioned time-phased plan/forecast with baseline/forecast/actual comparison. Actual-cash ownership/date/version are settled. No actual tenant dataset is required merely to build; the following approved bindings are required.

| CEP | ID | Required input/decision | Type | Exact expected value/format | Canonical reason | Blocking AC/DoD | Human response |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 065 | HR-065-01 | Plan/forecast source bindings | B/C | Approved document/version mapping each baseline/forecast fact family to its owning source, eligible state, stable ID/version, project/context, amount/currency/sign fields and dated evidence; identify the source control/reconciliation evidence. Reuse existing authoritative sources; no new forecasting model. | PCM-CASHFLOW requires approved dated facts and versioned snapshots. Absent: no authoritative plan/forecast inputs. | AC1,2,5; source/history DoD | |
| 065 | HR-065-02 | Forecast cash-event timing | B/C | For each selected source family, name the authoritative expected cash-event date field or approved timing rule and supporting document/version; explicitly state unavailable-date treatment. | Cost recognition and schedule dates cannot silently become expected payment dates. Absent: affected forecast cannot be time-phased. | AC1,3,5; no-hidden-default DoD | |
| 065 | HR-065-03 | Reporting buckets | B/C | Approved bucket boundaries or calendar rule, calendar/timezone, boundary inclusivity and reporting horizon; reference the governing policy/version. | SPEC-004 requires a defined reporting bucket. Absent: no comparable time-phased states. | AC1,3,5; approved capability DoD | |
| 065 | HR-065-04 | Schedule/commitment allocation binding | B/C | Authoritative milestone/payment schedule or other approved dated allocation input; binding of source amounts to dated allocations, split/weight/amount basis and treatment of missing/unallocated amounts; existing rule/version reference. | PDM-004 links baseline, commitments and milestones; it supplies no allocation formula. Absent: no invented spreading or schedule-to-cash allocation. | AC1–3,5; source/capability DoD | |
| 065 | HR-065-05 | Snapshot cutoff and source correction treatment | B/C | Approved as-of inclusion rule, event-date versus recorded/approved-time cutoff, timezone, handling of late/corrected/reversed/replaced sources and source-version lineage; specify which snapshot/buckets include each change and how source controls reconcile. | Versioned snapshots, as-of/freshness and correction identity are required; the specific forecast binding is missing. Absent: entry stays BLOCKED. | AC1,3–5; history/fail-closed DoD | |

## Minimum responses needed

1. **Minimum responses needed to unblock CEP-057:** HR-057-01 through HR-057-05, reusable as one approved dataset/policy/control packet. Supply missing external identity links only. Unresolved rows may remain explicit exceptions under the canonical contract; no blanket risk acceptance is requested.
2. **Minimum responses needed to unblock CEP-058:** HR-058-01 through HR-058-05, reusable as one approved finalized-history/crosswalk/year/control packet. Native mappings and Decision-05 do not need reapproval.
3. **Minimum responses needed to unblock CEP-065:** HR-065-01 through HR-065-05, reusable as one approved source/timing/bucket/allocation/cutoff contract. Existing document references can satisfy these; actual tenant data is not a build prerequisite.

These inputs remove the identified Human/data boundaries; they do not themselves complete the CEPs. Remaining implementation, real-source reconciliation, migration/retry/rollback where applicable and required tests/evidence remain Codex work under each unchanged contract.

## Ready-to-paste Human Authorization

```text
BONIRA V1 bounded Human resolution — [date]
Human Decision Authority: [name/authority]
Development tenant(s)/project scope: [explicit existing scope]

I supply/select/approve the following exact evidence and bindings.
Each document reference identifies its path/link, version, section and approval.
Unanswered IDs remain unresolved; this statement supplies no missing data.

HR-057-01: [dataset/source/version/approval]
HR-057-02: [approved Leave Policy/version/effective interval and rules]
HR-057-03: [missing external row links/corrections; existing CEP-029 refs]
HR-057-04: [as-of/cutover/coverage and overlap treatment]
HR-057-05: [source counts/totals/control report/exceptions]

HR-058-01: [finalized history/opening dataset/version/approval/lineage]
HR-058-02: [missing external employee links; existing CEP-029 refs]
HR-058-03: [external component crosswalk; any explicit ambiguity ruling]
HR-058-04: [Payroll-year code/version/start/end/as-of/source boundary]
HR-058-05: [source counts/signed totals/control report/exceptions]

HR-065-01: [approved plan/forecast source bindings/version]
HR-065-02: [cash-event date fields/rules]
HR-065-03: [buckets/calendar/timezone/boundaries/horizon]
HR-065-04: [dated allocation inputs and rules]
HR-065-05: [as-of/cutoff/late/corrected/reversed/replaced source treatment]

Use these resolutions to re-check entry and continue only CEP-057, CEP-058
and CEP-065 serially on current main under existing bounded Development
authority, once each package's inputs, dependencies and gates are proved.
Preserve unchanged Scope/AC/DoD and frozen Product Decisions. Keep unmatched
or unsupported rows as explicit exceptions; never invent balances, finalized
Payroll sources, statutory values or cash timing. Do not infer completion
from this authorization. No CEP-069..079, Production action, Human Sign-off,
Production Certification, Git writes, branch or worktree creation authorized.
```

## Six pre-existing untracked paths

Only the six requested paths were inspected. No helper was executed. All remain present.

| Exact path relative to repository | Classification | Disposition/basis |
| --- | --- | --- |
| `output/cep061-tooling/` | SAFE TEMPORARY TOOL OUTPUT | Task-local PyYAML 6.0.3 installation/cache only. Exact-path cleanup rejected; manual cleanup. |
| `output/cep061_restore_test_seeds.py` | REQUIRED SOURCE/ARTIFACT | Retain: disposable-test seed restoration/recovery procedure. |
| `output/cep062_migration_check.py` | REQUIRED SOURCE/ARTIFACT | Retain: migration retention and rollback/reapply procedure producing CEP-062 migration evidence. |
| `output/cep068_fixture_browser.cjs` | REQUIRED SOURCE/ARTIFACT | Retain: browser evidence reproduction source, referenced in retained failure logs. |
| `output/cep068_mission_contactsheet.png` | SAFE TEMPORARY TOOL OUTPUT | Inspected derivative overview; all 18 underlying Mission screenshots remain in canonical evidence. Exact-path cleanup rejected; manual cleanup. |
| `output/cep_closeout_tools.py` | UNKNOWN | Retain: historical Registry-edit helper; dispensability/recovery value not established. |

Automatic approval review rejected the single native PowerShell cleanup command for `E:\Construction_Company_Solution\output\cep061-tooling\` and `E:\Construction_Company_Solution\output\cep068_mission_contactsheet.png`, stating **“blocked by policy.”** No deletion occurred and no alternate deletion mechanism was attempted. No `git clean` or Git writes ran. No product, schema or business-data mutation occurred. This pack is the only new repository artifact; existing Registry lifecycle and frontier remain unchanged.

Source recovery used the approved consolidated archive directory identified by `BLOCKED_CEP_AUTHORITY_RECOVERY_20261017.md`. Specification, frozen Product Decision, final IMB and product-review archive hashes match their prior recorded identities. Relevant recovered content: SPEC-011/013/030, PCM-CASHFLOW, E2E-PROJ-046/047, PD-020/026/028/031, IMB-0041/0075/0080 and PDM-004. Available repository contracts and later approvals remained primary. No new official statutory/legal claim was made. Validation of this documentation task: prompt hashes, current Git/remote identity, aggregate read-only Development inventory, targeted canonical/implementation references and pack structure; no application tests rerun.
