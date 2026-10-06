# P10-S01–S06 Governed Metrics and Reporting Decision Packet

**Status:** **P10-S01 planning and decision preparation complete; Product Owner
decisions and runtime authorization pending.**

**Date:** 2026-10-07.

**Authority:** planning proposal derived from `ROADMAP.md`, the P10 session map in
`docs/ROADMAP_EXECUTION_PLAYBOOK.md`, and the formally closed P9 baseline in
`P9_FINAL_ASSURANCE_CLOSEOUT_AND_P10_HANDOFF.md`.

**Runtime effect:** none. This packet does not authorize models, migrations,
permissions, services, APIs, workflows, UI, jobs, queues, integrations, exports,
production cutover, or production activation.

## 1. Entry gate and exact official envelope

The prerequisite is verified:

- `P9-S01–S25 = Product Owner accepted`;
- `P9-S26 = closeout complete`;
- `P9 = Product Owner accepted / phase closed`.

The first official P10 envelope is exactly **P10-S01–S06**. The Execution
Playbook classifies the six-session tranche `A-H` and names its outcome **Metric
catalogue, governed read models, dashboards and source drill-through**. The
Roadmap names P10.1 **Governed metrics and management reporting**, status
`PLANNED`, and additionally identifies saved views, freshness indicators and
scheduled reports/exports as target outcomes. The Roadmap does not authorize a
separate warehouse.

This tranche starts planning-first. P10-S01 is this decision packet. Runtime for
P10-S02–S06 remains blocked until the Product Owner records the required choices
and supplies the bounded authorization in section 16. The official map fixes the
ending at S06; no later session number is inferred.

## 2. Session-by-session decomposition

| Session | Proposed bounded outcome | Prerequisites / stop condition |
| --- | --- | --- |
| P10-S01 | Entry verification, ownership analysis, metric-governance contract, lifecycle/permission/privacy/migration decisions, first-release selection, validation plan and bounded authorization wording | P9 closeout verified. Documentation only; stop with decisions and runtime authorization pending. |
| P10-S02 | Reporting domain foundation: permission catalogue, versioned Metric Definition catalogue and immutable publication/supersession evidence | Accepted `P10-M01`–`P10-M24`; exact domain/source contracts; no dashboard/result implementation beyond what S02 needs. |
| P10-S03 | Governed synchronous read-model build/refresh records, source watermarks, completeness/freshness/stale evidence, deterministic rebuild and immutable result lineage | Published metric versions from S02; stable source adapters; no queue, scheduler or warehouse. |
| P10-S04 | Tenant/project/portfolio Persian RTL dashboards, saved views, accessible chart/table parity and permission-preserving source drill-through | S03 results; source-domain read permissions/object scope enforced at drill-through; no unrestricted SQL or AI. |
| P10-S05 | Bounded on-demand report/export, exact result/source manifest, private non-cacheable delivery, audit and DMS retention boundary | Explicit export decisions and permissions; no scheduled delivery, email/SMS/push provider, background queue or external integration. |
| P10-S06 | Focused PostgreSQL acceptance, deterministic rebuild/tie-out, migration rollback/reapply, privacy/accessibility assurance, documentation reconciliation and bounded P10-S07 handoff preparation | All S02–S05 acceptance criteria pass. Finish as `implementation complete / Product Owner acceptance pending`; do not start S07. |

S02–S06 form one coherent possible runtime authorization after decisions. Session
completion never authorizes P10-S07+, production certification, cutover or
activation.

## 3. Inherited non-negotiable boundaries

P10 inherits without weakening:

1. Every Tenant-owned definition, saved view, projection, result, refresh,
   export manifest and history row is Organization-scoped. Active membership,
   Tenant status, business permission and applicable project/site/object scope
   are rechecked at service and view boundaries.
2. Platform Admin and Superuser have no implicit Tenant business-data access.
   Platform operation, support access and Tenant business use remain distinct.
3. Source domains own business facts. Reporting owns only governed metric
   definitions, immutable derived results and rebuild/refresh evidence. It cannot
   approve, correct or mutate a source fact.
