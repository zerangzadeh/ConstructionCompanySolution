# B02 Project Dashboard redesign

Recorded 2026-11-12, following isolated execution on 2026-11-11–12. Target `/projects/<uuid>/`.

**IMPLEMENTED · TESTED · READY_FOR_PO_VISUAL_REVIEW**

Project Detail visual acceptance remains **PO_ACCEPTANCE_PENDING**. These statuses are not `PO_ACCEPTED`, full B02 acceptance, a live CEP lifecycle change or production certification.

## Authority and baseline

The explicit Product Owner request **BONIRA — Project Dashboard UI/UX Redesign & Implementation**, sections 1–14, authorizes this bounded follow-up and its scope decisions. The supplied `BONIRA پروژه مجتمع باغستان.png` is a visual reference. Its example amounts, names, building image and action labels are not business instructions. No separate second conversation-generated image was available as a file. The current [UI guidelines](../../../ui-guidelines.md), [color system](../../../design/BONIRA_UI_COLOR_SYSTEM.md), [design registry](../APPROVED_DESIGN_CONFORMANCE_REGISTRY.md) and [B02 remediation report](B02_REMEDIATION_REPORT.md) informed implementation. Request and reference-image SHA-256 values are in [preservation evidence](evidence/b02-project-dashboard-20261111/preservation.json).

Branch `main`, HEAD `865fa3f3f7868e81b0aafba05d2683b28fe33b1e`, local `origin/main` divergence 0/0. The repository already contained substantial B02, B03 and other uncommitted work. [Entry status](evidence/b02-project-dashboard-20261111/entry-status.txt) and [entry paths](evidence/b02-project-dashboard-20261111/entry-diff-paths.txt) distinguish that baseline. A private binary entry patch and selected original files supported comparison and failure attribution. No commit or push was performed.

## Implemented design

- Compact project identity card with status, company, code and start date, followed by the existing section navigation. A permitted current DMS project photo can populate the header. Otherwise it uses a branded layers placeholder. No synthetic building photograph was added to product assets.
- Six available management indicators, with Persian numbers, explicit units, meaningful existing destinations and permission-sensitive omission. Related-document count reuses the same authorized DMS projection as the document section. Unavailable cost remains distinct from zero.
- A prominent full-width budget section uses two horizontal bars, exact amounts, remaining amount and consumption percentage. The redundant financial chart was removed. The contract ring retains exact text values and meaningful status colors.
- Recent records retain their real type, title, status, timestamp and existing authorized detail links. The commercial summary retains existing creation and list actions. Quick access contains the nonduplicated Workforce and Timekeeping viewing destinations with project context.
- Core information retains the end date, legacy project budget field, description and authorized archive operation. Company, code, start date and estimated budget remain in the header or indicators without unnecessary repetition.
- Scoped responsive CSS uses existing BONIRA variables and shared components. KPI columns are 6/3/2 at the tested desktop/tablet/mobile widths. Panels stack on narrower screens. Existing related-document rows retain title, type, version, availability and protected actions.

The reference's hypothetical waiting-work section was not implemented because this task has no authority to invent workflow work items. Existing commercial creation actions were retained instead of adding unapproved generic actions. No responsible organizational unit is shown because no qualifying direct project field was established. Progress remains explicitly unavailable rather than displaying an inferred percentage.

## Budget and cost semantics

`Project.estimated_budget` is labeled **بودجه تخمینی**, not approved or allocated budget. Recognized actual cost continues to come from `get_project_cost_projection`, including its recognized/reversal evidence. The legacy `Project.actual_budget` remains in basic information and is not substituted for recognized cost.

The comparison uses `Decimal`, requires a positive budget and actual evidence in the organization's currency, and retains the projection's incomplete-coverage notice. Bars are normalized together to `max(budget, actual)` so neither exceeds its track. Displayed consumption remains actual/budget, including percentages above 100. The exact server-rendered values remain usable without JavaScript. Commitment, open/released commitment, accrual and actual retain separate labels in expandable source evidence. This does not create cash/payment or accounting-recognition authority.

| Exercised state | Observed behavior |
|---|---|
| Positive budget and actual | PostgreSQL budget 9,875,000,000 IRR, actual 6,842,000,000 IRR; remaining 3,033,000,000 IRR; consumption 69.3%; normalized bars 100 and 69.29. |
| Budget with no actual evidence | Actual unavailable, no percentage or bars. Commitment-only evidence also cannot create a zero actual. |
| Actual with no positive budget | Actual remains visible. No percentage, remaining comparison or bars. |
| Zero/default budget and no actual | Zero budget is displayed, actual unavailable. The existing model represents an unset estimate with its zero default, not a new null state. |
| Actual exceeds budget | Synthetic budget 5,000,000,000 IRR; actual unchanged; remaining −1,842,000,000 IRR; consumption 136.8%; mild overrun message and normalized bars. |
| Unauthorized or different currency | No unauthorized financial section or data loading. Incompatible currency suppresses comparison rather than converting or relabeling amounts. |

