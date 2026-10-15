# CEP-006 schema remediation and reauthorization packet

**2026-10-15 · Design only.** CEP-006 is **EXECUTION PARTIAL**; AUTH-BATCH-002 is stopped. This packet proposes a bounded target contract and authorization path. It is not Product Decision approval, CEP reauthorization, migration permission, or an implementation instruction. No product code/model/migration was changed.

## A. Executive conclusion

The [grain evidence packet](CEP-006_COMPARISON_GRAIN_DECISION_PACKET.md) found 12 missing and three ambiguous dimensions among 41 declared dimensions across 13 Reporting pairs. [PD-033](docs/architecture/BONIRA_PD_033_RECONCILIATION_CURRENT_STATE.md) establishes latest eligible native run per existing native grain, but `subledger_gl.control_account` and `treasury_gl.currency/source_identity` are absent from the native aggregate runs. The native run services retain hashes/totals, not a recoverable, versioned per-grain membership manifest. Repeated-run ordering and invalidation are also unspecified. **Source-owned schema remediation is recommended for prospective exact evidence**; historical financial identity must not be inferred. The precise slice shape and policy choices in D02–D07 remain Human decisions.

**Repository anchors:** [Accounting `Account`, `JournalEntry`, `JournalLine`](apps/accounting/models.py); [Subledger `Obligation` and run](apps/subledgers/models.py); [Treasury movement, run, bank import/clearing](apps/treasury/models.py); [Payroll statutory output/reconciliation](apps/payroll/models.py); [source services](apps/subledgers/services.py), [Treasury–GL service](apps/treasury/services.py), [bank service](apps/treasury/statement_services.py); [Reporting pair catalogue/adapters](apps/reporting/reconciliation_catalog.py), [P10 authority and history policy](docs/architecture/P10_S07_S13_RECONCILIATION_AND_EXCEPTION_DECISION_PACKET.md). The canonical `packages/CEP-006.md` in `BONIRA_CODEX_EXECUTION_PACKAGE_DESIGN_CONSOLIDATED_LATEST.zip` says risk **HIGH**, scope **query/read-model correction and scalability**, Migration Impact **NONE**, and no source-domain schema work. The separately approved AUTH-BATCH-002 execution does not silently amend that scope.

## B. Approved D01/D08 disposition

**CEP006-D01 APPROVED:** PD-033 native-run selection applies only where the Reporting adapter consumes a retained native reconciliation run. Direct-source pairs derive currentness from their own source-domain lifecycle/version contract; no synthetic native run. This retains every declared grain, source-version and IMB-0044 AC requirement. **CEP006-D08 APPROVED:** `contractor_compliance` remains `gated_not_activated` until an authorized consumer persists all four right-side dimensions. No placeholder consumer or two-sided result. These approvals narrow applicability only; they do not resolve D02–D07 or authorize implementation. [PD-033](docs/architecture/BONIRA_PD_033_RECONCILIATION_CURRENT_STATE.md) records the approval addendum.

The presently run-consuming adapters are `subledger_gl`, `treasury_bank`, `treasury_gl`, and `payroll_insurance` ([adapter code](apps/reporting/reconciliation.py)). `payroll_financial_handoffs` and `fixed_asset_handoffs` have domain reconciliation evidence models, but their Reporting adapters consume proposal/envelope source rows, so D01 treats them as direct-source pairs.

## C. Remaining D02–D07 resolution matrix

