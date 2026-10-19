# Human authorization — Legacy Payment retirement

Source: Product Owner / Human Decision Authority instruction supplied in this
session on 2026-10-19, baseline `main @ 45a06ad`.

Legacy `payments.Payment` is deprecated and outside the target architecture.
Treasury is the sole current cash authority. All existing Legacy Payment rows are
seed/demo/test data; the authoritative historical migration population is **zero**.
No historical Treasury movement, GL entry, or opening balance may be fabricated.
The earlier requirement for a real migration dataset is superseded for this scope.

Authorized: bounded Development/non-production remediation of all active Payment
writers/readers, Billing settlement dependencies, DMS references, reports, UI,
permissions, seeds and tests; recovery checkpoint; minimum necessary Development
schema/data migrations; empty-database migration proof. Reconcile only directly
affected CEP-028/IMB-0050 and CEP-064/IMB-0049/0051 canonical artifacts. Preserve
dependency semantics and unrelated Product Decisions, AC and DoD.

Destructive Development retirement is conditional on all twelve retirement
readiness conditions passing. Before destructive database mutation, create and
verify a recoverable Development database checkpoint. Preserve audit/document
interpretability. `treasury.PaymentRequest` remains part of the product.

Git authority: safe attributable `git add`, `git commit`, `git push origin main`.
Work on existing local main. No branch/worktree, merge/rebase/reset/clean/stash,
force-push, production action, CEP-069..079 execution, Human Sign-off or Production
Certification. Continue bounded work without routine confirmation; stop for a new
material business/security/financial decision, unsafe repository state, or
production boundary.

## Exact Human readiness gate (follow-up instruction)

The twelve remediation areas are a work plan, not this gate. All conditions below
must PASS; any FAIL or UNVERIFIED means readiness FAIL and destructive
model/table/app removal remains blocked.

1. Zero active runtime writers to Legacy Payment, including create/void/allocation.
2. Zero active business/reporting readers from Legacy Payment.
3. Zero unresolved required FK/generic/document references; approved disposition
   or replacement for Billing, DMS and other required references.
4. Approved Treasury/Subledger settlement flows replace PaymentAllocation.
5. Behavioral/reconciliation proof of no Payment + Treasury double counting.
6. Payment permissions/routes/forms/templates/navigation have no required active
   consumer; compatibility surfaces require explicit transitional evidence purpose.
7. Current-operation seed/demo fixtures use Treasury-approved flows.
8. Required transition-test coverage is retained or replaced with focused/regression
   coverage.
9. Retained audit/document identifiers remain interpretable and traceable after
   application-code removal.
10. Full migration graph builds successfully from an empty database with the
    retirement changes.
11. Django/system checks, migration checks, focused tests and affected regression
    PASS; no required validation remains FAIL or UNVERIFIED.
12. Verified Development database rollback/recovery checkpoint before destructive
    database mutation; Git alone is insufficient.

Only all12 PASS permits `LEGACY_PAYMENT_RETIREMENT_READINESS = PASS` and destructive
Development retirement. After removal repeat empty-database migration, focused
and affected regression, Django/system and drift checks, repository/runtime
reference search, Billing/Treasury/Subledger replacement flows, no double counting,
and audit/document interpretability. Only all required post-removal checks PASS
permits `LEGACY_PAYMENT_RETIREMENT_COMPLETE = YES`.
