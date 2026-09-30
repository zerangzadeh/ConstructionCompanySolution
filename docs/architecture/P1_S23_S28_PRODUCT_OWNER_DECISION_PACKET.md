# P1-S23–S28 Product Owner decision packet

**Prepared:** 2026-09-29  
**Decisions recorded:** 2026-09-30  
**Status:** PRODUCT OWNER DECISIONS RECORDED; EXECUTION CONTRACTS READY AFTER P1-S19–S22 DEPENDENCIES

## 1. Purpose and fixed boundaries

This packet records the authoritative Product Owner choices and execution
contracts for P1-S23 through final P1 acceptance. It does not reopen P1-S01–S22 or
restate the P1-S19–S22 choices. Completion of the recorded P1.3 document contract
remains an entry dependency; this record authorizes no runtime change while
P1-S19–S22 execute separately.

The following boundaries are already fixed: materials remain Tenant-local;
Materials owns identity, attributes and conversions; Procurement owns quotes and
purchases; Inventory owns movements and valuation; Estimates owns rate usage;
Quality owns approval evidence; transactions retain the applied identity, unit and
rate snapshot; price observations are not a financial ledger; and no shared
cross-Tenant catalogue is authorized in P1.

The Product Owner selected **D23-01=A, D23-02=A, D24-01=A, D24-02=A, D25-01=A,
D26-01=A and D28-01=A** on 2026-09-30. These selections and every boundary and
consequence stated for Option A below are authoritative. Permissions/capabilities
are used instead of mandatory job titles wherever possible. A later revision must
state its replacement boundary explicitly.

## 2. Authoritative decisions

### D23-01 — Canonical material-code stewardship and correction

**Exact issue:** who allocates the canonical Tenant material code, whether it can
change after use, and how aliases and corrections preserve history.

| Option | Practical consequence |
| --- | --- |
| **A — Tenant-governed required code; dedicated stewardship permission; immutable after first transactional use; later identifiers are aliases or an audited supersession** | Preserves stable references and transaction snapshots while allowing each Tenant to keep its coding scheme. No Platform user acquires material-data authority. |
| B — System-generated Tenant sequence is the sole canonical code | Strong collision control, but forces one allocation pattern and complicates migration of existing customer codes. |
| C — Editable Tenant code with uniqueness only | Simple UI, but a later edit can reinterpret integrations, imports and historical references. |

**Recommended default:** **A**. Existing codes are adopted as canonical during
migration; the Tenant may configure format/sequence rules for future codes, but
the Platform must not invent an industry coding standard.

**Product Owner decision:** **A — ACCEPTED 2026-09-30.**

**Unlocks:** S23 identity, alias, duplicate-review and migration contract; S27
history/merge acceptance.

**Safely deferrable beyond P1:** cross-Tenant canonical identity, industry-code
mapping and automatic external-code synchronization.

### D23-02 — Duplicate resolution, merge and alias authority

**Exact issue:** whether P1 supports destructive merge, audited supersession, or
review-only duplicate marking.

| Option | Practical consequence |
| --- | --- |
| **A — Audited supersession/merge by dedicated permission; losing record becomes an alias; existing transactions keep original reference and snapshot; new selection resolves to the survivor** | Enables safe cleanup without rewriting approved history; requires concurrency, cycle and cross-Tenant controls. |
| B — Duplicate flag and alias only; no merge in P1 | Lower migration risk, but users must manage parallel material records and downstream selection rules. |
| C — Rewrite all references to the survivor and delete the duplicate | Produces a clean current database but destroys source lineage and is incompatible with retained history. |

**Recommended default:** **A**, implemented as non-destructive supersession rather
than physical deletion or historical FK rewriting.

**Product Owner decision:** **A — ACCEPTED 2026-09-30.**

**Unlocks:** S23 duplicate/alias workflow and S27 merge/history tests.

**Safely deferrable beyond P1:** probabilistic duplicate detection and bulk merge;
manual candidate review is sufficient.

### D24-01 — UOM family, conversion direction and versioning

**Exact issue:** how convertible units are grouped, which direction is
authoritative, and whether later factor changes reinterpret old transactions.