| Decision | Repository fact | Proposed bounded remediation | Still requires Human decision |
| --- | --- | --- | --- |
| D02 — direct-source gaps | The grain packet records U01–U06 and U10–U11; PO currency, Inventory pool warehouse/unit, Project Cost contract project/event and historical pool cutoff are not established. | Resolve each in its owning source domain; do not make Reporting own a financial mapping. Some may require source-domain schema, some a proved existing path. | Exact path and currentness/cutoff policy for each gap; whether these belong in this amendment or a separately authorized source-domain package. |
| D03 — subledger account | `accounting.Account` is the posted ledger account identity; `JournalLine.account_id` is the exact posted line link. `Obligation.recognition_journal_id` exists, but its reconciliation service emits `CONTROL_MAPPING_NOT_APPROVED` and sums all obligations by direction/as-of. | Prospective immutable account slices under each Subledger run, with explicit account FK and pinned obligation/journal-line source evidence. | Approved AP/AR control-account mapping, whether a run may span multiple accounts, and how amounts are allocated without invented GL totals. |
| D04 — Treasury–GL currency/source | `TreasuryMovement` has currency, version, occurrence ID and journal FK; `JournalEntry` has currency, source UUID/version and journal lines. The native run stores aggregate totals, cutoff, counts and hash only. | Prospective immutable run slices with currency and an approved stable source-scope identity, plus versioned movement/journal membership rows. | Definition of `source_identity` at declared grain, mixed-currency disposition, precise included-set and reversal/posted semantics. |
| D05 — eligibility | Subledger, bank and Treasury–GL services create retained runs near the end of `transaction.atomic`; no persisted lifecycle field. Payroll `matched`/`exception` is a comparison outcome, not run success. | Preserve immutable outcome; add only the source-owned completion/invalidation evidence needed for current eligibility. Mismatch may be complete, subject to Human policy. | Whether review is required, what invalidates a run, and which complete mismatch remains eligible; do not equate match with successful execution. |
| D06 — ordering | As-of/cutoff fields exist, but no approved same-grain repeat sequence. UUID/`created_at` are not business sequence. Payroll statutory reconciliation is one-to-one with an output, so the exact `statutory_output` grain does not permit two runs for that output. | Prefer a source-owned monotonic grain-local revision allocated under lock, with a predecessor link as audit lineage; see G. | Whether repeat execution creates a new revision or is prohibited for each pair; tie/fail-closed rule; treatment of historical unsequenced runs. |
| D07 — source versions | Subledger obligations and journals have source versions; bank import has payload/acceptance hash; Treasury movements/journals have source versions; Payroll output has schema/revision/digest. Native runs do not uniformly pin all included versions. | Prospective immutable source-evidence rows and hashes in each owning domain; Reporting records exact IDs/versions as read lineage only. | Required source set and version/line granularity per pair; review hash and replacement pin; unresolved historical runs remain unverifiable. |

## D. `subledger_gl` target data contract

**Authority:** Accounting owns [`Account`](apps/accounting/models.py) and the posted [`JournalLine.account`](apps/accounting/models.py) identity; Subledgers owns [`Obligation`](apps/subledgers/models.py) and its native reconciliation. Reporting may read those identities but cannot assign a control account. `Account.code` is tenant-unique, while the stable FK/public ID is preferable to a mutable display label; an account used by a journal line cannot change code/type under its model rule. The current Subledger run persists `direction`, `as_of_date`, totals, obligation/journal ID arrays and hash, but **no account**, source versions, or per-account amounts.

**Proposed minimum, conditional on D03:** add a tenant-scoped immutable `SubledgerReconciliationAccountSlice` (conceptual name) belonging to one native run, with `control_account → accounting.Account`, direction/as-of inherited and validated against the parent, per-account subledger/GL totals and difference, evidence hash, source count, and eligibility/provenance marker. Add tenant-scoped immutable evidence links from the slice to the exact obligation ID plus its persisted `source_kind/UUID/version/line/hash`, and to the exact posted journal/line/account plus journal `source_uuid/version` and posting/hash evidence. Record a source-version snapshot at run time; do not infer it later from a current source head. The sums of account slices must conserve parent totals; every included source is assigned once under the approved mapping, or the run is unavailable at that grain.

**Cardinality:** the existing service takes all obligations of one direction/as-of; it does not constrain them to one Account. Therefore one-account-per-run is **not established**. A normalized child slice is the safer proposed shape if D03 permits multiple accounts, because a single FK on the parent would misstate a mixed run. If D03 mandates one account per run, the service must filter/validate that single scope before creating a prospective run; the existing historical aggregate cannot be relabeled. Approval of the actual control mapping remains prerequisite; current `linked_gl_total = 0` and `CONTROL_MAPPING_NOT_APPROVED` are not a valid GL tie-out.

