# B03 Return Workflow Implementation

Executed on 2026-11-12 under the approved [Return workflow contract](B03_RETURN_WORKFLOW_CONTRACT_PROPOSAL.md). Baseline `main` and upstream were `24ad220f0376cb0b6232b745938b35433843a32d`, with a clean entry working tree. Concurrent B04 changes appeared later and were preserved separately from this task's edits.

**BON-DEF-0017 is FIXED / RETESTED_PASS.** The complete Return → author correction → resubmission → independent approval journey passed. The latest derived B03 position is **22 PASS / 0 FAIL / 0 BLOCKED / 0 NOT_RUN**. Formal PO acceptance remains pending.

| B03 checkpoint | PASS | FAIL | BLOCKED | NOT_RUN |
|---|---:|---:|---:|---:|
| Original execution, historical | 7 | 14 | 1 | 0 |
| First bounded remediation, historical | 19 | 2 | 1 | 0 |
| Final three-finding remediation, historical | 21 | 0 | 1 | 0 |
| This Return implementation, latest derived result | 22 | 0 | 0 | 0 |

The [new retest overlay](B03_RETURN_IMPLEMENTATION_RETEST.csv) carries forward the 21 previously passing primary rows and replaces the remaining approval-row blocker with actual implementation evidence. The affected paths also received focused regressions. Earlier overlays, screenshots, reports and original matrix results retain their historical outcomes.

## Implemented behavior

A returned report stays retained with its submitted snapshot, original supporting rows and exact source references. The explicitly authorized original author creates one linked successor with a new UUID and revision number. Its header and all five supporting-entry families support controlled correction, removal and permitted additions. Request UUIDs, locked reports and edit-version checks prevent duplicate successors, lost edits and duplicate resubmission. Ordinary entry-add/submit endpoints reject correction successors so every correction passes the new authority and concurrency checks.

The new `daily_reports.correct` permission is default-denied, including owner and manager defaults. It requires an explicit existing role assignment. Return uses scoped approval permission, current workflow candidacy/assignment and independent author/submitter checks. Its trimmed reason must contain 1–1,000 characters. The source form validates reason and replay payload before shared runtime completion. Generic workbench Return is guarded and the workbench source link leads to the reasoned form.

Every new MVP submission seals a canonical snapshot/hash with header, entries, quantities/units, master labels, references, exact DMS pins, author, actual submitter and aware timestamps. PostgreSQL guards preserve sealed content and immutable lineage. A deferred decision guard requires the matching completed work item, terminal workflow instance and domain audit event before a sealed approval/Return can commit. Submitted history remains immutable through direct model writes, bulk operations and deletion attempts.

Each successor receives fresh independent candidates and a fresh workflow instance. Existing FULL_ERP behavior uses an approve-only compatibility branch. A sealed correction's independent-review rules remain enforced if the deployment profile changes. Publication uses existing supersession authority. Eligible old in-flight reports use explicit, reasoned runtime migration in their existing definition, retaining old versions, cancelled items and assignment history. Custom or unprovable baselines fail closed.

Lists and exports show each chain tip once. Exact UUID detail, history and print retain the requested revision and frozen labels. Protected DMS downloads continue resolving the recorded exact version. Inaccessible inherited references remain opaque. Date/time presentation uses the organization's timezone and Jalali formatting. New UI uses the existing Persian RTL forms and detail components.

## Migrations and database evidence

All migration execution used task-owned disposable PostgreSQL databases in `C:/Users/azera/AppData/Local/Temp/bonira-return-643e829f/pg`, loopback port `52437`. A read-only dump of the prior isolated `b03_clean` validation template supplied upgrade-test clones. A separate empty database exercised installation from an empty schema. Existing Development, demo and Production databases received no migration or business writes.

| Migration | Result |
|---|---|
| `daily_reports.0008_daily_report_return` | Added predecessor, revision number, edit version, snapshot/hash, returned status and checks. Replaced unconditional day uniqueness with original-report uniqueness. |
| `daily_reports.0009_revision_guards` | Installed lineage, parent-locking entry immutability and deferred decision/audit guards. Reverse refuses removal when successor history exists. |
| `organizations.0130_daily_report_correction_permission` | Registered correction permission and excluded it from default system-role grants. |
| `audit.0060_daily_report_return` | Recorded Return/correction/baseline audit action choices. |
| `workflows.0028_daily_report_return_catalog` | Added the conditional Return-capable template while retaining the legacy template. |

The independent SQL witness verifies all five migrations, **462 applied / zero pending**, eight database triggers and zero default correction grants. It also verifies three original/successor pairs, 30 supporting-entry rows, six completed independent review decisions, distinct work items, unchanged source hashes and exact predecessor links. [Persisted state](evidence/b03-return-24ad220f-20261112/persisted-state.json) · [Upgrade migrations](evidence/b03-return-24ad220f-20261112/ui-migrations.log) · [Empty installation baseline](evidence/b03-return-24ad220f-20261112/migration-initial.log) · [Empty installation completion](evidence/b03-return-24ad220f-20261112/migration-empty-complete.log)

## Acceptance verification

**53 distinct focused PostgreSQL tests passed**, plus eight subtests. The main selection passed 50 tests. Three separately cloned databases qualified Return concurrency, legacy approval concurrency and the existing labor retry race. Added final assertions qualified replay conflicts, reason limits, DMS-version preservation and correction-clone rollback. [Main results](evidence/b03-return-24ad220f-20261112/qualification-business-final.log) · [Return race](evidence/b03-return-24ad220f-20261112/qualification-race-final.log) · [Legacy approval race](evidence/b03-return-24ad220f-20261112/qualification-legacyrace.log) · [Labor race](evidence/b03-return-24ad220f-20261112/verified-labor.log) · [Final assertions](evidence/b03-return-24ad220f-20261112/qualification-final-assertions.log)

