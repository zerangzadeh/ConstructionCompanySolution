# MVP-06 — Critical MVP Print Outputs

Status: **MVP-06 COMPLETE — implementation acceptance PASS**, 2026-11-03
(Asia/Tehran). Product Owner visual acceptance: **PENDING**.
Bounded Human request in the attached task is the scope and
authorization; this MVP package is not a CEP. No production or Git writes.
Start: clean `main`, HEAD and cached `origin/main`
`2c97fbf716ec27f1a468ec41ace3c90bd4ada566`, divergence 0/0.

## Intended touch set

- Shared `core/printing.py`, `templates/print/` components,
  `templates/components/print_action.html`, local `css/erp_print.css` and
  `js/erp_print.js` under existing accounts static assets.
- Read projections: `print_outputs.py` in Billing, Procurement, Daily Reports,
  Expenses; existing authorized detail adapters in billing/views.py,
  procurement/order_workspace.py, procurement/receipt_workspace.py,
  daily_reports/views.py, and filtered expenses/views.py list adapter.
- Print entry action on those five source templates; focused security/source/
  query tests, isolated validation/Chrome scripts and `output/mvp-06/` evidence.
- No models, migrations, permissions/grants, workflow, calculations, Product
  Surface, navigation, dependencies or CEP lifecycle changes. Browser-native
  HTML/print CSS will be evaluated against real Chrome before final selection.

Registry's older repository checkpoint is historical metadata; later Human
checkpoints are visible in Git and prior MVP reports. All CEP lifecycle and
frontier records remain unchanged because this is separately authorized MVP-06.

## Entry assessment and shared print foundation

Inspected Roadmap MVP-06 and frozen D1–D7, UI guidelines/color tokens, MVP-03,
MVP-04 A–F implementation and subsequent A/B UI remediation evidence, MVP-05,
the five current source surfaces, model/services/version semantics, dependencies
and shared frontend assets. No established shared print route/template, print
CSS, browser-print helper or application PDF library was found in the inspected
runtime seams. Existing XLSX generators and uploaded-document storage are not
print foundations. The existing isolated PostgreSQL/installed Chrome test
approach and local Vazirmatn/font/color assets were reused.

Architecture: authorized existing source lookup/filter → domain `print_outputs`
projection → shared `Document`/`Table`/`Cell` contracts → one HTML document and
shared header/table/value/note components → local CSS/JS → browser print.
`core/printing.py` contains presentation formatting, resource safety and response
mechanics only. Calculations and lifecycle decisions remain in their domains.

All source actions use the shared `components/print_action.html` (`چاپ`). The
preview contains only print/back controls and page/date guidance. Query strings
retain current scope/filter context; summary printing removes the page slice.
Back removes only `format`. No external redirect, new endpoint or numbering.
Print waits for local fonts; browser Save as PDF remains available through the
browser's own dialog. There is no customer-facing server PDF endpoint.

The shared white A4 portrait surface uses 14mm top, 12mm side and 16mm bottom
margins, `lang=fa`/`dir=rtl`, local variable Vazirmatn and existing BONIRA tokens.
It has restrained typography/borders, wrapping fixed-width tables, isolated
numeric/identifier values, repeating table headings, row break avoidance,
unbroken totals/approval groups and sensible paragraph widows/orphans. Page
margin boxes show BONIRA and LTR page/total counters; the ordinary screen footer
is hidden in print. No shell, navigation, module drawer, filters, floating UI or
decorative cards appear in the document. Grayscale output uses no essential fills.
Long organization names/references wrap. Daily Report narrative precedes entries;
empty optional entry tables are omitted.

## Library decision

**BROWSER-NATIVE.** No application dependency was added or changed. Installed
Chrome print media/print-to-PDF is the qualification mechanism; Poppler renders
pages for inspection. Bundled `pypdf` is a read-only verification tool, not a new
project dependency or runtime renderer. The ten qualified one-/multi-page outputs
below demonstrate browser-native sufficiency; no custom PDF structures, competing
libraries, reporting framework, CDN or background jobs were introduced.

## Print inventory and authorization