4. DMS alone owns retained document/export bytes and immutable versions. P10 may
   pin an exact `DocumentVersion` and hash; it never copies bytes.
5. Audit is append-only action evidence, not a source of metric facts, workflow,
   notification, or an alternate result store.
6. Every result pins metric-definition version, source adapter/version, source
   identities or a reproducible source manifest, source cutoff/watermark,
   calculation fingerprint, currency/unit/timezone/period and generated time.
7. Published definitions and finalized results are immutable. Change uses a new
   definition version, refresh/rebuild, correction, replacement or supersession
   link; accepted P0–P9 history is never rewritten.
8. Consequential permissions deny by default. Position, title, dashboard
   visibility and notification never grant authority. Accepted SoD and
   membership-scoped authorization remain in force.
9. Migration is expand-only and non-fabricating. No historical definition,
   owner, approval, result, source pin or freshness status is inferred.
10. UI is Persian-first, RTL, Jalali for display, accessible and permission-aware.
    Persistent dates remain canonical and metric currency/unit/period labels are
    explicit.
11. P10 outputs have no automatic operational or financial effect. Drill-through,
    download and a displayed exception do not create an assignment, approval,
    posting, payment, cost, stock, payroll, contract or workflow transition.

## 4. Ownership and authority model

### 4.1 Owning domain and fact classes

The proposed owning domain is **Reporting and Analytics**, implemented as a
bounded `reporting` module after approval. It owns:

- versioned metric identity, definition, grain, formula, filters, owner,
  sensitivity, allowed dimensions, unit/currency/time basis, freshness target and
  registered source-adapter contract;
- publication/supersession/retirement evidence for metric definitions;
- immutable derived result and dimension rows, result/source manifests,
  refresh/rebuild attempts, watermarks, completeness and freshness evidence;
- Tenant-scoped dashboard composition and saved-view configuration;
- on-demand export manifests and, only when retained as evidence, exact DMS pins.

It does **not** own budgets, commitments, costs, journals, cash, procurement,
inventory, equipment/assets, workforce/payroll, contracts/claims, Field/HSE/QA,
partners, support, Knowledge, documents, memberships, permissions, or Audit facts.

| Fact class | P10 treatment |
| --- | --- |
| Authoritative | Metric-definition/version governance and P10-owned immutable derivation/refresh/export evidence only. |
| Derived | Metric values, dashboard totals, completeness, freshness and presentation-ready dimensions calculated from exact authoritative inputs. |
| Referenced | Tenant/project/site/WBS/CBS/cost-center identifiers, source record/version/status, fiscal/calendar period, currency/unit policy and DMS pins. |
| Cross-domain sources | Organizations/Projects; P2 Accounting; P3 Treasury/AP/AR; P4 budget/project cost; P5 Procurement; P6 Contracts/Billing; P7 Workforce/Payroll; P8 Inventory/Equipment/Fixed Assets. P9 facts remain available only through separately approved metrics and their source permissions. |
| Downstream consumers | Authorized managers, analysts, finance/project-control users and auditors; P10.2 reconciliation may later consume exact result/source evidence, but S01–S06 creates no reconciliation exception or close authority. |

### 4.2 Authority-collision register

| Existing authority | Collision risk | Required containment |
| --- | --- | --- |
| `apps.financials` compatibility dashboard | It currently calculates `variance = approved estimate - recorded expense` and mixes legacy posted `Payment`; this is not accepted budget-versus-actual semantics or Treasury cash authority. | Freeze as compatibility behavior, label it legacy/non-governed, and do not migrate or alias its figures into P10. P10 uses published definitions and authoritative adapters. Removal or replacement is a later explicit contract. |
| Accounting statements and retained reconciliation | A generic P10 total could appear to replace posted-ledger statements or close evidence. | Accounting remains sole journal/statement authority. P10 references exact posted lines/retained statement versions and cannot close/reopen a period. |
| Project Cost read models | Recalculating actual/commitment/forecast independently would create a competing cost authority. | Project Controls remains cost semantic owner. P10 consumes its accepted source contracts/facts and preserves incomplete-coverage labels. |
| Treasury/AP/AR, Payroll, Inventory, Equipment and Fixed Assets proposals | A proposal can be mistaken for recognized actual, liability, cash, journal or cost. | Metrics distinguish proposed, reviewed, recognized, posted, cleared and reversed statuses. No proposal is promoted to an authoritative downstream fact. |
| Domain dashboards/reconciliations | Centralizing lifecycle decisions would bypass domain ownership. | P10 may compose read-only links and summaries; domain services and ordinary permissions remain authoritative. P10.2 exception/close workflows are outside S01–S06. |
| DMS and Audit | Export or audit rows could become a duplicate evidence store. | DMS retains bytes/versions; Audit retains action evidence. Reporting stores only typed pins/manifests and minimized identifiers. |

