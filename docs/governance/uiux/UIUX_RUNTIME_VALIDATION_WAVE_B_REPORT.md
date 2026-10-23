# BONIRA UI/UX Targeted Runtime Re-validation

## Baseline

Branch `main`; product HEAD and `origin/main` `43ac319c6e73e48ca9626461b73987922c498ec3`; divergence 0/0. Development `http://127.0.0.1:8001/`, configured loopback PostgreSQL `construction_erp`, settings `config.settings.development`; zero pending migrations. Microsoft Edge 155.0.4283.62, genuine isolated headless browser login sessions; desktop 1440×900, tablet 1024×768 and mobile 390×844 sampled. Execution 2026-10-21T22:48:19.708000+03:30 to 2026-10-21T22:57:41.075000+03:30 (Asia/Tehran).

Existing untracked UIUX/graphify artifacts preserved. This is observation → evidence → classification, not remediation, full runtime-audit closure, Human Sign-off, Production Certification or CEP-078/079 execution.

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

Owner comparisons use the designated retained Owner; no-workspace uses the preserved Supervisor. Pagination subset PASS (25/5, filter/sort/query preservation, clear and keyboard), with aggregate existing date-label FAIL_ACCESSIBILITY retained. RV-033 scheduled/revoked states observed; whole readiness UI remains PARTIAL. [Detailed addendum](UIUX_RUNTIME_VALIDATION_WAVE_A_ADDENDUM.md).

## Updated Wave A Decision

**WAVE_A_COMPLETE_WITH_EXPLICIT_EVIDENCE_GAPS**

All newly executable bounded Wave A targets are evidence-classified. Reporting/Closeout authorization and natural error/unauthorized-Home UTV remain. This does not require every artificial/unavailable state to PASS.

## Wave B Runtime Results

| Scenario | Persona/target | Result | Evidence | Finding |
| --- | --- | --- | --- | --- |
| RV-006 | P-17 / Estimate context/cascade subset | FAIL_UIUX | RV-EV-024 | UIUX-F-105 |
| RV-006 | P-17 / Expense context/cascade subset | PARTIAL | RV-EV-025 | — |
| RV-006 | P-17 / Daily Report choice boundary | FAIL_PERMISSION_OR_SCOPE | RV-EV-026 | UIUX-F-055, UIUX-F-111 |
| RV-006 | P-17 / Equipment Assignment choice boundary | FAIL_PERMISSION_OR_SCOPE | RV-EV-027 | UIUX-F-057, UIUX-F-111 |
| RV-008 | P-17 / Approved-request PO preparation | FAIL_PERMISSION_OR_SCOPE | RV-EV-028 | UIUX-F-054, UIUX-F-111 |
| RV-010 | P-05 / Journal form/dimensions/hierarchy | FAIL_UIUX | RV-EV-029 | UIUX-F-030, UIUX-F-074, UIUX-F-075, UIUX-F-112 |
| RV-012 | P06 Treasury | BLOCKED_PERMISSION / BLOCKED_TEST_DATA | RV-EV-031 | Existing entry/account/source gaps |
| RV-014 | P07 Billing | BLOCKED_PERMISSION / BLOCKED_TEST_DATA | RV-EV-031 | Specialist/contract-term/lifecycle gaps |
| RV-019 | P04 Equipment/Fleet | BLOCKED_PERMISSION / BLOCKED_TEST_DATA | RV-EV-031 | Data alone is not specialist authority |

RV-006 Estimate/Expense browser context/cascade subset works for permitted A/B. Defaults follow selected session project; with no fixed session project, A→B replaces child choices and resets stale phase. A fixed session context intersects child options (form B under session A is empty until session switches). Canonical Expense `/expenses/create/` used. No business POST or artificial delay/error injection; manipulated-write and natural loading/error behavior remain UTV.

Daily Report and Equipment Assignment expose ungranted C/D project/site metadata; PO preparation exposes ungranted C/D requests/projects. Paths stopped immediately. No subsequent request selection/item reuse/PO transaction or affected-path mutation. P17 is the actual operational Project Manager explicitly permitted by provisioning for RV006/RV008 preparation; no Procurement Buyer or Fleet specialist substitution is claimed.

