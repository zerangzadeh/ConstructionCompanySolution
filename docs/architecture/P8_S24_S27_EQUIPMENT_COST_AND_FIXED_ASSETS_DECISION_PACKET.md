# P8-S24–S27 Equipment Cost and Fixed Assets Architecture and Product Owner Decision Packet

**Prepared:** 2026-10-05  
**Prerequisite verified:** `P8-S01–S23 = Product Owner accepted`; `ROADMAP.md` and the accepted P8-S18–S23 packet record that disposition on 2026-10-05.  
**Status:** **P8-S24–S27 = Product Owner accepted**. P8-C01–C38=A and the exact section 14 bounded runtime authorization remain authoritative.  
**Official envelope:** exactly P8-S24–S27, as fixed by section 14 of `docs/ROADMAP_EXECUTION_PLAYBOOK.md`. P8-S28–S30 are not included.  
**Authority boundary:** implementation is limited to the section 14 non-production authorization. It creates Equipment proposal and distinct Fixed Assets evidence models, migrations, permissions, services and Persian-first UI, but no journal, Project Cost actual, payable, cash movement, Inventory mutation/revaluation, P7 Payroll consumption, production cutover or production behavior.

## 1. Bounded purpose and preserved ownership

This tranche may later add two linked but non-collapsed authorities:

1. Equipment-owned, version-pinned operational cost-rate and allocation **proposals** derived from accepted Equipment usage evidence; and
2. a distinct Fixed Assets authority for a source-backed asset register, book-value lifecycle and non-posting depreciation evidence.

Accepted P8 ownership remains unchanged:

| Fact or action | Authority | Preserved boundary |
| --- | --- | --- |
| Equipment identity, deployment, meters, usage, fuel, downtime and maintenance | Equipment | Operational evidence only; it never becomes an asset ledger, journal or Project Cost actual. |
| Material custody and moving-WAC valuation | Inventory | Equipment and Fixed Assets may reference final Inventory evidence but cannot create, edit, reverse or revalue it. |
| Procurement acceptance and supplier commercial evidence | Procurement; AP when recognized | A reference is not a liability, payment or capitalization fact. |
| Employee/time/payroll evidence | Workforce/Time/Payroll | This tranche does not consume P7 Payroll proposals or create labor cost. |
| Equipment rate policy and allocation proposal | Equipment | A management/source proposal only; it is not an actual, journal, invoice, asset cost or posted overhead. |
| Asset identity, capitalization basis, asset book, depreciation, impairment, transfer and disposal history | distinct Fixed Assets authority | The register links to Equipment where useful but never derives financial facts from operational status or descriptive cost. |
| Accounts, periods, journals and posting | Accounting | Fixed Assets may later offer an immutable source proposal; only Accounting can create/post a journal under a separate consumer contract. |
| Project cost classification and actual | Project Controls | Equipment/Fixed Assets may later offer immutable source proposals; only Project Controls can recognize an actual under a separate contract. |
| Payment, receipt and cash movement | Treasury | Disposal proceeds, purchase references and asset status never create cash facts. |

No cross-domain consumer may treat a proposal, link, descriptive amount or Fixed Assets subledger event as its own authoritative fact.

## 2. Exact session-by-session decomposition

| Session | Bounded result if separately authorized | Explicit exclusions |
| --- | --- | --- |
| **P8-S24** | Equipment cost architecture: versioned rate policies/components; eligible finalized usage basis; conserved project/site/WBS/activity/cost-center allocation; immutable proposal envelope/lines; reversal/replacement and reconciliation evidence | Project Cost actual, Accounting journal, Payroll consumption, AP/Inventory mutation, automatic maintenance/fuel/spare cost roll-up |
| **P8-S25** | Fixed Assets foundation: asset class and book-policy versions, independent `FixedAsset` identity, optional effective Equipment link, source-backed candidate/review/capitalization lifecycle and immutable opening/capitalization transaction evidence | Treating every owned Equipment as an asset, inferred legacy value, journal posting, payment, tax book, revaluation |
| **P8-S26** | Monthly straight-line book-depreciation architecture: useful-life/residual/source pins, bounded convention policy, deterministic preview/review/finalize run and lines, period locking, reversal/replacement and no-effect handoff proposals | Tax depreciation, multiple methods/books, automated GL posting, Project Cost actual, retroactive silent recomputation |
| **P8-S27** | Fixed-asset impairment, operational/financial transfer separation and disposal/retirement evidence; Persian-first RTL workbench; permissions/SoD, audit, historical migration exceptions, concurrency/idempotency, source/handoff reconciliation and acceptance evidence | Cash/proceeds recognition, automatic gain/loss, journal or actual creation, production activation, P8-S28–S30 conservation/closeout work |

