# Current retained-demo RFQ authority gap

No permission, role definition, scope, assignment or platform duty has been changed.
Policy successors are published and current; this is a separate fixture-authority gap.

The seven retained primary-tenant demo memberships cannot close sealed custody,
attach sealed evidence, request/approve protected opening or administer confidential
access. Buyer/reviewer/evaluator additionally lack `rfq_quotes.view_confidential`;
a per-quote grant cannot substitute for that permission. Existing specialist role
catalogues are sufficient; the runtime has no matching lawful demo assignments.

The initial proposed three specialist accounts alone would be insufficient.
A complete bounded alternative, ONLY if explicitly authorized, is five NEW synthetic
accounts scoped to `MVP08-P01`, retaining all existing personas unchanged:

| New account | Existing native role(s) | Duty |
| --- | --- | --- |
| mvp08.rfq-custodian | rfq_custodian | sealed evidence and close; no opening |
| mvp08.rfq-opening-approver | rfq_opening_approver | independent opening approval/access administration |
| mvp08.rfq-preparer | tenant_manager + rfq_opener | existing sourcing operations plus guarded confidential reading/opening request |
| mvp08.rfq-reviewer | tenant_manager + rfq_opener | independent admissibility/comparison/award decisions |
| mvp08.rfq-evaluator | tenant_manager + rfq_opener | separate commercial evaluation |

This would use the existing seed's explicit synthetic fixture-bootstrap convention,
with native role/scope rows and audit provenance, not pretend that current runtime
administrators can delegate permissions outside their own authority. No broad custom
role, permission definition, default grant, workflow rule or existing account change.
Each quote would still require separate native confidential access grants and all
three self-decision denials. Source-processing test evidence would remain expressly
synthetic Development/UAT fixture evidence, not real scanner qualification.

Continuation section 8 prohibits widening persona permissions. Pending clarification,
none of this proposed fixture extension is executed. Other existing Development tenant
memberships and platform role assignments are not a substitute for demo authority.