| Contract criterion | Verified assertions | Result |
|---|---|---|
| 1. Independent reasoned Return | Blank/overlong reason, author/submitter, missing permission/candidacy, suspended membership/tenant, sibling/foreign scope and generic workbench POST deny without mutation. | PASS |
| 2. Immutable submitted content | Sealed header/entries/snapshots/history retained across correction and approval. Direct/bulk update, delete, reparent and unaudited state-change attempts fail. | PASS |
| 3. Author correction | Explicit permission and original-author checks. All five families edited, removed and added. Invalid quantities, percentages and stale versions fail. Source rows remain unchanged. | PASS |
| 4. Fresh independent review | New UUID, revision, hash, submitter, candidates and work item. Old decision cannot affect successor. Repeated Return creates the next linked revision. | PASS |
| 5. Concurrency and rollback | Return/approve race, identical concurrent correction creation, stale concurrent edits, duplicate concurrent resubmission and payload-key conflicts. Audit failure rolls back Return and clone creation. Runtime-start failure rolls back sealing/submission. | PASS |
| 6. Compatibility and prior corrections | FULL_ERP legacy self-approval/backfill retained. Profile switching cannot bypass successor separation. Earlier author protection, labor replay, proposal review and tenant-local field timestamps pass focused regression. | PASS |
| 7. Governed adoption | Eligible active migration and missing-instance backfill pass. Old version/items retained. Unprivileged migration, custom configuration and unprovable actor baseline fail closed. | PASS |
| 8. Identity, scope and source boundaries | One original per tenant/site/day, single successor, chain-tip list/export, exact historical print/detail, unchanged DMS pins/current version and original safety source FK/state. | PASS |
| 9. Browser usability | Complete journeys at 1440/1024/390 px, required reason feedback, author editing of five families, fresh reviewer approval, Jalali history/print and contextual return. | PASS |

Actual installed Chrome `156.0.8078.80` completed three authenticated journeys using headless Chrome sessions. Twelve representative final screenshots cover Return, correction, resubmission and historical print. All recorded layouts are Persian/RTL with no horizontal document overflow or duplicate main-content IDs. Screens were visually inspected, including narrow and tablet layouts. The first visible Chrome attempt was interrupted by browser closure and remains recorded as incomplete. Final accepted journeys use the final service behavior. [Chrome assertions](evidence/b03-return-24ad220f-20261112/chrome/results.json) · [390 px Return](evidence/b03-return-24ad220f-20261112/chrome/return-390.png) · [1024 px correction](evidence/b03-return-24ad220f-20261112/chrome/correction-1024.png)

Implementation attempts exposed and corrected a SQL placeholder-escaping issue in trigger installation, a duplicate start-outcome name, and missing positive-quantity validation in correction material rows. Legacy tests were updated to use explicit current fixture grants and the FULL_ERP profile. A mixed transactional test run encountered the retained-table/serialized-catalog cleanup issue, so final race selections used separate fresh clones. Failed attempts are retained separately and were not converted to passing results. [Attempt record](evidence/b03-return-24ad220f-20261112/ATTEMPTS.md)

Django system check, migration drift check and targeted Ruff/whitespace checks pass. [Checks](evidence/b03-return-24ad220f-20261112/checks.json)

Supplemental permission-registry checks passed three tests and 28 subtests. The global enforcement-reference check failed on 23 unrelated resources; comparison against the entry commit proves the same failure set existed before this task. Daily Report's enforcement references pass. This pre-existing global failure was not repaired or counted as a B03 pass. [Supplemental results](evidence/b03-return-24ad220f-20261112/qualification-permission-registry.log) · [Baseline attribution](evidence/b03-return-24ad220f-20261112/permission-registry-attribution.json)

## Changed files and preservation

The [source and preservation manifest](evidence/b03-return-24ad220f-20261112/CORRECTED_BASELINE.json) records file hashes, migration identities, the clean entry status and the recoverable Git bundle checkpoint. The bundle captures HEAD and requires base `865fa3f3f7868e81b0aafba05d2683b28fe33b1e`, which remains in the repository. No Git checkpoint commit was created by this task.

Changes comprise Daily Report models, migrations, snapshot/revision/Return services, workflow adapter/configuration, selectors, association reads, forms/views/routes/templates, print/export and read-only admin metadata. Shared changes add the registered command/attribute and guard workbench Return. Authorization changes cover the permission enum/resource/defaults/catalog migration. Audit changes add action choices. A guarded management command exposes governed publication. Focused tests cover the new contract and modernize legacy fixtures. The manifest identifies the exact files and separates concurrent changes outside this scope.

The shared defect register updates only BON-DEF-0017. Earlier B03 evidence, the approved proposal, the original matrix, B02 outcomes and its five blocked rows retain their recorded results. Concurrent equipment/safety/quality/B04 work was left intact.

## Remaining deployment constraints

There are no unresolved attributable P0/P1 defects in the verified contract. Correction authority still requires an explicit grant. Old reports with unprovable submitter identity or historical DMS pins remain ineligible for automatic adoption. Customized workflow definitions require a compatible governed version. Removing the revision schema after successor creation requires a separate retention-preserving plan. Existing business databases still require separately authorized rollout of the migrations and any workflow adoption.

B03 stops at this closeout. The task-owned UI server and isolated PostgreSQL cluster were stopped after checking that no other clients were connected; disposable data is retained. [Resource closeout](evidence/b03-return-24ad220f-20261112/resource-closeout.json)

This task performed no B04 validation, production action, commit, push or formal PO acceptance.
