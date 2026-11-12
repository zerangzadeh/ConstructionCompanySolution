# BONIRA Phase A coverage and gaps

## Assessment baseline

| Item | Observed value |
|---|---|
| Checkout | E:/Construction_Company_Solution |
| Baseline | main at 865fa3f3f7868e81b0aafba05d2683b28fe33b1e, 2026-11-09 20:48:20 +03:30, Some structural fixes |
| Upstream | Local origin/main ref matched HEAD. No fetch was performed. |
| Checkout selection | E: was the newest of three discovered local checkouts. D: was 9705b765 and F: d05c5c45 at discovery. |
| Index and working tree | Read-only git ls-files -m, git diff-index --cached HEAD and git ls-files -o --exclude-standard each returned exit 0 and no paths. The initial sandboxed git status failed. The pre-delivery git status succeeded and confirmed a clean tree. After delivery, the only reported changes were the 11 new files in docs/validation/comprehensive-product. Ignored files are outside this check. |
| Product Surface | config/settings/base.py sets MVP and installs ProductSurfaceMiddleware. Development and production settings import base. FULL_ERP is an explicit internal test/deployment override. No runtime process or deployment profile was sampled. |
| Exposure override | The 23 allowlisted organizations routes can be exposed to effective Platform Admins. Other technical administration stays MVP-hidden. Workforce ESS status is mixed by source_type. |
| Graph | Existing Graphify graph was queried for navigation and guard orientation; graph file was dated 2026-10-20. The checked-out URL registry, code and tests supplied the baseline. |

The requested PRODUCT_STRATEGY_AND_MVP_CHARTER.md filename was absent from the located repository and document holdings. Agents.md points to docs/architecture/PRODUCT_VISION_AND_MVP_RELEASE_STRATEGY.md as frozen D1–D7 authority. Reconciled it with ROADMAP.md, Agents.md, docs/ui-guidelines.md and the actual Product Surface. The strategy's earlier seven-section narrative precedes the current system users destination; use the current navigation and platform reports.

## Coverage accounting

| Scope | Registered declarations | Declarations with literal test references | Inventory rows incl. variants | Current executed |
| --- | --- | --- | --- | --- |
| MVP_ROUTE | 380 | 239 | 464 | 0 |
| BACKEND_ACTIVE_UI_HIDDEN | 265 | 132 | 265 | 0 |
| PLATFORM_ADMIN | 23 | 15 | 33 | 0 |
| MIXED_ROUTE | 1 | 1 | 4 | 0 |

- Denominator **669** includes the explicit root URLs, mounted application declarations and one internal Django Admin mount. Debug media helper and generated Django Admin CRUD routes are outside this route-declaration denominator. Named app declarations were extracted from all mounted URL modules. **668** mapped to an exact source handler; Django Admin remains an internal mount.
- **97** additional rows represent inventoried operation variants, including **14 XLSX** and **5 print** branches on existing URLs. Template evidence records filters, pagination, confirmations, dialog/multipart/HTMX leads and contextual links. Stateful template controls, dynamic selectors, query switches and modal permutations require rendering and can yield additional child steps.
- **41** distinct scenarios, including **11** Platform Admin and the unchanged 15 UAT IDs. **1127** execution rows over 11 batches include primary, reverse-separation and UI overlays. These rows are planning coverage. **0** current runtime results and **0** current PO decisions were recorded.
- **282** declarations have no literal test/verification reference in the source scan. A match can be a fixture, navigation check or assertion and needs inspection. **149** MVP/platform declarations have no literal reference, and **59** MVP/platform declarations have neither a shared-navigation entry nor a literal template URL reference. Dynamic URLs and intentional action-only routes are included in that last count.
- Existing E2E register has **608** IDs, **253** rows in the historical critical/high gaps CSV, and **27** P10 S20 workload scripts in certification/p10_s20/journeys.json. Domain family references in the catalog preserve the existing baseline. Only workload routes with a literal name match are joined into the inventory. The historical critical/high CSV remains the residual queue for older FULL_ERP journeys outside this MVP program.

| Batch | Scenario IDs | Exact execution rows |
| --- | --- | --- |
| B01 | UAT-01, UAT-15, CV-AUTH-01, CV-GUARD-01 | 308 |
| B02 | UAT-02, UAT-04, CV-TIME-01 | 68 |
| B03 | UAT-03, CV-FIELD-01 | 22 |
| B04 | UAT-05, UAT-06, CV-EXP-01, CV-EQP-01 | 66 |
| B05 | UAT-07, UAT-08, UAT-09, CV-BIL-01 | 73 |
| B06 | UAT-11, UAT-12, UAT-13, UAT-14, CV-INV-01 | 88 |
| B07 | CV-TEN-01, CV-WF-01, CV-PAR-01 | 48 |
| B08 | UAT-10, CV-REP-01 | 21 |
| B09 | CV-DOC-01, CV-DOC-02 | 65 |
| B10 | PA-01, PA-02, PA-03, PA-04, PA-05, PA-06, PA-07, PA-08, PA-09, PA-10, PA-11 | 66 |
| B11 | CV-UI-01 | 302 |

