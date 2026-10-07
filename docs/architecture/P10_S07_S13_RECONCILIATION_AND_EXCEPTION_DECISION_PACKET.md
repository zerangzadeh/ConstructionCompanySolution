# P10-S07–S13 Reconciliation and Exception Decision Packet

**Status:** **Product Owner accepted.**

**Date:** 2026-10-07.

**Prerequisite:** `P10-S02–S06 = Product Owner accepted`.

**Authority:** this packet, `ROADMAP.md`, the P10 session map in
`docs/ROADMAP_EXECUTION_PLAYBOOK.md`, the accepted
`P10_S01_S06_GOVERNED_METRICS_AND_REPORTING_DECISION_PACKET.md`, and the directly
affected domain/data/permission authorities cited below. Models, migrations and
tests remain authoritative for current runtime behavior.

**Runtime effect:** the Product Owner accepted `P10-R01`–`P10-R36 = Option A`
and authorized implementation of exactly the 13 pair codes in this packet. This
does not authorize `P10-S14+`, production use, a source-domain mutation or any
downstream effect.

## 1. Entry gate and exact bounded envelope

The entry gate is satisfied: the Product Owner accepted the six governed metrics,
synchronous immutable results, source lineage, material-result review, Persian
RTL/Jalali dashboard, permission-preserving drill-through and bounded on-demand
export delivered by P10-S02–S06.

The next official envelope is exactly **P10-S07–S13**: financial/operational
reconciliation pairs, exception evidence and rebuild checks. This packet prepares
all material Product Owner decisions for that envelope. It does not treat planning
as approval.

The governing containment rule is:

> Reporting/Reconciliation owns governed comparison definitions, immutable
> comparison runs, exception coordination evidence and rebuild verification. It
> never owns, replaces, corrects, posts, settles, values, recognizes, closes or
> otherwise mutates an Accounting, Treasury, Project Cost, Inventory,
> Procurement, Contract/Billing, Payroll, Fixed Assets or other source fact.

Absence, gated authority, incomplete coverage, inaccessible evidence and unknown
values remain explicit states. They never become zero, a synthetic match, a
balancing item or an invented source fact.

## 2. Exact session decomposition

| Session | Exact bounded outcome | Entry / stop condition |
| --- | --- | --- |
| `P10-S07` | Reconciliation foundation: code-governed pair/version catalogue, source-authority registry, comparison grain, side/role semantics, readiness state and default-deny permission catalogue | `P10-R01`–`P10-R36` accepted and exact pair owners/reviewers named. Stop if a pair lacks authoritative sides or stable version/cutoff semantics. |
| `P10-S08` | Immutable synchronous run/tie-out foundation for the authorized finance-facing pairs, with exact scope/cutoff/source manifests, coverage and `unknown/incomplete/not_applicable` states | No posting, close/reopen, settlement, valuation or source correction. Existing domain-native reconciliation remains authoritative and is referenced, not reimplemented. |
| `P10-S09` | Immutable synchronous run/tie-out foundation for the authorized operational/cross-domain pairs and proposal/acknowledgment checks | Dormant consumers are reported as `gated/not_activated`, not mismatches or zero. No producer/consumer activation. |
| `P10-S10` | Exception snapshots, classification, aging, assignment history, evidence pins, immutable disposition/correction references, material close review and controlled reopen | Assignment is coordination metadata, not a workflow engine or permission grant. Correction occurs only in the owning source domain. |
| `P10-S11` | Rebuild/recalculation verification: exact replay checks, successor recalculation, stale-state detection, deterministic locks, idempotency and historical reproducibility | No accepted/finalized run is overwritten. Missing retained input produces `unverifiable`, never a fabricated result. |
| `P10-S12` | Persian-first RTL/Jalali workbench, permission-preserving drill-through, DMS evidence boundary, privacy/minimization, accessible table parity and bounded synchronous operations | No scheduled delivery, general export expansion, provider, queue, notification or external integration. |
| `P10-S13` | Focused PostgreSQL acceptance, clean-schema migration and rollback/reapply, pair-by-pair authority/no-effect assurance, documentation reconciliation and bounded S14 handoff preparation | Completion state is `implementation complete / Product Owner acceptance pending`; no S14 work begins without a new decision and authorization. |

S07–S13 are one proposed runtime tranche. Partial delivery cannot be described as
accepted reconciliation control unless the pair-specific acceptance criteria for
the delivered subset pass and the Product Owner explicitly accepts that subset.

## 3. Ownership and authority model

### 3.1 P10-owned facts

Reporting/Reconciliation may own only:

- code-governed `ReconciliationPair` identity and immutable versions, including
  grain, side roles, adapter versions, cutoffs, comparison rules, tolerance and
  materiality policy pins, readiness and source-owner approvals;
- immutable run, side manifest, tie-out and exception snapshots;
- coordination-only assignment history, immutable dispositions, source-correction
  references and independent close/reopen evidence;
- rebuild-check attempts and exact replay/newer-source comparison evidence; and
- minimized audit references and exact DMS `DocumentVersion`/hash pins.