**Constraints:** FK `PROTECT`, same-tenant checks at service/model boundaries, unique `(run, control_account)`, immutable slice and link payload, unique included source identity within the run/grain, hash verification, aggregate conservation, and no account without approved posting/control mapping. A revision/predecessor is separate from account identity. Exact DB constraint feasibility for cross-table tenant equality needs migration design review; application validation plus transaction locks cannot be represented as a simple cross-table check constraint.

## E. `treasury_gl` target data contract

**Authority:** Treasury owns movement and native run facts; Accounting owns journal/line facts. The [service](apps/treasury/services.py) currently visits posted movements through the cutoff, sums legs and journal lines, checks occurrence/source-version equality, and hashes a transient payload containing movement/journal IDs. [`TreasuryGLReconciliationRun`](apps/treasury/models.py) persists only cutoff, counts, totals, exceptions and hash. A hash proves payload integrity if the original payload is available; it is neither an extractable source-ID set nor source version.

**Proposed minimum, conditional on D04:** tenant-scoped immutable `TreasuryGLReconciliationSlice` records the approved `currency` and **stable source-scope identity** at one cutoff, plus per-slice totals/hash and provenance. Immutable included-source rows record each `TreasuryMovement` ID, occurrence ID, persisted movement version/currency/status at capture, its leg IDs/amounts, linked `JournalEntry` ID, journal `source_uuid/source_version/currency/status`, included journal-line IDs and posting/evidence hash. The snapshot must distinguish missing/unposted journal evidence from an included posted journal; no fabricated GL side. The source-scope identity cannot be defined as the hash of a changing included set if that would make every rerun a different grain; D04 must decide its stable meaning. A single run may contain multiple currency/source slices only if D04 explicitly allows it and slice totals conserve the parent; otherwise service creation must reject mixed scope.

**Constraints:** FK `PROTECT`, tenant equality, unique `(run, currency, approved_source_identity)`, unique membership of each movement/version and journal/version within its approved slice, no duplicate line inclusion, immutable capture, source/journal version equality checks where the native service already requires them, and conservation of slice-to-parent totals. Conditional unique indexes and checks can enforce local field invariants; cross-model source status/tenant/lineage checks remain transactional service validations. No Reporting-owned financial identity column is proposed.

## F. Native-run lifecycle contract (proposal, not approved behavior)

| Pair | Persisted facts now | Smallest proposed prospective evidence | Eligibility remains undecided |
| --- | --- | --- | --- |
| `subledger_gl` | Atomic retained run; no status/review state on run; separate one-to-one review. | Creation completion evidence plus append-only invalidation/review disposition linked to immutable run/slices; no mutation of totals. | Completed with difference may be eligible only if D05 permits; missing approved control mapping currently prevents a valid grain result. |
| `treasury_bank` | Atomic retained run; separate review; statement import must be accepted; clearing links/reversals retained. | Keep run immutable; pin statement payload/acceptance hash and exact clearing/reversal IDs; add append-only invalidation if D05 requires it. | A mismatch is a completed comparison, not necessarily a failed execution; review requirement undecided. |
| `treasury_gl` | Atomic retained run; separate review; exception list. | Completion/invalidation evidence with immutable slices/source membership. | Exception-bearing run may be complete; D05 decides eligibility and review. |
| `payroll_insurance` | Immutable `StatutoryReconciliation` is one-to-one with output; `matched`/`exception` describes result. Output pins calculation/schema/revision/digest. | Reuse output/calculation lifecycle and one-to-one constraint; add invalidation evidence only if the existing correction/withdrawal chain cannot express D05 policy. | Do not treat `exception` as failure; review and current output series rules need D05/D07. |

`started`/`failed` attempts may be operational events rather than final run rows; no need to put every requested label on each native model. An immutable completion record plus append-only invalidation is preferable to rewriting a retained run to `superseded`. Current-read supersession is derived from the approved ordered successor, while historical runs remain visible. These are design recommendations, not authorized lifecycle semantics.

