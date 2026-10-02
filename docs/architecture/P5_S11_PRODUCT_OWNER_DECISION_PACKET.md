# P5-S11 Product Owner Decision Packet

**Status:** P5-S11-D01 through D04, including the comparison-input,
normalization-v1, evaluator, exception-v1, allocation, tie/no-award and
finalization decisions below, were Product Owner accepted on 2026-10-02. The
scoped P5-S11 sourcing-only award self-finalization rule explicitly supersedes
P5-D01 only as recorded below. The Product Owner authorized implementation on
2026-10-02. Clean disposable PostgreSQL verification, including migration
rollback/reapply and focused P5-S07–S11 regressions, completed on 2026-10-02.
The final focused acceptance run passed all dedicated S11 cases; the Product Owner
accepted P5-S11 as implemented and PostgreSQL-verified on 2026-10-02.
This record itself does not authorize
P5-S12+ behavior.

**Boundary:** P5-S11 may build on P5-S01–S10 custody, close-manifest, package
freeze, protected opening, confidential grant, commercial-admissibility, audit and
immutability evidence. It may not create a PO, contractual/financial fact,
Inventory/AP/Accounting/Treasury action, portal capability or downstream handoff.
Even the accepted sourcing-only award boundary requires a separately authorized
implementation after the detailed gates below are resolved.

## S11-D01 — Comparison and normalization basis

**Accepted decision:** Retain versioned asserted commercial inputs and use a
versioned, reproducible normalization policy. Original asserted/source values are
immutable. Every normalized value must be derived, traceable and reproducible from
the exact policy version and source revision; it must not silently alter quote or
source content. A final comparison may use only eligible, `ADMISSIBLE`, opened
revisions with retained evidence.

**Accepted detailed comparison inputs and normalization policy v1:** Comparison
v1 operates only on `ADMISSIBLE`, opened, frozen revisions applicable to the same
RFQ line or lot. Its authoritative asserted inputs are the RFQ line/lot identifier,
offered quantity, RFQ-defined asserted unit price and/or line amount, currency, and
an explicitly stated line/lot commercial discount. Delivery/commercial terms remain
evidence only, not numeric scoring inputs, unless separately governed.

Every asserted/source value remains unchanged. Policy v1 derives only deterministic
comparison amounts using the RFQ governing quantity/unit definition, and retains the
exact inputs, source revision, asserted value, policy version and calculation
lineage. It permits no FX conversion, tax/VAT normalization, escalation/indexation,
inferred discount, hidden unit conversion or source-value overwrite. If currency,
unit basis, quantity basis or a required asserted input is not deterministically
comparable, comparison fails closed for explicit review/policy. Comparison v1 adds
no other scoring, ranking or transformation rule.

## S11-D02 — Evaluator and conflict governance

**Accepted decision:** Use explicit evaluator appointments, scoped permissions,
retained conflict declarations and auditable finalization. Every evaluator action
is Tenant/object/revision scoped. An affected evaluator cannot clear their own
declared conflict. Preserve evaluator, conflict, recommendation and finalization
lineage. A business-operation self-approval is possible only when the existing
Tenant policy explicitly permits that exact operation; this never extends to
Protected, system or access operations.

**Accepted detailed evaluator, conflict, permission and finalization policy:** Use
explicit revision/comparison-scoped evaluator appointments. Retain and audit every
appointment and revocation. Separate permissions are required for comparison
preparation/evaluation, applicable exception approval, and comparison finalization.
Each appointed evaluator retains conflict status/evidence. A conflicted evaluator
cannot evaluate or finalize the affected comparison or self-clear their conflict;
an independently authorized actor decides the conflict disposition.

Self-finalization is disabled by default. The existing Tenant business-operation
self-approval policy may explicitly permit the same authorized user to prepare and
finalize a comparison for a small/single-user Tenant, with explicit audit. It never
applies to Protected, system or access operations, or to conflict self-clearance.
Only one governing finalized comparison version may be active; its evidence is
immutable and a correction is append-only through a superseding comparison.

## S11-D03 — Exception handling

**Accepted decision:** Use a closed, versioned catalogue of explicitly
non-material exceptions. Each exception needs retained evidence and independent
approval unless the Tenant policy explicitly permits self-approval for that exact
business operation. An exception can never permit late material quote changes,
replacement of frozen evidence, bypass of admissibility or silent alteration of
comparison inputs. Anything outside the approved catalogue fails closed.

