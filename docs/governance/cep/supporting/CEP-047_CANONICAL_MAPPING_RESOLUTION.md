# CEP-047 — Finding001 Canonical Mapping Resolution

Continue the existing CEP-047 execution.

`CEP-047-FINDING-001` requested approved `INT-B04 / INT-B05 / INT-B06` mappings or their canonical locations.

The canonical mappings are confirmed from the approved BONIRA integration/backlog artefacts. Do not invent or broaden them.

## Governing authority

`PD-010 — Project Cost producer authority`

Rules:

- `ProjectCostFact` remains the Project Cost authority.
- Source domains may produce Project Cost facts only through explicit approved Producer Contracts.
- Actual Cost producers require approved mapping, cutoff and producer contract.
- Every produced fact retains Source Identity, Source Version and Producer Contract lineage.
- Missing mapping/policy is fail-closed.

Mandatory guardrail:

`NO APPROVED PRODUCER CONTRACT → NO PROJECT COST FACT`

No generic model/field/domain similarity may authorize Project Cost production.

---

## INT-B04 — Inventory → Project Cost Actual

Canonical source:
`BONIRA_INTEGRATION_MASTER_BACKLOG` → Detailed Target Contracts for Series B → `INT-B04`

Canonical contract:

- Source: posted/valued inventory consumption attributable to project/cost dimension.
- Target: Project Cost actual candidate.
- Automation: `L2`.
- Required contract: approved Inventory producer contract with unit/value basis.
- Correction: inventory reversal/correction must create the corresponding Project Cost reversal/replacement.
- Reconciliation: inventory consumption/value ↔ Project Cost.

Final Implementation Backlog mapping:

`IMB-0034 — Inventory → Project Cost actual producer`

Additional binding requirements:

- producer is source-specific;
- source identity/version must be retained;
- processing is idempotent;
- retry/failure cannot duplicate target occurrence or bypass validation;
- approved Inventory→ProjectCost mapping must exist;
- cutoff/effective-date rule must exist;
- Project Cost classification must exist;
- no generic Inventory record → ProjectCostFact behavior;
- source and target authorities remain separate.

---

## INT-B05 — Equipment → Project Cost Actual

Canonical source:
`BONIRA_INTEGRATION_MASTER_BACKLOG` → Detailed Target Contracts for Series B → `INT-B05`

Canonical contract:

- Source: approved equipment usage/allocation evidence.
- Target: Project Cost actual candidate.
- Automation: `L2`.
- Required policy:
  - cost rate/version;
  - time/quantity basis;
  - project/site/activity dimensions.
- Reconciliation: equipment operational usage ↔ recognized Project Cost.

Final Implementation Backlog mapping:

`IMB-0035 — Equipment → Project Cost actual producer`

Additional binding requirements:

- approved Equipment→ProjectCost producer mapping must exist;
- applicable cost rate/version evidence must exist;
- Project Cost classification must exist;
- source identity/version must be retained;
- processing must be idempotent;
- correction/reversal must remain source-version aware;
- retry/failure cannot duplicate target occurrence or bypass validation;
- no generic Equipment existence → Project Cost behavior;
- no CMMS scope expansion.

---

## INT-B06 — Fixed Assets / Depreciation → Project Cost Actual

Canonical source:
`BONIRA_INTEGRATION_MASTER_BACKLOG` → Detailed Target Contracts for Series B → `INT-B06`

Canonical contract:

- Source: approved depreciation/asset allocation evidence.
- Target: Project Cost actual candidate.
- Automation: `L2`.
- Required policy:
  - depreciation allocation;
  - project attribution version.
- Reconciliation: asset-book depreciation ↔ Project Cost.

Final Implementation Backlog mapping:

`IMB-0036 — Fixed Assets → Project Cost actual producer`

Additional binding requirements:

- approved Fixed Asset/Depreciation→ProjectCost allocation mapping must exist;
- asset-book version must be retained;
- Project Cost classification must exist;
- source identity/version must be retained;
- processing must be idempotent;
- mapping and reversal must be explicit;
- retry/failure cannot duplicate target occurrence or bypass validation;
- Fixed Asset existence alone must never create Project Cost;
- source and target authorities remain separate.

---

## Execution Instruction

Treat the above mappings as the canonical resolution input for `CEP-047-FINDING-001`.

Re-run CEP-047 entry/grounding against these contracts.

If repository reality can implement these exact contracts within the canonical CEP-047 scope:

1. mark Finding001 resolved with provenance to these canonical mappings;
2. continue bounded CEP-047 implementation;
3. execute the canonical required tests/evidence;
4. evaluate all CEP-047 AC and scoped DoD;
5. preserve remaining runtime UTV;
6. do not infer `GATE-05` passage merely from CEP-047 completion.

If a further material business rule is required that is not defined above or in the canonical CEP-047 prompt:

`STOP → RECORD NEW FINDING → DO NOT INVENT`

Do not modify the approved mappings, PD-010, CEP scope, AC, DoD or canonical dependency semantics.

At completion, report the normal CEP-047 execution verdict, evidence, Git status and gate impact.