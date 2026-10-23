# BONIRA UI/UX Pilot Audit Checkpoint 02

## Baseline

`main @ 43ac319c6e73e48ca9626461b73987922c498ec3`

## Progress

The second pilot pass expanded the audit beyond the original sample to the application shell, main navigation, project surfaces, organization access administration, ESS, inventory, equipment, fixed assets, and shared list/localization patterns.

- Static screen candidates catalogued: **383**
- Pilot-reviewed routed surfaces: **20**
- Shared components/pattern surfaces explicitly reviewed: **3**
- Findings: **29**
- HIGH: **19**
- MEDIUM: **10**
- CRITICAL: **0**
- Findings currently requiring domain review: **0**
- Confirmed root patterns: **12**

No remediation has been authorized or executed.

## New material conclusions

### 1. The inconsistency observed by the Product Owner is now source-confirmed

The list-to-detail convention is not consistent across the product:

- Project list links code and name and also adds an icon-only detail action.
- Equipment and Warehouse lists link only the name.
- Inventory count/transfer sections make the whole row-like block clickable.

This is no longer treated as anecdotal UI feedback; it is a confirmed cross-module pattern.

### 2. Main navigation has a concrete state defect

The RFQ destination can appear twice: once enabled when permission exists and once as an unconditional disabled duplicate, both using `NAV-019`.

The navigation also contains hard-disabled placeholders for capabilities that are implemented or reachable elsewhere. This makes the sidebar a poor representation of the actual product.

### 3. ESS still leaks internal source semantics

The employee dashboard renders wording such as «وضعیت منبع», raw `row.status`, «آخرین تغییر منبع» and «مشاهده در منبع». This confirms that the technical-language problem is not confined to admin or finance specialists.

### 4. Inventory, Equipment and Fixed Assets confirm the same root pattern

All three areas show the same family of issues already seen in Payroll, Procurement and Subledgers:

- boundary/governance terminology in the primary UI;
- flat command surfaces;
- weak task hierarchy;
- internal identifiers or data-model concepts shown directly;
- descriptions of what the subsystem does *not* do instead of what the user should do.

### 5. Root patterns can now be promoted

The audit has enough cross-module evidence to promote 12 patterns into `UIUX_ROOT_PATTERN_CATALOGUE.yaml`.

This still does **not** authorize remediation and still does **not** establish a domain/business-architecture defect.

## Important domain boundary

The current evidence continues to support a UI/presentation diagnosis first.

For example:

- hiding a raw Treasury Movement ID behind an authorized searchable selector should preserve the same authorized object;
- replacing ISO weekday entry with weekday choices should preserve the same canonical weekday value;
- reorganizing RFQ actions into a journey must not invent, bypass or reorder domain-valid transitions;
- simplifying fixed-asset wording must not collapse accounting authority separation.

Any proposed remediation that would change those underlying semantics must be escalated to domain review instead of being treated as a UI fix.

## Next audit phase

The pilot calibration is now sufficient to begin the **full systematic surface audit**.

Recommended execution order:

1. shared shell/components and navigation;
2. Core / Organization / Project;
3. Procurement / Materials / Inventory / Parties;
4. Accounting / Treasury / Subledgers / Expenses / Fixed Assets;
5. Workforce / Timekeeping / Payroll / ESS;
6. Equipment / Daily Reports / Safety / Quality;
7. Reporting / Compliance / Knowledge / Support / Workflow administration.

Formal remediation backlog generation should wait until each root pattern has a sufficiently complete impacted-surface map.