RV-010 uses canonical Accountant with legitimate organization financial scope: C/D visibility is not a P05 scope failure. Inline draft-detail line form retains independent Site/WBS choices and stale Site A after selecting Project B (F074). Source/evidence/reconciliation fields confirm F075/F030. Two balanced saved lines contain actual project/site/WBS values but ordinary dimension summary shows dash plus UUID (F112). [Read-only dimension verification](runtime_evidence/diagnostics/TARGETED_RUNTIME_DIMENSION_VERIFICATION.json). The `/line/` endpoint is POST-only (GET 405); usable line form is inline on detail. No journal/line created, submitted or posted. Styled representative desktop/tablet/mobile and focus checks ran; no page-level mobile overflow observed. No screen-reader or financial-posting certification claimed.

## Remaining Wave B Blockers

- P03 bounded Buyer, P04 Fleet, P07 Billing and P24 technical-office specialist roles remain absent. No role invented or Owner/platform substitute used.
- P02 Member supports only a subset; its affected Daily Report path was not repeated after F111. P17 advanced comparison/exception permissions remain missing.
- RV-024 Reporting/Closeout remains BLOCKED_AUTHORIZATION_FIXTURE: quarantined identity, no roles/scopes, canonical assigner-subset denial, no closeout case.
- RV-012: P06 A/B grants do not satisfy organization entry; no active mapped Treasury account, independent checker, eligible approved source or movement lifecycle.
- RV-014: approved baseline/progress is insufficient without approved contract terms for cutoff; certificate/statutory/invoice lifecycle unavailable.
- RV-019: meter/reading/usage/plan/work-order data exists, but no P04 authority, approved qualification or cost policy/rate. No new Fleet runtime claim or repeated maintenance-list read. P17 fixture actor is not specialist readiness.
- Security-stopped follow-on paths, manipulated business POST rejection and natural loading/error variants remain UTV. No fixture altered to force PASS.

## Security / Tenant Isolation

Unauthorized access observed: **YES** — same-tenant selector metadata only.  
Cross-tenant leakage observed: **NO**, bounded to sampled paths.  
Object-scope leakage observed: **YES** — ungranted C/D metadata, F111.

RV-EV-026/027/028 capture disclosure; affected paths stopped. Successful unauthorized business mutation was not tested/proved. Independent RV-EV-030 boundaries: P17 Project A direct URL 200; C and Tenant B project URLs 403; search A/B only and no Tenant B; unauthorized C/Tenant B form-options 200 with empty options; cross-tenant member authorization 403 for actual Owner/Admin. Captured form project/site/WBS/request IDs show no Tenant B selection in sampled paths. Passing direct/search boundaries do not erase selector leakage. No complete security certification.

## New Findings

- **UIUX-F-111 / HIGH / FAIL_PERMISSION_OR_SCOPE:** ungranted same-tenant project/site/request metadata in create selectors. RV-EV-026/027/028. No remediation.
- **UIUX-F-112 / MEDIUM / FAIL_UIUX:** saved journal dimensions absent from ordinary line summary. RV-EV-029 and independent dimension verification.

[Findings register](UIUX_FINDINGS_REGISTER.yaml) retains original assessments and appends later history. F015/016/017/020/030/065/066/074/075/105/109/110 confirmed in bounded observations; F054/055/057 partially confirmed before security stop. F085 NOT_REPRODUCED for Daily Reports only, with static component evidence retained and applicability review. Reporting/Closeout F043–047 remain NOT_EVALUATED. No domain rule or Product Decision inferred.

## Reference Persona Retention

REFERENCE USERS DELETED: NO  
REFERENCE USERS AUTO-DEACTIVATED: NO

All authorization and 514 model fingerprints match. No account retirement, cleanup, credential reset or fixture change. Passwords remained in existing DPAPI storage and process memory; no credentials/tokens/cookies/CSRF payloads saved.

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

Only authentication/session bookkeeping and governed context selection. No business/admin POST, migration, role/permission creation, quarantine bypass or fixture change. Original Wave A report/evidence and provisioning artifacts preserved. [Focused artifact/integrity verification](runtime_evidence/diagnostics/TARGETED_RUNTIME_VERIFICATION.json).

## Final Decision

TARGETED_RUNTIME_VALIDATION_PARTIAL

STOP. No Wave C, remediation or additional provisioning.
