# BONIRA Form Standardization Rollout

2026-11-05. Local main at 59f2fde64fc3684f09871b82a2b1945905c28aab. Ready for visual review.

## Standards and references

[UI guidelines sections 14.3 and 14.4](E:/Construction_Company_Solution/docs/ui-guidelines.md) and [component reuse guides](E:/Construction_Company_Solution/templates/components/README.md).

Compact Form uses the Product Owner-approved direction. The Sectioned Form uses the supplied visual board and awaits separate Product Owner review. Individual migrated pages are ready for visual review.

- [Compact visual reference](E:/Construction_Company_Solution/docs/compact-form-reference.png)
- [Compact specification](E:/Construction_Company_Solution/docs/compact-form-specification.png)
- [Preserved Sectioned visual reference](E:/Construction_Company_Solution/docs/sectioned-form-reference.png)

## Migrated routes

25 Compact Form routes and 5 Sectioned Form routes were migrated. Warehouse Create remains the implementation reference. Warehouse and Expense have no existing Edit endpoint in this branch, so no new route was introduced.

| Pattern | Existing route |
| --- | --- |
| Compact Form | `parties:create` |
| Compact Form | `materials:material_create` |
| Compact Form | `materials:category_create` |
| Compact Form | `materials:unit_create` |
| Compact Form | `projects:create` |
| Compact Form | `projects:site_create` |
| Compact Form | `projects:phase_create` |
| Sectioned Form | `expenses:create` |
| Sectioned Form | `expenses:draft_create` |
| Compact Form | `expenses:category_create` |
| Sectioned Form | `daily_reports:create` |
| Compact Form | `workforce:work_team_create` |
| Compact Form | `timekeeping:calendar_create` |
| Compact Form | `timekeeping:holiday_create` |
| Compact Form | `timekeeping:shift_create` |
| Compact Form | `timekeeping:shift_break_create` |
| Compact Form | `equipment:create` |
| Compact Form | `equipment:assignment_create` |
| Compact Form | `equipment:meter_reading_create` |
| Compact Form | `equipment:usage_create` |
| Compact Form | `equipment:fuel_create` |
| Compact Form | `equipment:maintenance_plan_create` |
| Compact Form | `equipment:work_order_create` |
| Compact Form | `equipment:operator_qualification_create` |
| Compact Form | `equipment:downtime_create` |
| Sectioned Form | `safety:create` |
| Sectioned Form | `quality:create` |
| Compact Form | `materials:category_detail` |
| Compact Form | `materials:material_detail` |
| Compact Form | `expenses:category_detail` |

## Exclusions

The [route inventory](E:/Construction_Company_Solution/output/form-standardization/mvp-entrypoints.json) records every candidate and its disposition. It includes the detail routes that also host edit forms and settings/upload workspaces whose names do not contain Create/Edit.

| Forms or workspaces retained | Reason |
| --- | --- |
| Contract Create and Estimate Create | Separate reference patterns and inherited business-parent presentation |
| Procurement request/order/receipt/RFQ, stock custody/count/transfer/movement, claims and payable measurements | Transaction or version workspaces with line items and source authority |
| Contractual records, guarantees, compliance evidence, retention, tax invoices, Equipment cost policy/rate/allocation/handoff/reversal/reconciliation | Specialized financial, source and lifecycle commands |
| Equipment multi-source maintenance record and work-order spare/evidence links | Maintenance and linked-source workspaces |
| Workforce field Create/Edit, employee registration, employee profile image, contextual workforce assignment, attendance/correction/leave/overtime/timesheet | Existing identity, conditional-assignment and operational workflows |
| Field observations, field evidence/proposals, inline daily-report entries | Field capture and parent-detail workspaces |
| Membership/account/settings/password forms, DMS uploads/version/link/evidence, project gallery/WBS/activity and workflow configuration | Identity administration, file handling, inline actions or specialized editors |
| MVP-hidden capabilities | Product Surface exposure excludes rollout |

## Implementation

Compact pages reuse one base and one form card. Sectioned pages reuse the same header foundation, existing controls, validation and footer, with a field-group profile and a small opt-in stylesheet. The card receives CSRF explicitly. Read-only material/category editors retain disabled fields and omit Save.

Page form fields remain independent of global context. Existing widgets, native choices, searchable work-team selectors, date and money helpers, parent metadata, hidden keys and ordinary browser validation remain authoritative. The Equipment meter and correction selectors now display record names, values and dates instead of an internal object label.

Sectioned groups remain expanded. There are no illustration-derived uploads, statuses or calculations. Each visible field is rendered once, and any future additional field falls into the final Details section.

Views changed only to select the relevant template. No model, migration, permission, business service, workflow or Product Surface file was modified.

## Verification

139 successful real Chrome scenarios across the final batch manifests. Zero horizontal overflow results. Compact pages were checked at 1440 and 390 px. Sectioned pages were checked at 1440, 1024 and 390 px.

