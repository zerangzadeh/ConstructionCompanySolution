# BONIRA test execution plan

## Entry gate and seed contract

1. Record current commit, index/working-tree delta, settings module, server-owned Product Surface, migration frontier, browser build and test data revision. Reconcile any movement against the Phase A baseline in [Coverage and gaps](COVERAGE_AND_GAPS_REPORT.md). Halt affected results if their baseline differs; keep independent batches moving.
2. A technical owner provisions an isolated loopback Django instance and disposable PostgreSQL copy with compatible schema, unique database name, private media and protected-document directories, isolated cache/ops sink, and a captured test mail backend. Verify connection and schema identity read-only before making fixtures. Provisioning or schema changes belong to authorized Phase B setup. Existing development, demo or production databases are excluded from mutation.
3. Reuse the `seed_mvp_demo` command and documented MVP08 fixture and branch states on the isolated copy. See `docs/governance/mvp/MVP-08_HUMAN_UAT_GUIDE.md` and `scripts/verification/mvp08_serve.py`; the helper's hardcoded demo identity and storage settings must be verified before reuse. Use synthetic credentials privately. Snapshot before each mutation chain. Keep a clean source snapshot and independent clones for each batch. Never rerun seed over a partially completed chain to simulate rollback.
4. Use T-A with project P1/site S1 and sibling S2, P2/site S3, and T-B with identical labels but distinct identities. Seed scope grants, active/inactive and no-membership accounts, and enough authorized records for at least two pages. Use actors from each scenario. Translate capability and permission codes into explicit grants using existing catalog/services. Keep maker/reviewer, procurement custodian/opening approver/evaluator, and PA-only vs target-tenant member separate. Default operator never uses superuser. Use a separate, clearly marked recovery fixture only for the technical authority comparison.
5. Verify valid audit, workflow, policy and version fixtures before a lifecycle run. Before authorizing policy-dependent scenarios, identify the actual rule/version used in the fixture. A missing documented fixture or disabled local browser blocks only its dependent assertion. Reuse immutable demo history for read/output cases and reset clones for mutable cases.
6. Keep separate browser profiles and session cookies per actor. Save test data keys, canonical URLs and expected source records in the run manifest. Use fixture business codes to resolve UUIDs. Run FULL_ERP profile controls on their own process and copy using test settings overrides. The server setting is never a request parameter or role grant.

## Run protocol

The [execution matrix](TEST_EXECUTION_MATRIX.csv) is the exact worklist. Filter by Batch, then scenario and inventory ID. Each row gives expected behavior and links to the relevant catalog for detailed actions. Rows in B11 are a UI overlay on UI-facing inventory IDs. B01 hidden rows receive exposure tests only. State-dependent links discovered while running retain the original inventory ID with a child step ID. Execute browser actions first, capture sanitized HTTP/method and DOM signals, then compare authoritative model/service state and audit using a separate read-only verifier. For concurrency use separate sessions and database connections, capture both outcomes and verify the one valid durable transition. Use existing named tests as focused technical checks only after reviewing their assertion and setting. Record exact node IDs and actual test result alongside browser and state evidence.

Save under a run-specific evidence directory `<baseline>/<batch>/<scenario>/<inventory-id>/<step>` with a manifest of viewport, browser, timestamp, role, tenant/project/site fixture keys, before and after witnesses, and file hashes. Use actual workbook/print artifacts, redacted screenshots or short recordings, response/status and model or audit snapshots where applicable. Capture no secrets, reset links, private content, credentials or raw production data. Fixture-only UUIDs can be retained in protected technical manifests for correlation.

| Batch | Scope and prerequisites | Expected outcome and Product Owner review |
|---|---|---|
| B01 | UAT-01, UAT-15, CV-AUTH-01, CV-GUARD-01. Base role matrix, MVP and separate FULL_ERP fixture, test mail. | Shell, authentication, recovery and exposure boundaries verified. PO reviews wording/discoverability only after objective checks. |
| B02 | UAT-02, UAT-04, CV-TIME-01. Project, workforce, identity link, calendar and time-review fixture. | Project/site continuity and independently governed worker/time history. PO reviews field flow and time vocabulary. |
| B03 | UAT-03, CV-FIELD-01. Clone with active site, workforce/equipment and review roles. | Daily and field evidence matches persisted activities and review history. PO reviews site operator comprehension. |
| B04 | UAT-05, UAT-06, CV-EQP-01, CV-EXP-01. Independent equipment/expense/HSEQ snapshots and policy reviewers. | Scoped operations, spend/cost and separate incident/issue review states. PO reviews flow, badge meaning and mobile ergonomics. |
| B05 | UAT-07–09, CV-BIL-01. Approved estimate/baseline, versioned terms and isolated independent reviewers. | Complete priced, versioned claims and explicit supported payable/assurance branches. PO reviews terms, deductions and history navigation. |
| B06 | UAT-11–14, CV-INV-01. Independent RFQ roles and protected policies, sealed test file, award, two receipts, warehouse. | Sourcing lineage, remaining quantity, explicit stock and custody/reversal reconcile. PO reviews scope, seal state and partial-delivery cues. |
| B07 | CV-TEN-01, CV-WF-01, CV-PAR-01. Tenant grants/roles, independent assignee/reviewer and shared masters. | Scoped user delegation and declarative workbench honor least privilege. PO reviews role language and business-party discoverability. |
| B08 | UAT-10, CV-REP-01. Preseed approved claim, stock, procurement, expense and reporting records. | Outputs and audit/read models tie to exact authorized data. PO opens the actual workbook and A4 output. |
| B09 | CV-DOC-01, CV-DOC-02. Private storage, five generic targets and eight specialized variants. | Exact association/version and independent read/download/source protections. PO reviews evidence labels and contextual return. |
| B10 | PA-01–11. Separate platform fixtures with healthy/fault harness, protected accounts and disposable mail/session state. | Each platform capability and both directions of separation verified. PO reviews status and confirmation clarity across viewport sizes. |
| B11 | CV-UI-01. Renderable fixtures per page plus UI checklist. | Measured responsive and keyboard results per route/state, and explicit PO decisions for discretionary items. |

Execute B01 and B10 separation checks first, then B05, B06 and B09 high-risk chains. Each batch can start from its own compatible snapshot. Block only steps that genuinely need the unavailable predecessor, including the exact fixture and step reference. Never mark downstream steps PASS when skipped. Record failures and continue independent cases. Finish by reconciling status and coverage counts with the exact planned denominator and tracking any conditional coverage separately.

| Status | Use |
|---|---|
| NOT_RUN | Planned or skipped without an execution result. |
| PASS | All applicable browser, rule, persisted-state and negative checks ran and matched. Capture witnesses. |
| FAIL | An observed assertion differs from expectation. Link defect and evidence. |
| BLOCKED | A concrete prerequisite or dependency prevents execution. Record reason and affected steps. |
| NEEDS_PO_REVIEW | A scoped judgment or decision remains. Preserve technical outcome separately. |
| PO_ACCEPTED | Named PO explicitly accepted the specific scope on dated evidence. Preserve technical outcome separately. |

Scenario roll-up requires every mandatory step to pass; a failed mandatory step remains visible even if later steps are blocked. Historical results, test-source mentions and status codes are provenance only.