## Historical evidence reconciliation

| Workbook | Existing E2E IDs | Historical coverage status counts |
| --- | --- | --- |
| BONIRA_JOURNEY_RISK_COVERAGE_ASSESSMENT.xlsx | 608 | Assessment fields blank |
| BONIRA_JOURNEY_RISK_COVERAGE_ASSESSMENT_RESULT.xlsx | 608 | RUNTIME_PROVED 159, PARTIAL_EVIDENCE 163, UTV 133, AUTOMATED_PROVED 108, DOCUMENTED_IMPLEMENTED 36, NOT_APPLICABLE 9 |

All workbook IDs reconcile to the CSV set. Static status in the two workbook inventories is 593 CORRECT, 8 NOT APPLICABLE, 5 PARTIAL and 2 DEFERRED-BY-DESIGN. These values describe those assessments. Do not transfer coverage labels to the current run.

| Source | Historical evidence and current action |
|---|---|
| docs/governance/mvp/MVP-01_COMPLETION_REPORT.md | Product Surface and hidden-route controls. Recheck current middleware, contextual links and mixed ESS branches in B01. |
| MVP-02 reports and output/workforce-timekeeping-journey/REPORT.md | Workforce/timekeeping implementation and prior Chrome evidence. Verify current identity, assignment and time behavior in B02. Visual acceptance pending per UAT record. |
| MVP-03 reports including CONTRACT_HUB_REMEDIATION | Billing, estimate and contract context/UX, and explicit Contracts List PO acceptance dated 2026-11-01. Preserve its limited scope. Reverify saved terms, revisions and history in B05. |
| MVP-04, MVP-04A and MVP-04B reports | Staged PR, RFQ, order, receipt and inventory evidence. Early tranche “not started” labels preceded later tranches. Reuse synthetic approved PR and sealed lineage where compatible in B06. |
| MVP-05/06/07 completion reports | P0/P1 Excel, browser-native print and focused usability. Reuse output contracts and historical failures as test leads. Rerun actual downloads and print, authoritatively reconcile fields and preserve source scopes in B08. |
| MVP-08 completion, guide and results | Bounded technical continuation reported PASS, 15/15 Human UAT entries NOT_EXECUTED. Accepted five-artifact preservation exception applies only to evidence custody. Reuse baseline as described in the journey catalog and record actual Phase B outcomes. |
| docs/assessments/platform-admin and output/platform-admin-*/REPORT.md | Assessment predates operators/dashboard/user management changes. Completion, dashboard redesign, roles redesign, user directory/detail and user management reports supply bounded historical proofs. Earlier completion reported browser unavailable, later reports include scoped desktop/mobile browser runs. Current temporary-password handler and scope guards are present. Reverify each PA flow. |
| docs/validation/related-documents-phase1.md / phase2.md | Five source details and contextual operations. Focused automated evidence historical. Required Chrome/PO review unresolved in the source phase reports. |
| docs/validation/related-documents-phase3.md | Eight specialized variants. Follow-up reports Chrome for a bounded matrix and preserves narrower automated results; approved, quarantined, denied and exact-version cases require baseline checks. Validate missing combinations independently. |
| docs/governance/uiux/UIUX_RUNTIME_VALIDATION_COMPLETION_REPORT.md, UIUX_FULL_AUDIT_CHECKPOINT_01–09 and current findings register | Audit and remediation trail. Use specific finding and cited evidence. Prior closure alone supplies no current result. Reverify in B11 and corresponding business/authority batch. |

Historical register source is docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml and its referenced closeouts. The table has 133 unique top-level finding IDs and selected later appendices. Each current finding state remains **unverified**. A prior browser report is historical evidence only; a prior automated report is historical automated-only proof for its stated selection. Future disposition requires current evidence.

| Current re-verification class | Phase A count |
|---|---|
| Independently reverified against current UI | 0 |
| Reverified through current automation only | 0 |
| Historical closed finding rows in the top-level scan | 23 |
| Other top-level findings without current verification | 110 |
| Reopened by Phase A reproduction | 0 |

## Explicit residual scope and next checks

