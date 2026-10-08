# P10-S20 Workload and Environment Specification

**Candidate:** `P10-RC1-20261007-E0E078C9`  
**Frozen runtime commit:** `0db3ac9a9fa70e8a857ef0867d532be5206a14c4`  
**Workload profile:** `P10-S20-WP1-20261007-E0E078C9-A`  
**Environment:** `P10-S20-ENV1-LOCAL-20261007-A`  
**Environment fingerprint:** `71bcd079a9792227064a4b049fc61d9ec24dec1016e83525a56b85940a46fd8d`  
**Status:** **P10-S20 = performance execution prerequisites satisfied for environment-qualified testing**  
**Certification disposition:** **Production capacity certification remains gated; only a short non-certification calibration has executed.**

This specification freezes the Product Owner-approved Option A workload without
inventing production evidence. It is the sole workload contract for the frozen
candidate. The row/document counts are end-of-horizon minimums, not product
quotas or new runtime limits. The observed local topology is frozen below, but it
is neither isolated nor production-equivalent and therefore cannot support a
production-capacity conclusion.

## 1. Accepted concurrency and duration envelope

| Input | Frozen value |
| --- | --- |
| Baseline concurrency | 50 users |
| Peak concurrency | 100 users |
| Surge concurrency | 130 users |
| Tenant count | 10 |
| Active users per Tenant | 25 |
| Representative projects per Tenant | 10 |
| Peak interval | 30 minutes |
| Surge interval | 15 minutes at 130% of peak |
| Endurance interval | 2 hours |

The runner must use separate Tenant identities and project/object fixtures. It
must not reuse one privileged account as a substitute for the accepted user mix.

## 2. Frozen journey mix and scripts

All percentages below are accepted Option A values and total 100%. Route names
are Django URL names. Each script uses a non-privileged identity with the exact
permission, Tenant, project/object scope and workflow assignment required for
that path. POST steps use current CSRF/session handling and never bypass a
service boundary.

| Script | Share | Exact journey |
| --- | ---: | --- |
| `J01A` Tenant switch | 4% | GET `organizations:select` → POST `organizations:switch` → GET `projects:list` |
| `J01B` Workbench | 7% | GET `projects:detail` → GET `workflows:workbench` → GET `support:notifications` |
| `J01C` Scoped support | 4% | GET `support:workbench`; 1 percentage point uses an approved, unexpired, purpose-bound support grant and the other 3 use ordinary Tenant members |
| `J02A` Project controls read | 8% | GET `projects:list` → `projects:detail` → `projects:controls` → `projects:controls_comparison` |
| `J02B` Procurement read | 5% | GET `procurement:request_list`/`request_detail` → `order_list`/`order_detail` → `receipt_list`/`receipt_detail` |
| `J02C` Inventory read | 4% | GET `inventory:warehouse_list` → `inventory:warehouse_detail` → `inventory:transaction_list`/`transaction_detail` → `inventory:custody_workbench` |
| `J02D` Field/HSE/QA read | 4% | GET `daily_reports:field_observation_list`/`field_observation_detail` or `daily_reports:list`/`detail` → `compliance:workbench` → `compliance:detail` |
| `J02E` Masters/DMS metadata read | 4% | GET `workforce:employee_list` → `materials:material_list` → `documents:list` → `documents:detail` |
| `J03A` Purchase request mutation | 4% | POST `procurement:request_create` → `request_item_add` → `request_submit`; a new idempotency key is used per logical request |
| `J03B` Field/compliance mutation | 4% | POST `daily_reports:field_observation_create` → `field_observation_save` → `field_observation_evidence_add`, or POST `compliance:create` → `compliance:evidence`; source and DMS-version pins are retained |
| `J03C` Receipt/stock mutation | 3% | POST `procurement:receipt_create` → `receipt_item_add` → `receipt_post`; only the domain service creates the stock movement |
| `J03D` Document/expense mutation | 4% | 2% POST `documents:link-add` or `documents:version-add`; 2% POST `expenses:draft_create` → `expenses:allocate` |
| `J04A` Workflow action | 6% | GET `workflows:workbench` → POST `workflows:work_item_claim` → POST `workflows:work_item_action`; includes 10% stale/conflict retries within this script |
| `J04B` Procurement approval | 3% | GET `procurement:request_detail` → POST `procurement:request_approve` using a different authorized actor |
| `J04C` Billing verification | 3% | GET `billing:progress_detail` → POST `billing:progress_verify` → GET `billing:claim_detail` |
| `J04D` Expense/compliance review | 3% | GET the assigned record → POST `expenses:approve` or `expenses:return`, or POST `compliance:transition`, with maker/reviewer separation |
| `J05A` Contract/Billing | 3% | GET `billing:baseline_list` → `billing:baseline_detail` → `billing:claim_list` → `billing:claim_detail` |
| `J05B` Accounting | 3% | GET `accounting:dashboard` → `accounting:journal_list` → `accounting:journal_detail`; one third creates/submits a balanced bounded journal through `journal_create`/`journal_submit` |
| `J05C` Treasury/subledger | 2% | GET `treasury:workbench` → `treasury:statement_workbench` → `subledgers:workbench` → `subledgers:aging` |
| `J05D` Payroll/workforce | 2% | GET `payroll:workbench` → `payroll:run_detail` or `payroll:payslip_detail`, with masked non-payroll viewers denied |
| `J06A` Governed metric | 4% | GET `reporting:dashboard` → POST `reporting:refresh` → GET `reporting:drillthrough` |
| `J06B` Reconciliation | 3% | GET `reporting:reconciliation_workbench` → POST `reporting:reconciliation_execute` → GET `reporting:reconciliation_detail` |
| `J06C` Closeout | 3% | GET `reporting:project_closeout_workbench` → POST `project_closeout_create`/`project_closeout_assess` → GET `project_closeout_detail` |
| `J07A` Private download | 3% | GET `documents:list` → `documents:detail` → `documents:version-download`; responses remain private/non-cacheable |
| `J07B` Private upload/version | 2% | POST `documents:upload` or `documents:version-add` with the frozen file-size distribution and exact hash metadata |
| `J08A` Bounded export | 3% | GET `reporting:export`, `projects:controls_export`, `projects:cost_reconciliation_export` or `reporting:project_closeout_export` within the frozen export bounds |
| `J08B` Treasury import | 2% | Invoke the authenticated Treasury statement preview/import application-service path with an explicit `5 MiB`/`10,000-row` bound, then GET `treasury:statement_workbench` |