| Option | Practical consequence |
| --- | --- |
| **A — Tenant units join an explicit dimension/family with one family base; store a versioned directed factor to the base; derive reverse/cross conversions; transactions retain conversion version and input/output snapshots** | Gives one deterministic path, prevents conversion cycles and preserves historical calculations. |
| B — Store arbitrary directed pair conversions | Flexible, but multiple paths can disagree and require graph consistency/conflict rules. |
| C — Store both directions independently | Easy lookup, but reciprocal drift creates contradictory results. |

**Recommended default:** **A**. The Platform owns the closed dimension/type
semantics; the Tenant owns its units, family membership and effective conversion
facts. Dimensionless or non-convertible units remain explicitly isolated.

**Product Owner decision:** **A — ACCEPTED 2026-09-30.**

**Unlocks:** S24 conversion schema/service and S27 consistency/history review.

**Safely deferrable beyond P1:** compound-unit algebra, formula-based
temperature/density conversions and automatic external conversion feeds.

### D24-02 — Conversion precision and rounding policy

**Exact issue:** where rounding occurs and who controls precision without silently
hard-coding a commercial or accounting value.

| Option | Practical consequence |
| --- | --- |
| **A — Preserve a high-precision Decimal calculation; round only at the declared output/use boundary using a versioned Tenant policy selected from Platform-supported rounding modes; snapshot policy/version and unrounded result** | Supports different quantity contexts without changing history; unknown policy fails closed for conversions that require rounding. |
| B — Round every conversion to the target unit's current `decimal_places` | Simple, but chained conversions accumulate error and later unit edits can reinterpret history. |
| C — One fixed global scale and rounding mode | Deterministic but unnecessarily hard-codes policy across Tenants and use cases. |

**Recommended default:** **A**. Schema capacity and safety limits remain Platform
technical controls; actual business scale/rounding selections are Tenant policy,
not invented regulatory/accounting values. Direct conversion to an exactly
representable result does not need artificial rounding.

**Product Owner decision:** **A — ACCEPTED 2026-09-30.**

**Unlocks:** S24 calculation/rounding implementation and S27 precision regression.

**Safely deferrable beyond P1:** context-specific policies for valuation, payroll
or tax; P1 needs quantity conversion only.

### D25-01 — Dynamic technical-attribute governance

**Exact issue:** who defines category-specific attributes and how definition
changes affect approved materials and historical use.

| Option | Practical consequence |
| --- | --- |
| **A — Platform-owned closed data types/operators; Tenant-owned versioned category definitions; material values validate against the applied definition version** | Provides safe flexibility without executable Tenant code; approved history remains explainable. |
| B — Fixed Platform fields only | Simple and searchable, but cannot represent category-specific construction specifications. |
| C — Free-form JSON without governed definitions | Fast to build, but weak validation, search, migration and audit semantics. |

**Recommended default:** **A**. Definitions are declarative only; no Tenant Python,
SQL, templates, network callbacks or arbitrary expressions.

**Product Owner decision:** **A — ACCEPTED 2026-09-30.**

**Unlocks:** S25 attributes, search/import validation and history tests.

**Safely deferrable beyond P1:** complex formulas, external taxonomy import and
cross-Tenant template sharing.

### D26-01 — Technical/quality approval ownership and use gate

**Exact issue:** who may submit and approve material technical suitability, the
lifecycle to preserve, and whether approval controls new transactional selection.

| Option | Practical consequence |
| --- | --- |
| **A — Materials steward owns draft master data; dedicated technical/quality permissions own review and approval evidence; lifecycle is draft -> review -> approved/rejected, with supersession for later revisions; Tenant policy controls self-approval where the Platform permits it** | Separates master maintenance from evidence-based approval, works without mandatory workforce positions, and uses the existing authorization/workflow boundary. New transactions may require an approved effective revision by Tenant policy. |
| B — Material maintainer also approves by default | Lower overhead, but weak separation and unclear quality accountability. |
| C — Approval always requires a named Quality job position | Strong organizational routing for large firms, but blocks small Tenants and confuses positions with permissions. |

**Recommended default:** **A**. Position/project routing is optional evidence, not
permission. Approval applies to a version and scope; rejection does not erase the
master. Existing materials migrate to an explicit `legacy_unreviewed` compatibility
state and remain usable under an explicit Tenant compatibility policy until
reviewed; the migration must not fabricate approval.

**Product Owner decision:** **A — ACCEPTED 2026-09-30.**

**Unlocks:** S26 documents, substitutes/equivalents and approval state; S27
permission, separation and migration tests.

