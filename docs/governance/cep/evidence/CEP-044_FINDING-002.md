# CEP-044-FINDING-002 — financial write-off correction contract

**HISTORICAL BLOCKER-SPEC — RESOLVED by HUMAN-CEP044-CORRECTION-20261019.**
The prior finding/proposal and partial result below are retained. The governing
Human clarifications, rather than any inference from the proposal, control the
resumed implementation. See [Correction provenance](CEP-044_CORRECTION_PROVENANCE.json).

## Exact unresolved Human decision

The persistence authorization resolves Finding001 and permits an immutable source
predecessor link. It explicitly does **not** select new financial correction
semantics. Before implementing approval of a corrected write-off, the source
contract must determine whether the old approved effect is fully reversed and
replaced, or adjusted, and whether reversal and replacement approval share one
atomic effective-date boundary. Those alternatives change outstanding balances,
failure outcomes and historical/as-of results; they are not equivalent technical
implementation choices.

Human decision HUMAN-CEP044-PERSISTENCE-20261019 item 8 requires a stop before
implementing a material lifecycle/recognition/settlement/correction rule absent
from canonical sources. No monetary transition has been implemented under an
inferred answer.

## Approved sources and limits

[Semantic review](CEP-044_SEMANTIC_REVIEW.json) retains hashes and excerpts. The
local prompt's Scope/AC/DoD, frozen PD-015/030, recovered SPEC-024 and recognition
matrix were reviewed, including the approved recovery archive identities. Further
inspection of local accepted P3 policy packets and recovered write-off journeys
was performed before declaring this gap.

- PD-015 and SPEC-024 require an auditable write-off, approval, exact source
  identity, retained history and a new governed correction/reversal occurrence.
  They do not specify the financial correction sequence or commit/date boundary.
- SPEC-002 assigns write-off and reversal/correction recognition to Subledgers,
  with **L2 Accounting drafts**. Accounting remains GL authority. Older P3
  synchronous-posting wording does not authorize bypassing the current matrix.
- Accepted P3-S27-Q03 A-Revised already defines explicit scoped approval/reversal
  permissions, no default grants, versioned Platform/Tenant Self-Approval policy,
  independence only where that policy requires it, no implicit Protected
  classification and no thresholds. Those settled rules are **not** being
  reopened or reported as missing approval-depth policy.
- The P3 implementation contract defines effective-date as-of behavior: exclude
  future facts, restore amounts from a reversal's effective date, preserve older
  retained snapshots. It defines standalone reversal evidence, reasons and
  authorization, but not the correction's coupled replacement boundary.
- P3 Q01 specifies a Billing/source-obligation correction sequence. It does not
  define correction of an approved AP/AR write-off; applying it by analogy would
  infer another financial source contract.
- Recovered E2E-SUB-011/012/013 review rows identify the held target and PD-015
  disposition; they do not supply the missing financial transition contract.

No repository-local source, recovered write-off specification or inspected
approved decision supplies that exact rule. Source absence is not inferred from
a single search. The new predecessor FK is structural provenance; it does not
decide eligibility or enable correction of an approved or rejected record.

## Concrete minimum contract proposed for Human approval

This is a proposal only, **not implemented or activated**:

1. Correct an approved write-off by **full reversal and replacement**, never an
   inferred delta or destructive edit. The replacement pins the exact prior
   decision and the same tenant, obligation and source/version lineage.
2. Keep the original financial effect while a replacement is pending. On
   successful replacement approval, commit the original reversal and replacement
   approval **atomically**, enforcing the existing explicit approval and reversal
   permissions/object scope and applicable versioned Self-Approval rules for
   both actions. A failed correction leaves both original and replacement effects
   unchanged and retains safe failure/retry evidence.
3. Use **one explicit correction effective date** for reversal and replacement,
   no earlier than the prior write-off's effective date. Preserve earlier as-of
   results; require the existing applicable open Accounting boundary whenever a
   GL effect is involved. Actual account mappings and recognition remain under
   SPEC-002; this proposal creates no posting rule or Treasury effect.
4. A rejected/unapproved replacement has no financial effect. This proposal does
   not enable a new cancellation path, threshold, approval depth or default
   permission grant. Any further material rule absent from approved sources
   remains a stop condition.

Required resolution: explicitly approve this bounded contract, or provide the
authoritative alternative. The migration authority remains valid; no new Scope,
AC, DoD, dependency, financial owner or production decision is requested.

## Safe work completed and held work

`WriteOffProposal.corrects` is a nullable protected FK to a retained decision.
Existing data remains NULL without inferred historical pairing. Structural
validation rejects a foreign tenant, a different obligation, a foreign actor or
self-reference. Existing instance immutability is preserved; queryset mutation,
bulk bypass and deletion of retained source links are blocked. This adds no
business permission, grant, workflow default, policy value, source adapter,
approval/reversal activation, recognition writer, UI or settlement behavior.

The additive migration refuses rollback once a correction link exists, so
retained lineage requires forward recovery. The populated disposable rehearsal
checks obligations, proposals, approved/rejected decisions, reversal history,
audit and grants. The separately authorized configured Development migration
checks fingerprints of every pre-existing managed table and creates no source
links. Detailed outcomes are in the current Completion Report/evidence manifest.

The initial focused test failure came from inherited `bulk_update()` marking its
transaction for rollback after the immutable update guard raised. An explicit
early `bulk_update()` guard fixed it; focused tests pass. This was a corrected
new-test/implementation failure, not baseline debt. Existing unrelated fixture
debt and UTV are preserved.

Full CEP-044 AC and scoped DoD are incomplete. Required new financial/workflow/
recognition/reconciliation validation remains blocked, not deferred as a PASS.
GATE-05 stays NOT_PASSED. Serial continuation and completed-work Git checkpoints
remain stopped on this unresolved financial contract; no production action,
Human Sign-off or certification occurred.