It may not own a source balance, stock quantity/value, journal, statement,
obligation, allocation, cash movement, claim, contract, budget, commitment,
invoice match, payroll result/proposal, asset book, project cost fact or source
correction. A P10 disposition explains an exception; it does not adjust either
side or certify a source domain's books.

### 3.2 Pair catalogue and source authorities

`Left` and `right` identify comparison roles, not debtor/creditor direction. Every
run pins both authoritative versions and their independently valid statuses.

| Pair code | Governed comparison | Left authority | Right authority | Initial readiness / boundary |
| --- | --- | --- | --- | --- |
| `estimate_budget` | Accepted estimate handoff scope/amounts versus the governing accepted budget baseline and conserved mapping | Estimation owns approved estimate revision/lines | Project Controls owns accepted `BudgetVersion`, manifest and allocations | Ready only for exact pinned handoff versions; legacy Project budget fields are excluded. |
| `commitment_projection` | Effective issued PO/approved cost-contract commitment versus classified Project Cost commitment projection | Procurement or Contracts owns the exact commitment version | Project Controls owns only an accepted producer-contract projection | Pair is `gated/not_activated` when a producer contract is absent; never infer a commitment projection. |
| `po_receipt_invoice` | Issued PO/change versus posted goods receipt or accepted service performance versus AP/Finance supplier-invoice version and immutable match evidence | Procurement owns PO and receipt/service acceptance | AP/Finance owns supplier invoice; Matching owns derived match/discrepancy evidence only | Compare existing immutable match evidence; P10 cannot approve a discrepancy or release AP/stock/cost/cash. |
| `inventory_quantity_value` | Posted/reversed quantity/trace custody versus accepted valuation layers/events for the same stock scope/cutoff | Inventory custody owns quantity and traceability | Inventory Valuation owns monetary layers/policy evidence | Currency, unit, warehouse, material and cutoff must align. Accounting/Project Cost proposals are separate, non-authoritative consumers. |
| `claim_settlement` | Approved receivable claim and active settlement allocation versus the exact Treasury-backed allocation/cash lineage | Billing owns claim and claim-settlement allocation | Treasury owns cash movement; AP/AR owns recognized obligation/allocation where activated | Existing legacy Payment lineage stays explicitly labelled; no cash or AR/AP is synthesized. |
| `subledger_gl` | Recognized AP/AR obligation/allocation totals versus posted Accounting control lines | AP/AR owns subledger facts | Accounting owns journal/statement facts | Consume the domain-native retained reconciliation/review where present. Missing source/posting adapters remain unavailable. |
| `treasury_bank` | Treasury book/clearing facts versus imported bank-statement lines/matches | Treasury owns book movement, clearing and account | Treasury Bank Reconciliation owns statement/match evidence, not a second cash balance | Consume exact domain-native bank runs. No provider parsing or new independent sign-off is implied. |
| `treasury_gl` | Treasury movement source identities/amounts versus posted Accounting journal lines | Treasury owns movement/instrument state | Accounting owns posted lines and existing source-to-GL reconciliation | P10 composes/reference-checks existing retained evidence; it cannot post or close. |
| `project_cost_sources` | Accepted source contracts/events versus Project Cost facts and coverage/rebuild evidence | Each registered producer owns its immutable source fact | Project Controls owns classified projection and coverage | Explicitly incomplete until each producer is activated. Exclusions/uncomparable facts remain visible. |
| `payroll_insurance` | Finalized payroll/employee-insurance run components versus the exact statutory list/reconciliation evidence | Payroll owns finalized run/results | Payroll Statutory owns list/output/reconciliation evidence | Sensitive; exact run/rule/schema/source versions required. Missing official authority/schema is unavailable, not zero. |
| `payroll_financial_handoffs` | Finalized Payroll facts/proposals versus consumer acknowledgment/reconciliation evidence by liability, Accounting, Treasury-payment and Project Cost family | Payroll owns finalized facts and immutable proposal | Named downstream domain owns acknowledgment or later recognition/execution fact | In S07–S13 compare proposal/acknowledgment only. No AP recognition, journal, cash or cost actual may be inferred. |
| `fixed_asset_handoffs` | Fixed Asset book/transaction/depreciation proposal versus Accounting/Project Cost acknowledgment evidence | Fixed Assets owns register/book evidence and proposal | Accounting or Project Controls owns any separately activated consumer fact | Proposal/acknowledgment only unless consumer activation is separately authorized; no GL control balance is invented. |
| `contractor_compliance` | Approved contractor insurance/clearance/assessment evidence versus linked Contract/AP/Accounting references or acknowledgments | Contracts/Compliance owns policy-pinned assessment and clearance evidence | Contract/AP/Accounting each owns its own fact if separately activated | Article 38 interpretation/effect and financial consumption remain gated; missing consumer is `not_activated`. |

The Product Owner may authorize a strict subset. An omitted or not-ready pair is
not silently treated as reconciled. Pair publication requires the accountable
owner of each side, one P10 control owner and the materiality/tolerance approver to
be named in the decision record.

