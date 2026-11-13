# B10 Platform Admin final validation

**13 November 2026, Asia/Tehran. Technical result: 66 PASS.** The MVP matrix records 64 PASS and two `NEEDS_PO_REVIEW` for formal visual acceptance of the current Company List and Company Detail. Zero attributable P0/P1 defects remain unresolved.

| Outcome | PASS | FAIL | BLOCKED | NOT_RUN | NEEDS_PO_REVIEW | PO_ACCEPTED |
|---|---:|---:|---:|---:|---:|---:|
| Original Wave 01 | 60 | 3 | 0 | 1 | 2 | 0 |
| B10 technical | 66 | 0 | 0 | 0 | — | — |
| Current MVP matrix | 64 | 0 | 0 | 0 | 2 | 0 |

The 66-row overlay records current and original outcomes side by side. There are 38 rows with current Chrome and PostgreSQL evidence, seven with current Chrome responsive and focused test evidence, and 21 with historical browser journeys carried forward and focused integration checks against the current source. The current matrix retains prior evidence links. The overlay leaves all PO decision fields blank. [Final overlay](B10_FINAL_RETEST.csv) · [Original rows](evidence/b10-24ad220f/B10_ORIGINAL_RESULTS.csv) · [Source compatibility and reconciliation](evidence/b10-24ad220f/pretest-reconciliation.json) · [Row verification](evidence/b10-24ad220f/overlay-verification.json)

| Journey | Qualified result |
|---|---|
| PA-01 Dashboard | Chrome rendered 30 companies, 33 accounts and three memberships, matching PostgreSQL. Active and suspended company KPIs also matched. A credential login opened the dashboard, and the desktop and keyboard-operated mobile menus exposed the same eight destinations. Focused tests checked the activity window, empty state and visibility. |
| PA-02/03 Companies | Chrome checked the current Company List and Detail at 1440, 1024 and 390 px. Search found the exact company, row navigation reached its detail, and no-results, keyboard sorting and page 2 worked. Focused tests requalified onboarding, distinct initial owner, rollback, stale edits, suspend/reactivate, permissions and audit. Both PO-edited templates and their dedicated CSS retain their entry fingerprints. |
| PA-04/05 Accounts | Current directory, detail, create and edit screens passed responsive checks. Existing integration tests confirmed scoped membership references, account creation without tenant grants, protected accounts, audited edits, activation/deactivation, and invalidation of old sessions and tokens. |
| PA-06 Recovery | Wave 01 Chrome and isolated SMTP evidence covers delivery, failure, cooldown, link use and temporary passwords. Current tests requalified the stored recipient, transport outcomes, cooldown, invalid/expired/used tokens, forced change, target and CSRF guards, and absence of credential disclosure. |
| PA-07/08 Roles | Current tests covered operator grant/revocation, last administrator protection, stale and protected role updates, explicit tenant authority, independent approval and forged target denial. Chrome exposed exactly one named company combobox at each width. Keyboard selection and the native fallback worked. A Platform-only actor could select a company without seeing its member grants. |
| PA-09 Settings and catalogs | The MVP profile stayed read-only. Chrome recorded a draft and optional synthetic review for the registered `project-controls-budget-overrun-response` policy, published it, published a linked successor and retired the successor. PostgreSQL verified versions, review, actors and audit. Stale draft edit/publication, duplicate publication and invalid CSRF failed closed. The protected-operation dialog sent zero POSTs on Cancel and one on Confirm. The confirmed version received one retirement audit event. Replay preserved prior versions. The B05 statutory dependency remains open. |
| PA-10 Audit and status | Both audit date labels matched the Jalali picker. Invalid dates stayed visible with validation at all three widths. A direct malformed request returned an empty result with the input retained. Combined actor, company, action and date filtering returned 32 events over pages of 25 and 7 with matching PostgreSQL records. Current status rendered safely. The focused failure probe displayed sanitized degraded and unverified states. |
| PA-11 Separation | Separate Chrome contexts issued 86 method-specific requests across all 33 planned row IDs. Tenant Admin requests returned 403 and anonymous requests redirected to login. Denied requests preserved the checked business and audit tables. A Platform-only session had no tenant membership and was denied tenant lists, project detail/export/create and technical Django Admin in MVP. B07 evidence and current focused delegation tests qualified explicit tenant access and cross-tenant denials. |

[Current dashboard, company, user and selector checks](evidence/b10-24ad220f/retest/browser-results.json) · [Login, navigation and reverse separation](evidence/b10-24ad220f/navigation/browser-results.json) · [PA-11 exact rows and witnesses](evidence/b10-24ad220f/final/pa11-security.json) · [B07 evidence](B07_EXECUTION_REPORT.md) · [Audit PostgreSQL witness](evidence/b10-24ad220f/final/audit-postgresql-witness.json) · [Policy PostgreSQL witness](evidence/b10-24ad220f/catalog/policy-lifecycle-postgresql.json) · [Retirement PostgreSQL witness](evidence/b10-24ad220f/catalog/protected-retirement-postgresql.json)

