# B03 Return / Edit / Resubmit — Implementation Contract Proposal

Assessment dated 2026-11-12 (Asia/Tehran) for **BON-DEF-0017**. Baseline is local `main` at `865fa3f3f7868e81b0aafba05d2683b28fe33b1e` with the existing working-tree changes.

Represent a correction as a new `DailyReport` row with its own UUID, a link to the returned predecessor and copies of its supporting entries. Freeze the submitted content of each revision and start a fresh shared workflow instance on resubmission.

This proposal applies the authorized Product Owner decisions for independent review, reasoned Return, author correction and retained history. BON-DEF-0017 remains partially fixed until implementation and retest.

The current report has draft, submitted and approved states. Supporting entries point to the report UUID, and the existing workflow uses one start key per UUID. A linked successor can therefore reuse those relationships while receiving a new workflow instance. The Workflow and Permission Matrix requires explicit correction and locks submitted content. [Models](../../../../apps/daily_reports/models.py) · [Services](../../../../apps/daily_reports/services.py) · [Workflow adapter](../../../../apps/daily_reports/workflow.py) · [Permission matrix](../../../architecture/WORKFLOW_AND_PERMISSION_MATRIX.md) · [B03 evidence](B03_FINAL_REMEDIATION_REPORT.md)

## State, authority and editing

| Operation | Required state and authority | Atomic result |
|---|---|---|
| Return for correction | Submitted revision with a sealed snapshot and Return enabled. Requires active membership, current site/project scope, `daily_reports.approve`, existing work item claim/act authority and independence from the author and recorded submitter. Accept a trimmed reason of 1–1,000 characters. | Verify the snapshot, complete the review item with outcome `returned`, execute the registered Return command, set the report to `returned`, reach a terminal workflow step and append actor/reason/hash audit evidence. |
| Start correction | Returned revision with no successor; original author, current scope, `daily_reports.view` and new `daily_reports.correct` permission | Create exactly one new draft report, increment revision number, link predecessor and clone its content/supporting records with new row UUIDs. Retain original author identity and record source→copy provenance. |
| Edit correction | Successor revision still draft; original author with `daily_reports.correct`, current membership/scope and expected edit version | Update only this new draft's content. Its header and existing labor/equipment/material/activity/delay rows may be corrected or removed; source rows remain unchanged. Existing quantity, relationship and unit validation remains mandatory. Increment edit version and append a change audit receipt. |
| Resubmit | Correction draft; original author with `daily_reports.correct` and existing `daily_reports.submit`; expected edit version and request UUID | Validate complete content and relationships, seal snapshot/hash with actual submitter, set this revision to submitted and create a fresh independent review instance/items/candidates. |
| Approve | Submitted successor; current independent authorized reviewer and workflow authority | Verify submitted hash, approve this revision exactly once and complete its own workflow atomically. Earlier returned revisions remain returned. |

**R1 submitted → R1 returned. R2 newly created draft → R2 submitted → R2 approved.** Another Return before approval starts the same process with R3. Approval ends the chain.

Organization, project, site, phase and reporting date are fixed across the chain. Changing report identity/context is outside correction. Ownership alone grants no permission. `daily_reports.correct` is a new registered capability because editing/removing correction-draft content exceeds the current add-only entry operations. Its catalog entry is default-denied; role assignment uses existing governed administration, with no inferred grant to authors/managers. Return uses the existing approval capability as an alternative review outcome and needs no separate return permission.

Route successor draft writes through the correction service. Existing entry-add endpoints and the ordinary submit path must reject a successor unless they invoke the same author, permission and edit-version checks. The correction form can reuse entry validators and preserve existing per-family add permissions for newly added rows. Show the reason to authorized report readers through the exact revision history selector, using only the domain Return event fields needed on the page.

The original author must remain explicitly identifiable and actively entitled. Missing/inactive author or unprovable required independence fails closed; neither username matching nor reviewer takeover substitutes for author authority. Ordinary legacy draft operations retain their existing permissions. The correction permission does not grant document access, attachment changes or downstream domain authority.

## Submitted content and exact revision reads