### 3.3 Existing reconciliation authority

Accounting, Treasury/bank, AP/AR, Procurement matching, Payroll, Inventory,
Project Cost and Fixed Assets already retain domain-specific evidence. P10 does
not copy those lifecycles into a generic engine. For such a pair, the P10 adapter
pins and verifies the exact native run/review/hash and may present a cross-domain
summary. A native reconciliation remains the authority for its own control,
disposition and sign-off. Conflicting P10 output is a P10 exception requiring
investigation; it does not invalidate or rewrite the native result.

## 4. Governed comparison semantics

Every published pair version fixes:

1. business question, sides and accountable source owners;
2. organization/project/account/warehouse/contract/run and line grain;
3. included, excluded and terminal statuses for each side;
4. source adapter/version, public identity/version/line and reversal/replacement
   behavior;
5. canonical cutoff/as-of instant, fiscal/operational period, Tenant timezone,
   currency, precision and unit/conversion-policy versions;
6. exact match keys, allowed aggregation and one-to-one/one-to-many/many-to-one
   relationship rules;
7. completeness prerequisites and readiness states;
8. tolerance and materiality policy versions;
9. exception classifications, required evidence and permitted dispositions;
10. sensitivity, retention and source drill-through contract; and
11. reproducibility fingerprint and expected no-effect boundary.

The comparison result for each scope is one of:

- `matched_exact`;
- `matched_within_tolerance` (difference remains visible);
- `mismatch`;
- `missing_left` or `missing_right` only when the pair contract proves the record
  should exist;
- `incomplete` when coverage or required evidence is partial;
- `unknown` when a value/status cannot be established;
- `uncomparable` when currency, unit, grain, period or version alignment is absent;
- `not_applicable` when the pair contract proves exclusion; or
- `gated/not_activated` when a producer/consumer or authority is intentionally
  unavailable.

`unknown`, `incomplete`, `uncomparable` and `gated/not_activated` are never
coerced to `0`, equality or a resolved exception. Proposal, reviewed, recognized,
posted, cleared and reversed states remain distinct. P10 cannot net different
currencies, units, periods, projects, parties or lifecycle states merely to make a
pair balance.

## 5. Tolerance and materiality

- Exact match is the default. A non-zero tolerance requires an immutable,
  effective-dated pair policy approved by both source owners and the P10 control
  owner.
- A policy declares the dimension it governs: Decimal absolute amount, relative
  percentage with a defined denominator, quantity/unit, date/business-day window,
  or controlled rounding. Float is prohibited.
- Currency/unit conversion is allowed only through an authoritative pinned policy
  already accepted for both sides. No P10-owned FX rate, UOM rule or rounding rule
  is introduced.
- Tolerance classifies a difference; it never edits, auto-adjusts, force-matches
  or posts a balancing entry.
- Materiality is separate from tolerance. It governs review priority, independent
  close and escalation, never whether evidence is retained. Qualitative triggers
  (for example duplicate identity, cross-Tenant evidence, missing posting key,
  unauthorized status or broken lineage) are material regardless of amount.
- Unknown/incomplete amounts cannot be declared immaterial. Aggregate materiality
  cannot hide individually prohibited or lineage-breaking items.
- Policy change creates a new pair version. Historical runs retain the old policy
  and are not reclassified in place.

## 6. Reconciliation and exception lifecycle

### 6.1 Pair and run lifecycle

Pair version: `draft -> in_review -> published -> superseded | retired`, with
`draft/in_review -> withdrawn`. Published versions are immutable.

Run: `requested -> capturing -> comparing -> completed | failed | cancelled`.
Cancellation is allowed only before source capture. A completed run and its side,
tie-out and exception snapshots are immutable. A completed material financial run
may additionally be `review_pending -> accepted | rejected` through append-only
review evidence; rejected does not delete the run.

A run pins organization, scope, pair version, cutoff, source transaction snapshot
or equivalent reproducible watermarks, ordered source manifests/hashes, policy
versions, coverage, totals, classifications, generated time/actor and calculation
fingerprint. One side being unavailable completes as an explicit non-success
comparison state when that state is itself reproducible; it does not fabricate a
number.

### 6.2 Exception lifecycle

An exception is an immutable snapshot in a run plus an append-only coordination
history:

`open -> assigned -> in_review -> disposition_recorded -> close_pending -> closed`

`closed -> reopened` requires a reason, new evidence or a source/version change,
and a separately authorized reopen action. Reopen creates a new lifecycle event;
it never deletes the earlier closure. Assignment can change through history and
does not grant source, evidence or action permission.

Required classification families are:

- existence: missing expected side, orphan, duplicate;
- identity/version: wrong source, stale version, superseded/reversed source,
  duplicate integration/posting key;
- amount/quantity: exact difference, rounding/tolerance, cap/conservation breach;
- context: Tenant/project/party/account/warehouse/WBS/CBS/cost-center mismatch;
- time: cutoff, effective date, accounting/operational period mismatch;
- status: draft/proposal/recognized/posted/cleared/reversed mismatch;
- policy/mapping: absent or incompatible currency, UOM, posting, classification,
  regulatory or tolerance version;
