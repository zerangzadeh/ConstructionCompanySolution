# Project Detail — targeted UI/UX remediation

**Date:** 2026-11-13 · **Status:** READY_FOR_PO_VISUAL_REVIEW / PO_ACCEPTANCE_PENDING

The existing Project Detail was improved within the supplied nine findings. WBS now shows authorized operational content; navigation and frequent creation actions have distinct roles; performance states and supporting content are more compact. This report is a new remediation/retest overlay. Historical B11 outcomes and the prior redesign evidence remain unchanged. No attributable P0/P1 defect remains in the focused checks below. This does not issue PO acceptance or production certification.

## Confirmed findings and corrections

| Finding confirmed in the entry render | Implemented correction and independent evidence |
|---|---|
| 01. WBS was a counters/navigation banner. | Two-level work-package preview, descendant activity counts, actual activity names/statuses and available planned dates. Tested third-level rollups, scope, archive exclusion, bounded results and constant query count. Chrome reconciles the prepared source data. |
| 02. Three WBS buttons competed for attention. | One primary **مدیریت ساختار شکست و فعالیت‌ها** links to the existing workspace. One small contextual **همه فعالیت‌ها** link opens its distinct Activity section. The redundant WBS-section button was removed. Both destinations and return work. |
| 03. Panels stretched or carried excessive empty space. | Removed performance-card stretching. Compact, content-driven performance cards, a narrow Quick Create strip and a full-width recent-record list reduce imbalance. Tablet/mobile stack naturally. An intermediate column-stack attempt left a large gap and was replaced before final capture. |
| 04. Missing progress/cost states repeated explanations. | One compact progress state explains the missing approved baseline/measurement. Actual cost is an unavailable dash when no qualifying evidence exists. Coverage detail moves into the existing source disclosure. Existing Decimal, currency, reversal, positive-budget and overrun guards remain intact. |
| 05. Supporting summaries competed with operations. | Identity → KPIs → WBS → performance → Quick Create → recent records → contracts/commercial → documents/information. All existing authorized capability destinations remain reachable. |
| 06. Long mixed-language recent titles disrupted rows. | Consistent type/title/status/date presentation; title link clamps to two lines visually, retains full accessible text and a title attribute. Long titles also have keyboard/touch-operable **عنوان کامل** disclosure. Full stored Persian/English business text is preserved. |
| 07. Management/navigation repeated in Quick Actions. | Quick Create now contains authorized Report and Expense creation only, retaining project preselection. Commercial creation remains in its summary. Equipment/Sites/Workforce/Timekeeping navigation remains in the appropriate tabs/overflow/KPI or contextual summary. No frequent create is duplicated in several prominent panels. |
| 08. Header was oversized and omitted the end date. | Compact title/status/company/code with start and available end dates; small neutral fallback; tiny/unloadable photo previews remain hidden. Basic information keeps explicit labels and the legacy project-budget field. Breadcrumb navigation stays neutral; the real Archive POST remains destructive and unchanged. |
| 09. Project-to-Equipment context required confirmation. | Existing assignment-backed handoff passes Project → Equipment List → Detail → Operations → Project, search context, project-scoped positive cases, sibling/foreign 403 and unrelated-equipment 404. No Equipment source file changed in this remediation. |

## WBS sources and limits

`apps/projects/dashboard.py` calls the existing `get_organization_wbs_nodes` and `get_organization_activities` services only after all three existing Project Controls/WBS/Activity permissions and surface exposure checks pass. These services retain organization/project/object authorization and archive rules. Restricted actors neither query nor see the preview or its management links.

The preview reads authorized node metadata, aggregates scoped activity counts and loads a five-activity sample in **three queries**, without per-row database access. It presents at most three roots and two direct child branches per root. Counts include all reachable authorized descendants, including deeper levels; the caption states this explicitly. Additional roots/branches/activities are identified with counts and remain accessible in the full workspace. Inaccessible or archived parents are not promoted to invented roots, and their titles are never fetched for the preview. Traversal is guarded against cycles; it does not repair source data.

