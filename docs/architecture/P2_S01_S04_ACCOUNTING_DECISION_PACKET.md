# P2-S01–S04 Accounting Policy and ADR Decision Packet

**Prepared:** 2026-09-30  
**Status:** D2-01 THROUGH D2-08 ACCEPTED; P2-S02–S34 COMPLETE  
**Authority:** On 2026-09-30 the Product Owner accepted the successful P1 result
and requested that P2 start. This closes P1-S28 and authorizes this bounded P2
entry/decision session. It does not supply the accounting choices below, certify
Iranian accounting or tax rules. The accepted decisions authorized the bounded
P2-S05–S22 implementation recorded in section 4.

## 1. Bounded session contract

| Item | Contract |
| --- | --- |
| Goal | Revalidate the accepted native-accounting boundary and obtain the minimum product decisions required for the P2.1 ledger, fiscal-period and posting-registry design. |
| Included | Native-book scope; chart of accounts and dimensions; fiscal-period model; IRR/precision activation boundary; opening balances; close/reopen authority; accounting sign-off and first posting producer. |
| Excluded | Models, migrations, permissions, UI, journal posting, statutory values, autonomous filing, FX, Treasury/AP/AR, inventory valuation, historical-journal fabrication and production certification. |
| Direct evidence | `ADR_P0_S04_ACCOUNTING_POSTING.md`; P0-D02; P1-S14 Q01/Q02 decisions; current `Payment`, Billing settlement and `financials` projection boundaries; P1 authorization/configuration foundations. |
| Stop condition | Satisfied on 2026-09-30 by D2-01 through D2-08 = A. P2 foundation may proceed while unset precision/rounding values remain inactive and fail-closed. |

The Product Owner's statement that P0 and P1 went well is recorded as acceptance
of the completed P1 evidence and permission to enter P2. It does not fabricate
still-unsupplied P0.2/P0.3 release parameters such as provider/residency, numeric
RPO/RTO or plan limits. Those gates retain their existing owners and continue to
govern only their affected rollout and production behavior.

## 2. Preserved decisions and invariants

The following are already decided and are not reopened by this packet:

- Accounting is the sole native general-ledger authority; operational domains own
  their source documents, Treasury owns cash, and AP/AR owns obligations and
  settlement allocations.
- Posted journals are balanced and immutable. Corrections use linked reversal and
  replacement; finalized history is never silently edited or deleted.
- Posting is service-driven, transactional and idempotent, never signal-driven.
  Source identity/version, event identity and the applied rule version are pinned.
- Every record and relationship is Tenant-scoped. Permission, membership, Tenant
  status, object scope and separation rules are rechecked inside the transaction.
- Initial monetary support and canonical monetary display are IRR. Toman and FX
  behavior are absent; unsupported cross-currency operations fail closed.
- Dates persist with ISO/Gregorian-compatible semantics and timezone-aware UTC
  instants; the Persian UI presents Jalali dates. Fiscal configuration is explicit
  and effective-dated and never rewrites historical meaning.
- Existing `Payment` and `financials` records remain compatibility evidence and
  projections. They are not a ledger and are not converted into authoritative
  historical journals without an accepted migration/opening contract.

## 3. Product Owner decisions

Select one option for every decision. The recommended coherent bundle is
`D2-01=A, D2-02=A, D2-03=A, D2-04=A, D2-05=A, D2-06=A, D2-07=A, D2-08=A`.

### D2-01 — Initial native-book scope

| Option | Consequence |
| --- | --- |
| **A — Core GL first (recommended)** | Deliver COA/dimensions, fiscal controls, manual/opening journals, immutable posting and reversal first. Treasury, AP/AR, inventory valuation and producer integrations remain later packages. |
| B — Core GL plus one producer immediately | Adds a named operational producer to P2.1 and requires its complete recognition, reconciliation and correction contract before ledger acceptance. |
| C — External books only | Reopens approved P0-D02 and requires a replacement authority/integration decision; P2 native-ledger work stops. |

**Decision:** **D2-01 = A — ACCEPTED.** Accounting is the authoritative native
ledger owner; operational domains retain their source facts. P2.1 starts with
manual/opening sources only and no operational producer.

### D2-02 — Chart of accounts and dimensions

