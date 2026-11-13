# BONIRA — Project Operations Dashboard

2026-11-13. **Implemented and verified. Ready for Product Owner visual review.**

WBS and Activities now form the operational centerpiece immediately below the KPIs. The existing Equipment assignment model supports a working Project → Equipment → Operations handoff, including server-enforced project scope and a canonical return path. Progress and costs retain explicit unavailable states where authoritative measurements are absent.

Final verification passed **25 Django tests and six subtests**, **10 Chrome journey groups**, and **18 additional Equipment page states** across owner/project-scoped roles at 1440, 1024 and 390 px. No new attributable P0/P1 remains unresolved. Final visual PO acceptance has not been issued.

## Authority and baseline

The current request **BONIRA — Project Detail Dashboard Redesign** authorizes the bounded implementation. The supplied `BONIRA Persian Project Dashboard.png` directs visual hierarchy. Its sample company, dates, financial amounts, percentages and construction illustration are not application data or authority for new business behavior. Request/reference hashes and the incoming working-tree fingerprints are recorded in [entry evidence](evidence/entry.json).

Local `main`, HEAD and local `origin/main` were `24ad220f0376cb0b6232b745938b35433843a32d`. Existing uncommitted B03–B11 and other incoming work was preserved. [Entry Git state](evidence/entry-status.txt) · [Entry paths](evidence/entry-paths.txt) · [Final source delta](evidence/source-delta.json).

The relevant UI guidelines, current design registry, B11 report and existing Project Dashboard report were reviewed. The existing WBS/Activities workspace, equipment assignments, optional global context and governed permissions remain the application authorities. No new planning, scheduling, assignment or financial engine was introduced.

## Original problems and implemented hierarchy

| Original page | Implemented behavior |
|---|---|
| WBS entry appeared late, below secondary summaries. | A full-width work-planning card follows the KPI row, with one dominant entry action and separate WBS/Activities section links. |
| A large budget block dominated the page even when actual evidence was unavailable. | Balanced progress and budget panels follow the primary work-planning section. Unavailable measurements remain clearly labeled. |
| Secondary destinations competed in one long navigation row. | Dashboard, information, WBS and progress remain direct anchors. Other existing destinations use an accessible overflow menu. |
| Quick access emphasized only supporting workforce destinations. | Six authorized operational destinations cover report/expense creation, sites, contracts, claims and Equipment. Workforce/timekeeping remain lighter supporting links. |
| Equipment navigation entered the global module without proving project association. | Project context is validated, assets are selected through authorized assignments, operational events use the project's deployments, and return links are server-built. |
| Documents and basic information occupied consecutive full-width sections. | They share a lower-priority desktop row and stack at narrower widths. Existing DMS controls and archive capability remain available under their permissions. |

The final order is project identity/navigation → KPIs → WBS/Activities → progress/budget → recent activity/contracts → commercial summary/quick actions → documents/information. Existing shared cards, icons, typography, colors and responsive patterns are reused. The optional construction artwork was omitted; no new image dependency was needed.

## WBS and Activities

The prominent **ساختار شکست کار و فعالیت‌ها** section displays actual authorized WBS-node, activity and active-activity counts. These are source counts, not inferred progress percentages. The primary **ورود به ساختار شکست و فعالیت‌ها** action opens the existing project's Controls workspace. Two secondary links target its existing `#wbs-title` and `#activities-title` sections.

The existing requirement for Project Controls, WBS and Activities read authority is preserved. A restricted reader sees an explanation without counts or unauthorized links. An authorized empty project retains an introduction and a working start action. No records are invented for display.

The current schedule-baseline acceptance service explicitly denies acceptance because its governing authority is not approved. The dashboard therefore shows awaiting-baseline / measurement-unavailable states. It does not derive progress from activity counts, spending or contract totals and does not show a decorative 0% chart.

## Equipment context handoff

The dashboard link carries a page-level `project` filter. The server resolves it through the active organization's authorized Project service and existing assignment-read service. The Equipment read service intersects Equipment permission, project scope and authorized assignment identities. A forged sibling or foreign project is denied; an unrelated asset under a valid project context returns 404.