- coverage/lineage: incomplete adapter, inaccessible evidence, missing hash/pin;
  and
- integrity/security: cross-Tenant reference, unauthorized state or hash failure.

Permitted dispositions are `source_correction_required`,
`source_correction_recorded`, `valid_timing_difference`,
`accepted_within_policy`, `duplicate_confirmed`, `not_applicable_confirmed`,
`gated_dependency`, and `unable_to_verify`. Each disposition requires reason,
actor/time, exact exception/run/pair version, evidence and/or source-correction
reference prescribed by the pair version. A disposition never changes comparison
amounts or authoritative facts.

Closure requires the current source/version to be rechecked. A material financial,
integrity or security exception requires an independent closer who differs from
the runner and last disposer. Non-material timing/tolerance cases may use the
pair's explicitly approved lighter rule. Source correction is made through the
source domain's permissions and lifecycle, then a new reconciliation run proves
the effect; a link alone does not claim that the exception disappeared.

## 7. Rebuild, recalculation and historical reproducibility

Three operations remain distinct:

| Operation | Input basis | Result |
| --- | --- | --- |
| Exact replay check | Original pair version, manifests, cutoff, policies and source versions | Immutable `RebuildCheck`: `matched`, `mismatched` or `unverifiable`; never changes the original run. |
| Successor recalculation | Same pair version or an explicitly newer pair version plus current/newer authoritative source heads | New immutable run linked as successor; old accepted run remains historical. |
| Projection repair | Authoritative P10 run/exception events rebuild only mutable indexes/current pointers | Recreated projection with before/after hashes; no run, disposition, review or source history rewrite. |

An exact replay uses retained snapshots or exact immutable source versions. If
retention, access or a legacy gap prevents replay, the result is `unverifiable`
with the missing requirements recorded. A value is never reconstructed from a
later source head and presented as the old result.

A newer source correction marks an earlier current presentation `stale` by rule
but does not alter the earlier run. The UI may switch its current pointer only to
a completed, permission-valid successor and, where material, after independent
review. The stale and successor relationship stays visible.

Stable identities are:

- run: `organization + pair-version + scope fingerprint + cutoff + ordered
  source-watermark fingerprint`;
- exception: `run + classification + side identities/versions + comparison grain`;
- lifecycle action: `organization + exception + action + operation key`; and
- replay: `organization + original run + replay-engine version + operation key`.

Same key/same payload returns the original outcome. Same key/different payload
fails closed. Services lock pair version, scope/current pointer, source heads where
owned locks are available, run and exception in a documented deterministic order;
authorization, source status and stale preconditions are rechecked inside
`transaction.atomic()`. Concurrent identical requests produce one authoritative
outcome. Failed/cancelled attempts do not replace the last valid current result.

## 8. Permissions and separation of duties

All new codes require `BusinessPermissionCode`, `permission_registry`, an
expand-only catalogue/default-grant migration, service/view enforcement and
Tenant-isolation tests. **Recommended default grants: none.** Existing Reporting
or source permissions do not imply these permissions, and these permissions do
not imply source access.

| Proposed permission | Consequential boundary |
| --- | --- |
| `reporting.reconciliation_catalog.view` | View published pair metadata; no result/source access. |
| `reporting.reconciliation_definition.prepare` | Prepare a pair-version candidate; cannot publish it. |
| `reporting.reconciliation_definition.publish` | Publish/supersede/retire after both source-owner reviews; author cannot publish own candidate. |
| `reporting.reconciliation_run.execute` | Run a published pair synchronously within effective object scope. |
| `reporting.reconciliation_run.view` | View permitted runs/tie-outs; source details still require source permissions. |
| `reporting.reconciliation_run.review` | Accept/reject a material run; reviewer differs from runner. |
| `reporting.reconciliation_exception.view` | View minimized exception facts in scope. |
| `reporting.reconciliation_exception.assign` | Record coordination assignment; grants no other authority. |
| `reporting.reconciliation_exception.disposition` | Record immutable reason/evidence/correction reference; cannot mutate source. |
| `reporting.reconciliation_exception.close` | Close under pair policy; independent for material/integrity/security cases. |
| `reporting.reconciliation_exception.reopen` | Reopen with reason/evidence; separately granted and audited. |
| `reporting.reconciliation_evidence.link` | Link an already authorized exact DMS version; does not grant byte access. |
| `reporting.reconciliation_rebuild.execute` | Run exact replay/successor/projection check; cannot overwrite history. |
| `reporting.reconciliation_rebuild.review` | Independently review mismatch/unverifiable rebuild evidence. |
| `reporting.reconciliation_audit.view` | View minimized P10 control history; no sensitive source payload. |

Every view/action requires active membership, active Tenant, pair/result permission
and applicable project/account/warehouse/contract/object scope. Drill-through also
rechecks the source domain's ordinary permission. Sensitive payroll, bank,
commercial, party, document and person data retains the stricter source
classification and permission.

