# P6-S26–S32 Taxpayer Invoice and Contractor Compliance Implementation

**Status:** Product Owner accepted (2026-10-03). P6-S33–S38 subsequently became
implementation complete / acceptance pending; P6-S39+ and production activation
remain unauthorized.

## Product Owner regulatory-governance correction (2026-10-03)

National tax, statutory-insurance, clearance, schema and other regulatory facts
are Platform-owned. The three national Billing consumers resolve the effective
published Platform version directly by document date; `TenantPolicySelection`
cannot select or override those policies. A Platform Admin may create, edit a
draft, attach sources, record review evidence, publish, retire and create a
superseding version, including on the same version and as the same user. Published
versions remain immutable. Tenant selection remains only for separately permitted
company-specific policies. No legal value, Article 38 effect, schema, credential
or production provider behavior is activated by this correction.

## Delivered boundary

P6-S26–S32 adds a bounded statutory-evidence layer in Billing without creating a
second policy, party, contract, workflow, document, subledger, Accounting or audit
authority.

- `TaxpayerInvoice` is a versioned derivative of one approved immutable
  `ProgressClaim` revision. Original, correction and cancellation lineage must
  match the linked commercial correction chain. Approved history is immutable;
  a linked replacement or cancellation closes the predecessor without rewriting
  it.
- The effective tax code, submission mode, schema identity, required external
  fields and exact field mapping come only from a direct Platform-resolved, effective,
  published `PlatformPolicyVersion` backed by external sources and accepted
  review evidence. No Iranian value or official schema is seeded in code.
- `ContractorComplianceAssessment` records a policy-pinned insurance basis,
  Decimal rate and deduction fact for one approved `PayableCertificate`, with an
  optional approved, effective and unexpired `ContractComplianceEvidence`
  clearance record. A reviewed policy may require clearance. The assessment has
  no AP, journal, Project Cost, Treasury or cash effect.
- `StatutorySubmissionEvidence` records immutable export or test-adapter attempts,
  request hash, correlation ID, provider-neutral response/error evidence and
  retry lineage. `StatutorySubmissionResolution` retains append-only human
  decisions. Tenant locking plus unique idempotency/correlation constraints
  prevent concurrent duplicates; a later attempt requires a failed predecessor
  and explicit retry authorization.
- Only `export_only` and explicitly supplied in-process `test_adapter` modes are
  supported. There is no live provider adapter, credential store, transport,
  scheduler, queue, notification or production activation. Credential-like
  request/response keys are rejected from persisted evidence.
- Dedicated permissions, shared workflow candidacy, strict submitter/approver
  separation, row locks and audit atomicity cover invoice and contractor-
  assessment approval. Persian-first RTL screens expose preflight, lineage,
  policy, error/human-resolution and source-to-submission evidence.

## Fail-closed rules

Creation stops when Tenant/project/contract/party/source alignment is invalid;
  the commercial source is not approved; the Platform policy is missing, ineffective,
  unpublished, not externally sourced or lacks accepted review; the
policy mapping references an unregistered internal fact; a required payload value
is absent; or required clearance is missing, wrong-contract, ineffective,
unapproved or expired. Rates use `Decimal`; source dates resolve historical
Platform regulatory versions so rule rollover does not rewrite history.

External acceptance or export evidence never changes the source claim or payable
certificate and never creates/replaces AR, AP, posting, GL reconciliation,
Treasury or cash facts. `reconcile_taxpayer_invoice` exposes the retained chain
from source claim through policy and every submission attempt with an explicit
`financial_effect = none` marker.

## Schema and migrations

- `billing.0013` creates taxpayer invoices, contractor assessments, statutory
  submission attempts/resolutions, constraints and work indexes.
- `billing.0014` and `billing.0015` add the immutable shared-workflow submission
  snapshots.
- `organizations.0087` installs the ten dedicated permissions and bounded default
  management-role grants.
- `workflows.0026` registers the taxpayer-invoice and contractor-compliance
  workflow types/templates. Existing workflow runtime and workbench remain the
  only approval mechanism.

## Verification (2026-10-03)

- Clean PostgreSQL migration/bootstrap plus the combined policy/permission and
  retained P6 suites reached **154 passed** before one new test stopped on an
  overly specific Unicode message assertion; every retained regression had
  already passed. The assertion was narrowed without changing runtime code.
- A subsequent fresh-schema focused tranche run passed **18 tests** in 483.68s.
  It covers reviewed/effective policy selection and rollover, schema preflight,
  original/correction/cancellation lineage, permission and Tenant isolation,
  workflow candidacy/SoD, concurrent idempotency, duplicate prevention,
  provider outage, human retry authorization, credential exclusion, audit
  rollback, contractor deduction/clearance gates, reconciliation, RTL UI and
  AP/AR/GL/source-document non-effects.
- A final clean-schema hardening rerun passed the **2 directly affected tests**
  in 350.77s after enforcing permission checks before idempotent replay and
  exposing contractor-certificate-to-submission reconciliation. It also verified
  that providerless controlled-export evidence accepts an intentionally blank
  provider key without implying a live provider.
- `python manage.py check`, migration-drift check and targeted Ruff passed.

## Product Owner acceptance (2026-10-03)

Product Owner accepted P6-S26–S32 based on the completed bounded implementation,
corrected Platform-owned regulatory-governance architecture, and focused
validation. Acceptance includes direct effective-date national-policy resolution,
Tenant non-override, Platform Admin same-user create/review/publish lifecycle,
immutable/superseding history, historical pins, retained Tenant Owner/Admin access
only for Tenant-configurable policies, and receivable-claim, taxpayer-invoice and
contractor-compliance behavior. It does not accept legal content or production
activation.

## Open gates and next scope

No official Iranian rate, threshold, calendar, identifier, field schema, filing
rule, Article 38 interpretation/effect, provider behavior or credential was
invented. Real policy versions, official schemas, live transport/authentication,
credential custody, legal/accounting acceptance and production activation remain
separate gates. Payroll tax and employee insurance-list processing remain P7.2.
The existing materials/document-link/platform-policy permission-registry gaps
remain unresolved and unchanged.

P6-S33–S38 subsequently proceeded under separate Product Owner authorization and
is implementation complete / acceptance pending. P6-S39+ and all production
activation remain unauthorized.