## G. Total ordering and supersession contract

| Mechanism | Fit | Limitation |
| --- | --- | --- |
| Explicit `supersedes`/predecessor FK only | Preserves exact lineage without sorting by UUID/time. | Branching successors or two independent first runs must be serialized/uniquely prevented; predecessor alone is not a total order. |
| Monotonic grain-local revision | Deterministic `1…n` within tenant + pair + full declared grain + business as-of; query and unique constraint are straightforward once grain is persisted. | Requires new field/index, locked counter or scope row, and policy for legacy unnumbered runs. |
| Immutable run revision plus predecessor | **Recommended conditional design:** allocate next revision under `transaction.atomic`/row lock; link the previous eligible run/slice; unique grain/revision and at-most-one successor; explicit invalidation may leave last valid predecessor current. | D03/D04 must first settle grain and D05 must settle eligibility. If a parent run covers several grains, revision belongs to each grain slice, not a misleading parent-wide number. |

For bank, a grain-local revision can live on `BankReconciliationRun` because account/import/as-of already identify one grain. For subledger and Treasury–GL it belongs on the proposed per-grain slice if multiple slices are approved. Payroll's one-to-one output relation prevents rerunning the identical output; whether a newer output revision is a new grain or a successor is a policy question. `created_at`, UUID and row order remain audit/technical evidence, not business ordering. A failed or invalidated higher revision never silently displaces the last eligible current revision.

## H. Source-version evidence contract

| Pair | Minimum immutable prospective pin | Distinctions that must remain visible |
| --- | --- | --- |
| `subledger_gl` | Run/slice ID and revision; Account FK; obligation ID plus its `source_kind/UUID/version/line/hash`; exact journal and journal-line IDs plus `JournalEntry.source_uuid/source_version`, posted status/hash; as-of. | Obligation source version ≠ journal source version ≠ native run revision ≠ run hash. Current Account configuration cannot prove historical control mapping. |
| `treasury_bank` | Run ID/revision; account, statement import ID, accepted payload/acceptance hash and policy version; exact statement lines, clearing/proposal/reversal IDs and linked movement IDs/versions; as-of. | Statement hash identifies a snapshot, not every movement version; `active` clearing is mutable current state. |
| `treasury_gl` | Run/slice ID/revision; currency and approved stable source-scope identity; included movement/leg IDs, occurrence/version, linked posted journal/line IDs and source UUID/version/hash; cutoff. | Business occurrence ≠ movement row ≠ journal source version ≠ native run ID. Transient service payload cannot be treated as persisted membership. |
| `payroll_insurance` | Reconciliation ID; output ID, series/revision/schema/content digest; calculation ID, series/revision/policy/source digest; finalized payroll run ID/input/calculation digest; as-of/period. | `matched`/`exception` is outcome, not completion state. Output revision is not a new run version unless the policy says so. |

Reporting's `ReconciliationSideSnapshot.source_manifest` and `source_watermark` may carry these exact native references after the source domains persist them; Reporting remains a read/projection authority. The P10 [decision packet](docs/architecture/P10_S07_S13_RECONCILIATION_AND_EXCEPTION_DECISION_PACKET.md) requires exact native run/review/hash, cutoff, versions and reproducibility, with `unverifiable` rather than invented history.

## I. Historical backfill classification

