# Blocked CEP authority recovery — 2026-10-17

This is source-recovery evidence, not a second lifecycle register or a change to
any canonical CEP contract. The live state and frontier are in
`CEP_EXECUTION_REGISTRY.yaml`. Repository baseline: `main` at
`dd843a2d77aca43955c0089e28220b3ab05e5bdb`, matching `origin/main`;
working tree was clean before this recovery.

## Recovered canonical material

The repository's `docs/architecture/BONIRA_PD_032_CANONICAL_HOME.md` identifies
the approved consolidated archive directory:
`E:\ERP_Construction_Documents\New Version\BONIRA_TRUE_LATEST_STATE_RECONSTRUCTION_20261013\Consolidated_Packages`.
The archives were read directly without modifying their contents:

| Archive | SHA-256 | Relevant members |
| --- | --- | --- |
| `BONIRA_PRODUCT_DECISION_FREEZE_CONSOLIDATED_LATEST.zip` | `1c11429f2e0cc16c61b585832537e5035d19d008bccefc4e94f6d18839047599` | Frozen `BONIRA_FINAL_PRODUCT_DECISION_REGISTER.md` (PD-001, 014, 020, 022, 024, 025, 028, 029, 030, 031); `BONIRA_PRODUCT_OWNER_DECISION_REVIEW.md` (accepted DTR-PD-009/010 semantics) |
| `BONIRA_REQUIRED_SPECIFICATION_COMPLETION_CONSOLIDATED_LATEST.zip` | `cf45d1f6db5821084205e3cdf0553cd68c036855cd4c1d5bbe1ee28c7e6693be` | `BONIRA_REQUIRED_SPECIFICATION_COMPLETION_REGISTER.csv`, `BONIRA_CONFIGURATION_PROFILE_MATRIX.csv`, `BONIRA_PROJECT_CONTROLS_METRIC_POLICY_MATRIX.csv`, `BONIRA_EMPLOYMENT_RELATIONSHIP_SPECIFICATION.md`, `BONIRA_EMPLOYEE_DOCUMENT_DMS_SPECIFICATION.md`, `BONIRA_EMPLOYMENT_OFFBOARDING_CLEARANCE_SPECIFICATION.md`, `BONIRA_SHIFT_ROSTER_SPECIFICATION.md`, `BONIRA_PAYROLL_CUMULATIVE_YTD_SPECIFICATION.md`, `BONIRA_HSE_QA_V1_SCOPE_SPECIFICATION.md`, `BONIRA_INTEGRATION_REGISTRY.csv` |
| `BONIRA_IMPLEMENTATION_ROADMAP_CONSOLIDATED_LATEST.zip` | `54082de6f32d9a26805aaa3050f24a9863d73f840d827274f0cd3145988b6784` | `BONIRA_IMPLEMENTATION_GATE_REGISTER.csv` (GATE-06) |
| `BONIRA_PRODUCT_REVIEW_CONSOLIDATED_LATEST.zip` | `51d9276179bf60065473cb425a161a210c7e46001849e11f36b1792d17cb9503` | `BONIRA_INTEGRATION_MASTER_BACKLOG_FINAL_EN.md` (INT-R01) |
| `BONIRA_FINAL_IMPLEMENTATION_MASTER_BACKLOG_CONSOLIDATED_LATEST.zip` | `7cc3d73c1673b8d50cec337ea030514248ae0115cfc3aef260e212ad0a04b6be` | `BONIRA_FINAL_IMPLEMENTATION_MASTER_BACKLOG.csv` (affected IMBs) |

The frozen Product Decision completion record states that PD-001–031 were
explicitly frozen. The required-specification completion report identifies the
specification archive as complete for backlog purposes while preserving
unspecified values and runtime evidence. All seven local CEP prompt byte hashes
matched `docs/governance/cep/CEP_PROMPT_MANIFEST.yaml`.

## Blocker disposition

