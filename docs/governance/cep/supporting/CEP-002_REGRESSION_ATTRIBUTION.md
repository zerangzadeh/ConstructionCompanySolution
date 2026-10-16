# CEP-002 Regression Attribution

## Final verification-only classification — 2026-10-14

This record attributes the 15 failures from the fresh isolated, migrated database run (`CEP-002-EV-015`). No product code, fixture, migration, permission catalog, workflow, financial, authorization or CEP scope was changed during this attribution.

## Common finding

The current authorization contract checks both an effective business permission and an explicit effective scope in `apps.organizations.authorization.require_business_permission`. The legacy fixtures create active memberships directly:

- `apps.procurement.tests.ProcurementFixtureMixin` creates `OrganizationMembership` rows directly for its owner/member/viewer identities.
- `apps.financials.tests.FinancialReportTests.setUp` creates its company-owner membership directly.

Neither fixture calls `create_organization_with_owner` or `bootstrap_membership_authorization`, which create the explicit effective role assignment and organization scope grant. The immediate denial in every failure is therefore before the tested workflow/financial behavior and before any CEP-002 route, Home service, shared-shell redirect, template, or middleware request behavior is reached.

| Failing test | Exact first failing point | CEP-002 code/behavior reached? | Attribution |
| --- | --- | --- | --- |
| `WorkbenchTests.test_tenant_isolation_permissions_and_secure_source_link` | `_submitted_request` → `create_purchase_request` → `_require_role` → `require_business_permission(PURCHASE_REQUESTS_CREATE)` | No | **B** |
| `WorkbenchTests.test_multi_position_dedup_counts_states_and_filters` | Same purchase-request setup path | No | **B** |
| `WorkbenchTests.test_role_permission_count_and_tab_use_routing_evidence` | Same purchase-request setup path | No | **B** |
| `WorkbenchTests.test_work_reserved_by_another_member_is_excluded` | Same purchase-request setup path | No | **B** |
| `WorkbenchTests.test_pagination_responsive_context_and_query_bound` | First `_submitted_request` in setup loop; same authorization denial | No | **B** |
| `WorkbenchTests.test_high_open_item_volume_keeps_page_and_query_count_bounded` | Initial `_submitted_request`; same authorization denial | No | **B** |
| `WorkbenchTests.test_claim_release_action_stale_and_htmx_csrf` | Initial `_submitted_request`; same authorization denial | No | **B** |
| `WorkbenchTests.test_unprivileged_viewer_sees_no_mutation_controls` | Initial `_submitted_request`; same authorization denial | No | **B** |
| `FinancialReportTests.test_report_uses_approved_estimates_and_recorded_expenses` | Common `setUp` → `create_project` → `_has_project_permission(PROJECTS_CREATE)` | No | **B** |
| `FinancialReportTests.test_report_rejects_cross_tenant_project` | Common `setUp`; same project-create authorization denial before test body | No | **B** |
| `FinancialReportTests.test_financial_report_view_is_tenant_scoped` | Common `setUp`; same project-create authorization denial before view request | No | **B** |
| `FinancialReportTests.test_organization_reports_include_only_active_projects` | Common `setUp`; same project-create authorization denial | No | **B** |
| `FinancialReportTests.test_dashboard_returns_tenant_scoped_counts_and_totals` | Common `setUp`; same project-create authorization denial | No | **B** |
| `FinancialReportTests.test_dashboard_view_requires_active_organization` | Common `setUp`; same project-create authorization denial before dashboard request | No | **B** |
| `FinancialReportTests.test_dashboard_view_renders_active_organization` | Common `setUp`; same project-create authorization denial before dashboard request | No | **B** |

## Classification result

- Category A — CEP-002 regression: **0**.
- Category B — pre-existing/cross-domain legacy test-fixture debt: **15**.
- Changed CEP-002 behavior reached by a failing path: **No**.

The fixture debt is recorded separately and is not a CEP-002 closure blocker. Repair belongs to the owning workflow/financial and authorization-fixture maintenance scope; it is not authorized or implemented here.