Each session is independently gated. S25 depends on the accepted ownership contract, S26 on an accepted S25 asset/book contract, and S27 on accepted S25–S26 lifecycle/history contracts. A later session cannot broaden an earlier session by inference.

## 3. Conceptual model and relationships

The following are design concepts, not current schema commitments:

| Concept | Relationships and invariant |
| --- | --- |
| `EquipmentCostPolicyVersion` | Tenant-scoped reviewed/published immutable version with currency/precision policy, effective range, eligible usage measure, bounded component definitions and allocation rules. Publication supersedes rather than edits prior versions. |
| `EquipmentCostRate` | Belongs to a policy version and Equipment or governed equipment class; has effective dates, rate unit and explicit components. It is an internal proposal rate, not a supplier price, Inventory value, asset carrying amount or posted actual. |
| `EquipmentCostAllocation` / line | Pins one finalized Equipment usage source/version, deployment/project/site context, rate/policy version, measure, calculated amount and conserved coded distribution. Finalized allocations are immutable and corrected by linked reversal/replacement. |
| `EquipmentCostSourceEnvelope` | Immutable reviewed proposal exposing finalized allocation lines to a named future consumer. Consumer acknowledgment/reconciliation is evidence only and creates no consumer fact. |
| `FixedAssetClassVersion` | Tenant-scoped reviewed/published classification with book-policy and required-account-mapping references; changes are prospective and versioned. No account mapping authorizes posting. |
| `AssetBookPolicyVersion` | One initial book, IRR monetary-policy pin, monthly straight-line method, bounded commencement convention, precision/residual rules and effective dates. Exact configured values must exist before calculation. |
| `FixedAsset` | Independent Tenant asset identity, class/version, description, ownership/control evidence, ready-for-use date, status and optional component/parent relationship. It may have effective links to operational Equipment but is never the same aggregate. |
| `FixedAssetEquipmentLink` | Effective-dated link with reason and actor evidence. One asset component has at most one active primary Equipment link; one Equipment may link to a parent asset and material component assets where explicitly reviewed. Link changes do not alter historical transactions. |
| `AssetSourceReference` | Immutable typed reference to the source owner, public ID/version/line, amount/currency/date, evidence hash/reference and review state. It does not copy or mutate the source lifecycle. |
| `AssetTransaction` | Append-only Fixed Assets subledger event such as opening, capitalization, addition, impairment, impairment reversal where policy permits, transfer, disposal/retirement, correction reversal and replacement. Each event pins book/policy/source/correlation/idempotency evidence. |
| `DepreciationRun` / `DepreciationLine` | One Tenant, book and period scope. A finalized line pins asset/component, depreciable basis, useful life, residual value, convention, elapsed/remaining life, precision, calculated amount and prior carrying-value watermark. |
| `FixedAssetSourceEnvelope` | Immutable proposal for a named Accounting or Project Controls consumer with source event/line and policy/version pins. It is not a journal, actual, liability, payment or posting instruction. |
| `AssetReconciliationEvidence` | Read-only comparison of source references, asset transactions, depreciation, proposal acknowledgments and consumer facts if separately available. A difference remains visible; it is never force-balanced by writing another domain. |

Every record is explicitly organization-scoped, uses UUID public identifiers, validates same-Tenant and project/site relationships, and records actor/time. Monetary values use `Decimal`, IRR plus the effective monetary-policy version, never `float`. Asset components conserve parent acquisition basis without duplicating it. Finalized carrying value is derived only from the asset transaction/depreciation ledger, never stored as an editable Equipment field.

## 4. Lifecycle and workflow contract