Checks covered initial rendering, required errors, date normalization/value retention, successful submissions, Cancel navigation, disabled/read-only editors, denied users, project restrictions, Tab order, source-choice dependencies and single in-flow action areas. Save ran against existing services in the isolated test database.

| Focused check | Result and evidence |
| --- | --- |
| Compact calendar masters | PASS in [calendar batch](E:/Construction_Company_Solution/output/compact-form-rollout/verified-tests.xml) for `test_calendar_forms`. The earlier Create/Edit case failure in that file was superseded by the next row. |
| Compact Create/Edit and read-only access | PASS with 26 subtests in [Create/Edit recheck](E:/Construction_Company_Solution/output/compact-form-rollout/create-edit-recheck.txt) |
| Expense Create and draft pilot | PASS in [Expense pilot](E:/Construction_Company_Solution/output/sectioned-form-rollout/expense-pass.txt) |
| Safety, Quality, Daily Report and additional Equipment forms | 2/2 PASS in [remaining forms check](E:/Construction_Company_Solution/output/form-standardization/remaining-tests.txt) |
| Existing Expense context explanation and work-team hierarchy | 2 existing tests PASS in [boundary checks](E:/Construction_Company_Solution/output/sectioned-form-rollout/adoption-tests.xml). The third failed browser case in that earlier file was superseded by the preceding row. |
| Warehouse/Contract footer regression | PASS in [footer regression](E:/Construction_Company_Solution/output/form-standardization/footer-regression.txt) |
| Django system checks, Ruff lint/format, JavaScript syntax and git whitespace | PASS |

Warehouse Create viewport screenshots remained byte-identical to the pre-rollout context-alignment captures at 1440, 1024 and 390 px. Contract Create retains its sticky footer. The accepted Contracts and Warehouse List templates were not modified.

## Screenshots

| Page | Desktop | Mobile |
| --- | --- |
| Material Create | [1440 px](E:/Construction_Company_Solution/output/compact-form-rollout/b1-owner-material-1440-viewport.png) | [390 px](E:/Construction_Company_Solution/output/compact-form-rollout/b1-owner-material-390-viewport.png) |
| Work Team | [1440 px](E:/Construction_Company_Solution/output/compact-form-rollout/b1-owner-team-1440-viewport.png) | [390 px](E:/Construction_Company_Solution/output/compact-form-rollout/b1-owner-team-390-viewport.png) |
| Equipment meter reading | [1440 px](E:/Construction_Company_Solution/output/compact-form-rollout/b1-owner-equipment-meter_reading_create-1440-viewport.png) | [390 px](E:/Construction_Company_Solution/output/compact-form-rollout/b1-owner-equipment-meter_reading_create-390-viewport.png) |
| Expense | [1440 px](E:/Construction_Company_Solution/output/sectioned-form-rollout/b1-owner-expense-1440-viewport.png) / [1024 px](E:/Construction_Company_Solution/output/sectioned-form-rollout/b1-owner-expense-1024-viewport.png) | [390 px](E:/Construction_Company_Solution/output/sectioned-form-rollout/b1-owner-expense-390-viewport.png) |
| Expense draft | [1440 px](E:/Construction_Company_Solution/output/sectioned-form-rollout/b1-owner-expense-draft-1440-viewport.png) / [1024 px](E:/Construction_Company_Solution/output/sectioned-form-rollout/b1-owner-expense-draft-1024-viewport.png) | [390 px](E:/Construction_Company_Solution/output/sectioned-form-rollout/b1-owner-expense-draft-390-viewport.png) |
| Safety Incident | [1440 px](E:/Construction_Company_Solution/output/sectioned-form-rollout/b1-owner-safety-1440-viewport.png) / [1024 px](E:/Construction_Company_Solution/output/sectioned-form-rollout/b1-owner-safety-1024-viewport.png) | [390 px](E:/Construction_Company_Solution/output/sectioned-form-rollout/b1-owner-safety-390-viewport.png) |
| Quality Issue | [1440 px](E:/Construction_Company_Solution/output/sectioned-form-rollout/b1-owner-quality-1440-viewport.png) / [1024 px](E:/Construction_Company_Solution/output/sectioned-form-rollout/b1-owner-quality-1024-viewport.png) | [390 px](E:/Construction_Company_Solution/output/sectioned-form-rollout/b1-owner-quality-390-viewport.png) |
| Daily Report | [1440 px](E:/Construction_Company_Solution/output/sectioned-form-rollout/b1-owner-daily-report-1440-viewport.png) / [1024 px](E:/Construction_Company_Solution/output/sectioned-form-rollout/b1-owner-daily-report-1024-viewport.png) | [390 px](E:/Construction_Company_Solution/output/sectioned-form-rollout/b1-owner-daily-report-390-viewport.png) |

[Safety field-error full page](E:/Construction_Company_Solution/output/sectioned-form-rollout/b1-owner-safety-validation-full.png) and [Daily Report field-error full page](E:/Construction_Company_Solution/output/sectioned-form-rollout/b1-owner-daily-report-validation-full.png). All per-route captures and scenario manifests are retained in the batch folders.

