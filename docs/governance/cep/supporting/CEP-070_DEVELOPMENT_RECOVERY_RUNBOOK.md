# Approved synthetic Development recovery controls

Authority: `CEP-070_EXT0020_HUMAN_APPROVAL_20261027.md`. Machine-readable
configuration: `CEP-070_DEVELOPMENT_RECOVERY_POLICY.json`. All four classes share
RPO 900 seconds, RTO 3,600 seconds, a maximum 900-second backup spacing,
30-day minimum recovery-copy retention and a 30-day restore-test interval.
PITR is not required in this scope. No production policy is supplied.

The existing `backup_bundle.py` remains a capture-only adapter. The separately
authorized `cep070_recovery_controls.py` adds protected local storage verification,
supervised scheduling, complete-bundle integrity checks, durable due dates,
retention receipts, exception events and an OS worker lock. No Django app, schema,
tenant permission, asynchronous product queue or new dependency is introduced.

## Local storage and secrets

Only generated synthetic bundles are retained under
`E:/BONIRA_Recovery/<run-id>/bundles/`. Resolve the exact
non-secret run reference from `STORAGE_INITIALIZATION.json` in the execution's
evidence folder. The directory boundary disables inherited access and grants
access only to the current operator, Local System and local Administrators.
Every capture/validation rechecks the actual directory/file DACLs and rejects
links/reparse points. This is ordinary OS access control, not encryption,
immutable/WORM storage or evidence of production key custody.

The existing repository `.env` supplies Development secrets. Its contents are
never copied into a recovery bundle, plan or public evidence. The execution
checks and, if necessary, tightens only this file's DACL, preserving original
ACL metadata privately under the approved storage boundary. No secret value or
original ACL identity list is printed. A named private libpq service supplies
connection metadata and a scoped process environment supplies the password.
Temporary service metadata and fixture files are removed at the end of the run.

## Supervised qualification procedure

Use the existing `.venv-2` runtime and PostgreSQL 18.6 binaries. Set
`BONIRA_CEP070_APPROVED_QUALIFICATION=1` and
`BONIRA_CEP070_PRIVATE_STORE` to a newly initialized, verified private store.
`scripts.cep070_recovery_controls.create_private_store` initializes a unique
empty directory; it never replaces an existing directory. Set the optional
`BONIRA_CEP070_TEMPLATE_DATABASE=test_construction_erp` only when its user/org
counts are zero and its migration graph exactly matches the current repository;
the harness checks those conditions before cloning. The template is never the
restore target and no connections are forcibly terminated.

Run `scripts/cep070_erp_recovery_proof.py`. The approved mode provisions two new
loopback fixture databases, synthetic current ERP content and three private file
trees. It never connects to the configured business database. Existing migrations
only provision the disposable schema; this is not a migration test or cutover.

The bounded worker holds a Windows byte-range lock for its lifetime. Two actual
captures are requested. The next capture deadline is 900 seconds after the
previous capture starts; dispatch reserves the plan's existing 180-second tool
execution budget ahead of that deadline. Thus execution can be more frequent
than every 15 minutes, never using that budget as an allowed late-backup grace
period. Actual timestamps and interval comparisons must be evaluated; a configured
deadline alone is not a cadence PASS. Capture failure retains partial bytes and
sanitized exception events, leaves the last good bundle/due date unchanged and
fails the worker. Incomplete captures are quarantined, never recovery points.

The restored fixture must match all complete table rows, sequence state,
constraint identities and normalized predicates; all file trees and immutable
version digests; exact Decimal budgets; and authorized/cross-tenant service
behavior. Failed equality or objective checks cannot advance the restore-test
date. The restore clock runs from invocation against the preprovisioned empty
target through reconciliation and service validation. Zero lost acknowledged
fixture writes proves RPO only for that quiescent synthetic scenario; it supplies
no changing-workload, provider, region, web-startup or production SLA claim.

## Retention and subsequent drills

Successful bundles receive a durable receipt binding the capture-manifest hash,
policy hash, completion timestamp and `retain_until = completion + 30 days`.
Inventory/byte integrity and receipt consistency are checked before use. A
shortened retention deadline or mismatched manifest is a failure. Failed capture
bytes are retained separately in a quarantined disposition. There is no purge
operation: expiration means separate disposition authority is required. Backup
retention never overrides document/audit retention or legal holds.

An actual successful restore records its measured outcome and sets the next test
due 30 days after completion. On a supervised worker invocation, a supplied
restore callback runs when due; an absent/failed callback supplies no successful
drill evidence. Restart reloads durable status after acquiring the OS lock.
Clock-controlled 30-day boundary tests verify control behavior only; they do not
establish 30 elapsed days or an executed future drill.

The current executor assignment is session-bounded. The worker stops after its
requested cycles, and no unattended Windows task/service is installed. Future
due dates are retained for the next authorized executor. Continuous operation
after this session is unverified, not implicitly staffed or scheduled.

Human Decision Authority is accountable and owns acceptance. Codex is the
technical executor and records technical evidence only. CEP-070 production AC/DoD
and CEP-074's production-equivalent environment remain governed by their unchanged
contracts. This Development drill cannot be renamed CEP-074 or final certification.
