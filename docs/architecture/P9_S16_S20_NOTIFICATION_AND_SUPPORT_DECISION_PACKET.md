# P9-S16–S20 Notification and Support Decision Packet

**Status:** **PRODUCT OWNER ACCEPTED — 2026-10-06.**
`P9-N01`–`P9-N18 = Option A` and the bounded runtime are Product Owner accepted.
**Official envelope:**
`P9-S16–S20` only. **Prerequisite:**
`P9-S01–S15 = Product Owner accepted`, verified in `ROADMAP.md`, the execution
playbook, and the accepted P9 decision packets.

## 1. Exact session decomposition

| Session | Bounded planning contract |
| --- | --- |
| S16 | Tenant notification policy, recipient preference/consent, in-app record and delivery-intent boundary. |
| S17 | Source-linked notification lifecycle, read/dismiss, retry/uncertainty and escalation/reminder policy; no scheduler or provider. |
| S18 | Calendar aggregation and supervisor workbench over authoritative work-item/due facts; no second work-item authority. |
| S19 | Support case lifecycle, safe diagnostic consent, attachment/evidence boundary, time-limited support-access proposal. |
| S20 | Support SLA/escalation, audit/reconciliation, permissions/RTL UI, migration posture and focused acceptance. |

## 2. Ownership and data flow

Notifications owns tenant policy, recipient preference, immutable source link,
delivery intent/status and read evidence—not source business facts, assignments or
provider receipts. Workflows remains the work-item authority; source domains own
their state. Calendar is a read model over source due dates. Support owns cases,
safe diagnostic consent and support-access proposals—not tenant membership,
documents or production facts. DMS alone owns attachment bytes and versions;
Audit owns append-only audit evidence. Any future provider submission is an
integration/outbox concern, separately authorized.

`source fact/work item → notification intent → in-app recipient view → optional
future delivery proposal`; `support case → consented diagnostic references/DMS
pins → escalation or time-limited access proposal`. Neither flow mutates
Accounting, Cost, Inventory, Equipment, Contracts, Procurement, AP/AR, Treasury,
Payroll, Fixed Assets or production.

## 3. Lifecycles and controls

- Notification: `draft → queued_intent → in_app_available → read|dismissed`;
  `queued_intent → cancelled|expired`; delivery uncertainty is recorded, never
  inferred as delivered. Source cancellation produces a linked cancellation,
  never silent deletion.
- Support case: `open → triaged → in_progress → awaiting_requester|resolved →
  closed`; `resolved|closed → reopened`. Published response/closure is immutable;
  correction is an appended replacement; escalation is a source-linked event.
- Access proposal: `draft → requested → approved|rejected|expired|revoked`; a
  future platform authorization service, not Support, enforces any grant.

Every consequential transition locks/re-reads its record, checks expected state,
deduplicates a caller operation key plus payload hash, records actor/time/reason,
and commits audit/state/source linkage atomically. Actor self-triage/closure is
denied when the pinned policy requires a distinct reviewer; no broader person-level
SoD is implied. Tenant, membership, source project/site scope, consent and channel
permission deny by default.

## 4. Conceptual data and migration posture

Concepts: `NotificationPolicyVersion`, `NotificationPreference`,
`NotificationIntent`, `NotificationRecipientState`, `CalendarProjection`,
`SupportCase`, `SupportCaseEvent`, `DiagnosticConsent`, `SupportEvidencePin`,
`SupportAccessProposal`, `SlaPolicyVersion`, and `SupportEscalation`.
All are organization-scoped; source links retain type/public id/version/hash.
Published policy, sent/read state, closure and DMS pins are immutable. Migrations
must be expand-only and non-fabricating: no historical notices, read states,
consents, deliveries, SLA breaches, support cases, access grants, attachments or
calendar events may be inferred/backfilled.

Persian-first RTL/Jalali screens require readable source context, recipient/channel
state, consent warning, expiry, escalation and audit trail; sensitive diagnostics
and DMS evidence require distinct access permission and must not appear in exports
without explicit scope.

## 5. Product Owner decisions

