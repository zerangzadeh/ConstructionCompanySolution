# ADR P0-S10: Async delivery, transactional outbox and idempotency boundaries

**Status:** PROPOSED — preparation complete; acceptance and implementation pending.
**Recorded:** 2026-09-25. **Scope:** P0.1 async/outbox ADR; informs P0.2,
P1.3, P6.3 and P9.4 without implementing those packages.
**Authorization:** Product Owner: “continue and do S10”, following the
[S09 handoff](../ROADMAP_EXECUTION_PLAYBOOK.md#34-p0-s09-dms-domain-link-adr-proposal-and-s10-handoff).

Prepare ownership, delivery/retry/authorization and recovery contracts within the
[Roadmap](../../ROADMAP.md). No worker, scheduler, broker, Celery/Redis, integration,
notification channel, provider or dependency is selected or installed. Preserve
current synchronous behavior. This is neither event sourcing nor a new workflow
engine, and it grants no privileged/support or background-service exception.

## 1. Current evidence and limits

| Source | Verified behavior and planning consequence |
| --- | --- |
| [Workflow runtime](../../apps/workflows/runtime.py): `complete_work_item` | Atomic completion locks runtime/subject context, rechecks work-item authority, checks assignment/candidacy/separation and resolved domain permission, executes a registered domain command synchronously, then records completion/history/audit and advances runtime. Keep these business invariants in one domain transaction. |
| [Workflow models](../../apps/workflows/models.py) and runtime | Organization-scoped idempotency constraints exist for instances/work items; assignment history is unique by organization/work item/key. Completion returns an existing result when that item's key is found. These are local operation identities, not external delivery receipts or a general payload-fingerprint contract. |
| [Audit service](../../apps/audit/services.py): `record_audit_event`; [models](../../apps/audit/models.py): `AuditEventQuerySet`, `AuditEventManager`, `AuditEvent` | Persists evidence using the caller's database transaction; instance and default-manager/queryset guards restrict mutation. Metadata key checks are not a general payload-redaction engine. Audit has no job claim/attempt/acknowledgement lifecycle and must not become the outbox. |
| [Organization service](../../apps/organizations/services.py): `create_organization_with_owner` | Organization and initial Tenant Owner creation registers post-commit callbacks for purchase-request and daily-report starter workflows. The current function name is compatibility evidence and does not merge the independent target Tenant Admin role. The callbacks are not durable pending-work records. This ADR neither moves these effects nor claims they are part of the creation transaction. |
| [Account service](../../apps/accounts/services.py): `update_personal_settings`; [workforce service](../../apps/workforce/services.py): profile-image cleanup | Old image deletion is registered with `transaction.on_commit`. After-commit timing is different from durable retry/recovery; personal account scope must not be relabeled as a tenant job. No cleanup behavior changes here. |
| [Document services](../../apps/documents/services.py): `_create_version`, `add_document_version`; [S08](ADR_P0_S08_PRIVATE_DOCUMENT_STORAGE.md) | File storage and database outcomes need explicit reconciliation. Scanning/quarantine, export and durable retry are future proposals, not existing asynchronous jobs. |
| [Requirements](../../requirements.txt), [database requirements](../../requirements-db.txt), application/configuration search | No Celery/outbox implementation was found in the inspected files; current dependency files do not add a broker/worker stack. This bounded inspection is not an audit of deployed infrastructure or every external side effect. |

Direct [runtime test bodies](../../apps/workflows/test_runtime.py) inspected, not run:
`test_domain_command_failure_rolls_back_all_runtime_changes` verifies rollback of
the sample command/runtime history;
`test_complete_is_idempotent_and_advances_to_terminal` verifies repeated completion
calls the sample command once. The [audit test](../../apps/audit/tests.py)
`test_audit_events_are_append_only` covers instance and queryset mutation denial.
None tests a broker, external acknowledgement, payload-key conflict or worker crash.

Narrow C2 inspection of `on_commit` callers and the completion-key branch was needed
to distinguish post-commit execution and local idempotency from durable delivery.
The [workflow transaction contract](TENANT_WORKFLOW_AND_WORK_MANAGEMENT.md#10-transaction-concurrency-and-idempotency)
remains authoritative for business completion; its operations guidance is not a
general integration-replay policy.

## 2. Proposed ownership and alternatives

| Responsibility | Proposed owner and source of truth |
| --- | --- |
| Business state, approvals and financial finality | Existing domain services and registered workflow commands. Queue execution never updates domain status generically or makes an approval. |
| Durable delivery intent | Platform delivery infrastructure stores a tenant-scoped outbox record in the same database transaction as the source decision. The domain defines the purpose, destination contract and stable source/version identity. |
| Dispatch, leases and attempts | Platform transport/job adapter owns retryable execution state and attempt evidence. A broker message is a wake-up/delivery carrier, not business truth. |
| Provider submission and reconciliation | Consuming integration domain owns request identity, external receipts, uncertain outcomes, correction/cancellation and source-to-provider reconciliation. Transport success is not statutory/business acceptance. |
| Notification preference, recipient and read/delivery state | Future P9.4 owns the notification record and permitted channels. WorkItem remains the actionable assignment; AuditEvent remains evidence. |
| Scan/export/maintenance result | Owning domain stores version-bound processing/result evidence and accepts it through its service, under S08 and the approved operation authority. |

Prefer an application-owned transactional outbox using existing Django/PostgreSQL
for durable intent, with a separately approved maintained transport/worker adapter.
Reuse commodity queue, email, storage and security components after explicit
dependency review; do not build a general queue platform or security protocol.

| Alternative | Tradeoff / disposition |
| --- | --- |
| Keep a bounded operation synchronous | Appropriate where no durable asynchronous requirement exists; remains the current baseline. Network latency/failure must not be hidden inside a purportedly atomic external transaction. |
| `on_commit` dispatch only | Avoids dispatch before commit, but a process can stop after commit before delivery. Useful as a best-effort wake-up for a durable record, not sufficient as its replacement. |
| Database outbox, recoverable dispatcher and approved worker transport | Captures intent with the source commit and permits recovery after dispatch loss. Recommended proposal; needs operational ownership, duplicate handling and reconciliation. |
| Polling execution without a separate broker | Possible initial transport for approved bounded work; still needs the same durable state, leases and operational checks. Decide throughput/latency from workload rather than presuming a broker. |
| Derive jobs from AuditEvent, signals or tenant executable callbacks | Excluded: audit is not dispatch state, critical business effects cannot be hidden in signals, and tenant code/URLs cannot define an unrestricted execution surface. |

No scheduling frequency, retry count, timeout, SLA or package is approved here.
The async design must not convert all existing `on_commit` callbacks or synchronous
services automatically; each consuming package needs a reviewed delivery contract.

## 3. Transaction and execution contract

Within an authorized domain transaction, re-read/lock source state, enforce tenant,
permission, object scope, workflow authority and separation, perform the domain
transition, record audit, and insert durable intent atomically. Failure rolls back
all database effects. Do not send external requests inside this transaction.
External completion that must affect business state is a subsequent explicit
domain transition, not an extension of the original database transaction.

Proposed intent evidence: public UUID, tenant, registered operation/schema version,
source type/identity/version, purpose, stable business idempotency key, canonical
payload fingerprint, minimal payload or immutable version reference, initiating
actor/membership and authorization evidence, destination configuration version,
correlation/causation IDs, creation/due time and expiry/cancellation policy. Store
credentials by protected configuration reference, never cookies, session state,
tokens, file contents or bearer URLs in job payloads/logs. Target and schema
identifiers come from a platform-owned allowlist, not arbitrary imports or callbacks.

Separate immutable intent from mutable delivery state and retained attempt history.
Proposed delivery states are pending -> leased -> succeeded, retry-wait, blocked,
outcome-unknown or exhausted; cancellation is an authorized transition while its
contract still permits it. Dispatch/lease expiry alone does not prove delivery or
non-delivery. Record provider acceptance and downstream business acceptance
separately from transport completion.

1. A recoverable dispatcher finds committed eligible intent; after-commit wake-up
   may reduce latency, but polling/reconciliation recovers missed wake-ups.
2. Claim a bounded batch using database serialization and a lease generation;
   commit the claim before external I/O. A stale lease holder cannot overwrite a
   later local result. Lease fencing alone cannot undo an external side effect.
3. Re-resolve tenant/source and the approved operation authority at execution,
   validate payload fingerprint/schema/version and cancellation/expiry, then call
   the approved adapter. Rechecks fail closed; do not trust a message's tenant ID
   or stored actor identity as an authorization grant.
4. Use the same external operation key for retries. Record attempts and receipts;
   acknowledge transport only after the required local result is durable. A crash
   between those steps must be recoverable without a second business effect.
5. Apply accepted results through the owning domain service with its own atomic
   invariants and idempotency. Callback/import receipts are validated and deduplicated
   before use; untrusted external data never chooses an arbitrary tenant or command.

## 4. Idempotency, order and uncertain external outcomes

Propose a tenant + operation + source-version + destination/business-purpose key,
with a reviewed uniqueness constraint. A notification fan-out also needs a stable
recipient/channel identity; a retry attempt is not a new logical message. Same key
and same canonical payload returns/reconciles the previous result; same key with
different payload fails explicitly. A correction is a new reviewed operation linked
to its original, not a retry whose payload changes silently.

At-least-once delivery can repeat dispatch. Do not claim exactly-once external
effects from an outbox, row lock or successful broker acknowledgement. Use provider
idempotency where its verified contract supports it, and persist provider request
and receipt identities. If a timeout/crash follows possible acceptance, record
outcome-unknown and query/reconcile that identity before retrying. If neither safe
retry nor status lookup exists, stop for authorized human resolution; do not guess
failure and resubmit a financial/statutory action.

Classify retryable transport failure, permanent validation rejection, policy or
authorization block, stale source and uncertain outcome separately. Use bounded
backoff, attempt/deadline limits and poison-message isolation under approved
operating policy. Exhaustion is visible unresolved work, not silent success or
permission to mutate the source. Operator retries retain the original key and
reason/audit; edited payloads require a new operation and approval where applicable.

Declare ordering per aggregate/destination when required. A correction cannot
overtake its original submission merely because another worker is faster. Retain
source version/sequence/dependency and park premature work for reconciliation;
do not impose global tenant ordering without a need. Older events may be suppressed
only under an explicit domain policy; financial/evidence history is not coalesced
like a replaceable projection refresh.

## 5. Authority, tenant lifecycle and privacy

The [S07 scope proposal](ADR_P0_S07_PROJECT_SITE_AUTHORIZATION.md) still gates
object authorization and privileged paths. A worker credential is technical access,
not a superuser business identity. No synthetic membership or support bypass is
introduced. Distinguish three operation contracts before enabling a handler:

- Deferred user commands must recheck active membership, current permission/scope,
  state and any current workflow assignment/separation at execution. Stored
  authorization evidence explains the request but cannot preserve revoked power.
- Delivery of an already committed decision is not a new approval. The responsible
  domain must decide whether it remains an obligation after initiator revocation,
  suspension or cancellation, and specify approved execution authority and allowed
  actions. No such exception is accepted here; absent that contract, block delivery
  and surface the unresolved obligation rather than silently canceling or bypassing.
- Maintenance, scanning, export and retention actions need explicit purpose, scope,
  authority and lifecycle policy. Personal-account work and tenant work must have
  separate explicit contexts; a missing tenant is never a platform-wide wildcard.

Recheck notification recipient membership, subject visibility, permitted channel
and preference/consent at delivery. External content must be minimal; a link back
to an authenticated view still re-authorizes on access. Do not copy sensitive work
item titles, financial amounts, filenames or diagnostics into a message just
because the recipient was once a candidate. Read/delivery state does not claim or
complete a WorkItem. Scheduling/escalation invokes registered domain services and
retains their normal authority; scheduling is not a second approval system.

Replay, cancellation, recipient change, handler configuration and cross-tenant
operational inspection require approved permissions/separation and audited reasons.
New capabilities use the existing permission registry and catalog/default-role
migrations. Dispatch dashboards must separate authorized tenant views from any
separately approved operational controls. No tenant-authored network destination,
executable template or unregistered expression is authorized.

## 6. Recovery, retention and compatibility gates

Keep outbox intent, receipts, deduplication keys, attempts and correlation lineage
in the recovery design with source records, audit and S08 blob/version evidence.
Retention must preserve deduplication knowledge for the approved retry/replay
window; do not prune keys while old messages or provider retries can still arrive.
Q03 determines evidence retention and privacy obligations; no duration is invented.

A database restore can resurrect pending work whose external effect already
happened. Pause dispatch after restore until source/provider receipts and operation
keys are reconciled; rebuilding a broker queue must not imply blind resubmission.
Rollbacks must retain readable handler/payload versions for outstanding intent or
explicitly block it for recovery. Transport rollback cannot erase external effects.
Use corrections/reversals through authorized domain services, never database edits
to pretend an accepted transmission did not occur.

After acceptance and separate package authorization:

1. Select one concrete producer/consumer contract and classify its current side
   effects, source/version identity, authority, latency and failure policy. Do not
   broaden the first slice to every workflow or callback.
2. Approve schema/handler ownership, dependencies, operating limits and privacy;
   expand durable intent/attempt storage with constraints and transaction tests.
   Keep current domain services authoritative and preserve finalized history.
3. Rehearse with a non-delivering validation adapter. Compare intent/source/audit
   parity and expected recipient/scope decisions; do not send historical audit
   events as “backfilled” notifications or external submissions.
4. Switch one producer with a single coordinated writer. Prevent synchronous plus
   asynchronous duplicate sends; drain/account for in-flight work before rollback.
   Existing `on_commit` setup/cleanup changes require their own approved tests.
5. Validate crash windows, duplicates, concurrency, unauthorized/foreign-tenant
   messages, restore/reconciliation and bounded workload behavior. Retain legacy
   compatibility until parity/dependency and retention gates pass; removal still
   requires explicit approval.

Operations need named ownership, queue age/lease expiry/retry/unknown-outcome
visibility, per-tenant fairness/quotas, alerting, redacted correlation and recovery
runbooks. D03 controls provider/residency/operator; D04 recovery targets; D05 capacity
and lifecycle; Q03 retention/export; Q04 authority/Self-Approval selections are
recorded but named review and operation-specific enforcement remain open. P6.3 additionally
retains Q02 professional/legal/provider-protocol acceptance. P9.4 channel choices
remain unapproved. These inputs gate affected implementation, not this proposal.

## 7. Static design cases and acceptance limits

These are design walkthroughs, **not executed tests**:

| Case | Proposed expected result |
| --- | --- |
| Domain transaction rolls back | No committed state, work-item completion, audit or outbox intent from that operation. |
| Commit succeeds, process stops before dispatch | Durable pending intent is recovered; missing wake-up does not lose work. |
| External effect succeeds, local receipt or broker acknowledgement is lost | Reuse identity and reconcile; never infer safe resubmission from missing local success. |
| Same key repeats with same versus different payload | Same-input deduplication; different input explicitly rejected, not treated as success. |
| Lease expires during slow external I/O | Fence stale local writes and use provider identity/reconciliation to address duplicate external attempts. |
| Forged tenant, revoked actor/scope or unsupported handler | Deny/block under the operation contract; no worker-superuser or null-tenant fallback. |
| Initiator revoked or tenant suspended after a committed obligation | Block pending an accepted lifecycle/authority contract; retain obligation and reason for resolution. |
| Notification visibility changes before delivery | Recheck recipient/content authority; no sensitive disclosure or WorkItem completion. |
| Correction arrives before original or retries are exhausted | Park/reconcile or expose unresolved failure; preserve ordered domain history. |
| Restore resurrects intent for an already accepted external request | Pause dispatch and reconcile receipts/keys before reopening; no blind replay. |

Implementation acceptance needs atomic producer tests, payload/key conflict tests,
worker crash/lease races, provider timeout fixtures, callback authenticity and
deduplication, per-recipient isolation, explicit service authority, ordering,
retry exhaustion, source/result reconciliation and restore/rollback evidence.
No runtime delivery or operational guarantee is certified by this ADR. P0.1 and
affected implementation packages remain incomplete; S04-S10 acceptance is separate.