| Aggregate | Lifecycle | Correction/reversal rule |
| --- | --- | --- |
| Cost policy/rate | draft -> reviewed -> published -> superseded/retired | Published versions are immutable; successor versions are prospective unless an explicit correction policy authorizes a bounded replacement. |
| Equipment cost allocation | draft/preview -> reviewed -> finalized -> reversed/replaced | A finalized allocation cannot be edited or deleted. Reversal is equal-and-opposite against the exact original source/policy, then an optional replacement. |
| Asset candidate | captured -> source-validated -> reviewed -> accepted/rejected | Rejection preserves evidence. Acceptance creates or links the asset draft but does not create a journal or payment. |
| Fixed asset | draft -> ready-for-review -> capitalized/active -> suspended/held-for-disposal -> disposed/retired | Capitalization requires complete source and policy facts. Final history changes only through linked transactions. Status rewind is prohibited. |
| Asset class/book policy | draft -> reviewed -> published -> superseded/retired | Published versions are immutable and remain pinned to historical assets/runs. |
| Depreciation run | draft/preview -> reviewed -> finalized -> reversed -> replaced | Finalization locks scope/watermark. Correction reverses the affected run/lines and creates a replacement; no silent recalculation. |
| Impairment | proposed -> evidenced -> independently reviewed -> finalized -> reversed/replaced where policy permits | No automatically inferred impairment. Amount/date/reason/source and approval are immutable. |
| Transfer | proposed -> reviewed -> effective/cancelled | Operational deployment and financial dimension/custodian changes remain separate events; neither silently changes the other. |
| Disposal/retirement | proposed -> evidence-complete -> reviewed -> finalized -> corrected by reversal/replacement | Disposal does not recognize proceeds, cash or gain/loss. Source references and any future proposals stay explicit. |
| Handoff proposal | prepared -> reviewed -> available -> acknowledged/rejected -> reconciled | Consumer state is evidence only. Replacement retains predecessor/supersession lineage and stable occurrence identity. |

Workflow coordination is optional and may call only registered Equipment or Fixed Assets commands. Domain services remain authoritative and re-check permission, Tenant state, source state and SoD inside the transaction. Workflow, position, candidacy or approval-route assignment never grants a business permission.

## 5. Source, calculation and cross-domain handoff boundaries

### 5.1 Equipment allocation calculation

An allocation may use only a finalized, non-superseded `EquipmentUsageLog` or reviewed meter-derived usage basis that pins deployment and coding. The effective published rate/policy is resolved at the usage occurrence date. The calculation records measure × component rate, monetary precision/residual treatment and a conserved distribution whose line measures and amounts equal the parent after explicit residual assignment.

Downtime, idle time and unassigned operation follow an explicit published policy; they are never silently spread. Fuel, spare, external service, Payroll and depreciation amounts are excluded from the initial rate unless a later authorized source contract makes each component independently traceable and prevents duplication. S24 does not consume those sources.

### 5.2 Fixed Asset source acceptance

Capitalization requires reviewed ownership/control evidence, an accepted typed source reference, acquisition or construction amount, IRR/monetary-policy version, ready-for-use date, asset class/book policy, useful life, residual value, component allocation where material, project/site/cost-center dimensions where applicable, and preparer/reviewer evidence. Missing or conflicting facts fail closed.

Permitted initial source families are explicit reviewed acquisition/construction source envelopes and controlled legacy opening evidence. Equipment `acquired_on`, `ownership_type`, maintenance cost, fuel, usage, free text, Inventory balance/value, approved budget, purchase order, receipt alone, invoice alone or payment alone is insufficient. The source owner retains its lifecycle; Fixed Assets records a pinned reference and its own reviewed transaction.

### 5.3 Handoff boundary

| Producer -> consumer | Permitted packet output | Consumer-only action | Failure behavior |
| --- | --- | --- | --- |
| Equipment -> Project Controls | Reviewed immutable cost-allocation proposal with source usage/rate/coding/version/reversal lineage | Recognize/classify a Project Cost fact under a separately accepted source contract | Missing mapping, duplicate occurrence, closed scope or unauthorized contract creates no actual. |
| Fixed Assets -> Accounting | Reviewed immutable capitalization/depreciation/impairment/disposal proposal with book/event/line/policy/account mapping references | Create, approve and post a journal in Accounting | Missing/closed period, mapping or authorization creates no journal and does not roll back the asset event. |
| Fixed Assets -> Project Controls | Reviewed immutable depreciation or asset-cost proposal with explicit project/WBS/activity/cost-center distribution | Recognize a Project Cost fact | No accepted source contract means no actual. |
| Accounting/Project Controls -> Fixed Assets | Read-only acknowledgment/rejection and consumer fact reference | Own correction/reversal in the consumer domain | A mismatch opens reconciliation evidence; Fixed Assets never edits the consumer fact. |
| Procurement/AP/Inventory -> Fixed Assets | Reviewed immutable source reference/envelope | Own order/receipt/liability/valuation lifecycle | Missing final source evidence fails capitalization; Fixed Assets never finalizes another domain. |

