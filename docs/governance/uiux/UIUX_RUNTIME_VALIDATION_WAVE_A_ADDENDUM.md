# BONIRA UI/UX Targeted Runtime Re-validation — Wave A Addendum

## Baseline

Branch `main`; product HEAD and `origin/main` `43ac319c6e73e48ca9626461b73987922c498ec3`; divergence 0/0. Development `http://127.0.0.1:8001/`, configured loopback PostgreSQL `construction_erp`, settings `config.settings.development`; zero pending migrations. Microsoft Edge 155.0.4283.62, genuine isolated headless browser login sessions; desktop 1440×900, tablet 1024×768 and mobile 390×844 sampled. Execution 2026-10-21T22:48:19.708000+03:30 to 2026-10-21T22:57:41.075000+03:30 (Asia/Tehran).

This addendum supplements [the original Wave A report](UIUX_RUNTIME_VALIDATION_COMPLETION_REPORT.md), original RV-EV-001 through RV-EV-014 and their screenshots. Original history is not overwritten. Later results are under `targeted_revalidation` in [results](UIUX_RUNTIME_VALIDATION_RESULTS.yaml). No already-sufficient ordinary-user target was rerun except newly enabled pagination. No CEP/UAT/production authority is implied.

## Fixture Layer Verification

[Fixture registry](UIUX_RUNTIME_FIXTURE_REGISTRY.yaml) and [provisioning report](UIUX_RUNTIME_FIXTURE_PROVISIONING_REPORT.md) govern readiness. Authorization fingerprint `dc41830339a943bd6aab2820da7340fc3e7d361f2e3643cae153b5abf3393007` matches current DB and provisioning. All 514 model fingerprints and role/permission catalogue fingerprints match before/after. Zero pending migrations. Recovered credentials worked for the same Owner/Supervisor; actual Tenant Admin, Project Manager and Accountant bundles were used. No fixture or authority was repaired or added. [Before](runtime_evidence/diagnostics/TARGETED_RUNTIME_BEFORE.json), [after](runtime_evidence/diagnostics/TARGETED_RUNTIME_AFTER.json).

Initial new screenshots were unstyled because the external audit harness blocked the configured Tailwind CDN asset. The harness guard was corrected, and styled replacements govern visual/accessibility/responsive claims. [Capture exception](runtime_evidence/diagnostics/TARGETED_RUNTIME_CAPTURE_EXCEPTION.json) retains excluded visual states. DOM options/HTTP evidence from stopped scope paths remains valid; no styled re-entry into stopped paths. Intermediate pre-swap Estimate/Expense observations are superseded by settled captures; they are not final cascade failures. No product change occurred.

## Wave A Gap Re-test

| Scenario | Persona/target | Previous status | New status | Evidence |
| --- | --- | --- | --- | --- |
| RV-002 | P-15 / Owner Home comparison | BLOCKED_ENVIRONMENT: credential | FAIL_UIUX | RV-EV-015 |
| RV-004 | P-15 / Owner navigation | BLOCKED_ENVIRONMENT: credential | FAIL_UIUX | RV-EV-016 |
| RV-005 | P-15 / Owner search comparison | BLOCKED_ENVIRONMENT: credential | FAIL_UIUX | RV-EV-017 |
| RV-026 | P-15 / Tenant Owner administration | BLOCKED_ENVIRONMENT: credential | FAIL_UIUX | RV-EV-018 |
| RV-003 | Supervisor zero-scope / Preserved no-workspace state | BLOCKED_ENVIRONMENT: credential | PASS | RV-EV-019 |
| RV-023 | P-01 / Pagination and date-filter accessibility | BLOCKED_TEST_DATA: 9 rows | FAIL_ACCESSIBILITY | RV-EV-020 |
| RV-004 / RV-026 | P-16 / Tenant Admin navigation/administration | BLOCKED_IDENTITY | FAIL_UIUX | RV-EV-021 |
| RV-002 / RV-004 | P-17 / Project Manager Home/navigation | BLOCKED_PERMISSION | FAIL_UIUX | RV-EV-022 |
| RV-033 | P-16; P15 independent reader / Scheduled/revoked authorization histories | UTV scheduled/revoked | PARTIAL | RV-EV-023 |

Pagination browser subset is PASS: exact page lengths 25/5, filter plus ascending sort survive actual next/previous navigation, `aria-sort` stays ascending, clear empties filter fields while retaining sort. Keyboard activation and representative focus captured. Date-range labels still fail accessibility (F110), so RV-023 aggregate remains FAIL_ACCESSIBILITY. F085 is NOT_REPRODUCED on Daily Reports; the separate static bounded-pagination component finding is preserved for route-applicability review.

Scheduled/revoked histories are now observed: active Tenant Admin, revoked Member, future Viewer bounded to 2099. Future/expired share one label; future and revoked assignments remain ineffective. Full persona readiness/coverage metadata remains PARTIAL, not all 26 personas ready. Owner tenant-role catalogue 403 and Admin catalogue 200 match the explicit Tenant Admin catalogue role gate; both platform-role and cross-tenant member boundaries deny. No role inferred from persona title, and no authority changed.

## Updated Wave A Decision

**WAVE_A_COMPLETE_WITH_EXPLICIT_EVIDENCE_GAPS**

All fixture-cleared bounded Wave A retests executed. This is cumulative execution disposition, not all-PASS or full runtime closure. Reporting/Closeout retain BLOCKED_AUTHORIZATION_FIXTURE; natural runtime error and unauthorized Home remain UTV; advanced Manager comparison and full RV-033 readiness metadata remain gaps. Existing failures remain. Unchanged P21/P26 and later waves stay outside this task.

## Security / Tenant Isolation

Wave A sampled cross-tenant member administration and platform boundaries denied. Broader current results include same-tenant selector leakage on three stopped Wave B paths; see [Wave B report](UIUX_RUNTIME_VALIDATION_WAVE_B_REPORT.md). Do not carry forward the original all-NO security snapshot as current.

## New Findings

UIUX-F-111 (HIGH, selector object-scope leakage) and UIUX-F-112 (MEDIUM, saved journal dimensions absent in display) belong to Wave B. Existing finding assessments are preserved; later assessments appended. No remediation.

## Reference Persona Retention

REFERENCE USERS DELETED: NO  
REFERENCE USERS AUTO-DEACTIVATED: NO

Same persistent identities, role/scope and history retained. Authentication/session bookkeeping and governed context selection only.

## Safety Boundary

PRODUCT CODE CHANGED: NO  
AUTHORIZATION SEMANTICS CHANGED: NO  
NEW PERMISSION CREATED DURING RUNTIME: NO  
SCOPE BROADENED DURING RUNTIME: NO  
PRODUCTION ACTION: NO  
REMEDIATION: NO  
CEP-078 EXECUTION: NO  
CEP-079 EXECUTION: NO  
GIT WRITE: NO

## Final Decision

TARGETED_RUNTIME_VALIDATION_PARTIAL

STOP. No Wave C, remediation or further provisioning.
