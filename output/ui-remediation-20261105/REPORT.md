# BONIRA — Requested UI and Daily Report remediations

Status: ready for visual review. Product Owner visual acceptance has not been issued by the agent. Local main HEAD: 59f2fde64fc3684f09871b82a2b1945905c28aab. No commit or push was performed.

The user explicitly authorized the bounded report-reference schema/permission extension after reviewing the proposal. All earlier unrelated uncommitted rollout work is retained.

## Result

- Main navigation opens `/equipment/` as «تجهیزات». Operations is reached within that section and links back to the master list. «ثبت تجهیز جدید» belongs to the master list and is absent from Operations. An operations-only reader retains an authorized menu fallback. The same central navigation metadata feeds desktop/mobile/Home/module selection; capability exposure and permission enforcement remain separate.
- Materials, Material Categories and Equipment reuse the same operational-list template as Safety: application context header, breadcrumbs, page heading/action, filter workspace, chips, result count/sort, responsive rows, empty states and pagination. Existing material/equipment parameters and XLSX behavior remain. Category search/sort/pagination use the existing tenant-scoped query and list helpers. Existing archive actions remain accessible in viewport-positioned row menus.
- Work Teams retains its permission-aware sibling navigation. The current section is a label rather than a self-link button; New Team uses the standard page-header action position.
- Daily Report Create retains safety/quality notes and adds searchable multiple references plus existing-document selection and one optional new DMS upload. Further documents can be added with the existing Detail-page DMS actions.
- `DailyReportRecordReference` is tenant-owned, append-only, UUID identified and audited. Records must match report project/site/phase and be readable. Reviewed/closed sources, their original report FK and their workflows remain untouched. One source can be referenced by several reports.
- `daily_reports.link_records` is registered and explicitly enforced alongside report creation and source read access. Built-in default roles already allowed to create reports receive it; tenant custom roles retain their explicit grants. Document operations retain the existing DMS view/upload/source checks, versioning, quarantine and byte ownership. The whole initial report and all associations commit atomically; failed uploads roll back data and remove generated files.

## Validation

- Focused navigation/list and Product Surface regression: 20 tests + 14 subtests PASS. [JUnit](E:/Construction_Company_Solution/output/list-navigation-remediation/verified-tests.xml).
- Focused report-reference, permission-code uniqueness and database catalogue checks: 11 tests + 4 subtests PASS. [JUnit](E:/Construction_Company_Solution/output/daily-report-association/verified-tests.xml).
- 41 successful real installed-Chrome scenarios on an isolated PostgreSQL live server. Configured widths: 1440, 1024 and 390px; zero page-level horizontal overflow. [Scenario manifest](E:/Construction_Company_Solution/output/ui-remediation-20261105/browser-manifest.json).
- Browser journeys cover equipment list → Operations → list → Create, permission-restricted controls, shared row-menu usability, filtering/empty results/Clear, Back/Forward/refresh, actual remote multiple selection, validation/value retention, actual report submission with an existing document and a new uploaded PDF, persisted Detail references and mobile Cancel. Native fallback refresh and submission validation are covered with HTTP tests; native mobile-keyboard behavior was not manually exercised.
- Ruff lint/format, JavaScript syntax, Django system checks, migration-state drift check and `git diff --check`: PASS.
- Authorized additive migrations were applied only to local development PostgreSQL `construction_erp` at `127.0.0.1`, with DEBUG/development assertions: organizations 0126, daily_reports 0007, audit 0056. [Migration log](E:/Construction_Company_Solution/output/daily-report-association/local-migrations.txt).

## Before / after evidence

List before captures were taken at 1440px in this remediation. After captures are at all three widths. The Daily Report before images below are explicitly the earlier Sectioned rollout baseline, not a new before capture.

