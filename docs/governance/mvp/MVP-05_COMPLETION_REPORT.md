# MVP-05 — Shared XLSX Foundation + P0 Exports

Implementation complete, 2026-11-03; scoped export acceptance PASS with the
explicitly attributed pre-existing frontend regression findings below. Direct bounded Human request (attached task)
is the package contract and authorization; this is an MVP package, not a new CEP.
Start branch `main`; HEAD and origin/main
`cf0a4f7ca70ac318bb72060e6fccc8d005d8c705`; working tree clean.
No commit, push, branch/worktree creation or production action authorized.

## Intended touch set

Shared `core/xlsx.py`, shared template action, domain `xlsx_exports.py` modules
in Billing, Procurement, Inventory and Expenses; existing authorized list/detail
adapters in Billing views, Procurement views/order_workspace/receipt_workspace/
rfq_workspace, Inventory journey_views and Expenses views. Existing P0 list
templates and Billing claim detail receive only an export action. Dependency
inputs and three hash locks gain openpyxl and its required dependency. New focused
tests, isolated validation/browser scripts and this report own evidence.
No models, schema, migrations, domain calculations, workflow or permissions change.

## Source inspection

Roadmap MVP-05 and D5 define P0 Billing, Procurement, Inventory, Expenses.
MVP-03/MVP-04 evidence and current implementations inspected. Existing graph
query vocabulary: export, billing, procurement, inventory, expense. Graph points
to Expense/services and legacy reporting CSV; current source inspection is needed
for the later journey adapters. No established XLSX generator or suitable shared
workbook utility exists. Document download helpers are document-storage specific.
The exposed “هزینه‌ها و تنخواه” navigation targets Expenses; no separate petty-cash
record type is implemented there. Treasury remains outside this export scope.

## Shared XLSX Foundation

