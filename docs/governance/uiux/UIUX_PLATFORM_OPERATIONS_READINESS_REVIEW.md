# Platform Operations readiness review — BATCH-02 / UIUX-F-122

Date: 2026-10-22, Asia/Tehran. Mode: **read-only analysis; this report only**.
Decision: **PLATFORM_OPERATIONS_ASSIGNMENT_READY**.

This means an existing canonical assignment path and eligible existing actors
were identified. It does not authorize or perform the assignment, fixture
preparation, assessment recording or BATCH-02 runtime retest.

## Baseline and evidence

Branch `main`; HEAD `43ac319c6e73e48ca9626461b73987922c498ec3`. Existing ten dirty
product files and untracked UIUX, tests, Graphify and document artifacts remain.
The prior BATCH-02 closure evidence manifest matches its current files. F-121
remains `RUNTIME_VERIFIED_RESOLVED`; F-122 remains
`REMEDIATION_IMPLEMENTED_PENDING_RUNTIME_RETEST`.

Source/test/governance inspection and read-only PostgreSQL queries used
`config.settings.development`, loopback database `construction_erp`, with session
`default_transaction_read_only = on`. No credentials or authentication material
were read. Tests were inspected, not executed. Existing Graphify nodes/edges were
queried in memory for navigation; no graph output was written.

## 1. Canonical role/duty definition — YES

`PlatformRoleCode.PLATFORM_OPERATIONS = "platform_operations"` is already defined
in `apps/organizations/models.py:137`. Migration
`apps/organizations/migrations/0041_alter_platformroleassignment_role.py` records
it alongside Platform Admin, Platform Security and Restore Evidence Approver.
`PlatformRoleAssignment` at `models.py:2667` stores the explicit user assignment,
effective interval, assigning/approving actors, reason and revocation history.

The decided governance source
`docs/architecture/P1_S19_S22_PRODUCT_OWNER_DECISION_PACKET.md:9` assigns
storage/recovery execution to Platform Operations, key custody to Platform
Security, and restore-evidence approval to a separately assigned approver.
The role is implemented existing authority, not a proposed new Product Decision.

## 2. Exact implemented permission/capability set

This duty has **no BusinessPermission/M2M permission bundle** and grants no Django
staff/superuser flag, tenant membership, tenant role or scope. Current production
source references to this duty enforce these three operations:

| Canonical operation | Authority and remaining checks |
| --- | --- |
| `apps/documents/services.py:859`, `record_document_processing_assessment` | Record append-only scanner/OCR assessment against a DocumentVersion. Stores version hash, adapter provenance, verdict and assessment/audit evidence. Sealed supplier evidence forbids extracted text, details and provider reference. |
| `apps/documents/services.py:931`, `record_document_signature_evidence` | Record provider-neutral signature evidence; validate state; deny sealed supplier-quote evidence. No inferred legal signature certification. |
| `apps/documents/services.py:1547`, `reconcile_document_recovery_boundary` | Reconcile document storage/hash and recovery evidence for a tenant against an existing same-organization key-custody attestation and nonempty database reference. It does not approve restore evidence or supply Platform Security key-custody authority. |

`has_platform_role` (`apps/organizations/authorization.py:143`) requires an active
authenticated user, matching explicit role, started/not-ended interval and no
revocation. It does not infer the role from another platform duty or Superuser.
The duty also satisfies `is_platform_actor` for explicitly permitted platform
audit recording (`apps/audit/services.py:68`); that is not tenant authorization.

**Material scope:** the operational services accept their document/organization
inputs under the platform-duty gate. The assignment has no per-tenant,
per-document or BATCH-02 scope field. Its capability is platform-wide; a reason
containing a fixture marker is audit context, not an enforced object restriction.
Bound the future assignment by time and the separately authorized task. No new
permission or narrower authorization model is proposed here.

## 3. Distinct from Platform Admin and Superuser — YES

Platform Admin is a separate explicit `platform_admin` assignment. Superuser is
the separate technical `User.is_superuser` authority. Neither implies Platform
Operations; an ordinary nonstaff/nonsuperuser can hold Operations explicitly.
No platform duty supplies ordinary tenant business authority.

