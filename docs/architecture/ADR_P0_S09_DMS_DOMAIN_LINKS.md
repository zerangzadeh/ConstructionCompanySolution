# ADR P0-S09: Extensible explicit DMS domain links

**Status:** PROPOSED — preparation complete; acceptance and implementation pending.
**Recorded:** 2026-09-25. **Scope:** P0.1 / PPC-10, informing P1.3.
**Authorization:** Product Owner: “continue and do S09”, continuing the
[S08 handoff](../ROADMAP_EXECUTION_PLAYBOOK.md#33-p0-s08-private-document-storage-adr-proposal-and-s09-handoff).

Prepare link ownership, alternatives, authorization and preservation rules within
[Roadmap P0.1/P1.3](../../ROADMAP.md). Do not change the six-target schema, implement
P1.3, introduce GenericForeignKey, relax all-linked-context access or invent
privileged/support exceptions. Storage and object scope remain governed by the
proposed [S08 storage ADR](ADR_P0_S08_PRIVATE_DOCUMENT_STORAGE.md) and
[S07 authorization ADR](ADR_P0_S07_PROJECT_SITE_AUTHORIZATION.md), neither accepted
by this session. DMS numbering, OCR, signatures and search implementation are out
of scope; their link-consumption requirements are considered only where necessary.

## 1. Verified current link contract

| Evidence | Current behavior and limit |
| --- | --- |
| [Models](../../apps/documents/models.py): `DOCUMENT_LINK_TARGET_FIELDS`, `DocumentLink` | One table has six nullable target FKs: project, contract, estimate, expense, payment and daily report. A database check requires exactly one target; six conditional constraints enforce document/target uniqueness. Target deletion uses PROTECT; document/organization FKs use CASCADE. `clean` checks related organizations. A FK to a target alone does not establish same-tenant equality. |
| Model lifecycle and [Django Admin](../../apps/documents/admin.py): `ImmutableAdminMixin`, `DocumentLinkAdmin` | Link instance deletion is blocked and Django Admin disables add/change/delete. Unlike `DocumentVersion.save`, `DocumentLink.save` validates but has no existing-row update guard. Intended link history is not a proven universal immutability barrier; this session adds no enforcement. |
| [Services](../../apps/documents/services.py): `TARGET_MODELS`, `TARGET_VIEW_PERMISSIONS`, `_target_field`, `_validate_target_access` | Explicit type/permission maps resolve a supported target, check tenant, linked project soft deletion and target view permission. They do not enforce one common project across all links. No per-user project/site grant layer exists here. |
| Services: `_validate_document_context_access`, `add_document_link` | Existing document access requires permission for every linked context. Adding a link locks the document, checks upload authority/current contexts, rejects archived documents, validates the new target and appends a link plus audit atomically. This is not a service for editing/removing historical links. |
| Services: `get_organization_documents`, `get_organization_document` | Listing excludes documents linked to target types whose view permission is missing. It does not call the per-target validator or reproduce its deleted-project check. Detail uses the complete context validator. Therefore list/detail parity for lifecycle and future object scope remains an acceptance gap. |
| [Forms](../../apps/documents/forms.py): `TARGET_FIELDS`, `TARGET_PERMISSIONS`, `DocumentTargetForm` | Separate six-target maps; tenant/project-lifecycle filtering and type view permissions, duplicate-target exclusion for existing documents, exactly-one selection. A form choice remains input, not service authorization. |
| [List](../../templates/documents/list.html) / [detail](../../templates/documents/detail.html) templates | Render `document.links.all`, `link.target` and target type. Future projections must preserve authorized labels and avoid disclosing denied context through lists, counts or labels. |

Inspected [test bodies](../../apps/documents/tests.py), not executed:
`test_document_link_requires_exactly_one_same_tenant_target` checks zero/multiple
targets, a bulk-created zero-target database failure and cross-tenant service denial;
`test_add_link_supports_an_existing_financial_entity_and_audits` checks a Payment
link and audit; `test_document_access_requires_linked_context_permission` checks
list/detail/form denial without the linked permission;
`test_archive_preserves_versions_and_links_and_removes_active_listing` checks
preserved versions/links; `test_endpoints_reject_cross_tenant_document_uuid` checks
foreign-document route denial. These are not exhaustive six-target, multi-project,
mutation, concurrency or bulk tenant-integrity tests.

The update guard and list/detail differences triggered narrow C2 reads of model,
Django Admin and list/template consumers. The current links refer to a Document, not a
particular DocumentVersion or target revision. A link is not evidence of which
bytes were approved. No database or live deployment was inspected.

## 2. Alternatives and proposed ownership

| Option | Benefit / cost | Disposition |
| --- | --- | --- |
| Keep expanding the nullable-FK table | Preserves a single query surface and explicit FKs; every new target widens constraints, maps, forms and dependencies in DMS. | Compatibility baseline; not preferred for the growing target model. |
| Domain-owned typed link tables plus a platform-owned adapter registry | Real FK per target type; owning domain supplies its scope/lifecycle rules; no central table expansion for each target. Needs complete enumeration and query planning across registered link types. | Recommended proposal, pending acceptance. |
| DMS-owned typed tables behind the same registry | Keeps schema stewardship centralized and retains real FKs, but DMS still absorbs target-specific dependencies and migration coordination. | Viable alternative if ownership/coordination is accepted explicitly. |
| GenericForeignKey or arbitrary model-name/UUID dispatch | Weakens explicit referential/lifecycle ownership and allows uncontrolled target resolution. | Excluded. A registry is not permission to create an untyped foreign key. |

DMS remains the sole Document/DocumentVersion and byte authority, as specified in
the [Data Model](DATA_MODEL.md#9-evidence-documents-and-media). The business domain
owns target identity, hierarchy, lifecycle and any approved evidence binding.
Organizations authorization owns capabilities and accepted object scope. The
platform owns the closed registry and DMS coordination/query contract. A new link
type does not authorize a new business domain or replicate file storage.

In the recommended design, each typed table holds a real document FK, a real FK
to its concrete target, tenant, stable link UUID, creation time/actor and lineage.
Use string model references and startup registration to keep dependency direction
explicit; DMS must not import every target's business services during model loading.
Adapters supply scoped queries/services; no signals synchronize critical state.
Exact schema/module locations require the approved P1.3 package.

Each platform registration must define a stable type key, owning domain, typed
table/target identity, scoped selector, read and link-command authorization,
project/site resolution, lifecycle/archive behavior, safe display/link projection,
version-binding rules, migration mapping and retention/export dependencies.
Registration is code-reviewed and validated at startup; no tenant Python, model
paths, callbacks or executable expressions. Incomplete/unknown registrations fail
closed. A retired domain must retain read/history/authorization support for stored
links; silently omitting its table would relax every-context authorization.

## 3. Relationship, version and authorization invariants

- Document, link, concrete target and any pinned version/revision belong to the
  same tenant. Resolve the organization through authenticated membership/session,
  never a posted organization ID. Validate target project/site hierarchy from
  authoritative rows. Null project does not grant broad access.
- One typed link has exactly one concrete target. Preserve current uniqueness of
  document/target during compatibility; any future purpose/version multiplicity
  needs an explicit business key and migration decision. Database constraints
  cover uniqueness/referential checks where possible; cross-table tenant equality
  needs a specified service and database enforcement strategy, including bulk paths.
- Do not introduce an implicit same-project requirement for all legacy links:
  current validation allows different projects within a tenant. Preserve those
  relationships and require authority for every context. Future domain commands
  that require one project must reject incompatible links explicitly; quarantine
  ambiguous migration cases rather than reparenting evidence.
- Context links continue to reference the document and its history. Finalized
  business decisions that need evidence must separately pin the exact document
  version/hash and target revision/action, under an approved domain contract.
  A new file version never rewrites that binding. Do not infer historic approval
  of the current/latest bytes from an existing document-only link.
- A link never grants permission or creates a second workflow authority. Read,
  download, version-add, link-add and archive require the relevant document
  capability and all linked-source authority. Future dedicated link/correction
  permissions require the existing catalog/registry/default-role migration and
  negative tests; no new grants are created here.

For lists, search, selectors, counts, previews, workbench links and exports, enforce
the same complete context set before pagination, aggregation or rendering labels.
Conceptually, a document must have at least one valid governing link and **no
denied or unresolved governing link across any registered type**. “Any allowed
link” is insufficient. Cache/index/projection state cannot be the final authority;
missing adapter, deleted/invalid target, lost membership or revoked scope denies
ordinary access and exposes only a separately authorized recovery path. No such
privileged recovery exception is granted in this ADR.

Adding a more restrictive link can make a previously visible document unavailable
to another reader; it never broadens the actor's authority. Recheck current and new
contexts under transaction locks, with an agreed lock/version protocol for target
scope changes, permission revocation, archive and concurrent link additions. All
writers that affect the decision must participate; a document lock alone does not
serialize independent role or target changes. Record link creation and audit
atomically, with a stable operation identity for retry and a unique business key
for duplicate-link races. Retry must not re-authorize through a weaker path.

## 4. Historical links, correction and deletion

Propose append-only typed link identity and explicit correction evidence. Do not
retarget, overwrite, delete or silently ignore an erroneous historical link. A
correction records the original and replacement identities, actor, reason, time,
reviewer/authority and affected evidence, preserving finalized bindings and audit.
Correction is not ordinary upload authority. Its approval/separation and effect
on access remain Q03 and Q04 accountable-review/acceptance matters; Q04 policy
selections, including final G3 — Revised with Protected Operations, are recorded but
not implemented.

In particular, marking a restrictive link “superseded” must not automatically drop
it from authorization and widen access. Until an approved correction/access-release
policy exists, the full retained link set continues to govern access. If policy
later distinguishes historical and governing links, it must specify confidentiality,
retention, required review and safe presentation for both sets, with denied-source
details protected. A wrong link is a recoverable governance issue, not an excuse
for support or Tenant Owner bypass.

Target archive preserves links and evidence; ordinary availability follows the
target's declared lifecycle and approved retention/export path. Typed target FKs
should protect referenced evidence from hard deletion. Document/tenant cascades,
queryset/bulk writes and migrations must be included in the future integrity review;
instance methods and Django Admin restrictions alone are insufficient. No hard-delete or
schema-contraction approval follows from this proposal.

S08's quarantine/hold/disposal rules apply to linked original bytes and derivatives.
A new link or link correction cannot release a hold, certify a scan, make old bytes
latest or dispose of evidence. Export must retain link lineage, pinned versions
where actually recorded, unresolved statuses and scope/completeness evidence; it
must not synthesize historic approvals or disclose inaccessible linked contexts.

## 5. Expand, map, switch and validate

After ADR acceptance and separate P1.3 authorization:

1. Inventory current six-target rows, document/version/target identifiers, tenant,
   creator/time, uniqueness, linked projects and consumers. Record an exact legacy
   link-to-typed-link mapping. Preserve UUIDs where feasible, otherwise immutable
   mapping; retain all six target kinds, archived history and original audit IDs.
2. Expand typed schema and registry with checked constraints and adapter contracts.
   Reuse Django ORM/PostgreSQL constraints and the existing permission infrastructure;
   no package is needed for this proposal. Backfill links without changing bytes,
   versions, current pointers, target revisions or claiming prior approval. Verify
   environment-specific lineage against S08's migration caveat before cutover.
3. Use a reviewed bounded write freeze or one transactionally coordinated writer
   during backfill/cutover; no independent legacy/new writers or hidden signals.
   For compatibility reads, union both representations by stable lineage so no
   link is missed or double-counted. Missing mappings and authorization differences
   block cutover, rather than silently treating a document as less restricted.
4. Validate per-tenant/type and per-document link-set parity, metadata/history,
   orphan/duplicate counts, target protection and every-context decision parity
   across lists, detail, downloads, forms, Django Admin and direct services. Include known
   list/detail/update-guard gaps as explicit reviewed corrections, not accidental
   side effects. Each correction needs tests and approved scope.
5. Switch approved consumers together, retaining compatibility for historical IDs
   and audit/export readers. Review query plans and representative counts to avoid
   per-row adapter queries or filtering after pagination. Never solve performance
   by skipping a denied/unknown type or materializing permissions as permanent grants.
6. Rehearse rollback with post-cutover writes and all link types represented. If a
   new type cannot be represented in the old schema, rollback must keep a compatible
   reader or stop affected actions; never drop its links. Removing legacy fields,
   tables, adapters or migrations requires separate explicit approval after verified
   deployment, parity, dependency removal and retention/tenant revalidation.

The exact schema, same-tenant database strategy, corrected-link access policy,
version-binding boundary and query budget need review by the Product Owner and
named DMS/domain/security owners. Q04 A-H selections now govern project/site,
privileged and Self-Approval direction, while named review/evidence still gates
acceptance. Q03 gates evidence/hold/export. D03-D05 storage/recovery/lifecycle inputs keep their
existing gates. No prior ADR is accepted or parent package completed here.

## 6. Static design cases and implementation gates

These cases are design walkthroughs, **not executed tests**:

| Case | Proposed expected result |
| --- | --- |
| Each of the six legacy target types is backfilled | Preserve exact document/target/tenant/actor/time and audit lineage; no file or version rewrite. |
| Forged tenant, foreign target or mismatched pinned version | Deny in service and the approved integrity enforcement paths; no link or partial audit committed. |
| Same tenant, projects A/B; reader can access only A | Retain both links; deny the whole document without B labels/counts/source leakage. |
| One registered type allowed, another denied or adapter missing | Deny; registry omission and “any link” queries cannot widen access. |
| Target archived or scope revoked between listing and action | Recheck at action; safe denial and consistent future list/detail behavior. |
| Duplicate add/retry or concurrent scope/link change | Stable identity/unique key and serialized authority; no duplicate history or stale-authority commit. |
| Correct a restrictive historical link | Retain history and restrictions until separately approved release policy; no automatic widening. |
| Version 2 added after a decision pinned version 1 | Preserve version 1 evidence; a legacy document-only link remains unpinned, never fabricated approval. |
| Direct update, bulk delete or target/Tenant cascade | Future enforcement must protect retained evidence; current instance/Django Admin guards are not sufficient proof. |
| Cutover parity failure or rollback after a new link type | Block unsafe switch/rollback; retain all contexts, bytes and history. |

P1.3 implementation must test all adapters and negative tenant/project/site cases,
multi-context conjunction, unknown/retired adapters, target lifecycle, correction
anti-escalation, version lineage, bulk invariants, concurrent changes, query plans
and migration/rollback. The inspected tests and this proposal do not certify these
gates. PPC-10, P0.1 and P1.3 remain incomplete.
