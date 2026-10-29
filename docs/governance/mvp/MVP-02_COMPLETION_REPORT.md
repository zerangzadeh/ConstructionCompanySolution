# MVP-02 — Field Workforce MVP

**Status: COMPLETE — Development/non-production only, 2026-10-29 (Asia/Tehran).**

## Completion record

1. **Package:** MVP-02 — Field Workforce MVP. Authorization is the Human Product
   Owner's supplied MVP-02 request. No other package or production action is authorized.
2. **Result:** all AC-01–AC-17 PASS. This is bounded implementation completion;
   it issues no Human Sign-off, production certification, commercial MVP readiness,
   complete HR/Payroll readiness, or Full ERP readiness.
3. **Git grounding:** branch `main`; starting and ending HEAD
   `13e0b1d85f766336eca8286a904e3080b4597f9c`; local `HEAD...origin/main` is `0/0`.
   No remote freshness beyond that local reference is claimed.
4. **Working tree:** clean at entry; bounded source, tests, documentation and
   package evidence remain uncommitted for review. Exact inventory and hashes are
   in [VALIDATION.json](../../../output/mvp-02/VALIDATION.json). Test-generated
   historical CEP-062 traces were restored to HEAD content with Windows checkout line endings. Synthetic P7 document
   files were preserved under package evidence, outside operational document storage.
5. **Identity:** `User` remains authentication; tenant `Person` remains human
   identity; effective-dated `WorkRelationship` explicitly links legacy `Employee`.
   Employee continues to own operational compatibility for assignments, skills,
   qualifications and time entry. No Worker model, wholesale cutover, inferred
   identity matching, or mandatory backfill was added. New workers require an
   explicit collaboration start date. Legacy identity establishment requires date
   evidence; ambiguous existing links fail closed for governed reconciliation.
6. **National ID:** optional `Person.national_id`; Persian/Arabic digits normalize
   to ASCII and blanks to NULL; existing Iranian checksum validation is reused.
   A partial database unique constraint enforces non-null uniqueness per tenant.
   The same value in different tenants is permitted. Explicit direct/legacy User
   links reject contradictory non-empty IDs and competing effective Person links.
   Later User-ID edits and account linking cannot silently drift. Existing User
   authentication-ID uniqueness/validation remains unchanged. Short identity writes
   serialize with a PostgreSQL transaction advisory lock; identity services acquire
   it before their row locks. Ordinary partial User/Employee updates that exclude
   identity fields avoid that lock. IDs are not copied into audit metadata.
7. **Migrations:** `apps/organizations/migrations/0125_mvp02_field_workforce_permission.py`
   and `apps/workforce/migrations/0016_mvp02_person_national_id.py` applied successfully
   to configured Development. Drift check and package-target migration check PASS.
   Historical-model tests prove legacy values, dates, explicit links and optional
   absence of national ID survive forward/reverse/forward. The permission migration
   supports reverse/forward reactivation without granting tenant custom roles.
   Built-in defaults retain the new operational-edit permission through existing
   catalog bootstrap. Global migration check still fails on previously pending
   `payroll.0010_cep069_reviewed_statutory_context`; it was not applied here.
8. **Operational UI:** focused Persian RTL list/search/filter, 25-row paging,
   worker creation/editing without login, personnel number, national ID, contact,
   position/project profession, crew, project/site assignment and active state.
   Skill/qualification facts are shown only with their existing read permissions.
   Existing status services retain active-assignment and finalized-history guards.
9. **Context:** Project, Site and Daily Report links enter validated scoped Workforce
   or Timekeeping context. Context continues into employee and time-entry forms,
   histories, detail links and timekeeping actions. Contextual worker creation
   requires explicit assignment confirmation and commits identity/assignment atomically.
10. **Domain separation:** Attendance, Timesheet/allocation and Overtime still use
    their existing services, states and approval rules. Browser entry produced one
    independent record of each and one explicit timesheet allocation. Daily Report
    aggregate manpower remained unchanged; navigation creates no domain facts.
11. **MVP-GAP-016:** confirmed against the old workbench's 30/20 fixed slices.
    Five histories now have independent 25-row paging plus server-side date,
    project, site and worker filters. Datetime filters use tenant timezone; invalid
    filters fail closed. Own empty draft timesheets remain discoverable. Relative
    query-growth checks cover 1 versus 25 displayed workers and 1 versus 32
    attendance records; no row-dependent query growth remains in those checks.
    Qualification status reuses prefetched lifecycle evidence.
12. **Product Surface:** existing central `field_workforce` capability and operations
    navigation own exposure; legacy Employee entry routes adapt through the central
    profile. Full HR/ESS stays hidden, including direct URLs in MVP. The raw JSON
    attendance-import UI is centrally classified as technical administration and
    hidden in MVP; its backend and FULL_ERP availability remain intact.
13. **Technical leakage:** business labels replace model/UUID selector labels;
    worker/project/site/team choices are searchable and bounded to 40 results,
    retaining selected values while validating against full scoped querysets.
    Raw attendance exception codes are replaced by business notes, and visible
    leave text is Persian. No raw UUID input is required in the verified journey.
14. **Changed files:** 51 source/docs/test files; exact inventory is in VALIDATION.json.
    Main additions are field forms/selectors/services/views/templates, identity
    integrity guards, two additive migrations, paginated timekeeping histories,
    contextual links and focused PostgreSQL/Chrome verification. No dependency added.
15. **Automated validation:** final affected run **181 PASS, 0 FAIL, 61 subtests PASS**;
    five independently reproduced unrelated baseline tests are explicitly deselected.
    Those five also failed in the broad investigation and in the isolated recorded-HEAD
    registry/Product Surface probe. Commands, files, deselections, checks and logs
    are recorded in VALIDATION.json. Changed-Python Ruff, Django system check,
    13 template compilations, static resolution, JavaScript syntax and diff checks PASS.
