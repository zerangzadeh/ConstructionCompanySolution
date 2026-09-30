# P1-S19–S22 Product Owner decision packet

**Prepared:** 2026-09-29  
**Decided:** 2026-09-29; recorded/implemented through P1-S22 on 2026-09-30  
**Status:** DECIDED — D19-01..D19-10 accepted as recorded below

## Decision record

The Product Owner selected `D19-01=A`, `D19-02=A`, `D19-03=A`, `D19-04=A/A1`,
`D19-05=C`, `D19-06=A`, `D19-07=A/A1`, `D19-08=A`, `D19-09=A` and
`D19-10=A` for P1. Platform Operations owns storage/recovery execution; Platform
Security owns key custody; a separately assigned Restore Evidence Approver owns
restore-evidence approval. Tenant lifecycle authority uses dedicated Tenant RBAC,
Tenant Owner policy approval and distinct memberships for hold release/disposal
review. The protected filesystem is a P1 adapter only and is **not production
storage readiness**.

Still deferred without invented values: legal/contractual retention durations,
destructive disposal, legally certified signature standards, numeric RPO/RTO,
quota/commercial values, production object-storage provider/region, production
scanner/OCR provider, asynchronous transport and access-releasing link correction.

## 1. Purpose and fixed boundaries

This packet contains only the minimum decisions needed to turn P1-S19 through
P1-S22 into executable DMS sessions. It reconciles the current Roadmap, execution
playbook, proposed S08/S09 ADRs and the open Q03/D03-D05 inputs.

The following boundaries are already fixed and are not reopened:

- DMS remains the sole `Document`/`DocumentVersion` and byte authority; business
  domains retain target lifecycle and business-evidence authority.
- Storage credentials never grant Tenant business-data access. Every read, search,
  preview, export and mutation requires the active Tenant plus authority over every
  governing linked context.
- Original versions, hashes and link lineage are preserved. No silent retargeting,
  destructive history rewrite, cross-Tenant deduplication, `GenericForeignKey`,
  public storage URL, custom cryptography or legal-signature claim is authorized.
- Unknown retention obligations and unscanned/unknown content fail closed.

Selections may be recorded as `D19-01=A`, for example. Any revision must state the
replacement boundary explicitly.

## 2. Decided alternatives and consequences

### D19-01 — Disposition of S08 private-storage ADR

**Exact decision:** accept S08 as the target storage/upload/retention architecture,
accept it with stated revisions, or defer it.

| Option | Architectural consequence |
| --- | --- |
| **A — Accept S08 with D19-03 through D19-08 supplying its open parameters** | Establishes private storage, immutable byte identity, quarantine, append-only processing evidence, hold-aware disposition and manifest-based recovery as the implementation contract. |
| B — Accept with revisions | Executable only if every changed ownership, state, availability, retention or recovery rule is written into the decision. |
| C — Defer/reject | S19-S22 remain blocked because storage, scan state and retention semantics have no accepted authority. |

**Recommended default:** **A**. S08 preserves existing version/hash evidence and
fails closed without selecting a vendor or inventing law.

**Unlocks:** storage/processing schema and service design across S19-S22.

### D19-02 — Disposition and ownership model of S09 links

**Exact decision:** accept the link authority and select the physical ownership
pattern.

| Option | Architectural consequence |
| --- | --- |
| **A — Domain-owned typed link tables plus a platform-owned closed adapter registry** | Each domain owns its real target FK and scope/lifecycle adapter; DMS coordinates complete-context queries. Scales without central nullable-FK growth, but requires registry validation and union/query planning. |
| B — DMS-owned typed link tables plus the same closed registry | Retains real FKs and centralized DMS schema ownership, but DMS absorbs target dependencies and migration coordination. |
| C — Keep widening the current nullable-FK table for S19-S22 | Lowest immediate migration cost but preserves the scalability/dependency defect; suitable only as an explicitly temporary compatibility decision with a later migration gate. |