| ID | Options | Recommend | Consequence | Sessions |
| --- | --- | --- | --- | --- |
| N01 | A tenant-local policy; B global policy | **A** | Preserves tenant autonomy/isolation. | S16–20 |
| N02 | A in-app first; B email first; C all channels | **A** | No provider dependency. | S16–17 |
| N03 | A consent per channel; B implied consent | **A** | Privacy fail-closed. | S16 |
| N04 | A source-linked immutable intent; B mutable message | **A** | Reproducible audit. | S16–17 |
| N05 | A no delivery claim without receipt; B optimistic sent | **A** | Prevents false assurance. | S17 |
| N06 | A no scheduler now; B synchronous reminders | **A** | Defers operational automation. | S17 |
| N07 | A cancel linked intent; B delete | **A** | Retains history. | S17 |
| N08 | A read-only calendar projection; B calendar authority | **A** | Avoids duplicate work facts. | S18 |
| N09 | A existing WorkItem authority; B support task engine | **A** | No parallel workflow. | S18–19 |
| N10 | A tenant-scoped support cases; B platform-global queue | **A** | Protects tenant privacy. | S19 |
| N11 | A explicit diagnostic consent/version; B implied diagnostics | **A** | Privacy/audit boundary. | S19 |
| N12 | A exact DMS pins; B copied attachments | **A** | DMS-only bytes/versions. | S19 |
| N13 | A proposal-only timed access; B direct grant | **A** | Authorization stays authoritative. | S19 |
| N14 | A versioned SLA policy; B editable SLA | **A** | Historical explainability. | S20 |
| N15 | A policy-pinned SoD; B universal separation | **A** | No unjustified stricter rule. | S19–20 |
| N16 | A scoped audit/export; B broad support export | **A** | Sensitive minimization. | S20 |
| N17 | A operation-key idempotency/locks; B best effort | **A** | Retry/race safety. | S16–20 |
| N18 | A proposal-only downstream effects; B automatic effects | **A** | Preserves domain authority. | S16–20 |

## 6. Validation and acceptance

Focused PostgreSQL tests must prove tenant/project/site isolation; permission,
consent and sensitive-diagnostic denial; valid transitions/SoD; immutable policy,
intent/read/closure/DMS history; source cancellation/replacement; deterministic
calendar projection; idempotency and concurrent stale-state rejection; proposals
cause no downstream mutation; RTL/Jalali navigation; and bounded migration
rollback/reapply. Django check, migration drift, targeted Ruff, template
compilation and diff hygiene are required. Broad suite is not required.

### 6.1 Product Owner acceptance evidence — 2026-10-06

- A single-runner empty PostgreSQL schema applied the complete repository graph,
  including `organizations.0103`, `support.0001` and `support.0002`.
- The resulting Support schema contained the five expected tables, 18 foreign
  keys, the four named uniqueness constraints, ordinary relation indexes and no
  persistent calendar table. All five Support record families contained zero
  inferred rows.
- `apps.support.test_p9_s16_s20`: **11 passed in 21.783s**. Coverage includes
  tenant/recipient isolation, permissions and platform-role default denial,
  notification deduplication/acknowledgement, derived calendar facts, assignment,
  lifecycle/stale-state/concurrency/idempotency, immutable event/evidence history,
  exact and sensitive DMS pins, independent time-bounded access approval/use/
  revocation, authoritative audit events, RTL/Jalali routes, and downstream
  no-effects.
- Dependency-safe rollback/reapply succeeded for `support.0001`–`0002` and
  `organizations.0103`. Reapply restored all five tables, the evidence
  relationships, 18 foreign keys, the named constraints and all 17 Support
  permissions. The 536 unrelated permission codes retained the same SHA-256
  catalogue digest; no historical Support or downstream facts were fabricated.
- Django system check, migration drift, targeted Ruff, both Support-template
  compilations, all 14 Support URL reversals/configuration loading and
  `git diff --check` passed. The broad application suite was intentionally not
  run and is not required for this bounded tranche.

The Product Owner accepts these validation results and the bounded corrective
work: active Tenant-member assignment enforcement, transition replay
idempotency, immutable case/evidence history, sensitive DMS evidence access,
independent support-access approval and stale support-access state protection.
This acceptance does not expand the authorized runtime.

## 7. Exact bounded runtime authorization wording

> Product Owner authorizes `P9-S16–S20` only after accepting N01–N18, solely for
> tenant-scoped in-app notification/support records, source-linked calendar
> projections, DMS version pins, consented diagnostics, policy-pinned controls,
> RTL UI, audit, expand-only migrations and source-only proposals. It does not
> authorize email/SMS/provider delivery, queues, schedulers, external integrations,
> offline/native clients, knowledge publication, production activation, direct
> support access grants, inferred historical data, or automatic downstream actions.
> Missing legal, channel, consent or technical rules fail closed.