| Page | Before | 1440 | 1024 | 390 |
|---|---|---|---|---|
| Materials | [Before](E:/Construction_Company_Solution/output/list-navigation-remediation/before/b1-owner-materials-1440-viewport.png) | [1440](E:/Construction_Company_Solution/output/list-navigation-remediation/after/b1-owner-materials-1440-viewport.png) | [1024](E:/Construction_Company_Solution/output/list-navigation-remediation/after/b1-owner-materials-1024-viewport.png) | [390](E:/Construction_Company_Solution/output/list-navigation-remediation/after/b1-owner-materials-390-viewport.png) |
| Categories | [Before](E:/Construction_Company_Solution/output/list-navigation-remediation/before/b1-owner-categories-1440-viewport.png) | [1440](E:/Construction_Company_Solution/output/list-navigation-remediation/after/b1-owner-categories-1440-viewport.png) | [1024](E:/Construction_Company_Solution/output/list-navigation-remediation/after/b1-owner-categories-1024-viewport.png) | [390](E:/Construction_Company_Solution/output/list-navigation-remediation/after/b1-owner-categories-390-viewport.png) |
| Equipment | [Before](E:/Construction_Company_Solution/output/list-navigation-remediation/before/b1-owner-equipment-1440-viewport.png) | [1440](E:/Construction_Company_Solution/output/list-navigation-remediation/after/b1-owner-equipment-1440-viewport.png) | [1024](E:/Construction_Company_Solution/output/list-navigation-remediation/after/b1-owner-equipment-1024-viewport.png) | [390](E:/Construction_Company_Solution/output/list-navigation-remediation/after/b1-owner-equipment-390-viewport.png) |
| Work Teams | [Before](E:/Construction_Company_Solution/output/list-navigation-remediation/before/b1-owner-teams-1440-viewport.png) | [1440](E:/Construction_Company_Solution/output/list-navigation-remediation/after/b1-owner-teams-1440-viewport.png) | [1024](E:/Construction_Company_Solution/output/list-navigation-remediation/after/b1-owner-teams-1024-viewport.png) | [390](E:/Construction_Company_Solution/output/list-navigation-remediation/after/b1-owner-teams-390-viewport.png) |
| Operations | [Before](E:/Construction_Company_Solution/output/list-navigation-remediation/before/b1-owner-equipment-operations-1440-viewport.png) | [1440](E:/Construction_Company_Solution/output/list-navigation-remediation/after/b1-owner-equipment-operations-1440-viewport.png) | [1024](E:/Construction_Company_Solution/output/list-navigation-remediation/after/b1-owner-equipment-operations-1024-viewport.png) | [390](E:/Construction_Company_Solution/output/list-navigation-remediation/after/b1-owner-equipment-operations-390-viewport.png) |
| Safety reference | [Before](E:/Construction_Company_Solution/output/list-navigation-remediation/before/b1-owner-safety-reference-1440-viewport.png) | [1440](E:/Construction_Company_Solution/output/list-navigation-remediation/after/b1-owner-safety-reference-1440-viewport.png) | [1024](E:/Construction_Company_Solution/output/list-navigation-remediation/after/b1-owner-safety-reference-1024-viewport.png) | [390](E:/Construction_Company_Solution/output/list-navigation-remediation/after/b1-owner-safety-reference-390-viewport.png) |

| Daily Report evidence | 1440 | 1024 | 390 |
|---|---|---|---|
| Initial viewport | [1440](E:/Construction_Company_Solution/output/daily-report-association/browser/b1-owner-daily-create-1440-viewport.png) | [1024](E:/Construction_Company_Solution/output/daily-report-association/browser/b1-owner-daily-create-1024-viewport.png) | [390](E:/Construction_Company_Solution/output/daily-report-association/browser/b1-owner-daily-create-390-viewport.png) |
| Related-record section | [1440](E:/Construction_Company_Solution/output/daily-report-association/browser/b1-owner-daily-references-section-1440-viewport.png) | [1024](E:/Construction_Company_Solution/output/daily-report-association/browser/b1-owner-daily-references-section-1024-viewport.png) | [390](E:/Construction_Company_Solution/output/daily-report-association/browser/b1-owner-daily-references-section-390-viewport.png) |
| Selected values after server error | [1440](E:/Construction_Company_Solution/output/daily-report-association/browser/b1-owner-daily-selection-validation-1440-viewport.png) | [1024](E:/Construction_Company_Solution/output/daily-report-association/browser/b1-owner-daily-selection-validation-1024-viewport.png) | [390](E:/Construction_Company_Solution/output/daily-report-association/browser/b1-owner-daily-selection-validation-390-viewport.png) |