**Accepted detailed exception catalogue v1 and lifecycle:** The closed, versioned
v1 catalogue is limited to `NON_MATERIAL_METADATA_OMISSION`,
`DISPLAY_FORMAT_VARIANCE`, `DUPLICATE_NON_GOVERNING_EVIDENCE`, and
`NON_MATERIAL_DOCUMENT_LABEL_VARIANCE`. Each entry has a stable code and
description, applicability rule, required retained evidence, explicit approval
requirement and versioned catalogue ownership. Its lifecycle is
`PROPOSED -> APPROVED / REJECTED / WITHDRAWN`; an approved exception is immutable
and correction requires supersession.

No exception can change frozen quote content/asserted commercial values, cure
inadmissibility, permit a late material change, or alter quantity, unit price,
currency, scope, delivery obligation or another material commercial term. Anything
outside catalogue v1 fails closed.

## S11-D04 — Award boundary and contract

**Accepted decision:** After a finalized comparison, S11 may record an immutable,
sourcing-only award decision. It must retain exact selected revision(s), applicable
quantities/allocations, comparison version, decision evidence, actors and approval
lineage. Correction is append-only and superseding, never in-place. An award cannot
create or modify a PO, contract, AP obligation, GL journal, Treasury/cash record,
budget fact or any other downstream domain object. Downstream handoff needs separate
later authorization. Existing P5-D01 remains controlling except for the explicit,
limited P5-S11 sourcing-only award self-finalization supersession below.

**Accepted detailed quantity and allocation policy:** Support single-award and
multi-award sourcing decisions. Every award quantity/allocation is explicit,
non-negative and conserved against the approved sourcing requirement;
over-allocation is prohibited. A partial award is valid only when explicitly
represented and its unawarded remainder is retained. A finalized allocation changes
only through a superseding award, never in place.

**Accepted detailed tie and no-award policy:** Ties are never automatically broken.
An unresolved tie is retained as `TIE_REVIEW_REQUIRED`. `NO_AWARD` is an explicit
outcome with retained reason/evidence. Tie resolution and no-award decisions are
auditable and cannot silently alter evaluation or comparison results.

**Accepted detailed award-finalization and correction policy:** A finalized award
is immutable and retains the finalized comparison version, selected revision(s),
quantities/allocations, actors, evidence, policy versions and approvals. A
correction/replacement is an explicit append-only superseding award; the superseded
award remains permanently retained and auditable. Finalization creates no PO,
contract, AP, GL, Treasury/cash, budget or other downstream-domain record, and
downstream handoff remains unauthorized.

**Accepted detailed RFQ applicability and award governance:** Comparison and award
operate at explicit RFQ line or lot scope. A line is independently awardable only
when so marked by the RFQ; an indivisible lot must be awarded whole. Multi-award is
allowed only when the RFQ expressly permits split/partial award. Alternates may
participate only where the RFQ permits them and maps them to the exact line/lot;
they never silently replace the base offer or act as equivalent where their basis is
materially different. Non-comparable alternates fail closed.

Award preparation and finalization require separate permissions, and an award
references a finalized comparison. `TIE_REVIEW_REQUIRED` cannot automatically select
a winner. `NO_AWARD` and tie resolution each require an explicit authorized decision
and retained reason/evidence; neither silently changes the finalized comparison.
Finalized award correction, cancellation or reallocation requires a new superseding
award that permanently retains the predecessor/successor chain, quantities, actors,
reasons and evidence.

**Scoped P5-D01 supersession — accepted:** P5-S11 explicitly supersedes P5-D01's
self-approval prohibition only for its immutable sourcing-only award business
operation. Award preparation and finalization remain separate permissions and
self-finalization is disabled by default. A Tenant may explicitly enable it through
the approved Tenant business-operation self-approval policy, including for a small
or single-user organization. When disabled, distinct authorized preparer and
finalizer are required. When enabled, the applied policy version, actor,
Tenant/object/revision scope, decision and evidence must be explicitly audited.

This exception never permits an actor to self-clear a conflict: an actor with an
unresolved conflict cannot prepare or finalize the affected award. It does not
extend to Protected system/security/access operations, confidential reveal,
break-glass, downstream PO/contract/AP/GL/Treasury/cash/budget/access-grant actions
or another cross-domain operation. The award remains an immutable sourcing decision;
downstream handoff is separately gated. All other P5-D01 Protected-operation
controls remain unchanged.

## Implementation gate

All Product Owner decisions are complete. Clean PostgreSQL migration
apply/rollback/reapply completed, followed by 9 focused S11 PostgreSQL tests
(two-revision tie/no-award, split/allocation, policy, conflict/exception,
lineage, idempotency/concurrency and downstream-non-mutation coverage) and 10
retained P5-S07–S10 regressions. The Product Owner accepted P5-S11 as implemented
and PostgreSQL-verified on 2026-10-02.
P5-S11 supplies only its comparison/evaluator/exception/sourcing-award runtime
authority. P5-S12 and later work remain outside this packet.
