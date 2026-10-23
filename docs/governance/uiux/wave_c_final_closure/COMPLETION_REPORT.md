# Wave C final closure pass — 2026-10-23

Decision: **WAVE_C_PENDING_REAL_TIME_CONDITION**. Wave C cannot yet be declared complete.

Bounded authority: [attached Human request](AUTHORIZATION.txt), existing D01–D05 and existing PD-WC-07 scanner procedure. No Authorization architecture, catalogue/default-role reconciliation, business decisions, Waves A/B, Production or CEP execution was reopened. Branch `main`; entry/end HEAD `43ac319c6e73e48ca9626461b73987922c498ec3`, matching upstream. [Entry state](ENTRY.json) preserves accepted dirty-source hashes; [integrity](INTEGRITY.json) verifies the bounded delta.

## 1. REGRESSION_ATTRIBUTION

All ten original failure conditions are classified in [REGRESSION_ATTRIBUTION.json](REGRESSION_ATTRIBUTION.json): **7 ATTRIBUTABLE_REGRESSION, fixed; 3 BASELINE_PREEXISTING, retained; 0 INDETERMINATE; 0 unresolved attributable regressions**. Counts classify causes, rather than subtracting totals of failed test methods.

| Original case | Classification | Final disposition |
|---|---|---|
| test_permission_is_intersected_with_project_scope | ATTRIBUTABLE_REGRESSION | Fixed |
| test_payroll_registry_is_complete_and_owner_admin_are_denied | BASELINE_PREEXISTING | Retained |
| test_review_is_permissioned_read_only_and_preserves_downstream_state | BASELINE_PREEXISTING | Retained |
| test_tenant_permission_and_project_scope_hide_match_evidence | BASELINE_PREEXISTING | Retained |
| test_correction_is_atomic_and_reconciles_versions_without_overwriting_history | ATTRIBUTABLE_REGRESSION | Fixed |
| test_explicit_reversal_is_idempotent_and_cannot_reactivate_or_post | ATTRIBUTABLE_REGRESSION | Fixed |
| test_reversal_permission_has_no_implicit_system_role_grants | ATTRIBUTABLE_REGRESSION | Fixed |
| test_reversal_preserves_aging_cutoff_and_reconciliation_amount | ATTRIBUTABLE_REGRESSION | Fixed |
| test_settlement_writeoff_and_source_reversal_keep_their_own_authorities | ATTRIBUTABLE_REGRESSION | Fixed |
| test_additive_migration_preserves_existing_obligation_and_source_history | ATTRIBUTABLE_REGRESSION | AP permission regression fixed; HEAD schema debt retained |

Immutable HEAD export: **5 PASS / 5 FAIL** ([frozen.xml](frozen.xml)); accepted entry: **0 PASS / 10 FAIL** ([entry_before.xml](entry_before.xml), replayed from saved entry modules). Some HEAD tests fail at an earlier legacy-authority setup barrier. The unchanged incomplete Match Review approver is separately proved denied at its exact policy guard under frozen HEAD in [FROZEN_APPROVER_PROBE.json](FROZEN_APPROVER_PROBE.json), with [AST/source attribution](SOURCE_ATTRIBUTION.json). Its temporary repair was restored byte-for-byte; unrelated baseline debt was not absorbed.

Final focused selection: **6 PASS / 4 baseline FAIL** ([fixed_final.xml](fixed_final.xml)). Final affected regression: **45 main tests + 10 subtests PASS / 2 baseline fixture FAIL** ([affected_final.xml](affected_final.xml)). Full repository regression was not run and is not claimed green. Earlier `fixed_10.xml`/`affected.xml` are superseded because they temporarily included the baseline-only approver repair.

The AP migration case's new permission failure is fixed. It now reaches the same **pre-existing `WriteOffProposal.corrects_id` schema mismatch** as immutable HEAD: the test pins `subledgers.0005` but calls current services requiring the field introduced by unchanged migration `0007`. This is one additional unmasked baseline condition, not an unresolved attributable regression. It is preserved without changing domain services, schema or the migration target. The other retained final failures are the Payroll registry omission and the two incomplete approver-fixture cases.

The bounded fixes reuse the sealed-custody test's already active role assignment, remove its organization scope before the unrelated-project denial, assign the AP fixture's intended custom role explicitly after migration, and assert only the approved `accountant` reversal default. Product authorization and financial services are unchanged. Scoped Ruff lint/format, Django check and migration drift pass. A pre-existing formatting issue in the restored, unchanged Match Review file was not repaired.