An additional observed defect was corrected within the existing contract-status presentation query. Its inherited creation-date ordering split status aggregation into separate groups, which were then overwritten when converted to a dictionary. Clearing that ordering before grouping restores the real count. The private browser fixture had three active contracts and six total. The original chart showed one active; the corrected chart and KPI agree on three. A regression fixture explicitly checks multiple active contracts. No contract state or business rule changed.

## Navigation and document security

The duplicate **ساختار شکست و فعالیت‌ها** destination was removed from basic information and quick access. Exactly one direct Controls link remains in the standalone progress section, reachable through the **برنامه و پیشرفت** tab. Its original B02 gate still requires all three effective Project Controls, WBS and Activities read permissions. Partial authority receives neither the link nor direct endpoint access.

Existing overview, information, progress, commercial lists, sites, costs, recent records, related documents and gallery destinations remain available when authorized. Chrome exercised all six local section anchors with keyboard activation and verified current-tab state. It followed Contracts, Sites and Reports indicators, Controls, a recent record, document detail, gallery, Estimates, Claims, Workforce and Timekeeping. Project identifiers/filter parameters remained in the relevant destination. File retrieval used the existing protected endpoint and returned the expected image bytes.

Header-photo selection requires the existing exact DMS document read and clean/available download authorization, a project typed link, PHOTO type, image MIME and exposed preview route. It does not expose raw storage. A documents-read actor without download authority could see the authorized document row/count but no header image or download. Direct preview was denied. A foreign-tenant actor was denied both project and photo access. The added photo metadata reuses resolved rows without adding a query per image; daily-report recent records select their site to avoid a new site N+1.

## Verification

All fixtures and mutations were confined to fresh private PostgreSQL databases `dashboard_browser` and `dashboard_technical` in an owned temporary cluster. The runner checked the database, loopback port and data-directory identity before execution. [Schema witness](evidence/b02-project-dashboard-20261111/schema-witness.txt) records 457 applied migrations and zero pending before fixture creation. The schema was restored from a clean isolated schema dump. No operational Development, demo or Production data was used. Temporary overrun/zero-budget changes were restricted to the synthetic project and restored in `finally`.

The [final read-only witness](evidence/b02-project-dashboard-20261111/final-database-witness.json) confirms restored budget, unchanged actual evidence and zero pending migrations. An environment-only closeout check interrupted by early teardown was rerun successfully. The owned web server and PostgreSQL instance were stopped and temporary login/session secrets removed; [cleanup record](evidence/b02-project-dashboard-20261111/cleanup.json). Unrelated running instances were left untouched.

| Check | Result and evidence |
|---|---|
| Installed Google Chrome 156.0.8078.80 | **26/26 PASS**, [case observations](evidence/b02-project-dashboard-20261111/after.json), [execution log](evidence/b02-project-dashboard-20261111/chrome-run.log). |
| Final responsive CSS | **3/3 PASS**, [width and KPI-column checks](evidence/b02-project-dashboard-20261111/final-responsive.json). |
| 1440, 1024, 390 CSS px | Correct RTL, one main landmark, readable indicators, loaded permitted photo, exact budget/contract values, working tabs, and document width no greater than viewport. Screenshots below. |
| Page health and fallback | No observed JavaScript errors or local HTTP errors in the authorized navigation sequence. Bars, exact amounts and contract legend remain with JavaScript disabled. |
| Appearance preference | No application dark-theme mechanism was established in the current page assets. Chrome dark system preference retained the supported light surface and passed layout checks, [capture](evidence/b02-project-dashboard-20261111/system-dark-preference-1440.png). No new dark theme is claimed. |
| Focused Django/PostgreSQL selection | **48 passing methods out of 49**, with one pre-existing failing method containing two failing subtests. [Log](evidence/b02-project-dashboard-20261111/regression.log), [structured result](evidence/b02-project-dashboard-20261111/technical-summary.json). All 16 focused B02 remediation/concurrency methods passed. |
| Failure attribution | The existing shared document-navigation test still expects `data-related-documents-nav` on Expenses Detail and Daily Report Detail. Both failures reproduced with entry Project Detail, dashboard and document-presentation overlays. [Entry attribution log](evidence/b02-project-dashboard-20261111/regression-entry-attribution.log). These pages were not changed by this task. This selection is not reported as wholly green. |
| Static checks | Ruff check and format check passed for all five changed Python files; `git diff --check` passed. [Ruff output](evidence/b02-project-dashboard-20261111/ruff.log), [check results](evidence/b02-project-dashboard-20261111/static-checks.json). |

The test selection was `apps.projects.test_command_center`, `apps.projects.test_photo_gallery`, `apps.documents.test_related_documents` and `tests.test_b02_remediation`. The existing browser-test expectations were updated for the server-rendered budget comparison. The real Chrome evidence above comes from the separate isolated browser probe rather than a claim that every historical browser-suite case or the full repository suite was executed.

### Before and after