The association means **authorized assignment history**, including historical assignments. It does not claim current deployment, change ownership, or silently modify the global project/site session. The UI explicitly explains that equipment remains company-owned and the projection follows assignment records.

Equipment List retains project context through search, reset, sort/pagination, detail links and XLSX output. Equipment Detail and Operations retain project/asset context and a canonical Project Dashboard return. Operations limits usage, meter readings, fuel, downtime and work orders to authorized project deployments. Meters, qualifications and maintenance plans remain clearly described company-level information for the associated assets. Unassigned operational events are not attributed to a project without deployment evidence.

The selected equipment name/code is visible in the Operations context banner. Asset create/status/archive controls still require their existing organization-level authority; project-scoped read access does not grant those mutations. Operational action visibility uses the existing effective permission/scope checks, including the compound cost-workbench guard. Existing mutation services remain authoritative.

[Independent owner/project-role Chrome retest](evidence/equipment-final.json) · [Operations at 390 px](evidence/equipment-operations-390.png) · [Journey and denial results](evidence/chrome-final.json)

## Metrics and supported actions

| Information | Source and treatment |
|---|---|
| Budget | Existing `Project.estimated_budget`, explicitly labeled **بودجه تخمینی**. It is not relabeled as an approved budget. |
| Recognized cost | Existing Project Cost projection. No actual evidence remains unavailable. Currency mismatch, incomplete coverage, reversals and comparison guards retain their existing behavior. |
| Remaining budget / consumption | Existing Decimal comparison, only with qualifying actual evidence and a positive comparable estimate. No empty-source zero is fabricated. |
| Contract states | Existing tenant/project-scoped Contracts read service and actual status aggregation. |
| Sites and reports | Existing authorized source services. Daily Reports retain the current-revision selector. |
| Documents | Existing authorized DMS projection and exact version/security handling. |
| WBS / activities | Existing scoped read services, excluding unavailable/archived sources according to those services. |
| Progress | Awaiting approved baseline and reliable measurement. No invented percentage or date. |

The screenshot fixture has a persisted estimate of 9,875,000,000 IRR, two active contracts, one daily report, three WBS nodes and three activities. Its unavailable actual cost is intentional. These values live in isolated test data and are never production UI constants. [Source reconciliation](evidence/chrome-final.json). Existing positive, missing-evidence, different-currency and overrun cost regressions also pass.

Quick Report and Expense creation now initialize the authorized project from the dashboard entry. GET initialization uses the existing scoped Project resolver; forged contexts fail closed. Submitted forms retain their normal domain validation and do not trust the query parameter as write authority. The global session remains unchanged. Existing Contract/Claim routes are reused from their authorized commercial projections. Recent record times render in the organization's configured timezone with Jalali display, including a tested Tehran-midnight boundary.

## Responsive and browser evidence

Installed Google Chrome **156.0.8078.80** was used at 100% zoom. The dashboard has one main landmark, Persian RTL content, working hash navigation, visible keyboard focus and no measured horizontal document overflow at all three widths. The overflow menu opens with Enter and closes with Esc, returning focus to its trigger. Native details behavior remains available without the added script.

| Width | Before | Final |
|---|---|---|
| 1440 px | [Before](evidence/before-1440.png) | [After](evidence/after-1440.png) |
| 1024 px | [Before](evidence/before-1024.png) | [After](evidence/after-1024.png) |
| 390 px | [Before](evidence/before-390.png) | [After](evidence/after-390.png) |

[Viewport measurements](evidence/after-responsive.json) · [Ten Chrome groups](evidence/chrome-final.json) · [Empty project](evidence/empty-390.png). The successful sequence exercises WBS and return, every dashboard GET destination, Quick Create initialization, Equipment List → Detail → Operations → Project, authorized project-role access, sibling/foreign denials, missing-baseline states and protected-page regression checks. The 18 final Equipment page states also verify their visible operational destinations and scoped empty state.

The provided development project was additionally rendered through the full Project view, Organization middleware and template inside a read-only transaction, using an existing explicitly authorized member and an unsaved session. It returned HTTP 200. No real project content or credentials were published from that check. This is a read-only view verification rather than a claim that a real-user Chrome session was manipulated.