## 2. RV-029_FINAL

**PASS.** No qualifying populated Development history existed ([discovery](DATA_DISCOVERY.json)). Canonical DMS/category and Employment services produced one labelled synthetic document with two genuinely scanned versions and two append-only Employment records for the existing explicitly linked actor. No person, employee, identity link or work relationship was inferred or created. The old Employment version remains unchanged and explicitly superseded; current/historical states and effective dates are visible.

[Real HTTP](EMPLOYMENT_HTTP.json): **10/10 PASS** for populated management list, named source selection, synthetic employee detail, invalid POST/no write, populated own history, management denial, another-employee denial, cross-tenant denial, same-tenant unauthorized denial and forged own-history selector containment. Missing/mismatched `Employee.user` service and HTTP-layer probes both deny and roll back ([controls](EMPLOYMENT_CONTROLS.json)); source bytes/hash pins and immutable-history denial pass. Document download remains unavailable under its explicit category policy; safety was not bypassed.

Representative desktop **1440×1000** and mobile **390×844** management/detail/error/own-history views pass. The newly populated page exposed **UIUX-F-133**, an attributable presentation defect: raw `Person object (UUID)` labels. Its scoped form/template correction uses existing person names and employee number, with regression assertions and [current HTTP](FINAL_HTTP_DELTA.json). Identity resolution and permissions are unchanged.

[Fixture provenance and scanner results](EMPLOYMENT_FIXTURE.json), [browser reconciliation](BROWSER_RECONCILIATION.json), [mobile current/history](employment_own_history_lower_mobile.png).

## 3. RV-030_FINAL

**PASS.** Existing Development activation and Commercial specialist were reused. Authenticated browser verification covers list/create/detail, named project selection/context, invalid required-reference redisplay, draft → submitted → under review → lost, preserved revisions and state-dependent actions. Terminal mutation is denied with HTTP 400 and four revisions retained ([delta](FINAL_HTTP_DELTA.json)). Corrected form IDs are unique; selected captures have one main and no page overflow. Basic Tab/focus visibility is verified in both representative layouts. No raw policy/UUID metadata dominates the ordinary flow.

Tender has no separate counterparty field. Existing contract/commercial-review counterparty evidence is retained; no new counterparty or policy semantics were invented. Earlier service/HTTP evidence is reused. Browser timeouts/autoreload transients were recovered through documented browser APIs. Incorrect-tab/viewport attempts are explicitly superseded; final evidence uses verified paths and actual dimensions. No environment setting or product requirement was weakened. No browser blocker remains.

[Desktop terminal](tender_final_desktop.png), [mobile terminal](tender_final_mobile.png), [browser reconciliation](BROWSER_RECONCILIATION.json).

## 4. RV-007_FINAL

**RV-007_PENDING_REAL_CLOSE_CONDITION.** Canonical `WAVE-C-RFQ-A` remains issued. Real close: **2026-10-24 14:46:11 Tehran**. Earliest opening: **2026-10-25 14:46:11 Tehran**. Dates/state match discovery and data fingerprints ([real-time evidence](RFQ_REAL_TIME.json)).

No close, custody/opening transition, confidential comparison, date adjustment, scan/CLEAN fabrication or duty bypass was performed. Close manifest/custody, protected and independent opening, confidential comparison access, unauthorized/site/cross-tenant/manipulated-action denials, source/hash/scan integrity, stage/next-action UI and desktop/mobile post-close verification remain required after the real prerequisites pass. Reaching the scheduled time alone does not prove those prerequisites or authorize early opening.

## 5. REMAINING_EVIDENCE_GAPS

- **PENDING_REAL_TIME_CONDITION:** RV-007's legally/time-valid close and subsequent protected opening/comparison journey.
- **BLOCKED_ENVIRONMENT:** none remaining for the required executable browser/runtime work.
- **BASELINE_DEBT:** three original baseline cases and the separately unmasked HEAD schema mismatch, as detailed above. Other repository baseline debt is outside this selected validation.
- **ATTRIBUTABLE_REGRESSION:** none unresolved; UIUX-F-133 is also resolved.
- **OUT_OF_WAVE_C_CERTIFICATION:** successful official statutory calculation/export/filing acceptance under PD-WC-D03, Production policies/providers/legal certification, Human Sign-off and Production Certification/Cutover. These are not converted to PASS.

