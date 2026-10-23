# BONIRA Wave C — Final Domain Product Decisions

## PD-WC-D01 — Development Financial Profile

APPROVED.

For Development / Wave C only, authorize a bounded non-production financial profile containing:

- monetary-policy bridge versions using the already approved monetary semantics and values;
- effective period from the Wave C execution date until 2026-12-22;
- existing future-effective published policies remain unchanged;
- Tenant selection/application through canonical policy services;
- invoice matching tolerance:
  - quantity tolerance = 0 bps
  - unit-price tolerance = 0 bps
- Treasury self-approval = false;
- independent preparation/approval actors;
- dedicated synthetic Development AP control, cash and clearing accounts.

All such configuration is:

`UIUX_TEST_ONLY_NON_AUTHORITATIVE`

It is Development configuration only and establishes no Production accounting, Treasury or tolerance policy.

Applies to:

- RV-011
- RV-013
- ordinary Payroll dependency in RV-018

---

## PD-WC-D02 — Payroll Variable Input Producer

APPROVED.

Variable Payroll inputs shall no longer require the operator to manually provide technical source metadata when a governed upstream source is available.

For the bounded Wave C implementation, the authoritative upstream source shall be:

`Approved Timesheet Revision`

The user selects an eligible approved Timesheet through an authorized selector.

The server must derive and persist:

- source identity;
- source revision/version;
- source status;
- employee identity;
- covered period;
- approved quantity evidence;
- canonical source snapshot/provenance.

The UI must not require operators to manually enter:

- source UUID/reference;
- version;
- status;
- raw JSON payload;
- idempotency metadata.

An explicit mapping contract must define how supported Timesheet quantities map to existing Payroll input units/rules.

No payable hours, rates, premiums or Payroll values may be inferred unless already determined by an existing approved Payroll rule/configuration.

Manual explicit inputs may remain available only where the existing domain contract intentionally supports them.

This decision closes the Product Decision required for F-059.

---

## PD-WC-D03 — Statutory Coverage Boundary

APPROVED.

Wave C is a UI/UX runtime validation and does not certify Iranian Payroll statutory correctness.

Wave C shall validate:

- ordinary Payroll lifecycle;
- fixed-rule calculation;
- review/finalization journey;
- payslip presentation where supported;
- handoff preparation;
- prerequisite visibility;
- unavailable-source/error states;
- authorization and isolation;
- correct fail-closed behavior when reviewed statutory authority or schemas are absent.

Successful populated official statutory calculation/export is NOT required for Wave C closure.

It remains explicitly unvalidated until source-backed UAT / statutory / Production certification using genuine reviewed:

- tax and insurance sources;
- statutory source packages;
- official output schemas;
- calendar/identifier semantics;
- filing/provider requirements.

Wave C must not claim statutory certification.

---

## PD-WC-D04 — Supplier Portal Authoritative Payload

APPROVED.

For the bounded Supplier Portal journey, one submission consists of one immutable original primary bid document:

- PDF, or
- DOCX.

The original uploaded file is the authoritative payload for integrity evidence.

BONIRA must:

1. receive the actual file bytes;
2. store the retained original through protected canonical storage;
3. compute SHA-256 server-side over the exact retained bytes;
4. persist/associate immutable submission and revision provenance;
5. verify stored-content integrity;
6. use the server-derived digest for integrity/idempotency decisions.

Any client-supplied digest is non-authoritative comparison metadata only.

A digest mismatch must not be accepted as valid integrity evidence.

Existing DMS storage, `DocumentVersion.sha256`, processing/quarantine controls and confidentiality rules should be reused where appropriate.

The bounded extension of `QuoteRevisionEvidence` to support external portal ingestion is APPROVED, including the minimum additive choice/CHECK-constraint migration required.

This decision does not define multi-file bid-package digest semantics.

Multi-file packages and attachment aggregation remain a separate future contract if required.

---

## PD-WC-D05 — Tender Activation

NO NEW PRODUCT DECISION REQUIRED.

Use the already approved bounded Tender lifecycle.

Development may create the required activation/configuration evidence through existing models/services.

No Production:

- scoring policy;
- award logic;
- tender threshold;
- legal evaluation rule;
- accounting consequence

may be inferred.

---

## Certification Boundary

The following remain outside Wave C:

- Production chart-account selections;
- Production tolerance/self-approval policies;
- Iranian statutory rate/legal certification;
- official filing/export acceptance;
- live banking/payment release;
- Production Tender legal/scoring/award policy;
- Production deployment/certification.