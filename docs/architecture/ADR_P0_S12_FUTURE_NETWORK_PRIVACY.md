# ADR P0-S12: Future-network privacy, consent and shared-data boundaries

**Status:** PROPOSED for P0.1 review; not accepted and not implementation authorization

**Scope:** planning boundaries for a possible controlled B2B network after its
deferred triggers are met. This proposal does not launch the network, select a
business model, create consent terms, or authorize schema, dependency, P0.2 or
P0.3 work.

The [Domain Model](DOMAIN_MODEL.md#3-domain-landscape),
[Data Model](DATA_MODEL.md#11-network-and-privacy-boundary),
[Business Model](BUSINESS_MODEL.md#10-ecosystem-and-network-strategy) and
[Roadmap deferred trigger](../../ROADMAP.md#deferred-until-explicit-triggers)
remain authoritative. This ADR develops their privacy boundary without changing
the deferred disposition. It defines product record authority and control
responsibilities, not legal ownership of customer or third-party data.

## 1. Verified current behavior and limits

| Current evidence | Bounded conclusion |
| --- | --- |
| [`BusinessParty`, `PartyRole` and `PartyContact`](../../apps/parties/models.py) carry `organization`; party tax identifiers and contacts are unique within a tenant, and relationship validation rejects mismatched tenants. | Current counterparties, roles and contacts are tenant records. Matching values across tenants neither identify one platform party nor authorize correlation or disclosure. |
| [Party services](../../apps/parties/services.py) require active tenant management access, lock mutations and reject a party from another organization. `test_cross_tenant_party_operations_and_member_mutation_are_denied` and `test_contact_model_rejects_cross_tenant_party` cover direct negative cases. | Current party management is not a network publication or discovery path. Archive/list behavior is tenant-local. |
| The [current domain/data model](DOMAIN_AND_DATA_MODEL.md#model-conventions-and-tenant-boundary) separates global `User`, tenant `OrganizationMembership`, tenant `Employee` and tenant `BusinessParty`; cross-organization foreign keys are forbidden. | Login, workforce, counterparty and future platform-party identities must not be collapsed or treated as mutual grants. |
| [Document models](../../apps/documents/models.py) keep document, version and link metadata organization-owned; current services recheck every linked context. `test_endpoints_reject_cross_tenant_document_uuid` and `test_document_access_requires_linked_context_permission` cover relevant denial behavior. | Current private documents and their metadata cannot be network evidence, attachments or previews merely because a party or relationship is published. |
| A bounded search found no `PlatformPartyClaim`, `VerifiedRelationship`, `PublicationConsent`, discovery/recommendation or network runtime in application code. | The target concepts in the Data Model are unimplemented. No existing party, invitation, portal, support or subscription record is implicit network participation. |

This inspection is evidence for a planning boundary, not a repository-wide privacy
audit. Current code and migrations remain authoritative for implemented behavior.
S12 changes none of them.

## 2. Proposed ownership and separation

Choose a **separate platform publication boundary with explicit tenant-controlled
contributions** if the network is later approved. Preserve the tenant system of
record and create no shared canonical master by side effect.

| Record or responsibility | Proposed authority boundary |
| --- | --- |
| Tenant party/profile, contacts and qualification facts | The originating tenant domain remains authoritative and private. A network record may reference an explicitly selected source version only through an approved publication action; it does not become the tenant master. |
| Tenant transactions and operations | Contracts, RFQs/quotes, awards, orders, receipts, invoices, claims, payments, journals, projects, capacity facts and operational records remain tenant-private unless a future, specifically approved cross-party workflow defines each disclosed field and recipient. Network participation alone is never that approval. |
| Tenant evaluations | Project, quality, safety, commercial and performance evaluations remain tenant-private. No raw evaluation, author identity, free text, score or derived reputation is shared by default. |
| Tenant documents and identities | Documents, evidence, contacts, `User`, membership, employee and support data remain under their existing tenant/domain authorities. A published claim carries neither the source document nor directory identity unless each is separately and explicitly within accepted scope. |
| Future platform identity/claim | A platform-network authority may own only the separate claim, verification, consent/publication, relationship, discovery/moderation and dispute evidence defined by an accepted network package. It must retain source tenant, publisher, subject, version and policy provenance. |
| Derived network aggregate | A governed analytics authority may produce only accepted, purpose-limited outputs after privacy, competition and minimum-cohort controls are decided and tested. It never becomes an alternate transaction or evaluation authority. |

The tenant controls whether its eligible facts are offered for publication under an
accepted policy; the platform controls verification, presentation, abuse response
and removal from the network surface. Neither control implies legal title or the
right to publish another party's personal, confidential or contractual data.

### Alternatives not selected by this proposal

| Alternative | Disposition |
| --- | --- |
| Share or search tenant masters by default | Reject. It breaks tenant isolation and infers participation, audience and purpose. |
| Merge equal tax/contact identifiers into one platform party | Defer with the separately triggered shared-catalogue/overlay decision. Equality is matching evidence, not authority, identity proof or consent; incorrect merge and existence disclosure remain material risks. |
| Reuse the invitation-scoped partner portal as the network | Reject. The portal is bilateral access to one tenant's process; it does not create public/cross-tenant discovery, a platform identity or rights in other tenants. |
| Separate platform claims and explicit publications | Proposed architecture if triggers and decisions are later accepted. It preserves source ownership, revocation and provenance without rewriting tenant history. |

## 3. Participation, consent and sharing contract

Participation is opt-in and purpose-specific. S12 intentionally does not choose
the consenting role, consent text, legal basis, duration, audience taxonomy,
default visibility, commercial consideration or withdrawal terms.

A future publication decision must identify at least:

1. the participating tenant and authorized actor under a separately accepted
   permission/separation policy;
2. the subject/claim, exact fields and source version or supplied statement;
3. purpose, allowed audience/use and any geography/channel restriction;
4. verification state and verifier, effective time, expiry/review condition and
   policy/terms version;
5. whether the subject is a tenant, a tenant-local `BusinessParty`, or a separately
   verified platform identity, without silently merging them;
6. revocation/withdrawal behavior, retained evidence and downstream obligations;
7. provenance visible to recipients and dispute/correction contact; and
8. a stable request/publication identity for retries, audit and reconciliation.

Do not infer consent or participation from subscription, Tenant creation, accepting
product terms unrelated to the network, Tenant Owner/Tenant Admin/Platform Admin/
Superuser status, party creation, tax-ID
matching, a portal invitation, a contract/RFQ/award, document upload, support case,
publicly discoverable information or a relationship claimed by another tenant.
One tenant cannot consent for another tenant, its users, workers or counterparties
unless a future accepted legal/authority model specifically establishes that scope.

Publication and bilateral transaction sharing are different operations. A tender
or marketplace flow, if later approved, must state which party sees which fields at
each stage; a discovery profile is not authority to expose bids, comparisons,
award reasons, project data or documents. No future network recipient gains rights
to reuse facts for a new purpose merely because it could view them once.

## 4. Revocation, correction and relationship lifecycle

Revocation is prospective control over the platform surface, not permission to
rewrite another tenant's history or destroy evidence contrary to policy.

- Recheck consent and current publication state before discovery, recommendation,
  export, delivery and any queued continuation. Expiry or revocation blocks new
  use and removes the item from eligible indexes/caches under an accepted service
  contract; a worker or stale search projection cannot preserve authority.
- Record who revoked what, authority, reason, effective time, affected purposes and
  reconciliation status. Idempotent retries must not republish a revoked version.
- A correction or superseding source version creates traceable replacement; it
  does not silently alter claims or decisions already made from an earlier version.
- Define, before launch, the treatment of recipient copies, already-completed
  bilateral transactions, fraud/dispute evidence, legal holds, backups and public
  claims. S12 chooses no irrevocability, deletion promise or notice period.
- A verified relationship is separate from publication consent. Either side's
  withdrawal, dispute, expiry or verification loss changes future eligibility but
  does not grant access to the other tenant or erase its private relationship
  evidence.

## 5. Provenance, verification, reputation and intelligence

Every shared claim must distinguish the claimant, subject, source tenant/source
version, verifier, verification method/class, effective/expiry state and later
correction, dispute, revocation or supersession. “Verified” must have a defined
meaning and must not imply platform endorsement beyond that meaning. Unverified,
expired and disputed states cannot be silently presented as current verified fact.

Tenant-local qualification and performance sources remain explainable,
category/time/project-specific records. A future shared qualification or reputation
view needs an accepted claim vocabulary, evidence eligibility, weighting,
minimum-data, conflict-of-interest, response/appeal, correction and anti-gaming
model. It must not expose individual evaluations or allow a score to be reverse
engineered to a tenant, project, employee, bid or transaction.

“Anonymous” and “aggregated” are acceptance claims, not labels. Benchmarking or
price/lead-time/performance intelligence stays disabled until minimum cohort,
dominance/outlier, sparse-combination, query differencing, temporal/geographic
granularity, suppression and re-identification tests are decided with privacy and
competition review. No threshold, noise technique, metric or secondary-use right
is invented here.

## 6. Cross-tenant isolation, authorization and support

[S07](ADR_P0_S07_PROJECT_SITE_AUTHORIZATION.md#3-enforcement-and-workflow-contract)
continues to govern ordinary tenant and object scope. Network participation,
platform identity, verification or relationship state does not create an
`OrganizationMembership`, business permission, project/site grant, workflow
candidacy, portal session or support grant in either tenant.

- Resolve the current tenant from authenticated membership for tenant sources;
  never trust tenant, party or publication IDs from a request as authority. Deny
  foreign records without names, counts, match hints or existence leakage.
- A future network package requires explicit permission codes, registry/catalog
  entries, reviewed default-role grants (if any), object/purpose checks and tenant
  negative tests. S12 creates none and selects no approving role.
- Search, recommendations, moderation, exports and metrics must query the separate
  eligible-publication boundary. They cannot fall back to tenant tables or private
  indexes when network data is missing.
- [S08 private storage](ADR_P0_S08_PRIVATE_DOCUMENT_STORAGE.md#2-proposed-ownership-and-storage-contract)
  applies to any source evidence and future derived artifact. No public object key,
  cross-tenant byte deduplication or storage credential is authority to share.
- [S11 support rules](ADR_P0_S11_TENANT_LIFECYCLE_ENTITLEMENTS_SUPPORT.md#6-support-access-and-separation)
  remain unchanged. A support case, operator credential, superuser status, plan
  level or technical database/storage access supplies neither tenant consent nor
  network authority. Minimized diagnostics must not become network content.
- Moderation and abuse handling need separately accepted read/action scope,
  separation, appeal and audit. “Safety” is not a standing privileged exception,
  concealed impersonation or permission to browse tenant-private facts.

Suspension/cancellation removes ordinary tenant access under S11. It does not
publish data, prolong consent, erase network evidence or authorize a background
operation. The disposition of active publications and relationships during each
tenant state is an open lifecycle decision, not inferred here.

## 7. Retention, export, offboarding and data placement

Consent state, publication history, verification/dispute/moderation evidence,
recipient/delivery evidence and derived aggregates need their own versioned
retention classifications. A tenant source's policy and a platform-network
record's policy may differ, but neither may silently extend access to the source.

[S08 retention/export rules](ADR_P0_S08_PRIVATE_DOCUMENT_STORAGE.md#4-retention-legal-hold-export-and-disposal)
and [S11 offboarding](ADR_P0_S11_TENANT_LIFECYCLE_ENTITLEMENTS_SUPPORT.md#5-offboarding-export-and-pending-obligations)
apply: archive is not expiry, cancellation is not deletion, revocation is not
automatic disposal, hold release is not deletion authority, and partial deletion
cannot be reported complete. No duration or immediate-backup-erasure promise is
made.

A future tenant/network export must use an authorized manifest with purpose,
scope, cutoff, source/publication versions, provenance and completeness. A tenant
may receive its own contributions and consent/publication history as policy allows;
it must not receive another tenant's private sources, recipient activity, abuse
reports, personal data or protected platform evidence without separately accepted
authority. Recheck authority before generation and delivery; protected temporary
bundles are never public URLs.

Offboarding one tenant must not delete a global `User`, another tenant's master or
history, a counterparty's independent claim, or shared evidence still lawfully
required under an accepted policy. Conversely, another tenant's dependency cannot
indefinitely preserve discovery or new use after revocation without an expressly
accepted basis. These conflicts, data locations, operators and recovery treatment
must be resolved before implementation.

## 8. Open decisions and acceptance boundaries

| Gate / accountable decision | Required outcome before the stated boundary |
| --- | --- |
| Deferred network trigger / Product Owner | Confirm mature party/qualification governance, verified-relationship model, sufficient opt-in density, abuse/moderation capacity and legal/commercial operations before moving the program out of deferred status. P0-S12 does not satisfy the trigger. |
| Network purpose and business model / Product Owner | Select bounded initial use case, participants, value exchange, commercial model, non-lock-in/export commitments and prohibited uses. No launch scope or shared-data authority exists until accepted. |
| Consent and identity / Product Owner with named privacy/legal and security reviewers | Define participant/subject identity proof, authorized consenting actor, notice/terms, purposes, audiences, expiry/review, withdrawal, dispute/correction and rights handling. Validate applicable privacy, confidentiality and contractual authority; S12 certifies none. |
| Claim/relationship governance / named party-domain and operations owners | Define claim vocabulary, verification levels/evidence, merge/non-merge rules, relationship confirmation, moderation, fraud/abuse response, appeal and operator authority. |
| Reputation/intelligence / named privacy, competition and metric reviewers | Approve eligible sources, aggregation and suppression controls, cohort thresholds, anti-gaming, explanation, correction and re-identification/competition tests before any score or benchmark. |
| D03/D04 | Decide network data/backup/log/support/moderation locations, providers/operators, incident ownership and numeric recovery objectives before data placement or commitments. Existing open parameters remain open. |
| Q03 | Decide evidence, retention/hold/export/disposal obligations and accountable approver for tenant sources and separate platform records before design acceptance or data placement. No periods are selected. |
| Q04 and S07 | A-H selections govern explicit scope, privileged disposition, revised support/emergency access, final G3 — Revised with Protected Operations and its configurable business Self-Approval, and eligible fallback. Named security/workflow/privacy/legal/domain review remains before access-design acceptance; no runtime exception is implemented. |
| S11 lifecycle | Decide publication/relationship behavior for suspension, cancellation, re-entry and offboarding, including pending operations. Network work does not implement P0.3. |
| Architecture/security acceptance | Threat model correlation/existence leakage, scraping, enumeration, impersonation, poisoning, collusion, re-identification, cache/index revocation and cross-tenant failures; approve dependency/provider choices and operations before implementation. |

All P0-S03 decisions retain their original gates. This proposal does not accept
S07, S08 or S11; close P0/P0.1; freeze release scope; or authorize P0.2/P0.3.

Only after the deferred trigger, the decisions above and a separately authorized
network work package may detailed design inventory eligible sources, define the
physical schema/permissions, prepare reviewed tenant opt-in/backfill rules, run a
bounded pilot and produce privacy/security/competition/operational evidence. There
is no automatic migration of existing parties, contacts, evaluations, documents,
transactions or invitations into the network.

## 9. Static design walkthroughs and validation limits

These are reviewed planning cases, **not executed application tests**:

| Case | Proposed expected outcome |
| --- | --- |
| Two tenants use the same party tax ID/contact | Keep separate tenant records; reveal no match and perform no platform merge/publication without accepted identity and consent decisions. |
| Tenant publishes a supplier profile but has private contracts/evaluations | Expose only the accepted claim fields/audience; no transaction, document, score, author or existence leakage. |
| Supplier/other tenant disputes a claim | Mark the claim under the accepted dispute policy, preserve provenance, restrict presentation as required and route review; do not grant either tenant access to the other's source. |
| Publication consent expires or is revoked while indexed/queued | Block new use, remove/reconcile eligible indexes and queued delivery, retain only policy-authorized evidence; worker credentials cannot override. |
| Relationship is verified | Record bounded relationship evidence; create no membership, project/site scope, portal access, workflow candidacy or authority to see either tenant's history. |
| Tenant attempts to attach a private document to a network claim | Deny unless an accepted, separately authorized publication includes the exact safe version/fields; never expose a raw storage key or linked contexts. |
| Support/operator wants private source data to resolve a network issue | No implicit access. Use minimized evidence or a separately accepted S11/Q04 path; record original actor and purpose. |
| Cancellation occurs with active publication, dispute or hold | Deny ordinary tenant access; follow the still-to-be-decided lifecycle/retention contract, with no automatic publication, deletion or continued use. |
| Benchmark cohort is sparse or one tenant dominates | Suppress/deny output until accepted thresholds and re-identification/competition tests pass; “anonymous” label is insufficient. |
| Tenant exports or offboards | Export only authorized tenant contributions/history with explicit completeness; exclude other tenants' private data and preserve independent identities/required evidence. |
| Portal invitee or awarded supplier appears in tenant workflow | Do not enroll in or publish to the network; portal/bilateral activity is not consent. |
| Revoked claim remains in cache, recommendation or recipient retry | Treat as reconciliation failure, block delivery/use and preserve incident evidence; never restore from stale projection. |

Future acceptance requires executable cross-tenant negative tests, publication and
revocation races, list/detail/search/export parity, cache/index reconciliation,
consent/authority history, dispute/moderation separation, offboarding/restore and
re-identification/abuse exercises. S12 provides only documentation inspection,
static boundary walkthroughs and consistency checks. It supplies no legal opinion,
privacy certification, runtime assurance, operating capacity or launch approval.
