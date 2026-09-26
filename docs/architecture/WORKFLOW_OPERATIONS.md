# Tenant workflow operations (W6)

This runbook applies to the F5 workflow foundation. All identifiers and queries
must be scoped to one organization. Use the application services with an active
membership and the required business permission; never edit runtime status,
candidate rows, or audit rows directly in SQL or Django Admin.

## Tenant Owner and authorized Tenant operator

- Select the correct active organization, then open **Workbench**. It shows one
  queue for the membership; position tabs are filters, not separate accounts.
- To process a task, claim it when offered, then choose an allowed decision.
  A valid company permission and current candidacy or assignment are both
  required. A stale or already completed task must be reloaded rather than
  submitted again with a new operation key.
- A missing task can mean the membership is inactive, the organization is
  suspended, the role lacks `work_items.view` or the domain view permission,
  the route did not select this member, or another member claimed the task.
  Check these conditions in that order. Changing a position does not grant a
  business permission.
- Definition publication, suspension recovery, and open-instance version
  migration currently have service boundaries but no owner-facing page. An
  authorized operator must perform those actions through the documented
  services. Tenant Owners should provide the Tenant, record, intended outcome,
  and reason to that operator. Tenant Owner status does not itself grant the
  operator permission or imply Tenant Admin / Local Admin assignment.

## Workbench user

- Use the organization switcher before opening Workbench. Filter by workflow,
  project, site, assignment, priority, due date, or position as needed.
- Claiming reserves an offered task; releasing makes it available to the
  current candidate pool. The displayed routing reason records why the task
  reached the queue. It is evidence, not a permission grant.
- If a decision returns a conflict, refresh the task. The previous submission
  may already have committed, or another person may have acted. Do not create
  a fresh key to force a second decision.

## Operator triage and recovery

1. Record the organization UUID, subject type and UUID, instance UUID, current
   version and step key, status, suspension reason, open WorkItem IDs, active
   candidate membership IDs, and related audit events. Query with
   `organization=organization` on every model. Verify the subject's domain
   state before acting.
2. Check tenant status; active membership and role; required permission; route
   configuration; effective position assignment or delegation; and fallback.
   Fix membership or workforce data through their owning services. A route
   that selects nobody suspends the instance with `unresolvable_routing`.
3. For an incidentally suspended instance whose current version is still
   valid, invoke `resume_workflow_instance(actor=..., organization=...,
   instance_id=..., reason=..., idempotency_key=...)`. This re-resolves a step
   only when it has no open item. If an open item already exists but its
   candidate/assignee is stale, use the authorized work-item reassignment or
   delegation service and record the reason. Verify the resulting item,
   candidates, instance status, and audit event in the same tenant.
4. If the published graph or routing is wrong, create a new draft of the same
   definition, correct it, validate and publish it. Existing instances remain
   pinned to their version. For each open instance, confirm that the active
   step key exists in the target and that its domain state is still valid.
   Invoke `migrate_workflow_instance(actor=..., organization=...,
   instance_id=..., target_version_id=..., reason=...,
   idempotency_key=...)` only after that review. The service cancels old open
   items, maps the step, activates new items, and records audit evidence in
   one transaction. If the step cannot be mapped, revise the target version
   or use the domain's documented cancellation/correction path; do not force
   a generic state update.
5. Reuse the **same** idempotency key when retrying an uncertain operation.
   Use a new key only for a distinct, reviewed action. Confirm exactly one
   assignment-history row or lifecycle audit event and the expected domain
   state. Escalate a repeated conflict or still-unresolved route with the
   recorded IDs and audit trail.

The service permissions are `workflows.reassign` for suspend/resume/cancel and
`workflows.migrate_instances` for version migration. The services recheck
authorization and tenant scope under row locks. An operator may call them from
`manage.py shell` using explicitly looked-up actor, organization, and UUIDs;
the shell session itself grants no extra authority.

## PostgreSQL deployment and rollback

1. Take a verified database backup and retain the deployed code revision.
   Confirm PostgreSQL 18.6/Psycopg 3 and the configured database name. Review
   `python manage.py migrate --plan`, then run `python manage.py migrate` and
   `python manage.py check` before exposing the new code.
2. Run the workflow, tenant isolation, concurrency, and Workbench tests against
   a separate PostgreSQL test database. Confirm the permission catalog,
   starter templates, and trigger guards exist. Compare open-record shadow
   reports with domain state before switching a domain.
3. Test a reverse migration on a disposable restored copy first. The W5
   catalog `RunPython` migrations intentionally use no-op reverse functions:
   reversing their migration records does **not** remove catalog rows or
   tenant definitions. Do not assume a code downgrade is a full data rollback.
   For a failed deployment with live instances, stop writes and restore the
   verified backup together with its matching code, or retain the expanded
   schema and restore only compatible application code after review.
4. Reapply forward migrations on the disposable copy and verify the migration
   ledger and catalog/guard state. Never reverse the runtime schema on a live
   database containing open or completed workflow history. Contraction needs
   its own approval and retention plan.

### Missing equipment-maintenance catalog rows

Migration `workflows.0017_equipment_maintenance_compatibility_catalog` owns the
platform workflow type and compatibility template for maintenance records. If
the migration ledger says `0017` is applied but either of those rows is absent
(for example, after an incomplete restore), creating a maintenance record
recreates only the missing platform-owned rows inside the same transaction. It
does not change an existing type/template, tenant definition, published version,
or runtime history. An inactive existing row remains an operator configuration
error and must be reviewed before it is reactivated.

PostgreSQL test role needs `CREATEDB` for Django's normal test runner, or the
test database must be provisioned by a database administrator. Never point
pytest at a production database.
