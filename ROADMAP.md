# BONIRA CEP Delivery Roadmap

**Program stage:** pre-production. **Planning reconciliation:** 2026-10-16.

## 1. Purpose and authority boundary

This Roadmap describes the CEP program's delivery direction, structure,
dependency-ordered planning, and residual/future product scope. It grants no
implementation authority. [CEP Program Authority](docs/governance/CEP_PROGRAM_AUTHORITY.md)
defines the source hierarchy. For current CEP lifecycle, recorded authorization,
blockers, completion, UTV, Git integration, and the execution frontier, read
`CEP_EXECUTION_REGISTRY.yaml`. A canonical CEP contract defines that package's
scope, acceptance criteria, and Definition of Done. Code, migrations, and tests
define implementation reality.

## 2. Current product stage

BONIRA is a Persian-first, multi-tenant construction ERP in pre-production.
Implemented development capability and production readiness are separate claims.
Unresolved decisions, integrations, acceptance evidence, and production controls
remain gated where their source contracts require them. No roadmap label grants
production activation, Human Sign-off, or Production Certification.

## 3. Origin of the CEP program

The current controlled program follows Audit 01–20, Product and Domain /
Technical Reviews, Gap Analysis, the Remediation Master Backlog, frozen Product
Decisions, dependency analysis, CEP package design, and canonical execution
prompts. Those upstream artifacts establish scope and policy; ordinary execution
does not regenerate them. The [program authority](docs/governance/CEP_PROGRAM_AUTHORITY.md)
records how to use them.

## 4. Historical P0–P10 development baseline

P0 through P10 were executed as historical development phases. Their
architecture, capability, decision, and session lineage remains available in
the [dated project record](docs/PROJECT_STATUS.md), architecture decision and
closeout packets, completion reports, and the committed historical versions of
this Roadmap and the Playbook at `a4a18a1`.

Historical `PLANNED`, `NEXT-CANDIDATE`, `incomplete`, or `blocked` language
records the state of a particular capability, decision, or session at that time.
It does not place a P-phase back into the execution queue. Phase execution does
not imply that every target capability in that phase was delivered or certified.

## 5. CEP program inventory

The governed inventory contains 86 CEP IDs; the [Registry](CEP_EXECUTION_REGISTRY.yaml)
contains the individual records. Its classification is:

| CEP range | Program role |
| --- | --- |
| CEP-001–CEP-068 | V1 implementation and remediation |
| CEP-069–CEP-072 | Production certification |
| CEP-073–CEP-079 | Verification and UAT |
| CEP-080–CEP-086 | Post-V1, deferred |

The first three ranges comprise 79 current-governed records; seven are Post-V1.
The inventory is not a queue or a grant to execute any record.

## 6. CEP program structure

V1 packages address bounded implementation, correction, and evidence gaps in the
construction ERP. Production certification packages evaluate release controls;
Verification/UAT packages provide their own acceptance evidence. Post-V1
packages remain deferred until their canonical triggers, dependencies, decisions,
and authorizations are satisfied. Each CEP retains its canonical identity and
contract; this Roadmap does not replace CEP scope, AC, DoD, or the dependency
graph.

## 7. Dependency and gate model

The approved CEP dependency model and canonical package sources govern exact
prerequisites. For each CEP, verify its dependencies and applicable gates against
those sources, the Registry, standing or specific Human authority, and repository
evidence. `DEPENDENCY READY`, `ELIGIBLE`, `READY`, and a Roadmap entry do not
expand scope or authorize production. Objectively defined technical/evidence
gates may pass under the Execution Policy; a blocked dependency stays blocked
until supported resolution is recorded.

## 8. Delivered and closed baseline

The historical phases delivered a broad non-production baseline: tenant identity
and authorization; shared masters; projects, estimates, contracts, procurement,
inventory, equipment, workforce, payroll foundations, workflow/workbench,
billing/claims, documents, HSE/Quality, and governed reporting/reconciliation.
Delivery depth varies by domain, and many downstream financial, statutory,
provider, and production effects remain absent or gated. The Registry owns
current CEP closure; a [completion report](docs/governance/cep/reports/CEP-026_COMPLETION_REPORT.md) and its
evidence explain one execution result. The [historical snapshots](docs/PROJECT_STATUS.md)
retain dated validation claims.

## 9. Current execution frontier

The Registry's `execution_frontier`, CEP records, and gate records determine the
current frontier. Read them at the start of every session and reconcile them after
a Human Git checkpoint. Eligible current-governed non-production CEPs may proceed
under standing authority as defined by the Execution Policy. This Roadmap
deliberately maintains no second live CEP queue or per-CEP completion ledger.

## 10. Remaining dependency-ordered delivery model