| Proposed item | Existing records | Classification and rule |
| --- | --- | --- |
| Existing run FK/ID, direction/as-of or account/import/cutoff, totals and evidence hash | Already persisted on respective native runs. | **SAFE-BACKFILL** only for copying those exact values into a derived index if needed; no financial reinterpretation. |
| Subledger account slice/account FK and per-account totals/source-line mapping | Current run holds aggregate totals and ID arrays; service says control mapping unapproved. | **UNBACKFILLABLE-WITHOUT-INFERENCE**; prospective-only after D03. Do not derive from today's Account/chart or journal state. |
| Treasury–GL run currency, stable source identity, included movement/journal versions and per-source totals | Run has count/hash; original transient payload is not stored as typed evidence. | **UNBACKFILLABLE-WITHOUT-INFERENCE** on present evidence; prospective-only after D04. A hash cannot reconstruct its inputs. |
| Bank import/account/as-of and statement payload hash | Run/import links already persist these. | **DERIVABLE-WITH-CANONICAL-EVIDENCE** from FK and immutable accepted import; clearing membership/version at run time is not necessarily derivable from current `active` flag. |
| Payroll output/calculation/run/version/digest links | Existing FKs and immutable source records persist these. | **DERIVABLE-WITH-CANONICAL-EVIDENCE** for exact linked values; historical current-eligibility/review policy still unresolved. |
| New grain-local sequence/predecessor | Old runs may share grain/cutoff and have no business order. | **PROSPECTIVE-ONLY**; do not number old rows using `created_at` or UUID. |
| Legacy provenance classification | Absence of new typed evidence is observable. | **SAFE-BACKFILL** of a nonfinancial marker such as `legacy_unverified`, never of missing financial identities. Retain each old run, expose reason and prevent unsupported current claims. |

Prospective cutover should start only after the new source service writes complete typed evidence atomically and verifies it. A legacy run with unverified grain/version remains historical and queryable; it cannot supersede a fully evidenced new run merely because it was created later. Any desire to promote a historical run requires exact archived inputs and separate source-owner verification, not automatic backfill.

## J. Direct-source pair disposition after D01

These pairs need source-domain currentness, not a fabricated native reconciliation run. “Implementable” means the source contract appears sufficient for a bounded read correction, **not** that the current Reporting adapter is correct or CEP-006 is authorized to implement it.

| Pair | Source lifecycle/currentness evidence | Disposition |
| --- | --- | --- |
| `estimate_budget` | `ProjectBudgetControl` points to a governing accepted `BudgetVersion`, with version/predecessor and pinned manifest estimate revision. Adapter currently sums all accepted versions. | **IMPLEMENTABLE WITH EXISTING SOURCE CONTRACT**, subject to exact pointer/as-of proof. |
| `commitment_projection` | PO version and Project Cost fact source-version exist, but source-contract join and PO currency are unresolved (U01–U02). | **SOURCE CONTRACT REMEDIATION REQUIRED**. |
| `po_receipt_invoice` | Approved invoice version, immutable match `version_number/supersedes`, PO version/line and invoice line links persist. Adapter currently sums all retained match lines. | **IMPLEMENTABLE WITH EXISTING SOURCE CONTRACT**, subject to source-owner confirmation of current match and cutoff. |
| `inventory_quantity_value` | Posted transaction/reversal lineage exists; valuation pool is mutable and has no warehouse/unit or historical cutoff snapshot (U03–U06). | **SOURCE CONTRACT REMEDIATION REQUIRED**. |
| `claim_settlement` | Claim correction/revision/status and active/reversed allocation links persist. | **IMPLEMENTABLE WITH EXISTING SOURCE CONTRACT**, subject to historical cutoff and correction tests. |
| `project_cost_sources` | Fact persists source ID/version/occurrence and contract FK, but producer contract lacks project and event pairing is ambiguous (U10–U11). | **SOURCE CONTRACT REMEDIATION REQUIRED**. |
| `payroll_financial_handoffs` | Proposal has finalized run FK, family/currency/source digest and predecessor; acknowledgement pins proposal/source digest. | **IMPLEMENTABLE WITH EXISTING SOURCE CONTRACT**, subject to correction/currentness and acknowledgement scope tests. |
| `fixed_asset_handoffs` | Envelope has exact asset source, consumer, occurrence key, status and `supersedes`; adapter currently includes superseded envelopes. | **IMPLEMENTABLE WITH EXISTING SOURCE CONTRACT**, subject to source-owner currentness and consumer-reference tests. |
| `contractor_compliance` | Approved D08 keeps the right side unactivated. | **SOURCE CONTRACT REMEDIATION REQUIRED before two-sided activation**; present gated output remains valid. |

