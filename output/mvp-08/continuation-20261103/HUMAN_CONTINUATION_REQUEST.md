Continue from the current blocked MVP-08 working state.

Do NOT restart MVP-08 from the beginning.

Do NOT discard or regenerate already-qualified Journey 1, Journey 2, demo-state, XLSX, Print, authorization, responsive, or offline evidence unless the policy change creates an actual blast radius.

The current blocker is:

`BLOCKER-MVP08-RFQ-POLICY-EXPIRED`

The three existing published RFQ policy versions expired on 2026-10-25 / 2026-10-26 and have no currently effective successor.

This continuation provides the required Human Product Decision for the current MVP:

# Human Product Decision — RFQ Separation of Duties

Preserve the currently accepted RFQ separation-of-duties behavior.

For all three policies below:

```text
allow_self_approval = false
```

Self-approval / self-finalization remains prohibited.

The governing intent is:

- the actor preparing quote admissibility must not approve their own admissibility decision;
- the actor preparing/finalizing the commercial comparison must remain subject to the existing independent-finalization rule;
- the actor preparing the sourcing award must not finalize their own supplier-selection award.

This decision does NOT authorize any new permission, role, workflow, sourcing rule, financial policy or domain behavior.

---

# 1. Policy Successors

Create new governed successor versions for exactly:

```text
rfq-admissibility-self-approval
rfq-comparison-self-finalization
rfq-sourcing-award-self-finalization
```

Do not modify the expired versions.

Do not extend their `effective_to`.

Do not rewrite historical selections.

Determine the next valid version number from the existing platform policy history rather than assuming one.

Each successor must use:

```text
parameters:
    allow_self_approval: false
```

Effective dating:

```text
effective_from = current lawful configuration date
effective_to = null
```

The intent is that these operational separation-of-duties policies remain effective until superseded by a future explicitly governed version.

Do not create another arbitrary short-lived test expiry.

---

# 2. Preserve Historical Policy Evidence

The expired versions remain immutable historical records.

Verify that after successor creation:

- previous versions still exist unchanged;
- their old effective dates remain unchanged;
- historical tenant selections remain preserved;
- no historical sourcing/award record is repointed;
- new current selections reference only the new successor versions.

Do not delete, retire retroactively, overwrite or mutate the previous policy versions.

---

# 3. Use Existing Governance Services

Use the existing canonical policy services, including where applicable:

- `create_platform_policy_version`
- `publish_platform_policy_version`
- `select_tenant_policy_version`
- `apply_tenant_policy_selection`

Do not insert policy/version/selection records through ad-hoc direct database writes if governed services already exist.

Do not change `policy_specs.py`.

The existing code-owned policy contract is already sufficient.

No schema or migration change is authorized.

---

# 4. Publication and Tenant Selection

Publish the successor versions through the existing governed mechanism.

Apply/select them only for the lawful MVP-08 demo organization(s) required to execute Journey 3.

Do not globally alter unrelated customer/Development tenant selections merely to make MVP-08 pass.

If the intended current platform configuration already requires these policies for another explicitly governed tenant, preserve its existing lawful selection rather than automatically replacing it.

Record exactly:

```text
policy code
old version
old effective range
new version
new effective range
parameters
publisher
tenant selection
reason
```

No credentials or sensitive identifiers in the report.

---

# 5. Preflight

Before resuming Journey 3, run an explicit preflight proving that the current application clock selects the new effective versions for the MVP-08 demo tenant.

Verify all three resolve successfully through the same native policy-selection path that previously raised the expiry blocker.

Required:

```text
RFQ ADMISSIBILITY POLICY: CURRENT
RFQ COMPARISON POLICY: CURRENT
RFQ SOURCING AWARD POLICY: CURRENT
ALLOW_SELF_APPROVAL: FALSE
```

If any of these fail:

STOP the affected continuation and report the exact governance/configuration failure.

Do not bypass policy selection.

---

# 6. Resume Existing Demo State

Resume from the retained current MVP-08 demo state.

Do not rebuild Journey 1 or Journey 2.

Do not destroy:

- approved Daily Report;
- approved Billing claim;
- existing Project/Site/Workforce/Equipment/HSE/Quality data;
- existing PR draft/source data;
- retained evidence.

Extend only the current Journey-3 demo chain as needed.