The runner cannot accept their own material financial run. The last disposer
cannot solely close a material, integrity or security exception. A pair author
cannot publish that version. A P10 user cannot correct a source without the
source-domain permission and lifecycle. Tenant Owner/Admin, position, assignment,
Platform Admin and Superuser provide no exception. Platform staff require an
independently approved, purpose/time/scope-bound Tenant-access grant.

## 9. DMS, evidence and Audit boundaries

- DMS alone owns bytes and immutable versions. P10 stores only exact
  `DocumentVersion` public identity/hash, evidence role, sensitivity and the
  access decision needed for the control history.
- Existing source-domain evidence stays source evidence; P10 references it rather
  than uploading a duplicate. New exception evidence uses the existing safe DMS
  path and inherits the strictest source/exception sensitivity.
- Linking never grants download. Every view/download rechecks DMS, source-domain,
  Tenant and object permissions. Redacted/unavailable evidence remains visibly so.
- Audit records action evidence: pair publication, execution, review, assignment,
  disposition, close/reopen, evidence link, rebuild and denied attempts. It does
  not store source payloads, become a reconciliation side or reconstruct missing
  business facts.
- Required audit fields include Tenant, public IDs, actor/membership, action/time,
  reason, pair/run/exception version, scope/cutoff, before/new lifecycle state,
  correlation and idempotency keys, source/DMS pins and result hashes. Sensitive
  values are minimized.

## 10. Tenant/Platform privacy and UI contract

All pair definitions instantiated for business use, runs, exceptions, assignment
history, evidence links, rebuild checks and saved filters are Tenant-scoped.
Platform code may supply a non-executable pair template catalogue, but Platform
Admin/Superuser has no implied Tenant-result visibility. Cross-Tenant aggregation,
benchmarking, publication or support access is excluded.

The S12 workbench is Persian-first, RTL and mobile-responsive. It must show pair,
both authorities, scope, cutoff, currency/unit/period, readiness, coverage,
freshness/staleness, exact difference, tolerance and materiality policy, lifecycle,
assignee, evidence/correction lineage and rebuild status. Dates persist
canonically and display Jalali with unambiguous time/timezone. Charts require
equivalent accessible tables. Keyboard/focus/error behavior, Persian labels and
private/non-cacheable responses are acceptance requirements. Redaction,
`unknown`, `incomplete`, `uncomparable`, `not_applicable`, `gated/not_activated`,
`stale` and `unverifiable` must be visibly distinct from zero and match.

## 11. Expand-only, non-fabricating migration posture

S07–S13 may add only new P10 tables, indexes, constraints and permission-catalogue
rows required by accepted decisions. It must not rename/drop/retype a source field,
rewrite a domain-native reconciliation, promote legacy `financials`, or activate a
producer/consumer.

No migration may infer a source version, owner, cutoff, tolerance, materiality,
pair readiness, result, exception, disposition, evidence, review or freshness.
Existing domain-native runs remain where they are and may be referenced only by
exact deterministic pins. Legacy or incomplete rows remain unlinked/unknown with
explicit migration evidence. Historical zeros/defaults are not proof of value.
Backfill is permitted only when all inputs and the deterministic rule already
exist; otherwise leave nullable/unknown and fail closed at consequential use.

Rollback removes only the new P10 structures and grants after proving that no
source-domain or accepted P10-S02–S06 record changed. Contract/removal work is not
authorized in this tranche.

## 12. Downstream no-effect and preserved gates

No P10 comparison, exception, assignment, disposition, closure, review or rebuild:

- posts/reverses a journal or closes/reopens an Accounting period;
- recognizes/writes off an AP/AR obligation or allocation;
- moves, clears, matches or settles cash;
- issues/changes a PO, accepts a receipt/service, approves an invoice or force
  matches a discrepancy;
- changes a budget, commitment, Project Cost actual/forecast or source contract;
- moves/revalues stock, changes custody or produces an Inventory/Accounting cost;
- approves/settles a claim, changes a contract, applies contractor insurance or
  clearance effects;
- finalizes payroll/statutory output, creates a liability/payment/journal/cost;
- capitalizes/depreciates/transfers/impairs/disposes an asset; or
- creates a workflow work item, notification, provider call, scheduled/background
  job, integration event or production decision.

Preserved outside this envelope: all `P10-S14+`; project closeout; release
certification and production gates; AI/RAG/embeddings/vector/semantic search;
external providers, publication/search and integrations; queues, schedulers and
automated retries/delivery; a warehouse; official/legal/regulatory activation;
all dormant producer/consumer activation; automatic operational/financial
effects; production cutover/activation; and `S25-G10`.

The six inherited failures in
`apps.organizations.test_permission_registry` remain separate non-blocking
repository debt. S07–S13 must neither fix them opportunistically nor count them as
new P10 failures. Focused acceptance must prove every new P10 code is uniquely
registered, enforced and has no default grant; any overlap with those six failures
is a blocker requiring explicit re-scoping.

## 13. Complete Product Owner decision register