## 5. Proposed first-release metric catalogue

The recommended first runtime slice is deliberately smaller than the long-term
KPI catalogue. Every metric is Tenant-scoped; portfolio aggregation includes only
projects within the actor's effective scope. Missing or gated inputs remain
`unknown/incomplete`, never zero.

| Metric | Definition boundary and grain | Authoritative inputs / owner | Required drill-through |
| --- | --- | --- | --- |
| Approved budget | Sum of the currently governing accepted budget-version lines, by Tenant/project/period and currency; no estimate substitution | P4 Budget / Project Controls | Budget version, line, WBS/CBS/cost-center mapping and acceptance evidence |
| Committed cost | Active approved contractual/issued-PO commitments net only of approved changes, separately by source family | Contracts and Procurement; Project Controls classifies | Contract/amendment or issued PO version and classified commitment fact |
| Actual cost with coverage | Sum of recognized classified Project Cost facts by project/period/source family; proposal-only and missing producers excluded and explicitly reported as coverage gaps | P4 Project Cost over accepted producer facts | Cost fact, exact source/version/status, mapping and reversal/replacement lineage |
| Cleared cash position | Cleared Treasury book movements by account/as-of date/currency; legacy `Payment` is not silently substituted | P3 Treasury | Account, instrument/movement, clearing and reversal evidence |
| Procurement cycle time | Deterministic elapsed time between registered request/order/receipt state events; open cycles shown separately and no Audit-only inference | P5 Procurement/workflow source history | Request/order/receipt version and transition timeline |
| Inventory quantity and value | Posted less reversed quantity and accepted Inventory valuation evidence, separated by warehouse/material/as-of cutoff; missing-cost exceptions visible | P8 Inventory | Stock movement, custody, valuation pool/event, policy/source version and reversal |

Forecast-at-completion, earned-value/cost performance, payroll/person metrics,
partner scoring, HSE/QA metrics, project-closeout, reconciliation health and
cross-Tenant benchmarking are excluded from the first runtime slice. They require
later source stability, sensitivity or tranche decisions. The catalogue can name
them as future candidates but cannot publish executable definitions for them in
S01–S06.

Each published definition must state: stable code, title, business question,
grain, formula, dimensions, included/excluded statuses, source owner/adapter and
version, time/cutoff basis, Tenant timezone, currency/unit and conversion policy,
late-correction/reversal behavior, completeness rules, sensitivity, metric owner,
reviewer, freshness target, allowed scopes, and drill-through contract.

## 6. Lifecycle and concurrency contracts

### 6.1 Metric definition/version

`draft -> in_review -> published -> superseded`

`draft/in_review -> withdrawn` is allowed with a reason. A published version is
immutable and cannot return to draft. A correction creates a new version linked
as replacement/supersession; retirement publishes a terminal `retired` successor
that prevents new refreshes without deleting historical results. Publication
locks the metric identity and candidate version, rechecks permission/SoD/source
contract inside `transaction.atomic()`, allocates the next version exactly once,
and rejects stale review. Stable idempotency identity is
`organization + metric code + candidate version + publication operation key`;
same key/same fingerprint returns the original outcome, while a changed payload
fails closed.

### 6.2 Refresh/rebuild attempt and result