Closed-loop users pause uniformly `2–5s` after ordinary steps and `5–15s` after
report, upload, download, import or export steps. Warm-up and ramp are outside the
measured intervals: ten minutes to peak and five minutes from peak to surge.
Expected authorization/validation denials are tagged separately; every successful
mutation must satisfy its domain result, audit and no-cross-Tenant assertions.

External supplier/portal participants are **0%** for this first-release capacity
profile because external upload/delivery is not activated. Purpose-bound Platform
support traffic is **1% of total requests**, already included in `J01C`, and never
uses implicit Tenant access.

## 3. Frozen representative database volumes and skew

The generator must meet or exceed these **end-of-month 24 minimums**. A standard
Tenant is one volume unit. Nine Tenants use one unit and the designated largest
Tenant uses two units, producing an aggregate of eleven standard units. Active
users and project count remain exactly 25 and 10 per Tenant rather than scaling.

| Data family | Standard Tenant minimum at month 24 | Ten-Tenant aggregate minimum |
| --- | ---: | ---: |
| Organization/access | 40 memberships (25 active, 5 suspended, 10 inactive/invited), 8 roles, 200 project/site/object-scope assignment or grant rows | 425 memberships, 88 roles, 2,200 scope/grant rows; largest Tenant retains 25 active users |
| Project structure | 10 projects, 30 sites, 600 WBS nodes, 1,000 activities, 200 phase/cost-centre rows | 100 projects, 330 sites, 6,600 WBS nodes, 11,000 activities, 2,200 phase/cost-centre rows |
| Shared masters | 1,000 parties/roles, 5,000 material/UOM/category rows, 500 employees/assignments, 10 warehouses, 150 equipment/assets | 11,000; 55,000; 5,500; 110; 1,650 respectively |
| Commercial/procurement | 200 estimate/BOQ revisions, 120 budget versions, 200 contracts/amendments, 1,000 RFQ/quote/award rows, 4,000 PO/receipt rows, 1,200 claim/certificate/guarantee rows | 2,200; 1,320; 2,200; 11,000; 44,000; 13,200 respectively |
| Field/operations | 5,200 daily/field reports, 120,000 labor/time rows, 80,000 stock/reservation/count rows, 20,000 equipment usage/maintenance rows, 10,000 HSE/QA/compliance rows, 60,000 workflow/work-item/event rows | 57,200; 1,320,000; 880,000; 220,000; 110,000; 660,000 respectively |
| Finance/control | 50,000 journals and 250,000 lines, 50,000 subledger rows, 20,000 payments/allocations, 50,000 bank import/statement rows, 24 payroll runs and 12,000 result/payslip rows, 100,000 project-cost/reconciliation facts | 550,000 journals; 2,750,000 lines; 550,000 subledger; 220,000 payments; 550,000 bank rows; 264 runs and 132,000 payroll rows; 1,100,000 control facts |
| Reporting/closeout | the shared six code-governed metric definitions, 13 reconciliation pair codes and nine closeout control families; plus 25,000 metric run/result rows, 2,400 reconciliation run/exception rows and 100 closeout assessment/evidence/proposal rows per standard Tenant | the same shared catalogues; 275,000 metric rows, 26,400 reconciliation rows and 1,100 closeout rows |
| Audit/history excluding DMS | 500,000 audit events and 250,000 lifecycle/revision/assignment-history rows | 5,500,000 audit events and 2,750,000 history rows |

