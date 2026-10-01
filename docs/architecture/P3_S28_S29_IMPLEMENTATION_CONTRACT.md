# P3-S28–S29 Treasury and Subledger UI Implementation Contract

**Status:** Implemented under the Product Owner’s 2026-10-01 authorization;
focused database acceptance is pending repair of pre-existing reusable-test
migration drift.

## Authorized boundary

The workbenches render existing Tenant-scoped Treasury accounts, movements,
statement imports/lines, exact-match proposals, clearings and retained bank runs;
and AP/AR obligations, allocations, exact as-of aging, retained reconciliations
and write-off proposals. They call only existing audited application services.

Every route resolves the active Organization from authenticated membership/session,
uses the registered permission at the HTTP boundary, scopes tenant objects before
use, and relies on the service to lock/re-authorize lifecycle, SoD, policy,
idempotency and object-scope invariants. POST routes retain Django CSRF protection.

Settlement UI accepts a posted directional Treasury movement only. It does not
select, expose for mutation, or create a cash-account posting; downstream
Accounting-clearing activation remains outside this slice.

## Explicit exclusions

No source recognition adapter, Accounting producer/mapping activation, write-off
approval or reversal, Protected Operation reclassification, threshold, aging
bucket, production activation, legacy `Payment`/claim-settlement cutover/backfill,
external integration, background job, P3-S30+, or `MATERIAL_DOCUMENTS_LINK`
remediation is included.

## UX and evidence

Templates are Persian-first RTL, responsive and keyboard-labelled, retain mixed
numeric LTR presentation and mark IRR. They use CSRF forms and retained history
instead of editable financial evidence. Sensitive bank identifiers are not
rendered. Disabled/unimplemented source, posting and write-off paths are stated
plainly without implying new authority.
