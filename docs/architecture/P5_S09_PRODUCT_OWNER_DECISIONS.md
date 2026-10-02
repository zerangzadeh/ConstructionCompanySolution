# P5-S09 Product Owner Decisions

**Prepared:** 2026-10-02

**Status:** P5-S09-D01 through P5-S09-D06 accepted by the Product Owner on
2026-10-02; implementation and acceptance evidence completed in P5-S09.

**Scope:** P5-S09 protected opening/reveal only. P5-S10+, comparison,
normalization, evaluation/scoring, award/No-Award, PO creation, portal/P5.2,
downstream handoffs and production activation remain unauthorized.

## Verified decision baseline

P5-D01 and P5-D02 already require protected, immutable, revision-specific opening
after the effective earliest-opening boundary; independent human approval; no
Owner/Admin/platform/support bypass; exact tenant/project/object scope; redacted
audit; and no access to withdrawn, superseded, late, quarantined or otherwise
ineligible revisions. P5-S07 supplies the immutable effective-revision manifest and
P5-S08 supplies immutable, hash-pinned, quarantined evidence. The Product Owner's
accepted dispositions below now resolve the bounded P5-S09 runtime choices without
granting commercial admissibility or any P5-S10+ capability.

P5-S09 implements the four default-ungranted capabilities, immutable package freeze,
request and independent approval/opening evidence, exact revision-scoped viewer
grants/revocations, package-wide CLEAN technical revalidation and synchronous exact-
version delivery. Business admissibility and break-glass remain absent.

## P5-S09-D01 — Protected-opening approval lifecycle

**Decision:** **A — ACCEPTED (2026-10-02).**

**Exact Product Owner question:** Which persisted lifecycle must satisfy P5-D01's
independent approval requirement before a quote revision becomes opened?

**Why required:** The accepted decision requires a distinct approving human and
says the operation remains pending when that actor is unavailable, but it does not
define whether approval and execution are two or three durable steps.

| Option | Practical implications and consequences |
| --- | --- |
| **A — Request then independent approval atomically opens (recommended)** | A holder of `rfq_quotes.open` creates an immutable pending request; a different actor holding a new default-ungranted `rfq_quotes.approve_open` capability approves it, and approval atomically creates the immutable opening event. Neither capability implies the other. This is the smallest workflow with explicit SoD, deterministic locking/idempotency and no approved-but-unexecuted gap. Audit retains requester, approver, timestamps, reason, target revision and evidence-set fingerprint. No generic Workflow dependency is required. |
| B — Synchronous dual-actor co-sign | One call supplies requester and approver. Simpler schema, but weak operational evidence, no durable pending state, awkward authentication/session handling and poor scalability for delayed approval. It conflicts with the accepted “remains pending” clarification. |
| C — Request, independent approval, then separate execution | Strongest three-person-capable ceremony, but creates an approved-pending-execution state, expiry/revocation questions, more recovery paths and a larger workflow/operations surface. |

**Security/confidentiality/SoD/audit:** A enforces requester ≠ approver inside the
locked transaction and grants neither actor content merely from participating.
Denied and conflicting actions remain redacted. Owner/Admin/platform identity is
irrelevant without explicit permission and object scope.

**Workflow/data/integration/scalability/operations:** A uses a Procurement-owned
bounded lifecycle rather than generic workflow mutation. It supports later UI or
workflow coordination without making Workflow authoritative. Unique request
idempotency and one immutable opening event per revision make concurrency tractable.
No downstream integration is activated.

**Dependencies:** P5-D01, P5-D02, P5-S07 effective manifest, P5-S08 evidence.

**Recommended safeguards/clarifications:** Add `rfq_quotes.approve_open` with no
default-role grant or identity bypass. Require a non-content reason code/text; lock
organization, memberships/scopes, RFQ/version/manifest/revision, request and evidence
set on approval; re-check earliest-opening time and technical eligibility; reject
self-approval and stale evidence fingerprints; never auto-grant viewing.

