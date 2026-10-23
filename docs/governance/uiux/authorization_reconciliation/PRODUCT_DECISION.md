# Authorization Role Reconciliation and Platform Initial Grant

Human Product Decision supplied in this session, 2026-10-22. Bounded Development
implementation authority; no production execution or Git writes authorized.

The existing authorization architecture remains authoritative. Platform Admin
creates Tenants and designates an Initial Tenant Owner with active membership,
canonical Tenant Owner assignment and Organization scope. Platform authority
does not imply tenant membership, a tenant role, or business-data access.

Review registered permissions absent from defaults against domain purpose. Map
them to appropriate existing roles, adding specialist roles only where current
roles cannot express operational responsibility with least privilege and
separation of duties. Do not use Tenant Owner/Admin to eliminate blockers.

Platform Admin may make an Initial Grant where ordinary tenant delegation cannot
assign the authority because no lawful delegator exists. The grant references an
existing active tenant, active approved role and permissions, exact active target
membership, explicit scope, reason and complete audit. No second platform
approver is required. Self-grants are prohibited. Existing tenant delegation,
protected operations, scope, audit and isolation remain unchanged.

Development users/memberships/assignments may be reconciled or recreated while
preserving domain data unless a reset is necessary. No production identity
migration or legacy-production compatibility requirement arises.

Scope: minimum Role-Permission Matrix correction, Development authorization
fixtures, bounded Initial Grant, focused regression and affected Wave C
revalidation. No Bootstrap Package, multi-stage Bootstrap Governance, new Platform
Security approval workflow or unrelated authorization redesign.

## Implementation contract

- Existing `create_organization_by_system_admin` and
  `bootstrap_membership_authorization` already establish canonical ownership;
  focused regression verifies this path without creating a new bootstrap model.
- `role_reconciliation.py` contains explicit additions; no suffix-based grants.
  Catalogue definitions do not assign specialist roles to memberships. Existing
  identity links, domain activation and source policy gates remain enforced.
- `platform_initial_grant` locks/re-reads platform authority, tenant, receiver,
  role/permissions and delegation evidence inside one transaction. It checks the
  actual ordinary assignment contract, including an independent tenant approver,
  before allowing the exception. It never calls or weakens the ordinary service.
- An explicit narrow scope cannot coexist with broader/unrelated receiver scopes:
  the existing model unions roles and scopes. Use a separate exact membership or
  reconcile Development scope through normal governed services in that case.
- Role and optional scope records retain source `platform_initial_grant`, with
  nullable tenant assigning/approving memberships. Correlated audit events retain
  the platform actor, exact receiver/role/permissions, before/after permissions and
  scope IDs, time, reason and absence-of-delegator decision. No fake tenant actor
  or second platform approver is introduced.
- The trusted management command takes an existing actor username and exact UUIDs;
  it calls the same service. It is an operator CLI, not a tenant HTTP endpoint.

Example (placeholders must be replaced with governed existing identities):

```powershell
.venv/Scripts/python.exe manage.py platform_initial_grant --actor PLATFORM_ADMIN_USERNAME --organization TENANT_UUID --membership MEMBERSHIP_UUID --role ROLE_UUID --scope project --project PROJECT_UUID --reason "Bounded first operational assignment"
```

## Matrix review rationale

The complete generated matrix is `ROLE_PERMISSION_MATRIX.csv` (one permission per
row). The baseline had 148 catalogue permissions absent from every default role:
131 registered codes and 17 existing Support codes missing from the registry.
147 now have explicit responsibility assignments in `role_reconciliation.py`.
`support.audit_reconcile` remains explicitly unassigned because it has no
implemented enforcement path; this task does not invent that operation. Existing
Support enforcement paths are now registered. Registry baseline debt and this
reserved code are documented in `REGISTRY_BASELINE_DEBT.json`.

| Responsibility | Existing role or necessary specialist | Boundary |
| --- | --- | --- |
| Recognition preparation, AP enrollment preparation, source reversal | Accountant | Existing financial service controls retained |
| Recognition/AP enrollment/write-off review | Accounting Reviewer | Separate from preparing/proposing responsibility |
| Billing eligibility, indexation, price books, closeout coordination | Project Manager | Existing project/commercial responsibility |
| Schedule/change acceptance and closeout review | Project Controls Reviewer | Separate from operational preparation |
| Employment and sensitive HR administration | HR Administrator | Existing roles include unrelated project/financial powers; no Payroll preparation |
| HR clearance/certificate/personal-change review | HR Reviewer | Independent from HR administration |
| Own Employment, ESS, personal requests | Member | Explicit identity/ownership checks remain mandatory |
| Rosters | Supervisor | Existing field supervision responsibility |
| Leave policy/balances | Tenant Manager | Existing operational management responsibility |
| Payroll preparation/statutory outputs/handoff preparation | Payroll Specialist | No Payroll review/finalization |
| Payroll/handoff review and finalization | Payroll Reviewer | No Payroll preparation |
| RFQ custody; opening; opening approval/access administration | RFQ Custodian; RFQ Opener; RFQ Opening Approver | Separate closed-source duties and domain candidacy remain required |
| Supplier invitation management | Supplier Portal Manager | No external user tenant membership |
| Projection preparation; review; audit; sensitive exports | Reporting Analyst; Reviewer; Auditor; Sensitive Reader | No transaction authority; sensitive reading/export separately assigned |
| Tenant support operation; tenant confirmation; platform-side confirmation | Support Operator; Access Confirmer; Access Approver | Existing independent requester/tenant/platform-side checks retained; role name alone never supplies Platform authority |

The existing Support service requires tenant permission and scope even for its
platform-side confirmation. This decision does not redesign that contract or
grant platform users implicit tenant access. An explicitly assigned support duty
continues to require its ordinary membership and scope.
