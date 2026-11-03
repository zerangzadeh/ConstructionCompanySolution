Continue from the current clean `main` checkpoint after MVP-07 implementation completion.

Execute:

# MVP-08 — Demo States, Final MVP Verification & Human UAT Handoff

This is the final package of the approved eight-package BONIRA MVP delivery plan.

MVP-08 is primarily a **release-verification and Human-UAT preparation package**, not a new feature-development package.

Do not reopen completed MVP packages merely to improve them.

---

# 1. Canonical Sources

Read first:

- `ROADMAP.md`
- `docs/architecture/PRODUCT_VISION_AND_MVP_RELEASE_STRATEGY.md`
- `docs/ui-guidelines.md`
- `design/BONIRA_UI_COLOR_SYSTEM.md`
- `docs/governance/mvp/MVP-01_COMPLETION_REPORT.md`
- `docs/governance/mvp/MVP-02_COMPLETION_REPORT.md`
- `docs/governance/mvp/MVP-03_COMPLETION_REPORT.md`
- current MVP-04 completion evidence
- `docs/governance/mvp/MVP-05_COMPLETION_REPORT.md`
- `docs/governance/mvp/MVP-06_COMPLETION_REPORT.md`
- `docs/governance/mvp/MVP-07_COMPLETION_REPORT.md`
- `docs/governance/cep/reports/CEP-079_COMPLETION_REPORT.md`
- current Journey documentation under `docs/governance/journeys/`
- existing demo/seed commands, especially:
  - `apps/accounts/management/commands/seed_demo_data.py`
  - `apps/workforce/management/commands/seed_workforce.py`

Historical CEP/UAT evidence may be reused as supporting regression evidence, but must not substitute for current MVP verification.

---

# 2. Canonical MVP Journeys

The final MVP verification must cover these three canonical journeys:

## Journey 1 — Project & Site Operations

```text
Project
→ Site
→ Daily Report
→ Workers / Timekeeping
→ Equipment
→ Safety / Quality
```

## Journey 2 — Contract & Claims

```text
Estimate
→ Contract
→ Progress Claim
→ Adjustments / Deductions
→ Approval
→ Excel / Print
```

## Journey 3 — Procurement & Materials

```text
PR
→ RFQ
→ sourcing / supplier-selection behavior where required by the implemented domain
→ PO
→ GRN
→ Inventory
```

Use the actual current product/domain implementation.

Do not simplify away implemented sourcing/award steps merely to make the demo easier.

Do not invent automatic domain effects that do not exist.

---

# 3. MVP-08 Objectives

MVP-08 must establish:

1. repeatable realistic MVP demo starting states;
2. current browser-level E2E verification of all three canonical journeys;
3. current MVP Product Surface verification;
4. tenant/permission isolation verification;
5. output regression verification;
6. RTL/responsive/offline usability verification;
7. absence of blocking MVP defects;
8. a concise, executable Human UAT package for the Product Owner.

No Production Certification or production cutover is authorized.

---

# PART A — DEMO STATES

# 4. Demo-State Assessment

Inspect existing development-only seed/demo infrastructure before creating anything new.

Determine whether:

- `seed_demo_data`
- `seed_workforce`
- existing MVP verification fixtures
- existing journey fixtures

can safely provide the required MVP demo states.

Prefer reuse or bounded extension.

Do not automatically create another parallel demo-data framework.

However, if the existing broad ERP seed is unsuitable for repeatable MVP demonstration, create a clearly bounded MVP-specific demo mechanism rather than corrupting or overloading unrelated historical seed behavior.

Document the decision.

---

# 5. Demo-State Requirements

Demo data must be:

- Development/Test only;
- deterministic;
- repeatable;
- idempotent;
- Persian/business-readable;
- safe to rerun;
- clearly identifiable as synthetic demo data;
- usable through ordinary product screens;
- internally consistent across the three journeys.

It must not depend on random values that change business references on every run.

Use stable business identifiers where appropriate.

---

# 6. Environment Safety

Demo seeding must fail closed outside approved Development/Test environments.

Never seed Production.

Never delete or rewrite arbitrary customer data.

If reset/rebuild behavior is required, it may operate only on the explicitly owned MVP demo tenant/data namespace and must contain strong guards.

Do not use broad:

```text
delete all
truncate
flush customer database
```

behavior.

---

# 7. Use Domain Services