`requested -> building -> succeeded | failed | cancelled`

Only explicit, synchronous, user-initiated execution is authorized for the first
slice. Cancellation is available only before source capture begins; after that,
failure retains attempt evidence. A successful result is immutable. It becomes
`stale` as a derived condition when its source watermark/cutoff no longer meets
the definition's freshness contract, and may later be linked to a replacement
result. Stale results remain visible with warning and cannot masquerade as fresh.

The idempotency identity is `organization + metric-version + scope fingerprint +
as-of/cutoff + source-watermark fingerprint`. Same key/same fingerprint returns
the existing result; a collision fails closed. The service locks metric version,
scope and competing active attempt in deterministic order, captures a consistent
PostgreSQL source snapshot/cutoff, then writes result and source manifest
atomically. Concurrent attempts for the same identity cannot publish two current
results. Failed attempts never replace a last successful result.

### 6.3 Dashboard and saved view

A personal view is `active -> archived` and may be replaced by a new revision.
A shared view is `draft -> published -> superseded | withdrawn`; its published
configuration is immutable. Sharing requires separate permission and cannot
expand recipients' metric or source access. A dashboard has no business lifecycle:
it renders permitted current results and their freshness/coverage labels.

### 6.4 On-demand report/export

`requested -> generating -> completed | failed | cancelled -> expired`

The first slice permits only bounded synchronous generation. Same actor, request
fingerprint and retry key returns the same manifest while valid; changed payload
fails closed. Completed manifest metadata is immutable. Correction creates a new
linked export. Expiry revokes delivery, not retained DMS history. Durable evidence
is stored only as a DMS `DocumentVersion`; otherwise bytes are response-only,
private/non-cacheable and not persisted by Reporting. Scheduled states, provider
delivery and background retries are absent.

## 7. Required permission catalogue and SoD

All new permissions are active-membership, Tenant and applicable object-scope
checked. **Recommended default-role grant posture: no automatic grants for any new
P10 permission.** Grants must be explicit in the accepted permission catalogue;
role names, positions and Platform status do not imply them.

| Permission code | Consequential action / scope | SoD and additional rule |
| --- | --- | --- |
| `reporting.metric_catalog.view` | View published definitions and non-sensitive metadata | Does not grant metric results or sources. |
| `reporting.metric_definition.prepare` | Create/revise/withdraw draft definition | Author cannot publish own candidate. |
| `reporting.metric_definition.review` | Review/request correction | Cannot substitute for source-domain owner acceptance. |
| `reporting.metric_definition.publish` | Publish/supersede/retire definition | Publisher must differ from author; source owner review must be recorded. |
| `reporting.metric_result.view` | View authorized non-sensitive results within object scope | Does not grant portfolio scope or source drill-through. |
| `reporting.metric_result.view_sensitive` | View specifically classified sensitive aggregate/result | Separate, default-denied; excluded from first metric set. |
| `reporting.portfolio.view` | Aggregate permitted projects into portfolio result | Intersection of project scopes only; never broadens source access. |
| `reporting.metric_refresh.run` | Run/rebuild a published metric | Cannot change definition/source facts; explicit user action only. |
| `reporting.metric_refresh.review` | Review completeness/tie-out and mark an accepted current result | Reviewer differs from runner for material financial metrics. |
| `reporting.source_drillthrough.view` | Request source links/manifests | Also requires each source domain's ordinary view permission and object scope; denied details are masked. |
| `reporting.saved_view.manage_own` | Create/archive own saved views | Sharing unavailable. |
| `reporting.saved_view.manage_shared` | Publish/supersede/withdraw shared views | Publisher cannot grant access; recipients are re-authorized at read time. |
| `reporting.export.create` | Create a bounded on-demand export | POST/CSRF, reason and audit required; no scheduler/provider. |
| `reporting.export.download` | Download own/permitted completed non-sensitive export | Recheck membership, Tenant, object and metric access on every download. |
| `reporting.export.sensitive` | Include/download explicitly sensitive fields/results | Separate default-denied permission; not used in first metric set. |
| `reporting.audit.view` | View minimized P10 lifecycle/action evidence | Does not reveal source payloads or sensitive result values. |

