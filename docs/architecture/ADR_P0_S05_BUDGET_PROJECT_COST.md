# ADR P0-S05: Budget, CBS, cost-center and project actual-cost authority

**Date:** 2026-09-25. **Status: ACCEPTED AS TARGET ARCHITECTURE ON 2026-09-28;
NOT IMPLEMENTATION AUTHORIZATION; INDEPENDENT P4 GATES PRESERVED.**

The Product Owner requested P0-S05 following the
[S04 handoff](../ROADMAP_EXECUTION_PLAYBOOK.md#compact-p0-s05-handoff).
This proposal addresses P0.1/PPC-03 and informs P4.1. It preserves the accepted
native financial direction and the accepted target
[S04 financial-source contracts](ADR_P0_S04_ACCOUNTING_POSTING.md).
No cost producer, schema, permission, workflow or UI is implemented here.

## 1. Authority and current evidence

[Roadmap P0.1/P4.0/P4.1](../../ROADMAP.md) defines the scope;
[Domain Model](DOMAIN_MODEL.md#2-domain-principles) and
[Data Model](DATA_MODEL.md#6-transaction-source-of-truth-matrix) define target
ownership. The [PPC-03 finding](PRODUCT_CAPABILITY_AND_READINESS_AUDIT.md#19-pre-production-correction-register)
requires one budget/actual authority before real cost history accumulates.
Models/migrations remain current schema authority. The evidence below is static,
not a new passing runtime test or production-data assessment.

| Current evidence | Consequence for the proposal |
| --- | --- |
| [Project](../../apps/projects/models.py) stores independent Decimal `estimated_budget` and `actual_budget`; [create_project](../../apps/projects/services.py) takes both as inputs. | Neither field establishes an accepted line-level budget or a transaction-derived actual. Preserve values as legacy evidence until an approved transition. |
| [Estimate.total_amount / EstimateRevision.total_amount](../../apps/estimates/models.py) sum items, using the current revision when present. [create_estimate_revision](../../apps/estimates/services.py) copies the approved revision, moves `current_revision` to the draft and changes the root status to draft. Approval supersedes the prior approved revision. | A budget must pin specific accepted source versions/lines. A new draft or later approval cannot change a previously accepted budget. |
| [Financial report services](../../apps/financials/services.py), `_build_report` and `get_project_financial_report`, select approved Estimate roots, recorded Expenses and posted Payments. Report variance is approved-estimate total minus recorded-expense total; cash is separate. | The existing report is an operational projection, not a budget/actual/GL authority. From these filters, starting a new estimate draft excludes that Estimate root until reapproval; this static inference is not a newly executed regression test. |
| [WBSNode](../../apps/projects/models.py) is project-specific work structure; [create_wbs_node](../../apps/projects/services.py) checks tenant/project parent context. | Reuse WBS identity. Do not reinterpret the WBS tree as CBS or a chart of accounts. |
| [Billing ProjectBaseline](../../apps/billing/models.py) is a versioned, priced commercial measurement snapshot tied to a receivable contract. [create_project_baseline](../../apps/billing/services.py) creates that contract's next version. | This existing baseline is not the cost BudgetBaseline. Link commercial evidence explicitly; do not rename/reuse Billing's model as a budget. |
| [Project migration 0004](../../apps/projects/migrations/0004_project_budget_fields.py) renamed `budget` to `estimated_budget` and added `actual_budget`; [Estimate migration 0002](../../apps/estimates/migrations/0002_estimateitem_unit_of_measure_estimaterevision_and_more.py) created initial revision links. | Preserve original migrations and provenance. A historical default zero or backfilled revision link is not proof of accepted cost scope, currency or budget approval. |

Direct regression references are
`test_report_uses_approved_estimates_and_recorded_expenses` and
`test_report_rejects_cross_tenant_project` in [financials tests](../../apps/financials/tests.py),
and `test_explicit_request_creates_workbench_item_and_preserves_revision_invariants`
in [Estimate workflow tests](../../apps/estimates/test_workflow.py).
Those bodies were inspected; no tests were run. The narrow expansion into Billing
and migration history resolves baseline-name ambiguity and revision provenance,
not a new audit of those domains.

## 2. Proposed ownership and dimensions

| Fact / owner | Proposed boundary |
| --- | --- |
| Contractual BOQ / Contracts and Billing | Commercial quantities, prices and measurement terms, including the delivered Billing baseline. Contract price/revenue is not automatically expected internal cost. |
| Estimate revision / Estimation | Calculated assumptions, quantities, resource/rate evidence and scenarios. Approval establishes estimate evidence; explicit budget acceptance is a separate action. |
| Accepted BudgetBaseline version / Project Controls | Authorized internal cost plan, mapped lines, approved changes and governing version. Project's manual totals do not compete with this authority. |
| CBS / Project Controls | Tenant-owned cost classification, with an explicitly selected project structure/version and controlled leaf codes; hierarchy totals roll up leaves once. |
| Cost center / Project Controls | Tenant-owned responsibility/overhead allocation dimension with explicit applicability to projects. It is not a department, required workforce structure, bank account or GL account. |
| WBS/activity / Projects | Work scope and execution structure. Site/phase/activity links are validated against their project; not every project must use every optional level. |
| COA and posting dimensions / Accounting | Ledger classification and financial posting validation. Versioned mappings connect cost classifications to Accounting without making CBS the COA. |
| Source fact / producer domain | Commitments, incurred/valued resource events, obligations and cash retain their original domain authorities. Project Controls owns classified projections and forecast assumptions, not another ledger. |

Proposed default is one governing cost-budget version per organization/project at
a time, with explicit currency basis and non-overlapping validity. Multiple
contracts or estimate inputs feed that budget through a scope manifest; they do
not become additive project budgets by default. Alternative scenarios remain
estimates/forecasts, not additional governing baselines. More complex budget books
would require an approved extension rather than hidden parallel authorities.

CBS codes and cost-center codes must be unique within their defined tenant/local
structure scope; retain UUID identities independently of display codes. Prevent
cycles and invalid parent/project links. Archive referenced dimensions instead of
deleting history. Historical facts retain dimension/mapping versions and recorded
labels; reorganizing the current tree does not rewrite prior results.

Small contractors can use a minimal cost structure without departments, positions
or employee assignments. Unassigned optional responsibility is explicit; unknown
mandatory cost classification is an exception, not an invented default allocation.
The exact starter CBS and cost-center applicability policy remain open.

## 3. Estimate-to-budget handoff and lifecycle

An explicit handoff identifies organization/project, source Estimate UUID and
approved revision UUID/version, included source-line IDs, any commercial BOQ or
Billing baseline/item versions, and the reason for inclusions, exclusions and
adjustments. Map commercial price to cost only through reviewed cost assumptions;
do not import margin, tax or recoverable amounts as cost without the applicable
policy. P4.0's resource/coefficient extensions remain separate work.

Each accepted budget line retains quantities/UOM where applicable, Decimal amount,
explicit source and budget currency, relevant rate/rounding evidence, WBS/CBS/
cost-center context, and mapping/assumption versions. Many-to-many mappings use
explicit split amounts or quantities and approved allocation bases. Allocation
totals must conserve the in-scope source amount after documented adjustments;
rounding residuals are explicit. No copying one whole source amount into every
destination. Excluded or unmatched scope is visible with reason and approver;
unresolved required mapping blocks acceptance.

Proposed lifecycle: `draft -> submitted -> accepted`, with `submitted -> draft`
for a reasoned return and `draft/submitted -> withdrawn`. Submission freezes its
reviewed payload; a returned edit creates a new submission version. Acceptance
records approver/time/reason, source/mapping versions and audit evidence. An
accepted version is immutable. A new revision starts from it and becomes governing
only through another accepted handoff/change. The former version remains available
with a supersession link; its recorded values/approval evidence do not change.
No direct edit, deletion or silent reset of the original comparison baseline.

Creating a new estimate draft, approving another estimate revision, amending a
contract or changing a CBS mapping does not automatically rebaseline. A later
budget revision needs an explicit reason and change comparison. Previously
accepted budgets retain their pinned estimate revision even after it becomes
superseded; eligibility to use a superseded source for a *new* handoff requires
an explicit approved policy, not the current pointer's accidental state.

Acceptance locks the governing project-budget control and relevant draft/source
versions, re-reads state, checks scope/permission/separation, then commits the new
version, governing link, any registered workflow completion and audit atomically.
Enforce unique project/version and at most one governing version with database
constraints plus a consistent lock order. Concurrent acceptances using an outdated
predecessor must conflict instead of replacing each other silently.

A durable tenant/project handoff ID plus submitted version is the retry identity.
Identical authorized retries return the recorded result; changed payload with the
same identity conflicts. Separate IDs must not let the same scope appear twice
in a baseline: validate the source-line/scope manifest and non-overlapping splits
independently of transport retries. Reusing evidence for a later baseline revision
is explicit replacement lineage, not additive spend. Approved budgets do not post
journals or create liabilities by themselves.

## 4. Cost, commitment, accrual, cash and forecast semantics

Each view declares its tenant/project, currency/valuation basis, cutoff, governing
budget version, mapping version, source coverage and refresh/watermark. Missing
producer coverage or posting evidence is visibly incomplete, never a zero-cost
assertion or certification of comprehensive actuals.

| Measure | Proposed meaning and source rule |
| --- | --- |
| Original / current budget | Original accepted cost baseline and latest governing accepted version, with explicit revision bridge. Neither equals the sum of all current approved estimates. |
| Authorized commitment | Effective approved/issued external cost obligation from the contract/PO source, with change/cancellation lineage. A receivable sales contract is not a cost commitment. |
| Open commitment | Unfulfilled cost exposure after source-matched performance/consumption and approved releases under that producer's contract. Settlement/payment does not consume it. Show authorized total and remaining amount separately. |
| Actual cost | Classified incurred/valued source facts under an approved recognition basis. A financial actual must trace to relevant subledger/posting evidence; an operational cost awaiting that evidence is separately labeled and reconciled, not silently counted twice. |
| Accrual | Incurred cost awaiting the final invoice/settlement evidence, governed by Accounting and its source. Invoice replacement clears/reverses or adjusts that same recognition lineage; accrual plus invoice cannot count the same work twice. |
| Paid cash | Treasury outflow, with AP/AR/source links when allocated. Advances, asset purchases and settlement are not automatically current project cost. Unallocated cash remains explicit. |
| ETC / EAC | Approved remaining-work forecast and total forecast. For a matching scope/currency/cutoff, EAC = actual cost + ETC. ETC includes remaining committed work once plus uncommitted forecast work; do not add open commitments again to EAC. |
| Variance | Label budget-to-actual remaining capacity separately from forecast variance. Here remaining capacity = current budget - actual; favorable forecast variance = current budget - EAC. This is not earned-value cost variance, which belongs to P4.2. |
| WIP | Separate versioned Accounting/project-control policy, source provenance and reconciliation. Neither budget minus expense nor cash surplus establishes WIP, revenue recognition or profit. No WIP formula is approved here; optional professional evidence may attach to a future policy version. |

Forecast versions retain the source cutoff, selected budget, assumptions, preparer,
review evidence and risk/exception explanations. Submitted/accepted forecasts are
immutable; updates produce another version. Forecast acceptance never revises a
budget, changes a source or posts GL. Exact approval, contingency, escalation and
overrun-warning/blocking policies remain open; a negative variance alone creates
no new blocking rule.

Minimum producer contracts prevent known double-counting paths:

| Producer boundary | Contract needed before cost integration |
| --- | --- |
| PO/service receipt/invoice | Identify the same committed work across performance/accrual and final invoice, consume commitment once, and account for quantity/price differences as linked adjustments. Never sum all documents as independent actuals. |
| Inventory | Reconcile quantity and approved valuation to project consumption/returns. Buying or holding stock may be an asset; procurement payment, receipt, supplier invoice and later issue are not four project costs. Define the stock/commitment bridge before integrating. |
| Expenses / AP | Retain expense source and any payable/posting identity; a later invoice or payment matching that expense must not recreate its cost. |
| Payroll / equipment | Use finalized cost distributions or accepted valuation/posting evidence; field time/usage observations and their downstream payroll/depreciation/expense entries cannot all count as separate costs. |
| Claims / Treasury | Receivable claims and receipts remain commercial/cash measures; payable certificates may feed cost only under an accepted source contract. Settlement does not recognize a second actual. |

These are interface acceptance requirements, not implemented producer behavior or
permission to expand P4.1 into P5/P6/P7/P8 in this session.

## 5. Lineage, corrections, reconciliation and access

Each classified fact retains tenant, source kind/UUID/version/line, economic event
and occurrence identity, project context, recognition date, source currency/amount,
mapping/valuation versions, split identity and available posting/subledger links.
Use S04's proposed economic-event identity contract. Retries, duplicated imports
and the arrival of a downstream representation do not create another cost for
the same event. One recognized source can split across valid destinations, but
the conserved total is still one event.

Cost facts and aggregate projections are rebuildable from retained source evidence
and approved classification history. A classification change creates a reasoned
superseding version or reclassification adjustment; it must not leave old and new
splits simultaneously active in the same view. Reports pin their chosen history
and mapping basis. A source correction/reversal retains the original links and
uses the owning domain's services. A projection rebuild cannot change GL, remove
audits or bypass S04's period-close controls. Changing a GL dimension requires an
Accounting-approved correction; changing a management view must not masquerade as
a restated posted journal.

| Reconciliation | Evidence / owner |
| --- | --- |
| Estimate/BOQ -> budget | Included/excluded scope, mapping splits, explicit adjustments and total bridge; Estimation/Commercial source owners with Project Controls acceptance. |
| Commitment -> performed/released/open | Source-line matches, amendments and cancellations, preventing both missing and duplicate relief; producer owner with Project Controls. |
| Source -> classified actual -> GL | Recognized event totals equal active allocations plus explicit unresolved amounts; compare to relevant GL cost/asset/WIP postings by matching basis and retain timing, valuation and scope differences. Accounting owns financial disposition, Project Controls classification. |
| Paid -> Treasury/AP/AR | Movement and allocation lineage reconciles to cash/subledger separately. Cost-minus-paid is not universally AP outstanding because advances, tax, stock, timing and other obligations may differ. |
| Budget/forecast -> displayed totals | Version/cutoff/coverage and source drill-through; include classified and unresolved totals without rolling up parents and children twice. Project Controls owns display semantics. |

Mismatch resolution is an auditable source correction, classification repair or
approved disposition, not a manually edited actual total or GL balancing plug.
Export/reconciliation must retain the scope and version evidence used.

Resolve organization through active membership; validate every relationship and
mapping at view/service boundaries. Reads/exports/drill-through need business
permission and applicable project/site scope, including sensitive source checks.
Budget preparation, acceptance/rebaseline, classification administration, forecast
approval and export need explicitly designed permissions and separation rules.
Future implementation must add permission codes/registry/catalog/default-grant
migrations and tests; no grant is invented here. Recheck authorization/tenant
state inside mutation transactions. Workflow coordination uses existing registered
domain services; workforce positions never grant permission. Q04 policy selections
are recorded, including final G3 — Revised with Protected Operations and configurable
business-operation Self-Approval; named review,
risk/control evidence and compatible implementation still gate acceptance.
Suspended tenants cannot mutate; cancelled tenants cannot use normal business access.

## 6. Legacy containment and delivery sequence

Keep `Project.estimated_budget` / `actual_budget`, current report semantics, Estimate
revisions and Billing baselines intact in S05. Retirement as authorities is a target,
not authorization to remove compatibility fields or silently change existing UI.

1. **Design gates:** accept this ADR, resolve affected policy choices and approve
   implementation. P4.1 retains P1.2 and P2.1 dimension prerequisites; P1.1 scope
   enforcement is a cross-cutting acceptance dependency. P4.0 remains the owner
   of deeper estimate/resource analysis; no new phase order is declared here.
2. **Expand:** in an approved P4.1 slice, introduce budget/CBS/cost-center/mapping
   authority and explicit Estimate-version handoff. Choose a bounded producer
   with coverage/reconciliation contracts. Operational projections can be useful
   before all producers exist, but stay labeled partial and never become GL.
3. **Inventory/map:** retain legacy values with tenant/project identity, original
   field meaning, source provenance and a reviewed cutoff. Inspect all writers/
   readers before switch, including [Project forms](../../apps/projects/forms.py),
   [views](../../apps/projects/views.py), [Django Admin](../../apps/projects/admin.py),
   [project detail](../../templates/projects/detail.html), lists and shared field
   labels. These are confirmed consumers, not a complete migration inventory.
   Find seed/import/report/export dependencies in the authorized implementation
   slice; none is assumed absent from this narrow inspection.
4. **Backfill with review:** a manual estimated total may seed a draft candidate
   only with explicit scope/currency/provenance and acceptance; never auto-approve
   it. `actual_budget` cannot become a synthetic expense, payable, journal or
   authoritative cost fact. Missing original evidence/currency/line mapping stays
   a named exception. Do not backfill from the live Estimate root total or current
   tenant currency without historical evidence. Q01 governs conversion rules.
5. **Switch/validate:** select one authority per measure, reconcile legacy vs new
   totals with explained differences, show versions/coverage and preserve original
   snapshots. Differences can be legitimate; do not force equality by plug entries.
   Replace legacy input/display roles only in that approved slice; prevent dual
   authority/dual writes. Rehearse concurrent acceptance, correction and recovery.
6. **Rollback/contract:** before switch, disable new writers without deleting draft
   mapping evidence. After accepted budgets/cost history, preserve versions and
   reconcile ownership before any rollback; prefer a controlled forward repair.
   Retain compatibility until deployment, dependency removal, retention, tenant
   revalidation and passing tests. Field removal needs separate explicit approval;
   migration reset/squash and destructive cleanup remain out of scope.

## 7. Static acceptance walkthroughs

All amounts below are Decimal values in hypothetical single currency `C`, with no
tax, FX or retention. These illustrate proposed semantics, not approved accounting
policy, an IRR choice or runtime tests.

| Case | Inputs and expected evidence/result |
| --- | --- |
| Pinned handoff | Accepted estimate revision E1 has included cost lines 600 + 400; baseline B1 = 1,000. The 600 line splits 360 + 240 across two valid CBS leaves, conserving 600. E2 is a later 1,100 draft: B1 remains 1,000. Accepting E2 alone also leaves B1 unchanged; only budget acceptance can create governing B2 = 1,100 with a +100 bridge. |
| Cost versus cash | B1 = 1,000; approved service commitment 600; performed/accrued work 200 leaves open commitment 400. Paying 150 changes paid cash, not actual 200 or open commitment 400. ETC = remaining committed work 400 + uncommitted forecast 300 = 700; EAC = 200 + 700 = 900; remaining budget capacity 800; favorable forecast variance 100. |
| Accrual replacement | The same performed work is invoiced at 210. Reverse/clear recognition of 200 and recognize 210, or apply an approved linked +10 adjustment: actual is 210, not 410. If remaining work is still 400, retain a +10 matched commitment-price change (authorized total 610, performed 210, open 400); otherwise flag the difference for review. With unchanged ETC 700, EAC is 910 and favorable forecast variance 90. Payment remains 150. |
| Reclassification / reversal | Reclassify the performed 200 from CBS A into 120 at A + 80 at B: total remains 200 and prior split history survives. In a separate branch, if that performance is reversed while the commitment remains valid, actual returns to 0 and open commitment to 600. If paid 150 is still real, retain cash as an advance/unapplied item under AP/Treasury policy; do not invent a refund. |

Duplicate handoff acceptance or source delivery must preserve the same accepted
version/totals. Cross-tenant or wrong-project mapping, overlapping included scope,
missing currency, mismatched UOM, unauthorized acceptance and stale-predecessor
concurrent acceptance must fail without partial budget/workflow/audit changes.
No actuals produced yet means missing coverage, not a demonstrated zero balance.

## 8. Open decisions, consequences and acceptance gates

| Input / accountable role | Latest gate and retained boundary |
| --- | --- |
| Budget policy / Product Owner and Project Controls reviewer, to be named | Before accepting detailed P4.1 design: initial baseline/change authority, eligible source revisions, one-budget scope, starter CBS, cost-center applicability, allocation bases, contingency/overhead treatment and overrun controls. These are proposals, not new accepted defaults. |
| Q01 / Product Owner and Platform policy owner | Section 9 records IRR initial base/storage/display, no FX behavior, UTC/ISO persistence with Jalali UI, explicit fiscal calendar, versioned precision categories and no current financial inventory valuation. Actual precision/rounding values and later P4/P8 valuation decisions require authorized effective configuration; source evidence is mandatory only where the policy or claimed basis requires it. |
| Q02 / Product Owner and Platform policy owner | Section 9 records the export-only boundary and official-source hierarchy. Actual source versions remain required where recognition/accrual replacement, capitalization/WIP, forecast basis or source-to-GL assertions declare provenance dependence. Optional professional evidence is not a global development gate. No legal formula or current BillingPolicy rate is certified. |
| Q04 / Product Owner and security/workflow owner | A-H selections are recorded; named security/workflow/accounting/domain and applicable legal review remains before affected acceptance. Budget services must prohibit Self-Approval for Protected Operations and apply auditable platform/tenant policy plus tenant compliance responsibility to configurable business approvals. |
| Migration / Product Owner, reviewer and operator | Approve pilot/coverage, cutoff, historical evidence mapping, exceptions and rollback acceptance before switching authority or rollout. No sample project/producer is selected by the walkthroughs. |

The full [S03 open-input register](../ROADMAP_EXECUTION_PLAYBOOK.md#unresolved-parameters-and-latest-gates)
remains open at its original gates, including D01 workload/pilot details, D03-D05
and Q03 retention/storage requirements. S04 is accepted as target architecture;
its implementation and affected policy/source gates remain. This ADR does
not freeze release scope, complete PPC-03/P0.1 or authorize implementation.

Alternatives declined in this proposal: retain editable Project totals as final
authorities (no source history); treat every approved estimate as additive budget
(overlapping scope/live revision drift); reuse Billing's commercial baseline for
cost (different meaning); compute actuals from cash or sum every source document
(timing and duplicate recognition); create a parallel project GL (violates D02).
Tradeoff: explicit mapping and reconciliation require reviewer work and may expose
historical gaps; they preserve explainable totals instead of manufacturing history.

Build-vs-Reuse: use Decimal, Django ORM, database constraints/transactions and
existing workflow/authorization/audit mechanisms. Own ERP budget acceptance,
classification and reconciliation rules. No dependency or new app is approved.

Future approved implementation must test source-version pinning and immutable
history; split conservation and scope completeness; tenant/project/permission
denials; concurrent/idempotent acceptance and audit rollback; lifecycle/SoD;
commitment relief and accrual/invoice/stock/payroll deduplication; classification
supersession and source reversal; currency/UOM precision; financial tie-out and
partial-coverage labels; legacy cutover/rollback and representative volume.
Existing Project/Estimate/Billing/report behavior remains a regression obligation
until replaced by an approved product change. These are planned tests, not results.

## 9. P1-S14 Product Owner disposition and incorporated Q01/Q02 baseline

**D14-02 Option A accepts this ADR as target architecture.** Immutable accepted
budget baselines, CBS/cost-center classification and separate commitment, accrual,
actual, paid and forecast facts retain the ownership and lineage described above.
All detailed P4 budget policy, pilot, migration, implementation and acceptance
gates remain independent and open.

The incorporated P1-S14 baseline is: initial Tenant base currency/storage/display
IRR with future multi-currency readiness but no FX behavior; UTC/ISO-compatible
storage with Jalali UI and explicit fiscal calendar; versioned platform-governed
precision categories with final accounting values unset until configured through
an applicable versioned policy;
and no authoritative financial inventory valuation in P1-S14/current Inventory.
Official versioned sources remain required where an S05 policy declares provenance
mandatory or its semantics make a source-backed accounting/legal assertion.
Optional professional evidence may supplement an exact
policy/source version but is not a global development gate. This acceptance
authorizes no financial implementation, valuation method, statutory rate, Chart of
Accounts or P4 work.