**Implemented scope:** Immutable opening request/event models, request/approve
services, direct requester/approver SoD, idempotency, concurrency and atomic rollback.

## P5-S09-D02 — Supplier-package completeness and freeze point

**Decision:** **A — ACCEPTED (2026-10-02).**

**Exact Product Owner question:** At what event does the P5-S08 evidence set become
complete and permanently closed to additional attachments for P5-S09 opening?

**Why required:** P5-S08 accepts evidence items independently and intentionally has
no package-finalization lifecycle. An immutable opening cannot safely identify “the
package” while attachments may still be accepted.

| Option | Practical implications and consequences |
| --- | --- |
| **A — Opening request freezes the current complete package (recommended)** | Creating the pending request requires exactly one original, snapshots every current attachment/version/hash, and permanently blocks later S08 custody for that revision. Approval revalidates the same fingerprint. This prevents approval drift and preserves a simple immutable chain. |
| B — Approval freezes the package | Attachments may arrive while approval is pending. Approval must detect/reject stale requests or silently change the reviewed set; only rejection is safe, creating more retries and operational ambiguity. |
| C — Add a separate package-finalization operation | Clearest explicit supplier-package lifecycle, but introduces another permission, actor, state and recovery process not described in accepted P5 decisions and expands P5-S09. |

**Security/confidentiality/SoD/audit:** A prevents evidence injection between request
and approval. The snapshot contains only technical identifiers/hashes in general
audit; filenames and content stay sealed.

**Workflow/data/integration/scalability/operations:** A needs an immutable opening-
request evidence manifest and a custody guard. It remains local and synchronous,
with bounded rows (maximum 21 items) and deterministic fingerprints.

**Dependencies:** P5-S08 item limits/idempotency and P5-S07 manifest immutability.

**Recommended safeguards/clarifications:** A request with no original fails; package
fingerprint includes ordered evidence IDs, types, slots, version IDs and canonical
hashes; cancellation/denial never reopens custody unless explicitly decided later.

**Implemented scope:** Immutable freeze/package-item schema and fingerprint,
post-request custody prohibition, stable reuse and stale-package/concurrency tests.

## P5-S09-D03 — Technical readiness versus business admissibility

**Decision:** **A — ACCEPTED (2026-10-02).**

**Exact Product Owner question:** Must P5-S09 decide commercial admissibility, or
does it only require package-wide clean technical processing before protected reveal?

**Why required:** Accepted text uses “eligible” and mentions P5-S09 admissibility,
but defines neither admissibility grounds/actors nor whether one unsafe or unknown
attachment blocks the whole revision.

| Option | Practical implications and consequences |
| --- | --- |
| **A — Package-wide clean technical gate; defer business admissibility (recommended)** | Every pinned item must have a latest authoritative CLEAN assessment matching its canonical hash. Opening asserts only technical readiness and effective/timely lineage. Qualification, responsiveness and commercial admissibility remain unreviewed for a later authorized slice. Safest bounded S09. |
| B — Add a separate post-reveal admissibility lifecycle in S09 | Requires admissibility permissions, reasons, states, reviewer SoD, correction/appeal semantics and rules for excluded evidence. It materially expands S09 but could prepare comparison sooner. |
| C — Allow partial/item-level opening when some attachments are non-clean | Improves availability but reveals an incomplete supplier assertion, complicates hashes and audit, and risks biased evaluation. |

**Security/confidentiality/SoD/audit:** A fails closed if any item is absent,
unknown, processing, unsafe, unsupported, error, hash-mismatched or missing in
storage. Scanner/platform roles still gain no reveal authority. No audit contains
extracted content.

**Workflow/data/integration/scalability/operations:** A reuses Documents processing
assessments without changing quarantine bytes or introducing malware infrastructure.
It requires no commercial policy engine or downstream integration.

**Dependencies:** P5-D02; P5-S08 canonical hashes, quarantine and processing history.