| Option | Consequence |
| --- | --- |
| **A — Tenant-local versioned COA with separate dimensions (recommended)** | Tenant owns hierarchical account codes under platform-closed account types. Project, site, phase, CBS/cost center, party and other approved dimensions remain separate validated references/snapshots rather than account-code segments. |
| B — Platform template copied to each Tenant | Faster setup, but still requires Tenant-local ownership, controlled versioning and no forced shared identity after copy. |
| C — Segmented account string | Encodes dimensions in account numbers and increases migration, validation and reporting coupling. |

For A/B, confirm whether account-code reuse after archival is forbidden
(recommended: **forbidden**) and whether posting accounts must be leaf accounts
(recommended: **yes**).

**Decision:** **D2-02 = A — ACCEPTED.** Account-code reuse after archival is
forbidden and posting is limited to active leaf/posting accounts. Project, Site,
WBS and BusinessParty are independent validated dimensions; CBS/Cost Center remain
owned by the later Project Controls package and must not be encoded in account codes.

### D2-03 — Fiscal-year and period structure

| Option | Consequence |
| --- | --- |
| **A — Configured non-overlapping periods (recommended)** | Each Tenant creates an explicit fiscal year and ordered, non-overlapping periods from its effective calendar configuration. No statutory start date or number of periods is hardcoded. |
| B — Fixed 12 monthly periods | Simpler, but invents a universal operating/statutory calendar and makes adjustment periods difficult. |
| C — Free-form dates without year/period authority | Insufficient close, numbering and statement control; not recommended. |

For A, confirm whether an optional separately closed adjustment period is allowed
(recommended: **yes, only when explicitly configured**).

**Decision:** **D2-03 = A — ACCEPTED.** Explicit non-overlapping periods and an
optional explicitly configured adjustment period are allowed. Used fiscal dates
and finalized history are immutable against later configuration changes.

### D2-04 — Monetary precision activation

| Option | Consequence |
| --- | --- |
| **A — Versioned policy required before posting (recommended)** | Schema and setup may proceed, but posting remains unavailable until an effective platform-allowed/Tenant-selected money precision and rounding policy is configured. No value is inferred. |
| B — Product Owner supplies exact initial values now | Requires the method, money scale, intermediate scale and all rounding points, with the authoritative policy/source record where provenance is required. |
| C — Implicit database/default rounding | Rejected because it creates unversioned accounting behavior. |

**Decision:** **D2-04 = A — ACCEPTED.** The versioned mechanism may be implemented
without values; submission/posting remains inactive and fail-closed until both
effective precision and rounding policy versions exist. This is not a global
development blocker and no default method, scale or rounding point is invented.

### D2-05 — Opening-balance strategy

| Option | Consequence |
| --- | --- |
| **A — Controlled cutoff opening journal (recommended)** | Per Tenant, import/review a balanced opening journal by account, currency and applicable dimensions at an approved cutoff, retain source evidence and reconcile it to legacy facts without historical replay. |
| B — Validated historical replay | Post only individually proven source events and versions; higher effort and missing legacy evidence becomes a blocking exception. |
| C — Hybrid by source class | Requires explicit disjoint coverage and reconciliation proving that no event appears in both opening balances and replay. |

**Decision:** **D2-05 = A — ACCEPTED.** Opening journals require cutoff, evidence
and reconciliation provenance. No historical journal detail is fabricated.

### D2-06 — Close, reopen and late corrections

| Option | Consequence |
| --- | --- |
| **A — Protected close/reopen (recommended)** | Close and reopen are distinct protected operations with dedicated permissions, reason, immutable evidence and maker/checker separation. Posting and close lock the same period authority. Late corrections require an authorized reopen or a later open-period adjustment under a separately configured policy. |
| B — Close protected, reopen Platform-only | Stronger central control but creates operational dependency and does not itself supply accounting review. |
| C — Tenant Admin may freely reopen | Rejected because role alone cannot bypass protected-operation separation or evidence. |

**Decision:** **D2-06 = A — ACCEPTED.** Journal posting/opening acceptance and
period close/reopen are Protected Operations with explicit permission, reason,
separation and immutable audit evidence.

### D2-07 — Accounting review/sign-off