**Safely deferrable beyond P1:** mandatory multi-stage routing, laboratory/LIMS
integration, expiry rules without an authoritative source, and mandatory approval
for every transaction. These may be configured later and must not be implied now.

## 3. Final acceptance choices

### D28-01 — P1 residual-risk disposition and P2 handoff

**Exact issue:** how the Product Owner will dispose of S27 findings and authorize
final P1 acceptance without converting deferred capabilities into silent claims.

| Option | Practical consequence |
| --- | --- |
| **A — Conditional P1 acceptance only after all P1 acceptance tests pass; explicitly listed fail-closed deferrals remain open roadmap items; P2 handoff does not imply production certification** | Allows P2 to start while preserving truthful limits and named remediation ownership. |
| B — Require every deferred DMS/material enhancement before P1 closeout | Broadens P1 and delays P2 even where the omitted capability is safely fail-closed. |
| C — Accept P1 with unresolved high-risk tenant-isolation, authorization, history or recovery failures | Creates an unsafe phase boundary and is not acceptable. |

**Recommended default:** **A**. At S28 the Product Owner chooses accept or return
for remediation based on S27 evidence; no further architecture choice should be
invented at closeout. Cross-Tenant access, unauthorized approval/merge, historical
rewrite, conversion ambiguity, or document-security failure cannot be deferred.

**Product Owner decision:** **A — ACCEPTED 2026-09-30 as the closeout rule only.**
This is not final P1 acceptance; S28 must wait for S27 acceptance evidence.

**Unlocks:** S28 final P1 acceptance and conditional P2 handoff.

**Safely deferrable beyond P1:** only the items explicitly identified above and in
the recorded P1.3 decision contract, with owner/target phase and fail-closed
behavior recorded. Production certification remains P10.

## 4. Execution contracts

The product-policy gate for S23-S26 is satisfied. Execution remains dependency-
blocked until P1-S19–S22 complete and provide the accepted P1.3 document boundary.
Each implementation session must introduce its required business permissions,
default-role grants, audit actions, migrations and Tenant-isolation/authorization
tests atomically; UI visibility is never authority.

### P1-S23 — Canonical identity, aliases and supersession

- **Goal:** adopt existing Tenant codes as canonical; add immutable aliases,
  duplicate review and audited non-destructive supersession.
- **Required invariants:** organization-scoped identity; code immutability after
  transactional use; dedicated stewardship/merge permissions; cycle/concurrency
  prevention; losing records retained; historical FKs and snapshots unchanged;
  new selection resolves to the survivor.
- **Acceptance:** cross-Tenant aliases/merge are denied; unauthorized merge is
  denied; correction never deletes a material or rewrites historical data; audit
  identifies actor, reason, survivor and superseded record.
- **Excluded:** shared cross-Tenant catalogue, automatic external-code sync,
  probabilistic matching and bulk merge.

### P1-S24 — Deterministic versioned UOM conversion

- **Goal:** introduce Tenant-local families/dimensions, one family base and
  effective versioned directed factors to that base.
- **Required invariants:** one deterministic conversion path; compatible
  dimensions only; reverse/cross results derived rather than independently
  authored; Decimal calculation; no float; transaction/use records retain the
  applied conversion/policy versions plus required input, unrounded-result and
  output snapshots.
- **Precision:** round only at the declared output/use boundary under a versioned
  Tenant policy selected from Platform-supported modes. Unknown required policy
  fails closed. No accounting, tax or regulatory value is inferred.
- **Acceptance:** historical reproduction survives later factor/policy changes;
  ambiguous, cyclic, incompatible or non-deterministic conversion is rejected.
- **Excluded:** compound-unit algebra, formula conversions and external feeds.

### P1-S25 — Governed attributes and observations

- **Goal:** add Platform-closed declarative types/operators and Tenant-owned,
  category-scoped, versioned definitions/values; provide bounded import/search and
  effective price/source observations under the fixed domain ownership contract.
- **Required invariants:** values validate against the applied definition version;
  Tenant scope and approved-history explanation are preserved; price observations
  retain source, currency and unit and never become a financial ledger or override
  Procurement quote ownership.
- **Acceptance:** invalid/version-mismatched values and cross-Tenant definitions
  fail closed; imports are reviewable and idempotent; no executable Tenant content
  exists.