## K. Exact proposed schema/migration impact (conditional design)

**Recommended impact: `SCHEMA + DATA-MIGRATION`**, replacing canonical `NONE` only after explicit package reauthorization. This is the minimum credible classification for the proposed prospective evidence plus deterministic legacy provenance marking; it does **not** authorize a production migration. Exact model names, field types, and migration order require D02–D07 approval and migration review.

| Owner | Proposed schema object/change | Constraints/indexes and write contract |
| --- | --- | --- |
| Subledgers | Immutable account slice child of `SubledgerReconciliationRun`; immutable obligation/journal-line membership/version evidence; prospective grain-local revision/predecessor or a narrower one-account run field if D03 proves that cardinality. | Tenant-scoped FK `PROTECT`; unique `(run, account)` and `(tenant, direction, as_of, account, revision)`; no duplicate included source; conservation/hash/tenant/account mapping validated atomically. |
| Treasury | Immutable Treasury–GL slice child with currency/stable source identity; immutable movement/leg/journal-line membership/version evidence; grain-local revision/predecessor. | Unique `(run, currency, source_identity)` and `(tenant, cutoff, currency, source_identity, revision)`; membership uniqueness and posted/source-version checks; indexed current lookup. |
| Treasury bank | Prospective grain-local revision and predecessor on run, plus exact statement/clearing membership pin if D07 requires it; append-only invalidation evidence if D05 requires it. | Unique `(tenant, account, statement_import, as_of, revision)`; one successor per predecessor; exact source FK/version/hash checks. |
| Payroll statutory | Reuse one-to-one output and existing revision/schema/digest; add only a source-owned invalidation/currentness record if D05/D07 show an actual gap. | Preserve one reconciliation per output and immutable source links; no speculative status field. |
| Each affected native owner | Explicit provenance/completion/invalidation evidence for prospective runs; legacy marker on old rows or a sidecar provenance record. | No mutable financial totals or historical overwrite; eligible current selection must be indexed and tenant-scoped. |
| Reporting | No financial-identity ownership. Adapter/query and snapshot lineage fields may use existing JSON columns if exact source references fit the approved P10 contract. | No Reporting schema proposed merely to copy missing identity. |

**Forward migration:** expand nullable fields/tables; deploy writer that transactionally creates typed source evidence; validate constraints and source scope; mark existing runs `legacy_unverified` via a narrow data migration (classification only); switch reads after verified new evidence; retain legacy reads as historical/unverifiable. Do not set non-null on legacy-unknown identity fields. **Reverse migration:** code rollback can stop new writes and restore prior read path while retaining new evidence; dropping evidence tables/columns would destroy accepted history and must not be an automatic reverse operation. **Rehearsal:** representative tenant volumes, mixed currencies, multiple accounts, same-grain concurrent retries, duplicate/invalid source membership, interrupted migration, checksum/reconciliation, lock duration and rollback/read-path behavior. No production migration or irreversible cutover is authorized.

## L. Acceptance Criteria and Definition of Done

The canonical CEP-006 prompt retains **16/16 AC** across IMB-0044/0048/0066. **Proposed AC change: NO**; the current-state, no-double-count, as-of/version, source authority and scalability outcomes remain. **Proposed scoped DoD change: YES, evidence/test supplement only** to cover source-domain schema invariants, forward/data migration, legacy unverifiable treatment, tenant/scope authorization, exact source-version lineage, concurrent same-grain revision allocation, no-write Reporting boundary, and rollback rehearsal. The semantic DoD outcome is unchanged. Required model/service/migration and focused regression tests expand accordingly. No criterion may be waived to keep migration `NONE`.

## M. Authorization impact — proposed canonical amendment, not applied