`core/xlsx.py` defines reusable `Column` and `Sheet` contracts, workbook creation
and Django `FileResponse`. Domain `xlsx_exports.py` modules supply business
columns, authoritative values and eager-loading. Library mechanics stay shared.
`openpyxl==3.1.5` (MIT), with `et_xmlfile==2.0.0`, is installed locally;
requirements.txt pins openpyxl and all three existing hash locks include both
universal wheels. No pandas, CSV substitute, hand-built OpenXML or extra writer.
[Library documentation](https://openpyxl.readthedocs.io/en/stable/tutorial.html).

Every worksheet explicitly sets `sheet_view.rightToLeft = True`. Persian headers
are ordered, bold, wrapped and 36pt high, with restrained fill, configured widths,
A2 freeze panes and autofilter. Dates remain native Gregorian Excel dates;
aware datetimes are converted using `OrganizationSettings.timezone`, then stored
as Excel-compatible naive wall time. Expense currency comes from governed
`OrganizationSettings.currency`; Billing retains its claim currency snapshot.
No currency conversion or Procurement currency inference occurs.

All strings, including `=`, `+`, `-`, `@`, tab-prefixed formulas, Excel error
literals and document identifiers, are explicitly string cells with text format.
No formulas, macros or external links are generated. Invalid control characters
are removed and text respects Excel's 32,767-character cell limit. Decimal/int
values remain numeric; filenames strip path/control characters; worksheet names
are valid, unique and bounded to 31 characters. Empty results retain every sheet
and its headers. Responses use the XLSX MIME type, attachment disposition,
private/no-store cache policy and nosniff.

## Export Inventory and Security

| Surface (existing route) | Workbook / worksheets | Permission |
| --- | --- | --- |
| Billing claim list | صورت‌وضعیت‌ها / ردیف‌های کارکرد / کسورات و اضافات | claims.view |
| Billing claim detail | Same sheets for the authorized current claim only | claims.view + existing scoped object lookup |
| Purchase Requests | درخواست‌های خرید / اقلام | purchase_requests.view |
| RFQs | استعلام‌های خرید / اقلام | rfqs.view |
| Purchase Orders | سفارش‌های خرید / اقلام | purchase_orders.view |
| GRNs | رسیدهای کالا / اقلام | goods_receipts.view |
| Inventory movements | گردش انبار | stock_transactions.view |
| Expenses and current Petty Cash entry | هزینه‌ها و تنخواه | expenses.view |

`?format=xlsx` uses the existing route and its authentication, active tenant,
permission and Product Surface middleware/decorators. It reads only the existing
authorized service queryset; object detail first performs the same scoped lookup.
This is another representation of the existing read capability, not a new
permission/catalog/default grant or a bypass of hidden surfaces.

All list adapters export `page.paginator.object_list`: the complete authorized,
filtered and sorted result before the page slice. The shared action retains
current query parameters and removes only page. Invalid form/relationship choices
retain existing fail-closed empty/404 semantics. Children are prefetched through
authorized parents, not fetched globally and filtered after generation.

Filters are exactly those of each current screen: Billing project/contract,
search/status/period; PR project/search/status/required date; RFQ project/search/
status/closing dates; PO project/supplier/source lineage/search/status/order dates;
GRN project/supplier/search/status/received dates; Inventory project/warehouse/
search/type/status/dates; Expenses description/vendor/receipt text, project/phase
text, category and incurred date. Expenses has no separate site-ID filter; its
current phase text filter and authorized project selector remain authoritative.
No new site/project permission semantics or unsupported filters are invented.

## Column / Source Mapping

Each dotted source below starts at the named model for that sheet. Null optional
relationships produce blank cells. `get_*_display` is Django's existing Persian
choice label. Values are copied; workbook generation performs no business
calculation. PO `line_total` and `total_amount` are the existing model properties.
Billing quantities, rates, adjustments and totals are persisted calculation-service
results, never recalculated by export. Claim numbers are explicitly text.

### Claim summary — `ProgressClaim`

| Excel column | Authoritative source / existing transformation |
| --- | --- |
| پروژه | `project.name` |
| شماره قرارداد | `contract.contract_number` |
| عنوان قرارداد | `contract.title` |
| شماره صورت‌وضعیت | `lambda r: str(r.claim_number)` |
| نسخه | `revision_number` |
| وضعیت | `get_status_display` |
| شروع دوره | `period_start` |
| پایان دوره | `period_end` |
| تاریخ قطع اندازه‌گیری | `measurement_cutoff` |
| ارز | `currency_code` |
| مبلغ ناخالص | `gross_amount` |
| کسورات و اضافات | `adjustment_amount` |
| مبلغ خالص | `net_amount` |

### Claim lines — `ProgressClaimItem`

| Excel column | Authoritative source / existing transformation |
| --- | --- |
| شماره قرارداد | `claim.contract.contract_number` |
| شماره صورت‌وضعیت | `lambda r: str(r.claim.claim_number)` |
| نسخه | `claim.revision_number` |
| شرح ردیف | `baseline_item.description` |
| واحد | `baseline_item.unit` |
| مقدار تجمعی قبلی | `previous_cumulative_quantity` |
| مقدار دوره | `current_quantity` |
| مقدار تجمعی جدید | `new_cumulative_quantity` |
| نرخ واحد ثبت‌شده | `unit_rate_snapshot` |
| مبلغ دوره | `current_amount` |

### Adjustments — `ClaimAdjustment`

| Excel column | Authoritative source / existing transformation |
| --- | --- |
| شماره قرارداد | `claim.contract.contract_number` |
| شماره صورت‌وضعیت | `lambda r: str(r.claim.claim_number)` |
| نسخه | `claim.revision_number` |
| نوع | `get_adjustment_type_display` |
| شرح | `description` |
| نرخ ثبت‌شده | `rate_snapshot` |
| مبلغ مبنا | `base_amount_snapshot` |
| مبلغ | `amount` |

### PR documents — `PurchaseRequest`

| Excel column | Authoritative source / existing transformation |
| --- | --- |
| شماره درخواست خرید | `request_number` |
| عنوان | `title` |
| پروژه | `project.name` |
| تاریخ نیاز | `required_by` |
| وضعیت | `get_status_display` |

### RFQ documents — `RequestForQuotation`

| Excel column | Authoritative source / existing transformation |
| --- | --- |
| شماره استعلام | `rfq_number` |
| عنوان | `title` |
| پروژه | `project.name` |
| درخواست خرید | `purchase_request.request_number` |
| نسخه صادرشده | `current_version_number` |
| مهلت دریافت | `closing_at` |
| وضعیت | `get_status_display` |

### PO documents — `PurchaseOrder`

| Excel column | Authoritative source / existing transformation |
| --- | --- |
| شماره سفارش خرید | `order_number` |
| پروژه | `project.name` |
| تأمین‌کننده | `supplier.display_name` |
| درخواست خرید | `purchase_request.request_number` |
| استعلام منبع | `source_award.comparison.commercial_scope.rfq_version.rfq.rfq_number` |
| نسخه استعلام منبع | `source_award.comparison.commercial_scope.rfq_version.version_number` |
| نسخه سفارش | `current_version.version_number` |
| تاریخ سفارش | `order_date` |
| تحویل موردانتظار | `expected_delivery_date` |
| وضعیت | `get_status_display` |
| مبلغ کل ثبت‌شده | `total_amount` |

### GRN documents — `GoodsReceipt`

| Excel column | Authoritative source / existing transformation |
| --- | --- |
| شماره رسید کالا | `receipt_number` |
| پروژه | `project.name` |
| شماره سفارش خرید | `purchase_order.order_number` |
| نسخه سفارش مبنا | `purchase_order_version.version_number` |
| زمان دریافت | `received_at` |
| وضعیت | `get_status_display` |

### PR lines — `PurchaseRequestItem`

| Excel column | Authoritative source / existing transformation |
| --- | --- |
| درخواست خرید | `purchase_request.request_number` |
| مصالح | `material.name` |
| شرح ردیف | `description` |
| واحد | `unit_of_measure.name` |
| مقدار | `quantity` |

### RFQ lines — `RequestForQuotationLine`

| Excel column | Authoritative source / existing transformation |
| --- | --- |
| شماره استعلام | `rfq.rfq_number` |
| مصالح | `material.name` |
| شرح ردیف | `description` |
| واحد | `unit_of_measure.name` |
| مقدار | `quantity` |

### PO lines — `PurchaseOrderItem`

| Excel column | Authoritative source / existing transformation |
| --- | --- |
| سفارش خرید | `purchase_order.order_number` |
| مصالح | `material.name` |
| شرح ردیف | `description` |
| واحد | `unit_of_measure.name` |
| مقدار | `quantity` |
| قیمت واحد ثبت‌شده | `unit_price` |
| مبلغ ردیف ثبت‌شده | `line_total` |
| ردیف درخواست خرید | `purchase_request_item.description` |
| شرح قلم انتخاب تأمین‌کننده | `source_award_allocation.award.comparison.commercial_scope.rfq_version_line.description` |

### GRN lines — `GoodsReceiptItem`

| Excel column | Authoritative source / existing transformation |
| --- | --- |
| رسید کالا | `goods_receipt.receipt_number` |
| ردیف سفارش خرید | `purchase_order_item.description` |
| مصالح | `material.name` |
| واحد | `unit_of_measure.name` |
| مقدار دریافت‌شده | `quantity` |

### Stock movements — `StockTransaction`

| Excel column | Authoritative source / existing transformation |
| --- | --- |
| شماره گردش | `transaction_number` |
| پروژه | `project.name` |
| انبار مبدأ | `source_warehouse.name` |
| انبار مقصد | `destination_warehouse.name` |
| مصالح | `material.name` |
| واحد | `unit_of_measure.name` |
| نوع گردش | `get_transaction_type_display` |
| مقدار | `quantity` |
| زمان وقوع | `occurred_at` |
| وضعیت ثبت | `get_status_display` |
| مرجع | `reference` |
| رسید کالا | `goods_receipt_item.goods_receipt.receipt_number` |
| برگشت گردش | `reversal_of.transaction_number` |
| رسید کالای گردش اصلی | `reversal_of.goods_receipt_item.goods_receipt.receipt_number` |

### Expenses / current Petty Cash entry — `Expense`

| Excel column | Authoritative source / existing transformation |
| --- | --- |
| پروژه | `project.name` |
| کارگاه | `phase.site.name` |
| فاز | `phase.name` |
| تاریخ هزینه | `incurred_on` |
| گروه هزینه | `primary_group.name` |
| دسته هزینه | `expense_category.name` |
| شرح | `description` |
| فروشنده | `vendor_name` |
| طرف تجاری | `party.display_name` |
| ارز | `organization.settings.currency` |
| مبلغ | `amount` |
| وضعیت | `get_status_display` |
| مرجع رسید | `receipt_reference` |

## Performance

Documents and their items use select_related plus one prefetch per child sheet;
Billing adds one prefetch for adjustments. PO totals reuse the existing model
property over the prefetched items. Inventory/Expenses iterate joined querysets.
No row mapper queries the database. The focused PR writer test bounds four
documents with items to at most three queries (including lazy tenant settings),
separate from existing permission/filter queries. Existing pagination may hydrate
one bounded screen page before XLSX consumes its unsliced sorted queryset; no
unrestricted second business query or per-row lookup is added.

## Deferred / Omitted Fields

- P1 Daily Reports, Estimates, Timekeeping / Equipment XLSX: DEFERRED.
- MVP-06, Print and PDF: NOT STARTED.
- Billing exports saved service results, not a fresh calculation. No new cumulative
  monetary total, tax/insurance assumption, receivable balance or posting state.
  Existing adjustment types/rate/base snapshots are copied only when persisted.
- Procurement has no standalone business Award number or universal document
  currency field. Award lineage uses its existing RFQ/version and issued RFQ line
  description; no UUID is substituted. The generated `item-<UUID>` scope code is
  deliberately omitted because it is technical. Stored PO prices/model totals are copied
  without assigning currency or interpreting accounting. RFQ exports include
  RFQ headers and lines, not protected bid payloads or sealed evidence.
- Inventory has no direct Site field; it exports existing project and warehouse
  context, receipt references and reversal relationship. No valuation, accounting
  value or newly computed balance is added.
- Current Expenses/Petty Cash surface is backed by Expense, not a separate cash
  fund or petty-cash ledger. Expense has no business document number; the existing
  receipt reference is used and may be blank. Site is present only through phase.
  No Treasury settlement, fund balance, AP/GL code or accounting classification.
- Large-volume export capacity, memory limits and alternate delivery are deferred.
  The current synchronous writer retains workbook cells in memory; no Celery,
  Redis, queue or async job is introduced. Excel's native numeric precision and
  text length constraints apply; no business rounding/conversion is introduced.

## Authority / Closeout Boundaries

No models/schema/migrations, authoritative calculations or workflow changes.
No new permission grants, Product Surface exposure or production action.
No CEP Registry lifecycle entry is invented for the independently authorized MVP
package. Only MVP-05 is executed; no automatic continuation to MVP-06.
Human Sign-off / Product Owner visual acceptance: NOT ISSUED BY CODEX.
Production Certification / Production Cutover: NOT EXECUTED.
Branch: main. Branch/worktree created: NO.
git add / commit / push / merge: NOT EXECUTED.

## Validation Environment and Failed Attempts

Tests run against dedicated PostgreSQL clones `test_bonira_mvp05_20261103` and
`test_bonira_mvp05_reg_20261103`, cloned from the existing migrated isolated
Module Selector test database. Django checks its migration plan against each test
DB. The Development database is not migrated or written. Fixture reset guards
require the exact dedicated test name and preserve database triggers/constraints.
No production environment is used. Browser files are synthetic.

- `output/mvp05-focused-attempt1.log`: 9 PASS, two new fixture errors (undefined
  foreign actor and absent synthetic expense group). Both fixture-only repairs
  are in the new tests; no product authorization was weakened.
- `output/mvp05-focused-attempt2.log`: 10 PASS / four subtests; actual Chrome
  downloads and reopen checks passed at that intermediate state.
- `output/mvp05-final-focused.log`: 10 PASS / four subtests, two FAIL. The added
  split test correctly found an automatically generated `item-<UUID>` sourcing
  code in a PO export. The export now uses the existing issued RFQ line description
  instead, with its relation eagerly loaded. This is an MVP-05 defect and is
  corrected, not attributed to baseline debt.
- The other failure is BASELINE TEST DEBT: unchanged F4 browser driver reads
  `a.firstChild.textContent` and expects flat navigation, while accepted current
  Module Selector uses icon/title/description cards. It fails on the unchanged
  Projects page before any export. Both template/driver match HEAD in preservation
  evidence. Original F4 sources and runtime code are preserved. The current F3
  card-aware acceptance and F2 local interaction checks are rerun instead; this
  report does not claim that the obsolete F4 driver passed.
- Browser reruns now use fresh unique download directories, so reopening always
  inspects the newly completed download rather than a prior same-name artifact.

- `output/mvp05-affected-regression.log`: 72 PASS / 19 subtests, 13 fixture failures.
  Four Billing tests stop at missing historical WorkflowTemplate catalog data;
  nine Award→PO tests stop during Admissibility fixture setup because historical
  `_make_actor` omits explicit membership authorization. No MVP-05 export code is
  reached by those failures. The isolated regression runner now restores the same
  three compatibility catalog seeds used by MVP-03 and the same explicit actor
  assignment adapter used by accepted `output/mvp-04f/run_validation.py`.
  Runtime services and authorization remain untouched; only these 13 failed
  cases are retried. Passing unaffected coverage is retained.
- The current Module Selector probe completed ten scenarios (including all three
  PR widths) before a scroll-return timeout at unchanged Workforce 1024px. It is
  retried separately; no unrelated navigation product change is made.

## Final XLSX / Browser Verification

- [Verified focused run](../../../output/mvp05-verified.log): **12 PASS / four
  subtests**, plus one unrelated Module Selector failure described below. The
  nine XLSX functional/integrity methods and two download methods all PASS;
  the shared interaction regression method also PASS. This is not claimed as a
  wholly green 13-method command.
- [Actual downloaded workbook inspection](../../../output/mvp-05/workbook-integrity.json):
  **8/8 newly completed Chrome downloads reopen successfully**. File sizes equal
  Chrome download-completion byte counts. Includes Billing list and detail, PR,
  RFQ, PO, GRN, Inventory and Expenses. Expected sheets/headers/order, RTL,
  source row counts, native numeric/date cells, source values, formula-like text,
  absence of formula cells/technical IDs and empty results are verified by the
  new automated tests. Billing rows/totals match existing calculation-service
  results. Split 4+6 supplier orders retain source PR/RFQ and issued line
  descriptions through their GRNs/Inventory without financial record changes.
- [Billing Chrome cases](../../../output/mvp-05/browser/billing/results.json),
  [operational cases](../../../output/mvp-05/browser/operational/results.json),
  [denied cases](../../../output/mvp-05/browser/denied/results.json): eight actual
  downloads and six unauthorized action-absence cases PASS. The clicked anchors
  retain page filters, produce business filenames, keep the current page usable,
  show no JavaScript exceptions, and preserve RTL without page overflow.
  Actual installed Google Chrome runs at 1440px/390px with external URLs blocked.
  Desktop PO and mobile Billing/Expenses captures were visually inspected;
  header/action spacing, readable Persian copy and shared button styling PASS.
- The scoped writer test verifies header-only empty sheets, valid unique names,
  Persian/long text, negative Decimal values, dates, tenant-zone conversion,
  numeric-looking text IDs, `=`, `+`, `-`, `@`, tab prefixes and Excel error
  literals. Formula-like input remains literal string data after reopen.
- [Shared interactions](../../../output/mvp-05/frontend-regression/command.txt):
  F2's existing six desktop/mobile offline scenarios PASS, including local
  selectors and confirmation behavior. Existing JS/CSS/Tailwind/vendor sources,
  navigation and Product Surface remain unchanged.

## Affected Regression and Findings

[Initial affected run](../../../output/mvp05-affected-regression.log): 72 PASS /
19 subtests; [fixture-corrected retry](../../../output/mvp05-fixture-retry.log):
13/13 PASS. **85 distinct affected regression cases PASS across those commands**.
Coverage is Product Surface/hidden-route isolation, Claims filters and scope,
Billing calculation/rounding/snapshots/workflow retries, PR lifecycle/scope,
RFQ preparation/filters/source guards, Award/partial PO lineage and consumption,
GRN partial receipts/post/void/remaining quantities, Inventory draft/post/reversal/
retry/isolation, Expense lifecycle/allocation/budget/finance boundaries and
current Module Selector presentation rules. This is affected coverage, not the
whole repository suite or production certification.

**Existing frontend finding — not changed by MVP-05:** the current F3 browser
probe completes ten scenarios in its first run, then times out returning the
horizontal drawer scroll to zero on unchanged Workforce at 1024px. Its
[separate unchanged retry](../../../output/mvp05-module-selector-retry.log)
reproduces the same assertion (after seven completed scenarios in that run).
[First failure evidence](../../../output/mvp-05/module-selector-attempt1/failure.json)
and [retry evidence](../../../output/mvp-05/module-selector-regression/failure.json)
are retained. The failing driver assertion is `f3_browser.mjs:182`; no JavaScript
exception or export failure is involved. Assets, Module Selector template/driver,
Workforce implementation and relevant source paths match HEAD in
[preservation proof](../../../output/mvp-05/preservation.json). No unrelated
navigation repair or residual-risk acceptance is made. Current full F3 regression
PASS is **not** claimed; follow-up is outside the bounded XLSX implementation.
The obsolete F4 driver failure is separately retained in
[legacy F4 evidence](../../../output/mvp-05/legacy-f4-attempt/failure.json).

Ruff check and format: **15/15 Python files PASS**. Node driver syntax and
`git diff --check`: PASS. Django system check: no issues; migration drift:
no changes detected. Dependency imports and XLSX generation/reopen PASS.
An optional whole-venv `pip check` reports pre-existing ambient `nltk==3.9.1`
missing click/joblib/regex/tqdm; NLTK is absent from project dependency inputs,
locks and the XLSX path. No unrelated environment repair was performed.

## Final Acceptance / Handoff

| Requirement | Result |
| --- | --- |
| Shared openpyxl foundation; RTL, native types, empty files and centralized safety | PASS |
| Billing P0 operational list/detail, saved lines/adjustments/totals | PASS |
| Procurement PR/RFQ/PO/GRN and partial/split lineage | PASS |
| Inventory movement/source/reversal operational export | PASS |
| Expenses/current Petty Cash source surface | PASS |
| Existing query filters, permissions, tenant/project/warehouse boundaries | PASS |
| Actual workbook reopen, headers/order/types/source values, no formulas/technical keys | PASS |
| Real Chrome downloads and page usability | PASS |
| F1–F4 source foundation preserved; affected shared interactions | PASS, with inherited F3/F4 test findings retained above |
| P1 XLSX | DEFERRED |

**MVP-05 COMPLETE — implementation scope.** Product Owner visual acceptance remains
pending; this report grants no Human Sign-off or production authority. No commit
or push. MVP-06 not started. End HEAD equals start HEAD; all changes remain
uncommitted on main. Actual touch set: 15 Python files (seven existing view
adapters and eight new export/test/validation files), eight existing templates
plus one shared action component, four dependency files, one new Chrome driver
and this report. No models/migrations, domain services, assets or unrelated
product sources changed.

Execution evidence is retained under `output/mvp-05/` and the linked root
validation logs. Existing ignore rules leave a mix of untracked and ignored
evidence; no Git staging or ignore-rule change was performed.