The same synthetic project and PostgreSQL evidence were used on both sides. The browser's neutral one-pixel test photo intentionally proves the protected image path and appears blank; it is not a proposed production project photograph. The no-cost examples show the actual branded fallback. Images were inspected for hierarchy, clipping, reading order and preserved actions.

| Viewport | Before | Final implementation |
|---|---|---|
| 1440 | [Before](evidence/b02-project-dashboard-20261111/before-1440.png) | [After](evidence/b02-project-dashboard-20261111/after-1440.png) |
| 1024 | [Before](evidence/b02-project-dashboard-20261111/before-1024.png) | [After](evidence/b02-project-dashboard-20261111/after-1024.png) |
| 390 | [Before](evidence/b02-project-dashboard-20261111/before-390.png) | [After](evidence/b02-project-dashboard-20261111/after-390.png) |

Additional captures cover [no actual cost / placeholder](evidence/b02-project-dashboard-20261111/empty-1440.png), [mobile no actual cost](evidence/b02-project-dashboard-20261111/empty-390.png), [overrun](evidence/b02-project-dashboard-20261111/over-budget-1440.png), [actual with zero budget](evidence/b02-project-dashboard-20261111/zero-budget-390.png) and [restricted role](evidence/b02-project-dashboard-20261111/restricted-390.png).

## Changed files and preservation

| File | Task-owned change |
|---|---|
| [Project dashboard](../../../../apps/projects/dashboard.py) | Read-only comparison, real indicator destinations, correct status aggregation, retained Controls permissions. |
| [Detail template](../../../../apps/projects/templates/projects/detail.html) | Header, navigation, responsive composition and single Controls destination. |
| [Budget partial](../../../../apps/projects/templates/projects/dashboard_budget.html) | Exact money, native bars, remaining/percentage, unavailable/overrun states and source trace. |
| [Detail CSS](../../../../apps/projects/static/projects/detail_dashboard.css) | Scoped responsive Project Detail styles. |
| [Existing chart renderer](../../../../apps/projects/static/projects/dashboard_charts.js) | Additional draft/terminated status color mapping. |
| [Shared metric](../../../../templates/components/dashboard_metric.html) | Optional localized formatting, opted into by this detail page. Existing callers retain their defaults. |
| [DMS presentation](../../../../apps/documents/presentation.py) | Optional protected project-photo URL from already authorized document rows. |
| [Command-center tests](../../../../apps/projects/test_command_center.py), [browser expectations](../../../../apps/projects/test_command_center_browser.py), [DMS tests](../../../../apps/documents/test_related_documents.py) | Comparisons, status count, empty/currency/overrun/zero states and protected-photo authorization. |
| [MVP reconciliation](../MVP_SCOPE_RECONCILIATION.md), [design registry](../APPROVED_DESIGN_CONFORMANCE_REGISTRY.md), [B02 report addendum](B02_REMEDIATION_REPORT.md), [PO overlay](B02_PO_SCOPE_DISPOSITIONS.csv) | Dated Product Owner dispositions, preserving earlier results. |

[Preservation evidence](evidence/b02-project-dashboard-20261111/preservation.json) fingerprints the ten implementation/test sources and confirms the accepted Projects List template and workspace CSS match their entry content. The prior B02 Controls fix is retained. Concurrent edits arrived in unowned Projects views, Daily Report code and shared detail components during the session. They were preserved and are explicitly distinguished from unchanged entry hunks. No claim is made that the whole concurrently edited repository was frozen or that the latest B03 changes were certified. No model, migration, permission catalog, service workflow or financial producer was changed by this task. No dependencies were added.

## Product Owner decisions

Decision `PO-B02-PROJECT-DASHBOARD-20261112` records the user's explicit section 10 instructions. The [scope overlay](B02_PO_SCOPE_DISPOSITIONS.csv) is applied after the historical matrix and B02 retest without rewriting either.

| Topic | Current decision |
|---|---|
| Projects List | Existing design `PO_ACCEPTED`, preserved. |
| Project Detail | Direction approved; this implementation is ready for visual review, final acceptance pending. |
| Worker archive | Whole acceptance row `OUT_OF_SCOPE_MVP`. |
| Worker photo viewing / upload | Two whole acceptance rows `OUT_OF_SCOPE_MVP`. |
| Reservation-backed leave | Leave branches of submission/review `OUT_OF_SCOPE_MVP` for the complete operational journey. The mixed rows' Mission branches remain in scope with their existing evidence. |

The three whole-row exclusions reduce the historical 862-row MVP denominator by three for this decision alone. The two mixed rows remain. Exclusion never counts as PASS. Backend compatibility routes, services, models, source reservations and existing data remain intact.

## Remaining review

The Product Owner needs to assess the final visual hierarchy, density, mobile navigation and budget presentation against the supplied direction. Confirming this page's visual acceptance is the remaining task boundary. The two attributed shared-page test failures remain separately visible and require their own authorized remediation. Broader B02 variant coverage and overall product acceptance are not inferred from this dashboard result.