## 6. WAVE_C_FINAL_MATRIX

**11 PASS / 1 PENDING_REAL_TIME_CONDITION; Wave C remains open.** Retained PASS rows reuse accepted evidence whose implementation/configuration assumptions remain unchanged; this pass does not claim to re-execute all historical scenarios.

| Scenario | Current result | Coverage / boundary |
|---|---|---|
| RV-007 | PENDING_REAL_TIME_CONDITION | Issued canonical RFQ unchanged. Close 2026-10-24 14:46:11 Tehran; earliest opening 2026-10-25 14:46:11 Tehran. Protected opening/comparison and post-close browser controls not executed. |
| RV-009 | PASS | Prior accepted Inventory result retained; no Inventory changes. |
| RV-011 | PASS | D01 effective Development monetary bridge and populated statements; prior evidence retained. |
| RV-013 | PASS | Approved AP source, compatible posted Treasury source and settlement; prior evidence retained. |
| RV-015 | PASS | Prior workforce foundation result retained; explicit identity unchanged. |
| RV-017 | PASS | Prior Timekeeping result retained; no changed producer/identity semantics. |
| RV-018 | PASS | Ordinary Payroll/Timesheet producer/payslip/handoff preparation and fail-closed prerequisites only. Official statutory success is OUT_OF_WAVE_C_CERTIFICATION under D03. |
| RV-028 | PASS | Prior DMS result retained; additional genuine synthetic-source scans preserve safety. |
| RV-029 | PASS | Two canonical immutable Employment versions; own current/history runtime; explicit identity; management/detail, denial and invalid-POST controls; desktop/mobile verification. |
| RV-030 | PASS | Authenticated create/list/detail and state-dependent transitions through lost; terminal mutation denied; unique IDs; business labels, named project context, responsive/focus evidence. Prior contract counterparty evidence retained. |
| RV-031 | PASS | Prior accepted result retained; no related product change. |
| RV-032 | PASS | Retained original payload/server hash/quarantine/replay/external non-membership evidence retained under D04. |

[Machine-readable matrix](WAVE_C_FINAL_MATRIX.json). RV-018 PASS covers ordinary Payroll and fail-closed prerequisites only; official statutory success remains unvalidated and outside this wave.

## 7. MIGRATION_AND_DATA_INTEGRITY

No new schema/data migration was created or applied by this pass. Accepted Development procurement migration `0016` remains applied; configured Development migration graph is current and drift check reports no changes. Production was untouched.

Synthetic additions are limited to the labelled Tender/browser and Employment/source fixtures, genuine assessments, required typed link and append-only audit. All pre-existing business rows remain; the document numbering counter is the only changed pre-existing row in the Employment-entry snapshot. Workforce identity, RFQ state/dates, future policy versions and unrelated financial/Payroll/Inventory rows are unchanged. Identity-negative probes roll back; no finalized history was overwritten. Statutory calculations/outputs remain zero. [Data/source integrity](INTEGRITY.json).

The approved, existing PD-WC-07 platform-duty service provisioned a separate scanner target using the existing single-Superuser grant contract. Genuine Defender scans passed. **The time-bounded scanner duty remains active until 2026-10-23 02:03:51 Tehran** unless independently revoked. Early revocation was denied because that service requires a second active Superuser, which is absent. No second Superuser, policy bypass, direct role edit or false revocation claim was introduced. Expiry is enforced by the unchanged authorization service; the exact assignment/expiry is recorded in integrity evidence. This is disclosed Development fixture authority, not Production authority or a change to the role matrix.

## 8. GIT_AND_PRODUCTION_BOUNDARY

`main` / HEAD and upstream unchanged. Branch/worktree creation: **NO**. Git add/commit/push/merge/rebase/reset/stash: **NOT_EXECUTED**. The frozen source is a read-only Git archive export without Git metadata, not a worktree. Unrelated accepted dirty files and previous closed findings are preserved. CEP Registry and Roadmap are unchanged.

Production deployment/migration/data change/cutover, Human Sign-off and Production Certification: **NOT_EXECUTED**. Wave D and CEP-078/079: **NOT_EXECUTED**. No automatic continuation or new monitor was created. Existing Development processes were preserved.

## 9. FINAL_DECISION

**WAVE_C_PENDING_REAL_TIME_CONDITION**

STOP. No full Wave C completion or certification is claimed.