| Output | Exact route | Existing authority retained |
| --- | --- | --- |
| Progress Claim / Billing | `/billing/claims/<uuid:claim_id>/?format=print` | `billing:claim_detail`, `claims.view`, `_claim` → scoped `get_progress_claims` |
| Purchase Order | `/procurement/orders/<uuid:order_id>/?format=print` | `procurement:order_detail`, `purchase_orders.view`, `_order` → scoped source service |
| GRN | `/procurement/receipts/<uuid:receipt_id>/?format=print` | `procurement:receipt_detail`, `goods_receipts.view`, `_receipt` → scoped source queryset |
| Daily Report | `/daily-reports/<uuid:report_id>/?format=print` | `daily_reports:detail`, `daily_reports.view`, source service with project/site scope |
| Expense / Petty Cash summary | `/expenses/?format=print` plus current list filters/sort | `expenses:list`, `expenses.view`, source list service and existing filters; full authorized result before pagination |

These are representations of existing reads, not new business permissions or
grants. Authentication, active membership, organization/lifecycle, object/project/
site scope and central Product Surface middleware execute on the same routes
before projection. Foreign records are denied with the source's existing 403/404
semantics; a foreign Expense summary contains no other tenant's rows. No hidden
Accounting, Treasury, Financials or other capability is exposed.

## Data mapping

Every label below maps to a persisted field, current source lookup or existing
model property. Dates use existing `format_jalali`; Decimal/int values reuse
`erp_number` without quantization, float conversion, new rounding or calculations.
Datetime presentation explicitly uses governed `OrganizationSettings.timezone`.
Null optional values use `—`; user text is escaped. Joined descriptive fields are
separated by `—`, not recalculated. Status labels are existing Django choice labels.

### Common fields

| Printed label | Authoritative source / transformation |
| --- | --- |
| Organization identity | Authenticated active `request.organization.name` |
| Organization logo, if valid and present | `OrganizationSettings.logo`, existing raster validator, bounded inline bytes |
| Document title | Static Persian presentation label for the existing source capability |
| شماره / مرجع | Claim `claim_number`, PO `order_number`, GRN `receipt_number`; omitted for Daily Report/summary with no business number |
| Page/total counters; بنیرا | Browser pagination and static product branding, not transaction facts |

### Progress Claim / Billing

For a submitted/approved/returned/superseded/cancelled revision with a submission
snapshot, `S = ProgressClaim.submission_snapshot["claim"]` and item/adjustment rows
come from the same snapshot. Unsnapshotted drafts use the same persisted claim,
item and adjustment fields. No call to recalculation is made. Descriptions/units
come from the pinned immutable baseline, in its business sort order; snapshot
lists are never mutated. Current status/approval evidence remains authoritative.

| Printed label | Authoritative source |
| --- | --- |
| پروژه | `ProgressClaim.project.name` |
| شماره قرارداد / عنوان قرارداد | `contract.contract_number` / `contract.title` |
| طرف قرارداد | `S.party_identity.display_name`, otherwise pinned `party_identity_snapshot.display_name` |
| شماره / مرجع؛ نسخه | `S.claim_number` / `S.revision_number`, otherwise claim fields |
| وضعیت | `ProgressClaim.get_status_display()` |
| شروع دوره / پایان دوره / تاریخ نهایی اندازه‌گیری | `S.period_start` / `period_end` / `measurement_cutoff`, otherwise claim dates; ISO snapshot dates parsed to date then Jalali |
| ارز | `S.currency_code`, otherwise claim's currency snapshot |
| شرح / واحد | Pinned `ProgressClaimItem.baseline_item.description` / `.unit` |
| تجمعی قبلی / مقدار دوره / تجمعی جدید | Snapshot item `previous_cumulative_quantity` / `current_quantity` / `new_cumulative_quantity`, otherwise persisted item fields |
| نرخ ثبت‌شده / مبلغ دوره | Snapshot item `unit_rate_snapshot` / `current_amount`, otherwise persisted item fields |
| نوع کسور | Snapshot/persisted `adjustment_type` → existing `ClaimAdjustmentType` Persian label |
| نرخ ثبت‌شده (درصد) / مبلغ مبنا / مبلغ | Snapshot/persisted adjustment `rate_snapshot` / `base_amount_snapshot` / `amount` |
| ناخالص / کسور و تعدیلات / خالص صورت‌وضعیت | `S.gross_amount` / `adjustment_amount` / `net_amount`, otherwise persisted claim calculation results; currency is the same claim snapshot |
| زمان تأیید / تأییدکننده | `approved_at` / `approved_by.get_full_name()` if present; no username fallback or invented signature |

### Purchase Order