1. **Current runtime entirely untested.** Every inventory and execution row is NOT_RUN. Confirm runtime discoverability and all denied/error/empty branches, actual device widths, keyboard and data/state oracles in Phase B.
2. **Conditional routes.** Some registered MVP capability routes only render via specific grants, configured policy or domain states. Billing commercial/statutory paths, cost workbenches, delegated roles, employee source contexts, portal links and DMS variants need valid fixture-by-branch. A render condition or absent menu entry alone cannot establish whether a capability is unsupported.
3. **Route granularity.** A static template pass cannot enumerate all dynamic links, URL kwargs, same-page modes, formsets and modal states. All currently visible route families have planned primary coverage. B11 expands each rendered page's actual controls. The following eligible declarations lack a literal test/verification reference. The full machine list is obtained by filtering the inventory on Test_Reference_Count = 0 and the relevant Surface.
4. **MVP-hidden regression.** Finance (accounting, treasury, subledgers, financials, fixed assets), Payroll, full HR, internal reporting/reconciliation, Commercial, Compliance, Partner Qualification, Support/Knowledge and Django technical Admin retain existing backend functions. MVP scope covers denial and protected handoff consistency. Full UI/data validation under FULL_ERP remains separate.
5. **Unsupported or deferred boundaries.** No ordinary Platform workspace account delete, arbitrary settings/profile switch, generalized tenant export/offboarding workflow or impersonation is established. Uptime, real SMTP delivery, external statutory delivery, production readiness and certification are outside this run. Validate supported controls and document unconfigured cases.
6. **Historical test debt.** MVP-07 reported 17 affected baseline failures and Platform Admin completion reported older namespace/permission reconciliation failures. Historical attribution must be checked against the exact Phase B selection before classification. A baseline failure or missing fixture requires its own result and evidence.

## Eligible declarations with no literal test reference

accounts:password_reset_confirm, accounts:connection_requests, accounts:connection_request_respond, organizations:platform_user_detail, organizations:platform_user_edit, organizations:platform_user_status, organizations:platform_user_reset, organizations:platform_user_temporary_password, organizations:platform_company_onboarding, organizations:platform_company_edit, organizations:platform_company_status, organizations:account_create, organizations:member_authorization, parties:governance, parties:governance_action, parties:archive, parties:role_create, parties:contact_create, materials:material_archive, materials:category_archive, materials:unit_archive, projects:wbs_create, projects:wbs_archive, projects:activity_create, projects:activity_transition, projects:activity_archive, projects:phase_transition, projects:archive, contracts:contractual_list, contracts:contractual_create, contracts:contractual_submit, contracts:contractual_decide, contracts:contractual_revision, contracts:contractual_withdraw, billing:taxpayer_invoice_create, billing:taxpayer_invoice_detail, billing:taxpayer_invoice_submit, billing:taxpayer_invoice_approve, billing:taxpayer_invoice_return, billing:taxpayer_invoice_export, billing:contractor_compliance_create, billing:contractor_compliance_submit, billing:contractor_compliance_approve, billing:contractor_compliance_return, billing:contractor_compliance_export, billing:statutory_submission_resolve, billing:commercial_expiry_refresh, billing:guarantee_submit, billing:guarantee_approve, billing:guarantee_return, billing:compliance_evidence_submit, billing:compliance_evidence_approve, billing:compliance_evidence_return, billing:retention_release_submit, billing:retention_release_approve, billing:retention_release_return, billing:progress_submit, billing:progress_reject, billing:recovery_guidance, billing:payable_certificate_approve, billing:payable_certificate_return, billing:payable_certificate_back_charge, billing:payable_certificate_correct, billing:payable_measurement_reject, expenses:category_archive, expenses:submit, expenses:approve, expenses:return, documents:evidence-choices, documents:evidence-register, documents:evidence-detail, documents:contextual-upload, documents:contextual-link, documents:contextual-choices, documents:link-add, daily_reports:field_observation_create, daily_reports:field_observation_save, daily_reports:field_observation_evidence_add, daily_reports:field_observation_submit, daily_reports:field_observation_review_start, daily_reports:field_observation_review_decide, daily_reports:field_proposal_create, daily_reports:field_proposal_submit, daily_reports:field_proposal_review, daily_reports:labor_add, daily_reports:equipment_add, daily_reports:material_add, daily_reports:activity_add, daily_reports:delay_add, daily_reports:submit, daily_reports:approve, workforce:employee_archive, workforce:work_team_archive, timekeeping:attendance_finalize, timekeeping:attendance_correction_review, timekeeping:leave_mission_submit, timekeeping:leave_mission_review, timekeeping:overtime_submit, timekeeping:overtime_review, timekeeping:timesheet_submit, timekeeping:timesheet_review, timekeeping:timesheet_preview, procurement:rfq_close, procurement:rfq_cancel, procurement:portal_receipt, procurement:portal_grant_revoke, procurement:request_item_add, procurement:request_submit, procurement:request_approve, procurement:request_reject, procurement:request_cancel, procurement:order_choices, procurement:order_cancel, inventory:reservation_create, inventory:reservation_release, inventory:count_create, inventory:count_approve, inventory:count_post, inventory:transfer_create, inventory:transfer_detail, inventory:transfer_dispatch, inventory:transfer_in_transit, inventory:transfer_accept, inventory:warehouse_archive, inventory:transaction_request_posting, inventory:transaction_request_reversal, equipment:status_change, equipment:archive, equipment:assignment_status_change, equipment:cost_workbench, equipment:cost_policy_create, equipment:cost_rate_create, equipment:cost_policy_transition, equipment:cost_allocation_create, equipment:cost_allocation_finalize, equipment:cost_allocation_reverse, equipment:cost_handoff_create, equipment:cost_handoff_review, equipment:cost_handoff_reconcile, safety:review, safety:corrective_action, safety:resolve, safety:close, quality:review, quality:assign, quality:corrective_action, quality:submit_for_verification, quality:verify, quality:close