No recommendation is authorization. Every row must be explicitly accepted,
rejected or replaced before runtime work.

| Stable ID / decision | Options | Recommendation and rationale | Applies |
| --- | --- | --- | --- |
| `P10-R01` Envelope | A: S07–S13 only; B: include closeout S14–S17; C: include certification | **A.** Matches the official seven-session map and preserves later gates. | All |
| `P10-R02` Owning boundary | A: P10 owns comparison/control evidence only; B: central financial authority; C: each pair duplicated in P10 | **A.** Prevents a parallel ledger/subledger/source authority. | All |
| `P10-R03` Pair catalogue | A: code-governed immutable versions; B: Tenant-authored expressions/SQL; C: hard-coded unversioned services | **A.** Reproducible and bounded; prohibits executable Tenant logic. | S07–S13 |
| `P10-R04` Initial pair set | A: the 13 named pairs, each readiness-gated; B: generic arbitrary pairs; C: finance pairs only with unrecorded omissions | **A.** Covers Roadmap scope without pretending dormant consumers exist. Product Owner may explicitly authorize a smaller named subset. | S07–S13 |
| `P10-R05` Existing native reconciliations | A: reference/verify exact native evidence; B: replace in P10; C: copy results as new authority | **A.** Preserves Accounting/Treasury/AP-AR and other source controls. | S08–S13 |
| `P10-R06` Missing consumer/producer | A: `gated/not_activated`; B: missing/zero; C: fabricate expected row | **A.** Truthfully preserves dormant activation gates. | S08–S13 |
| `P10-R07` Missing/inaccessible value | A: unknown/incomplete/unverifiable; B: zero; C: omit silently | **A.** Non-fabricating and audit-visible. | S08–S13 |
| `P10-R08` Comparison status taxonomy | A: explicit statuses in section 4; B: pass/fail only; C: numeric difference only | **A.** Separates absence, inapplicability, incompleteness and mismatch. | S08–S13 |
| `P10-R09` Cutoff | A: pair-versioned consistent cutoff/manifests; B: query-time heads; C: dashboard timestamp only | **A.** Enables deterministic comparison and replay. | S08–S13 |
| `P10-R10` Status semantics | A: proposal/review/recognition/post/clear/reverse distinct; B: all approved-like states equal; C: latest row wins | **A.** Prevents false financial equivalence. | S07–S13 |
| `P10-R11` Currency/unit/period | A: exact alignment or authoritative pinned conversion; B: P10 defaults; C: ignore mismatch | **A.** Avoids invented conversion and false tie-out. | S07–S13 |
| `P10-R12` Tolerance default | A: exact unless versioned approved policy; B: global percentage; C: user-entered per run | **A.** Deterministic and domain accountable. | S07–S13 |
| `P10-R13` Tolerance effect | A: classify only and show difference; B: auto-adjust/force match; C: hide within-tolerance lines | **A.** Retains evidence and no-effect behavior. | S08–S13 |
| `P10-R14` Materiality | A: separate versioned amount/qualitative policy; B: same as tolerance; C: no materiality | **A.** Supports risk-based review without erasing exceptions. | S07–S13 |
| `P10-R15` Unknown materiality | A: cannot assert immaterial; B: treat as zero; C: exclude | **A.** Fails closed when magnitude is unknowable. | S10–S13 |
| `P10-R16` Run storage | A: immutable run/sides/tie-outs/exceptions; B: mutable current row; C: ephemeral result | **A.** Required for lineage and historical reproducibility. | S08–S13 |
| `P10-R17` Material run review | A: independent review; B: runner self-accepts; C: no acceptance state | **A.** Proportionate maker-checker for financial control evidence. | S08–S13 |
| `P10-R18` Exception model | A: immutable snapshot plus append-only lifecycle events; B: editable ticket; C: overwrite status/reason | **A.** Preserves original discrepancy and every decision. | S10–S13 |
| `P10-R19` Assignment | A: coordination metadata only; B: grants permission/work item; C: omit history | **A.** Useful routing without a second workflow/authorization engine. | S10–S13 |
| `P10-R20` Source correction | A: source domain only, then new run; B: edit from P10; C: balancing plug | **A.** Preserves source ownership and proves correction. | S10–S13 |
| `P10-R21` Disposition | A: reasoned immutable evidence, no value effect; B: disposition edits tie-out; C: free-text mutable note | **A.** Separates explanation from financial/operational truth. | S10–S13 |
| `P10-R22` Exception close | A: recheck current source; independent close for material/integrity/security; B: disposer closes all; C: auto-close on link | **A.** Prevents stale/self-certified closure. | S10–S13 |
| `P10-R23` Reopen | A: separate permission and append-only reason/evidence; B: edit closed row; C: prohibit reopen | **A.** Controlled recovery without history loss. | S10–S13 |
| `P10-R24` Exact replay | A: immutable matched/mismatched/unverifiable check; B: overwrite original; C: use latest source | **A.** Tests reproducibility without rewriting history. | S11–S13 |
| `P10-R25` Newer-source recalculation | A: linked successor run; B: update accepted run; C: hide old run | **A.** Keeps accepted historical governed results intact. | S11–S13 |
| `P10-R26` Projection repair | A: rebuild indexes/current pointers only with hashes; B: regenerate history; C: manual SQL | **A.** Recoverable and auditable. | S11–S13 |
| `P10-R27` Stale state | A: derived visible state plus reviewed successor switch; B: silent refresh; C: delete stale | **A.** Honest currentness and preserved evidence. | S11–S13 |
| `P10-R28` Idempotency/concurrency | A: stable fingerprints, atomic locks/rechecks; B: best effort; C: UI debounce | **A.** Prevents duplicate/conflicting runs and stale actions. | S07–S13 |
| `P10-R29` Permissions/default grants | A: 15 dedicated codes, no defaults; B: reuse metric/source roles; C: role-name checks | **A.** Deny-by-default with explicit action boundaries. | S07–S13 |
| `P10-R30` Drill-through | A: P10 plus source/DMS permission recheck; B: P10 permission reveals all; C: no drill-through | **A.** Prevents permission laundering while retaining explainability. | S08–S13 |
| `P10-R31` DMS/evidence | A: exact version/hash pins, DMS owns bytes; B: copy bytes to P10; C: mutable URL | **A.** Preserves one evidence authority and retention. | S10–S13 |
| `P10-R32` Tenant/Platform privacy | A: Tenant-local, no implicit Platform access/cross-Tenant analytics; B: Platform readable; C: global pool | **A.** Preserves isolation and purpose-bound support. | All |
| `P10-R33` UI | A: Persian RTL/Jalali, accessible table parity and explicit non-value states; B: English-only admin; C: chart-only | **A.** Meets the approved product UX and prevents false-zero display. | S12–S13 |
| `P10-R34` Migration | A: expand-only/non-fabricating, exact backfill only; B: infer/backfill defaults; C: replace native runs | **A.** Protects accepted history and rollback. | S07–S13 |
| `P10-R35` Execution mode | A: explicit bounded synchronous operations; B: queues/schedulers/providers; C: automatic on source writes | **A.** Matches the current infrastructure and authorization boundary. | S08–S13 |
| `P10-R36` Acceptance/closeout | A: focused PostgreSQL plus Product Owner acceptance; B: engineer self-accepts; C: full production certification | **A.** Proportionate evidence while preserving S14+ and production gates. | S13 |