Issued/completed/cancelled documents select `current_version.lines` where a
current version exists; drafts use prefetched base items. The version owns
description/quantity/price and material/unit links; master names are existing
linked labels because this domain has no separate historical master-name or
supplier-name snapshot. Immutable PO header fields remain the existing source.

| Printed label | Authoritative source |
| --- | --- |
| شماره / مرجع | `PurchaseOrder.order_number` |
| پروژه / تأمین‌کننده | `project.name` / `supplier.display_name` |
| تاریخ سفارش / تحویل موردانتظار | `order_date` / `expected_delivery_date` |
| وضعیت / نسخه سفارش | `get_status_display()` / `current_version.version_number` for issued versions |
| درخواست خرید مبنا | `purchase_request.request_number`, only when present |
| استعلام مبنا / نسخه استعلام | Selected version's `source_award.comparison.commercial_scope.rfq_version.rfq.rfq_number` / `.version_number`; draft uses its source award |
| شرح / مصالح | Selected version line `.description` and linked `.material.name`; draft item equivalents |
| واحد / مقدار / قیمت واحد | Selected line `.unit_of_measure.name` / `.quantity` / `.unit_price` |
| مبلغ ردیف | Draft/base line's existing `.line_total`; issued version 1's frozen `.source_item.line_total` uses the same existing amount property summed by the PO total; later versions use their existing version-line `.line_total` |
| جمع مبلغ سفارش | Existing `PurchaseOrder.total_amount` property, drafts or version 1 only, matching existing detail semantics |
| یادداشت‌ها | `PurchaseOrder.notes` |

No currency is inferred. Later amended versions have no authoritative total
property and therefore print their authoritative line totals without a newly
invented document total or the stale base-item total.
Version 1 explicitly reuses the immutable source item's existing rounded line
amount so it agrees with the existing header total; no print-layer rounding or
new calculation is introduced. The long fractional-quantity fixture verifies
this distinction. Later amended versions remain source-version driven.

### GRN

| Printed label | Authoritative source |
| --- | --- |
| شماره / مرجع | `GoodsReceipt.receipt_number` |
| پروژه / سفارش خرید مبنا | `project.name` / `purchase_order.order_number` |
| نسخه سفارش مبنا | `purchase_order_version.version_number`, never today's current PO version |
| تأمین‌کننده | Existing source `purchase_order.supplier.display_name` |
| زمان دریافت / وضعیت رسید | `received_at` in organization timezone / `get_status_display()` |
| مصالح / شرح سفارش مبنا | `GoodsReceiptItem.material.name` plus `.description` from the pinned PO version line matched by `source_item_id`; no mutable base description fallback |
| واحد / مقدار دریافت‌شده / یادداشت ردیف | Receipt item `unit_of_measure.name` / `quantity` / `notes` |
| یادداشت‌ها | `GoodsReceipt.notes` |

No stock valuation, posting implication, financial balance or Inventory mutation.

### Daily Report

| Printed label | Authoritative source |
| --- | --- |
| پروژه / کارگاه / فاز | `DailyReport.project.name` / `site.name` / optional `phase.name` |
| تاریخ گزارش / وضعیت / آب‌وهوا / تعداد نیروی انسانی | `reporting_date` / `get_status_display()` / `weather_conditions` / `labor_count` |
| کارهای انجام‌شده / خلاصه پیشرفت / مسائل و تأخیرها / یادداشت‌های ایمنی / یادداشت‌های کیفیت | `work_performed` / `progress_summary` / `issues_and_delays` / `safety_notes` / `quality_notes` |
| فعالیت: شرح / مقدار / واحد / پیشرفت ثبت‌شده (درصد) / یادداشت | `DailyActivity.description` / `quantity` / optional `unit_of_measure.name` / `progress_percent` / `notes` |
| نیروی انسانی: گروه کاری / تعداد نیرو / ساعات کارکرد / یادداشت | `DailyReportLaborEntry.team_name` / `worker_count` / `hours_worked` / `notes` |
| تجهیزات: نام تجهیز / ساعات کارکرد / یادداشت | `DailyReportEquipmentEntry.equipment_name` / `hours_used` / `notes` |
| مصالح ثبت‌شده / مقدار / واحد ثبت‌شده / یادداشت | `DailyReportMaterialEntry.material_name` / `quantity` / `unit` / `notes`, preserving existing saved labels |
| تأخیر: تاریخ / دسته / علت / اثر / طرف مسئول / مدت (ساعت) / وضعیت | `DelayEvent.occurred_on` / `category` / `cause` / `impact` / `responsible_party` / `duration_hours` / `get_status_display()` |
| زمان تأیید / تأییدکننده | `approved_at` / named `approved_by`, only when persisted |