The sample prioritizes actual `active`, then `planning`, then other existing statuses, with planned start dates where present. It does not infer that an old planning date is a future commitment. The heading is **فعالیت‌های پروژه**. Dates are explicitly activity plans, rendered in Jalali format. No scheduling, WBS, physical-progress or approval engine was introduced.

The persisted synthetic screenshot project contains five visible WBS nodes, three roots, five activities and two active activities. The first root contains three activities across its subtree; its displayed child contains two, including a third-level descendant. The same prepared business records were used before and after. Names and dates come from these records, not presentation constants. [Source reconciliation and Chrome results](evidence/chrome-final.json).

## Navigation, measurement and image rules

Tabs navigate major sections; WBS owns work management; Quick Create owns frequent operational creation; summaries own detail links. Intentional compact navigation/KPI/detail links remain where they offer a different context. Every visible action still uses existing authorization and MVP exposure checks. Quick Create GETs resolve the supplied project through the authorized Project service and do not change the global session; normal submitted forms retain their existing write authority and validation.

The budget shown is `Project.estimated_budget`, explicitly **estimated**, never approved. Recognized actual cost comes only from the existing Project Cost projection. An absent actual amount is not zero. Comparable positive estimates and qualifying actual evidence are required for consumption/remaining comparisons. Legacy `Project.actual_budget` remains separately labeled in basic information and is not substituted for recognized cost. The existing financial comparison function is AST-identical to the entry implementation. No approved project-wide progress baseline or reliable measurement is available under current policy, so no percentage/bar or invented setup approval action is shown. Actual WBS/Activity management remains available above.

The hero continues to use only the existing authorized DMS photo projection. A presentation guard rejects images below 160×90 native pixels or failed loads and uses the lightweight fallback; mobile omits the empty fallback. The guard cannot determine whether a sufficiently large photo depicts a document. It does not relabel document types, inspect content or bypass DMS security. Chrome tests 1×1 and 320×180 PNG dimension behavior; the existing Django photo suite covers DMS authorization. Related documents/gallery remain reachable.

Equipment context means **authorized assignment history**, including historical assignments. Equipment remains company-owned. Operations uses authorized deployment associations; company-level meters, qualifications and maintenance plans retain their existing labels/authority. The handoff is not a claim of exclusive or currently active project ownership.

## Before / after — installed Google Chrome

Chrome **156.0.8078.80**, Persian RTL, 100% zoom. The browser viewports were exactly the dimensions below; PNGs capture the full document for review. Final measured document widths equal the viewport widths, with one main landmark and no horizontal page overflow.

| Viewport | Before | After |
|---|---|---|
| 1440 × 900 | [Before](evidence/before-1440.png) | [After](evidence/after-1440.png) |
| 1024 × 768 | [Before](evidence/before-1024.png) | [After](evidence/after-1024.png) |
| 390 × 844 | [Before](evidence/before-390.png) | [After](evidence/after-390.png) |

[Final layout measurements](evidence/after-responsive.json) · [Empty project](evidence/empty-390.png) · [Equipment Operations mobile](evidence/equipment-operations-390.png).

## Focused verification and independent retest