16. **Browser:** **18/18 checks PASS**, scenarios A–H, real headless Chrome/CDP against
    an isolated PostgreSQL live server. Nine desktop/mobile screenshots and actor
    result files are under [browser evidence](../../../output/mvp-02/browser/).
    Screenshots were visually reviewed; desktop is 1440px and mobile is 390px.
17. **Authorization/isolation:** new `employees.change_operational` is registered and
    enforced inside transactions. Creation/editing/linking retain organization-level
    authority. Explicit `employees.view` can read only matching assignment projections
    under project/site grants; assignments never grant permission. Foreign context
    and selector values fail closed. Mixed-site sheets require complete entry scope
    before exposing entries/totals; direct leave/overtime/correction details require
    their source permissions. Existing identity, own-data and authorization tests pass.
18. **Acceptance:** all 17 criteria PASS; traceability is below. AC-14 was required
    and implemented, rather than marked NOT_REQUIRED_FOR_MVP-02.
19. **Attributable regressions:** none remain. Initial fixture/probe defects and
    the observed query-growth issue were repaired before final validation. Active
    ESS tests now use FULL_ERP to verify preserved own-data security, assert current
    navigation rather than retired NAV IDs, and retain linked/unlinked direct-URL
    checks. The old timekeeping heading assertion now verifies separate history
    sections and hidden technical import. MVP denial has separate automated/browser coverage.
20. **Pre-existing/out-of-scope:** global permission-registry duplicate Payroll model
    registrations, enforcement-reference gaps and 77 namespace mismatches; two
    pre-MVP platform navigation/route expectations; and the pending Payroll migration.
    See [baseline findings](../../../output/mvp-02/baseline-findings.json). No global
    catalog repair, platform-navigation redesign or Payroll work was absorbed.
21. **Documentation:** Roadmap, strategy implementation-status section, current
    domain/data identity guide, the narrow persistent workforce status sentence,
    and this report synchronized. Frozen D1–D7, historical implementation records,
    canonical CEP prompts and CEP_EXECUTION_REGISTRY.yaml remain unchanged.
22. **Deferred:** MVP-03 Billing, MVP-04 Procurement/Inventory, MVP-05 XLSX, MVP-06
    print, MVP-07 P1 outputs/usability and MVP-08 complete demo states/final E2E/Human
    UAT. The reusable synthetic crew fixture is package verification data, not a
    global demo seed. Automatic continuation stops here.
23. **Git writes:** NONE. No branch/index/commit/push/merge/rebase/worktree/ref write.
    No production migration, deployment, certification or Human sign-off.

## AC traceability

| AC | Result | Evidence |
| --- | --- | --- |
| 01 Existing model | PASS | Person/WorkRelationship/Employee reuse; no new identity table |
| 02 Non-login | PASS | Focused create/edit; browser A; User remains absent |
| 03 National ID | PASS | Person field, checksum/normalization/read/edit and migration tests |
| 04 Link consistency | PASS | Person/User/Employee/episode conflict tests and concurrent-ID test |
| 05 Tenant integrity | PASS | Per-tenant DB uniqueness, foreign-tenant and forged-selector denials |
| 06 Simplified UI | PASS | Field list/detail/create/edit; browser A/B/H |
| 07 Operational data | PASS | Crew/profession/assignment/status and permissioned skill/qualification tests |
| 08 Timekeeping | PASS | Browser D; source-separated services/states and focused tests |
| 09 Context | PASS | Actual Project→Site→Workforce and Report→Timekeeping clicks, B/C |
| 10 Product Surface | PASS | Central capability/nav tests; hidden HR/ESS/import URLs denied |
| 11 Authorization | PASS | Scoped read/write, source permissions, mixed-sheet and P1.1 regressions |
| 12 No inferred facts | PASS | Report aggregate unchanged; independent explicit time records |
| 13 Leakage | PASS | Bounded business selectors; actual browser labels/forms/RTL review |
| 14 History usability | PASS | Fixed slices replaced; date/context filters, independent paging, stable query growth |
| 15 Migration safety | PASS | Development apply, no drift, historical-model preservation and recovery |
| 16 Browser | PASS | A–H, 18 successful checks and 9 screenshots |
| 17 Regressions | PASS | Final 181 tests/61 subtests; five baseline failures separately reproduced |

## Recovery boundary

A code rollback may retain the additive nullable field and existing legacy records.
Do not contract the schema merely to roll code back. If reversing the national-ID
migration in a non-production recovery, first export/back up newly entered IDs;
Django's reverse AddField removes that new column. The preservation test exercises
legacy NULL values, not a claim that column removal preserves newly entered IDs.
Permission reversal deactivates its catalog entry; forward execution reactivates it.
Production rollback/migration remains outside this authorization.

Recursive deletion of generated test-document folders was rejected by automatic
approval review (`blocked by policy`). A safer, reversible move preserved the five
verified synthetic `%PDF-1.4 / P7` fixtures in `output/mvp-02/test-generated-documents/`.
No user documents were deleted. Historical CEP-062 content was restored without a Git diff.


## Product Owner visual review and UI/UX remediation — 2026-10-29

The completion record above preserves the original functional implementation and
validation evidence. The Product Owner subsequently rejected the rendered
selector interaction and visual/interaction quality. That rejection does not
reopen the successful identity/domain/security implementation. Product Owner
visual acceptance is **PENDING**; no Git checkpoint is authorized.

The separately authorized bounded correction and current validation evidence are
recorded in [MVP-02_UIUX_REMEDIATION_REPORT.md](MVP-02_UIUX_REMEDIATION_REPORT.md).
Functional/browser PASS must not be read as Human visual acceptance.
