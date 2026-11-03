Continue from the current clean `main` checkpoint after MVP-06 implementation completion.

Execute:

# MVP-07 — P1 Outputs & Non-blocking Usability

## Canonical Scope

Read first:

- `ROADMAP.md`
- `docs/architecture/PRODUCT_VISION_AND_MVP_RELEASE_STRATEGY.md`
- `docs/ui-guidelines.md`
- `design/BONIRA_UI_COLOR_SYSTEM.md`
- `docs/governance/mvp/MVP-02_COMPLETION_REPORT.md`
- `docs/governance/mvp/MVP-03_COMPLETION_REPORT.md`
- current MVP-04 completion evidence
- `docs/governance/mvp/MVP-05_COMPLETION_REPORT.md`
- `docs/governance/mvp/MVP-06_COMPLETION_REPORT.md`
- `docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml`
- `docs/governance/uiux/UIUX_WAVE_C_ENTRY_REVIEW.md`
- relevant current source/models/services/templates for Daily Reports, Estimates, Timekeeping and Equipment

Canonical P1 XLSX targets are:

1. Daily Reports
2. Estimates
3. Timekeeping / Equipment

MVP-07 also permits **bounded non-blocking usability remediation** on current MVP-visible surfaces only.

Do not start MVP-08.

---

# Objective

Complete the remaining P1 operational XLSX outputs and remediate a bounded set of current MVP-visible usability defects that:

- are genuinely user-facing;
- are still reproducible;
- do not require new product/domain decisions;
- do not require new authorization semantics;
- do not change business calculations/workflows;
- do not reopen hidden ERP capabilities;
- do not turn MVP-07 into a new full UI/UX audit.

---

# PART A — P1 XLSX OUTPUTS

## 1. Reuse MVP-05 Foundation

Reuse the accepted shared XLSX infrastructure created in MVP-05.

Do not create another workbook/export framework.

Preserve:

- `openpyxl`;
- shared workbook mechanics;
- RTL worksheet handling;
- typed cells;
- deterministic columns;
- safe filenames;
- formula-injection protection;
- empty-result behavior;
- shared Django response mechanics;
- tenant/permission/filter behavior.

Do not introduce another XLSX library unless a proven technical blocker exists.

---

# 2. Daily Reports XLSX

Implement the P1 operational XLSX output for the existing Daily Report domain.

Inspect the actual model and existing related records.

Include only authoritative fields that currently exist.

Where supported, suitable sheets may include:

- گزارش‌های روزانه
- فعالیت‌ها
- نیروی انسانی
- تجهیزات
- مصالح
- تأخیرها

Use existing business fields such as, where actually implemented:

- project;
- site;
- phase;
- reporting date;
- status;
- weather;
- labor count;
- work performed;
- progress summary;
- issues/delays;
- safety notes;
- quality notes;
- existing child entries.

Do not invent productivity, progress or cost calculations.

Preserve existing project/site permissions and filters.

---

# 3. Estimates XLSX

Implement the P1 operational XLSX export for current Estimates / BOQ functionality.

Inspect current Estimate models, versions, status semantics and BOQ lines.

Where supported include:

- project;
- estimate number/reference;
- title;
- version/revision;
- status;
- line description;
- unit;
- quantity;
- authoritative rate/price;
- authoritative line amount;
- authoritative existing totals.

Use persisted/versioned values where required.

Do not:

- recalculate commercial values in the export layer;
- invent contract values;
- infer tax/statutory values;
- alter Estimate approval/version semantics.

---

# 4. Timekeeping / Equipment P1 Target

Treat `Timekeeping / Equipment` as the canonical P1 target family.

Inspect both current MVP-visible domains.

Do not force them into one workbook unless that is naturally supported by current UX/business semantics.

Prefer separate operational exports where clearer:

## Timekeeping

Where currently supported include appropriate data from:

- Attendance;
- Timesheet;
- Overtime;
- worker/person;
- project;
- site;
- date;
- work hours;
- overtime;
- status.

Preserve the existing rule that Attendance, Timesheet and Overtime remain distinct backend concepts.

Do not introduce Payroll semantics.

## Equipment

Where currently supported include:

- project/site;
- equipment;
- date;
- operating hours;
- usage/log information;
- status;
- existing notes or operational values.

Do not invent:

- fuel consumption;
- depreciation;
- maintenance cost;
- ownership cost;
- productivity;
- accounting value

