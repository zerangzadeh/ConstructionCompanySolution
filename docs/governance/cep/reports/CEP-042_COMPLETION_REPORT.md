# CEP-042 — Accounting recognition source adapters

**EXECUTION COMPLETE — Development / Non-Production only.** 24/24 AC and all
four scoped IMB DoD pass. Finding001 is resolved by the bounded Human decision;
the original failed entry and its evidence are retained as history.

| Checkpoint | Result |
| --- | --- |
| Primary IMBs | IMB-0056, IMB-0057, IMB-0059, IMB-0060 |
| Branch / start and end HEAD | `main` / `90a1b2803936f5a95ce5322151c492ee7bafef11` |
| Human authority | HUMAN-CEP042-PERSISTENCE-20261018; minimum additive mapping persistence/migrations only |
| Canonical prompt | `7f19b517513eb1048df8b6fa5e22752bc928ffd02901b75985ccb0b649db06d9` matches manifest; only migration language in sections16/21/22 changed; Scope/AC/DoD/dependencies/ownership unchanged |
| Entry | CEP008/021 COMPLETE; no external dependency; GATE05 exit-only |
| Persistence | Three append-only Accounting mapping/independent-approval/source-draft tables, four explicit permissions with no default grants |
| Source behavior | Inventory valuation, finalized Payroll components, explicit asset capitalization/disposal/depreciation, approved direct Expense; no inferred treatments/accounts |
| Targets | Accounting-owned balanced drafts only; immutable source/native-version/mapping pins, reversal/replacement and dimension lineage |
| Failure / replay | Savepoint failure preserves source and error/retry audit; source and full journal header/line digests reject drift; unique target under concurrent retry |
| Migrations | organizations0120 + accounting0013 applied only on verified loopback local Development PostgreSQL; existing history/audit/catalog/grant digests unchanged; new tables empty; no backfill |
| Focused validation | 18 tests + 7 subtests PASS; 2 final targeted checks PASS (19 unique focused tests); populated migration rollback/reapply PASS; concurrent retry PASS |
| Affected regression | 11 scenarios verified: 7 original PASS plus 4 PASS with explicit test-only role/scope setup; original 4 failures retained as baseline fixture debt with unchanged-guard proof; no full regression PASS claim |
| Prerequisite baseline | 10 tests / 28 subtests PASS |
| Checks | Touched-module Ruff PASS; six new files format PASS; Django check PASS; migration drift NONE; diff/document checks PASS |
| Gate / frontier | GATE05 NOT_PASSED: four CEP042 contributions verified; required other contracts incomplete/unverified. Frontier recalculated |
| UTV | Runtime performance/concurrency beyond scoped automated evidence; no browser/UI, production or UAT PASS claimed |
| Git | No branch/worktree, add, commit, push or merge; completed Human CEP035/037 checkpoint reconciled inline |
| Human Sign-off / Production Certification / Cutover | NOT EXECUTED |

Mappings contain explicit source-measure-key account assignments, independent
acceptance, effective date and provenance. No account values or mappings are
seeded. Missing, unsupported, unaccepted or ineffective mappings fail closed.
Payroll informational components do not generate entries. Signed source amounts
are conserved; reversing sources must match predecessor components/dimensions,
and inverse drafts retain the predecessor mapping. Corrections require retained
prior reversal evidence. Expense reimbursement uses its Direct Expense source;
settlement never creates a second expense recognition.

The existing SPEC-002 18-row recognition registry and posting registry are
unchanged. Native revision/fingerprint/book/valuation evidence is retained in
`SourceRecognitionDraft.source_version_reference` and the full source snapshot;
JournalEntry version1 describes the immutable event UUID, not an invented native
revision. No new operational posting rule was added. These outputs cannot be
submitted/posted without a separately approved source posting contract.

Actual product surfaces: Accounting models plus recognition_models.py,
recognition_sources.py and recognition_services.py; additive Accounting0013 and
Organizations0120; explicit permission enum/registry/default-grant exclusion;
audit action catalog; bounded source hooks in Inventory, Payroll, Fixed Assets
and Expenses. Tests and bounded legacy-scenario fixtures live in
`apps/accounting/test_cep042_*.py`. No templates, routes, settings, Product
Decisions, dependency graph, unrelated migration or production state changed.

Evidence is indexed by `../evidence/CEP-042_EVIDENCE_MANIFEST.csv`; exact touch
set is `../evidence/CEP-042_CHANGE_MANIFEST.csv`. Migration/source/target traces
contain only synthetic test data or row counts/digests, never development PII.

Next CEP: **NOT STARTED AT CLEAN OPERATIONAL BOUNDARY**. Four financial adapters
now share uncommitted mapping, journal, permission, audit and source-hook changes.
Further financial work would materially increase review/collision and regression
attribution cost. CEP043 is the next unreviewed candidate, subject to its own full
canonical entry review. This is an operational handoff, not a new approval gate;
a later session can resume under standing authority without routine Human
reauthorization. No Git checkpoint was executed or requested by this agent.

## Preserved historical entry

Before HUMAN-CEP042-PERSISTENCE-20261018, the canonical prompt prohibited
migrations and no reusable Accounting source-mapping version/line store existed.
The failed entry reported 0/24 AC and no product mutation. Finding001 records that
seam, inspected alternatives and original authority boundary. The later Human
migration decision superseded only that restriction; it did not approve posting
rules, new owners, account treatment or fallback mappings.