No handoff in S24–S27 activates a consumer. Proposal preparation and acknowledgment are separately permissioned, idempotent and auditable.

## 6. Authorization and separation of duties

A later runtime must add dedicated default-deny `BusinessPermissionCode` entries, registry metadata, explicit default-role grants and a data migration. Proposed capabilities are:

- Equipment: `equipment.cost_policy.view`, `.manage`, `.publish`; `equipment.cost_allocation.view`, `.prepare`, `.review`, `.reverse`; `equipment.cost_handoff.prepare`, `.review`, `.reconcile`.
- Fixed Assets: `fixed_assets.view`, `.candidate.prepare`, `.candidate.review`, `.manage`; `fixed_assets.class_policy.manage`, `.class_policy.publish`; `fixed_assets.capitalize`, `.transaction.prepare`, `.transaction.review`, `.transaction.reverse`; `fixed_assets.depreciation.preview`, `.finalize`, `.reverse`; `fixed_assets.transfer`, `.impair`, `.dispose`; `fixed_assets.handoff.prepare`, `.handoff.review`, `.reconcile`; `fixed_assets.audit.view`.

Final names belong to an authorized implementation, but the separations do not. At minimum:

- policy/rate preparation is separated from publication;
- usage capture is separated from allocation review where configured;
- asset candidate preparation is separated from capitalization;
- asset/source preparation is separated from capitalization review;
- depreciation preview/preparation is separated from finalization;
- the actor finalizing a depreciation run cannot approve its reversal/replacement;
- impairment and disposal preparation are separated from finalization;
- proposal preparation is separated from review/release;
- Accounting journal posting and Project Cost recognition permissions are never granted by a P8 role or action.

Small-Tenant self-approval is allowed only through an explicit protected-operation policy that identifies capability, risk, reason, actor and audit evidence. It is never inferred from Owner/Admin role. Every read and mutation checks active membership, Tenant state, permission and applicable project/site/object scope at view and service boundaries; supplied organization IDs, UI visibility, position, Equipment assignment and asset custody grant nothing.

## 7. Audit, idempotency and concurrency

Audit is append-only at the application layer and records organization, public IDs, actor, time, action, previous/new lifecycle state, reason, source type/id/version/line, Equipment/asset/component, project/site/WBS/activity/cost center, book/policy/rate version, currency/precision, amounts/measures, correlation ID, idempotency key, reversal/replacement link, handoff identity and acknowledgment/reconciliation result. Sensitive commercial, employee and document data is minimized and access-controlled.

Commands use a stable organization + aggregate/action + source occurrence idempotency identity. Same key and semantically identical payload returns the original result; same key with different payload fails closed and is audited. Finalization locks rows in deterministic order: Tenant policy/book/period, source aggregate, Equipment/asset/component, allocation or run, lines, proposal envelope. State and authorization are re-read inside `transaction.atomic()`.

Database constraints must cover organization-scoped identifiers, one active published policy per governed effective interval where applicable, non-overlapping effective rates/links, unique source occurrence, one finalized calculation for an unreversed source/version/policy, unique run book/period/occurrence and reversal/replacement lineage. Service checks cover cross-domain source state, period/policy effective dates, component conservation and SoD. Concurrent retries must leave one authoritative result and no downstream consumer fact.

## 8. Depreciation and carrying-value rules

The first release is one book and monthly straight-line depreciation only. Each asset/component pins capitalization basis, ready-for-use date, useful life, residual value, commencement convention, book/policy version and precision. Depreciable basis is capitalization basis plus eligible finalized additions less residual value and finalized impairments/other policy-permitted adjustments. It cannot be negative, residual value cannot exceed the applicable basis, and accumulated depreciation cannot reduce carrying value below residual value unless a separately governed impairment rule permits it.

Exact useful life, residual, commencement convention, precision, residual assignment and fiscal period must be configured/reviewed; the system must not invent them. Draft preview is reproducible and clearly non-authoritative. Finalization pins its source watermark. Later source corrections never silently rewrite prior periods; they require an explicit prospective adjustment or reversal/replacement policy and open-period evidence. Closed Accounting periods are read as a gate signal only; Fixed Assets cannot reopen them.

Impairment is reviewed evidence, not a usage/maintenance-status formula. Transfer changes explicit financial dimensions/custodian/location prospectively and does not rewrite historical deployment or depreciation. Disposal stops future depreciation as defined by the accepted convention, retains all history and produces proposal evidence only; it does not calculate or recognize cash, tax, journal gain/loss or Project Cost effect.