Seal a canonical, versioned JSON snapshot at submission containing all report header values; all five supporting-record families with original IDs, Decimal strings and explicit units; relevant master IDs and displayed labels; safety/quality reference identities/context; document association identities and available exact DMS version IDs/hashes; author, actual submitter/membership, reporting date and aware submission instant. Include snapshot format and review-policy versions. Compute SHA-256 using existing Python facilities. Hash only the sealed content/envelope, excluding later decision state and audit events.

Submitted, returned and approved revision content, child rows and sealed snapshot cannot be edited/deleted through services, model/queryset bulk operations or admin. Add bounded PostgreSQL guards for sealed report/entry content and immutable lineage. The first submitted→returned/approved decision may update only its allowed review/status metadata. Old audit events and completed/cancelled workflow history stay append-only. Existing reference models already prohibit update/delete; do not weaken them.

Legacy rows receive no fabricated historical snapshot during schema migration. Before an eligible existing submission adopts Return, freeze its locked current content with provenance `legacy_capture`, actual capture time, original recorded submission time and only provable actors/versions. This proves the adoption baseline, not an unavailable earlier document version. If required source evidence or identity cannot be established, report that record as operationally blocked. Do not infer a historical DMS version from today's current version.

Carry inherited safety/quality references and document identities forward from the predecessor's snapshot. Daily Report typed links are document-level, so capture the authorized DMS version UUID/hash at initial submission and carry that same pin into the successor's snapshot. Recheck current access before displaying or downloading inherited evidence. Preserve inaccessible references without exposing their labels or content. If required evidence cannot be validated for resubmission, leave the correction draft intact and report the validation failure. Association editing stays outside this correction form.

Existing UUID detail/history/print URLs always identify their exact revision; they must not silently redirect to the latest revision. Daily Report list/export selectors show the chain tip once, with revision number and links to prior versions. History selectors retain every authorized revision. Split the list selector from the exact-UUID detail loader, which currently reuses the report queryset. Do not change the global default manager to hide old rows. Frozen snapshot presentation preserves historical labels; mutable draft presentation uses current validated values. Existing foreign keys continue pointing to their original report revision and are never automatically retargeted.

## Shared workflow and FULL_ERP compatibility

Add a code-owned return-capable template under `daily_reports.daily_report_approval` and register `daily_reports.daily_report.return_for_correction`. The database permits one definition per tenant/type/scope and one published version per definition. Publish the compatible successor with `supersede_workflow_version()`, which retires the old version and retains its configuration and pins. [Registry](../../../../apps/workflows/registry.py) · [Workflow models](../../../../apps/workflows/models.py) · [Publication service](../../../../apps/workflows/services.py)

The new version uses a start condition on server-derived `return_enabled`. Set it for sealed MVP submissions, adopted submissions and correction successors. Route those to `legacy_approval` with the existing single-decision policy and `exclude_creator`/`exclude_submitter` flags. This step offers approve and Return, with Return reaching a terminal `returned` step. Route ordinary FULL_ERP submissions to an approve-only step with the current legacy routing and authorization rules, including tested self-approval compatibility. Keep project/site specificity. If the matching configured version lacks the required Return contract, fail the versioned submission before any write and identify the incompatible configuration. Bind Return with `include_work_item=True` and recheck authority, author and actual submitter IDs, exact subject, state and sealed policy. The approval command enforces independence for return-enabled revisions even if the deployment profile changes.

**Existing in-flight submissions:** adopt only active instances with a compatible step key in the same definition. Under the report lock, verify the author and submitter against existing audit and runtime context, seal the legacy baseline and call `migrate_workflow_instance()` with an operator who already has `workflows.migrate_instances`, a reason and a replay key. The runtime uses the old instance's stored creator/submitter context when rebuilding candidates. Require that context to match the proven identities. Preserve the old step and assignment history, then have an eligible reviewer claim the fresh item and Return normally. Open submissions without an instance can use existing backfill under the same baseline and independent-candidate checks. Custom definitions or incompatible histories keep their existing flow until they have a governed compatible version and a deterministic mapping. Publishing and runtime migration use their existing separate permissions.