unless already authoritative in the current Equipment domain.

---

# 5. P1 XLSX Security and Filters

All P1 exports must preserve:

- Authentication;
- Authorization;
- tenant isolation;
- organization scope;
- project/site scope;
- Product Surface;
- existing object/domain permissions;
- current list filters.

Export the complete authorized filtered dataset before pagination where consistent with MVP-05 conventions.

Do not export records the user cannot see.

---

# 6. XLSX Verification

Reopen all generated files with `openpyxl`.

Verify:

- valid workbook;
- expected sheets;
- RTL;
- correct Persian headers;
- deterministic column order;
- authorized row counts;
- native numeric cells;
- valid date/datetime cells;
- no formulas from user input;
- no technical IDs;
- no UUID leakage;
- empty result behavior;
- current filter preservation.

Use real Chrome to verify actual downloads.

---

# PART B — NON-BLOCKING USABILITY

# 7. Usability Entry Reconciliation

Before changing UI, perform a **bounded read-only reconciliation**.

Inspect:

- current MVP-visible Product Surface;
- current UI/UX findings register;
- Wave C reconciliation;
- MVP-02 through MVP-06 completion evidence;
- actual current templates/components;
- current accepted UI standards.

Do not assume old findings are still reproducible.

For each candidate usability issue classify:

```text
CURRENT_REPRODUCIBLE
ALREADY_RESOLVED
STALE_FINDING
OUT_OF_MVP_SURFACE
REQUIRES_PRODUCT_DECISION
REQUIRES_DOMAIN_CHANGE
REQUIRES_PERMISSION_CHANGE
ELIGIBLE_MVP07_USABILITY
```

Only `ELIGIBLE_MVP07_USABILITY` may be remediated.

---

# 8. Eligible Usability Definition

A usability issue is eligible only if all are true:

1. current MVP-visible customer surface;
2. reproducible in current code/browser;
3. non-blocking;
4. user-facing;
5. bounded;
6. fixable without model/schema changes;
7. fixable without calculation/workflow changes;
8. fixable without permission/role changes;
9. fixable without new product policy;
10. consistent with current UI guidelines and shared components.

Examples of eligible classes:

- unclear business terminology;
- confusing labels/help text;
- poor action hierarchy;
- avoidable duplicate user entry;
- awkward empty state;
- poor responsive layout;
- incorrect spacing/alignment;
- inaccessible control labeling;
- inconsistent use of shared list/form/detail patterns;
- confusing confirmation text;
- missing contextual guidance;
- safe keyboard/focus/usability improvements;
- real current Module Selector presentation/usability defect if reproducible.

These are examples, not authorization to redesign every page.

---

# 9. Explicitly Ineligible Usability Work

Do not modify issues requiring:

- new roles;
- permission expansion;
- scope broadening;
- workflow redesign;
- financial/statutory policy;
- new master data;
- new business entity/model;
- hidden-module exposure;
- large navigation redesign;
- new Product Surface architecture;
- Accounting/Treasury/Payroll activation;
- unresolved specialist authorization;
- broad HR/ESS development.

Classify and document them instead.

---

# 10. Old UI Findings

Do not mechanically remediate every historical open finding.

The historical UI/UX register contains findings across modules and waves outside the current MVP surface.

MVP-07 is not permission to close the entire historical backlog.

Only fix findings that are:

- current;
- MVP-visible;
- reproducible;
- relevant;
- safe under the eligibility definition above.

Do not mark an old finding `RESOLVED` merely because nearby UI changed.

Closure requires current browser evidence.

---

# 11. Module Selector / F3-F4 Debt

MVP-05 and MVP-06 retained inherited Module Selector/F3 and obsolete F4 test findings.

Re-evaluate them now because MVP-07 includes non-blocking usability.

Distinguish:

### Actual Product Defect

If the current Module Selector still has a reproducible user-facing defect such as:

- broken horizontal scroll return;
- unusable keyboard behavior;
- viewport clipping;
- inaccessible focus behavior;

and the fix is bounded and does not alter navigation authority/Product Surface:

it may be fixed in MVP-07.

### Obsolete Test Debt

If the failure is only caused by an old test expecting pre-card navigation markup:

- update/retire the obsolete test appropriately;
- do not change the accepted UI merely to satisfy an obsolete assertion.

Do not claim full F3/F4 PASS unless current applicable tests actually pass.

---

# 12. UI Boundaries

Preserve:

