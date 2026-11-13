# B07 execution report

**12–13 November 2026 · MVP · Tenant Isolation, Workflows and Parties**

| Outcome | Planned | PASS | FAIL | BLOCKED | NOT_RUN |
|---|---:|---:|---:|---:|---:|---:|
| First attempt | 48 | 25 | 12 | 0 | 11 |
| Final qualified outcome | 48 | 48 | 0 | 0 | 0 |

**B07 is ready for Product Owner acceptance review.** All 48 rows have actual Chrome and PostgreSQL evidence. Ten defects were fixed and independently retested. Zero attributable P0/P1 defects remain unresolved. Formal PO acceptance remains unrecorded. [Current matrix](../TEST_EXECUTION_MATRIX_MVP.csv) · [Original outcomes](B07_ORIGINAL_RESULTS.csv) · [Final row evidence](evidence/b07-24ad220f/row-outcomes.json)

## Scope

The matrix reconciled to **15 CV-TEN-01**, **11 CV-WF-01** and **22 CV-PAR-01** rows. The latter includes nine Party and thirteen Materials routes. All routes resolve through the MVP Product Surface. The update preserved **1,083 other matrix rows**. [Reconciliation](evidence/b07-24ad220f/retest-tenant-materials/surface.json) · [Preservation](evidence/b07-24ad220f/matrix-preservation.json)

Google Chrome 156.0.8078.80 used separate synthetic actor contexts against a loopback Django server. A real credential login exercised company selection. Other actor contexts used separate authenticated test sessions. The runner reused existing owner-account, context, workflow, procurement, workforce, Party and Materials fixtures. A separate process and read-only database transactions verified persisted state.

## Tenant and authorization

Authorized company switches persisted membership-backed choices. Forged company IDs preserved the prior session. Member lists, details, avatars, settings, role catalogues and account operations stayed tenant-scoped. Owner and Tenant Admin responsibilities remained distinct. Forged elevation, last-owner removal, self-approval, foreign membership updates and restricted mutations caused no unauthorized business change. Independent approval supported role and project grants. View-only authorization retained history with zero mutation controls.

The site actor received only its authorized site and phase. Sibling, foreign and inconsistent payloads failed. Stale context cleared, unsafe return navigation stayed local and revoked membership invalidated the old session. Foreign or restricted document access disclosed no bytes and created no download audit. An authorized download returned the exact synthetic clean version. Project exports denied sibling and foreign targets. Security-denial checks retained audit counts. [Tenant rows](evidence/b07-24ad220f/retest-tenant-materials/browser-rows.json) · [Document, export and session checks](evidence/b07-24ad220f/retest-tenant-materials/supplemental.json)

Connection consent required the target identity. Acceptance created one membership and replay created no additional membership or audit. Rejection created no membership. Invalid decisions preserved pending state. Provisioning required password rotation and omitted credentials on invalid responses. Both authorization expiry forms accepted Jalali datetime input and stored equal aware expiries with independent approval. [Expiry original](evidence/b07-24ad220f/original-expiry/supplemental.json) · [Expiry retest](evidence/b07-24ad220f/retest-expiry/supplemental.json)

## Workflow integrity and concurrency

Chrome created a scoped definition, rejected an unregistered command, saved its four-step graph, validated it and published the exact version. Published edits, foreign versions and insufficiently granted lifecycle actions failed.

A member submitted a representative PR. An independent approver found its item and source link, claimed, released, reclaimed and approved it. Source, item and instance reached their expected terminal states with one approval audit. Duplicate submission, exact replay, stale action, maker/foreign action, invalid outcome and missing CSRF were checked. Rejection used the existing source reason form. My Requests stayed identity-scoped and Manager stayed team-scoped. [Workflow rows](evidence/b07-24ad220f/retest-workflow-parties/browser-rows.json) · [Submission and rejection](evidence/b07-24ad220f/retest-workflow-parties/supplemental.json)

**4/4 final PostgreSQL concurrency cases passed.** Shared workflow claims and decisions had one winner. Daily Report Return covered concurrent decision, correction creation, edit and submission. Safety and Quality competing reviews committed once. Focused regressions also checked document-version pinning, maker separation, rollback and the governed Return path. [Concurrency](evidence/b07-24ad220f/concurrency-retest.log) · [Focused retest](evidence/b07-24ad220f/focused-retest.log)

## Parties and reference integrity

Chrome created individual and company Parties, rejected duplicate identifiers, revised identity and added roles, primary contact and alias. Operational detail stayed read-only. Restricted and foreign writes had no effect.

Contracts and Procurement reused the same Party. Foreign, archived and ineligible suppliers were excluded or rejected. New-order selection excluded inactive supplier roles. Archive retained contract and order FKs, and separate Chrome reads verified both historical records. The protected canonical merge reference retained its source relationship and audit after controlled archive denial. Existing merge behavior supplied only that protected-reference fixture. [Party rows](evidence/b07-24ad220f/retest-workflow-parties/browser-rows.json) · [Reuse and protected references](evidence/b07-24ad220f/retest-workflow-parties/supplemental.json) · [Historical reads](evidence/b07-24ad220f/retest-party-history/supplemental.json)

Materials checks covered scoped lists, creation, normalized duplicates, edits, category/unit FKs, alias actions and archive. Active references protected units and categories. Missing, malformed and foreign governance context caused controlled denial with no write. [Materials rows](evidence/b07-24ad220f/retest-tenant-materials/browser-rows.json)

## Remediation