| Canonical field | Current CEP-006 | Proposed bounded amendment |
| --- | --- | --- |
| Migration Impact | `NONE` | `SCHEMA + DATA-MIGRATION` for source-owned exact evidence and nonfinancial legacy provenance marker; production execution separately gated. |
| Scope | Query/read-model correction, refresh scalability, GL/Audit list bounding. | Add only Subledger/Treasury native-run grain, source-version, eligibility and ordering evidence **needed by IMB-0044**; D02 may require separately scoped source-domain corrections. Keep IMB-0048/0066 outcomes unchanged. |
| AC | 16 unchanged | 16 unchanged proposed. |
| DoD | Source/read-model tests and regression; migration N/A. | Semantic outcome unchanged; add model/service/migration, tenant/invariant/concurrency, legacy/rollback evidence. |
| DAG | No prerequisite CEPs in original package. | **No silent change.** If separate remediation package is selected, explicit new dependency approval is needed. |
| Risk | `HIGH` | **Reassess; likely at least HIGH**, with schema, finance and migration exposure. Do not assert a new canonical rating before approval. |
| Financial authority | Accounting/source domains remain authoritative. | **NONE changed.** Reporting remains read/projection only. |
| Exclusions | No financial semantic change, retained-history deletion, deployment or Human Sign-off. | Also exclude guessed backfill, source posting/GL correction, new journal, arbitrary account mapping, universal grain, new consumer, and production migration/cutover. |

The original canonical prompt/design is sealed historical execution material; this packet does not edit it. The Human Decision Maker must approve an explicit amended package and migration boundary before any model/migration mutation. `AUTH-BATCH-002` serial queue authority is not automatically extended to a materially revised package.

## N. Recommended packaging and queue consequence

**Recommendation:** use a separately authorized, source-domain remediation CEP **if** D02–D07 confirm the proposed cross-domain schema additions. This keeps the existing CEP-006 read-model/scalability scope recognizable and makes the new migration/concurrency work independently reviewable. Governance does not yet establish that a separate CEP is mandatory; therefore **separate-CEP requirement: UTV pending Human packaging decision**. A single explicitly reauthorized CEP-006 is possible only with a bounded canonical amendment to scope, migration, tests and evidence. No implementation route can preserve the old `Migration Impact = NONE` while requiring the proposed schema.

The available consolidated CEP package archive lists `packages/CEP-001.md` through `packages/CEP-086.md` (86 packages). `CEP-087` is only the next numeric **candidate** in that archive, not an assigned or authorized ID; verify any newer canonical register before allocation. If a separate remediation CEP is approved, its completion becomes an explicit prerequisite to resuming CEP-006 and requires a Human-approved DAG/queue amendment. CEP-009, CEP-011 and CEP-013 remain **NOT STARTED** under the stopped AUTH-BATCH-002 queue. No automatic activation, new queue membership or branch is implied.

## O. Human decisions still required

1. **D02:** resolve U01–U06/U10–U11 and decide which source-owned gaps belong in this remediation.
2. **D03:** approve control-account mapping and one-account versus multi-account run cardinality, including per-account totals and source membership.
3. **D04:** define Treasury–GL stable source identity, currency scope, included movement/journal set and per-slice totals.
4. **D05:** approve eligible completion, mismatch, invalidation and review semantics separately for each native pair.
5. **D06:** approve same-grain repeat policy and total revision/predecessor ordering, with legacy behavior.
6. **D07:** approve exact source ID/version/line/review/hash pins and treatment of unverifiable historical runs.
7. **Packaging/authorization:** choose amended CEP-006 or a separately authorized remediation package, approve exact migration scope, required tests/evidence and any DAG/queue change; separately authorize production migration if ever needed.

## P. Exact resume conditions

Keep CEP-006 **EXECUTION PARTIAL** and AUTH-BATCH-002 **STOPPED** until D02–D07 and packaging are approved, the canonical package/authorization explicitly covers any required source-domain schema and data migration, historical provenance rules are accepted, and an actual execution touch set and migration plan are verified against the then-current `main` tree. Only after bounded implementation, focused tests, required regression, migration-drift and rehearsal evidence, and a truthful **EXECUTION COMPLETE** report may the existing queue rule consider CEP-009. Nothing in this packet starts CEP-009, CEP-011 or CEP-013.
