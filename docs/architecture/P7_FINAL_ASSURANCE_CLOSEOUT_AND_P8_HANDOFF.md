# P7 Final Assurance, Closeout, and P8 Handoff

**Status:** P7-S33–S36 and consolidated P7-S01–S36 Product Owner accepted on
2026-10-04. P7 is complete within its documented non-production boundaries. P8
remains planning authority only; P8 implementation and production activation remain
unauthorized.

## 1. Bounded outcome

P7-S33–S36 closes the implementation tranche through assurance and reconciliation;
it creates no new Payroll calculation, statutory value, filing transport, financial
authority, downstream consumer, or production behavior. The review covers the
accepted Workforce, Timekeeping, Core Payroll, statutory tax/employee-insurance,
payslip, financial-handoff, and audit/history boundaries.

## 2. P7-S33 privacy, retention, export, and access assurance

- Payroll, payslip, statutory, handoff, and their audit permissions remain
  dedicated and default-denied. General Workforce, Project, Accounting, Tenant
  administration, or `audit.view` access grants none of them.
- Generic audit access now separates Core Payroll and statutory audit events:
  `payroll_audit.view` does not reveal statutory events, and
  `payroll_statutory_audit.view` does not reveal Core Payroll events.
- Financial-handoff list/detail access is minimized to the explicitly authorized
  liability, Accounting-source, payment, or Project Cost family. Reconciliation
  permission retains cross-family visibility because reconciliation is its stated
  purpose. Review entry requires the matching family review permission.
- Payslip export remains a dedicated `payslips.export` capability, now uses a
  CSRF-protected POST action, returns only the immutable payslip presentation
  snapshot, and records its content digest and actor in append-only audit history.
  Statutory export continues to require its separate permission and retains an
  immutable schema-pinned artifact, digest, attempt, correlation, status, actor,
  and retry/resolution lineage.
- No Workforce, Timekeeping, Core-result bulk, audit-history, or financial-handoff
  export was added. Those records cannot be exported merely because they can be
  viewed. Existing screens continue to omit unnecessary personal contact data.
- Finalized Payroll/statutory/handoff evidence is immutable and protected from
  deletion through application-layer immutable records and protected references.
  No disposal path was authorized. Numeric legal retention periods and official
  filing-retention requirements remain unresolved external-authority inputs, so
  production activation fails closed rather than inventing a duration.

## 3. P7-S34 historical rule/version and retroactivity assurance

Historical results remain bound to the effective pay configuration, Payroll rule,
input snapshot/digest, monetary-policy versions and snapshot, statutory policy and
schema versions, identity evidence, source versions, and correction lineage selected
for that run. Later catalogue, rule, policy, or presentation changes do not
reinterpret a locked run.

Retroactivity remains explicit: an adjustment/off-cycle/replacement run records the
new fact and source; reversal creates a linked negative mirror; statutory correction
and cancellation create successors; financial proposals require the corresponding
replacement/reversal lineage. No service silently edits finalized history or
back-applies a later rule. Missing/stale authority, mapping, identity, allocation,
acknowledgment, or policy evidence remains a visible fail-closed exception.

## 4. P7-S35 reconciliation, golden cases, concurrency, and no-effects

The retained P7 modules cover effective-version selection, snapshot independence,
Decimal and final-boundary rounding, positive and negative component effects,
missing-input/authority/schema failure, adjustment/reversal/replacement, independent
tax and employee-insurance calculations, schema output and reconciliation, all four
financial-handoff families, Project Cost minute/amount conservation, Tenant and
project scope, and immutable evidence.

Current focused validation added privacy regression coverage for audit-domain
separation and family-minimized handoff visibility. The final four-test boundary
set passed in 11.83 seconds, including the real two-thread financial-handoff
idempotency race and CSRF-protected payslip export. An eight-test golden/history/
reconciliation set passed in 17.23 seconds. Targeted Ruff passed. The normal
migrated-schema run was stopped during unusually long test-database setup without
producing a test result; accepted clean-schema and focused PostgreSQL evidence from
S13–S32 remains the migration baseline, and this tranche introduces no migration.
The two successful focused sets reused the existing PostgreSQL test schema with
`--nomigrations` after `makemigrations --check --dry-run` reported no drift.
The seven-test audit regression module also passed in 10.65 seconds; Django system
check and targeted whitespace checks passed.

The no-effect assertions remain unchanged: Payroll creates no AP/subledger
obligation, Accounting journal/GL entry, Treasury movement/payment/cash effect,
Project Cost actual, contract/budget/schedule mutation, or live statutory filing.
Downstream acknowledgments and reconciliations are evidence only and never confer
downstream approval authority.

## 5. Product Owner acceptance and P7-S36 readiness disposition

The Product Owner accepts P7-S33–S36 based on this packet, focused PostgreSQL
validation, and retained P7 regression evidence. This consolidates P7-S01–S36 as
accepted and closes P7 within its documented non-production boundary. Acceptance
covers the privacy/access/export controls, retention/evidence posture, immutable
version-pinned history, explicit correction/reversal/replacement lineage,
reconciliation, idempotency/concurrency, golden cases, downstream no-effects, and
the bounded P8 planning handoff.

Accepted validation evidence is: privacy/export/concurrency `4 passed`; golden
history/reconciliation `8 passed`; audit regression `7 passed`; Django system check
passed; migration drift none; targeted Ruff passed; and whitespace/diff validation
passed. The interrupted normal migrated-schema test setup is not recorded as passed
and is not an acceptance blocker: this tranche introduced no migration, drift is
absent, accepted P7-S13–S32 clean-schema evidence remains applicable, and affected
runtime/regression validation passed.

P7 is not production-ready for real statutory or financial execution. Activation
remains blocked by authoritative Iranian tax/insurance values and interpretations,
Article 38 and statutory-retention interpretation, official schemas/identifiers and
calendar/file/deadline/provider contracts, credentials/provider operations,
production security/operations evidence, and separately authorized downstream
recognition or execution. Existing technical-register issues remain separate and
unresolved.

## 6. Bounded P8 handoff

P8 may begin only after explicit Product Owner authorization. Its entry packet must
confirm Inventory/Equipment/Fixed Asset ownership and the Product Owner gates for
valuation method, traceability depth, capitalization/depreciation policy,
maintenance ownership, expiry policy, and spare-parts usage. It must preserve P7
Payroll and labor-distribution lineage as read-only source evidence and must not
reinterpret Payroll results, create Project Cost actuals from P7 proposals, or treat
P7 acceptance as authority for inventory valuation, asset accounting, GL posting,
or production activation. No P8 code, schema, permission, UI, or runtime behavior is
part of this tranche.