The designated largest Tenant therefore holds `18.18%` of aggregate volume. Its
largest project holds `25%` of its project-scoped rows; the other nine projects
share `75%`, making the largest project approximately three times the median and
`4.55%` of the aggregate project-scoped dataset. Common list filters must return
1–5% of Tenant rows, while unfiltered authorized workbenches exercise the full
Tenant partition. Cross-Tenant rows are never part of an authorized result.

## 4. Frozen DMS, upload, export and import bounds

| Parameter | Frozen Option A value |
| --- | --- |
| Standard Tenant DMS | 20,000 documents, 50,000 immutable versions, 30,000 typed links and 50 GiB logical bytes |
| Largest Tenant DMS | 40,000 documents, 100,000 versions, 60,000 links and 100 GiB logical bytes |
| Aggregate DMS | 220,000 documents, 550,000 versions, 330,000 links and 550 GiB logical bytes |
| Version distribution | exact aggregate average `2.5` versions/document; at least 10% have 5 or more versions |
| File-size distribution | 50% `<=256 KiB`; 30% `>256 KiB–1 MiB`; 15% `>1–5 MiB`; 5% `>5–10 MiB` |
| Concurrent peak transfer shape | 5 uploads and 15 authorized downloads inside the accepted 100-user peak |
| Ordinary DMS upload | one file/request; positive size through **10 MiB inclusive**; 10 MiB + 1 byte is a required rejection |
| Tabular/export response | maximum **50,000 rows and 25 MiB** per synchronous request; whichever limit is reached first |
| Governed interactive report | maximum **10,000 rendered/result rows** before the bounded export path is required |
| DMS export | manifest-only, maximum **50,000 rows/25 MiB**; bundled document bytes are excluded because current scope does not activate that capability |
| Treasury statement import | maximum **5 MiB source bytes and 10,000 rows** per synchronous import; both positive bounds are passed explicitly |

The performance profile exercises ordinary private DMS operations only. Sealed
supplier evidence/package limits and external portal upload are outside this
profile and remain unactivated; they are not silently treated as 10 MiB ordinary
documents. Storage class, encryption/key reference, scan/quarantine latency and
failure behavior remain environment facts under section 6.

## 5. Frozen history, growth and retention shape

- History depth is **24 complete months ending at the certification cutoff**;
  every month has data and the measured dataset is pre-grown to month 24.
- Monthly compound growth used to distribute rows is: access/masters `1%`;
  project/commercial `2%`; operations/finance/reporting `3%`; documents `2.5%`;
  document versions `3%`; audit/workflow/history `4%`.
- All 24 months remain online and queryable. No fixture hard deletion or partition
  pruning may make the measured workload smaller.
- Lifecycle shape is `70%` finalized/closed, `20%` active/open and `10%` draft,
  returned, exception or correction state. At least `5%` of finalized records
  carry reversal/correction/supersession lineage.
- `20%` of documents and eligible business rows are archived but retained; `2%`
  of documents are under active legal hold. These are workload-shape values, not
  a new legal retention policy.