## 9. Migration and historical-data approach

Use expand -> map/backfill -> validate -> switch, with rollback/recovery evidence, only after runtime authorization. Do not remove or repurpose accepted Equipment/Inventory fields or P8-S18–S23 records. A new Fixed Assets app/domain requires approved app ownership before schema work; it must not be embedded in Equipment or Accounting.

Historical migration is non-fabricating:

- retain `Equipment`, `EquipmentAssignment`, `MaintenanceRecord` and all P8 operational history unchanged;
- do not infer asset existence, ownership, capitalization, book value, useful life, residual, in-service date, accumulated depreciation, impairment, disposal, rate or allocation from Equipment fields, maintenance cost/notes, Inventory, budgets or journals;
- accept an opening asset/balance only with reviewed source evidence, as-of date, book/policy, currency/precision, gross basis, accumulated depreciation/impairment, remaining life, residual, dimensions and preparer/reviewer;
- keep incomplete candidates or legacy references read-only with explicit exception reason; they are excluded from final depreciation and handoffs;
- preserve source IDs and opening reconciliation totals by Tenant/book/class without force-balancing;
- rehearse on isolated non-production PostgreSQL data, validate clean-schema and forward/rollback paths, and retain an exception/export manifest.

No migration writes Accounting journals, Project Cost facts, AP liabilities, Treasury transactions, Inventory valuation or P7 records.

## 10. Persian-first RTL UI and evidence requirements

The later UI provides separate workbenches for Equipment cost proposals and Fixed Assets. It is responsive/mobile-aware, RTL and Persian-first, with localized Jalali display while storing ISO/timezone-aware dates. It must visibly distinguish draft/preview, reviewed/finalized, reversed/replaced and proposal/acknowledgment states.

Required drill-through includes usage -> rate/policy -> allocation -> proposal; asset -> source/version -> capitalization/addition -> depreciation run/line -> correction; and proposal -> named consumer acknowledgment/reconciliation. Users see source availability, policy/version, book/period, amount/measure conservation, SoD blocker, missing evidence, migration exception and correction lineage. Restricted source details remain redacted unless separately authorized.

Labels must state that Equipment allocations and Fixed Asset handoffs are proposals and that Fixed Assets subledger evidence is not an Accounting journal, Project Cost actual, supplier liability, payment or tax return. UI actions are POST/CSRF-protected, permission/object-scoped, duplicate-safe and auditable. No export is included unless separately approved with dedicated permission, minimization and audit.

## 11. Validation and acceptance criteria for later runtime

A later implementation is acceptable only when focused tests and evidence prove:

1. active-Tenant resolution, permission and project/site/object scope on every read/mutation, including cross-Tenant FK/form/service and guessed-ID denial;
2. all decision-selected lifecycles, immutable final history, reversal/replacement and no-delete rules;
3. effective policy/rate/book resolution, Decimal precision and conserved measure/amount/component allocations;
4. deterministic straight-line golden cases for commencement, residual, component, partial/final period, impairment, transfer, disposal, reversal and replacement choices;
5. stable same-payload retries, conflicting-payload rejection, deterministic row locking and race coverage for publication, capitalization, allocation, run finalization, reversal and disposal;
6. source state/version pins and failure when source, currency, mapping, period, evidence or policy is absent/stale;
7. maker-checker/SoD and protected self-approval exception behavior;
8. non-fabricating legacy migration, exception manifest, clean-schema migration and safe rollback/reapply rehearsal;
9. Persian-first RTL accessibility, responsive behavior, clear non-financial/proposal labels and end-to-end drill-through;
10. append-only audit completeness, sensitive-data minimization and separately permissioned audit/reconciliation access;
11. explicit no-effect assertions: zero Accounting journal/posting, Project Cost actual, AP liability, Treasury movement, Inventory mutation/revaluation, Payroll consumption or production activation;
12. targeted Django checks/tests, migration-drift check, Ruff/format and documentation/reference consistency, expanding only for affected-boundary failures.

P8-S28–S29 remain the official later quantity/value/depreciation reconciliation review and P8-S30 remains the closeout/P9 handoff. S24–S27 acceptance cannot mark them complete.

## 12. Complete Product Owner decision register

All decisions below are accepted as Option A. Runtime authority remains exactly bounded by section 14.

