# P3-S23–S27 AP/AR Activation Decision Packet

**Status:** Q01 = A, Q02 = A with Treasury-clearing clarification,
Q03 = A-Revised, and Q04 = A accepted by the Product Owner on 2026-10-01.
These decisions close the product-policy questions only; they do not authorize
implementation or activation.

**Date:** 2026-10-01

**Subsequent reconciliation (2026-10-03):** authorized P6-S07–S13 now stores an
explicit claim due date from pinned contract `payment_due_days` and registers
`billing.progress_claim.v1` for separately permissioned AR recognition. Approval
does not recognize AR. Because obligation/journal reversal orchestration remains
deferred, claims with recognized AR fail closed for correction. AP, automatic
recognition, posting production, write-offs and production activation remain
closed. The decision narrative below is retained as historical gate evidence.

This packet resolves only the four bounded gates retained by the accepted
[P3-S23–S27 implementation contract](P3_S23_S27_IMPLEMENTATION_CONTRACT.md).
It does not change application code, register an AP/AR source or Accounting
producer, activate write-offs, or authorize P3-S28+.

## Accepted decision summary

| Gate | Accepted disposition | Effect |
| --- | --- | --- |
| Q01 | **A — staged AR activation; AP remains closed** | Makes one immutable approved progress-claim revision eligible only after Billing supplies the missing due-date and post-approval correction facts. |
| Q02 | **A — explicit directional event kinds and configured account roles, clarified** | Settlement mappings use the exact Treasury-created directional clearing roles; Subledgers never select or mutate cash-account postings. |
| Q03 | **A-Revised — policy-governed Self-Approval/SoD, no threshold and no approval/reversal default grants** | Uses the accepted Platform/Tenant Self-Approval policy without implicitly classifying write-off or reversal as Protected Operations. |
| Q04 | **A — retain exact unbucketed aging** | Closes the optional bucket decision for now without inventing boundaries. |

Q01–Q03 remain fail-closed until the accepted choices are separately authorized,
implemented and pass the existing activation evidence gates.

## Q01 — Eligible sources and recognition semantics

### Decision closed

The decision selects the authoritative AP and AR source records and, for each, the immutable
source version/status, recognition date, amount, due date, party/tax snapshot,
and post-recognition correction/reversal behavior. The current approved
`ProgressClaim` has an immutable approved revision and amount but no dedicated
due-date or party/currency snapshot fields; there is no approved native supplier
invoice or payable-certificate source.

### Options

| Option | Complete product choice | Consequences |
| --- | --- | --- |
| **A — Staged AR activation; AP remains closed (accepted)** | The only first eligible source is an **approved `ProgressClaim` revision**. Its UUID plus revision number is the source identity/version; recognition date is the Tenant-local date of `approved_at`; amount is the immutable approved net total; party, tax/adjustment basis and currency are copied from an immutable claim/contract snapshot; due date must be a new explicit immutable claim term and may not be inferred. An approved claim is never edited. A correction is a linked approved corrective revision: reverse the affected settlement/write-off evidence first, reverse the original recognition journal/obligation, then recognize the replacement (or an explicitly linked delta if later approved as a distinct source rule). No AP source is eligible until a native approved supplier invoice/certificate provides the same facts. | Requires a bounded Billing/source-contract change before registering the AR adapter. Recognition stays blocked when any required snapshot is absent. AP remains blocked. Accounting reversal and replacement retain exact lineage. Authorization continues through `subledgers.obligations_recognize`; source approval does not itself grant posting authority. |
| B — Activate AR and AP together later | Register nothing until both the receivable claim and a native supplier invoice/certificate expose complete immutable terms and correction contracts; then activate both in one release. | Lowest semantic asymmetry and one acceptance exercise, but delays usable AR aging and collections. No immediate Accounting or permission change. |
| C — Permit manually entered AP/AR obligations | Treat an authorized manual entry plus attachments as the source; the operator supplies recognition date, amount, due date, party and tax facts. Corrections use reversal/re-entry. | Faster coverage but introduces a second financial fact authority, weakens exact source lineage, and duplicates Billing/Procurement ownership. It would need new maker/checker permissions and evidence rules. Not recommended. |