No new productivity/physical-progress calculation or inferred workforce identity.

### Expense / current Petty Cash surface

| Printed label | Authoritative source |
| --- | --- |
| ارز؛ مبلغ column currency | Governed `OrganizationSettings.currency`, not legacy `Organization.currency` |
| جست‌وجوی شرح / فروشنده / رسید؛ جست‌وجوی پروژه / فاز | Existing applied list text filter criteria, explicitly labelled as search criteria |
| گروه هزینه (filter) | Valid selected active `PlatformExpenseGroup.name` resolved from existing code choice |
| از / تا تاریخ هزینه | Existing valid `incurred_on_from` / `_to` criteria parsed by `parse_user_date`, then Jalali |
| شرح / پروژه و کارگاه | `Expense.description` / `project.name` / optional `phase.site.name` / `phase.name` |
| تاریخ / گروه و دسته | `incurred_on` / `primary_group.name` (existing category display fallback) / optional `expense_category.name` |
| فروشنده / طرف تجاری | `vendor_name` / optional `party.display_name` |
| مبلغ | `Expense.amount` |
| وضعیت / مرجع رسید | `get_status_display()` / `receipt_reference` |

No aggregate total, opening/closing cash, petty-cash fund balance or cross-currency
sum is manufactured. Expense owns no business document number or cash ledger.

## Security, performance and omitted fields

Django autoescape remains enabled throughout; no `safe`, user HTML, remote
resource URL, CSS or executable content enters the print contracts. CSP restricts
scripts/styles/fonts to self, images to validated raster data, and denies all
other resource classes, forms and base URLs. Valid stored tenant logos use the
existing validator, bounded 2MiB reads and a fixed PNG/JPEG/WebP MIME allowlist;
SVG, invalid or missing files are omitted. No arbitrary file path or remote URL
is accepted from a request. Responses are private/no-store and nosniff.

Source services retain tenant/object scope. Billing joins baseline items;
Procurement joins line masters and reads one pinned-version description map;
Daily Report reuses the source's eager-loaded child sets; Expenses joins project,
phase/site, group/category and party. No per-line queries are introduced. The
focused test compares 1 versus 41 PO lines, including the complete HTTP adapter.

Omitted: unsupported organization address/phone/tax/registration fields, fake
logos or signatures, print-generation timestamp, invented Daily Report number,
Expense number/fund/settlement/AP/GL data, Procurement currency/tax/payment
terms, and later-version PO totals. Billing adjustment description fields such
as `contract_term.retention` are internal source selectors; existing Persian
adjustment-type labels are used instead. Pinned baseline and PO line facts are
preserved; no versioning design is changed. Daily Report typed attachment records
have a separate Documents access boundary and are intentionally not traversed by
this source-read print; no document file/content/private storage reference is
exposed. Broader outputs, P1 XLSX and MVP-07 remain out of scope.

## Verification and visual findings

Validation used dedicated PostgreSQL clones `test_bonira_mvp06_20261103` and
`test_bonira_mvp06_reg_20261103`, derived from the previously qualified isolated
schema clone. No Development/customer fixtures, resets or migrations were used.
The runner retains the existing guarded cascade cleanup for retired Payment FKs
and code-owned seed restoration; no product integrity guard is changed.