Put the reasoned Return form on report detail, reachable from the workbench's source link. Suppress the generic Return button and reject that outcome through the generic POST. The generic form has no reason field and runtime replay can return before the domain command validates a changed reason. Keep generic approval under its existing rules. Use the shared runtime unchanged. [Runtime](../../../../apps/workflows/runtime.py) · [Workbench](../../../../apps/workflows/workbench.py)

## Required schema and migrations

**No new report-revision or supporting-entry table is required.** Each existing DailyReport-shaped row is one revision. The following additions are necessary:

| Schema change | Exact purpose |
|---|---|
| `DailyReport.previous_revision`: nullable self `OneToOneField`, `PROTECT`, reverse `next_revision` | Immutable predecessor; at most one immediate successor and no branching. Existing rows default NULL. |
| `revision_number`: positive integer, default 1 | Root = 1; successor = predecessor + 1. |
| `edit_version`: positive bigint, default 0 | Optimistic concurrency token for correction-draft mutations. |
| `submission_snapshot`: JSONField, default empty object, noneditable; `submission_hash`: CharField(64), default empty string, noneditable | Durable sealed submission with canonical payload and capture provenance. |
| Add `DailyReportStatus.RETURNED = "returned"` | Terminal disposition of a submitted revision; current status column length suffices. |
| Replace `daily_report_org_site_date_uq` with uniqueness on the same columns **where `previous_revision IS NULL`** | Retain one original business-day report while allowing only explicitly linked corrections. The OneToOne predecessor constraint prevents multiple successors. |
| Local check constraints and bounded PostgreSQL triggers | Root/revision-number consistency and snapshot/hash presence pair. Enforce immutable lineage, a returned predecessor, matching tenant/context/author and incremented number. Child guards take the same parent lock as sealing and reject writes to sealed entries. Forbid reparenting or deleting any successor or sealed report. Strictly increasing immutable lineage prevents cycles. |

Migration set for later implementation: **(a)** additive Daily Reports fields, state/check/uniqueness changes and guards after current `0007`; **(b)** organization permission enum/catalog migration for `daily_reports.correct`, default-denied; **(c)** audit action choices for `daily_report.returned`, `daily_report.correction_created`, `daily_report.correction_saved`, `daily_report.baseline_frozen`; **(d)** additive shared-workflow catalog data for the returnable template, leaving the legacy template untouched. Audit-choice alterations normally change Django migration state, not an audit table's physical columns. No generic workflow schema change or destructive data backfill is required.

Apply the root-uniqueness replacement atomically before enabling successor creation. Existing rows remain revision 1 with empty snapshots and unchanged statuses/content. Future migration must validate constraints and demonstrate old create uniqueness in an isolated PostgreSQL clone. Schema rollback is conditional: once a successor exists, the old unconditional unique constraint cannot be restored safely. Disable new operations and retain data; never delete correction history to force rollback. Exact migration numbers/dependencies must be reconciled with the then-current concurrent tree.

## Transactions, replay and affected files

Keep the shared runtime lock order **subject → instance → step → item → membership authority**. Prepare workflow publication before acquiring report locks. In a Return/approve race, one decision commits and the other receives a state conflict. Correction creation locks the returned predecessor and its unique predecessor link prevents branching. Draft saves lock the successor and compare `edit_version` to reject stale edits. Resubmission locks the successor, verifies the edit version and checks for an existing open instance across matching definitions before sealing and starting the new review atomically. If there is no independently eligible reviewer who can claim and act, correction resubmission rolls back and the author keeps the draft.

Require request UUIDs for Return, correction creation/save and resubmission. Reuse immutable audit receipts with normalized payload hashes and existing indexed correlation IDs under the relevant report lock. Identical authorized replay returns the original result; the same key with another payload conflicts. Recheck current permission/scope before replay. Keys and workflow lookup use the exact revision UUID, so a prior version's decision cannot affect its successor. Return reason, predecessor/successor IDs, revision/hash, prior/new state, actor/time, work item and workflow version are retained in the domain audit. Keep existing labor idempotency intact.