**Decision:** **Q01 = A — accepted.** It delivers value from the only credible current
candidate without fabricating an AP invoice model or allowing manual records to
become a competing source of truth. It also keeps missing due dates visible and
fail-closed instead of deriving them from approval, period end, or contract end.

**Still deferred:** the AP invoice/certificate domain and its recognition policy;
grace-day policy; credit notes, debit notes and tax/legal
treatment; legacy `Payment`/`ClaimSettlementAllocation` backfill or cutover;
production activation; and any source other than the explicitly accepted adapter.

## Q02 — Accounting event kinds and posting mappings

### Decision closed

The decision selects the registered Accounting business-event vocabulary and the configured
debit/credit account roles for obligation recognition, Treasury settlement,
write-off and reversal. The decision must preserve Accounting as journal owner,
Treasury as cash-movement owner and AP/AR as obligation/allocation owner.

### Options

| Option | Complete product choice | Consequences |
| --- | --- | --- |
| **A — Explicit directional events and configured roles (accepted)** | Register `subledgers` events `receivable_recognized`, `payable_recognized`, `receivable_settled`, `payable_settled`, `receivable_written_off`, and `payable_written_off`. Use the existing Accounting reversal event against the exact original journal for every reversal. Mappings are versioned and source-specific: AR recognition debits receivables control and credits the configured source-recognition role; AP recognition debits the configured source cost/asset/clearing role and credits payables control; AR settlement debits the **exact unapplied-receipt/settlement-clearing role created by the Treasury posting contract**, never a Treasury cash/bank account, and credits receivables control; AP settlement applies the equivalent direction-specific Treasury outgoing-clearing semantics, debiting payables control and crediting the exact clearing role; AR/AP write-off uses direction-specific configured write-off roles. Subledgers never select or mutate cash-account postings. | Adds registered producer contracts and mapping validation. Posting remains synchronous and atomic, with exact occurrence IDs and one journal per business event. Missing/open-period-invalid mappings fail closed. Actual chart accounts remain Tenant configuration, not product constants. Write-off events require the accepted Q03 policy to be implemented. |
| B — Generic events with direction in metadata | Register only `obligation_recognized`, `settlement_applied`, and `writeoff_approved`; determine debit/credit direction from payload metadata. Reversals still target the original journal. | Smaller registry, but direction becomes payload interpretation rather than a visible contract, increasing mapping and reconciliation ambiguity. |
| C — Manual journals linked after the fact | Do not register a producer; Accounting users post manual journals and later link them to AP/AR records. | Avoids producer work but breaks atomic recognition/settlement, weakens idempotency and permits subledger-to-GL timing gaps. Not recommended. |

**Decision:** **Q02 = A with the Treasury-clearing clarification — accepted.**
Directional event kinds make the financial occurrence
auditable and keep mapping validation deterministic while leaving every actual
account selection in effective Accounting configuration. Acceptance approves
the event and role contract, not any chart-of-accounts identifier.

**Still deferred:** actual Tenant account IDs; revenue/cost/asset recognition
policy per future source; tax postings; foreign currency; period-end accruals;
write-off posting until Q03 A-Revised is separately implemented; legacy journal linkage; and asynchronous
or external posting.

## Q03 — Write-off authority, permissions and separation

### Decision closed

The decision defines who may propose, approve and reverse an AP/AR write-off; which roles receive
the existing permissions by default; whether Self-Approval is ever allowed; and
whether authorization varies by amount or object scope. No monetary threshold is
currently approved.

### Options

