# BONIRA UI/UX Full Audit Checkpoint 08

## Baseline

`main @ 43ac319c6e73e48ca9626461b73987922c498ec3`

## Progress

- Static screen candidates: **383**
- Static-reviewed routed surfaces: **93**
- Findings: **103**
- HIGH: **73**
- MEDIUM: **30**
- CRITICAL: **0**
- Root patterns: **25**
- Positive internal reference patterns: **16**
- Findings requiring domain review: **0**

No remediation has been authorized or executed.

## Coverage direction

This checkpoint intentionally adds almost no new root-pattern families. The systemic taxonomy is stable enough that the audit is now primarily expanding the affected-surface map and identifying reusable internal patterns.

## Equipment

The cost workspace confirms several previously identified patterns at once:

- `P8` delivery metadata is visible in runtime UI;
- occurrence/consumer identifiers are shown directly;
- Project Cost is mixed into Persian UI;
- audit/integration boundary wording dominates the page.

The maintenance list also strengthens the Jalali-display finding because scheduled dates are rendered directly.

## Workforce

The Workforce area contains an important contrast.

The Foundation workspace still uses tenancy/permission/boundary language in ordinary HR copy.

However, Department and Position structures are among the strongest visual surfaces in BONIRA:

- tree/list dual presentation;
- search/filter controls;
- details drawer;
- zoom/fullscreen for organization structure;
- actionable empty states.

This is now preserved as:

`REF-P15-WORKFORCE-ORG_CHART`

It is particularly relevant to the future Home/Dashboard redesign because it proves BONIRA can already deliver a more polished, product-specific visual language than generic card grids.

## Knowledge

Published knowledge currently mixes article consumption with authority metadata, manifest hash and non-standard `form.as_p` actions.

The dedicated History page is conceptually the correct place for provenance, but even there several outcomes/source fields remain raw canonical values.

The audit recommendation is therefore not to remove traceability. It is to keep the separate history/audit surface and improve its human-readable representation.

## Billing payable

Payable Measurement/Certificate forms confirm that the Billing Jalali-input inconsistency extends beyond guarantees/compliance forms.

They also use a local form renderer and generic «ثبت» CTA, strengthening the case for one canonical form system.

## Treasury

The Operations page is more task-oriented than the older workbench surfaces, but retained advance-reconciliation evidence and hash information still leak into the operational view.

## Shared tables

`table_pagination.html` already demonstrates query-preserving pagination through `pagination_query`.

This is now `REF-P16-SHARED-PAGINATION_QUERY_PRESERVATION` and should be reused to remediate the previously identified `bounded_table_pagination.html` query-state-loss defect.

## Next milestone

One additional static batch should be enough to prepare the first **Static Audit Coverage Review**.

Priority remaining static coverage:

- remaining Billing statutory/payable details;
- Treasury account/posting/reconciliation forms;
- Workforce position/team/detail/form variants;
- Equipment cost/maintenance form variants;
- Knowledge candidate/promotion corrections;
- shared row-action/detail-link conventions and error/unauthorized states.

After that:

1. produce Static Audit Coverage Review;
2. classify uncovered surfaces by representative-pattern equivalence versus runtime-required review;
3. generate `UIUX_RUNTIME_VALIDATION_MATRIX.yaml`;
4. define role/journey/browser/accessibility runtime scenarios;
5. still do not authorize remediation until the validation plan is frozen.