Earlier Daily Report baseline: [1440](E:/Construction_Company_Solution/output/sectioned-form-rollout/b1-owner-daily-report-1440-full.png) · [1024](E:/Construction_Company_Solution/output/sectioned-form-rollout/b1-owner-daily-report-1024-full.png) · [390](E:/Construction_Company_Solution/output/sectioned-form-rollout/b1-owner-daily-report-390-full.png).

Full-page form captures: [1440](E:/Construction_Company_Solution/output/daily-report-association/browser/b1-owner-daily-create-1440.png) · [1024](E:/Construction_Company_Solution/output/daily-report-association/browser/b1-owner-daily-create-1024.png) · [390](E:/Construction_Company_Solution/output/daily-report-association/browser/b1-owner-daily-create-390.png).

Persisted references/documents: [Desktop](E:/Construction_Company_Solution/output/daily-report-association/browser/b1-owner-daily-linked-records-1440-viewport.png) · [Mobile](E:/Construction_Company_Solution/output/daily-report-association/browser/b1-owner-daily-linked-records-390-viewport.png).

Restricted actor: [Report Create](E:/Construction_Company_Solution/output/daily-report-association/browser/b1-reader-daily-restricted-create-viewport.png).

## Remaining findings and boundaries

- Broader pre-existing suites are not green: 12 legacy DailyReportServiceTests fail in setup at project creation because their old fixture lacks current explicit authorization assignments; 3 registry-architecture tests report existing duplicate Payroll registrations, unrelated enforcement declarations and namespace mismatches. These failures are outside this bounded change and are retained, not silently repaired. [Run](E:/Construction_Company_Solution/output/daily-report-association/final-tests.xml) · [HEAD/source attribution](E:/Construction_Company_Solution/output/daily-report-association/baseline-findings.json).
- The broader-run browser failure was caused by the retained live-server seed omitting the additive permission; the task fixture now restores the canonical catalogue and the final focused browser run passes. Earlier failed diagnostic artifacts remain historical and are superseded by the `verified-tests` results.
- Concurrent edits to the Operations workspace, its new `_operations_action.html` / `_operations_summary.html` helpers, its workspace tests and generated Tailwind CSS were observed and preserved. Their redesign is not claimed as this agent’s work. Navigation was retested against the resulting current template.
- Contracts List, Warehouse List and Safety List source designs remain unchanged. No native-mobile-keyboard claim, production action or automatic Product Owner acceptance is made.

## Files changed for these requests

Navigation and lists (some files also retain earlier authorized rollout changes):