## Defects and UI verification

| Finding | Current disposition |
|---|---|
| BON-DEF-0001 | Exactly one named company combobox at 1440, 1024 and 390 px. Native fallback retained. |
| BON-DEF-0002 and UX-R-OBS-01 | Correct Jalali labels and retained invalid values passed the current Chrome and server checks. The later Wave 01 final closeout already delivered the correction. |
| BON-DEF-0003 | Protected retirement confirmation passed all three widths. Cancel and confirm matched the observed audit and record changes. |
| BON-DEF-0051, P2 | The policy editor now shows the saved source basis. Chrome confirmed it stayed `product_defined` through a subsequent edit. |
| BON-DEF-0052, P1 | The policy catalog now checks the expected draft timestamp under the row lock before edit or publication. A stale request preserved the current draft and audit counts. |
| BON-DEF-0053, P1 | The retirement form now identifies the exact version named in the confirmation. The service checks the target under lock. Chrome confirmed rejection of the replay, retention of the prior version and one retirement audit event. |

The 54 responsive observations span the dashboard, company and user pages, compact forms, roles and selectors, settings, status, audit errors and the catalog states. The measured states had one main landmark, RTL direction, labeled form controls and no document overflow. The policy forms reuse Jalali date inputs and accept canonical dates at the server boundary. Internal policy codes, JSON parameters and protected-operation codes remain visible where they identify the existing administrative contract. The Company List and Detail retain their PO-edited design. [Page measurements](evidence/b10-24ad220f/retest/responsive-observations.json) · [Audit measurements](evidence/b10-24ad220f/final/responsive-observations.json) · [Catalog measurements](evidence/b10-24ad220f/catalog/responsive-observations.json) · [Company List at 390 px](evidence/b10-24ad220f/retest/companies-390.png) · [Company Detail at 390 px](evidence/b10-24ad220f/retest/company-detail-390.png)

## Verification and closeout

Local `main` and local `origin/main` both resolved to `24ad220f0376cb0b6232b745938b35433843a32d`, with zero divergence. A new loopback PostgreSQL 18.6 cluster applied 462 migrations from zero and verified zero initial users and tenants. Browser runs used isolated clones, separate synthetic identities and Google Chrome 156.0.8078.80. Focused integration passed 75 tests and 71 subtests. A later overlapping check on the final catalog code passed 13 tests and 21 subtests. Django system checks, migration currency, schema drift, Ruff and scoped whitespace checks passed. [Entry state](evidence/b10-24ad220f/entry-source.json) · [Final fingerprints](evidence/b10-24ad220f/final-source.json) · [Clean database witness](evidence/b10-24ad220f/catalog.log) · [Focused integration](evidence/b10-24ad220f/focused-final.log) · [Final catalog tests](evidence/b10-24ad220f/focused-catalog-final.log) · [Final schema checks](evidence/b10-24ad220f/final-schema-checks.log)

Early test harness attempts hit fixture authorization, selector timing and assertion issues. The qualified runs above supersede those attempts. One legacy policy test expected a tenant policy page to be exposed under MVP. The current exposure policy denies that route under MVP. The focused checks verified the governed exposure behavior. The original Wave 01 reports, 1,065 other MVP matrix rows and concurrent B03–B09 work were preserved. All test mutations used the private cluster. Git changes remain local and uncommitted. B10 ends at this closeout. [Initial focused results](evidence/b10-24ad220f/focused-original.log) · [Defect reproduction](evidence/b10-24ad220f/reproduce-focused.log) · [Overlay verification](evidence/b10-24ad220f/overlay-verification.json)

## Product Owner decisions

1. Record formal visual acceptance or requested design changes for `INV-ORGANIZATIONS-PLATFORM-COMPANY-LIST--PA-03`. The technical result is PASS. [1440 px](evidence/b10-24ad220f/retest/companies-1440.png) · [390 px](evidence/b10-24ad220f/retest/companies-390.png)
2. Record formal visual acceptance or requested design changes for `INV-ORGANIZATIONS-PLATFORM-COMPANY-DETAIL--PA-02`. The technical result is PASS. [1440 px](evidence/b10-24ad220f/retest/company-detail-1440.png) · [390 px](evidence/b10-24ad220f/retest/company-detail-390.png)

The defect register records technical fix and retest dispositions. Formal PO acceptance of the fixes remains unrecorded. The two company visual decisions are the outstanding B10 row dispositions. [Defect register](../DEFECT_REGISTER.md)
