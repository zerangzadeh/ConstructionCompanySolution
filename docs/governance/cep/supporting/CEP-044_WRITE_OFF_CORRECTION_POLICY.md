# HUMAN-CEP044-CORRECTION-20261019

Source: explicit Human Product Decision in this CEP-044 continuation.
The governing decision below is retained verbatim. Development / Non-Production only.

---

Human Product Decision for CEP-044 — Finding002

APPROVED, with the following governing clarifications.

1. Correction model

A finalized/approved AP/AR write-off is never edited in place.

A correction uses:
    original write-off
        → full reversal of that exact write-off occurrence
        → replacement write-off occurrence, when a replacement remains required.

This is an atomic correction set.

“Full reversal” means reversal of the exact prior write-off effect being corrected.
It does NOT mean reversal, cancellation, deletion, or recreation of the underlying
AP/AR obligation itself.

2. Replacement amount

The prior write-off occurrence is reversed in full.

If the corrected outcome still requires a write-off, create a new replacement
write-off for the corrected governed amount.

Do not implement a hidden delta-edit against the original write-off.

If the corrected outcome requires no write-off, the correction may end with the
full reversal and no replacement.

3. Correction date

Every correction requires one explicit correction effective date.

The reversal and its replacement, if any, use that same correction effective date
for the correction event set.

Do not rewrite:
- the original obligation recognition date;
- the original write-off effective date;
- earlier historical/as-of facts.

The correction becomes effective prospectively from the explicit correction date.

If a required Accounting effect cannot legally/technically use that date because
the applicable fiscal-period contract fails, fail closed. Do not silently move the
correction into another accounting date or period.

4. Atomicity

The complete correction must execute transactionally.

Lock and re-read the affected:
- Tenant/scope authority;
- obligation;
- original active write-off;
- applicable correction/reversal lineage;
- relevant downstream Accounting evidence where required.

Then either:

    reversal + replacement + lineage + audit + required Accounting effects
    all commit,

or:

    none commit.

A partial financial correction is forbidden.

5. Lineage

Persist explicit immutable lineage:

    obligation
      → original write-off
      → reversal
      → replacement, if any

Retain:
- original source/write-off identity;
- predecessor/reversal/replacement identity;
- actor and timestamp;
- explicit correction date;
- reason;
- amount;
- applicable source/version;
- policy/mapping evidence;
- Accounting occurrence/journal identity where applicable.

Never delete or overwrite the original finalized occurrence.

6. Idempotency and concurrency

One governed correction economic occurrence may create at most one successful
reversal/replacement set.

Exact replay returns/reuses the existing result.

Same correction identity with conflicting payload fails closed.

Concurrent correction attempts must not create:
- duplicate reversal;
- duplicate replacement;
- over-write-off;
- overlapping active correction chains.

7. Permission and Self-Approval

Use the already accepted AP/AR authorization policy.

Do not create new role semantics or approval thresholds.

Specifically:
- proposal/default grants remain as already governed;
- approval/reversal require the existing explicit scoped permissions;
- Platform/Tenant Self-Approval policy remains authoritative;
- distinct persons are required only where the effective policy or an explicitly
  classified Protected Operation requires them;
- write-off, reversal, or correction must NOT be newly classified as Protected
  Operations merely by CEP-044;
- Owner/Admin/job title provides no implicit bypass.

Missing permission/policy/scope authority fails closed.

8. Accounting boundary

AP/AR remains authority for the write-off occurrence.

Accounting remains authority for journal/final GL effects.

Where CEP-044’s approved recognition producer requires Accounting effects,
the write-off reversal must reverse the exact original Accounting occurrence and
the replacement must create the corresponding governed replacement effect.

Do not:
- edit an existing posted journal;
- create a generic Subledger→GL writer;
- infer missing accounts/mappings;
- select fallback accounts.

Missing mapping or invalid fiscal-period authority fails closed.

9. Settlement / Treasury boundary

This decision does not authorize AP/AR to mutate Treasury cash facts.

If an active downstream dependency makes the proposed write-off correction
inconsistent or unsafe, apply the existing domain guard and fail closed rather
than automatically reversing another domain’s authoritative fact.

10. As-of behavior

Historical reports before the correction date continue to reflect the facts that
were effective at those dates.

From the correction effective date onward, reconciliation and aging must reflect
the reversal/replacement set without double counting.

11. Scope of this decision

This decision resolves only CEP-044 Finding002’s write-off financial correction
boundary.

It does not authorize:
- automatic write-off;
- materiality or monetary thresholds;
- new approval depth;
- new Protected-Operation classification;
- source obligation rewriting;
- Treasury mutation;
- new Accounting mappings;
- unrelated Scope/AC/DoD/dependency changes;
- Production actions.

Record this as the governing CEP-044 correction contract with provenance.
Update the applicable canonical prompt/source reference and hash only as required
without changing unrelated CEP semantics.

Then resume CEP-044 implementation, validation, AC/DoD evaluation, Registry/evidence
updates, and serial execution under the already authorized Development /
Non-Production authority.

GATE-05 remains NOT_PASSED unless independently proven under its canonical criteria.