| ID | Decision and options | Recommended disposition | Consequence |
| --- | --- | --- | --- |
| P8-C01 | Equipment cost meaning — A: immutable management/source proposal; B: Project Cost actual; C: Accounting expense | **A** | Preserves consumer ownership and permits later controlled handoff. |
| P8-C02 | Initial rate model — A: versioned component rate per Equipment/class and measure; B: free-form total; C: infer actual cost | **A** | Reproducible, governed calculation without false actuals. |
| P8-C03 | Eligible usage basis — A: finalized usage/meter evidence with reviewed exception; B: any log; C: manual quantity only | **A** | Pins allocation to accepted operational evidence. |
| P8-C04 | Rate effective dating — A: published version effective at usage occurrence; B: current rate at calculation; C: editable rate | **A** | Historical repeatability and correction safety. |
| P8-C05 | Downtime/idle/unassigned use — A: explicit versioned policy and exception coding; B: silently spread; C: always omit without evidence | **A** | Avoids hidden allocation and preserves operational context. |
| P8-C06 | Allocation dimensions — A: conserved project/site/WBS/activity/cost-center lines; B: project total only; C: free text | **A** | Supports later source-contract validation and drill-through. |
| P8-C07 | Initial cost components — A: governed internal rate components only; external/fuel/spare/payroll/depreciation excluded until separate source contracts; B: auto-roll up all; C: one opaque rate | **A** | Prevents duplication and premature P7/AP/Inventory/asset consumption. |
| P8-C08 | Allocation correction — A: linked equal-and-opposite reversal plus replacement; B: edit; C: delete/recalculate | **A** | Preserves finalized evidence. |
| P8-C09 | Equipment downstream behavior — A: separately reviewed immutable proposal only; B: automatic actual; C: automatic journal | **A** | No financial/GL or Project Cost activation. |
| P8-C10 | Asset authority — A: distinct Fixed Assets domain/app; B: fields on Equipment; C: Accounting-only row | **A** | Keeps operational, subledger and GL responsibilities separate. |
| P8-C11 | Equipment/asset relationship — A: optional effective-dated link supporting reviewed components; B: one mandatory 1:1 link; C: no link | **A** | Supports leased/expensed/grouped/component cases without identity collapse. |
| P8-C12 | Capitalization eligibility — A: reviewed source-backed candidate with complete ready-for-use/book facts; B: every owned Equipment; C: acquisition date alone | **A** | Implements accepted D04 without invented financial history. |
| P8-C13 | Initial capitalization sources — A: typed reviewed acquisition/construction envelopes plus controlled legacy opening; B: PO/receipt/invoice/payment alone; C: manual total | **A** | Preserves source ownership and auditability. |
| P8-C14 | Capitalization lifecycle — A: candidate -> validate -> review -> capitalized transaction; B: create active immediately; C: Accounting journal creates asset | **A** | Enables SoD and Fixed Assets-owned evidence without posting. |
| P8-C15 | Initial books/methods — A: one book, monthly straight-line only; B: multiple books/methods; C: tax book first | **A** | Matches accepted D04 and bounds legal/operational risk. |
| P8-C16 | Commencement convention — A: bounded Tenant-selected versioned convention with no implicit default; B: hardcode next month; C: hardcode daily prorata | **A** | Avoids inventing jurisdiction/accounting policy while remaining deterministic. |
| P8-C17 | Useful life/residual — A: explicit reviewed asset/component values or approved class version; B: infer from age; C: global default | **A** | Missing policy fails closed and history remains explainable. |
| P8-C18 | Precision/residual assignment — A: effective monetary-policy version plus deterministic final-line residual; B: binary float; C: ad hoc rounding | **A** | Conserves basis and prevents drift. |
| P8-C19 | Componentization — A: explicit material components conserving parent basis; B: prohibit; C: silently split by Equipment parts | **A** | Supports material components without duplicate cost. |
| P8-C20 | Depreciation run scope — A: Tenant/book/period run with locked source watermark; B: per-view live calculation; C: annual bulk overwrite | **A** | Reproducible concurrency-safe period evidence. |
| P8-C21 | Depreciation correction — A: reverse affected finalized run/lines and replace under open-policy evidence; B: edit accumulated amount; C: delete rerun | **A** | Preserves close and audit history. |
| P8-C22 | Late source change — A: explicit prospective adjustment or approved reversal/replacement; B: silent retroactive recompute; C: ignore always | **A** | Prevents historical mutation while allowing controlled correction. |
| P8-C23 | Impairment — A: separately evidenced/reviewed asset transaction, no automatic formula; B: infer from downtime/maintenance; C: omit lifecycle | **A** | Keeps operational condition from becoming an unauthorized financial fact. |
| P8-C24 | Transfer — A: separate operational deployment and financial dimension/custodian events; B: synchronize automatically; C: rewrite history | **A** | Maintains domain boundaries and prospective history. |
| P8-C25 | Disposal/retirement — A: reviewed evidence stops future depreciation and emits proposal only; B: auto cash/gain-loss/journal; C: delete asset | **A** | Retains asset history without consumer effects. |
| P8-C26 | Accounting handoff — A: immutable reviewed proposal/acknowledgment only; B: direct journal creation/posting; C: shared table | **A** | Accounting remains sole journal authority. |
| P8-C27 | Project Cost handoff — A: immutable reviewed proposal/acknowledgment only; B: direct actual creation; C: Equipment summary field | **A** | Project Controls remains sole actual authority. |
| P8-C28 | Period interaction — A: read validated book/Accounting-period gate; Fixed Assets cannot reopen; B: ignore close; C: auto reopen | **A** | Fails safely around closed periods. |
| P8-C29 | Historical migration — A: verified openings plus explicit exceptions/read-only legacy; B: infer from Equipment/journals/notes; C: discard | **A** | Non-fabricating migration with reconciliable evidence. |
| P8-C30 | SoD — A: separated prepare/review/finalize/reverse with explicit protected self-approval exception; B: role-only maker approval; C: none | **A** | Supports small and large tenants without implicit bypass. |
| P8-C31 | UI/export — A: RTL evidence workbench; no export until separately approved; B: editable spreadsheet/export by default; C: Admin only | **A** | Clear proposal status, least privilege and auditable drill-through. |
| P8-C32 | Release boundary — A: non-production verified runtime only after exact authorization; separate production decision; B: direct production activation | **A** | Preserves readiness and cutover gates. |
| P8-C33 | Asset numbering — A: immutable Tenant sequence plus UUID public identity; B: Equipment number reused; C: editable free text | **A** | Stable register identity without collapsing Equipment or exposing internal IDs. |
| P8-C34 | Initial ownership scope — A: source-backed owned/controlled assets; lease/right-of-use accounting deferred; B: full lease accounting now; C: every leased Equipment capitalized | **A** | Bounds legal/accounting scope and prevents operational lease status from creating an asset. |
| P8-C35 | Low-value/grouped assets — A: explicit versioned capitalization policy; individual/component record by default and reviewed grouped record only with conserved source/quantity evidence; B: auto expense threshold; C: auto group by class | **A** | Avoids inventing monetary thresholds while supporting controlled grouping. |
| P8-C36 | Valuation model — A: historical-cost book only; no revaluation/fair-value model; B: revaluation; C: market-value overwrite | **A** | Keeps the first book deterministic and source-backed. |
| P8-C37 | Construction in progress — A: accept only a reviewed ready-for-use capitalization source envelope; CIP subledger deferred; B: build CIP ledger in S25; C: infer from project spend | **A** | Avoids duplicating Project Controls/Accounting and fabricated completion. |
| P8-C38 | Tax/statutory depreciation — A: excluded; later separate authority/book/policy; B: reuse book depreciation; C: tax book now | **A** | Prevents book evidence from claiming legal tax treatment. |