The legacy migration `0035_p1_1_role_catalog_closeout.py` bootstraps **Platform
Admin only** for `admin`. It is historical migration behavior, not an Operations
provisioning route. Do not replay/edit migrations or invoke a bootstrap bypass.

## 4. Assignment/revocation path

Use the existing application services in
`apps/organizations/access_services.py`:

- `assign_platform_role` at line 814: atomic; nonblank reason; valid role and
  interval; active Superuser actor and approver; active target distinct from
  both; creates the assignment and `AuditAction.PLATFORM_ROLE_ASSIGNED`.
- `revoke_platform_role` at line 887: atomic; locks the assignment; requires a
  nonblank reason and **two distinct active Superusers**; neither may be the
  target. It stamps revocation fields and emits `PLATFORM_ROLE_REVOKED` without
  deleting the assignment. An already-revoked assignment returns unchanged after
  the initial actor/approver checks.

Assignment currently permits the same Superuser as actor and approver provided
the target differs. This is explicitly demonstrated by
`test_single_superuser_can_assign_platform_admin_without_tenant_access` in
`apps/organizations/test_p1_1_authorization.py:343`. Do not incorrectly require
two different Superusers for assignment as existing semantics. Nevertheless,
use two different existing actors in the proposal so canonical revocation is
also immediately feasible. Do not change the assignment semantics.

No caller/UI for assigning these platform duties was found outside the service
and its Platform Admin compatibility wrapper/tests. The route
`/organizations/platform/roles/` manages the OrganizationRole catalogue; it does
not assign `PlatformRoleAssignment` duties. There is no registered direct Admin
editor for the assignment in current organizations/accounts Admin modules.
The bounded operational entry is a trusted Development application-service call,
with explicit actor/approver/target arguments and no direct model/SQL write.

## 5. Authorized assigning actor

Read-only Development inspection confirms two distinct active Superusers:
`admin` and `superuser`. Therefore the proposed pair is:

- Assigning/revoking actor: `admin`.
- Approving actor: `superuser`.
- Target: the ordinary reference candidate below, distinct from both.

Both qualify through `is_active` and `is_superuser`, not because `admin` also has
Platform Admin. A Tenant Owner, Tenant Admin or non-Superuser Platform Admin
cannot assign/revoke this duty through these services. No login, credential
usability or Human approval action was exercised in this analysis.

## 6. Candidate Development identity

Existing synthetic candidate: **`account.demo-construction-03.viewer`**.
Current source-of-truth query confirms active account, `is_staff=False`,
`is_superuser=False`, active membership in active `demo-construction-03`, viewer
compatibility role, **zero effective tenant scope grants**, zero platform-role
assignments and no Operations duty. Explicit tenant authority would remain
unchanged. Platform processing does not require adding source-tenant membership
or grants to this user.

This is technically eligible and avoids changing P-17, the organization/view
positive-control actor or retained empty-state identity. It is a proposed
time-limited co-assignment to an existing synthetic account, not a claim that the
account is already a dedicated platform operator. Its current
`must_change_password=True` does not appear in the platform-role service gates;
interactive use would still require the existing first-login process. No password
reset or flag change is proposed for service-only fixture preparation.

`uiux.audit.empty` is the only active ordinary identity with zero memberships,
but is retained as `P-01-EMPTY` in `runtime_evidence/README.md:45`; do not silently
repurpose that baseline persona. The `uiux.persona.project-operations` alias is a
tenant member persona, not evidence of a Platform Operations assignment.

## 7. New persistent reference identity, if preferred

An additional identity is unnecessary for the minimum proposal. If the Human
instead authorizes a dedicated reference identity, current canonical
`create_organization_account` (`apps/organizations/services.py:103`) can create
one with the existing viewer role through tenant account-management authority.
The existing `account.demo-construction-01.owner` currently passes
`accounts.create`; role delegation is separately enforced. This flow records
`ORGANIZATION_ACCOUNT_CREATED`, requires a validated temporary password/first-login
change and creates a quarantined membership without effective tenant access.
No role catalogue, scope grant or tenant-access activation is needed merely to
assign the platform duty afterward.