| Validation | Result / evidence |
| --- | --- |
| Final source/security/precision tests and operational Chrome | **16 PASS / 4 subtests**: 15 functional methods plus one operational Chrome method; [final operational log](../../../output/mvp06-operational-verified.log) |
| Billing Chrome and prior focused checks | **15 PASS / 4 subtests**: 14 focused methods plus Billing Chrome; [verified Billing run](../../../output/mvp06-focused-verified.log). The final added PO precision method is included in the final operational run above. |
| Distinct focused coverage | **17 methods PASS**, including both Chrome methods; no claim that all were one command |
| Affected regression | **58 PASS / 18 subtests**, [regression log](../../../output/mvp06-affected-regression.log): central MVP/FULL_ERP surface/hidden routes, Billing journey/scope, GRN normal detail/lifecycle and version regressions, existing P0 XLSX source/scope/integrity suites |
| PDF structural/resource/content audit | **10 PDFs / 29 A4 pages PASS**; [audit](../../../output/mvp-06/pdf-audit.json). Reopened with bundled pypdf; valid structure, expected inspectable source tokens, embedded font/glyph programs, no blank/footer-only pages, no visible URLs/UUIDs or external actions, and repeated continuation headers. Skia Type 3 glyph programs are recognized as embedded resources. |
| Static checks | Ruff check/format **14 Python files PASS**, two Node syntax checks PASS, Django system check PASS, no migration drift and Git diff whitespace PASS; [final checks](../../../output/mvp-06/final-checks.json) |
| Templates and preservation | **11 templates compile; 21 protected source files unchanged**, [preservation/environment](../../../output/mvp-06/static-and-preservation.json) |

Installed **Google Chrome 156.0.8078.48**, desktop 1440px and representative
390px source/preview entry, ran the actual source `چاپ` links and toolbar handler.
The harness blocked all non-local requests; all ten render scenarios record
zero external attempts, runtime exceptions, failed print resources and horizontal
overflow. It waited for Vazirmatn and used print media plus `preferCSSPageSize`.
Browser headers/footers were disabled so URLs cannot enter the printed document;
the preview states this print setting. Native dialog/printer preferences remain
browser-owned. Built-in browser Save as PDF is supported; no server PDF action
is implied. Each final PDF page was rendered with native Poppler.

| Output / source size | Short A4 | Long A4 | Final render evidence |
| --- | --- | --- | --- |
| Claim: approved one line with retained 10% synthetic contractual deduction; long draft 37 lines | 1 page | 4 pages | [short](../../../output/mvp-06/browser/billing/claim-one-page.pdf), [long](../../../output/mvp-06/browser/billing-long/claim-multi-page.pdf), [all long pages](../../../output/mvp-06/browser/billing-long/claim-multi-page-contact.png) |
| PO: one line; long 73 issued lines with fractional quantity/large amount | 1 page | 6 pages | [short](../../../output/mvp-06/browser/operational/po-one-page.pdf), [long](../../../output/mvp-06/browser/long/po-multi-page.pdf), [all long pages](../../../output/mvp-06/browser/long/po-multi-page-contact.png) |
| GRN: one receipt line; long 73 lines pinned to issued PO | 1 page | 6 pages | [short](../../../output/mvp-06/browser/operational/grn-one-page.pdf), [long](../../../output/mvp-06/browser/long/grn-multi-page.pdf), [all long pages](../../../output/mvp-06/browser/long/grn-multi-page-contact.png) |
| Daily Report: narrative and empty optional sections; long 60 activities | 1 page | 4 pages | [short](../../../output/mvp-06/browser/operational/daily-one-page.pdf), [long](../../../output/mvp-06/browser/long/daily-multi-page.pdf), [all long pages](../../../output/mvp-06/browser/long/daily-multi-page-contact.png) |
| Expense summary: one expense; long 61 authorized expenses | 1 page | 4 pages | [short](../../../output/mvp-06/browser/operational/expenses-one-page.pdf), [long](../../../output/mvp-06/browser/long/expenses-multi-page.pdf), [all long pages](../../../output/mvp-06/browser/long/expenses-multi-page-contact.png) |

Agent inspected all five short page renders, all five multi-page contact sheets,
and full-resolution representative continuation/end pages, including approved
claim totals/approval metadata, GRN description wrapping and the final rounded
PO line/header amounts. Persian shaping is correct, identifiers/numbers retain
LTR ordering, tables fit printable width, repeated headings identify columns,
rows do not split in the qualified fixtures, margins/page numbers are clear,
totals retain their heading/currency context, grayscale is readable and there
are no navigation elements, clipped text or blank pages. Structural text
extraction is not used as proof of Persian visual correctness. Source fields may
contain English business names; they are preserved and Bidi-isolated.

All positive data is synthetic, confined to test databases. The 10% retention
and test-only reviewed policy fixtures are not official rates, statutory
activation, production qualification or Human UAT.

## Superseded findings and regression attribution

- First focused attempt: 8 PASS and two assertions incorrectly assumed a
  configured retention deduction in a fixture that had none. Source results
  were correct; assertions now check the actual persisted values. The Chrome
  fixture separately configures/independently approves an explicit synthetic
  retention term, then prints its actual approved 60/-6/54 snapshot.
