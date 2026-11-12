# B03 Daily Reports and Field Operations

**11 November 2026 · MVP · `UAT-03` and `CV-FIELD-01`**

| Scenario | Stage | Planned | PASS | FAIL | BLOCKED | NOT_RUN |
|---|---|---:|---:|---:|---:|---:|
| UAT-03 | Original | 14 | 5 | 8 | 1 | 0 |
| CV-FIELD-01 | Original | 8 | 2 | 6 | 0 | 0 |
| **B03** | **Original** | **22** | **7** | **14** | **1** | **0** |
| UAT-03 | Bounded retest | 14 | 11 | 2 | 1 | 0 |
| CV-FIELD-01 | Bounded retest | 8 | 8 | 0 | 0 | 0 |
| **B03** | **Bounded retest** | **22** | **19** | **2** | **1** | **0** |

The MVP matrix retains the original outcomes. The row evidence records both stages under the same 22 Phase A execution IDs. An independent organization-wide actor completed original Field reviews when the site-scoped actor was denied. The scoped denial remains a failure in the original rows. The protected proposal review POST passed in both stages. Its operator journey remains BLOCKED. Formal PO acceptance is pending. [MVP matrix](../TEST_EXECUTION_MATRIX_MVP.csv) · [Row outcomes](evidence/wave-03-865fa3f3/row-outcomes.csv)

## Source and environment

- `main`, HEAD and upstream at `865fa3f3f7868e81b0aafba05d2683b28fe33b1e`, with the existing Wave 01 and B02 working-tree changes. Reused the Phase A worklist, journey catalog and design registry, the B02 synthetic fixture patterns and its clean PostgreSQL dump. Captured entry status, compared source hashes, and verified the Wave 01 and B02 evidence files, the seven B02 fixed defect records and five B02 blocked rows. [Baseline and preservation](evidence/wave-03-865fa3f3/baseline.json) · [Entry Git status](evidence/wave-03-865fa3f3/entry-status.txt)
- Real Google Chrome `156.0.8078.80` via Playwright, with separate contexts for owner, site recorder, site reviewer, organization-wide fallback reviewer, viewer, sibling-site actor and other-tenant actor. The browser and the read-only PostgreSQL witness used the same guarded run identity. The loopback PostgreSQL 18 cluster held separate original and retest databases with 457 applied migrations and zero pending. Files and DMS custody were private to each database. Synthetic fixtures included two tenants with matching project/site names, sibling and second-project controls, authorized master data, and independent workflow actors. [Run manifest](evidence/wave-03-865fa3f3/RUN_MANIFEST.md)
- Source corrections were bounded to Daily Reports and existing Field permission admission. Validation of the five inline forms was reproduced on the intermediate retest build before their correction. The original Daily Report mutation evidence already showed the same redirect with zero invalid rows. The final affected regression suite ran on a fresh technical clone. [Original inline-form evidence](evidence/wave-03-865fa3f3/original/inline-validation/results.json) · [Technical results](evidence/wave-03-865fa3f3/technical.txt)

Five concurrent project/site list and shared-list source changes arrived during B03 and were preserved. A freshly started server verified the Daily Report context links against those changes. The owner opened both destinations and the site-scoped viewer received only the site link. [Latest context-link witness](evidence/wave-03-865fa3f3/retest/latest-context-links.json)

## Business logic and authorization