`GenericForeignKey` and arbitrary model-path dispatch remain prohibited under all
options.

**Recommended default:** **A**, matching the accepted domain-ownership direction:
business domains own relationships to their records; DMS owns documents/versions.

**Unlocks:** S09 acceptance, typed-link expansion/backfill contract and S20 link
implementation. Link correction may still be deferred under D19-09.

### D19-03 — Document numbering authority

**Exact decision:** choose the durable identifier contract for new documents.

| Option | Architectural consequence |
| --- | --- |
| **A — Immutable generated Tenant sequence using `OrganizationSettings.document_code_prefix`, plus optional external reference** | Adds a collision-safe internal business number while preserving supplier/contract references separately. Prefix changes affect only future allocations. |
| B — Tenant-entered reference is the only business number | Avoids an allocator but cannot guarantee completeness or collision-free numbering without stronger manual controls. |
| C — Per-project sequences | Improves local familiarity but adds project scope, concurrency and cross-project lookup complexity and does not cover non-project documents cleanly. |

**Recommended default:** **A** because the authoritative prefix already exists and
the model must support both internal identity and external references.

**Unlocks:** S19 numbering migration, allocation service and concurrency tests.

### D19-04 — Classification, confidentiality and access expiry

**Exact decision:** choose who owns classification vocabulary and whether
classification may independently restrict access.

| Option | Architectural consequence |
| --- | --- |
| **A — Platform-owned closed confidentiality levels; Tenant-owned descriptive categories; expiry only narrows access** | Stable security semantics and auditable Tenant taxonomy. A stricter level/expired grant can deny access but never override linked-context denial. |
| B — Fully Tenant-defined confidentiality levels | More flexible but requires versioned semantics, migration mapping and safeguards against weakening; materially larger governance surface. |
| C — Descriptive classification only in P1; confidentiality/expiry deferred | S19 classification can proceed, but S20 security acceptance cannot complete. |

**Recommended default:** **A**. Security meaning should not vary silently by Tenant;
Tenant categories can remain flexible without granting access.

For Option A, select the initial ordered codes:

| Sub-option | Consequence |
| --- | --- |
| **A1 — `internal`, `confidential`, `restricted`** | All content remains private; levels express increasing access restriction without implying anonymous publication. |
| A2 — `standard`, `sensitive`, `highly_restricted` | More neutral labels, but less familiar to document-control users. |
| A3 — Supply a different closed ordered list | Must define stable English codes, Persian labels and strictness order before S20. |

**Recommended level set:** **A1**, because it is compact and does not confuse
classification with public storage.

**Unlocks:** S19 classification and S20 confidentiality/expiry enforcement.

### D19-05 — Storage location and storage-operator ownership (D03)

**Exact decision:** select the production storage class/location and name the
operational owner permitted to administer it.

| Option | Architectural consequence |
| --- | --- |
| **A — Managed private object storage in a Product Owner-approved jurisdiction; Platform Operations owns configuration/credentials** | Best fit for immutable keys, lifecycle controls and scale; requires the actual provider/region and access jurisdiction to be named before data placement. |
| B — Operated private object store in an approved environment; Platform Operations owns it** | More infrastructure control and operational burden; the same isolation, backup, key and recovery evidence is required. |
| C — Protected filesystem retained for P1 only** | Allows local implementation with application streaming, but cannot satisfy production P0.2/P1 acceptance without documented isolation, backups and recovery; later migration is mandatory. |

**Recommended default:** **A**, provided the Product Owner supplies the actual
provider, region/jurisdiction, backup/export/log locations and named operations/
security owner. No support role gains business-data access.

**Unlocks:** storage adapter/configuration, placement metadata and migration plan.

**Safely deferrable beyond S22:** vendor price negotiation, provided provider,
region and operator authority are already fixed for the implemented environment.

### D19-06 — Import, quarantine, scanning and availability boundary