No person-level SoD is imposed on ordinary read, personal saved-view or
non-sensitive drill-through. Narrow person-level separation applies only to:

- definition author versus publisher;
- material financial refresh runner versus acceptance reviewer; and
- shared-view author versus publisher when the view exposes a new audience.

Self-approval remains prohibited for Platform Protected Operations. Platform
staff need an ordinary, independently approved, purpose/time/scope-bound Tenant
access grant before any Tenant result or source is visible.

## 8. Cross-domain interaction classification

| Interaction | Classification in S01–S06 | Boundary |
| --- | --- | --- |
| Read source facts/status/version from P2–P8 | Read/reference | Registered adapter, exact Tenant/object scope, consistent cutoff; no source write. |
| Publish metric definition/result | Authoritative mutation explicitly owned by P10 | Only P10 governance/evidence changes; no source-domain mutation. |
| Source drill-through | Read/reference | Re-authorize against the source domain; no permission laundering. |
| Flag missing/stale/unreconciled input | Proposal/handoff | Informational evidence only; it creates no P10.2 exception, assignment or correction. |
| Ask a source owner to correct data | Proposal/handoff | Source owner uses its ordinary lifecycle; P10 later refreshes. |
| Journal, payment, cost, stock, payroll, contract, claim or workflow change | Separately gated downstream action | Prohibited in this tranche. |
| Report export retained as formal evidence | P10 manifest plus DMS read/reference | DMS owns bytes/version/hash; P10 pins it. |
| Notification or scheduled delivery | Separately gated downstream action | No provider, queue or scheduler. |

## 9. Evidence, privacy and response controls

- Store only identifiers and values necessary to reproduce or explain the metric.
  Do not copy source descriptions, attachments, personal records or credential-like
  fields into result or Audit metadata.
- The first-release metrics contain no employee/person-level or precise-location
  dimension. Payroll, statutory, partner, support, Field location and sensitive
  HSE/QA data need later explicit metric/sensitivity decisions.
- Unauthorized dimensions are omitted or masked; aggregate visibility never
  implies drill-through. Do not use aggregation to expose a denied project's
  contribution. Small-cell disclosure thresholds are mandatory before any later
  person/sensitive metric.
- Platform catalogue metadata may be global only if it contains no Tenant value,
  source identity or provenance. Tenant definitions/results remain Tenant-local.
- Result, dashboard, drill-through and download responses are private and
  non-cacheable. Any future cache key must include Tenant, membership/effective
  scope, permission/sensitivity, metric version and source watermark.
- Export requires explicit permission, purpose, scope, selected fields, immutable
  manifest, actor/time and download audit. No broad export/offboarding capability
  is introduced.
- DMS evidence pins exact `DocumentVersion` and retained hash. Correction or
  supersession creates a new pin and link; P10 never floats to latest and never
  copies document bytes.

## 10. Migration posture

P10-S01 requires **no migration**. It is documentation and decision preparation
only.

If S02–S06 are later authorized, use expand-only migrations for new P10-owned
tables, constraints, indexes, permission catalogue entries and explicit default
grant rows (empty by the recommended decision). Do not rename/drop legacy
`financials` behavior, rewrite source records, fabricate metric owners or
definitions, backfill results, infer approvals/statuses/evidence, or manufacture
historical freshness. Existing rows remain outside the governed catalogue until
an authorized definition is published and a real refresh is run. Rollback must
remove only the new unconsumed expansion; accepted P0–P9 history is untouched.

## 11. UI contract

The necessary operational UI is limited to:

1. metric catalogue list/detail/version/provenance;
2. project and permitted portfolio dashboards with obvious metric version,
   as-of/cutoff, freshness, coverage, currency/unit and incomplete/stale labels;
3. accessible chart plus equivalent data table and textual summary;
4. normal navigation to saved views, history, source drill-through and on-demand
   export where permitted; and
5. permission-aware buttons and clear denied/unavailable/redacted states.

