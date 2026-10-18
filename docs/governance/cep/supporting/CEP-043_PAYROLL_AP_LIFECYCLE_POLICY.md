# CEP-043 Payroll → AP lifecycle policy

Status: APPROVED. Authority: Human Product Decision in this chat, 2026-10-18.
Decision: `HUMAN-CEP043-LIFECYCLE-20261018`. This policy resolves Finding002;
it supplements the existing frozen PD-009/030 and SPEC-029 without changing their
recognition ownership, CEP Scope/AC/DoD or dependency graph.

## A. Enrollment

AP/Subledger owns enrollment approval and activation. Payroll review/finalization
establishes source correctness/eligibility only; it never approves, recognizes or
finalizes AP obligations. Active enrollment permits AP consumption only of the
governed eligible finalized Payroll source categories.

Activated configuration is versioned and immutable. Material changes require a
new prospective version/time. Changes never rewrite finalized Payroll evidence,
created obligations, prior enrollment/version lineage or reconciliation history.
Withdrawal/deactivation prevents new consumption from its effective point; it
does not cancel, reverse, delete or modify existing obligations. Existing targets
retain exact source and enrollment versions.

Approved proposal A also applies: explicit AP preparation/approval capabilities
are default-denied in the existing permission system; no additional person-level
separation beyond existing protected-operation policy. Configuration pins exact
classification/source scope and explicit party/payee, recognition/due-date and
grouping evidence. No inferred family, payee, dates or aggregation. No actual
mapping rows are seeded; actual activation requires EXT-0013 evidence.

## B. Correction, reversal and replacement

Corrected/reversed/replacement finalized Payroll evidence must resolve exact prior
AP targets through retained source/version lineage. Payroll never directly edits,
finalizes, settles, pays or deletes AP obligations. AP owns all AP lifecycle effects.
Finalized AP history is immutable: explicit correction/reversal/replacement only.

Without active downstream consumption that prevents safe correction, AP may
record its governed correction/reversal and an eligible replacement AP draft.
Lock/re-read sources and targets; retain predecessor/reversal/replacement pins;
commit the entire required replacement set or none. Concurrent/replayed execution
cannot duplicate payable obligations. Replacement remains a draft until normal
AP-owned recognition/finalization. Ineligible corrected sources produce no
replacement payable merely to preserve count.

Consumed means an active authoritative downstream dependency, including applicable
settlement/payment allocation, Treasury consumption, write-off, Accounting
recognition/posting or another authoritative financial fact. Consumed targets
fail closed. No deletion/overwrite or automatic downstream unwind is allowed.
The owning domain must unwind its effect before AP replacement proceeds.

Idempotency uses source/revision/economic identity: exact replay returns existing
results; conflicting payload for the same identity fails closed. Reconciliation
retains source/version → enrollment version → AP original → AP correction/reversal
→ optional replacement. Approved proposal B adds explicit AP source-reverse
authority, exact inverse amount/currency, explicit effective date/reason, no
reversal before downstream unwind effective dates and no period of duplicate
active payables. Missing/unsupported cases fail closed, without negative payable,
cash reversal, inferred write-off or duplicate GL recognition.

## Boundary

Only missing CEP-043 lifecycle semantics are resolved. No Payroll approval of AP,
Treasury/cash action, Accounting posting, automatic downstream reversal, pricing,
statutory, unrelated Scope/AC/DoD/dependency or production authority is granted.
Existing bounded Development/Non-Production migration authorization applies.
GATE-05 stays NOT_PASSED. No Git writes.