## Remaining finding and limits

An existing Expense mismatch accepts arbitrary active platform groups as form choices, while the model still restricts `category` to legacy codes. A synthetic `sectioned` group was displayed and rejected during Save. [Browser evidence](E:/Construction_Company_Solution/output/sectioned-form-rollout/baseline-custom-group-rejection.png). The same form/model code is unchanged from HEAD. This backend semantics issue requires separate authorization. Expense submissions with a canonical `materials` group passed for both entry points.

The retained test database lacked the Safety/Quality compatibility templates after fixture flushing. The browser fixture now restores the exact code-owned compatibility configurations, following the existing HSE scope-test convention. This is test-only setup.

Browser verification uses headless installed Chrome with device dimensions and synthetic records. A physical mobile device and its native on-screen keyboard were not tested. Excluded workspaces have not been visually reverified by this rollout.

## Exact incremental files

- [apps/accounts/static/css/erp_create_form.css](E:/Construction_Company_Solution/apps/accounts/static/css/erp_create_form.css)
- [apps/accounts/static/css/erp_sectioned_form.css](E:/Construction_Company_Solution/apps/accounts/static/css/erp_sectioned_form.css)
- [apps/accounts/templatetags/form_layouts.py](E:/Construction_Company_Solution/apps/accounts/templatetags/form_layouts.py)
- [apps/equipment/forms.py](E:/Construction_Company_Solution/apps/equipment/forms.py)
- [apps/equipment/views.py](E:/Construction_Company_Solution/apps/equipment/views.py)
- [apps/timekeeping/views.py](E:/Construction_Company_Solution/apps/timekeeping/views.py)
- [apps/workforce/views.py](E:/Construction_Company_Solution/apps/workforce/views.py)
- [docs/ui-guidelines.md](E:/Construction_Company_Solution/docs/ui-guidelines.md)
- [docs/sectioned-form-reference.png](E:/Construction_Company_Solution/docs/sectioned-form-reference.png)
- [scripts/verification/mvp02_browser.mjs](E:/Construction_Company_Solution/scripts/verification/mvp02_browser.mjs)
- [templates/components/README.md](E:/Construction_Company_Solution/templates/components/README.md)
- [templates/components/form_footer.html](E:/Construction_Company_Solution/templates/components/form_footer.html)
- [templates/components/compact_form_page.html](E:/Construction_Company_Solution/templates/components/compact_form_page.html)
- [templates/components/compact_form_card.html](E:/Construction_Company_Solution/templates/components/compact_form_card.html)
- [templates/components/sectioned_form_page.html](E:/Construction_Company_Solution/templates/components/sectioned_form_page.html)
- [templates/components/sectioned_form_fields.html](E:/Construction_Company_Solution/templates/components/sectioned_form_fields.html)
- [templates/materials/unit_form.html](E:/Construction_Company_Solution/templates/materials/unit_form.html)
- [templates/materials/category_form.html](E:/Construction_Company_Solution/templates/materials/category_form.html)
- [templates/materials/material_form.html](E:/Construction_Company_Solution/templates/materials/material_form.html)
- [templates/expenses/category_form.html](E:/Construction_Company_Solution/templates/expenses/category_form.html)
- [templates/expenses/create.html](E:/Construction_Company_Solution/templates/expenses/create.html)
- [templates/parties/form.html](E:/Construction_Company_Solution/templates/parties/form.html)
- [templates/projects/create.html](E:/Construction_Company_Solution/templates/projects/create.html)
- [templates/projects/site_create.html](E:/Construction_Company_Solution/templates/projects/site_create.html)
- [templates/projects/phase_create.html](E:/Construction_Company_Solution/templates/projects/phase_create.html)
- [templates/equipment/create.html](E:/Construction_Company_Solution/templates/equipment/create.html)
- [templates/workforce/work_team_create.html](E:/Construction_Company_Solution/templates/workforce/work_team_create.html)
- [templates/timekeeping/compact_form.html](E:/Construction_Company_Solution/templates/timekeeping/compact_form.html)
- [templates/safety/create.html](E:/Construction_Company_Solution/templates/safety/create.html)
- [templates/quality/create.html](E:/Construction_Company_Solution/templates/quality/create.html)
- [templates/daily_reports/create.html](E:/Construction_Company_Solution/templates/daily_reports/create.html)
- [tests/test_compact_form_rollout.py](E:/Construction_Company_Solution/tests/test_compact_form_rollout.py)
- [tests/test_sectioned_form_rollout.py](E:/Construction_Company_Solution/tests/test_sectioned_form_rollout.py)

The pre-existing local Warehouse pilot, its selector enhancements, shared context component changes, reference images and earlier evidence were preserved. Those inherited local changes remain uncommitted alongside this rollout.

No commit or push was performed. No individual page has been marked Product Owner Accepted.