- The largest-Tenant and largest-project concentration remains the section 3
  `2x`/`25%` skew throughout the history.
- Certification evidence summaries remain retained for seven years after the
  candidate's last production use or longer under the governing rule; raw load
  traces may be reduced after 90 days under the accepted evidence contract.

## 6. Frozen environment and topology

The deterministic fingerprint is SHA-256 over canonical `environment.json`
excluding its `fingerprint_sha256` field. Environment ID
`P10-S20-ENV1-LOCAL-20261007-A` records the following observed local topology:

| Layer | Frozen observed value | Production-capacity gap |
| --- | --- | --- |
| Edge | direct `http://127.0.0.1:8000`; zero proxy instances; no TLS, edge compression or cache; body/timeout limits unset | No production proxy/TLS/topology evidence |
| Application | one Django 5.2.17 development `runserver`; CPython 3.11.1; shared Intel i7-1165G7 host, 4 cores/8 logical processors and 34,116,001,792 bytes RAM; no CPU/RAM cap, fixed production worker pool, request timeout or recycling | Development server and shared workstation are not production-equivalent |
| PostgreSQL | PostgreSQL 18.6 on loopback; local NVMe/NTFS; `max_connections=100`, 3 reserved, no pooler, TLS off; `shared_buffers=128MB`, `effective_cache_size=4GB`, `work_mem=4MB`, `maintenance_work_mem=64MB`; no dedicated CPU/RAM/IOPS | Shared local service has no provider class, reserved resources, IOPS guarantee, pooler or TLS |
| Private DMS | planned isolated root `E:/Construction_Company_Solution/.p10_s20_env1/dms` on local NTFS; capacity 376,438,779,904 bytes | Root is not provisioned; encryption/key, scanner/quarantine, throughput and latency evidence are absent |
| Network | runner/app/DB/DMS on one host; loopback 10-packet probe reported 0 ms at Windows timer resolution; external Wi-Fi link observed at 144.4 Mbps with no reservation | Zero-distance topology cannot represent production bandwidth, RTT, jitter or contention |
| Observability | runner latency/status/error classification and PostgreSQL active/max connection query available | Server correlation ID, application CPU/RAM, PostgreSQL waits/CPU and collection interval/retention are absent |
| Load runner | one CPython 3.11.1 process on the same 4-core/8-thread, 34 GB workstation; Windows system clock | Runner is not isolated and has no CPU/RAM/network limit or headroom proof |

The machine, process and service limits above are frozen facts, not capacity
claims. The complete machine-readable topology is `certification/p10_s20/environment.json`.
Because material differences remain, the only permitted classification is:

`environment-qualified / production capacity certification still gated`

## 7. Frozen pass/fail contract

- reads p95/p99 <= `2s / 4s`;
- mutations p95/p99 <= `3s / 6s`;
- governed reports p95/p99 <= `10s / 20s`;
- bounded operations p95/p99 <= `30s / 60s`, subject to any lower approved
  product limit;
- unexpected errors < `0.1%`;
- database connections < `80%` of the approved limit; and
- steady CPU < `75%` on each material application/database tier.

Results must be reported per journey and Tenant, not only as aggregate percentiles.
Cross-Tenant denials and expected validation/authorization failures are separate
security assertions and may not be hidden in the unexpected-error denominator.

## 8. Preflight and execution gate

No peak, surge or endurance run was executed. Bounded preflight produced:

- workload/config profile IDs and journey shares: **PASS** (`100%`);
- fixture plan compilation and one canary descriptor per data family: **PASS**;
- journey/service parse and Django URL reversal: **PASS** after all exact keyword
  parameters were reconciled (`94` route resolutions, zero failures);
- exactly one login-page reachability request: **PASS** (`HTTP 200`, `75.116ms`),
  but only against the shared, non-isolated local endpoint;
- PostgreSQL connection metric query: **PASS** (`9/100`, `9%` at the preflight
  instant), not a load result;
- environment ID/fingerprint verification: **PASS**
  (`P10-S20-ENV1-LOCAL-20261007-A` /
  `71bcd079a9792227064a4b049fc61d9ec24dec1016e83525a56b85940a46fd8d`);
  and
- all seven frozen workload/configuration artifacts: **PASS** against their
  recorded SHA-256 values.