Failure of snapshot validation, scope, cloning, audit, claim/completion, runtime migration/start or candidate resolution rolls back the enclosing operation. Runtime adoption is an explicit prior governed operation, or part of an explicitly authorized atomic adoption call; its successful migration must never be misreported as a completed Return. No partial Return may leave a returned report with an active review item.

| Files to change in a later implementation | Bounded responsibility |
|---|---|
| `apps/daily_reports/models.py`, new migration(s) | Revision fields, returned state, constraints and guards. Existing entry schemas remain unchanged. |
| `apps/daily_reports/services.py`; focused `revision_services.py`/`submission_snapshots.py` if needed | Correction creation/edit/sealing, replay, ownership, isolation and domain Return. |
| `apps/daily_reports/workflow.py`; `apps/workflows/registry.py`; additive catalog migration | Return command, snapshot-derived routing policy and submitter, shared completion and governed adoption. |
| `apps/workflows/workbench.py`, `views.py` | Route Daily Report Return through its reasoned source form and guard the generic outcome POST. |
| `apps/organizations/models.py`, `permission_registry.py`, catalog migration; `apps/audit/models.py`, action migration | One correction permission and immutable lifecycle audit actions. |
| Daily Report `forms.py`, `views.py`, `urls.py`, detail/correction templates | Contextual Return with reason; author-only new-revision form; hidden request/edit tokens; revision history/return and resubmit navigation. Reuse approved form/detail patterns. |
| Daily Report selectors/list presentation, `references.py`, `print_outputs.py`, exports and read-only admin declarations | Exact-version versus current-chain reads, frozen display, permission-safe association cloning and revision labels. |
| `test_workflow.py`, `test_b03_final_remediation.py`, new focused revision/concurrency tests | The acceptance checks below; preserve earlier evidence and unchanged contracts. |

## Acceptance criteria and risks

Implementation is acceptable only after isolated PostgreSQL and actual Chrome evidence proves:

1. Independent authorized reviewer Returns a submitted revision with a reason. Empty/whitespace reason, author review, missing permission/candidacy, inactive membership, suspended tenant and sibling/foreign scope fail without mutation, including direct POST/workbench paths.
2. Pre-Return submitted header, all five entry families, reference/evidence snapshot, hashes and prior audit/workflow history remain unchanged after correction and later approval. Direct save/bulk update/delete and reparent attempts cannot alter sealed content.
3. Only the explicitly entitled original author creates/edits the single successor. Every current field/UOM/relationship rule holds; correcting/removing successor rows leaves original rows and source domains intact.
4. Resubmission has a new UUID, sealed hash, actual submitter and fresh independent candidates/work items. Old decision keys/items cannot approve it. Repeated Return/edit/resubmit cycles preserve a complete chain.
5. Concurrent Return versus approval, duplicate correction creation, stale edits and duplicate resubmission commit exactly once. Exact replay is stable; payload-key conflict fails. Injected audit/domain/runtime failure rolls back all writes of that operation.
6. Existing FULL_ERP legacy approval and backfill tests retain their behavior. Profile switching cannot bypass correction-chain rules. Existing author denial, labor replay and proposal-review corrections do not regress.
7. Authorized in-flight migration retains the old version/items/history and permits subsequent Return; an unprivileged reviewer cannot migrate, and incompatible/custom/terminal histories fail closed. Legacy baseline provenance is honest.
8. Original creation still enforces one original report per tenant/site/date. Lists count chains once; exact historical UUID, print/export and existing cross-module references identify the correct revision. No downstream fact or DMS version changes occur.
9. Affected Return, author correction, resubmission, independent approval and history/print pages work in Persian/RTL at 1440, 1024 and 390 px with mandatory feedback, Jalali dates and contextual navigation. Keep original and post-implementation evidence separate.

Principal risks are the changed physical uniqueness contract and readers that assume one row per business day; legacy records without provable baseline actors/evidence; workflow adoption authority or custom step mapping; snapshot size; and conditional schema rollback. Address them with explicit chain-aware Daily Report reads, bounded legacy capture, existing migration authority, measured representative snapshots and retained data. Do not rewrite existing FKs, silently broaden permissions, or convert a blocked legacy adoption to PASS.

