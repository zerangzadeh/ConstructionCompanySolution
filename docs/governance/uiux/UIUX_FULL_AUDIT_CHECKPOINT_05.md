# BONIRA UI/UX Full Audit Checkpoint 05

## Baseline

`main @ 43ac319c6e73e48ca9626461b73987922c498ec3`

## Progress

- Static screen candidates: **383**
- Static-reviewed routed surfaces: **72**
- Findings: **82**
- HIGH: **59**
- MEDIUM: **23**
- CRITICAL: **0**
- Root patterns: **21**
- Positive internal reference patterns: **10**
- Findings requiring domain review: **0**

No remediation has been authorized or executed.

## Shared form infrastructure is now part of the audit

The audit found that `templates/components/form_field.html` is not a neutral renderer. It contains a large field-name-based label dictionary and can override the label explicitly defined by a form.

This creates a systemic source of terminology flattening. For example, a domain label such as «شرح سند» can be rendered as generic «توضیحات» because the field name is `description`.

A new root pattern is therefore recorded:

`RP-C21-SHARED-LABEL-OVERRIDE`

The future form standard should make each form's business label authoritative by default.

## Cascade filtering coverage expanded

Additional evidence confirms inconsistent dependent selection in:

- Accounting Journal dimensions: Project / Site / WBS;
- Accounting Opening: Fiscal Year / Period;
- Support evidence: Document / Document Version;
- Equipment Work Order: Equipment / Maintenance Plan;
- Billing compliance/retention: Contract/Certificate / Clearance Evidence.

These should follow the already-identified context/cascade reference pattern rather than waiting for post-submit rejection.

## Form Intelligence coverage expanded

Additional avoidable technical input was confirmed in:

- Accounting Journal provenance references;
- Equipment cost source/occurrence/reversal keys;
- Commercial Tender evidence raw Document Version UUID;
- Knowledge source/reuse forms using raw UUID/type/version inputs;
- generic form primary actions using «ثبت» instead of a task-specific CTA.

## Useful positive reference

Support case lifecycle is a good state-aware pattern. `CaseTransitionForm` exposes only transitions valid for the current status and uses business-facing action labels. The evidence selector on the same case still needs Document→Version cascade filtering, but the lifecycle interaction itself should be preserved.

## Next static-audit batch

Continue with:

- remaining Accounting statement and period interactions;
- Treasury payment/request relationships;
- Billing document/evidence selectors and payable forms;
- Workforce department/position/team/assignment cascades;
- Equipment operator qualification, spare links and cost handoff forms;
- Knowledge promotion/publication forms;
- shared status-badge semantics, filtering/search conventions, modal/dialog conventions and table action placement.

After the shared-component pass, static coverage should be sufficient to define the Runtime Validation Matrix without starting remediation prematurely.