**Exact decision:** choose when a `DocumentVersion` becomes the latest immutable
identity and how scan uncertainty affects availability.

| Option | Architectural consequence |
| --- | --- |
| **A — Create the version on durable receipt; keep latest identity truthful; availability is a separate append-only assessment** | Quarantined/failed latest versions remain visible as unavailable; authorized users may explicitly select an older available version. Strongest provenance and recommended S08 compatibility path. |
| B — Use a staging record; create the version only after successful scan** | Simpler available-version list but requires separate staged identity, retry and orphan reconciliation; rejected attempts are not document versions. |
| C — Synchronous scan before accepting upload** | Simple state machine but couples requests to scanner availability/limits and is unsuitable for larger files or outages. |

**Recommended default:** **A**. It preserves every accepted receipt and never lies
about the latest version. Unknown, timeout, unsupported or failed scans remain
unavailable; users cannot override them.

**Required operational selection:** approve a maintained scanner/import adapter and
its permitted processing location before real scanning. A fake “clean” default is
not permitted.

**Unlocks:** S20/S21 processing states, immutable assessment provenance, retry and
failure tests.

**Safely deferrable beyond S22:** asynchronous transport technology and OCR vendor;
S22 may use a synchronous adapter boundary/test double, but cannot mark unscanned
production files clean.

### D19-07 — Retention, hold, disposal and export authority (Q03)

**Exact decision:** approve the lifecycle structure and identify who may classify,
hold/release, export and dispose of evidence.

| Option | Architectural consequence |
| --- | --- |
| **A — Versioned Tenant retention policy; dedicated hold/export/disposal permissions; hold and disposal are Protected Operations** | Records trigger, source, scope and approver; active/unknown/conflicting obligations block disposal. Export uses a hash/size/version/link/provenance manifest and reports incomplete evidence. |
| B — Platform-wide fixed retention rules | Easier operation but cannot safely represent Tenant/contract/legal variation without authoritative universal durations. |
| C — Preserve indefinitely; export and disposal deferred | Safe from accidental destruction and sufficient for non-destructive DMS work, but S22 retention/export acceptance remains incomplete. |

**Recommended default:** **A for the structure**, with actual legal/contractual
durations left unset until authoritative sources are supplied. Unknown duration
means “not disposable”, never zero retention. Tenant governance owns policy
selection; hold release does not itself authorize disposal; disposal requires a
separate authorized intent and reason.

**Required Product Owner assignment:** name the accountable Tenant role(s) for
policy classification and export, and the independent approver(s) for hold release
and disposal. Existing Protected Operations self-approval prohibition remains.

| Authority sub-option | Consequence |
| --- | --- |
| **A1 — Dedicated business permissions assigned through the existing Tenant role catalogue; Tenant Owner approves policy, two distinct authorized Tenant memberships control hold release/disposal** | Avoids inventing a mandatory job title, works for small/large Tenants and keeps Platform Admin outside Tenant data. |
| A2 — Tenant Owner alone controls every lifecycle action | Operationally simple but violates the accepted Protected Operations self-approval boundary for destructive release/disposal. |
| A3 — Platform Admin approves Tenant disposal | Creates a control-plane path into Tenant business evidence and conflicts with the no-automatic-access boundary. |

**Recommended authority:** **A1**. Export may use its own dedicated permission
without dual approval; hold release and disposal remain protected, separate actions.

**Unlocks:** S22 retention/hold/export/disposition models and non-destructive tests.

**Safely deferrable beyond S22:** jurisdiction-specific duration values, destructive
disposal activation and legally certified signature standards. S22 can complete the
fail-closed lifecycle while disposal remains disabled.

### D19-08 — Recovery boundary and storage accounting (D04/D05)

**Exact decision:** approve the recovery unit/owners and the byte categories that
must be measured now.