| Journey | Browser and persisted-state result |
|---|---|
| Daily Report creation and references | Jalali `1405/08/17` persisted as `2026-11-08` under the intended project, site and active phase. Real Chrome search selected eligible Safety, Quality and DMS records. Two report-owned references persisted and left the source incident and issue in their reported states with their original site and no source-side report assignment. The DMS relationship persisted on the report. A forged foreign-site selection wrote no record. |
| Supporting entries | Labor recorded 4 workers and 6.50 hours. Equipment recorded 2.25 hours. Material retained its master FK, 12.0000 units, and the derived label and unit. Activity retained the project activity, unit, quantity and 45% progress. Delay recorded 1.50 hours on the selected Jalali day. Labor and equipment use the existing descriptive fields. They create no workforce attendance or equipment-usage records through this form. |
| Invalid supporting entries | Oversized values in all five forms wrote zero rows. Original submissions cleared safe inputs. After the correction each form retained its valid fields and displayed the failing field. The print target stays on the canonical report. A wrong-project activity and forged material were rejected. |
| Daily review | A site recorder created and submitted a report in Chrome. An independently authorized site reviewer approved it and closed its work item. A viewer and sibling-site approver were denied. Missing CSRF and repeated submit/approve left the workflow and audit unchanged. Post-approval labor mutation left the approved report unchanged. A separate report still permitted compatibility-policy self-approval and offered no Return transition. |
| Field capture and save | Invalid JSON preserved safe fields after remediation. Repeated create and save retained a single operation result. A stale draft had overwritten the newer content on the original build. Retest rejected it at revision 2 with the newer summary intact. The dedicated location permission is enforced in the detail and edit forms, including a forged location write from a scoped capture-only editor. |
| Field review | Submit recorded the canonical hash. Site-scoped independent review produced `draft → submitted → in_review → accepted`, with the expected actors and stable hash. A separate observation was rejected with its reason. Self-review, missing rejection reason, late attachments, and post-finalization edits did not change protected history. |
| Exact DMS evidence | Used the existing source picker and exercised the existing attachment POST. Clean v1 was pinned once. Pending and foreign versions did not attach. Chrome uploaded v2 to the same DMS document and reopened the source-bound v1. The v1 download matched the persisted SHA-256. The viewer without download authority received 403. The evidence breadcrumb returned to the exact source anchor. |
| Source-only follow-up | Prepared and submitted a proposal from the accepted observation, preserving source identity and canonical hash. The independent site reviewer accepted through the protected endpoint. Exact replay kept two transitions and produced no additional rows in the monitored Daily Report and entry models. The submitted proposal still has no operator review control. |

[Original daily browser and state](evidence/wave-03-865fa3f3/original/daily/browser-and-state.json) · [Original field browser and state](evidence/wave-03-865fa3f3/original/field/browser-and-state.json) · [Retest browser and state](evidence/wave-03-865fa3f3/retest/browser/browser-and-state.json) · [Supplemental Chrome and source witnesses](evidence/wave-03-865fa3f3/retest/supplemental/results.json)

The targeted timestamp regression used the tenant's `Asia/Tehran` setting. Field capture `08:20`, effective `09:10` and location capture `08:19` persisted as `04:50`, `05:40` and `04:49 UTC`. The reloaded Jalali fields showed the original wall times. An edited capture at `08:21` persisted as `04:51 UTC`. Proposal effective `09:45` persisted as `06:15 UTC`. The existing B02 local-time tests passed in the focused suite. The B03 recurrence of the offset failure was in separate Field forms. [Retest values](evidence/wave-03-865fa3f3/retest/browser/browser-and-state.json) · [Focused regressions](evidence/wave-03-865fa3f3/technical.txt)

## Approved design conformance and navigation

Applied the existing [Approved Design Conformance Registry](../APPROVED_DESIGN_CONFORMANCE_REGISTRY.md), [UI guidelines](../../../ui-guidelines.md) and the [existing form rollout](../../../../output/form-standardization/REPORT.md). The Field capture, inline entries and proposal forms use the existing parent-detail and transactional exceptions. The sectioned-form reference retains its existing PO review status.

| Page or state | Registry | Result |
|---|---|---|
| Daily Reports list | DC-02, DC-03, DC-04, DC-08, DC-09 | Persian RTL. Scoped results, pagination, state summaries, named date filters and create gating verified. The date link and detail menu offer the same record destination under the current list pattern. Added the guarded link to Field Observations. |
| Daily Report create and invalid input | DC-03, DC-07, DC-09 | Project → site → phase cascade, searchable authorized references, Jalali date and draft action verified. Scoped actor could select only the granted context. |
| Daily Report draft, review, approved detail and print | DC-03, DC-05, DC-07, DC-09 | Report summary identifies business context without a raw UUID. Five existing inline forms present field errors and retain valid values after retest. Project and site open through authorized links. Approved history is read-only. Chrome opened the actual Print action and saved a two-page A4 PDF. |
| Field list, capture and draft edit | DC-02, DC-03, DC-04, DC-05, DC-07, DC-09 | Existing shared header and return links, Persian labels, correct Jalali time, context, and visible errors. Read-only roles have no create or edit control. On mobile the field table scrolls within its 356 px container. The 780 px table does not widen the page. |
| Field review and accepted detail, proposal form | DC-03, DC-05, DC-07, DC-09 | Business status, history, and named reject reason. Self-review actions suppressed to match the existing service rules. JSON remains an input in the existing structured capture and proposal forms. Proposal review placement and operator comprehension require PO review. |
| Exact evidence picker and detail | DC-03, DC-05, DC-07, DC-09 | Business document title, separate witness and current version labels, permission-aware download and source return verified. The picker uses existing DMS authority. |