- **Excluded:** arbitrary Python/SQL/templates/expressions, complex formulas,
  external taxonomy synchronization and cross-Tenant template sharing.

### P1-S26 — Technical documents, substitutes and approval

- **Goal:** connect materials to the completed P1.3 document authority; add
  governed substitutes/equivalents and version/scope-specific technical-quality
  review evidence.
- **Required lifecycle:** `draft -> review -> approved/rejected`; later revision
  supersedes rather than overwrites. Dedicated permissions control submit/review/
  approve; optional position/project routing is evidence, never permission.
- **Compatibility:** existing materials become explicit `legacy_unreviewed`; they
  remain usable only under an explicit Tenant compatibility policy. Migration
  never fabricates approval. Tenant policy may require an effective approved
  revision for new selection and may control business self-approval only where
  the Platform permits it.
- **Acceptance:** unauthorized or cross-Tenant approval/substitution is denied;
  document access uses P1.3 security; rejection/renewal preserves history.
- **Excluded:** mandatory job titles, mandatory multi-stage routing, LIMS,
  unsupported expiry rules and universal approval for every transaction.

### P1-S27 — Integrated acceptance

- **Goal:** review the completed S19-S26 integration for Tenant isolation,
  permissions, document security, migration/history, merge concurrency,
  deterministic conversion and historical reproduction.
- **Mandatory evidence:** targeted PostgreSQL migrations/backfill/rollback or
  forward-recovery rehearsal; negative cross-Tenant and permission tests; alias/
  supersession lineage; conversion/policy version replay; legacy compatibility;
  P1.3 document-access and failure-state tests; audit completeness.
- **Non-deferrable failures:** cross-Tenant access, unauthorized approval or merge,
  historical-data rewrite, ambiguous/non-deterministic conversion and document-
  security failure. Any such result returns the affected slice for remediation and
  blocks S28 acceptance.

### P1-S28 — Closeout and conditional P2 handoff

- **Goal:** reconcile code/migrations/tests and authoritative documents, dispose of
  every S27 finding and record the Product Owner's final accept-or-return outcome.
- **Gate:** D28-01=A defines this rule but supplies no acceptance in advance. P1 is
  accepted only after all required S27 evidence passes and every deferral is
  explicit, owned, assigned below and fail-closed where applicable.
- **Outcome:** accepted P1 may hand off conditionally to P2; this is not production
  certification, which remains P10.

## 5. Explicit post-P1 deferrals

| Deferred capability | Later roadmap checkpoint | Required boundary before activation |
| --- | --- | --- |
| Shared cross-Tenant material identity/catalogue | Deferred-trigger track in `ROADMAP.md` | Separate consent, stewardship, merge/dispute, privacy and trigger decision; absent in P1 |
| Industry/external material-code mapping and synchronization | P4.0/P5 consuming-package design | Explicit source/licence/ownership and idempotent import decision; no inferred mapping |
| Probabilistic duplicate detection and bulk merge | P4.0/P5 catalogue-volume review | Human review, dedicated merge permission and the S23 non-destructive contract remain authoritative |
| Compound, density/formula and externally supplied conversions | P4.0 or P8.1 consuming package | Explicit formula/source/version policy; unsupported conversions fail closed |
| Financial, tax, payroll or valuation-specific rounding | P2, P4, P7 or P8 owning package | Owning-domain policy and authoritative values; P1 quantity policy must not be reused implicitly |
| Complex attribute formulas and external taxonomy synchronization | P4.0/P5 consuming-package design | Governed catalogue/source and bounded expression decision; executable Tenant code remains prohibited |
| Mandatory multi-stage material approval and laboratory/LIMS integration | P9.2 quality extension | Approved workflow/integration, evidence, credential and failure contract |
| Approval expiry rules and mandatory approval for every transaction | Relevant P4/P5/P8/P9 consuming package | Authoritative source plus explicit Tenant policy; `legacy_unreviewed` is never treated as approved |

## 6. Execution order

The resulting order remains:

1. **S23:** canonical identity, aliases and non-destructive duplicate resolution;
2. **S24:** UOM families and versioned deterministic conversions;
3. **S25:** governed attributes, price/source observations and search/import;
4. **S26:** technical documents, substitutes and technical/quality approval;
5. **S27:** integrated tenant, permission, history, merge, conversion and document-security acceptance;
6. **S28:** Product Owner acceptance/return record, documentation closeout and conditional P2 handoff.