Sections 1–5 and 7 remain frozen as workload profile
`P10-S20-WP1-20261007-E0E078C9-A`. The bounded preflight therefore records:

`P10-S20 = performance execution prerequisites satisfied for environment-qualified testing`

No peak, surge or endurance performance run was executed. Production capacity
certification remains blocked by the direct HTTP/no-TLS/no-proxy topology,
shared application/database resources without dedicated limits, incomplete
production DMS controls, and incomplete server-side telemetry. The only
permitted capacity statement remains:

`environment-qualified / production capacity certification still gated`

## 9. Hash-pinned workload artifacts

| Artifact | SHA-256 |
| --- | --- |
| `environment.json` | `7cb8a515054bcf72e257a75a41f9398911274bef4a9cdd17f7a6e8f38e9fb610` |
| `workload.json` | `0af970da66b9bc12628b8790af7927e25a409fd98391bb97a8f059560b3dbbd0` |
| `journeys.json` | `322fa73f778101e725b028242a44c6c2b2b45855bf15b01756e3f9e1a75ee359` |
| `ramp_think_time.json` | `20c892d7b79090a20802c892480055f5d18d63a330ac848de5a539c5637f1daf` |
| `dataset_volume.json` | `94ef28dc83cc57e402f96b35d0408e84bddce971ad911deb11a3c237be1668c2` |
| `fixture_generator.py` | `d144a06ab7f8904a1b5cd418b12cbf46fc9430abf33b7bbeae49ac9ac61e4383` |
| `preflight.py` | `aefcf0656252b8d36865233102b1e06d21182a1ab3add24ff52a38de5bb82cc1` |

The hash manifest is `certification/p10_s20/artifact_hashes.json`. Preflight
evidence is retained under `output/p10_s20_preflight/`; it is evidence only and
is not an executable workload artifact. The bounded closure record is
`output/p10_s20_preflight/bounded_preflight_closure.json`.

## 10. Short non-certification calibration

One `84.701s` calibration used 50 closed-loop virtual users and five exact copies
of the frozen journey distribution. It reached 50 simultaneous in-flight requests,
completed 500 journeys and issued 1,795 requests. All 27 journey shares matched
the frozen mix with `0.0` percentage-point variance.

| Class | p50 | p95 | p99 |
| --- | ---: | ---: | ---: |
| Read | `285.013ms` | `1,271.067ms` | `2,224.532ms` |
| Mutation | `276.783ms` | `931.141ms` | `2,074.430ms` |
| Mixed | `289.018ms` | `710.428ms` | `953.165ms` |
| Report | `302.622ms` | `1,349.614ms` | `2,499.905ms` |
| Bounded | `290.249ms` | `1,865.726ms` | `3,395.567ms` |

The numbers are collection proof only: placeholder UUIDs, empty POST payloads,
reused identities and 1,240 redirects mean they are not representative business-
throughput or capacity results. The run recorded 323 HTTP 403, 73 HTTP 404, ten
HTTP 405, 31 HTTP 500 and 13 connection refusals. The all-4xx/5xx/transport rate
was `25.0696%`; the unexpected 5xx/transport rate was `2.4513%`.

All 31 HTTP 500 responses were diagnosed as missing-relation `ProgrammingError`
caused by the configured database being behind the frozen candidate: reporting
`0001`–`0006`, inventory `0002`–`0006` and daily_reports `0005`–`0006` are
unapplied. No frozen-runtime code defect was established. The 13 refused
connections while development `runserver` remained alive are a separate immediate
environment/topology concern.

PostgreSQL connection collection remained available at `13/100` peak. Available
process telemetry recorded application host CPU `10.493%` mean / `20.582%` peak,
application working set `147,337,216` bytes peak, runner host CPU `0.605%` mean /
`4.592%` peak and runner working set `106,782,720` bytes peak. Database CPU/waits,
server correlation and independent tier telemetry remained unavailable.

**Full S20 environment-qualified performance run: DO NOT START.** First align the
configured database to candidate migration heads, supply executable record/payload
and permission bindings for the frozen journeys, resolve the connection refusals,
and repeat this short calibration. Raw and assessed evidence is under
`output/p10_s20_calibration/`. This calibration is not production-capacity
certification evidence and does not alter:

`environment-qualified / production capacity certification still gated`