## Tests, remediation and isolation

| Check | Result |
|---|---|
| `apps/projects/test_project_operations_dashboard.py`, `test_command_center.py`, `test_photo_gallery.py` | **25 PASS, six subtests PASS**. Seven new methods cover hierarchy/source counts, restricted reads, project-scoped Equipment/XLSX, same-asset cross-project event isolation, forged contexts, Quick Create initialization and organization-local timestamps. [Final log](evidence/acceptance-tests.log). |
| Focused post-remediation methods | **6 PASS, six subtests PASS** before adding the seventh timezone case. [Focused evidence](evidence/affected-final.log). |
| Independent Chrome | **10/10 groups PASS**, plus **18/18 Equipment page states PASS**, with no observed browser errors. |
| Django system/schema | PASS. **462 migrations applied, zero pending** in the isolated final database; no migration file was added. [Schema witness](evidence/schema-final.json), [system checks](evidence/system-check.log). |
| Ruff / JavaScript | Ruff check and JavaScript syntax PASS. Changed functions are formatted. Whole-file formatting passes except the incoming Daily Reports view's pre-existing formatting debt, which remains outside the changed function. [Static checks](evidence/final-static.log), [format comparison](evidence/format-status.json). |
| Protected pages | Company List and Detail passed current Chrome at all three widths; Projects List loads successfully. Their templates/dedicated styles and B11 artifacts retain entry hashes. [Hashes](evidence/protected-hashes.json). |

Early attempts exposed a duplicate Progress anchor and an Operations banner that did not name the selected equipment; both were corrected and independently retested. Other failed attempts were bounded harness issues: a missing fixture category/settings record, reading a FileResponse without consuming its stream, and requesting an empty sibling project as the restricted actor. Original result logs remain separately available; oversized response HTML and live CSRF values were removed from published logs. They do not replace the final passing evidence.

All fixture creation, browser sessions and automated tests used dedicated `project_redesign_*` / `test_project_redesign` databases and private storage on the loopback validation cluster. The databases were cloned from the previously migrated, empty validation baseline. They contain synthetic persisted domain records, not a copy of operational tenant data. A corrected isolated bootstrap/migration check supersedes the recorded connection-timeout attempt. The final schema witness verifies the actual configured database and private data directory.

No production operation or existing-development business mutation was performed by this redesign. The single development verification was read-only. No commit or push was performed. Historical B11 results and original evidence were not rewritten. [Verification summary](evidence/verification-summary.json) · [Final preservation/resource closeout](evidence/closeout.json).

## Changed files

| Files | Purpose |
|---|---|
| `apps/projects/dashboard.py` | Authorized WBS counts, Equipment handoff and supported Quick Actions. |
| `apps/projects/views.py` | Organization-local rendering for Project Detail only. |
| `apps/projects/templates/projects/detail.html` | Revised hierarchy, WBS centerpiece, progress state, quick actions and secondary composition. |
| `apps/projects/static/projects/detail_dashboard.css`, `project_dashboard.js` | Scoped responsive styling and keyboard handling for the section overflow. |
| `apps/equipment/services.py`, `views.py` | Assignment-backed project projection, event filtering, contextual URLs and effective action visibility. |
| `apps/equipment/templates/equipment/list.html`, `detail.html`, `operations_workbench.html`, `_project_context.html` | Preserved project/asset context, ownership explanation, return paths and scoped empty state. |
| `apps/daily_reports/views.py`, `apps/expenses/views.py` | Authorized GET project initialization for Quick Create. |
| `apps/projects/test_project_operations_dashboard.py` | Seven focused regression methods. |
| Design conformance registry | Dated follow-up record, preserving earlier decisions and B11 history. |

No model, permission catalog, migration, shared shell, shared financial calculation or application dependency changed. The existing accepted Projects List and PO-edited Company designs remain protected.

## Remaining Product Owner decision

Review the final visual hierarchy, WBS emphasis, responsive density and navigation against the supplied direction. **Project Detail remains READY_FOR_PO_VISUAL_REVIEW / PO_ACCEPTANCE_PENDING.** B11's historical review states remain unchanged. This implementation does not issue broader MVP acceptance or production certification.
