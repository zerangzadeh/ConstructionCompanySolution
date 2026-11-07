# MVP Detail Route Classification

46 named detail routes in the current MVP resolver. Dynamic route kinds retain their existing dispatcher. Classification is source-based; browser verification is explicitly limited to adopted routes.

Standard Record Detail: 9. Specialized: 37 (7 received shared visual conventions). Already compliant with the newly introduced exact Record Detail component at entry: 0. Existing approved specialized layouts are preserved, not asserted to have passed this rollout visual review.

| Route | Classification / result | Reason |
|---|---|---|
| `organizations:member_detail` | Specialized Operational Detail; Shared conventions applied; specialized body retained | Privileged membership authority remains read-only; shared header/info shell only. |
| `parties:governance_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Governed supplier/customer legal, tax and identity workflows; separate from operational master. |
| `parties:detail` | Standard Record Detail; Migrated | Operational party identity, specifications, roles and contacts; governance remains separate. |
| `materials:material_detail` | Specialized Operational Detail; Shared conventions applied; specialized body retained | Combined detail/edit endpoint: Compact editor preserved; existing-record header/summary only. |
| `materials:category_detail` | Specialized Operational Detail; Shared conventions applied; specialized body retained | Combined detail/edit endpoint: Compact editor preserved; existing-record header/summary only. |
| `projects:site_detail` | Standard Record Detail; Migrated | Existing authorized read-only site rows; shared detail presentation. |
| `projects:phase_detail` | Standard Record Detail; Migrated | Phase identity and existing status transitions. |
| `projects:detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Approved Projects Exception in UI guidelines section 30 requires separate instruction for final design. |
| `contracts:contractual_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Specialized contractual entitlement/change-order instruction workspace. |
| `contracts:detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Specialized contract items, workflow and financial/source relationships. |
| `billing:taxpayer_invoice_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Specialized billing/compliance/claim/measurement lifecycle, calculations and protected financial lineage. |
| `billing:contractor_compliance_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Specialized billing/compliance/claim/measurement lifecycle, calculations and protected financial lineage. |
| `billing:guarantee_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Specialized billing/compliance/claim/measurement lifecycle, calculations and protected financial lineage. |
| `billing:compliance_evidence_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Specialized billing/compliance/claim/measurement lifecycle, calculations and protected financial lineage. |
| `billing:retention_release_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Specialized billing/compliance/claim/measurement lifecycle, calculations and protected financial lineage. |
| `billing:baseline_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Specialized billing/compliance/claim/measurement lifecycle, calculations and protected financial lineage. |
| `billing:progress_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Specialized billing/compliance/claim/measurement lifecycle, calculations and protected financial lineage. |
| `billing:claim_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Specialized billing/compliance/claim/measurement lifecycle, calculations and protected financial lineage. |
| `billing:payable_certificate_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Specialized billing/compliance/claim/measurement lifecycle, calculations and protected financial lineage. |
| `billing:payable_measurement_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Specialized billing/compliance/claim/measurement lifecycle, calculations and protected financial lineage. |
| `estimates:detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Estimate item/revision/quantity-calculation workspace, not a simple record. |
| `expenses:category_detail` | Specialized Operational Detail; Shared conventions applied; specialized body retained | Combined detail/edit endpoint: Compact editor preserved; existing-record header/summary only. |
| `expenses:detail` | Standard Record Detail; Migrated | Expense pilot; actual lifecycle, allocations, assessments, documents and timestamp history. |
| `documents:evidence-detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Specialized protected evidence/version route; not ordinary DMS master detail. |
| `documents:employee-detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Protected workforce document route with separate identity/access boundary. |
| `documents:detail` | Specialized Operational Detail; Shared conventions applied; specialized body retained | Version, download quarantine, source linkage, retention and archive workflows preserved; shared shell only. |
| `daily_reports:field_observation_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Specialized field observation workspace and lifecycle. |
| `daily_reports:detail` | Specialized Operational Detail; Shared conventions applied; specialized body retained | Operational entry grids, HSE references, DMS and submit/approve forms preserved; shared shell only. |
| `workforce:field_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Field-worker identity/assignment/history workspace with dedicated field journey. |
| `workforce:employee_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | MVP compatibility route delegates to field-worker identity surface; no second design. |
| `timekeeping:record_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Dynamic operational attendance/overtime/timesheet record kinds and approval actions. |
| `timekeeping:timesheet_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Timesheet lines, approval and work-context workspace. |
| `procurement:rfq_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Specialized procurement lines, handoffs, source records and lifecycle. |
| `procurement:request_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Specialized procurement lines, handoffs, source records and lifecycle. |
| `procurement:order_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Specialized procurement lines, handoffs, source records and lifecycle. |
| `procurement:receipt_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Specialized procurement lines, handoffs, source records and lifecycle. |
| `inventory:count_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Specialized inventory quantity/value transactions, lines, counts or transfers; authoritative stock workflow. |
| `inventory:transfer_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Specialized inventory quantity/value transactions, lines, counts or transfers; authoritative stock workflow. |
| `inventory:warehouse_detail` | Specialized Operational Detail; Shared conventions applied; specialized body retained | Stock/balance and transaction workspace preserved; shared header/summary only. |
| `inventory:transaction_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Specialized inventory quantity/value transactions, lines, counts or transfers; authoritative stock workflow. |
| `equipment:work_order_detail` | Standard Record Detail; Migrated | Existing authorized read-only work-order rows and structured evidence. |
| `equipment:maintenance_detail` | Standard Record Detail; Migrated | Existing authorized read-only maintenance rows and source lineage. |
| `equipment:detail` | Standard Record Detail; Migrated | Equipment master identity; retained assignment/maintenance/financial links and state/archive forms. |
| `safety:detail` | Standard Record Detail; Migrated | Incident information, existing action forms, evidence and review revisions. |
| `quality:detail` | Standard Record Detail; Migrated | Issue information, existing verification/action forms, evidence and review revisions. |
| `workflows:version_detail` | Specialized Operational Detail; Excluded from generic migration; existing structure retained | Workflow definition/version administration and immutable configuration evidence. |
