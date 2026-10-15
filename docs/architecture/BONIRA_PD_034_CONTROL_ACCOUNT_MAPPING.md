# PD-034 — AP/AR control-account mapping

**Decision authority:** Human Decision Maker, “BONIRA — CEP-006 CONTROL ACCOUNT DECISION APPROVAL AND FINAL RESUME,” 2026-10-15.

**Decision status:** APPROVED for bounded CEP-006 implementation semantics. This is a successor record and does not alter the sealed `BONIRA-PD-FREEZE-v1.0` register or the separate PD-032 freeze.

**Register identity:** The available repository decision records end at PD-033. PD-034 is therefore the next verified available Product Decision ID. This record is additive and does not rewrite prior decision artifacts.

**Scope:** CEP-006 / IMB-0044, IMB-0048 and IMB-0066 only. The 16 Acceptance Criteria, scoped Definition of Done, CEP graph, financial authority, and non-production boundary remain unchanged.

## Approved decision: PD-006-CAM-02

Accounting owns an immutable, effective-dated, tenant-scoped control-account mapping policy with this selection key:

```text
Organization + source_kind + AP/AR direction + effective period
```

Each applicable new AP/AR Obligation resolves exactly one effective mapping before any GL posting or reconciliation use. The resolved Accounting `Account` and immutable mapping version are pinned on that Obligation as historical evidence.

```text
Accounting mapping policy
→ Obligation account pin
→ Posting account selection
→ Journal evidence
→ Reconciliation account slice
```

One Obligation has one pinned control account for this V1 dimension. Multi-account allocation, percentage rules, account inference, chart redesign, and activation of a new operational producer are not authorized.

## Required controls

- Mapping intervals for the same organization, source kind and direction must not overlap.
- Mapping lookup is deterministic by organization, source kind, direction and effective date; a missing or ambiguous result fails closed.
- The mapped Account must be a tenant-owned active posting account.
- Posting and reconciliation consume the Obligation’s historical pin. They do not independently select from a current mapping or journal history.
- Existing obligations and retained runs without a canonical pin remain `legacy_unverified`; no account identity may be backfilled from current configuration, names, codes, or journals.

## Disposition

`CEP-006-FINDING-003 / BLOCKER-PD` is **RESOLVED BY APPROVED CONTROL-ACCOUNT PRODUCT DECISION**. It does not approve CEP-009, CEP-011, CEP-013, Human Sign-off, production deployment, production migration, production cutover, or financial correction.
