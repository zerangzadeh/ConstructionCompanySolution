# BONIRA — Wave 01 final UX closeout

**2026-11-10 Asia/Tehran · bounded technical closeout complete · PO visual decisions pending.** The latest Companies List CSS passed at 1440, 1024 and 390 CSS px. UX-R-OBS-01 is corrected and independently retested. BON-DEF-0001 through BON-DEF-0003 remain **FIXED / RETESTED_PASS**. No PO_ACCEPTED decision was issued.

## Latest source baseline and preservation

Local `main`, HEAD and local `origin/main`: `865fa3f3f7868e81b0aafba05d2683b28fe33b1e`. Verification used the current dirty working tree, including the final incoming Companies List CSS. The local upstream reference was inspected without fetching or performing Git writes.

The [entry baseline](evidence/wave-01-final-ux/baseline.json) fingerprints 288 existing files. [Final source preservation](evidence/wave-01-final-ux/source-preservation.json) proves **284 unchanged files and exactly four authorized source/test changes**, with no unexpected drift. This includes byte-identical PA-02/PA-03 PO templates, company CSS, forms/views, shared filter/result components, prior validation reports, evidence, matrices, defect records and execution IDs. Authentication templates also remain unchanged.

The verified `apps/organizations/static/css/erp_platform_company_list.css` SHA-256 is `adde74039e9d3df87937848a4004a9ab0a66a18ab47ed6d1b7e1950caefbcc41`. Its entry and final hashes match. This pass resolves the **last-CSS verification block** recorded in the [previous remediation report](WAVE_01_UX_REMEDIATION_REPORT.md); that historical report and its evidence remain intact. Formal PA-02/PA-03 visual acceptance remains pending.

## Companies List final CSS verification

Actual Google Chrome **156.0.8078.80**, current `/organizations/platform/companies/`, synthetic Platform administrator, Persian locale and Tehran timezone:

| Width | Exact checks and observed result | Current screenshots |
|---|---|---|
| 1440 | RTL shell/sidebar, breadcrumb, heading/create action, KPI row, aligned filters, table headings/rows/statuses/actions, toolbar and pagination. Document width **1440/1440**; no visible control overlap, clipping or page overflow. | [Viewport](evidence/wave-01-final-ux/companies-viewport-1440.png) · [Full table](evidence/wave-01-final-ux/companies-final-1440.png) |
| 1024 | Same current design checked at tablet width; filters, narrower table, actions and navigation remain readable/reachable. Document width **1024/1024**; no visible control overlap, clipping or page overflow. | [Viewport](evidence/wave-01-final-ux/companies-viewport-1024.png) · [Full table](evidence/wave-01-final-ux/companies-final-1024.png) |
| 390 | Approved stacked KPIs/filters and card-style rows; visible status/field labels, actions, sort disclosure and pagination. Document width **390/390**; no visible control overlap, clipping or page overflow. | [Viewport](evidence/wave-01-final-ux/companies-viewport-390.png) · [Mobile rows](evidence/wave-01-final-ux/companies-final-390.png) · [Open sort menu](evidence/wave-01-final-ux/companies-sort-390.png) |

At each width, real interactions checked company search, empty results, status filtering, a row action reaching its exact company-detail URL, keyboard Enter opening the sort menu, sort navigation, page 2, the “شرکت جدید” destination and Platform breadcrumb navigation. Mobile clear restored the unfiltered 25-row first page. Status filtering for suspended companies correctly showed no results in the all-active synthetic fixture. Row actions retained the truthful “فعالیت‌ها و عملیات” label and matching company target. Geometry checks covered 31 visible controls per width; screenshot inspection confirmed the responsive presentation.

[Initial company checks](evidence/wave-01-final-ux/browser-companies.json) · [Final geometry/navigation](evidence/wave-01-final-ux/browser-companies-supplement.json) · [Mobile filter/action completion](evidence/wave-01-final-ux/browser-companies-mobile-completion.json).

The first script timed out when it targeted a table-header sort link hidden by the approved mobile layout. A supplemental script initially counted breadcrumb links as create actions. Both were harness issues, retained in the evidence; corrected selectors exercised the actual visible sort menu and header action successfully. **No Companies List or Company Detail source/design correction was necessary.**

## UX-R-OBS-01 — invalid Jalali input

**Reproduced before correction:** typing `1405/13/50` triggered automatic GET navigation after the debounce, changed the displayed results to the fail-closed empty state and redisplayed an empty date field. The invalid value remained only in the URL. [Before result](evidence/wave-01-final-ux/browser-before.json) · [Before screenshot](evidence/wave-01-final-ux/audit-invalid-before-1440.png).

The minimal correction uses the existing Audit **فیلتر** button as an explicit apply action. The shared GET-submit listener now respects cancellation by the existing Jalali validator. Audit reuses `JalaliDateMixin` / `JalaliDateInput` to retain invalid submitted values and render normal field errors. The existing canonical parser/conversion, inclusive queryset predicates, permissions and audit-domain behavior are unchanged.