| Option | Architectural consequence |
| --- | --- |
| **A — Recover DB, blobs, policy/hold/audit and keys as one reconciled boundary; measure originals, quarantine, derivatives and export bundles separately per Tenant** | Enables manifests, orphan/missing reconciliation and future quota policy without allowing quota to delete or bypass held evidence. |
| B — Recover DB and blobs independently; measure only available originals | Simpler metrics but permits inconsistent restores and hides quarantine/derivative/export cost; not suitable for S08 acceptance. |
| C — Defer recovery/accounting metadata** | Blocks storage cutover, restore validation and S22 operational acceptance. |

**Recommended default:** **A**. Name the recovery owner, storage/key owner and
restore-evidence approver. Held evidence continues to count for reporting but caps
must not delete it or block protected completion.

**Unlocks:** storage manifests, reconciliation states, restore rehearsal contract
and future quota metrics.

**Safely deferrable beyond S22:** numeric RPO/RTO, quota/cap values, warning prices,
overage billing and commercial operator—provided S22 makes no production-readiness
or commercial-enforcement claim.

### D19-09 — Link creation, correction and access-release authority

**Exact decision:** approve who may create links and whether correction can remove
a historical link from the governing access set.

| Option | Architectural consequence |
| --- | --- |
| **A — Existing document-link permission plus target authority may append; corrections are append-only and the full retained link set continues to govern access** | No correction can widen access in S22. Wrong links remain a governed recovery issue. Lowest privilege-escalation risk. |
| B — Add a dedicated correction permission with independent approval; approved supersession may change the governing access set** | More operationally usable but requires separation, race control, protected audit and an explicit safe-presentation rule. |
| C — Owning domain may retarget/delete its link | Weakens evidence lineage and may silently widen access; incompatible with S09 and not recommended. |

**Recommended default:** **A for S19-S22**. Defer access-releasing correction until
there is demonstrated operational need and a separately approved workflow.

**Unlocks:** append-only typed link creation/backfill and complete-context access
tests. **Safely deferrable beyond S22:** access-releasing correction behavior.

### D19-10 — Permission-scoped search and OCR boundary

**Exact decision:** select the initial search authority and index location.

| Option | Architectural consequence |
| --- | --- |
| **A — PostgreSQL metadata/full-text index for available-version derived text; authorize every result against all live links before exposure** | Uses the existing stack and Tenant scope; OCR text is version/hash-bound derived evidence, never authority. Requires query-plan and no-leak tests. |
| B — External search service** | Better future scale/features but introduces provider, residency, deletion, reindex and credential decisions under D03/Q03. |
| C — Metadata-only search; OCR/full text deferred | S21 can improve metadata discovery but cannot satisfy the roadmap full-text outcome. |

**Recommended default:** **A** for P1. It minimizes dependencies and keeps final
authorization in the application/database rather than the index.

**Unlocks:** S21 permission-scoped search and immutable OCR/processing provenance.

**Safely deferrable beyond S22:** OCR provider and advanced linguistic/ranking
features; imported OCR text must remain unavailable until its source/version and
processing provenance are validated.

## 3. Minimum approval set and resulting execution order

To begin **P1-S19**, decide D19-01 through D19-04 and select S09 ownership in
D19-02. To proceed through **S20-S22**, also decide D19-05 through D19-10, including
the named owners requested in D19-05, D19-07 and D19-08.

After those decisions the smallest coherent order is:

1. **S19:** immutable numbering plus classification/confidentiality foundations;
2. **S20:** accepted typed-link registry/expand-backfill and complete-context access;
3. **S21:** receipt/quarantine/assessment provenance and permission-scoped search;
4. **S22:** retention/hold/export/reconciliation contract and bounded P1.3 closeout.

Actual retention durations, destructive disposal activation, legal signature effect,
numeric RPO/RTO, commercial quota values, asynchronous transport, OCR vendor and
access-releasing link correction may be deferred as stated above. Their absence
must remain explicit and fail closed; it must not be represented as production
certification.