| Defect | Severity | Corrected behavior |
|---|---|---|
| BON-DEF-0040 | P1 | Member status saves when the browser omits the disabled role field. |
| BON-DEF-0041 | P2 | Authorization observers see permission-appropriate controls. |
| BON-DEF-0042 | P1 | Invalid provisioning responses omit submitted credentials. |
| BON-DEF-0043 | P1 | Invalid connection decisions preserve pending state and audit. |
| BON-DEF-0044 | P2 | Missing, malformed and foreign material context avoids server failures. |
| BON-DEF-0045 | P2 | Protected canonical Party archive returns controlled denial. |
| BON-DEF-0046 | P3 | Party list has one management entry and centralized secondary-link exposure. |
| BON-DEF-0047 | P2 | New-order selection requires an active tenant-owned supplier role. |
| BON-DEF-0048 | P2 | Cartable rejection reaches the existing required-reason form. |
| BON-DEF-0049 | P2 | Role and scope expiry use the shared Jalali picker. |

All ten have focused regression coverage and independent Chrome retests. [Defect register](../DEFECT_REGISTER.md) · [Defect evidence](evidence/b07-24ad220f/defect-outcomes.json) · [Regression tests](../../../../tests/test_b07_remediation.py)

## Design and test qualifications

DC-03/04/05/06/08/09 checks covered **35 page states at 1440, 1024 and 390 CSS px**, totaling 105 observations. The review covered Persian RTL, context, form grouping, navigation, status, feedback, scoped selectors and Jalali inputs/history. The Party form was compared with the approved compact-form reference. Wide member tables retain horizontal scrolling at narrow sizes. Representative screenshots and measurements support the observations. [Design registry](../APPROVED_DESIGN_CONFORMANCE_REGISTRY.md) · [Verification summary](evidence/b07-24ad220f/verification-summary.json) · [Corrected expiry](evidence/b07-24ad220f/retest-expiry/membership-expiry-saved-390.png)

| Validation | Outcome |
|---|---|
| Original focused selection | 127 passed, 15 failed, 17 subtests passed |
| Selected focused retest | 48 passed, 3 setup errors, 22 subtests passed |
| Independent concurrency qualification | 4 passed, including the three setup-affected cases |
| Final remediation and platform-inspector compatibility | 11 passed, 7 subtests passed |
| Concurrent inbound-transfer integration | 3 passed, 3 subtests passed |
| Django checks, migration currency, schema drift and Ruff | PASS |

Original failures included seven historical presentation/exposure/session expectations, five legacy Party fixtures missing explicit authority and three teardown failures involving retained Payment FKs. Qualification reused existing explicit-authority and cascade-cleanup helpers. A later transactional setup emitted ContentTypes before catalogue deserialization. The final concurrency run retained the complete app set and removed that redundant available-app signal in the isolated harness. [Attribution](evidence/b07-24ad220f/failure-attribution.json)

Browser qualification corrected compatibility-workflow seeding, echoed filter assertions, membership IDs, history action codes, selector focus and date-popup dismissal. One historical contract read crossed the 11-second harness budget while suites competed. A separate Chrome check with a 45-second budget passed on the same retained records. Earlier outcomes remain visible.

## Migration and source integration

Entry main, HEAD and local origin/main resolved to **24ad220f0376cb0b6232b745938b35433843a32d**, with zero recorded divergence and existing B03–B06 changes. A new loopback PostgreSQL 18.6 cluster applied **462 migrations from zero**, with zero users and tenants before fixtures. Separate original and retest databases cloned that baseline. B07 introduced no migration. Final system, migration and drift checks passed. [Entry fingerprint](evidence/b07-24ad220f/entry-source.json) · [Migration log](evidence/b07-24ad220f/migration.log) · [Empty baseline](evidence/b07-24ad220f/catalog.log) · [Final checks](evidence/b07-24ad220f/final-checks.log)

Four inbound-transfer files advanced concurrently. Their bytes were preserved and their three focused tests passed. B05 closeout also advanced 53 matrix rows and five existing defect records after the entry snapshot. B07 preserved those current updates while changing its own 48 rows and appending its ten defects. Fingerprints distinguish this delta from B07 changes. B03/B04 Return, B05 closeout and prior evidence remain integrated. Independent read-only PostgreSQL witnesses captured account, Party, material, reference and workflow records. [Final fingerprint](evidence/b07-24ad220f/final-source.json) · [Concurrent B05 rows](evidence/b07-24ad220f/concurrent-matrix-updates.json) · [Party/workflow witness](evidence/b07-24ad220f/b07_retest2-postgres.json) · [Tenant/material witness](evidence/b07-24ad220f/b07_retest-postgres.json) · [Inbound integration](evidence/b07-24ad220f/inbound-integration.log)

All writes used the disposable B07 cluster. Development, demo and Production databases were untouched. Changes remain uncommitted and unpushed. The disposable cluster was stopped after verification. [Execution commands](evidence/b07-24ad220f/execution-commands.json) · [Shutdown](evidence/b07-24ad220f/cluster-shutdown.log)

## Acceptance and B08 entry

**B07 readiness is 48/48 PASS, zero FAIL/BLOCKED/NOT_RUN and zero unresolved attributable P0/P1 defects.** No new unresolved business-rule authority decision arose.

Remaining PO items are formal B07 acceptance and the planned review of role/authorization wording and Party-maintenance discoverability. Every B07 PO acceptance cell remains NOT_RUN. Other waves retain their own decisions.

B08 should reconcile its 21 planned rows, use a fresh isolated database at the integrated migration frontier, and seed source-version-specific outputs with explicit export permissions and tenant cutoffs. Reconcile B05/B06 fixture readiness against their current reports. Carry B07 denials into output and read-model checks. B08 execution was not started.