## Historical findings and retest routing

| Finding | Module | Historical surface | Prior register state | Phase A disposition | Retest journey |
| --- | --- | --- | --- | --- | --- |
| UIUX-F-001 | Shared Shell | GLOBAL_AUTHENTICATED_SHELL | PILOT_CONFIRMED_STATIC | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-002 | Timekeeping | /timekeeping/calendars/new/ | PILOT_CONFIRMED_STATIC | Current baseline unverified | [UAT-04](USER_JOURNEY_CATALOG.md#uat-04) |
| UIUX-F-003 | Timekeeping | /timekeeping/calendars/new/ | PILOT_CONFIRMED_STATIC | Current baseline unverified | [UAT-04](USER_JOURNEY_CATALOG.md#uat-04) |
| UIUX-F-004 | Timekeeping | /timekeeping/calendars/new/ | PILOT_CONFIRMED_STATIC | Current baseline unverified | [UAT-04](USER_JOURNEY_CATALOG.md#uat-04) |
| UIUX-F-005 | Payroll | /payroll/ | PILOT_CONFIRMED_STATIC | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-006 | Payroll | /payroll/ | PILOT_CONFIRMED_STATIC | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-007 | Payroll | /payroll/ | PILOT_CONFIRMED_STATIC | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-008 | Procurement | /procurement/rfqs/&lt;uuid:rfq_id&gt;/buyer/ | PILOT_CONFIRMED_STATIC | Current baseline unverified | [UAT-12](USER_JOURNEY_CATALOG.md#uat-12) |
| UIUX-F-009 | Procurement | /procurement/rfqs/&lt;uuid:rfq_id&gt;/buyer/ | PILOT_CONFIRMED_STATIC | Current baseline unverified | [UAT-12](USER_JOURNEY_CATALOG.md#uat-12) |
| UIUX-F-010 | Parties | /parties/governance/ | PILOT_CONFIRMED_STATIC | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-011 | Documents | /documents/ | PILOT_CONFIRMED_STATIC | Current baseline unverified | [CV-DOC-01](USER_JOURNEY_CATALOG.md#cv-doc-01) |
| UIUX-F-012 | Subledgers | /subledgers/ | PILOT_CONFIRMED_STATIC | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-013 | Subledgers | /subledgers/ | PILOT_CONFIRMED_STATIC | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-014 | Subledgers | /subledgers/ | PILOT_CONFIRMED_STATIC | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-015 | Core | /search/ | PILOT_CONFIRMED_STATIC | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-016 | Shared Navigation | GLOBAL_AUTHENTICATED_SHELL | PILOT_CONFIRMED_STATIC | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-017 | Shared Navigation | GLOBAL_AUTHENTICATED_SHELL | PILOT_CONFIRMED_STATIC | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-018 | Shared List Pattern | MULTI_SURFACE | PILOT_CONFIRMED_STATIC | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-019 | Projects | /projects/&lt;uuid:project_id&gt;/controls/ | PILOT_CONFIRMED_STATIC | Current baseline unverified | [UAT-02](USER_JOURNEY_CATALOG.md#uat-02) |
| UIUX-F-020 | Organizations | /organizations/members/&lt;uuid:membership_id&gt;/authorization/ | PILOT_CONFIRMED_STATIC | Current baseline unverified | [CV-TEN-01](USER_JOURNEY_CATALOG.md#cv-ten-01) |
| UIUX-F-021 | Workforce / ESS | /workforce/ess/ | PILOT_CONFIRMED_STATIC | Current baseline unverified | [UAT-04](USER_JOURNEY_CATALOG.md#uat-04) |
| UIUX-F-022 | Workforce / ESS | /workforce/ess/ | PILOT_CONFIRMED_STATIC | Current baseline unverified | [UAT-04](USER_JOURNEY_CATALOG.md#uat-04) |
| UIUX-F-023 | Inventory | /inventory/custody/ | PILOT_CONFIRMED_STATIC | Current baseline unverified | [UAT-14](USER_JOURNEY_CATALOG.md#uat-14) |
| UIUX-F-024 | Inventory | /inventory/valuation/ | PILOT_CONFIRMED_STATIC | Current baseline unverified | [UAT-14](USER_JOURNEY_CATALOG.md#uat-14) |
| UIUX-F-025 | Equipment | /equipment/operations/ | PILOT_CONFIRMED_STATIC | Current baseline unverified | [UAT-05](USER_JOURNEY_CATALOG.md#uat-05) |
| UIUX-F-026 | Equipment | /equipment/operations/ | PILOT_CONFIRMED_STATIC | Current baseline unverified | [UAT-05](USER_JOURNEY_CATALOG.md#uat-05) |
| UIUX-F-027 | Fixed Assets | /fixed-assets/ | PILOT_CONFIRMED_STATIC | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-028 | Fixed Assets | /fixed-assets/ | PILOT_CONFIRMED_STATIC | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-029 | Shared Localization | GLOBAL_AUTHENTICATED_SHELL | PILOT_CONFIRMED_STATIC | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-030 | Accounting | /accounting/journals/&lt;uuid:journal_id&gt;/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-031 | Treasury | /treasury/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-032 | Treasury | /treasury/statements/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-033 | Reporting | /reporting/ | STATIC_CONFIRMED | Current baseline unverified | [CV-REP-01](USER_JOURNEY_CATALOG.md#cv-rep-01) |
| UIUX-F-034 | Reporting | /reporting/ | STATIC_CONFIRMED | Current baseline unverified | [CV-REP-01](USER_JOURNEY_CATALOG.md#cv-rep-01) |
| UIUX-F-035 | Compliance | /compliance/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-036 | Knowledge | /knowledge/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-037 | Support | /support/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-038 | Contracts | /contracts/&lt;uuid:contract_id&gt;/commercial-review/ | RUNTIME_VERIFIED_RESOLVED | Historical closure evidence only | [UAT-07](USER_JOURNEY_CATALOG.md#uat-07) |
| UIUX-F-039 | Billing | /billing/claims/&lt;uuid:claim_id&gt;/ | STATIC_CONFIRMED | Current baseline unverified | [UAT-07](USER_JOURNEY_CATALOG.md#uat-07) |
| UIUX-F-040 | Timekeeping | /timekeeping/ | STATIC_CONFIRMED | Current baseline unverified | [UAT-04](USER_JOURNEY_CATALOG.md#uat-04) |
| UIUX-F-041 | Timekeeping | /timekeeping/ | STATIC_CONFIRMED | Current baseline unverified | [UAT-04](USER_JOURNEY_CATALOG.md#uat-04) |
| UIUX-F-042 | Payroll / ESS | /payroll/ess/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-043 | Reporting | /reporting/reconciliations/ | STATIC_CONFIRMED | Current baseline unverified | [CV-REP-01](USER_JOURNEY_CATALOG.md#cv-rep-01) |
| UIUX-F-044 | Reporting | /reporting/reconciliations/ | STATIC_CONFIRMED | Current baseline unverified | [CV-REP-01](USER_JOURNEY_CATALOG.md#cv-rep-01) |
| UIUX-F-045 | Reporting | /reporting/project-closeout/&lt;uuid:case_id&gt;/ | STATIC_CONFIRMED | Current baseline unverified | [CV-REP-01](USER_JOURNEY_CATALOG.md#cv-rep-01) |
| UIUX-F-046 | Reporting | /reporting/project-closeout/&lt;uuid:case_id&gt;/ | STATIC_CONFIRMED | Current baseline unverified | [CV-REP-01](USER_JOURNEY_CATALOG.md#cv-rep-01) |
| UIUX-F-047 | Reporting | /reporting/project-closeout/&lt;uuid:case_id&gt;/ | STATIC_CONFIRMED | Current baseline unverified | [CV-REP-01](USER_JOURNEY_CATALOG.md#cv-rep-01) |
| UIUX-F-048 | Workflow Administration | /workflows/administration/versions/&lt;uuid:version_id&gt;/ | STATIC_CONFIRMED | Current baseline unverified | [CV-WF-01](USER_JOURNEY_CATALOG.md#cv-wf-01) |
| UIUX-F-049 | Workforce | /workforce/employees/&lt;uuid:employee_id&gt;/ | STATIC_CONFIRMED | Current baseline unverified | [UAT-04](USER_JOURNEY_CATALOG.md#uat-04) |
| UIUX-F-050 | Daily Reports | /daily-reports/&lt;uuid:report_id&gt;/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-051 | Materials | /materials/governance/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-052 | Accounting | /accounting/reconciliations/&lt;uuid:run_id&gt;/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-053 | Treasury | /treasury/movements/&lt;uuid:movement_id&gt;/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-054 | Procurement | /procurement/orders/create/ | STATIC_CONFIRMED | Current baseline unverified | [UAT-12](USER_JOURNEY_CATALOG.md#uat-12) |
| UIUX-F-055 | Daily Reports | /daily-reports/create/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-056 | Daily Reports | /daily-reports/&lt;uuid:report_id&gt;/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-057 | Equipment | /equipment/assignments/create/ | STATIC_CONFIRMED | Current baseline unverified | [UAT-05](USER_JOURNEY_CATALOG.md#uat-05) |
| UIUX-F-058 | Payroll | /payroll/configuration/employment/new/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-059 | Payroll | MULTI_PAYROLL_FORMS | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-060 | Procurement Supplier Portal | /procurement/portal/grants/&lt;uuid:grant_id&gt;/ | STATIC_CONFIRMED | Current baseline unverified | [UAT-12](USER_JOURNEY_CATALOG.md#uat-12) |
| UIUX-F-061 | Equipment | MULTI_EQUIPMENT_OPERATION_FORMS | STATIC_CONFIRMED | Current baseline unverified | [UAT-05](USER_JOURNEY_CATALOG.md#uat-05) |
| UIUX-F-062 | Compliance | /compliance/&lt;str:kind&gt;/&lt;uuid:record_id&gt;/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-063 | Knowledge | /knowledge/candidates/&lt;uuid:candidate_id&gt;/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-064 | Support | /support/cases/&lt;uuid:case_id&gt;/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-065 | Core / Home | / | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-066 | Core / Home | / | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-067 | Payroll | /payroll/runs/&lt;uuid:run_id&gt;/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-068 | Payroll | /payroll/statutory/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-069 | Payroll | /payroll/financial-handoffs/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-070 | Billing / Statutory | MULTI_BILLING_STATUTORY_FORMS | STATIC_CONFIRMED | Current baseline unverified | [UAT-07](USER_JOURNEY_CATALOG.md#uat-07) |
| UIUX-F-071 | Workforce | /workforce/foundation/performance/create/ | STATIC_CONFIRMED | Current baseline unverified | [UAT-04](USER_JOURNEY_CATALOG.md#uat-04) |
| UIUX-F-072 | Billing | /billing/commercial-controls/ | STATIC_CONFIRMED | Current baseline unverified | [UAT-07](USER_JOURNEY_CATALOG.md#uat-07) |
| UIUX-F-073 | Shared Forms | GLOBAL_FORM_COMPONENT | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-074 | Accounting | /accounting/journals/create/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-075 | Accounting | /accounting/journals/create/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-076 | Accounting | /accounting/openings/create/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-077 | Support | /support/cases/&lt;uuid:case_id&gt;/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-078 | Equipment | /equipment/operations/work-orders/create/ | STATIC_CONFIRMED | Current baseline unverified | [UAT-05](USER_JOURNEY_CATALOG.md#uat-05) |
| UIUX-F-079 | Commercial | /commercial/&lt;uuid:tender_id&gt;/evidence/ | STATIC_CONFIRMED | Current baseline unverified | [UAT-07](USER_JOURNEY_CATALOG.md#uat-07) |
| UIUX-F-080 | Knowledge | MULTI_KNOWLEDGE_FORMS | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-081 | Billing | MULTI_BILLING_COMPLIANCE_FORMS | STATIC_CONFIRMED | Current baseline unverified | [UAT-07](USER_JOURNEY_CATALOG.md#uat-07) |
| UIUX-F-082 | Shared Forms | MULTI_GENERIC_FORMS | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-083 | Billing | /billing/guarantees/new/ | STATIC_CONFIRMED | Current baseline unverified | [UAT-07](USER_JOURNEY_CATALOG.md#uat-07) |
| UIUX-F-084 | Compliance | /compliance/create/&lt;str:kind&gt;/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-085 | Shared Tables | GLOBAL_TABLE_PAGINATION | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-086 | Equipment | /equipment/operations/qualifications/create/ | STATIC_CONFIRMED | Current baseline unverified | [UAT-05](USER_JOURNEY_CATALOG.md#uat-05) |
| UIUX-F-087 | Equipment | /equipment/operations/work-orders/&lt;uuid:work_order_id&gt;/spares/create/ | STATIC_CONFIRMED | Current baseline unverified | [UAT-05](USER_JOURNEY_CATALOG.md#uat-05) |
| UIUX-F-088 | Treasury | /treasury/movements/new/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-089 | Billing | /billing/guarantees/new/ | STATIC_CONFIRMED | Current baseline unverified | [UAT-07](USER_JOURNEY_CATALOG.md#uat-07) |
| UIUX-F-090 | Shared Status Presentation | GLOBAL_STATUS_BADGE | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-091 | Shared Date Presentation | MULTI_SURFACE | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-092 | Accounting | /accounting/statements/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-093 | Accounting | /accounting/statements/&lt;uuid:run_id&gt;/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-094 | Billing | /billing/payable-certificates/&lt;uuid:certificate_id&gt;/ | STATIC_CONFIRMED | Current baseline unverified | [UAT-07](USER_JOURNEY_CATALOG.md#uat-07) |
| UIUX-F-095 | Compliance | COMPLIANCE_TEMPLATE_PUBLISH | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-096 | Equipment | /equipment/cost/ | STATIC_CONFIRMED | Current baseline unverified | [UAT-05](USER_JOURNEY_CATALOG.md#uat-05) |
| UIUX-F-097 | Equipment | /equipment/maintenance/ | STATIC_CONFIRMED | Current baseline unverified | [UAT-05](USER_JOURNEY_CATALOG.md#uat-05) |
| UIUX-F-098 | Workforce | /workforce/foundation/ | STATIC_CONFIRMED | Current baseline unverified | [UAT-04](USER_JOURNEY_CATALOG.md#uat-04) |
| UIUX-F-099 | Knowledge | /knowledge/publications/&lt;uuid:version_id&gt;/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-100 | Knowledge | /knowledge/platform/promotions/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-101 | Billing | MULTI_BILLING_PAYABLE_FORMS | STATIC_CONFIRMED | Current baseline unverified | [UAT-07](USER_JOURNEY_CATALOG.md#uat-07) |
| UIUX-F-102 | Treasury | /treasury/operations/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-103 | Knowledge | /knowledge/publications/&lt;uuid:version_id&gt;/history/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-104 | Audit | /audit/ | STATIC_CONFIRMED | Current baseline unverified | [CV-REP-01](USER_JOURNEY_CATALOG.md#cv-rep-01) |
| UIUX-F-105 | Estimates | /estimates/create/ | STATIC_CONFIRMED | Current baseline unverified | [UAT-07](USER_JOURNEY_CATALOG.md#uat-07) |
| UIUX-F-106 | Partner Qualification | /partners/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-107 | Accounts | /accounts/login/ | STATIC_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-108 | Workforce | /workforce/teams/ | STATIC_CONFIRMED | Current baseline unverified | [UAT-04](USER_JOURNEY_CATALOG.md#uat-04) |
| UIUX-F-109 | Organizations | /organizations/members/ | RUNTIME_CONFIRMED | Current baseline unverified | [CV-TEN-01](USER_JOURNEY_CATALOG.md#cv-ten-01) |
| UIUX-F-110 | Daily Reports / Shared Table Filters | /daily-reports/ | RUNTIME_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-111 | Daily Reports / Equipment / Procurement | Scoped choices | RUNTIME_CONFIRMED / RUNTIME_VERIFIED_RESOLVED | Historical closure evidence only | [UAT-12](USER_JOURNEY_CATALOG.md#uat-12) |
| UIUX-F-112 | Accounting | /accounting/journals/&lt;uuid:journal_id&gt;/ | RUNTIME_CONFIRMED | Current baseline unverified | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| UIUX-F-113 | Procurement | /procurement/requests/create/ | RESOLVED / RUNTIME_VERIFIED_RESOLVED | Historical closure evidence only | [UAT-12](USER_JOURNEY_CATALOG.md#uat-12) |
| UIUX-F-114 | Procurement | /procurement/receipts/create/ | RESOLVED / RUNTIME_VERIFIED_RESOLVED | Historical closure evidence only | [UAT-12](USER_JOURNEY_CATALOG.md#uat-12) |
| UIUX-F-115 | Equipment | /equipment/maintenance/create/ | RESOLVED / RUNTIME_VERIFIED_RESOLVED | Historical closure evidence only | [UAT-05](USER_JOURNEY_CATALOG.md#uat-05) |
| UIUX-F-116 | Contracts | /contracts/create/ | RESOLVED / RUNTIME_VERIFIED_RESOLVED | Historical closure evidence only | [UAT-07](USER_JOURNEY_CATALOG.md#uat-07) |
| UIUX-F-117 | Inventory | /inventory/create/ | RESOLVED / RUNTIME_VERIFIED_RESOLVED | Historical closure evidence only | [UAT-14](USER_JOURNEY_CATALOG.md#uat-14) |
| UIUX-F-118 | Inventory | /inventory/transactions/create/ | RESOLVED / RUNTIME_VERIFIED_RESOLVED | Historical closure evidence only | [UAT-14](USER_JOURNEY_CATALOG.md#uat-14) |
| UIUX-F-119 | Expenses | Allocation Project/WBS/Activity | RESOLVED / RUNTIME_VERIFIED_RESOLVED | Historical closure evidence only | [CV-EXP-01](USER_JOURNEY_CATALOG.md#cv-exp-01) |
| UIUX-F-120 | Expenses | /expenses/recurrences/ | RESOLVED / RUNTIME_VERIFIED_RESOLVED | Historical closure evidence only | [CV-EXP-01](USER_JOURNEY_CATALOG.md#cv-exp-01) |
| UIUX-F-121 | Billing | Shared commercial create Contract / DocumentVersion choices (three create forms) | RESOLVED / STATIC_CONFIRMED / RUNTIME_VERIFIED_RESOLVED | Historical closure evidence only | [UAT-07](USER_JOURNEY_CATALOG.md#uat-07) |
| UIUX-F-122 | Billing | /billing/retention-releases/new/ | RESOLVED / STATIC_CONFIRMED / RUNTIME_VERIFIED_RESOLVED | Historical closure evidence only | [UAT-07](USER_JOURNEY_CATALOG.md#uat-07) |
| UIUX-F-123 | Billing | /billing/payable-measurements/new/ | RESOLVED / RUNTIME_VERIFIED_RESOLVED | Historical closure evidence only | [UAT-07](USER_JOURNEY_CATALOG.md#uat-07) |
| UIUX-F-124 | Billing | /billing/payable-certificates/new/ | RESOLVED / RUNTIME_VERIFIED_RESOLVED | Historical closure evidence only | [UAT-07](USER_JOURNEY_CATALOG.md#uat-07) |
| UIUX-F-125 | Workforce | /workforce/foundation/training-requirements/create/ | RESOLVED / RUNTIME_VERIFIED_RESOLVED | Historical closure evidence only | [UAT-04](USER_JOURNEY_CATALOG.md#uat-04) |
| UIUX-F-126 | Quality | /quality/create/ | RESOLVED / RUNTIME_VERIFIED_RESOLVED | Historical closure evidence only | [UAT-06](USER_JOURNEY_CATALOG.md#uat-06) |
| UIUX-F-127 | Safety | /safety/create/ | RESOLVED / RUNTIME_VERIFIED_RESOLVED | Historical closure evidence only | [UAT-06](USER_JOURNEY_CATALOG.md#uat-06) |
| UIUX-F-128 | Workforce | /workforce/foundation/training-records/create/ | RESOLVED / RUNTIME_VERIFIED_RESOLVED | Historical closure evidence only | [UAT-04](USER_JOURNEY_CATALOG.md#uat-04) |
| UIUX-F-129 | Procurement supplier portal | /procurement/portal/accept/ | RESOLVED / RUNTIME_VERIFIED_RESOLVED | Historical closure evidence only | [UAT-12](USER_JOURNEY_CATALOG.md#uat-12) |
| UIUX-F-130 | Inventory | /inventory/valuation/ | RESOLVED / RUNTIME_VERIFIED_RESOLVED | Historical closure evidence only | [UAT-14](USER_JOURNEY_CATALOG.md#uat-14) |
| UIUX-F-131 | Workforce | /workforce/employees/&lt;uuid:employee_id&gt;/ | RUNTIME_VERIFIED_RESOLVED | Historical closure evidence only | [UAT-04](USER_JOURNEY_CATALOG.md#uat-04) |
| UIUX-F-132 | Procurement | /procurement/rfq-invitations/&lt;uuid:invitation_id&gt;/portal/ | RUNTIME_VERIFIED_RESOLVED | Historical closure evidence only | [UAT-12](USER_JOURNEY_CATALOG.md#uat-12) |
| UIUX-F-133 | Workforce | /workforce/employment/ | RUNTIME_VERIFIED_RESOLVED / EXECUTED | Historical closure evidence only | [UAT-04](USER_JOURNEY_CATALOG.md#uat-04) |
| UIUX-F-134 | Later addendum | Tenant role filter label | Later Wave E appendix reports scoped closure | Historical evidence only | [CV-TEN-01](USER_JOURNEY_CATALOG.md#cv-ten-01) |
| UIUX-F-135 | Later addendum | Picker keyboard Escape and focus | Final targeted appendix reports RV-EV-065 | Historical evidence only | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| RV-007 | Later addendum | Wave C scoped closure | rv007_final_closure/COMPLETION_REPORT.md | Historical evidence only | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| RV-022 | Later addendum | Business labels | rv022_business_labels closeout; F-048 preserved separately | Historical evidence only | [CV-UI-01](USER_JOURNEY_CATALOG.md#cv-ui-01) |
| SP-031 / UIUX-F-128 | Later addendum | Training requirement scope | Historical scoped remediation; Compliance namespace is MVP-hidden | Historical evidence only | [CV-GUARD-01](USER_JOURNEY_CATALOG.md#cv-guard-01) |
