# BONIRA UI/UX Full Audit Checkpoint 04

## Baseline

`main @ 43ac319c6e73e48ca9626461b73987922c498ec3`

## Progress

- Static screen candidates: **383**
- Static-reviewed routed surfaces: **64**
- Findings: **72**
- HIGH: **50**
- MEDIUM: **22**
- CRITICAL: **0**
- Root patterns: **20**
- Positive internal reference patterns: **9**
- Findings requiring domain review: **0**

No remediation has been authorized or executed.

## Home / Dashboard conclusion

The Product Owner concern about the current Home is confirmed by the frozen baseline.

The canonical Home is deliberately implemented as a permission-aware destination directory. The view explicitly avoids querying domain business facts, and `core.home` returns a fixed catalogue of authorized workspace links plus optional links to assigned work and alerts.

This is secure and predictable, but it does not function as a professional role-aware ERP dashboard.

A new product-level root pattern is recorded:

`RP-C20-HOME-LINK-DIRECTORY`

Remediation will require a Product Decision because meaningful dashboard summaries may require governed read models for task counts, alerts, exceptions, recency and role-specific indicators. The Product Owner's existing draft design should be treated as reference evidence, not a mandatory implementation.

## Form Intelligence findings continue

The current batch confirms that the same problem extends beyond cascade filtering:

- Billing statutory submission asks the user for idempotency/correlation identifiers.
- Workforce performance evaluation asks for a raw JSON criteria snapshot.
- Payroll operational/configuration surfaces still expose lineage, hashes and implementation metadata.

A useful counter-example also exists: Claim settlement filters Treasury receipts by Project, Party, posted status and reversal state, while generating the idempotency key internally. This is now `REF-P08-BILLING-CONTEXT_SETTLEMENT`.

## Payroll

Payroll Run, Statutory and Financial Handoff pages repeatedly mix operational work with calculation/integration lineage.

The audit recommendation remains presentation separation, not domain simplification:

- user task and valid next action first;
- exceptions and business result next;
- traceability, hashes, lineage and immutable-history details progressively disclosed.

## Next batch

Continue static coverage across:

- Accounting statements and creation forms;
- Treasury operational/statement forms;
- Billing payable/statutory details;
- Workforce structural/foundation forms;
- Payroll statutory/handoff forms and detail;
- Equipment work-order and cost forms;
- Commercial tender create/revise forms;
- Knowledge publication/promotion surfaces;
- Support access lifecycle;
- shared pagination, date, status, filter and modal components.

After static pattern coverage is broad enough, prepare the static-audit closure and runtime/role-based validation plan before any remediation backlog is authorized.
