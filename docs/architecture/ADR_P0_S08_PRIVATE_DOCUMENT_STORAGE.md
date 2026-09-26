# ADR P0-S08: Private document storage, upload safety and evidence retention

**Status:** PROPOSED — preparation complete; acceptance and implementation pending.
**Recorded:** 2026-09-25. **Scope:** P0.1 storage ADR / PPC-05, informing P0.2,
P0.3 and P1.3. **Authorization:** Product Owner: “Continue and do S08”.

Storage is the next listed P0.1 ADR topic after project authorization in the
[Roadmap](../../ROADMAP.md) and [audit ADR register](PRODUCT_CAPABILITY_AND_READINESS_AUDIT.md#20-adr-candidates-and-product-owner-decisions).
This session prepares that proposal only. Provider selection, packages, production
configuration, data movement, scanning jobs and P1.3 implementation are excluded.
The separate DMS link-extensibility ADR/PPC-10 remains pending; this proposal
preserves existing link semantics without choosing its replacement schema.

## 1. Current evidence and limits

| Source | Verified behavior and limitation |
| --- | --- |
| [Models](../../apps/documents/models.py): `document_version_upload_path`, `Document`, `DocumentVersion` | Tenant/document paths use random version filenames. Versions retain original name, claimed content type, byte size, SHA-256 and uploader. Version numbers are unique per document. Instance save/delete guards protect versions; these are not storage immutability or a universal database deletion barrier. `Document.clean` requires the current version to be the latest. |
| [Services](../../apps/documents/services.py): `_validate_uploaded_file`, `_create_version`, `add_document_version` | Allows PDF/JPEG/PNG, checks extension, supplied MIME, non-empty size up to 10 MiB and magic prefix; computes SHA-256. Adds versions under a document row lock. These checks do not scan malware or prove complete content validity. File creation occurs within database-transaction services; no storage compensation/reconciliation protocol is present in these functions. |
| Services: `_validate_document_context_access`, `get_document_version_for_download`, `record_document_download`, `archive_document` | Requires document permission and view permission for every linked target, validates tenant context, resolves a version without returning a storage URL, audits downloads and archives without deleting versions/links/files. Normal document resolution excludes archived records. No retention/hold/export or scan-state lifecycle appears in the inspected document model/services. |
| [Views](../../apps/documents/views.py): `_download_response`, `document_download`, `document_version_download` | Streams a storage file as an attachment with `nosniff` after authorization/audit. The audit precedes file opening/streaming, so it is not proof of completed delivery. |
| [Base settings](../../config/settings/base.py), [production settings](../../config/settings/production.py), [URLs](../../config/urls.py) | Local `MEDIA_ROOT`/`MEDIA_URL`; no private object-storage backend configured in these settings. Debug mode adds direct media serving. Production sets DEBUG false; actual reverse-proxy/bucket access policy was not inspected or certified. An opaque path alone is not access control. |
| [Migration 0004](../../apps/documents/migrations/0004_document_documentlink_documentversion_and_more.py) | Creates the versioned document structures and deletes the historical `ProjectDocument` model; contains no `RunPython` data-copy operation. Existing history must remain unchanged. This does not prove whether any environment had legacy records or lost data. |

Inspected [test bodies](../../apps/documents/tests.py), not executed:
`test_new_version_is_numbered_immutable_and_becomes_current`,
`test_upload_validation_rejects_mismatched_type_and_signature`,
`test_document_access_requires_linked_context_permission`,
`test_download_audit_is_version_specific_and_rechecks_access`,
`test_archive_preserves_versions_and_links_and_removes_active_listing`,
`test_views_create_add_version_and_secure_download` and
`test_endpoints_reject_cross_tenant_document_uuid`. They evidence version guards,
validation, linked-context denial, audit, archive preservation and protected routes;
they do not certify scan/hold/export, object storage or recovery.

Narrow C2 inspection was necessary for current-version compatibility, debug-media
exposure and legacy migration lineage. No broad endpoint or infrastructure audit
was performed. Current behavior is unchanged, including authorization differences
recorded in the [S07 proposal](ADR_P0_S07_PROJECT_SITE_AUTHORIZATION.md).

## 2. Proposed ownership and storage contract

Follow the existing target [data authority](DATA_MODEL.md#9-evidence-documents-and-media):
DMS owns document/version metadata and the immutable original-byte identity;
business domains own their source lifecycle and explicit links. Platform operations
owns private storage configuration, credentials, backup and recovery. Tenant
governance owns approved retention/export policy; accountable approvers remain to
be named under Q03. Audit records actions, not job scheduling or byte storage.

Propose private managed object storage through Django's storage interface, subject
to D03 acceptance. Alternatives are an operated private object store or protected
filesystem; either must meet the same isolation, durability and recovery gates.
Do not choose a vendor, region, price or adapter here. Reuse a maintained storage
adapter and scanning capability after dependency/provider review and explicit
approval; do not implement a storage protocol, antivirus or cryptography.

- Original bytes have a unique non-overwriting key and verified hash/size tied to
  tenant/document/version. Never treat a key, public UUID or SHA-256 as authority.
  Avoid cross-tenant deduplication and existence disclosure in this proposal.
- Deny public/anonymous listing and reads at the storage layer. Isolate quarantine,
  released originals, derived artifacts and export bundles by access policy, not
  naming alone. Apply least-privilege service identities and approved encryption,
  key recovery and rotation policies; secrets stay outside source/logs.
- Keep authorization in the application: active tenant context, document and all
  linked-source permissions, accepted project/site scope and applicable lifecycle
  policy. No support or privileged exception is granted by storage credentials.
- Prefer authorized application streaming initially to preserve the current
  download boundary. A future expiring signed URL needs explicit approval of its
  bearer-link lifetime and revocation exposure; it must never become a permanent
  metadata URL. Proxy/cache behavior must prevent reuse across users/tenants.
- Bind previews, OCR text, thumbnails, search and signature evidence to the exact
  source version/hash and processing provenance. Derivatives inherit restrictions
  and cannot bypass quarantine, hold, scope or retention. No OCR/signature service
  is selected, and a hash alone is not a legally trusted signature.

## 3. Proposed upload and availability lifecycle

Separate immutable version identity from append-only processing assessments and
current availability. Proposed states: receiving -> quarantined -> available,
rejected or processing-failed; retry appends a new assessment. Missing/timeout/error
scan results never mean clean. A later adverse assessment blocks delivery without
rewriting original bytes, prior verdicts or business history.

1. Authenticate and check upload authority, linked context and approved capacity
   rules before accepting bytes. Enforce bounded streaming and file-type/content
   checks; upload permission cannot grant access to another tenant's target.
2. Stage bytes privately under a tenant-bound upload identity. Record actual byte
   count/hash and durable receipt. Quarantine is unreadable through ordinary
   download, preview, OCR, search and export paths.
3. Use a reviewed scanner/content-validation pipeline with restricted privileges,
   resource limits and approved data residency. Retain engine/rule version,
   timestamp, input hash, verdict and error provenance. Unsafe or unsupported
   content fails closed; no user override makes unscanned bytes available.
4. Atomically register the version/assessment/link evidence or finalize an existing
   staged record, rechecking authority and state. Verify storage integrity before
   publishing availability. Retry by stable tenant/upload identity; conflicting
   bytes under the same request must fail, not create a second logical version.
5. Treat database/storage failures as separate outcomes: byte upload followed by
   DB failure leaves a tracked reconciliation candidate; DB metadata with missing
   or mismatched bytes remains unavailable and alerts operations. A reviewed,
   idempotent reconciler retries or disposes only demonstrably unreferenced staged
   objects after hold/retention checks. Never bulk-delete “orphans” by age alone.

The current latest-version requirement prevents silently pointing `current_version`
back to the previous clean version after adding a quarantined version. Proposed
compatibility option: preserve latest identity and track deliverability separately;
default latest download reports unavailable, while explicitly authorized older
available versions remain selectable. An alternative is a separately designed
staging record that creates the version only after release. Acceptance must choose
one and test numbering, concurrent upload, rejection and domain-link semantics;
neither is implemented or accepted here. Never silently serve old bytes as latest.

Future asynchronous scanning needs durable retry/idempotency and an after-commit
dispatch/recovery contract with the separate async/outbox ADR. This is a boundary
requirement, not permission to add Celery/Redis, a queue or a second workflow engine.
Manual review decisions, where required, must use existing registered workflow
services and business permissions rather than treating scan jobs as approvals.

## 4. Retention, legal hold, export and disposal

| Operation | Proposed rule and evidence |
| --- | --- |
| Archive | Preserve current archive semantics and all original versions/links. Archive is neither deletion nor retention expiry; routine visibility remains governed separately. |
| Retention | Classify evidence under an approved versioned policy with trigger date, scope, rule source and responsible approver. No duration is invented. Unknown/conflicting requirements block destructive disposition until reviewed. Include originals, derivatives, export copies and backups. |
| Legal hold | Explicit tenant/object scope, issuer authority, reason, effective time and release evidence. An active hold blocks disposal regardless of expiry, cancellation or quota; releasing a hold does not itself authorize deletion. Hold placement and disposal serialize against the same disposition state. |
| Export | Dedicated authority; explicit purpose, tenant/scope, cutoff and version manifest containing hashes, sizes, links and policy/processing provenance. Recheck access at request, generation and delivery; changed authority invalidates or rebuilds the bundle. Protected temporary bundles expire under approved policy, never public URLs. |
| Quarantined or missing export evidence | Include safe manifest status and explicit completeness failure; do not silently omit or deliver unsafe bytes. Any forensic transfer needs separately approved handling and authority; none is granted here. |
| Offboarding | Suspended/cancelled tenants do not acquire ordinary access. Any retained export path depends on the tenant-lifecycle ADR, Q03 and D05, with its own authority. Cancellation is not a deletion instruction. |
| Disposal | After approved retention and absence of holds, validate authority/reason and exact objects transactionally, record authorized intent, then idempotently delete permitted storage copies and record results. Partial failure remains pending and blocks a false completion claim. Retain permitted minimal audit/tombstone evidence under its own policy. |

The disposition design must define the irreversible cutoff, hold-versus-delete
ordering and recovery from external deletion failure. Backup copies expire under
approved schedules; do not promise immediate erasure from immutable backups.
Restores must replay disposition/hold evidence before normal access so deleted or
restricted data is not silently republished. Provider retention locks must be
evaluated against Q03 before enabling settings that cannot be reversed.

Exporting documents is one part of a complete tenant export, not a substitute for
relational business history. Multi-context documents retain all linked-context
checks; ordinary readers cannot obtain a wider export through storage tooling.
Policy administration, hold/release, export and disposal need separately approved
permissions, registry/catalog/default-role migrations and separation tests when
implemented. No permission code or role grant is added by this proposal.

## 5. Migration, recovery and operational acceptance

1. Inventory each environment's document/version/link rows and actual file keys,
   including archived versions, missing bytes, duplicates and historical storage.
   Investigate migration 0004's legacy lineage against environment evidence; do
   not assume empty legacy tables, reconstruct missing metadata without provenance
   or rewrite/delete historical migrations.
2. Choose approved provider/location, operators, scanning and retention policies.
   Expand metadata for storage location/processing evidence only under an approved
   package. Preserve UUIDs, version numbers, original filenames, hashes, uploader,
   timestamps, links and audit. Legacy “not assessed” never becomes “scan passed”.
3. Copy through a tenant/version manifest to private non-overwriting objects;
   verify original-byte hash/size, counts, link parity and authorized downloads.
   Retain source storage. Use a reviewed write freeze or tracked incremental-copy
   protocol so uploads during migration cannot be lost or pointed at stale bytes.
4. Rehearse coordinated DB, blob, policy/hold/audit and credential/key recovery at
   a defined consistent boundary. Reconcile every referenced version to verified
   bytes and classify orphan/missing entries. Restore in isolation, then reapply
   access restrictions and disposition evidence before reopening service.
5. Switch only after manifests, scan treatment, access isolation and rollback pass.
   Rollback must account for writes after cutover and preserve quarantine/hold
   state; it cannot restore a public path or unreviewed legacy availability.
   Source deletion/compatibility contraction requires separate explicit approval.

RPO/RTO remain D04 decisions, not inferred values. Backup success, storage versioning
and a correct hash are each insufficient proof of recoverability. P0.2/P10.3 must
produce timed restore evidence against accepted targets and named ownership.
Monitoring needs missing/corrupt objects, scan failures/backlog, retry/disposal
failures, unauthorized access and export failures without file contents, bearer
links, credentials or unnecessary personal filenames in logs.

## 6. Decision register and static acceptance cases

| Gate / accountable decision | Unresolved requirement |
| --- | --- |
| D03 / Product Owner and named operations/security owner | Locations for originals/quarantine/derivatives/scanner processing/backups/exports/logs, provider, operators, access jurisdictions and budget before storage implementation or data placement. |
| D04 / Product Owner and recovery owner | Numeric loss/outage targets, coherent recovery boundary, backup/key ownership and rehearsal criteria before recovery commitments. |
| Q03 / Product Owner to name evidence/legal approver | Retention triggers/durations, holds/release/disposal authority, export completeness/format and signature/evidence standards before design acceptance. No legal compliance is certified. |
| Q04 / scope and security/workflow reviewer | Apply recorded A1/B1/C1/D1/E1, revised F2, final G3 — Revised with Protected Operations, and H1; no mechanism is implemented by the selection. Review linked-context access, download/export revocation, emergency scope, Protected Operations classification and auditable business Self-Approval risk. Reviewer names/evidence remain OPEN. |
| D05 / commercial and tenant-lifecycle owner | Which staged/version/derivative/export bytes count toward storage, reservation/release and warning/cap policy. Holds cannot be evaded by quota enforcement. Values and cancellation/export policy remain open. |
| Storage implementation review | Choose staging-versus-latest availability model, delivery mechanism, scanner failure/retry policy, migration/rollback protocol and dependency approval. Async and DMS-link ADRs remain separate. |

These are static design scenarios, **not executed tests**:

| Case | Proposed expected result |
| --- | --- |
| Anonymous raw key, debug media route or foreign-tenant version | Production raw storage denies access; application returns no unauthorized bytes or metadata. |
| Document permission without one linked-source scope | Deny download, preview, search result and export of that document. |
| Valid magic prefix but malicious/unknown scan result | Quarantine or reject; never equate prefix/hash validation with scan success. |
| Scanner outage, duplicate retry or changed bytes under retry key | Fail closed, preserve provenance; idempotent same-input result, explicit conflicting-input failure. |
| New quarantined version after available version | Latest identity remains truthful; explicit older-version access only under accepted availability policy. |
| Blob succeeds/DB fails, or referenced blob disappears | Reconcile tracked state; no phantom availability or unreviewed cleanup. |
| Retention expiry races with hold placement | Serialize disposition decision; effective hold blocks deletion, outcomes retain audit. |
| Cancellation or full quota with held evidence | Preserve held history; no automatic destructive cleanup or ordinary access bypass. |
| Export scope revoked after request; bundle incomplete | Recheck and block/rebuild delivery; report completeness without leaking protected metadata. |
| Migration or restore hash mismatch/post-cutover write | Block cutover/reopening for affected evidence and reconcile; no source deletion or silent loss. |

Implementation acceptance additionally requires protected storage configuration
tests, service/route authorization parity, hold/disposal race tests, failure
injection, representative upload/export limits and a restore/rollback exercise.
This ADR neither completes PPC-05/P0.1 nor authorizes P0.2/P0.3/P1.3 implementation.