**Recommended Product Owner decision:** accept `P10-R01`–`P10-R36 = Option A`,
name the pair-side owners/P10 control owner/materiality approver for every
authorized pair, name the S13 acceptance owner and Authorized Technical
Maintainer, and list any explicitly tolerated Medium/Low risk. If the Product
Owner chooses a smaller initial pair set under R04, the exact codes must be listed;
all others remain unauthorized and visibly unavailable.

## 14. Focused PostgreSQL validation plan

Use one uniquely named disposable PostgreSQL database and one runner. Do not use,
inspect, migrate, reset or drop `test_construction_erp`. Start with focused P10
tests; expand only for an actual shared-boundary change or focused failure.

Minimum acceptance cases:

1. cross-Tenant definition/run/exception/evidence/rebuild reads and writes fail;
2. inactive Tenant/membership, missing P10 permission and missing object scope
   fail at service and view boundaries;
3. Platform Admin/Superuser has no implicit Tenant data access;
4. each new permission code is uniquely registered, enforced and default-ungranted,
   independent of the six preserved unrelated registry failures;
5. pair author cannot publish own version and both source-owner approvals are
   pinned; stale/concurrent publication yields one version;
6. every authorized pair proves exact source authority, statuses, adapter version,
   scope, cutoff, currency/unit/period and no mutation of either side;
7. existing native reconciliation is referenced by exact ID/version/hash and is
   neither copied as authority nor changed;
8. missing expected side differs from unknown, incomplete, uncomparable,
   not-applicable and gated/not-activated;
9. missing/unknown/inaccessible values never become zero, matched or immaterial;
10. proposal/review/recognition/post/clear/reverse states cannot compare as equal
    unless the pair version explicitly maps the same authoritative state;
11. exact match is default; Decimal tolerance boundary, relative denominator,
    unit/date tolerance and qualitative materiality behave deterministically;
12. within-tolerance differences remain visible and create no adjustment;
13. concurrent identical run requests create one immutable run; key/payload
    collision fails closed and failed attempts do not replace current results;
14. run/source/tie-out/exception hashes and ordered manifests reproduce at the
    original transaction snapshot/cutoff;
15. exception classification, assignment history, immutable disposition,
    correction reference, close and reopen preserve full lineage;
16. runner cannot review own material run; last disposer cannot solely close a
    material/integrity/security exception; ordinary non-consequential viewing is
    not over-constrained;
17. source correction requires source-domain permission/service and only a new
    run can demonstrate resolution;
18. exact replay reports matched, mismatched or unverifiable and never changes the
    original accepted run;
19. newer-source recalculation creates a linked successor, marks old presentation
    stale and never rewrites its result, exceptions, dispositions or review;
