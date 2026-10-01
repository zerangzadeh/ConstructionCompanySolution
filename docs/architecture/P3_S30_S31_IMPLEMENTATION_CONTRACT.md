# P3-S30–S31 Reconciliation Control Implementation Contract

**Status:** Authorized by the Product Owner on 2026-10-01; implementation and
focused acceptance are bounded by this contract.

## Authorized outcome

P3-S30–S31 adds immutable, independently reviewed evidence for retained
Treasury-to-GL and AP/AR subledger reconciliation runs. A dedicated reviewer
permission is required for each domain. The reviewer must be an active member of
the same Organization, must have current permission and scope, and must differ
from the run maker. Review locks and re-reads the Organization and run, verifies
the exact retained evidence hash, records a reason and signed evidence hash, and
is idempotent only for the identical request.

Statement duplicate-import acceptance covers the implemented file hash,
provider-row identity, exact-row evidence hash, and request-idempotency controls.
It does not introduce fuzzy matching, tolerances, provider assumptions, numeric
limits, background processing or an override path.

## Ownership and boundaries

- Treasury owns movement, statement, clearing and cash-to-GL reconciliation
  evidence; review never edits movements, mappings, journals or source rows.
- Subledgers own obligations, allocations, aging and subledger reconciliation
  evidence; review never selects or mutates Treasury cash-account postings.
- Accounting remains authoritative for journals and periods. S30–S31 does not
  activate unavailable recognition, settlement posting or write-off paths.
- Independent reconciliation review is not implicitly classified as a Protected
  Operation and does not add a threshold. Its explicit maker-checker rule is
  enforced directly and fail-closed.

## Data, permissions and audit

Two expand-only one-to-one review records preserve Organization, run, reviewer,
reason, retained run hash and signed evidence hash. New dedicated review
permissions are registered and granted only through the normal catalog/default
role mechanism. Review audit events are append-only. No existing retained run or
financial history is changed or backfilled.

## Acceptance

Focused tests cover permission denial, cross-Tenant objects, suspended/cancelled
Tenants, self-review denial, exact idempotency, tamper/hash failure, immutable
review evidence, duplicate statement import controls, CSRF, and RTL/accessibility
rendering. Retained Treasury, Accounting and subledger regressions are run only
to the smallest sufficient scope.

## Excluded

Production activation; legacy `Payment` or claim-settlement cutover/backfill;
external integration; background processing; write-off approval/reversal;
unavailable source recognition or Accounting production; thresholds, tolerances,
limits, currencies or policy invention; P3-S32+; and
`MATERIAL_DOCUMENTS_LINK` remediation.

## Closeout evidence

Implementation added expand-only migrations `organizations.0063`,
`treasury.0007`, `subledgers.0002` and `audit.0045`. Eight focused PostgreSQL
tests passed against an isolated database: independent/idempotent/tamper-evident
cash-to-GL review, exact duplicate statement-import controls, independent and
cross-Tenant-safe AP/AR review, and the retained CSRF/tenant/RTL workbench slice.
Django checks, migration-state checks, targeted Ruff and diff checks passed. The
three retained Treasury, subledger and Accounting regressions subsequently passed
from a clean isolated PostgreSQL database. The earlier apparent stall was test
infrastructure: orphaned diagnostic pytest processes retained a partially
migrated test database, not a Treasury, subledger or Accounting runtime change.
The stale disposable database was recreated after those verified processes ended;
no application-code or test-behaviour change was required. This closes the
P3-S30--S31 acceptance validation gate.