- Product Surface;
- navigation authority;
- Module Selector architecture;
- working Project/Site context;
- tenant scope;
- permissions;
- F1 local/offline foundation;
- Tom Select;
- SweetAlert2;
- shared BONIRA components;
- current accepted print/XLSX foundations.

Do not introduce:

- Select2;
- new jQuery dependency;
- CDN assets;
- another navigation registry;
- another module selector;
- competing confirmation library.

---

# 13. UX Remediation Strategy

Prefer fixing shared root patterns over page-by-page duplication.

If the same issue exists on several MVP-visible screens because of one shared component:

fix the shared component once where safe.

But do not perform broad rollout without checking representative screens.

For each remediation:

```text
Finding
→ current reproduction
→ root pattern
→ shared/bounded fix
→ automated browser check
→ visual recheck
```

Do not close solely from source inspection.

---

# 14. Browser Validation

Use installed Chrome.

Validate relevant MVP-visible surfaces at:

- 1440px
- 1024px
- 390px

For changed usability areas verify:

- RTL;
- responsive behavior;
- action visibility;
- keyboard/focus where relevant;
- no horizontal overflow;
- no technical leakage;
- no broken interactions;
- no Product Surface regression.

Capture before/after evidence for material UX changes.

---

# 15. No Broad Visual Redesign

MVP-07 is not a design refresh.

Do not:

- redesign Projects;
- redesign all Lists;
- redesign dashboards;
- change branding;
- introduce a new design system;
- globally restructure navigation;
- change every historical inconsistency.

Only remediate bounded current usability defects.

---

# 16. Regression

Run focused regression for:

- Daily Reports;
- Estimates;
- Timekeeping;
- Equipment;
- shared XLSX;
- affected UI components;
- Product Surface;
- navigation;
- tenant/permission isolation.

Preserve MVP-05 XLSX behavior and MVP-06 Print behavior.

Any new attributable regression must be corrected.

Inherited unrelated baseline debt must be documented separately.

---

# 17. Completion Report

Create:

`docs/governance/mvp/MVP-07_COMPLETION_REPORT.md`

Include:

## P1 XLSX Inventory

List every implemented P1 export.

## Column / Source Mapping

For every XLSX column:

```text
Excel column
→ authoritative model/service/source
→ existing transformation
```

## Usability Reconciliation

List candidate findings with classification:

```text
Finding
Current status
MVP-visible?
Reproducible?
Eligibility
Action
Evidence
```

## Implemented Usability Fixes

For every changed issue document:

- root cause;
- exact fix;
- affected surfaces;
- before/after evidence;
- browser validation;
- regression impact.

## Deferred Findings

Clearly separate:

- outside MVP surface;
- stale;
- requires product decision;
- requires permission/domain change;
- post-MVP.

Do not silently close them.

---

# 18. Final Required Status

Report exactly:

`MVP-07: PASS/FAIL`

`P1 XLSX FOUNDATION REUSE: PASS/FAIL`

`DAILY REPORTS XLSX: PASS/FAIL`

`ESTIMATES XLSX: PASS/FAIL`

`TIMEKEEPING XLSX: PASS/FAIL/NOT-APPLICABLE`

`EQUIPMENT XLSX: PASS/FAIL/NOT-APPLICABLE`

`P1 FILTER / SCOPE CONSISTENCY: PASS/FAIL`

`P1 PERMISSION / TENANT ISOLATION: PASS/FAIL`

`P1 XLSX INTEGRITY: PASS/FAIL`

`NON-BLOCKING USABILITY RECONCILIATION: PASS/FAIL`

`ELIGIBLE CURRENT USABILITY FINDINGS: <count>`

`ELIGIBLE FINDINGS REMEDIATED: <count>`

`CURRENT VISUAL VERIFICATION: PASS/FAIL`

`TECHNICAL LEAKAGE: PASS/FAIL`

`MODULE SELECTOR CURRENT DEFECT STATUS: PASS/FIXED/DEFERRED`

`F1-F4 FOUNDATION PRESERVED: PASS/FAIL`

`MVP-05 XLSX FOUNDATION PRESERVED: PASS/FAIL`

`MVP-06 PRINT FOUNDATION PRESERVED: PASS/FAIL`

`PRODUCT OWNER VISUAL ACCEPTANCE: PENDING`

If all scoped implementation requirements pass:

`MVP-07 COMPLETE`

Stop after MVP-07.

Do not start MVP-08.

No commit.
No push.