Use existing domain services and governed workflows for lifecycle operations wherever they exist.

Do not create impossible business states through direct database mutation merely because it is easier for a seed script.

For example:

- approvals should respect existing approval services;
- issued/versioned records should use existing lifecycle services;
- inventory posting should use existing Inventory services;
- claim approval should use current Billing workflow;
- procurement sourcing should preserve current source lineage.

Direct model creation is acceptable only where consistent with existing safe seed conventions and no lifecycle invariant is bypassed.

---

# 8. Demo Tenant and Personas

Prepare at least one coherent primary MVP demo organization and sufficient lawful personas to demonstrate:

- ordinary operational user;
- project/site user;
- procurement user;
- approver/reviewer where existing workflow requires independence;
- customer/tenant administrator where useful for surface verification.

Use existing permission architecture.

Do not create broad Superuser authority merely to make journeys pass.

Do not weaken permissions.

A second isolated tenant must exist for tenant-isolation verification.

Do not expose passwords in committed documentation or reports.

Development-only credential handling must follow existing safe project conventions.

---

# 9. Journey 1 Demo State

Prepare coherent data for one active project including:

- project;
- site;
- appropriate phase/WBS/activity context;
- field workers/workforce assignments;
- Daily Report data;
- Timekeeping context;
- Equipment and appropriate deployment/usage;
- Safety record;
- Quality record.

The data should allow an ordinary browser user to understand that all records relate to the same project/site context.

Do not fabricate unsupported workforce/payroll relationships.

Full HR and Payroll remain outside the MVP surface.

---

# 10. Journey 2 Demo State

Prepare a legitimate employer/receivable contract journey with sufficient existing domain configuration for:

- Estimate / BOQ;
- approved or otherwise valid Estimate state;
- Contract;
- Contract items;
- valid measurement/Billing baseline where required;
- work/progress evidence;
- Progress Claim;
- adjustments/deductions;
- workflow submission;
- independent approval where current domain requires it;
- XLSX export;
- Print output.

Use only actual configured contract terms and existing calculation semantics.

Do not invent:

- tax rates;
- insurance rates;
- statutory percentages;
- contract policies;
- approval authority;
- financial posting.

The Roadmap specifically requires Journey 2 demo state to use legitimate configured contract terms and valid baseline/progress/workflow state.

---

# 11. Journey 3 Demo State

Prepare a complete current Procurement/Inventory journey using actual implemented semantics:

```text
Approved PR
→ RFQ
→ commercial scope / supplier-selection configuration as required
→ supplier participation/quote state where required
→ protected opening/comparison/award where implemented
→ PO
→ GRN
→ Inventory receipt/movement
```

Preserve source lineage.

Use existing supplier/BusinessParty data.

Where partial/split award behavior is part of the current accepted domain, include at least one representative scenario if it materially improves E2E coverage.

Do not create AP, Treasury or Accounting effects.

Inventory remains sole stock authority.

---

# 12. Demo Data Verification

Verify that the demo preparation can run:

1. on a clean supported Development/Test state;
2. a second time without duplicating business records or corrupting state.

Record:

- first-run result;
- second-run result;
- created/existing counts;
- stable business references;
- any intentionally preserved state.

An idempotency claim requires actual rerun evidence.

---

# PART B — FINAL MVP TECHNICAL VERIFICATION

# 13. MVP Product Surface

Verify the default customer-facing `MVP` profile.

Confirm all intended MVP-visible capability families remain reachable where authorized:

- Project & Site Operations;
- Contract & Claims;
- Procurement & Materials;
- Shared Business Services;
- Platform Foundation.

Verify customer-facing navigation, Home, shortcuts, Module Selector and direct routes.

Hidden Full ERP capabilities must remain unavailable through the MVP customer surface.

At minimum confirm that hidden Accounting/Treasury/Payroll/full-HR/Financial capability routes do not become customer-visible merely because their backend remains active.

Do not alter Product Surface policy merely to satisfy verification.

---

# 14. FULL_ERP Boundary

`FULL_ERP` may be used only as an internal regression/verification profile where existing architecture permits it.

Do not:

- expose a customer profile switch;
- represent `FULL_ERP` as commercially ready;
- infer production readiness from backend route accessibility.

Its role in MVP-08 is regression safety only.

---

# 15. Journey 1 Browser E2E

Using real installed Chrome and ordinary UI navigation, verify:

```text
Project
→ Site
→ Daily Report
→ Workers / Timekeeping
→ Equipment
→ Safety / Quality
```

Verify actual context continuity rather than isolated page `200` responses.

Check:

- project/site identity;
- ordinary user navigation;
- create/view/update operations where safely part of current journey;
- status transitions where current UAT requires them;
- proper scoped related-object selections;
- no foreign project/site leakage;
- correct Persian/Jalali presentation;
- no technical implementation terminology.

---

# 16. Journey 2 Browser E2E

Using real Chrome verify:

```text
Estimate
→ Contract
→ Progress Claim
→ Adjustments / Deductions
→ Approval
→ XLSX
→ Print
```

Verify:

- Estimate/Contract linkage;
- correct Contract/Billing workspace;
- baseline/progress semantics;
- state-aware actions;
- claim calculation values from existing authoritative services;
- adjustments/deductions;
- independent approval where required;
- downloadable real XLSX;
- actual print preview/output;
- historical/version semantics.

Do not recalculate or reinterpret financial values in the E2E harness.

---

# 17. Journey 3 Browser E2E

Using real Chrome verify:

```text
PR
→ RFQ
→ sourcing / comparison / award as required
→ PO
→ GRN
→ Inventory
```

Verify:

- source lineage;
- quantities;
- partial/split behavior where selected for the demo;
- PO version semantics;
- GRN receipt;
- explicit Inventory handoff;
- Inventory posting/reversal behavior where part of the qualified scenario;
- no unintended financial side effects.

The journey must use ordinary customer-visible actions.

Service-only verification does not replace required browser interaction.

---

# 18. Cross-Tenant / Permission Verification

Use at least:

- authorized user in demo tenant A;
- restricted user;
- user/record from tenant B.

Verify representative routes/objects across all three journeys.

Confirm:

- hidden actions do not render;
- direct unauthorized URL access is denied;
- foreign objects are not exposed;
- exports and print outputs obey the same source authorization;
- object/project/site scope remains intact.

Do not weaken permissions to make UAT fixtures convenient.

---

# 19. Output Regression

Verify current accepted output foundations still work.

## P0 XLSX

Representative current downloads from:

- Billing;
- Procurement;
- Inventory;
- Expenses.

## P1 XLSX

Representative current downloads from:

- Daily Reports;
- Estimates;
- Timekeeping;
- Equipment.

Reopen generated XLSX files with `openpyxl`.

Do not rerun every historical test merely for ceremonial coverage if representative current verification plus affected regression gives sufficient evidence.

## Critical Print

Verify all five critical print targets still render:

- Progress Claim / Billing;
- PO;
- GRN;
- Daily Report;
- Expense/Petty Cash summary.

---

# 20. Responsive / RTL Verification

Primary complete E2E may run at desktop width.

Also perform representative current checks at:

- 1440px
- 1024px
- 390px

Across the MVP shell and key journey surfaces verify:

- RTL;
- no page-level horizontal overflow;
- usable tables/actions;
- Module Selector;
- navigation;
- dialogs;
- forms;
- Persian labels;
- mixed LTR identifiers/numbers;
- no critical clipping.

Do not require every E2E mutation to be repeated at all three widths if representative responsive verification provides equivalent evidence.

---

# 21. Offline / Local Runtime

Preserve F1-F4 frontend requirements.

Verification must fail if MVP customer journeys depend on runtime CDN/external frontend resources.

Block unexpected external requests during representative browser verification.

Preserve:

- local Tailwind;
- local fonts/icons/scripts;
- Tom Select;
- SweetAlert2;
- accepted Module Selector;
- current shared interaction foundation.

---

# 22. Technical Leakage Sweep

Perform a bounded current sweep of MVP-visible surfaces involved in the three journeys.

Critical leakage includes user-facing:

- raw UUIDs where business identifiers exist;
- idempotency keys;
- Django/model/service names;
- backend field identifiers;
- technical internal codes instead of business labels;
- framework/database terminology;
- raw permission codes;
- stack traces/debug output.

Do not expand this into hidden Full ERP cleanup.

Any critical leakage on the actual MVP journeys must be corrected before technical release readiness.

---

# 23. Blocking Defect Classification

During E2E verification classify newly discovered issues:

```text
BLOCKING_MVP_DEFECT
NON_BLOCKING_MVP_DEFECT
TEST_OR_FIXTURE_DEFECT
INHERITED_BASELINE_DEBT
REQUIRES_PRODUCT_DECISION
REQUIRES_DOMAIN_OR_PERMISSION_CHANGE
OUT_OF_MVP_SCOPE
```

A `BLOCKING_MVP_DEFECT` includes an issue that prevents an ordinary authorized user from completing a canonical journey, produces incorrect business results, creates unauthorized exposure, corrupts source lineage, or prevents required P0 output.

---

# 24. Authorized Defect Remediation

If verification finds a bounded attributable MVP defect that:

- is clearly within the already-approved MVP behavior;
- requires no new product decision;
- requires no new permission policy;
- requires no new financial/statutory policy;
- requires no architecture/domain redesign;

perform the minimum necessary correction and rerun the affected journey.

Document:

```text
Defect
→ reproduction
→ root cause
→ bounded correction
→ regression
→ E2E rerun
```

Do not stop for ordinary fixable implementation defects.

---

# 25. Mandatory Stop Conditions

Do not invent a solution if a blocking issue requires:

- new product policy;
- permission/role expansion;
- new statutory/financial rule;
- new accounting authority;
- major schema/domain redesign;
- production-only infrastructure;
- unresolved business interpretation.

Record the blocker precisely.

Technical verification cannot be marked PASS while a blocking canonical-MVP defect remains unresolved.

---

# 26. Historical CEP-079 Evidence

Read and preserve `CEP-079` evidence.

Its historical representative UAT may support regression confidence where directly relevant.

However:

- do not claim historical `44/44 PASS` proves the current MVP build;
- do not copy old results as new execution;
- do not promote hidden Full ERP scenarios into customer-facing MVP acceptance;
- do not claim Human Sign-off from CEP-079.

Current MVP-08 evidence must be generated against the current code and MVP surface.

---

# PART C — HUMAN UAT PACKAGE

# 27. Human UAT Principle

Codex/automation cannot issue Human Product Owner acceptance.

Automated browser PASS is not Human UAT.

After technical verification succeeds, prepare a concise manual UAT package for the Product Owner.

Do not mark Human UAT PASS.

---

# 28. Human UAT Guide

Create:

`docs/governance/mvp/MVP-08_HUMAN_UAT_GUIDE.md`

Design it for actual Product Owner use, not for developers.

Use approximately 12–15 concise business scenarios covering:

## Global

- Login/Home/Module Selector;
- Product Surface sanity;
- Persian/RTL usability.

## Journey 1

- Project/Site navigation;
- Daily Report;
- Workforce/Timekeeping;
- Equipment;
- Safety/Quality.

## Journey 2

- Estimate/Contract;
- Progress/Billing;
- adjustment/deduction;
- approval;
- Excel;
- Print.

## Journey 3

- PR;
- RFQ/sourcing;
- PO;
- GRN;
- Inventory.

## Cross-cutting

- restricted-user behavior;
- representative tenant isolation;
- mobile/narrow-screen usability;
- absence of obvious technical leakage.

---

# 29. UAT Scenario Format

Every Human UAT scenario must contain:

```text
Scenario ID
Business objective
Persona
Starting state
Navigation path
Exact actions
Expected business result
What to visually inspect
PASS / FAIL
Product Owner notes
Evidence reference
```

Avoid technical implementation instructions unless needed to reach the screen.

The Product Owner should not need to know Django internals to perform UAT.

---

# 30. Human UAT Effort

Keep the final Human UAT practical.

Do not require the Product Owner to repeat hundreds of automated assertions.

Automated verification owns technical depth.

Human UAT should focus on:

- business correctness;
- journey coherence;
- usability;
- terminology;
- visual quality;
- outputs;
- whether the product feels usable by the intended customer.

---

# 31. UAT Result Artifact

Create:

`docs/governance/mvp/MVP-08_HUMAN_UAT_RESULTS.md`

Initialize every scenario as:

`NOT_EXECUTED`

Provide fields for:

- result;
- notes;
- blocking/non-blocking classification;
- evidence/screenshot;
- Product Owner decision.

Do not pre-populate PASS.

---

# PART D — FINAL RELEASE-GATE ASSESSMENT

# 32. Release Gate Matrix

Create a current MVP release-gate matrix in:

`docs/governance/mvp/MVP-08_COMPLETION_REPORT.md`

Evaluate:

- MVP Product Surface;
- three canonical journeys;
- tenant/permission isolation;
- P0 XLSX;
- P1 XLSX;
- critical Print;
- responsive/RTL;
- offline frontend;
- technical leakage;
- blocking MVP defects;
- demo-state repeatability;
- Human UAT.

Clearly distinguish:

```text
TECHNICAL PASS
HUMAN PENDING
BLOCKED
NOT APPLICABLE
```

---

# 33. Earlier Product Owner Visual Acceptance

Review the status of MVP-02 through MVP-07 Human/Product Owner visual acceptance records.

Do not fabricate acceptance.

If prior package reports still state `PENDING`, carry that fact into the UAT package so the Product Owner can close relevant visual acceptance during final UAT.

A current final UAT acceptance may supersede the need for separate repeated visual sign-offs only if the Human explicitly accepts the relevant surfaces during MVP-08.

Automation cannot make that decision.

---

# 34. Regression Scope

Run focused and affected regression covering the actual MVP blast radius.

Prioritize:

- Product Surface;
- three core journeys;
- authentication/authorization/tenant isolation;
- shared XLSX;
- shared Print;
- shared frontend components.

Do not require an unrelated full Full-ERP suite to be entirely green to establish MVP technical readiness.

But:

- attribute every failure;
- do not hide failures;
- do not call inherited failures PASS;
- any failure attributable to current MVP implementation must be fixed or classified as a blocker.

---

# 35. Evidence

Retain current evidence under a bounded location such as:

`output/mvp-08/`

Include:

- demo seed first/second-run evidence;
- demo data catalog;
- browser E2E results;
- screenshots;
- output-download evidence;
- workbook integrity checks;
- print evidence;
- authorization/tenant checks;
- responsive results;
- technical-leakage sweep;
- regression attribution;
- final gate matrix.

Do not rewrite historical package evidence.

---

# 36. Explicit Boundaries

Do NOT:

- start Post-MVP work;
- expose hidden ERP modules;
- activate Accounting/Treasury/Payroll;
- create new statutory/financial rules;
- redesign Product Surface;
- start broad refactoring;
- rebuild the design system;
- introduce new workflow/business semantics;
- claim Production Certification;
- claim Production Cutover;
- claim commercial readiness beyond evidence;
- mark Human UAT PASS;
- modify CEP lifecycle merely because MVP verification passes.

MVP-08 is not Production Certification.

---

# 37. Required Technical Status

At the end of automated/technical execution report exactly:

`MVP-08 TECHNICAL VERIFICATION: PASS/FAIL/BLOCKED`

`DEMO STATES: PASS/FAIL`

`DEMO STATE IDEMPOTENCY: PASS/FAIL`

`JOURNEY 1 — PROJECT/SITE OPERATIONS E2E: PASS/FAIL`

`JOURNEY 2 — CONTRACT/BILLING E2E: PASS/FAIL`

`JOURNEY 3 — PROCUREMENT/INVENTORY E2E: PASS/FAIL`

`MVP PRODUCT SURFACE: PASS/FAIL`

`TENANT / PERMISSION ISOLATION: PASS/FAIL`

`P0 XLSX REGRESSION: PASS/FAIL`

`P1 XLSX REGRESSION: PASS/FAIL`

`CRITICAL PRINT REGRESSION: PASS/FAIL`

`RTL / RESPONSIVE: PASS/FAIL`

`OFFLINE FRONTEND: PASS/FAIL`

`CRITICAL TECHNICAL LEAKAGE: PASS/FAIL`

`ATTRIBUTABLE BLOCKING MVP DEFECTS: <count>`

`HUMAN UAT PACKAGE: READY/NOT_READY`

`HUMAN UAT: PENDING`

If technical requirements pass and there are zero unresolved attributable blocking MVP defects, state:

`MVP-08 READY FOR HUMAN UAT`

Do **not** state:

`MVP-08 COMPLETE`

until Human UAT has actually been executed and accepted by the Product Owner.

---

# 38. Stop Boundary

After preparing the Human UAT package:

STOP.

Do not automatically execute another development package.

Do not issue Human Sign-off.

Do not issue Production Certification.

Do not commit.
Do not push.

Return:

1. technical verification summary;
2. exact unresolved findings, if any;
3. demo-state summary;
4. Human UAT guide path;
5. Human UAT results path;
6. completion report path;
7. exact status `READY FOR HUMAN UAT`, `BLOCKED`, or `FAILED`.