- [core/product_surface.py](E:/Construction_Company_Solution/core/product_surface.py)
- [apps/accounts/templatetags/reference_lists.py](E:/Construction_Company_Solution/apps/accounts/templatetags/reference_lists.py)
- [apps/accounts/static/js/erp_filter_bar.js](E:/Construction_Company_Solution/apps/accounts/static/js/erp_filter_bar.js)
- [apps/materials/views.py](E:/Construction_Company_Solution/apps/materials/views.py)
- [apps/equipment/views.py](E:/Construction_Company_Solution/apps/equipment/views.py)
- [templates/components/operational_list.html](E:/Construction_Company_Solution/templates/components/operational_list.html)
- [templates/components/filter_bar.html](E:/Construction_Company_Solution/templates/components/filter_bar.html)
- [templates/components/list_detail_action.html](E:/Construction_Company_Solution/templates/components/list_detail_action.html)
- [templates/materials/material_list.html](E:/Construction_Company_Solution/templates/materials/material_list.html)
- [templates/materials/category_list.html](E:/Construction_Company_Solution/templates/materials/category_list.html)
- [templates/equipment/list.html](E:/Construction_Company_Solution/templates/equipment/list.html)
- [templates/equipment/operations_workbench.html](E:/Construction_Company_Solution/templates/equipment/operations_workbench.html)
- [apps/workforce/templatetags/field_journey.py](E:/Construction_Company_Solution/apps/workforce/templatetags/field_journey.py)
- [apps/workforce/templates/workforce/_field_navigation.html](E:/Construction_Company_Solution/apps/workforce/templates/workforce/_field_navigation.html)
- [apps/workforce/templates/workforce/field_team_list.html](E:/Construction_Company_Solution/apps/workforce/templates/workforce/field_team_list.html)
- [tests/test_list_navigation_remediation.py](E:/Construction_Company_Solution/tests/test_list_navigation_remediation.py)
- [tests/test_compact_form_rollout.py](E:/Construction_Company_Solution/tests/test_compact_form_rollout.py)

Daily Report functionality, shared widget/readability and evidence tooling:

- [apps/daily_reports/models.py](E:/Construction_Company_Solution/apps/daily_reports/models.py)
- [apps/daily_reports/reference_forms.py](E:/Construction_Company_Solution/apps/daily_reports/reference_forms.py)
- [apps/daily_reports/references.py](E:/Construction_Company_Solution/apps/daily_reports/references.py)
- [apps/daily_reports/views.py](E:/Construction_Company_Solution/apps/daily_reports/views.py)
- [apps/daily_reports/urls.py](E:/Construction_Company_Solution/apps/daily_reports/urls.py)
- [apps/daily_reports/migrations/0007_report_record_references.py](E:/Construction_Company_Solution/apps/daily_reports/migrations/0007_report_record_references.py)
- [apps/audit/models.py](E:/Construction_Company_Solution/apps/audit/models.py)
- [apps/audit/migrations/0056_daily_report_reference_action.py](E:/Construction_Company_Solution/apps/audit/migrations/0056_daily_report_reference_action.py)
- [apps/organizations/models.py](E:/Construction_Company_Solution/apps/organizations/models.py)
- [apps/organizations/permission_registry.py](E:/Construction_Company_Solution/apps/organizations/permission_registry.py)
- [apps/organizations/role_defaults.py](E:/Construction_Company_Solution/apps/organizations/role_defaults.py)
- [apps/organizations/migrations/0126_daily_report_record_reference_permission.py](E:/Construction_Company_Solution/apps/organizations/migrations/0126_daily_report_record_reference_permission.py)
- [templates/daily_reports/create.html](E:/Construction_Company_Solution/templates/daily_reports/create.html)
- [templates/daily_reports/detail.html](E:/Construction_Company_Solution/templates/daily_reports/detail.html)
- [templates/daily_reports/_record_references.html](E:/Construction_Company_Solution/templates/daily_reports/_record_references.html)
- [apps/accounts/templatetags/form_layouts.py](E:/Construction_Company_Solution/apps/accounts/templatetags/form_layouts.py)
- [apps/workforce/static/workforce/field_choices.css](E:/Construction_Company_Solution/apps/workforce/static/workforce/field_choices.css)
- [docs/ui-guidelines.md](E:/Construction_Company_Solution/docs/ui-guidelines.md)
- [docs/architecture/DOMAIN_AND_DATA_MODEL.md](E:/Construction_Company_Solution/docs/architecture/DOMAIN_AND_DATA_MODEL.md)
- [tests/test_daily_report_references.py](E:/Construction_Company_Solution/tests/test_daily_report_references.py)
- [scripts/verification/warehouse_list_validate.py](E:/Construction_Company_Solution/scripts/verification/warehouse_list_validate.py)
- [scripts/verification/mvp02_browser.mjs](E:/Construction_Company_Solution/scripts/verification/mvp02_browser.mjs)
