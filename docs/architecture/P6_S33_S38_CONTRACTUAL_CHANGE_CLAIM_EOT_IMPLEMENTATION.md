# P6-S33–S38 Contractual Change, Claim, and EOT Implementation

**Status:** Product Owner accepted on 2026-10-03. P6-S39+ and production
activation remain unauthorized.

## Product Owner decision

On 2026-10-03 the Product Owner assigned ownership to Contracts and approved a
versioned `draft → submitted → approved / returned` lifecycle with explicit
withdrawal and linked correction/cancellation lineage. Returned records are
revised as new versions. Entitlement, approved amount, delay responsibility and
approved EOT days are manually entered approval facts; the system does not derive
them from legal, contractual, schedule, Billing or Accounting assumptions.

## Delivered boundary

- `ContractualRecord` covers Site Instruction, Variation/Change Order,
  contractual Claim and EOT series. It pins Tenant, project, contract, party
  identity, notice, requested impacts, assumptions, workflow submission snapshot,
  explicit approved facts, actors, timestamps and reasons.
- `ContractualRecordEvidence` provides append-only typed references to an
  immutable DMS version, Project Controls register/change evidence, schedule
  revision, verified receivable progress or verified payable measurement. Each
  source retains its existing owner and state.
- Dedicated view/prepare/submit/approve permissions are registered and seeded.
  Shared workflow routing enforces candidacy and submitter/approver separation;
  services re-check permission and scope inside locked atomic transactions.
- Draft, submitted and returned records can be withdrawn. Submitted withdrawal
  invokes the registered domain command and atomically cancels the active workflow.
  Approved records are corrected or cancelled only through a linked new version;
  database guards preserve finalized records and append-only evidence.
- Persian-first RTL list/create/detail/decision/revision/withdrawal views expose
  requested assumptions separately from approved facts and show the no-effect
  boundary.

Approval creates no automatic change to contract value or amendments, budget,
schedule baseline or accepted schedule, `ProgressClaim`, `PayableCertificate`,
AP/AR, subledger, GL/Accounting, Treasury or cash. No posting/source adapter or
production integration was registered.

## Schema and catalog

- `contracts.0008` creates the two Contracts-owned models and constraints.
- `contracts.0009` adds PostgreSQL guards for retained finalized history and
  append-only evidence.
- `organizations.0089` installs four dedicated permissions and bounded management
  role grants.
- `workflows.0027` installs the workflow type and starter template; the existing
  workflow runtime remains the only approval mechanism.

## Verification

- Clean PostgreSQL schema/bootstrap plus the focused initial suite completed;
  after one view-context defect was corrected, the final fresh-schema focused run
  passed **8 tests in 454.60s**. It covered lifecycle, SoD, Tenant/permission
  isolation, idempotency/concurrency, correction/cancellation/withdrawal lineage,
  immutable history, audit rollback, RTL UI and source/financial non-effects.
- The submitted-withdrawal and finalized-history hardening rerun passed **2 tests
  in 9.28s** on the migrated retained test database.
- The final contractual-record plus permission-registry run passed all **9
  contractual-record tests** and five registry checks. Three registry architecture
  checks failed only on preserved pre-existing gaps: 19 unregistered models in
  materials/document-link/platform-policy/expense-group areas, 12 existing
  namespace mismatches, and the existing `MATERIAL_DOCUMENTS_LINK` enforcement-
  module reference gap. The new contractual resource introduced no additional
  mismatch.
- The combined retained P6 gate passed **153 tests**. Six P6-S01–S13 assertions
  failed because those retained tests still expect Tenant-selected national rules
  and maker-checker Platform publication, while the accepted P6-S26–S32
  architecture resolves national rules directly and permits same-admin Platform
  lifecycle. Two concurrency fixtures failed during serialized database restore
  on a duplicate `django_content_type`; neither error entered P6-S33–S38 code.
  These pre-existing/out-of-scope conflicts were not changed.
- Django system check, migration-drift check and targeted Ruff passed.

## Product Owner acceptance and open gates

On 2026-10-03 the Product Owner accepted P6-S33–S38 based on the completed
implementation, focused validation, retained P6 regression evidence and the
boundaries in this packet. Acceptance covers the delivered Contracts-owned
records, lifecycle and approvals, explicit approved facts, evidence and lineage,
corrections/withdrawals/cancellations/superseding revisions, permissions, SoD,
scope controls, locking, idempotency, audit, immutable history and Persian-first
RTL operations.

Acceptance does not resolve or accept the preserved permission-registry gaps,
the 19 unregistered models, 12 namespace mismatches,
`MATERIAL_DOCUMENTS_LINK` enforcement-reference gap, six obsolete P6-S01–S13
assertions or two serialized-test restore errors. Automated
contract amendment/value consumption, schedule rebaseline, cost/forecast impact,
Billing or financial handoff, legal/notice/valuation/delay rules, notifications,
external transmission, scheduler/queue behavior and production activation require
separate authorization. P6-S39–S42 later proceeded under bounded authorization
and is implementation complete / Product Owner acceptance pending; P7 is
subsequently Product Owner accepted and complete within documented non-production
boundaries. P8 remains planning-only.

The previously documented materials/document-link/platform-policy permission-
registry gaps remain unresolved and unchanged; the validation above preserves
their exact failure evidence rather than broadening this tranche to repair them.