| Check | Final result |
|---|---|
| Django: Project Operations, Command Center, Photo Gallery | **27 PASS, six subtests PASS**. Includes two added tests for hierarchy rollup/bounds/archive exclusion/query count and stored-title/create-only/order preservation. Existing tenant, cost/currency/overrun, Equipment event isolation, scoped export, Quick Create, timezone and photo authorization regressions pass. [Final log](evidence/acceptance-tests.log). |
| Real Chrome | **12/12 groups PASS**: all three responsive/keyboard sizes, hierarchy/action/full-title checks, image guard, WBS/Activity return, every dashboard GET destination, Quick Create preselection, Equipment journey, scoped positive/denial cases, empty states and protected pages. No observed browser errors. [Final JSON](evidence/chrome-final.json), [log](evidence/chrome-final.log). |
| Equipment independent retest | **18/18 page states PASS** for owner and project-scoped actors across all three viewports; action destinations and scoped empty state pass. [Evidence](evidence/equipment-final.json). |
| Protected independent retest | **9/9 exact viewport states PASS** for Projects List and Platform Company List/Detail. [Evidence](evidence/protected-responsive.json). |
| Django/static/schema | System check, Ruff check/format and JavaScript syntax PASS. Private retest database: 462 applied migrations, zero pending, consistent history. No model or migration changed. [System](evidence/system-check.log), [static](evidence/static-checks.log), [schema](evidence/schema-check.json). |
| Business preservation | **94 Project/Equipment/Expense/Contract/Daily Report/Document tables identical** between the prepared baseline and final retest clone; sessions excluded from this business comparison. [Evidence](evidence/business-preservation.json). |
| Scope and historical preservation | Six source files changed; all other entry source fingerprints and 11 protected hashes preserved. Prior redesign artifacts match their recorded closeout hashes; B11 matrix/report/retest retained. HEAD, local upstream and branch unchanged. [Source](evidence/source-preservation.json), [protected](evidence/protected-hashes.json), [prior redesign](evidence/prior-redesign-preservation.json). |

The first existing-regression run passed 25 tests/six subtests and the first Chrome replay passed 11 groups. The extended Django run then had one fixture-expectation failure: the existing Expense create service strips trailing whitespace, while the new test expected the untrimmed input. The fixture was corrected, without changing the service or stored-title behavior, and the full 27-test suite passed. [Preserved first extended result](evidence/tests-extended-first.log).

A second Chrome attempt failed an exact-label search-button locator after changing viewport; its other groups passed and the original journey had passed earlier. The replay now uses native Enter form submission from the Equipment search field. The complete 12-group run and independent 18-state Equipment check pass. [Preserved second attempt](evidence/chrome-second-attempt.json). A baseline-capture attempt also encountered a Windows UTF-8 harness decoding issue before capture; rerunning with UTF-8 enabled produced the complete before set. These attempts do not replace final results. [Replay checks](evidence/replay/README.md).

## Changed files and execution boundary

| File | Change |
|---|---|
| `apps/projects/dashboard.py` | Authorized bounded WBS/activity read composition; create-only frequent actions. |
| `apps/projects/templates/projects/detail.html` | Operational hierarchy, tree/activity preview, consolidated actions, compact header/progress and readable recent records. |
| `apps/projects/templates/projects/dashboard_budget.html` | Concise unavailable state and disclosure placement; financial conditions retained. |
| `apps/projects/static/projects/detail_dashboard.css` | Page-scoped content density, responsive tree/recent layout, focus and photo fallback styling. |
| `apps/projects/static/projects/project_dashboard.js` | Native-image dimension/load guard; existing overflow keyboard behavior retained. |
| `apps/projects/test_project_operations_dashboard.py` | Two focused new regression methods; original methods preserved. |

[Entry-to-final implementation patch](evidence/implementation.patch) · [Source hashes](evidence/source-delta.json).

Validation used dedicated `project_ui_original`, `project_ui_retest` and `test_project_ui` databases on the private loopback validation cluster. Baseline was cloned from the prior synthetic redesign retest; extra hierarchy and long-title fixtures were prepared before both screenshot sets. The retest was cloned after that preparation. No operational tenant database was copied, and no existing-development or production business data was mutated by this task. Private settings, secrets, cookies and uploaded storage are excluded from public evidence. No dependency, domain service, authorization rule, model, migration, protected page, shared shell or financial/progress policy changed. No commit, push, deployment or production operation occurred. [Resource and artifact closeout](evidence/closeout.json).

## Product Owner boundary

Review the final visual hierarchy, WBS preview density, responsive stacking and recent-record readability using the three After images. **PO_ACCEPTANCE_PENDING** remains explicit. The dimension guard's content-recognition limitation and current absence of approved project progress remain documented product constraints, not fabricated working features. This remediation stops here; no broad audit or further redesign cycle was started.