| CEP | Recovered authority and remaining boundary | Disposition |
| --- | --- | --- |
| 015 | SPEC-001 defines `project_controls.budget_overrun.response`, `project_controls.budget_overrun.override_enabled`, and `leave.accrual_preset`, but every Small/Standard/Enterprise suggested value is explicitly **UNSPECIFIED**. IMB-0017 requires approved explicit values before an activated suggestion. | Remains blocked; approved profile values and version/application semantics are required. No label-derived default. |
| 020 | Frozen PD-020/024, accepted DTR-PD-009/010, SPEC-001/004 recover the forecast state sequence, reforecast supersession, key types, and Project Controls/source-domain boundary. The matrix has no approved threshold key/value or active business-event enrollment. `ProjectCostForecast` is an immutable draft snapshot without approval state; the prompt says Migration Impact `NONE`. | Remains blocked for the unapproved control details and unavoidable lifecycle persistence migration. |
| 021 | Frozen PD-014/030 and SPEC-002 confirm Expense recognition and Treasury settlement ownership. Existing `Expense` has no reimbursement beneficiary/version and `PaymentRequest` has no Expense identity/version link. A derived ID or free-text reference cannot provide correction-safe durable lineage. Prompt Migration Impact is `NONE`. | Remains blocked; this is new bounded schema/migration authority, not an existing or no-migration implementation detail. |
| 022 | Frozen PD-025/029, SPEC-009/010/017/033, E2E-WORK-020 and PDM-009 recover the relationship, document, offboarding/clearance, and roster rules. The repository has the CEP-010 identity foundation but no offboarding/roster persistence. Prompt Migration Impact is `NONE`. | Source absence resolved; CEP remains blocked for bounded persistence/migration authority. |
| 025 | Frozen PD-028/031, PDM-012 and SPEC-013 recover the finalized-source/version, correction, and explicit reset boundary. The spec expressly withholds cumulative classification and reset policy values; Payroll has no cumulative-state model. Prompt Migration Impact is `NONE`. | Remains blocked for approved classification/reset policy and bounded schema/migration authority; statutory currentness remains UTV. |
| 027 | Frozen PD-022 and SPEC-026 list the approved HSE/QA/SAF journeys. `docs/architecture/P9_S06_S11_HSE_QA_CAPA_DECISION_PACKET.md` records Product Owner acceptance of the shared typed mechanics in `apps.compliance`. The prompt's expected `apps/safety`/`apps/quality` paths are expressly inspection hints, not an exclusive implementation surface. | Blocker resolved. The next execution must compare approved journeys with repository behavior and implement only missing in-scope pieces; no new model or policy is inferred here. |
| 028 | Frozen PD-001, INT-R01, and accepted D3-06/07/12 in `docs/architecture/P3_S01_S04_TREASURY_SUBLEDGER_DECISION_PACKET.md` define per-row evidence-backed mapping/opening/exception dispositions, required exact-match fields, tenant cutoff, reconciliation, and recovery limits. Legacy `Payment`/`PaymentAllocation` and Treasury models/migrations exist. The prompt makes the schema/authority prerequisite an entry condition and `GATE-06` an **exit** gate; the gate register requires repeatable/reconcilable migration code and required datasets before runtime migration execution. | Blocker resolved for migration **preparation** only. GATE-06 is not PASS; migration execution, cutover, and production actions remain unauthorized. The row-level mapping is CEP-028's approved implementation scope, not a preexisting table to invent. |

The earlier `AUTH-BATCH-001` CEP-028 gate classification was an authorization-time
snapshot. The current canonical prompt and gate register distinguish entry from
exit; the live Registry now records the recovered entry basis without declaring
GATE-06 PASS or changing the dependency graph.

## Objective gates and frontier

GATE-01 and GATE-02 remain PASS. GATE-03 is activation-only for relevant packages
and has no new evidence. GATE-06 remains unpassed: CEP-028 migration code,
reconciliation and datasets have not been produced or executed. No gate changed.
The dependency-ready non-production frontier after recovery is CEP-027 and
CEP-028. Neither CEP was executed in this session.