That optional path creates an identity **and a tenant-associated quarantined
membership**, so it is broader than using the existing candidate. No dedicated
audited standalone platform-only identity provisioning service was found.
`UserManager.create_user` is a low-level identity primitive without this actor
authorization/audit workflow; it is not the recommended provisioning shortcut.
Django User Admin has `has_add_permission=False` and rejects new-user saves
(`apps/accounts/admin.py:322,335`). The disabled
`provision_user_for_organization` at `services.py:364` must not be used as a bypass.

## 8. Minimum proposed mutation — not executed

One `PlatformRoleAssignment` for the existing candidate and the canonical audit
event; **no user, role catalogue, BusinessPermission, membership or scope changes**.
In a separately authorized Development task, invoke:

```python
assignment = assign_platform_role(
    actor=admin,
    approver=superuser,
    target=existing_candidate,
    role=PlatformRoleCode.PLATFORM_OPERATIONS,
    reason="BATCH_02_RUNTIME_CLOSURE_FIXTURE: Development-only preparation",
    starts_at=task_start,
    ends_at=task_start + timedelta(hours=1),
)
```

The one-hour window is a bounded proposal, not a new policy. Resolve and recheck
all named actors and existing assignments at execution; capture the returned
assignment ID and its audit event. No raw SQL/model assignment, staff flag,
Superuser promotion, grant, service override or new bootstrap is needed.

## 9. Reversibility and auditability

After fixture preparation, use `revoke_platform_role(actor=admin,
approver=superuser, assignment_id=assignment.pk, reason=...)`. Keep both
Superusers available until revocation completes. `has_platform_role` immediately
denies the revoked duty; expiry also denies it automatically. An expired but
unrevoked row still occupies the model's one-unrevoked-user/role uniqueness
constraint, so explicit revocation is preferable to deleting/recreating history.

Assignment and revocation events retain actor, target, role, approver and reason;
the row retains assigning/approving actors, interval and revocation fields.
Revocation does not delete prior processing assessments, canonical fixture
approval/workflow history or their audits. Document processing assessments are
append-only and reject update/delete (`apps/documents/models.py:561`).

## 10. Product Decision and BATCH-02 feasibility

**Product Decision required: NO. Authorization-model change required: NO.** The
role, operational gates, assignment/revocation APIs and two eligible Superusers
already exist. A future concrete assignment is still an authorization mutation
requiring bounded Human authorization; this analysis supplies no such execution.

The identified authority prerequisite is **technically provisionable**. Assignment
alone does not create a CLEAN result, scan a file, authorize fabricated findings,
approve a ComplianceEvidence record or close F-122. A later authorized task must
record truthful synthetic-fixture processing evidence via the canonical service,
create/submit/independently approve the minimum clearances, and complete the
missing fresh-process runtime matrix before changing F-122 to resolved.

Relevant existing test sources were inspected: Documents S21 explicitly assigns
Operations to an ordinary user through `assign_platform_role`, rejects an
unassigned tenant owner, and proves unknown/latest-non-CLEAN versions fail closed
(`apps/documents/test_p1_s21_processing.py:61,87`). S22 tests the separate
Operations/Security/Restore Evidence Approver recovery boundary
(`apps/documents/test_p1_s22_retention_recovery.py:163`). No tests were rerun or
new runtime PASS claimed.

## Safety boundary and verification

Only this report is created. No roles assigned/revoked, users created, account
flags/passwords changed, permissions/scopes changed, assessments/fixtures written,
product/test/graph/evidence/register files changed, server/browser launched,
BATCH-02 runtime checks executed, or Git writes performed. BATCH-01/F-121 and
BATCH-02/F-122 remain unchanged; BATCH-03..09, Wave C, Production and CEP-078/079
remain unexecuted.

Read-only integrity comparison covers all 519 model tables (User `last_login`
excluded) and 8,862 existing repository files, excluding this new report.
Before/after digests are unchanged. Source/Markdown references and report
whitespace were checked; application validation was not repeated.