**Recommended safeguards/clarifications:** Treat CLEAN as technical evidence only;
re-read the latest assessment under lock; verify stored-byte presence/hash at open;
retain all prior assessments; never treat clean as supplier qualification or bid
responsiveness.

**Implemented scope:** Package-wide technical-readiness predicate and fail-closed
unsafe/unknown/hash/storage tests. Admissibility models and services remain excluded.

## P5-S09-D04 — Post-opening audience and access grants

**Decision:** **A — ACCEPTED (2026-10-02).**

**Exact Product Owner question:** After an opening event, who may read the revision's
commercial content, and which independently controlled capability may grant or
revoke that access?

**Why required:** Project scope plus a confidential-view permission can expose every
opened bid in a project. Accepted decisions require assigned/exact scope but do not
define an assignment record or whether project scope alone is sufficient.

| Option | Practical implications and consequences |
| --- | --- |
| **A — Explicit RFQ/revision viewer grant plus dedicated grant authority (recommended)** | A durable grant identifies membership, RFQ/revision, grantor, purpose and validity. Reading requires active membership, `rfq_quotes.view_confidential`, project scope, opened revision and active exact grant. Creating/revoking grants requires a new default-ungranted `rfq_quotes.manage_confidential_access` capability; the grantor cannot grant themselves. Strong least privilege and revocation evidence, with more administration. |
| B — Permission plus project scope grants all opened bids | Reuses current authorization only and scales operationally, but may expose unrelated suppliers/RFQs to broad project teams. |
| C — Opening participants automatically receive content access | Conflates custody/opening authority with ongoing visibility and contradicts the accepted responsibility separation. |

**Security/confidentiality/SoD/audit:** A separates open, approve and view authority;
grants cannot self-elevate; every successful and denied access is audited by neutral
evidence/version IDs. Evaluator assignment later can reuse—not replace—the grant.

**Workflow/data/integration/scalability/operations:** A adds a small tenant-scoped,
effective-dated access record and revocation path. It should not use workforce
positions as permission or create a generic ACL framework.

**Dependencies:** P5-D01/P5-D02, P1.1 membership/scope controls, opening lifecycle
decision P5-S09-D01.

**Recommended safeguards/clarifications:** Add
`rfq_quotes.manage_confidential_access` with no default-role or identity bypass; no
self-grant; exact RFQ/revision binding; expiry is optional only when explicitly
supplied; revocation never erases access history. Opening requester/approver status
alone never grants view or grant-management authority.

**Implemented scope:** Confidential-view authorization service, exact-revision grant
and append-only revocation, dedicated permission and tenant/object-scope tests.

## P5-S09-D05 — Permitted content-delivery mechanism

**Decision:** **A — ACCEPTED (2026-10-02).**

**Exact Product Owner question:** What content operation does
`rfq_quotes.view_confidential` authorize in P5-S09?

**Why required:** Human reveal requires a controlled byte-delivery boundary, while
P5-D02 separately names preview, download and export and P5-S09 has no UI scope.

| Option | Practical implications and consequences |
| --- | --- |
| **A — Exact-version authenticated streaming/download only (recommended)** | A service returns one pinned opened `DocumentVersion` after all quote-specific checks and audits the access. Supplier filename may appear only in the authorized response. No generic Documents route, bulk export, preview, derivative, OCR, cache or search. |
| B — Metadata reveal now; bytes in a later slice | Avoids delivery risk but does not provide meaningful human commercial-content reveal, so P5-S09 cannot meet its core outcome. |
| C — Preview/render/derivative plus download | Better usability but introduces file rendering, derivative custody, cache isolation and active-content defenses outside the current pre-production boundary. |

**Security/confidentiality/SoD/audit:** A must revalidate exact opening and viewer
authorization per access, use attachment-only/no-sniff responses, never publish a
storage URL, and audit success/denial without filename/content. CSV/Office bytes are
download-only and never executed or rendered by the application.