All labels are Persian-first and RTL; display dates are Jalali with unambiguous
time/timezone where relevant. Keyboard, focus, semantic table, contrast and mobile
requirements apply. No primary workflow may be direct-URL-only. S01–S06 does not
redesign unrelated domain UI or expose Admin as the operating interface.

## 12. Product Owner decision register

Options are realistic alternatives; the recommended selection is not an accepted
decision until explicitly recorded.

| ID | Decision question and options | Recommendation / rationale | Sessions | Postponement consequence |
| --- | --- | --- | --- | --- |
| P10-M01 | Ownership: A Reporting owns definitions/derived results only; B Project Controls owns all metrics; C each domain owns separate dashboards | **A.** One governed semantic layer without taking source authority. | S02–S06 | Entire runtime blocked. |
| P10-M02 | Implementation boundary: A new bounded `reporting` module, freeze legacy `financials`; B expand `financials`; C external BI/warehouse | **A.** Avoids treating the misleading compatibility projection as P10 authority; no new dependency/warehouse. | S02–S06 | Schema/module work blocked. |
| P10-M03 | First metric set: A six metrics in section 5; B all audit-catalogue KPIs; C finance-only | **A.** Useful cross-domain slice with stable or explicitly coverage-labelled sources. | S02–S06 | Definitions and acceptance cases cannot be frozen. |
| P10-M04 | Definition scope: A Platform schema plus Tenant-owned published definitions constrained to registered adapters; B arbitrary Tenant formula/query; C code-only metrics | **A.** Governable and adaptable without arbitrary SQL/executable code. | S02 | Catalogue design blocked. |
| P10-M05 | Required definition fields: A complete contract listed in section 5; B formula/title only; C free text | **A.** Required for reproducibility, currency/time clarity and drill-through. | S02–S06 | Publication must fail closed. |
| P10-M06 | Definition lifecycle: A versioned draft/review/publish/supersede/retire; B editable live definitions; C code deployment only | **A.** Preserves accepted history and controlled correction. | S02 | Publication runtime blocked. |
| P10-M07 | Definition SoD: A author cannot publish; domain-owner review recorded; B same actor allowed; C universal two-person rule | **A.** Narrow justified SoD without burdening reads. | S02 | Publication runtime blocked. |
| P10-M08 | Source contract: A closed registered adapters with exact source/status/version; B unrestricted ORM/SQL; C manually uploaded totals | **A.** Prevents authority collisions and unauditable metrics. | S02–S03 | Refresh implementation blocked. |
| P10-M09 | Read-model storage: A PostgreSQL rebuildable projections/results; B external warehouse; C calculate every page request only | **A.** Matches Roadmap and current stack while retaining deterministic evidence. | S03–S06 | Result schema and performance acceptance blocked. |
| P10-M10 | Refresh execution: A explicit synchronous/on-demand only; B scheduler/queue; C implicit page-load refresh | **A.** Preserves deferred queue/scheduler gate and predictable authorization. | S03–S05 | Background behavior remains prohibited. |
| P10-M11 | Freshness: A source watermark/cutoff plus visible fresh/stale/incomplete state; B timestamp only; C hide stale results | **A.** Explains result currency and preserves history. | S03–S06 | Dashboard cannot claim governed results. |
| P10-M12 | Late corrections: A new refresh/result linked as replacement; B mutate prior result; C ignore source correction | **A.** Preserves immutable lineage. | S03–S06 | Correction acceptance blocked. |
| P10-M13 | Missing inputs: A unknown/incomplete with coverage; B treat as zero; C suppress whole dashboard | **A.** Non-fabricating and operationally useful. | S03–S06 | Metrics with any gap must remain unpublished. |
| P10-M14 | Drill-through: A result -> manifest -> source, with source permission recheck; B metric permission reveals source; C no drill-through | **A.** Meets Roadmap without laundering access. | S04–S06 | Dashboard cannot meet P10.1 acceptance. |
| P10-M15 | Portfolio scope: A intersection of actor's effective project scopes; B Tenant-wide when portfolio permission exists; C no portfolio | **A.** Preserves object scope and avoids aggregate leakage. | S04–S06 | Portfolio view stays excluded. |
| P10-M16 | Saved views: A personal active/archive plus separately published shared versions; B mutable shared filters; C none | **A.** Provides utility with immutable shared audience configuration. | S04–S06 | Shared views remain excluded. |
| P10-M17 | Default grants: A no automatic grants for new codes; B grants by existing role names; C reuse `financials.view` | **A.** Clean default-deny and prevents compatibility permission expansion. | S02–S06 | Permission migration cannot be finalized. |
| P10-M18 | Sensitive metrics: A exclude person/sensitive metrics from first set and reserve separate permission; B include masked payroll; C normal result permission | **A.** Minimum necessary and avoids premature small-cell policy. | S02–S06 | Sensitive metrics remain prohibited. |
| P10-M19 | Export: A synchronous on-demand scoped export only; B scheduled/email delivery; C no export | **A.** Delivers bounded Roadmap value without opening providers/schedulers. | S05–S06 | If postponed, S05 omits export and narrows acceptance. |
| P10-M20 | Export evidence: A private response unless explicitly retained in DMS with exact version/hash; B store bytes in Reporting; C public link | **A.** Preserves DMS authority and privacy. | S05–S06 | Retained export evidence blocked. |
| P10-M21 | Result acceptance SoD: A independent review only for material financial results; B always same runner/reviewer; C independent reviewer for every metric | **A.** Risk-proportionate separation. | S03–S06 | Material finance result cannot be accepted current. |
| P10-M22 | Legacy `financials`: A preserve/label compatibility, no backfill or authority promotion; B rewrite in place; C delete | **A.** Expand-first and protects existing behavior/history. | S02–S06 | Collision remains unresolved; runtime blocked. |
| P10-M23 | P10-S06 acceptance owner and tolerated risk: A Product Owner accepts after domain owners sign source semantics and no Critical/High open first-slice defect; B engineering self-accepts; C accept with unspecified risks | **A.** Explicit ownership and bounded risk. | S06 | Product Owner acceptance cannot occur. |
| P10-M24 | Release/rollback ownership for this non-production tranche: A named technical release executor plus Product Owner go/no-go; rollback on invariant/security/lineage failure; B implementer alone; C defer ownership | **A.** Separates execution from product decision and preserves production gate. | S02–S06 | Runtime authorization must remain withheld. |