20. projection repair rebuilds only derived indexes/current pointers and verifies
    before/after hashes;
21. evidence pins exact DMS version/hash, stores no bytes, inherits sensitivity
    and rechecks DMS/source permission on access;
22. Persian RTL/Jalali UI distinguishes zero from every non-value/readiness state,
    provides accessible table parity, correct focus/errors and private/no-cache;
23. every run, exception and rebuild has no Accounting/Treasury/Project Cost/
    Inventory/Procurement/Contract/Payroll/Asset/workflow downstream mutation; and
24. clean-schema migration, dependency-safe rollback/reapply, migration drift,
    Django checks, targeted Ruff/format, template/URL, local-link and diff-hygiene
    checks pass without changing P0–P9 or P10-S02–S06 history.

Pair-specific tests must deliberately inject a mismatch, missing source, reversed
or superseded source, stale cutoff and incompatible currency/unit/period for each
implemented adapter. Do not run the broad suite unless a focused result establishes
a concrete expansion trigger.

## 15. Preserved gates and documentation closeout

This implementation packet updates the P10 disposition in `ROADMAP.md`, the
execution map, and the directly affected domain/data/capability/permission
summaries. The Product Owner accepted P10-S07–S13 after reviewing the recorded
assurance evidence. The authoritative documents remain aligned on these facts:

- P10-S02–S06 is accepted;
- P10-S07–S13 is Product Owner accepted;
- source domains remain authoritative and P10 cannot become a parallel domain;
- unknown/incomplete/unverifiable never becomes zero;
- accepted history is immutable and rebuild creates evidence or a successor;
- the six unrelated permission-registry failures remain separate non-blocking
  debt; and
- all S14+, AI/provider/queue/integration/downstream/production gates remain.

## 16. Recorded bounded runtime authorization

> The Product Owner accepts `P10-R01`–`P10-R36 = Option A` as recorded in this
> packet and authorizes implementation of **P10-S07–S13 only**, for exactly these
> governed pair codes: `estimate_budget`, `commitment_projection`,
> `po_receipt_invoice`, `inventory_quantity_value`, `claim_settlement`,
> `subledger_gl`, `treasury_bank`, `treasury_gl`, `project_cost_sources`,
> `payroll_insurance`, `payroll_financial_handoffs`, `fixed_asset_handoffs`, and
> `contractor_compliance`. Source Owner remains the authoritative domain owning
> each compared fact; Reporting/Reconciliation is the governance/control-evidence
> owner; final tranche acceptance owner is the Product Owner; and the
> non-production migration/rebuild executor is the Authorized Technical
> Maintainer. This authorization excludes all other pairs, `P10-S14+`, AI/RAG/
> vector, providers, queues/schedulers, integrations, automatic downstream or
> financial effects, production activation and source-domain mutation.

## 17. Implementation, assurance and Product Owner acceptance closeout

The accepted bounded runtime is implemented and Product Owner accepted. It provides the exact 13
code-governed pair definitions, deterministic Decimal comparison and explicit
unknown/incomplete/gated/uncomparable states; no source value is fabricated as
zero. Immutable run, side, tie-out, exception-event and evidence snapshots pin
source/version, policy, cutoff and DMS evidence lineage. Corrections remain in
the source owner; reconciliation stores only immutable reference evidence.

Rebuild performs an exact replay or records an unverifiable result. A newer-source
calculation creates a linked successor and makes the predecessor visibly stale;
it never mutates an accepted historical run, its result, review or exception
history. Advisory locking, transaction rechecks and idempotency keys control
concurrent execution and exception retries.

The implementation adds 15 default-deny permissions for catalogue, definition,
run, exception, evidence, rebuild and audit operations. It enforces source
permission rechecks, Tenant scope, Platform/Tenant separation, pair-author versus
publisher separation, material-run review separation and material exception
close/reopen separation. The RTL/Jalali workbench provides governed drill-through
and no-cache private evidence views without DMS byte storage.

Focused PostgreSQL assurance passed 25 tests covering the 24 packet acceptance
areas, including every pair, isolation, source authorization, tolerance/
materiality, lifecycle, immutable lineage, replay/successor, stale-state,
idempotency, SoD, drill-through, no-effect and RTL/Jalali boundaries. The retained
P10-S02–S06 plus S07–S13 focused suite passed 41 tests. Clean-schema migration
and dependency-safe rollback/reapply passed using the uniquely named disposable
database `test_p10_s0713_accept_20261007_2315`; it was not
`test_construction_erp`.

Defects corrected during assurance were PostgreSQL nullable relation locking,
empty structured exception evidence, retry ordering that could advance an
exception twice, and a retained S02–S06 permission-count assertion. The six
unrelated `apps.organizations.test_permission_registry` failures remain separate
non-blocking repository debt. All `P10-S14+`, AI/RAG/vector, providers,
queues/schedulers, integrations, downstream effects and production gates remain
preserved. The next official P10 envelope is P10-S14–S17 only; it requires new,
separately recorded Product Owner decisions and bounded authorization.