**Workflow/data/integration/scalability/operations:** A reuses protected storage and
does not require UI, object storage or background work. Every access is synchronous;
production serving capacity remains explicitly unapproved.

**Dependencies:** P5-S09-D01, D03 and D04; P5-S08 exact version/hash lineage.

**Recommended safeguards/clarifications:** No range/public URL unless separately
approved; no generic `documents.download`; neutral errors; stream only current pinned
bytes whose stored hash still matches; deny all unclean/unopened evidence.

**Implemented scope:** Synchronous exact-version byte delivery, sanitized filename
release point, attachment-only/no-sniff contract and successful/denied audit tests.

## P5-S09-D06 — Break-glass activation in this slice

**Decision:** **A — ACCEPTED (2026-10-02).**

**Exact Product Owner question:** Should P5-S09 implement operational break-glass
access now, or keep emergency reveal fail-closed until a later contract defines its
grant authority and duration?

**Why required:** P5-D01 accepts controlled break-glass in principle but does not
specify approver capability, maximum duration, renewal, revocation, notification or
incident-review requirements. Those are material security policy.

| Option | Practical implications and consequences |
| --- | --- |
| **A — Do not activate break-glass in P5-S09 (recommended)** | Implement only normal protected opening after other decisions are approved. Emergency attempts remain denied. A later bounded contract defines temporary access without weakening normal controls. |
| B — Implement four-hour emergency viewer grants now | Add a dedicated request/approval lifecycle under new default-ungranted `rfq_quotes.request_emergency_access` and `rfq_quotes.approve_emergency_access` capabilities. A different approver may grant read-only access to one opened revision for at most four hours; renewal is a new independently approved request. Require incident reason, immediate in-product audit flag, manual incident review and request-time expiry enforcement. No scheduler, notification provider or mutation authority is introduced. |
| C — Owner/Admin/support bypass | Rejected by P5-D01/P5-D02. |

**Security/confidentiality/SoD/audit:** A is fail-closed and creates no latent bypass.
B can be safe only after every parameter is approved and independently enforced.

**Workflow/data/integration/scalability/operations:** A has no operational support
surface. B adds on-call ownership, expiry enforcement and review obligations; a
scheduler remains unauthorized, so expiry would need request-time enforcement.

**Dependencies:** P5-D01, P1.1 protected authorization foundation, decisions D04/D05.

**Recommended safeguards/clarifications:** Choose A for P5-S09. Any later B must be
read-only, exact-revision scoped, independently approved, time-bound, reasoned,
audited and incapable of evaluation mutation or award authority.

**Excluded scope:** Every emergency/break-glass model, permission, grant, expiry,
notification and access path remains deliberately absent and fail-closed.

## Consolidated Recommended Disposition

| Decision | Accepted option | Disposition |
| --- | --- | --- |
| P5-S09-D01 — Approval lifecycle | A — Request then independent approval atomically opens | **Accepted** — durable pending request and two-person protected open |
| P5-S09-D02 — Package freeze | A — Freeze on opening request | **Accepted** — immutable evidence-set manifest; later custody blocked |
| P5-S09-D03 — Readiness/admissibility | A — Package-wide clean technical gate; defer business admissibility | **Accepted** — reveal remains technical, not evaluative |
| P5-S09-D04 — Audience | A — Exact viewer grant, dedicated grant authority, permission and project scope | **Accepted** — least-privilege post-open access |
| P5-S09-D05 — Delivery | A — Exact-version authenticated streaming/download only | **Accepted** — human reveal without generic DMS exposure or derivatives |
| P5-S09-D06 — Break-glass | A — Keep disabled in P5-S09 | **Accepted** — no emergency bypass until a later approved contract |

This accepted table authorizes only the listed P5-S09 runtime choices. It does not
authorize P5-S10+, comparison, normalization, evaluation/scoring, award/No-Award,
PO creation, portal/P5.2, downstream handoffs, production infrastructure or
activation.