All recommended choices are Option A because the alternatives materially weaken
authority, auditability, privacy or the inherited no-background/no-production
boundary; the consistency is substantive, not cosmetic.

Before runtime authorization, the Product Owner must also name the accountable
metric owner/source-domain reviewer for each of the six metrics, the P10-S06
acceptance owner, the technical release/rollback executor, and any specifically
tolerated Medium/Low open risk. Names and tolerated risks are not inferred here.

## 13. Focused PostgreSQL acceptance strategy

Use one uniquely named disposable PostgreSQL database and one runner. Preserve and
do not inspect, migrate, reset or drop `test_construction_erp`. Start with focused
P10 tests; no broad suite is required unless a focused failure or shared-boundary
change supplies a recorded expansion trigger.

Minimum acceptance cases:

1. cross-Tenant definition/result/saved-view/export reads and writes fail;
2. inactive membership/Tenant and missing permission fail at service and view;
3. project/portfolio scope intersection prevents aggregate leakage;
4. author cannot publish own definition; stale review and concurrent publication
   produce one version;
5. material refresh runner cannot accept own result; ordinary reads require no
   unnecessary person-level separation;
6. same idempotency key/same fingerprint returns the original definition,
   refresh or export outcome; changed fingerprint fails;
7. concurrent identical refreshes publish one current immutable result;
8. late source correction marks old result stale and creates a linked replacement
   without rewriting it;
9. missing sources are incomplete/unknown, never zero; proposal-only status never
   becomes recognized cost/cash/journal;
10. deterministic rebuild from the same metric/source versions and cutoff ties to
    the same value, manifest and dimensions;