| Option | Complete product choice | Consequences |
| --- | --- | --- |
| **A-Revised — Accepted Platform/Tenant policy governs Self-Approval/SoD (accepted)** | Keep `subledgers.writeoffs_propose` in the existing Accountant default set. Give `subledgers.writeoffs_approve` and `subledgers.writeoffs_reverse` **no default-role grant**; assign them explicitly through the existing authorization and object-scope model. The already accepted Platform/Tenant Self-Approval policy governs approval and reversal. Where applicable policy requires independent approval, proposer and approver must be different active authorized memberships. Self-Approval is absolutely prohibited only when the operation is explicitly classified as a Protected Operation under accepted platform policy; this decision does **not** classify write-off or reversal as Protected Operations. Introduce no monetary or cumulative threshold. Missing required authorization or Self-Approval configuration fails closed. | Approval and reversal services must evaluate the effective versioned policy and exact object scope inside the transaction. Every decision remains versioned and auditable and retains exact Accounting/subledger lineage. No role, position or source approval implies write-off authority. No numeric policy field or reversal-request schema is authorized by this decision. |
| B — Default senior-role approval | Accountant proposes; Owner/Admin receive approval and reversal by default; proposer and approver differ, but reversal is a single authorized action. No amount threshold. | Easier setup, but broad default grants expand financial authority and single-actor reversal provides weaker control. Role membership still cannot bypass object scope. |
| C — Threshold-based delegated authority | Permit Self-Approval or role-specific approval below an approved amount and require independent approval above it; apply equivalent bands to reversal. | Supports higher-volume operations but cannot be implemented until the Product Owner supplies exact amounts, inclusivity, currency/basis, aggregation window, object scope and fallback behavior. No values may be inferred. |

**Decision:** **Q03 = A-Revised — accepted.** It uses the permissions already
catalogued, preserves the accepted policy-owned distinction between Protected and
other business operations, and closes the product gate without inventing a number
or silently elevating write-off/reversal classification.

**Still deferred:** every monetary or cumulative threshold; automated/de-minimis
write-off; batch approval; tenant-authored approval formulas; legal/tax treatment;
collection or dispute policy; UI; and any default approval/reversal grant beyond
the selected option.

## Q04 — Aging buckets

### Decision closed

The decision determines whether product-defined bucketed reporting is materially required in this
activation. Exact per-item as-of aging already reports due date, days past due,
remaining amount and undated status; only grouping boundaries are unresolved.

### Options

| Option | Complete product choice | Consequences |
| --- | --- | --- |
| **A — No buckets in this activation (accepted)** | Retain exact per-item as-of aging, including a distinct undated population; sort/filter by exact due date or days past due. | No schema, financial-policy or migration change. Reports remain accurate without arbitrary bands. Bucket summaries/charts are unavailable. |
| B — One product-wide fixed scheme | Add a single versioned set of product-defined day boundaries plus an undated group. | Comparable reports across Tenants, but activation is blocked until the Product Owner supplies every exact inclusive/exclusive boundary and label. Existing runs must retain the scheme version. |
| C — Tenant-configurable versioned schemes | Let each Tenant select a published bucket scheme while retaining the exact underlying aging facts. | More flexible but adds configuration lifecycle, permissions, validation, historical version pinning and cross-Tenant comparability costs. Exact boundaries still require an approved initial scheme. |

**Decision:** **Q04 = A — accepted.** Bucket grouping is not required for correctness or
reconciliation, so the existing exact report should remain authoritative until a
demonstrated reporting need justifies policy boundaries.

**Still deferred:** bucket boundaries and labels; tenant-configurable schemes;
dashboard charts; collection prioritization, DSO and expected-credit-loss policy;
scheduled snapshots; UI; and background generation.

## Scope retained after disposition

These accepted decisions do not themselves authorize or perform implementation
or activation. Legacy cutover/backfill, production
rollout, UI, background processing, external integrations,
`MATERIAL_DOCUMENTS_LINK`, and P3-S28+ remain separate gates.