Preserve the existing `seed_mvp_demo` idempotency contract.

If the seed command requires a bounded extension to create current Journey-3 starting state, make it deterministic and idempotent.

Rerun the seed twice after the extension and prove zero duplicate owned records.

---

# 7. Complete Journey 3

Continue the actual canonical customer-visible Procurement/Inventory journey:

```text
PR
→ approval
→ RFQ
→ RFQ lines / sourcing configuration
→ supplier invitation
→ quote capture/submission
→ close
→ protected opening
→ admissibility preparation
→ independent admissibility approval
→ comparison
→ independent comparison finalization
→ sourcing award
→ independent award finalization
→ PO
→ issued PO version
→ partial GRN(s)
→ explicit Inventory movement
→ Inventory posting
→ representative reversal
```

Use the actual implemented domain sequence.

Do not skip implemented sourcing/award stages merely to reach PO.

---

# 8. Separation-of-Duties Verification

Explicitly prove negative and positive cases.

For each governed stage:

## Admissibility

- preparer cannot approve their own preparation;
- independent authorized approver can approve.

## Comparison

- prohibited self-finalization is denied;
- independent authorized actor can finalize.

## Award

- prohibited self-finalization is denied;
- independent authorized actor can finalize.

Record native denials and successful independent decisions.

Do not widen permissions if a persona lacks authority.

Use an existing lawful persona where available.

If a genuinely missing role/permission policy is discovered, classify it separately and stop that path rather than silently granting broad authority.

---

# 9. Supplier Evidence and Confidentiality

Preserve current sourcing controls for:

- supplier source identity;
- quote revision;
- sealed/protected evidence;
- custody;
- protected opening;
- confidential access;
- processing/scanning evidence where current domain requires it;
- tenant/project isolation.

Synthetic supplier evidence is permitted for Development/UAT only.

Clearly identify it as synthetic.

Do not represent synthetic quote content as real commercial evidence.

---

# 10. Quantity and Lineage

Verify full lineage:

```text
PR item
→ RFQ line
→ quote
→ comparison
→ award/allocation
→ PO line/version
→ GRN item
→ Inventory transaction
```

Verify quantity conservation.

Where the accepted MVP-04 domain supports partial/split behavior, execute a representative partial journey if already part of the current demo design.

Ensure:

- awarded quantity does not exceed sourcing scope;
- ordered quantity does not exceed award allocation;
- received quantity does not exceed PO allowance;
- Inventory quantity follows explicit GRN handoff.

Do not alter quantity rules.

---

# 11. PO / GRN / Inventory Boundary

Preserve accepted architecture:

- GRN does not automatically become Inventory stock merely because receipt is posted;
- Inventory remains the sole stock authority;
- stock posting is explicit;
- reversal preserves original transaction/history.

Verify a positive posting and representative reversal.

Do not activate:

- AP;
- Treasury;
- Accounting;
- GL;
- supplier payment;
- inventory valuation.

---

# 12. Financial Boundary

After complete Journey 3, verify the MVP demo tenant still has no unintended:

- AP record;
- AR effect from procurement;
- Treasury transaction;
- GL journal;
- supplier payment;
- Payroll effect;
- Inventory valuation/accounting posting

caused by Journey 3.

Operational procurement and stock movement are the authority boundary.

---

# 13. Browser E2E

Complete Journey 3 using installed real Chrome and ordinary customer-visible UI wherever the current product exposes the required action.

Service-level checks may support domain assertions but must not replace required browser journey evidence.

Verify current:

- Persian terminology;
- RTL;
- action hierarchy;
- sourcing state progression;
- source links;
- supplier identity;
- PO;
- GRN;
- Inventory handoff;
- no critical technical leakage.

Use representative 1440px execution and responsive checks at 1024px / 390px on key sourcing pages.

---

# 14. Technical Leakage

Re-run the previously incomplete technical-leakage gate across the now-executed Journey 3 surfaces.

Fail on critical customer-visible leakage such as:

- raw UUID where a business identifier exists;
- Django/model/service names;
- permission codes;
- internal state keys;
- technical scope codes presented as primary business concepts;
- idempotency keys;
- stack/debug information.

Perform only bounded fixes that require no Product Decision or domain change.

---

# 15. Outputs

After Journey 3 is complete, verify from the coherent main demo state:

- Procurement XLSX;
- PO XLSX;
- GRN XLSX;
- Inventory XLSX;
- PO Print;
- GRN Print.

This time do not rely only on the separate independent output fixture.

The coherent Journey-3 demo chain itself must supply valid PO/GRN/Inventory evidence.

Reopen XLSX files with the existing `openpyxl` verification.

Render Print through the existing MVP-06 browser-native foundation.

---

# 16. Tenant / Permission Isolation

Repeat representative Journey-3 negative checks using:

- restricted same-tenant persona;
- second-tenant persona.

Verify denial for source records, detail pages, XLSX and Print where applicable.

No cross-tenant supplier/quote/award/PO/GRN/Inventory leakage.

---

# 17. Demo-State Qualification

After successful Journey 3 completion, update the retained demo state so Human UAT scenarios 11–14 have valid starting states.

Then re-run demo idempotency.

Required result:

```text
DEMO STATES: PASS
DEMO STATE IDEMPOTENCY: PASS
```

Do not overwrite the final Human starting state when the seed is rerun.

---

# 18. Human UAT Package

Update:

`docs/governance/mvp/MVP-08_HUMAN_UAT_GUIDE.md`

and

`docs/governance/mvp/MVP-08_HUMAN_UAT_RESULTS.md`

Remove the Journey-3 blocker wording only after current technical Journey 3 evidence passes.

Keep every Human result:

`NOT_EXECUTED`

Do not populate PASS.

The guide should become executable for all 15 scenarios.

---

# 19. Completion Report

Update:

`docs/governance/mvp/MVP-08_COMPLETION_REPORT.md`

Preserve the original blocked attempt as historical evidence.

Add a clearly dated continuation section documenting:

- Human Product Decision;
- three successor policies;
- old/new versions and dates;
- tenant selection;
- preflight;
- Journey-3 execution;
- negative self-approval tests;
- browser evidence;
- outputs;
- source lineage;
- financial boundary;
- leakage sweep;
- demo idempotency;
- regression attribution.

Do not rewrite history to pretend the original blocker never happened.

---

# 20. Regression

Run focused and affected regression for the actual continuation blast radius:

- policy versioning/selection;
- RFQ admissibility;
- comparison;
- award;
- PO;
- GRN;
- Inventory;
- Product Surface;
- authorization;
- XLSX;
- Print.

Do not require an unrelated entire Full-ERP test suite to be green.

Attribute every failure.

Any attributable MVP-08 defect must be fixed or reported as a blocker.

---

# 21. Final Required Status

If the continuation succeeds, report exactly:

`RFQ POLICY SUCCESSORS: PASS`

`RFQ POLICY HISTORICAL PRESERVATION: PASS`

`RFQ POLICY TENANT SELECTION: PASS`

`SELF-APPROVAL DENIALS: PASS`

`JOURNEY 3 — PROCUREMENT/INVENTORY E2E: PASS`

`JOURNEY 3 SOURCE LINEAGE: PASS`

`JOURNEY 3 QUANTITY CONSERVATION: PASS`

`INVENTORY EXPLICIT POST/REVERSAL: PASS`

`JOURNEY 3 FINANCIAL BOUNDARY: PASS`

`JOURNEY 3 TECHNICAL LEAKAGE: PASS`

`DEMO STATES: PASS`

`DEMO STATE IDEMPOTENCY: PASS`

`P0 OUTPUTS FROM COHERENT DEMO: PASS`

`TENANT / PERMISSION ISOLATION: PASS`

Then recompute the overall MVP-08 technical gates.

If all technical gates pass and no attributable blocking MVP defect remains:

`MVP-08 TECHNICAL VERIFICATION: PASS`

`ATTRIBUTABLE BLOCKING MVP DEFECTS: 0`

`HUMAN UAT PACKAGE: READY`

`HUMAN UAT: PENDING`

`MVP-08 READY FOR HUMAN UAT`

Do not state:

`MVP-08 COMPLETE`

until the Product Owner actually executes and accepts Human UAT.

---

# 22. Stop Boundary

After reaching `MVP-08 READY FOR HUMAN UAT`:

STOP.

Do not perform Human acceptance.

Do not issue Production Certification or Cutover.

Do not start Post-MVP work.

No commit.
No push.