| Retest | Result |
|---|---|
| Impossible input at 1440, 1024, 390 | `1405/13/50` stays visible after typing, debounce and Apply. Persian validation says **«تاریخ جلالی واردشده معتبر نیست.»**; invalid input is focused/identified. No navigation occurs; URL and displayed results stay unchanged. [Mobile feedback](evidence/wave-01-final-ux/audit-invalid-after-390.png). |
| Incomplete input | `1405/08` remains visible. Apply is blocked with **«تاریخ را با قالب شمسی صحیح وارد کنید.»**; URL/results remain unchanged. |
| Correct and apply a valid range | `1405/08/17`–`1405/08/20` submits canonical `2026-11-08`–`2026-11-11`, redisplays Jalali and retains existing range filtering. Clear removes the range. [Valid range](evidence/wave-01-final-ux/audit-valid-range-1440.png). |
| Direct malformed GET / server fallback | The invalid value remains visible with **«یک تاریخ معتبر وارد کنید.»** and accessible invalid-field markup. The server retains its existing fail-closed empty result for malformed requests. [Direct invalid screenshot](evidence/wave-01-final-ux/audit-direct-invalid-1440.png). |
| Focused date regression | Inclusive lower/upper bounds, exclusion of adjacent days, invalid ASCII/Persian digits, incomplete input, Jalali and ISO inputs, and reversed-range rejection passed. **2 tests and 7 subtests PASS.** |

[Actual browser assertions](evidence/wave-01-final-ux/browser-after.json) · [Focused test transcript and exact selection](evidence/wave-01-final-ux/focused-tests.log). **UX-R-OBS-01: FIXED / RETESTED_PASS; formal PO acceptance unrecorded.**

## Five authentication visual decisions

Open the [single visual review package](WAVE_01_AUTH_VISUAL_REVIEW.html): five existing execution IDs, each with current **1440 × 900 and 390 × 844** screenshots and one specific PO decision. The valid confirmation form used a private synthetic recovery token; no token or credential appears in the package.

Shared approved UI guidance remains applicable. The reviewed DC-01 registry, historical RV-001 login screenshot and F1 preservation report establish shared requirements and dated implementation evidence. No explicit page-specific approval for login or the four public-recovery screens was established. The located `E:/ERP_Construction_Documents/Main Page/BONIRA_Login_10of10_v7_palette_aligned.html` remains an **unapproved candidate**. No candidate design was adopted and no authentication page was redesigned.

The five original rows retain **NEEDS_PO_REVIEW / REFERENCE_MISSING**: login, recovery request, recovery receipt, password confirmation and recovery completion. [Capture record](evidence/wave-01-final-ux/browser-auth.json). Prior successful authentication/security journeys were preserved without rerunning them.

## Changes and regression evidence

| File changed by this closeout | Bounded change |
|---|---|
| `apps/accounts/static/js/erp_table.js` | One-line guard respecting an already-cancelled submit event. |
| `apps/organizations/platform_console.py` | Reuse the existing Jalali form mixin for Audit. Previous corrected date labels are retained. |
| `apps/organizations/templates/organizations/platform_audit.html` | Opt into existing explicit filter submission. |
| `apps/organizations/test_wave01_ux_remediation.py` | One targeted invalid-redisplay/canonical-date regression test; previous three tests retained. |

New artifacts are this report, the authentication visual package and run-specific evidence. Existing registries/reports/matrices were left byte-identical. BON-DEF-0001–0003 retain their current fixed/retested states; no observed regression warrants reopening them. **No additional product defect was discovered within these bounded checks.**

Django system check, focused Ruff lint/format, JavaScript syntax and changed-source whitespace checks passed. [System check](evidence/wave-01-final-ux/django-check.log) · [Ruff](evidence/wave-01-final-ux/ruff-check.log) · [Format](evidence/wave-01-final-ux/ruff-format.log) · [Syntax/whitespace](evidence/wave-01-final-ux/syntax-whitespace.json).

The [isolated environment witness](evidence/wave-01-final-ux/environment.json) pins MVP and verifies the private PostgreSQL database/port/data-directory identity. Browser/test databases were separately named clones of retained synthetic/clean databases; media, protected files, cache, sessions and mail were isolated. The technical database migration ledger matches the pre-existing clean template, including applied timestamps. No schema migration or production action was performed. Private services were stopped and temporary credential/token files and raw request logs removed after verification. [Cleanup witness](evidence/wave-01-final-ux/cleanup.json).

## Explicit remaining open Wave 01 items

- **Five authentication visual decisions**, together in the linked review package; PO decision, approver/date and approved source remain unrecorded.
- **PA-02 and PA-03 formal PO visual acceptance.** Their current PO-edited designs remain authoritative for this bounded check. PA-03 final-CSS technical verification is now PASS; PA-02 successful verification is preserved.
- **Formal PO acceptance of BON-DEF-0001–0003 and UX-R-OBS-01.** Technical fix/retest states do not imply acceptance.
- **Three blocked UAT-15 rows:** `INV-BILLING-CLAIM-ACTION-APPROVE--UAT-15`, `INV-DOCUMENTS-VERSION-DOWNLOAD--UAT-15`, `INV-INVENTORY-TRANSACTION-POST--UAT-15`. Their valid cross-tenant domain fixtures remain unavailable in the original Wave 01 run.
- **Twelve unattempted UAT-15 variants and one partially evidenced policy-catalog lifecycle row** retain NOT_RUN. Exact original IDs/dispositions are preserved in the [read-only open-item snapshot](evidence/wave-01-final-ux/open-wave01-historical-dispositions.json) and original MVP matrix; none was executed by this closeout.
- **Supplemental Audit action-filter/pagination browser coverage** remains without a dedicated result, as previously recorded.

No full-audit rerun, broad regression suite, migration, commit, push, production action or new wave was started. This bounded closeout stops here; the wider Wave 01 program remains open for the dispositions above.