**Product Owner disposition (2026-10-05):** `P8-C01–C38=A`, with every definition and consequence accepted as written and no deviation or broadening.

## 13. Production-readiness and later-session gates

Runtime completion would not certify production. Production remains gated by authoritative accounting/legal policy review; Tenant policy values; data-quality/opening reconciliation; performance/concurrency evidence; security/privacy and authorization review; support/recovery/backup restoration; consumer-owner acceptance; migration rehearsal; and a separate Product Owner cutover/activation decision.

At the time of this packet's acceptance, P8-S28–S29 remained unauthorized and
were reserved for independent quantity/value conservation, Equipment allocation,
asset carrying value, depreciation, source/consumer reconciliation and no-effect
review. P8-S30 remained the reserved closeout and P9 handoff. This packet neither
changed their scope nor pre-accepted them; their later execution is recorded in
`P8_FINAL_ASSURANCE_CLOSEOUT_AND_P9_HANDOFF.md`.

## 14. Exact bounded runtime authorization wording

The Product Owner authorized S24–S27 runtime with this exact bounded wording:

> I accept `P8_S24_S27_EQUIPMENT_COST_AND_FIXED_ASSETS_DECISION_PACKET.md` and select P8-C01–C38 as recorded, except for these expressly named deviations: [none or list]. I authorize implementation of **P8-S24–S27 only** within sections 1–11 of that packet: Equipment-owned versioned cost-rate and conserved allocation proposals from finalized usage evidence; a distinct Fixed Assets authority with source-backed register/capitalization evidence, one historical-cost book with monthly straight-line depreciation, controlled impairment/transfer/disposal, immutable reversal/replacement, proposal-only downstream handoffs, non-fabricating migration, Persian-first RTL evidence UI, and the specified Tenant isolation, permissions, SoD, audit, idempotency, concurrency and validation controls. This authorization is non-production and does **not** authorize P8-S28–S30, lease/right-of-use or CIP accounting, revaluation/fair value, tax/statutory depreciation, Accounting/GL journal creation or posting, Project Cost actual creation, AP liability, Treasury/cash movement, Inventory mutation or revaluation, P7 Payroll proposal consumption, automatic financial recognition, production cutover or production activation.

