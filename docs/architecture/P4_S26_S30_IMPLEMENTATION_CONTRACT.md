# P4-S26–S30 Expense Controls Implementation Contract

**Authorized:** 2026-10-01. **Boundary:** P4-S26 through P4-S30 only. P4-S31+
is not authorized.

## Delivered sessions

| Session | Delivered runtime | UI availability |
| --- | --- | --- |
| P4-S26 | Compatible `draft`, `submitted`, `approved`, `returned`, `void` lifecycle; legacy `recorded` history retained; dedicated permissions, row locking, audit and direct maker/submitter versus approver separation. | Expense list, draft form, detail and transition controls. |
| P4-S27 | Required retained source reference and SHA-256 identity, active-source duplicate rejection, Tenant-local idempotency keys and protected historical actor/timestamp evidence. Existing typed DMS links remain available and append-only. | Source identity is captured and shown on the detail view. |
| P4-S28 | Positive immutable splits across explicit Project, WBS, optional Activity, leaf CBS and policy-required CostCenter; governing accepted-budget identity and allocation-basis reference are pinned; split total must exactly equal expense amount. | Permission-scoped split grid on the expense detail view. |
| P4-S29 | Tenant/project-scoped weekly or monthly templates; a manual occurrence request creates exactly one reviewable draft. No scheduler, automatic approval, posting or financial handoff exists. | Template list/create and manual proposal action. |
| P4-S30 | Submission rechecks the current governing accepted budget under lock and records immutable matching-budget/prior-approved/proposal/remaining evidence. Approval is operational evidence only. | Advisory budget evidence and explicit unresolved-policy notice on the detail view. |

## Fail-closed gates and bounded authority

- P4-G01–G04 provide no coefficient, rate, price-book or spreadsheet authority.
- P4-G06–G09 are consumed only through the already accepted governing budget,
  its locked versioned structure and exact currency-free stored amounts. No new
  budget acceptance, rebaseline, FX or rounding authority is inferred.
- P4-G10 remains open. `is_overrun` and `remaining_after_proposal` are retained
  evidence in `advisory_only` mode; they do not warn, block, reserve or authorize.
- P4-G11–G18 remain unavailable. Expense controls do not read schedule, risk,
  delay, change, contractual-impact, rebaseline, earned-value, forecast or
  candidate-baseline facts as authority.
- Expense approval creates no AP obligation, GL journal, Treasury movement, cash
  settlement, contract change, schedule mutation, budget-baseline mutation,
  forecast, or Project Cost fact. Future handoffs require their own approved,
  versioned producer contracts and reconciliation policy.

## Invariants and reconciliation boundary

Every mutation resolves an active membership and project scope. Submission locks
the expense and governing budget-control rows, rejects stale coding and requires
exact allocation conservation. Approval rechecks conservation and forbids the
creator or submitting actor. Source and occurrence uniqueness are database-backed;
recurrence retries and request retries return their existing draft. Budget
assessments and allocations are immutable evidence. Voids preserve original
amount, coding, source and audit history.

## Deferred remainder

P4-G10 warning versus hard-stop behavior, period-close enforcement, automatic
recurrence scheduling, AP/employee/vendor settlement completion, accounting and
cash posting, Project Cost producer activation, and P4-S31+ control UI/export work
remain blocked. Tax/e-invoice classification remains «نیازمند بررسی قانونی» until
a separately approved rule version exists.