Residual work proceeds only through the applicable canonical CEPs under standing
or specific authority. The remaining direction includes administration surface
separation; bounded tenant, object-scope, privacy, and DMS corrections; source-
owned financial and project-cost integration; operational provider and
statutory-value activation; production storage, recovery, observability, and
release controls. This is a capability map, not a claim that every item is an
approved next task. Exact ownership, order, scope, and stop conditions remain
with the canonical CEP program and frozen decisions.

### 10.1 Accounting Gap — Fiscal-Year Closing & Opening Balance Roll-forward

**Status:** `DEFERRED_UNTIL_CURRENT_CEP_PROGRAM_COMPLETES`. Recorded by explicit
Human/Product decision on 2026-10-25. This is an independent Accounting functional
gap scheduled for consideration after the current CEP program completes. It is
not classified as Post-V1 and is not implementation authority or a production
readiness/certification claim. It changes no current CEP scope, dependency or Gate.

**Current implementation:** Initial / Migration Opening Import exists as a
controlled, independently reviewed import of supplied opening balances and
external source/evidence/reconciliation references. Automatic fiscal-year
roll-forward is missing. Period close retains controls and reporting evidence
but generates no next-year Opening Journal. Report-derived opening balances
remain read models and do not implement this missing process.

**Minimum future scope to define and authorize:**

- Derive eligible closing balances from POSTED Ledger.
- Distinguish permanent versus temporary accounts.
- Provide controlled year-end closing.
- Generate the next-year Opening Journal.
- Retain fiscal-year linkage and cutoff.
- Enforce idempotency and prevent duplicate roll-forward, including double
  counting against the continuing Ledger.
- Require approval and separation of duties (SoD).
- Define correction/reversal behavior without rewriting finalized history.
- Prove closing-to-opening reconciliation.
- Retain an audit trail.

**Boundary:** UIUX-F-076 concerns only initial setup / migration from the previous
accounting system. Its closure does not deliver or close this Accounting gap.
After the current CEP program completes, establish the bounded Product/Accounting
contract and execution authority before implementation. No roll-forward
implementation or schema/migration is included in the present UI clarification.

## 11. Production and verification path

Implementation evidence alone does not certify production. The CEP-069–CEP-072
range covers production certification and CEP-073–CEP-079 covers verification /
UAT. The earlier P10 certification attempt was administratively closed with
performance, production recovery, security, and release evidence still gated;
its [candidate](docs/architecture/P10_S18_CERTIFICATION_CANDIDATE_MANIFEST.md)
and [certification evidence](docs/architecture/P10_S19_S21_RELEASE_CERTIFICATION_EVIDENCE.md)
remain historical inputs, not new authorization. Production cutover and Human
Sign-off require their separate explicit decisions.

## 12. Deferred and Post-V1 scope

The seven Post-V1 CEPs remain in their governed range. Other target capabilities
remain deferred until a documented trigger and separate authority: controlled
B2B/network intelligence, shared cross-tenant catalogue, enterprise SSO,
broad offline synchronization, AI assistants, GIS/telematics, public API, and
any microservice or event-sourcing transition. These are product directions,
not delivered capabilities or approved implementation packages. General-purpose
CRM, tenant-authored executable BPM, parallel ledgers/workflow engines, and
unrestricted SQL or autonomous consequential AI remain outside the accepted
product strategy.

## 13. Historical P0–P10 reference

The historical implementation/dependency sequence was P0 decisions and
operational foundations; P1 masters/authorization; P2 Accounting; P3 Treasury
and AP/AR; P4 project costing/controls; P5 source-to-pay; P6 contracts/claims;
P7 workforce/payroll; P8 inventory/equipment/assets; P9 field/HSE/Quality and
knowledge; and P10 reporting/reconciliation/certification. It is lineage, not
the current execution order. Retain the original detailed Roadmap from Git
checkpoint `a4a18a1` and its referenced architecture/decision packets for
historical interpretation.

Legacy Roadmap links from dated packets resolve here to that retained historical
version; they do not describe current CEP state:

<a id="p03-saas-plans-entitlements-quotas-and-tenant-offboarding"></a>
<a id="p12-configuration-and-master-governance-corrections"></a>
<a id="product-owner-decision-register"></a>
<a id="deferred-until-explicit-triggers"></a>

## 14. Roadmap governance

Change this Roadmap when delivery direction, program structure, dependency-
ordered planning, phase disposition, or future scope materially changes. Record
current CEP lifecycle and Git state in the Registry and detailed execution
evidence in the relevant Completion Report. Use
`docs/ROADMAP_EXECUTION_PLAYBOOK.md` for execution procedure and `Agents.md`
for persistent Codex rules. Do not infer a Product Decision, dependency edge,
Gate PASS, or scope expansion from this Roadmap.