Any deviation, added source/consumer, multiple depreciation book/method, tax behavior, export, external integration or production activity requires a new explicit decision and authorization. Silence does not authorize it.

## 15. Implementation and validation evidence

P8-S24–S27 is implemented as an expand-only, non-production tranche:

- Equipment owns versioned cost policy/rate evidence, conserved allocation proposals, explicit equal-and-opposite reversal and reviewed Project Cost proposal envelopes.
- The distinct `fixed_assets` domain owns class/book policies, source-backed candidates, Equipment links, capitalization, transfer/impairment/disposal transactions, monthly straight-line depreciation runs/lines, explicit reversal and Accounting/Project Cost proposal/reconciliation envelopes.
- Dedicated default-deny permissions, role grants, tenant checks, maker-checker controls, audit actions, occurrence keys, row locks and database uniqueness constraints enforce the accepted boundary.
- Persian-first RTL workbenches expose policy/source/version, calculations, transaction/depreciation reversal, and proposal review/reconciliation with explicit no-posting labels. No consumer-domain service is invoked.

Validation completed on 2026-10-05:

- `python manage.py check` — passed.
- `python manage.py makemigrations --check --dry-run` — migration drift: none.
- Migration plan / SQL generation — passed.
- Complete current migration graph on empty disposable PostgreSQL database `p8s2427_mig_20261005_7f9a2c` — 350 migrations applied, including `equipment.0005`, `organizations.0099` and `fixed_assets.0001`–`0004`.
- Dependency-safe rollback/reapply — reversed Fixed Assets to zero, `organizations.0099` to `0098`, Equipment to `0004`; then reapplied all six P8-S24–S27 migrations successfully. Catalog verification found 14 P8 tables, 104 indexes, 77 foreign-key relationships, all 13 named constraints and both partial unique indexes.
- combined targeted P8-S24–S27 behavior and accepted P8-S18–S23 regression suites on a freshly recreated disposable PostgreSQL schema — 17 passed, including capitalization/allocation retries, partial-period daily-prorata, prospective transfer, disposal cutoff and proposal reconciliation evidence.
- the S18–S23 no-effect regression was reconciled to assert zero Fixed Asset creation rather than absence of the now-authorized app.
- Ruff format/check over all affected Python artifacts — passed.

The migration-mode evidence is complete: the empty-schema rehearsal used the normal Django migration graph, including its required `btree_gist` extension migration, and the disposable database was removed after verification. Product Owner acceptance was recorded on 2026-10-05 for the implemented P8-S24–S27 scope. At the time of that acceptance, P8-S28–S30 and every production-readiness/cutover gate remained separate and unauthorized. Subsequent P8-S28–S30 Product Owner acceptance is recorded only in `P8_FINAL_ASSURANCE_CLOSEOUT_AND_P9_HANDOFF.md`; it does not alter this packet's accepted C01–C38 decisions or authorize production activation.

The repository-wide permission-registry architecture suite remains at 5 passed / 3 failed because of retained pre-existing Payroll duplicate registrations and older Materials/Timekeeping/Inventory/Equipment namespace or enforcement-reference findings. The new S24–S27 resources were split by permission namespace, every new Fixed Assets model is registered, and no S24–S27 permission appears in those failure sets. Those earlier findings were not broadened into this tranche.