| Option | Consequence |
| --- | --- |
| **A — Permission-based independent reviewer (recommended)** | COA activation, opening acceptance and period close require an active Tenant member with the dedicated approval permission who did not prepare the same artifact. A job title/position does not grant authority. Missing reviewer leaves the action pending. |
| B — Tenant Owner may approve alone | Conflicts with the protected-operation separation baseline unless a separately accepted control exception changes that policy. |
| C — External professional required for every action | Adds a global role/dependency previously rejected; professional evidence may instead attach to exact policy versions where obtained or legally required. |

**Decision:** **D2-07 = A — ACCEPTED.** Authorization is membership/permission
based, never job-title based. The same preparer cannot approve the protected
record; no mandatory Accountant or Finance Manager position is introduced.

### D2-08 — First producer and execution mode

| Option | Consequence |
| --- | --- |
| **A — Manual/opening sources only in P2.1 (recommended)** | Establish and reconcile the kernel before integrating a business producer. Posting remains synchronous and atomic; no queue/outbox is introduced. |
| B — Approved progress-claim recognition pilot | Requires a separate recognition-policy, party/contract, AP/AR, reversal and reconciliation contract; current claim settlement alone is insufficient. |
| C — Existing Payment pilot | Requires P3 Treasury ownership, currency/bank/cutoff evidence and containment mapping; `Payment` cannot be relabeled as a journal source by assumption. |

**Decision:** **D2-08 = A — ACCEPTED.** P2.1 uses synchronous atomic services for
manual/opening sources. No Outbox, Celery or operational-domain producer is added.

## 4. Decision effect and next sessions

P2-S02 through P2-S04 validated the detailed COA/dimension, fiscal/numbering,
posting/close and opening contracts against the accepted bundle without conflict.
P2-S05 through P2-S12 now complete the bounded ledger/schema and opening-data
slice: Tenant-scoped leaf accounts, immutable fiscal dates, locked organization
numbering, balanced immutable posted journals, account/dimension snapshots,
code-owned manual/opening/reversal/replacement contracts, durable source/version/
event identity, payload conflict detection and synchronous idempotent posting.
Correction is a linked posted reversal followed, when needed, by a linked
replacement; neither rewrites the original.

The opening-balance import is a reviewable draft/proposed/accepted aggregate with
an approved cutoff, retained source/evidence/reconciliation references and exact
line transfer into one opening journal. It does not synthesize historical events.
Permission, active membership, Tenant scope, reason, audit evidence and maker/
checker separation protect posting, reversal, opening acceptance and period
close/reopen. PostgreSQL tests cover concurrent identical posting, duplicate
identity/payload conflicts, closed periods, Tenant/permission denials, reversals,
replacements and openings; forward migration `accounting.0002` backfills existing
foundation identities and posted snapshots.

The Product Owner's continuation pulled the kernel registry/reversal subset
forward from the earlier P2-S13–S22 grouping. Later producer registration,
operational source adapters, UI, statements and broad close/reconciliation work
remain open. CBS/Cost Center still belongs to Project Controls. Missing precision/
rounding selections still fail closed and do not block further development.

P2-S13 recalibrated the remaining S13–S22 sequence so no operational producer is
implicitly authorized. Registry entries now state Accounting ownership and exact
source/source-line models; every journal line retains a source-line UUID, with
opening-import lines and reversal origins transferred explicitly. A synchronous,
read-only, permission-checked preflight reconciles only manual/opening and their
Accounting-owned correction journals through a cutoff and exposes pending facts,
balanced posted totals and named lineage exceptions. S14-S18 then add immutable
idempotent retained runs, detailed source tie-outs and one controlled disposition
per exception. S19 adds one protected independent sign-off after verifying retained
hash/audit evidence and requiring every exception disposition; the reviewer must
differ from the run creator and every disposer. S20-S21 prove Tenant isolation,
authorization/SoD, concurrent idempotency, cutoff stability, tamper detection and
fail-closed behavior on PostgreSQL. S22 closes the documents without selecting an
operational producer. None of these actions changes a journal or balance.

## 5. Binding implementation exclusions

The existing multi-role and Tenant-isolation model remains authoritative. No tax,
insurance, statutory filing, inventory valuation, FX accounting, Outbox, Celery,
Treasury/AP/AR behavior or operational producer is authorized by these decisions.