Representative list, create, detail, review, evidence picker and exact-version detail were captured at **1440, 1024 and 390 CSS px**. All 38 captured retest states measured within the viewport with RTL and a single main landmark. Captures record visible controls, focused elements and separate field errors. The approved Daily Report shows the duplicate labor row from the deliberate replay probe. [Responsive page observations](evidence/wave-03-865fa3f3/retest/browser/page-observations.json) · [Daily mobile detail](evidence/wave-03-865fa3f3/retest/browser/daily-approved-390.png) · [Field mobile form](evidence/wave-03-865fa3f3/retest/browser/field-create-390.png) · [Exact-version detail](evidence/wave-03-865fa3f3/retest/browser/field-evidence-detail-1024.png) · [A4 print evidence](evidence/wave-03-865fa3f3/retest/browser/approved-report-a4.pdf)

## Defects and disposition

| Defect | Finding | Disposition |
|---|---|---|
| BON-DEF-0011 | Field HTTP gate rejected granted site actors | FIXED / RETESTED_PASS |
| BON-DEF-0012 | Local Field and proposal times stored with wrong offset and lost on redisplay | FIXED / RETESTED_PASS |
| BON-DEF-0013 | Stale draft overwrite and failed exact retry | FIXED / RETESTED_PASS |
| BON-DEF-0014 | Capture-only editor saw precise coordinates | FIXED / RETESTED_PASS |
| BON-DEF-0015 | Site-scoped Daily Report approval rejected before workflow authorization | FIXED / RETESTED_PASS |
| BON-DEF-0016 | Missing Field entry and Daily Report context links | FIXED / RETESTED_PASS |
| BON-DEF-0017 | Legacy Daily Report permits self-approval and offers no governed return | NEEDS_PO_REVIEW / RETESTED_FAIL |
| BON-DEF-0018 | Identical labor submission appended a second row | NEEDS_PO_REVIEW / RETESTED_FAIL |
| BON-DEF-0019 | Existing proposal review has no operator control | NEEDS_PO_REVIEW / BLOCKED |
| BON-DEF-0020 | English field labels, unlocalized timestamps and unlabeled review reason | FIXED / RETESTED_PASS |
| BON-DEF-0021 | Inline validation cleared valid inputs across five forms | FIXED / RETESTED_PASS |

The register carries exact reproductions, applicable authority and evidence for each finding. [Defect register](../DEFECT_REGISTER.md) · [Defect CSV](../DEFECT_REGISTER.csv)

**Historical recurrence.** The Daily Reports checks did not reproduce UIUX-F-050 (raw UUID summary), UIUX-F-055 (uncascaded report choices), UIUX-F-056 (master material still editable as manual name/unit), UIUX-F-110 (identical date-filter accessible names), or the Daily Report portion of UIUX-F-111 (ungranted create choices). The Field timestamp issue is a recurrence of the BON-DEF-0004 failure pattern in a separate form family. The original B02 result and its acceptance status are preserved. [Chrome historical checks](evidence/wave-03-865fa3f3/retest/historical/results.json) · [Historical findings](../../../governance/uiux/UIUX_FINDINGS_REGISTER.yaml)

## PO decisions and next wave

- Decide the MVP Daily Report separation policy and the authorized states and actors for any Return branch. The current compatibility configuration intentionally permits the demonstrated self-approval.
- Define replay identity for append-style daily entries so accidental duplicate submissions can be distinguished from intentional independent rows. The demonstrated duplicate remains a failure.
- Decide MVP placement and exposure for the existing source-only proposal review. Review site-operator comprehension of the existing structured capture and proposal fields.
- Formal visual and product acceptance is pending.

**Recommended next wave is B04** with `UAT-05` Equipment Allocation and Usage, `UAT-06` Safety and Quality Operations and Review, `CV-EQP-01` Equipment Cost Handoff, and `CV-EXP-01` Expenses and Petty Cash. Start from independent compatible synthetic snapshots and scope policy reviewers to their existing authority. B03 stopped at its bounded retest. [Execution plan](../TEST_EXECUTION_PLAN.md)

No production action, existing-database mutation, schema migration, commit, push, or automatic PO acceptance was performed.

## Final remediation addendum · 2026-11-12

The authorized final remediation was executed separately. BON-DEF-0018 and BON-DEF-0019 are FIXED / RETESTED_PASS. BON-DEF-0017 is PARTIALLY_FIXED: MVP self-approval is blocked and independent approval passes, while Return/edit/resubmit remains BLOCKED because the existing contracts cannot safely support it. [Final report](B03_FINAL_REMEDIATION_REPORT.md) · [Latest 22-row retest overlay](B03_FINAL_REMEDIATION_RETEST.csv). The results and PO-decision list above describe the preceding historical checkpoint.
