# CEP-043-FINDING-002 — missing enrollment and Payroll AP reversal lifecycle

**HISTORICAL BLOCKER-SPEC — RESOLVED by HUMAN-CEP043-LIFECYCLE-20261018.**
The Human approved A/B with governing clarifications, retained in
`../supporting/CEP-043_PAYROLL_AP_LIFECYCLE_POLICY.md`. Original blocked-entry
facts and proposals below are historical. Implementation resumes under the
existing bounded migration authorization; no new production or Git authority.

HUMAN-CEP043-PERSISTENCE-20261018 resolves Finding001's migration restriction.
The migration-only amendment is verified. Its item 7 requires stopping before
implementing a material lifecycle, transition, financial or ownership rule absent
from canonical sources. This finding identifies those rules; it does not reopen
the persistence authorization or require actual tenant mappings to build.

## Established contract

- PD-009/030: Payroll owns calculation/economic evidence; downstream authorities
  remain distinct; no duplicate recognition or unspecified posting.
- SPEC-029 / Financial Source Contract Completion / IMB-0061: finalized Payroll
  liability evidence, explicitly enrolled family, run/version plus liability
  occurrence/classification, target-owned L2 AP outcome, idempotency, retained
  corrections/reversals and reconciliation.
- INT-B07 detailed contract: AP Obligation draft, AP ownership, liability source
  classification, party/payee model and due-date/payment-grouping policy.
- Accepted P7-S29–S32: Payroll prepares/reviews source proposals only. It grants
  no cross-domain approval. Source corrections/reversals/replacements retain
  same-family predecessor lineage; observation records do not repair targets.
- Current AP supplier-source reversal: explicit AP reverse permission; it rejects
  an already reversed target, linked recognition journal, active settlement or
  approved write-off, and checks the timing of undone settlement/write-off effects.
  That implementation is restricted to supplier invoice/match occurrences.

## Exact gaps that prevent product implementation

1. **Enrollment approval/currentness contract.** Canonical INT-B07 says a family
   must be approved/enrolled, but specifies no enrollment transition/approval
   authority, relation between Payroll proposal review and enrollment approval,
   or effective-version/supersession/revocation rule. Existing source prepare/
   review permissions authorize source proposals; Accounting mapping approval
   approves ledger assignments. Neither grants AP enrollment authority. Choosing
   either as enrollment approval, or inventing an activation/revocation lifecycle,
   would introduce business/security semantics. Merely adding an `approved`
   boolean or accepting an unresolvable approval reference does not establish them.

2. **Payroll-specific AP reversal/correction contract.** Canonical INT-B07
   requires correction/reversal, but does not bind a finalized Payroll reversal/
   replacement to an AP target transition, define whether/how the existing
   supplier-only unconsumed-target guards apply, or define handling of already
   recognized/settled/written-off targets and correction effective dates. Payroll
   `reverse_run` finalizes an inverse run and marks the original REVERSED without
   AP coordination. A new AP reversal row must have an approved economic meaning
   in open-item/settlement/aging readers. Copying supplier rules, cancelling
   liabilities despite downstream consumption, allowing interim duplicate open
   items or inferring an adjustment/write-off is not authorized by persistence
   permission alone.

These gaps affect AC1/2 (approved source/target contract), AC4 (safe retry), AC5
(authority) and AC6 (correction/reversal/reconciliation). AC3 cannot close without
the corresponding approved occurrence/effect identity. All six remain BLOCKED;
DoD NOT MET. No speculative schema, service, permission, migration or product test
has been written. Migration/drift/preservation/concurrency tests of a new schema
are NOT EXECUTED because that implementation has not been authorized semantically.

## Specific Human decisions requested

The following is a concrete **proposal for approval, not an implemented policy**:

**A — Enrollment contract.** Payroll proposal review remains source approval
only. AP owns a separate explicit enrollment preparation/approval capability,
default-denied and enforced through the existing permission system. A prepared
immutable version is inactive until explicitly approved by an authorized AP
actor; no additional person-level separation is introduced beyond applicable
existing protected-operation policy. Each enrollment pins an exact liability
classification/source scope and explicit source-to-AP party/payee, recognition/
due-date and payment-grouping evidence; no inferred payee, dates, aggregation or
family. New approved versions apply prospectively; historical targets keep their
original pin. Withdrawal prevents future handoffs and does not erase or alter
existing obligations. Actual eligible families/tenant values remain EXT-0013
activation inputs and are not seeded by CEP-043.

**B — AP reversal/correction contract.** Extend the existing AP source-reversal
safety policy specifically to Payroll: an explicitly reviewed finalized Payroll
reversal occurrence may reverse only its retained predecessor AP effect, with
exact inverse source amount/currency and explicit effective date/reason. Require
the existing AP source-reverse authority and retain source/effect/reversal pins.
Do not reverse a target with a recognition journal, active settlement or active
write-off; retain failure/retry evidence and leave remediation to those owning
domains. Only after independently governed effects are undone may retry proceed,
and never before their reversal effective dates. A replacement must follow the
retained Payroll reversal/replacement lineage; reverse the eligible predecessor
and create the approved replacement target atomically, with no interval of
duplicate active payables. Missing or unsupported cases fail closed, with no
negative payable, cash reversal, inferred write-off or duplicate GL recognition.

Approval or an authoritative replacement for **A and B** is required before
implementing those rules. A Human decision must also resolve any inconsistency
found in these proposed policies; they are not added to the canonical prompt by
the migration-only amendment. Ordinary field/index/locking/test choices require
no Human decision once these material contracts are established.

## Evidence and queue

`CEP-043_SEMANTIC_REVIEW.json` retains exact authoritative passages/member hashes,
repository file/function locations and comparison results. It distinguishes the
missing executable contract from absent actual mapping values. The latter are
activation-only and are not used to block framework construction.

GATE-05 remains NOT_PASSED and does not cause this build stop. Finding001's
migration restriction is resolved; this is a new, specific semantic stop under
the Human decision. Serial queue stopped before product mutation. Independent
candidates remain unreviewed. Existing baseline debt/UTV remain unchanged; no
Git writes or production action.