- An imported historical browser TestCase was inadvertently discoverable. The
  attempt was stopped and the import changed to a module alias. Prior-package
  evidence written by that attempt was restored to the initially clean HEAD
  content using read-only Git, preserving the checkout line-ending convention;
  no prior evidence remains changed.
  [Bounded collection](../../../output/mvp06-collection.log) demonstrates the
  corrected selection before the subsequently added focused cases.
- Early render harness assertions expected exact 595-point A4 width and decoded
  native PDF metadata using Windows' default code page. They now allow normal
  Chrome sub-point A4 rounding and explicitly decode UTF-8.
- Actual visual review found empty Daily Report tables forcing a second page;
  narrative-first ordering and omission of empty optional tables corrected it.
- A proposed fixed footer placed outside the page content produced footer-only
  extra pages in real Chrome. It was replaced with native page-margin branding
  and correctly LTR page counters. All final PDFs pass the blank-page audit.
- Long Billing fixture preparation was correctly rejected first for a baseline
  not equal to the effective contract ceiling and then for not carrying prior
  cumulative progress across a baseline revision. The fixture now follows both
  domain contracts; no service, calculation or workflow rule was weakened.
- Visual review of fractional PO quantities exposed two existing amount
  properties with different precision. Version 1 now selects the frozen source
  line's existing rounded amount, which is also summed by the existing PO total;
  amended versions retain their own existing line amounts and omit unsupported
  header totals. The explicit precision test passes. No domain arithmetic changed.
- Read-only PDF audit assumptions were corrected for Skia's embedded Type 3 glyph
  programs and page-margin stream order. This did not modify PDFs or product code.

The final scoped tests/regression have no unresolved attributable MVP-06 failure.
This is affected coverage, not a full repository or production regression claim.
Inherited Module Selector/F3 and obsolete F4 browser findings from
[MVP-05](MVP-05_COMPLETION_REPORT.md#affected-regression-and-findings) remain
unchanged and out of scope. Their preserved evidence is linked there; the affected
frontend/navigation/assets match HEAD. They were not repaired or represented as
a fresh full F3/F4 browser PASS. No new library, global CSS or foundation changes.

## Closeout and required status

No models/schema/migrations, permission grants, workflow, financial authority,
Product Surface, dependency lock, Roadmap or Registry change. The sole configured
Development pending migration remains the pre-existing
`payroll.0010_cep069_reviewed_statutory_context`; it was not applied. Current and
cached upstream HEAD remain `2c97fbf716ec27f1a468ec41ace3c90bd4ada566` on `main`.
Actual touch set and source hashes are retained in
[the touch-set manifest](../../../output/mvp-06/touch-set.json).

```text
MVP-06: PASS
SHARED PRINT FOUNDATION: PASS
PRINT/PDF LIBRARY DECISION: BROWSER-NATIVE
PROGRESS CLAIM / BILLING PRINT: PASS
PURCHASE ORDER PRINT: PASS
GRN PRINT: PASS
DAILY REPORT PRINT: PASS
EXPENSE / PETTY CASH SUMMARY PRINT: PASS
A4 / PAGINATION: PASS
RTL PRINT OUTPUT: PASS
PERMISSION / TENANT ISOLATION: PASS
SOURCE-OF-TRUTH INTEGRITY: PASS
TECHNICAL LEAKAGE: PASS
OFFLINE / SELF-CONTAINED RENDERING: PASS
F1-F4 FOUNDATION PRESERVED: PASS
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
MVP-06 COMPLETE
```

The foundation-preservation PASS is bounded to unchanged F1–F4 implementation,
the affected regression and the newly qualified print behavior, with inherited
browser findings retained above. Product Owner visual acceptance/Human Sign-off:
NOT ISSUED BY CODEX. Production Certification / Cutover: NOT EXECUTED.
Branch/worktree created: NO. Git add/commit/push/merge: NOT EXECUTED.
Changes remain uncommitted for Human review. **MVP-07 NOT STARTED.**

Reproduce focused tests: `.venv/Scripts/python.exe scripts/verification/mvp06_validate.py
--reuse-db -q tests/test_mvp06_print.py tests/test_mvp06_browser.py`.
Set `MVP06_REGRESSION=1` to select the isolated regression clone. The PDF audit
uses the bundled Python interpreter with pypdf, not the application's venv.