11. drill-through rechecks source permission and masks denied source detail;
12. sensitive-result/export permissions remain independent and first-slice
    person/sensitive dimensions are absent;
13. retained export pins exact DMS `DocumentVersion`/hash, while response-only
    export stores no duplicate bytes;
14. dashboard/export has no operational or financial downstream mutation;
15. Persian RTL/Jalali, currency/unit/period/freshness/coverage labels, chart/table
    equivalence, normal navigation, keyboard focus and private/non-cacheable
    responses pass focused UI checks; and
16. clean-schema migration plus dependency-safe rollback/reapply returns to the
    exact pre-P10 schema without changing P0–P9 records, followed by migration
    drift and Django checks.

Targeted Ruff/format, template compilation, URL resolution, permission-catalogue
consistency, local links and diff hygiene complete the tranche. Broaden only if
shared authorization, Organizations, Projects, DMS or source-domain behavior is
actually changed.

## 14. Preserved deferred gates

The following remain unauthorized and outside P10-S01–S06 unless a later explicit
Product Owner decision opens a separately bounded package:

- `S25-G10` changes;
- AI-generated Knowledge, AI assistants, RAG, embeddings, vector databases,
  semantic/AI search or inference;
- external publication or search;
- email, SMS or push providers;
- queues, schedulers, background delivery or automated retry;
- external integrations or a separate warehouse;
- automatic operational effects or automatic financial effects;
- P10-S07–S24, including reconciliation/close, project closeout and production
  certification;
- production cutover and production activation.

“Semantic metric catalogue” means governed business definitions. It is not
semantic/AI search, embeddings, unrestricted natural-language queries or an
authorization-safe API for the future ERP Assistant.

## 15. Planning validation and documentation closeout

This S01 pass changes documentation only. Appropriate validation is local-link and
anchor checking, exact session/status/deferred-gate searches, Markdown whitespace
review and scoped diff review. Application tests, Django checks and migration
commands are not justified because no executable/configuration file changes.

`ROADMAP.md` and `docs/ROADMAP_EXECUTION_PLAYBOOK.md` must record S01 planning as
complete while leaving P10.1 `PLANNED`, all decisions pending, P10 runtime
unauthorized and P10-S07+ prohibited. No other architecture status changes merely
because this proposal exists.

## 16. Exact bounded runtime-authorization wording

The Product Owner may use the following wording only after replacing every bracket
with explicit facts and recording decisions in this packet:

> I accept `P10-M01`–`P10-M24` as recorded in
> `docs/architecture/P10_S01_S06_GOVERNED_METRICS_AND_REPORTING_DECISION_PACKET.md`,
> including the named metric/source owners, P10-S06 acceptance owner, technical
> release/rollback executor and tolerated-risk register dated `[DATE]`. P10-S01
> planning is complete. I authorize implementation of **P10-S02–S06 only** for
> the six first-release metrics, versioned metric catalogue, PostgreSQL governed
> read models, explicit synchronous refresh, Persian RTL/Jalali dashboards,
> permission-preserving source drill-through, saved views, bounded on-demand
> export, and the focused acceptance/closeout defined by that packet. This
> authorization preserves Tenant isolation; active-membership and object scope;
> Platform/Tenant separation; source-domain authority; DMS-only byte/version
> custody; exact version/hash/source lineage; immutable finalized history;
> explicit correction/replacement/supersession; default-deny permissions;
> accepted SoD; sensitive-data controls; expand-only/non-fabricating migration;
> proposal/no-effect behavior; and all accepted P9 boundaries. It excludes
> changes to `S25-G10`, P10-S07–S24, reconciliation/close, project closeout,
> production certification, AI/RAG/embeddings/vector/semantic search, external
> publication/search, email/SMS/push providers, queues/schedulers, external
> integrations, a warehouse, automatic operational or financial effects,
> production cutover and production activation. Completion must be reported as
> **`implementation complete / Product Owner acceptance pending`**. This wording
> grants no later-session or production authority.

Without that explicit decision record and authorization, the correct status is:
**P10-S01 planning complete; Product Owner decisions required; no P10 runtime
authorized.**
