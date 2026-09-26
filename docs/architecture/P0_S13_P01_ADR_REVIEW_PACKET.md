# P0-S13: P0.1 ADR review and decision packet

**Status:** READY FOR PRODUCT OWNER REVIEW — no ADR accepted and no implementation authorized

**Recorded:** 2026-09-25

This packet consolidates the nine P0.1 proposals prepared in P0-S04 through
P0-S12. It is a review aid, not a tenth ADR, a substitute for each proposal, or
evidence that an open decision has been made. The
[Roadmap decision register](../../ROADMAP.md#product-owner-decision-register),
[S03 open-input register](../ROADMAP_EXECUTION_PLAYBOOK.md#unresolved-parameters-and-latest-gates)
and each linked ADR remain authoritative.

## 1. Review boundary and status

P0-D01 and P0-D02 are approved directions. P0-D03 and P0-D04 have approved
directions with parameters open. P0-D05 has an approved policy with parameters
open. P0-D06 accepts the audit findings/priorities but expressly withholds
implementation authorization.

P0-S15 records authoritative Product Owner selections for Q04-A through Q04-H.
Reviewer names and outcomes remain OPEN, so the shared accountable-review gate is
not complete and no ADR acceptance or implementation authorization follows.

All nine detailed ADRs remain **PROPOSED**. “Execute P0-S13” authorizes preparation
of this consolidated review only. It does not mean:

- direction approval, formal ADR acceptance or rejection;
- selection of a parameter, formula, role, reviewer, operator, provider or pilot;
- approval of a migration, dependency, data move or compatibility contraction;
- authorization of P0.2, P0.3 or any downstream package; or
- activation of the deferred controlled B2B network.

Three decisions must stay distinct:

1. **Direction disposition:** Product Owner accepts the proposed architecture for
   completion of its named gates, requests revision, or defers/rejects it.
2. **Formal ADR acceptance:** all acceptance-blocking inputs and accountable
   reviewers required by that ADR are resolved and recorded.
3. **Implementation authorization:** a separately bounded package identifies
   scope, migrations, permissions, tests, rollout, rollback and operations.

A direction disposition does not collapse the latter two steps.

## 2. Consolidated ADR review matrix

| Review item | Proposed architectural direction | Readiness and decisions still required | Affected delivery |
| --- | --- | --- | --- |
| [S04 Accounting/posting](ADR_P0_S04_ACCOUNTING_POSTING.md#8-acceptance-gates-and-consequences) | Accounting is sole GL authority; Treasury, AP/AR and operational sources remain distinct; source/version/rule identity drives idempotent posting, reversal, close and reconciliation; legacy `Payment` is contained rather than treated as a ledger. | **Ready for direction review; not unconditional acceptance.** Q01 currency/fiscal/precision, Q02 professional recognition/statutory review, Q04 named review/risk evidence, pilot/cutoff/opening/reconciliation and named accounting/operations owners remain open. | PPC-02; P1.2, P2, P3 and every posting producer. |
| [S05 Budget/project cost](ADR_P0_S05_BUDGET_PROJECT_COST.md#8-open-decisions-consequences-and-acceptance-gates) | Accepted immutable budget baselines, explicit CBS/cost-center classification and source-reconciled commitment/accrual/actual/paid/forecast facts replace editable project totals as authorities. | **Ready for direction review; not unconditional acceptance.** Budget/change/CBS/allocation/contingency policy, Q01/Q02, Q04 review, migration coverage/cutoff and named Project Controls/accounting owners remain open. | PPC-03; P4.1 and cost-producing packages. |
| [S06 Regulatory/contract policy](ADR_P0_S06_REGULATORY_CONTRACT_POLICY.md#6-static-review-cases-and-implementation-gates) | Effective regulatory rule versions, versioned contract terms and tenant presentation/configuration have separate ownership; finalized calculations pin applied versions and snapshots. | **Ready for direction review; not unconditional acceptance.** Q01/Q02, authoritative sources/reviewers, applicability dates, precedence/order, cap semantics, retroactive correction and Q04 named review/evidence remain open. | PPC-01/PPC-06; P1.2, P6.3 and regulated consumers. |
| [S07 Project/site authorization](ADR_P0_S07_PROJECT_SITE_AUTHORIZATION.md#4-privileged-paths-and-separation-unresolved-not-exceptions) | Tenant permission is the union from all active applicable independent Membership role assignments, then intersected with explicit project/site object scope and workflow responsibility; roles remain Tenant-scoped, assignments/positions do not grant permission and no Tenant Owner/Tenant Admin/Platform Admin/Superuser/support bypass is assumed. | **Blocked for formal acceptance by Q04 review.** A1/B1/C1/D1/E1, revised F2, final G3 — Revised with Protected Operations, H1 and the authoritative multi-role rule are recorded; current single-role compatibility migration plus named security/workflow and conditional specialist review/evidence remain OPEN. | PPC-04/PPC-08; P1.1 and all sensitive domains. |
| [S08 Private storage](ADR_P0_S08_PRIVATE_DOCUMENT_STORAGE.md#6-decision-register-and-static-acceptance-cases) | DMS owns private immutable version identity; storage uses quarantine/availability states, provenance, protected export, hold-aware disposition and recovery reconciliation. | **Ready for direction review; not unconditional acceptance.** D03/D04 provider/location/operator/recovery, Q03 retention/hold/export, Q04 review, D05 storage accounting, availability/delivery/scanner and migration choices remain open. | PPC-05; P0.2/P0.3/P1.3 and all file consumers. |
| [S09 DMS links](ADR_P0_S09_DMS_DOMAIN_LINKS.md#2-alternatives-and-proposed-ownership) | Prefer domain-owned typed link tables with real FKs behind a platform-owned closed adapter registry; keep DMS as document/version authority and exclude GenericForeignKey/arbitrary dispatch. | **Ready for direction review; not unconditional acceptance.** Product Owner must confirm the recommended ownership option; S07 review, S08 retention/storage, Q03, physical schema/module placement, six-target backfill and cutover/rollback remain open. | PPC-10; P1.3 and every new DMS-linked domain. |
| [S10 Async/outbox](ADR_P0_S10_ASYNC_OUTBOX_IDEMPOTENCY.md#6-recovery-retention-and-compatibility-gates) | Keep business authority in domain services; use tenant-scoped transactional outbox intent and stable operation identity, with transport attempts, provider receipts, uncertain-outcome reconciliation and authority rechecks separated. | **Ready for direction review; not unconditional acceptance.** Select the first producer/consumer, operating owner, dependencies/transport, limits/retry policy, D03-D05/Q03 and Q04 review contracts, plus restore/reconciliation behavior. | P0.2 and future integration/notification/storage operations; no blanket conversion. |
| [S11 Tenant lifecycle/support](ADR_P0_S11_TENANT_LIFECYCLE_ENTITLEMENTS_SUPPORT.md#7-acceptance-gates-and-compatible-implementation-sequencing) | Separate tenant state, commercial phase, effective entitlements, quota usage/admission, retention disposition and support authority; cancellation does not delete history or authorize pending work. | **Ready for direction review; not unconditional acceptance.** D03/D04, D05 metrics/values/lifecycle/commercial operator, Q03, Q04 review, controlled inactive-tenant export/support paths and operation-specific background authority remain open. | P0.3 plus P0.2/P1.1/P1.3 intersections. |
| [S12 Future-network privacy](ADR_P0_S12_FUTURE_NETWORK_PRIVACY.md#8-open-decisions-and-acceptance-boundaries) | Keep network deferred; tenant sources stay private and authoritative; any future platform claim/publication is separate, explicit, purpose/audience/version-bound, revocable and provenance-preserving. | **Privacy boundary is ready for direction review; capability is not ready for activation.** Deferred trigger, purpose/business model, identity/consent terms, claims/relationships, moderation, reputation/aggregation, privacy/competition, D03/D04/Q03, Q04 review and S11 lifecycle remain open. | Before any cross-tenant network feature; not a core P0.2/P0.3 implementation authorization. |

## 3. Cross-ADR consistency review

The proposals are **conditionally coherent** when their open gates are preserved:

1. **Financial authority:** S04 owns journals/subledgers and posting acceptance;
   S05 owns project-control classifications and projections; S06 supplies pinned
   rule/term inputs. None makes cash, budget or mutable policy an alternate GL.
2. **Authorization and lifecycle:** S07 answers who may act on which tenant object;
   S11 may further block an otherwise authorized action by tenant/entitlement state.
   Neither permission nor entitlement substitutes for the other. Multiple roles are
   independent Membership assignments: their permissions union within the active
   Tenant, while every other authorization factor remains an intersection.
3. **Evidence and relationships:** S08 owns bytes/version state; S09 owns the
   explicit relationship contract between a document and a domain record. Target
   domains keep business lifecycle authority, and all linked contexts remain
   authorization inputs.
4. **Deferred execution:** S10 transports committed intent but does not create
   business authority. It must recheck the S07/S11 operation contract and preserve
   S08/S09 source/version lineage where files or links are involved.
5. **External sharing:** S12 creates no path around S07-S11. A platform claim,
   consent, verified relationship, support case or worker identity grants no
   membership, object scope, document access or background authority.
6. **History and recovery:** every proposal preserves finalized evidence and uses
   revision/reversal/supersession, manifest reconciliation and explicit rollback;
   none authorizes silent history rewrite or compatibility-field removal.

No direct authority conflict requiring an ADR rewrite was found. The important
remaining risks are unresolved policy choices and owners, not contradictory
proposed boundaries. That finding is static documentation review, not runtime,
professional, operational or legal acceptance.

## 4. Decision clusters and dependency order

The efficient review order is by shared blocker rather than ADR number.

| Order | Decision cluster | Decisions and named owners needed | ADRs unlocked for formal review |
| ---: | --- | --- | --- |
| 1 | Q04 authorization/separation | A-H Product Owner selections are recorded. Name security/workflow and conditional specialist reviewers; review revised F2 emergency access, final G3 — Revised with Protected Operations, and its business Self-Approval risks. | S07 directly; S04-S06 and S08-S12 access/operation clauses. |
| 2 | Q01/Q02 finance/regulation | Currency/fiscal/precision/valuation; statutory filing/export boundary; authoritative sources and accounting/legal reviewers; recognition, rule precedence and retroactivity. | S04-S06; downstream P1.2/P2/P4/P6.3/P7/P8.1 design. |
| 3 | D03/D04 operations/recovery | Provider and permitted data/log/backup/support locations; operators/incident owner; numeric RPO/RTO/scenarios; key/restore ownership and evidence. | S08, S10, S11 and future S12 data placement; P0.2. |
| 4 | Q03 evidence lifecycle | Signature/evidence standards; retention triggers/periods; hold/release/disposal authority; export format/completeness and responsible reviewer. | S08-S12 retention/export/rollback design; P1.3 and offboarding. |
| 5 | D05 commercial/lifecycle | Metric definitions/values; warnings/overage/upgrade; protected-completion accounting; trial/grace/suspension/cancellation/re-entry; pricing/support terms and external operator. | S11/P0.3 plus storage, async and offboarding interactions. |
| 6 | ADR-specific rollout | Budget policy; financial/storage/DMS migration pilots; S09 ownership choice; S10 first operation/dependency; named domain/operations owners and rollback evidence. | Separate bounded implementation-package proposals only after relevant ADR acceptance. |
| 7 | Deferred network | Decide only whether to accept S12 privacy guardrails now; do not assess launch until Roadmap triggers, purpose/business model and named privacy/legal/security/competition/operations reviews exist. | Future network program only; no current implementation package. |

This order is a review recommendation, not an approval or schedule commitment.
Independent clusters may be reviewed in parallel only when the same accountable
reviewers can preserve consistent decisions.

## 5. Product Owner disposition template

Record explicit answers; silence or “continue” is not a disposition. For each ADR:

| ADR | Direction disposition (`ACCEPT FOR GATE COMPLETION`, `REVISE`, `DEFER`, `REJECT`) | Required revision, if any | Formal acceptance blockers acknowledged | Accountable owner/reviewer names |
| --- | --- | --- | --- | --- |
| S04 | OPEN | — | Q01/Q02; Q04 review; migration/pilot | OPEN |
| S05 | OPEN | — | budget policy; Q01/Q02; Q04 review; migration | OPEN |
| S06 | OPEN | — | Q01/Q02; Q04 review; sources/precedence/retroactivity | OPEN |
| S07 | OPEN | — | Q04 reviewer names/evidence | OPEN |
| S08 | OPEN | — | D03/D04/D05/Q03; Q04 review; storage choices | OPEN |
| S09 | OPEN | — | ownership choice; S07/S08/Q03; Q04 review; migration | OPEN |
| S10 | OPEN | — | first operation; D03-D05/Q03; Q04 review; operations/dependency | OPEN |
| S11 | OPEN | — | D03-D05/Q03; Q04 review; export/support/background authority | OPEN |
| S12 | OPEN | — | network trigger/purpose and privacy/legal/security/competition/operations decisions | OPEN |

Then identify the first decision cluster to resolve and name its accountable
reviewers. Do not change an ADR to ACCEPTED until its stated mandatory acceptance
gates have evidence. Do not infer implementation authorization from an accepted
direction or ADR.

## 6. Acceptance and next bounded handoff

P0-S13 is complete when this packet is linked from the Roadmap/Playbook and static
consistency checks pass. It does not complete P0.1 because every disposition row
and multiple phase-gated inputs remain open.

P0-S14 prepared and P0-S15 populated the bounded
[Q04 Product Owner decision packet](P0_S14_Q04_PRODUCT_OWNER_DECISION_PACKET.md).
The selections are authoritative for this decision round. P0-S16 records that the
accountable reviews are not complete and that reviewer names, outcomes,
evidence/version and review dates, unresolved objections, and reviewer-driven
revisions all remain OPEN. A future session may record supplied reviews and update
affected ADR/Roadmap statuses; it must not invent review information, treat an
OPEN field as approval, accept an ADR or start implementation without separate
authority.
