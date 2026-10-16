# CEP-006 Control-Account Mapping Decision

**Historical status:** Product Decision preparation only — no implementation authorization

**Historical CEP-006 state:** `EXECUTION PARTIAL` (`CEP-006-FINDING-003 / BLOCKER-PD`)

**Scope:** Determine the missing AP/AR Subledger-to-Accounting control-account
contract required by `subledger_gl`. This document creates no mapping, posting
flow, migration, or financial authority.

## A. Executive blocker

There is no authoritative persisted rule that identifies the Accounting control
account for an `apps.subledgers.models.Obligation`.

`Obligation` records its organization, direction, immutable source identity,
currency (currently constrained to `IRR`), and an optional
`recognition_journal`. It has no control-account reference, mapping-version
reference, account allocation, or account-selection policy. The current
reconciliation service deliberately records `CONTROL_MAPPING_NOT_APPROVED` for
an obligation with a recognition journal and retains `linked_gl_total = 0`.

Consequently, selecting an account from a journal line, account name, account
code, or current chart would create financial semantics that have not been
approved. `CEP-006` cannot construct an authoritative `subledger_gl` direct
source until the Human Decision Maker approves a mapping contract.

## B. Current AP posting path

Representative supported AP source: approved Billing payable certificate.

```text
PayableCertificate (approved)
  -> billing.payable_handoffs.resolve_payable_certificate_obligation_source()
  -> ObligationSourceSnapshot(direction=payable, source_kind=billing.payable_certificate.v1)
  -> subledgers.recognize_obligation()
  -> Obligation
  -> [no AP posting request and no account selection]
```

The handoff is explicitly dormant and only registers a source resolver. The
resolver validates tenant, approval state, `IRR`, amount, party, project, and
contract context; it does not return an account or mapping identity.
`recognize_obligation()` creates only an Obligation and audit event. It does
not call Accounting, the Posting Registry, or a journal service.

The Accounting Posting Registry has a code-owned contract for
`billing.payable_certificate.v1/certificate_approved`, rule
`billing.payable-certificate.approved.v1`, but marks it
`operational_producer=False`. The contract identifies the Billing source and
rule version only; it contains no GL account selection.

Therefore the current AP control-account selection is absent: it is neither
explicit, deterministic, persisted, versioned, nor reusable by reconciliation.

## C. Current AR posting path

Representative supported AR source: approved Billing progress claim.

```text
ProgressClaim (approved)
  -> billing.handoffs.resolve_progress_claim_obligation_source()
  -> ObligationSourceSnapshot(direction=receivable, source_kind=billing.progress_claim.v1)
  -> subledgers.recognize_obligation()
  -> Obligation
  -> [no AR posting request and no account selection]
```

This is also a dormant source-resolver handoff. It validates the approved
source and creates the same immutable obligation evidence without invoking
Accounting.

The Posting Registry has a code-owned but non-operational contract for
`billing.progress_claim.v1/claim_approved`, rule
`billing.receivable-claim.approved.v1`. It has no account field or mapping
lookup.

Therefore the current AR control-account selection is absent: it is neither
explicit, deterministic, persisted, versioned, nor reusable by reconciliation.

## D. Existing mapping candidates

| Candidate ID | Model / service / configuration and persisted path | Owner, scope, versioning, tenant, currency, direction, history, posting usage | Can determine `control_account`? |
| --- | --- | --- | --- |
| C-01 | `subledgers.Obligation.recognition_journal` -> `accounting.JournalEntry` | Subledgers owns the link. It is tenant-validated and one journal may be linked to one obligation. It has no effective date, mapping version, AP/AR account field, or allocation. Journal currency is currently `IRR`; obligation direction is retained. The link is historical evidence only and is not used for posting or account selection. | **NO** — a journal can have several lines and no line is identified as the control line. |
| C-02 | `accounting.JournalLine.account` -> `accounting.Account` | Accounting owns the posted line. Account is tenant-scoped; journal and account are tenant-validated. Journal lines retain debit/credit, party and dimensional evidence, but no AP/AR direction, mapping version, effective date, or obligation allocation. A journal can have multiple lines/accounts. | **NO** — posted journal evidence does not declare a future or reconciliation control-account policy. |
| C-03 | `accounting.posting_registry._CONTRACTS` Billing entries | Accounting owns a code-owned, versioned source/event contract. Billing AP and AR contracts are source-family scoped and tenant-neutral code. Both are `operational_producer=False`; neither has currency, account, allocation, effective dating, historical pinning, or account lookup. | **NO**. |
| C-04 | `accounting.recognition_registry._POLICIES` | Accounting owns a frozen code policy registry. It says an Accounting draft occurs only when a matrix/mapping is active, and names the desired reconciliation relationship. The module states that it has no persistence or posting side effects. It has no account identity, mapping scope, effective date, allocation, or historical pin. | **NO** — it records a prerequisite, not the mapping. |
| C-05 | `treasury.TreasuryAccountMappingVersion` | Treasury owns a persisted, immutable, tenant-scoped, effective-dated and versioned mapping from a Treasury account to cash and clearing ledger accounts. It is approved and used by Treasury posting. It has no AP/AR source, obligation, party, document-family, or allocation semantics. | **NO** for AP/AR — it is authoritative only for Treasury cash/clearing mapping. |
| C-06 | Billing source snapshots and registered source resolvers | Billing owns approved document/source-family evidence. The snapshot supplies organization, source version, party, project, contract, `IRR`, amount, and AP or AR direction. It has no account identity, account policy, or allocation rule. | **NO**. |
| C-07 | `accounting.Account` chart | Accounting owns a tenant-scoped chart and posting-account validation. Account type and use in journal history are retained, but the chart carries no relation to an Obligation, AP/AR direction, source family, party, project, or mapping policy. | **NO**. |

No Organization accounting configuration or AP/AR posting service provides an
additional candidate. The existing Treasury mapping pattern demonstrates the
required qualities of a mapping record, but cannot be repurposed as AP/AR
authority.

## E. Single-vs-multi-account analysis

**Current result: UTV (unverified).**

The repository has no rule establishing that an obligation maps to one or to
multiple control accounts. Each Obligation currently has one source identity
and may link to one recognition journal, while a JournalEntry may have many
JournalLines and accounts. Neither fact establishes a control-account grain.

The Billing handoffs currently reject a `source_line_key`, so their existing
AP and AR sources are document-level obligations. They do not express a split
or multiple-control-account rule. A future multi-account design would require
an explicit allocation identity and rule; it cannot be inferred from journal
lines.

## F. Allocation analysis

No authoritative allocation rule exists.

There is no persisted allocation by obligation line, source type, tax,
retention, advance, currency, project, party, or accounting policy. Existing
`SettlementAllocation` allocates a Treasury settlement to an Obligation; it is
not an allocation of an Obligation across GL control accounts.

No allocation percentage, balance basis, debit/credit sign, or remainder rule
may be introduced for `CEP-006` without a Human Product Decision.

## G. Historical evidence/backfill

| Existing historical condition | Classification | Reason and permitted treatment |
| --- | --- | --- |
| Obligation has no `recognition_journal` | **UNBACKFILLABLE-WITHOUT-INFERENCE** | No posted-account evidence exists. Retain the obligation and existing reconciliation exception; do not assign a current mapping retrospectively. |
| Obligation links to a journal with one or more journal lines | **LEGACY-UNVERIFIED** | The journal and lines are exact evidence of what was posted, but there is no retained declaration identifying a line as the obligation's control account or an approved mapping policy. Do not derive a canonical mapping from those lines. |
| A future approved mapping version is pinned to a newly recognized obligation and the resulting journal line is linked by the approved contract | **EXACT-HISTORICAL-EVIDENCE** | This is possible only after the decision, schema, and controlled posting/reconciliation contract are implemented. |
| Historical source carries a separately retained approved mapping version and account identity | **DERIVABLE-WITH-CANONICAL-EVIDENCE** | No current AP/AR record has this evidence. A future bounded migration may classify only such records; it may not use current mapping values as historical facts. |

Existing reconciliation runs remain immutable evidence of their zero GL total
and exception snapshots. They must not be rewritten to make a later mapping
appear historical.

## H. Product Decision options

### PD-006-CAM-01 — organization and direction default

- **Mapping scope:** organization + AP/AR direction.
- **Control-account identity:** one Accounting-owned, tenant-scoped Account per
  effective mapping version.
- **Single vs multiple / allocation:** one account per obligation; no allocation.
- **Version/effective date:** immutable version records with an effective interval.
- **Historical pinning:** pin mapping version and Account to new Obligations;
  retain old records as the classifications in section G.
- **Schema / migration:** required for mapping versions and obligation pins;
  data migration only for nonfinancial provenance/classification.
- **Posting / reconciliation:** a separately authorized posting producer reads
  the pin; reconciliation reads that same pin and qualifying journal evidence.
- **Existing journals:** preserved as legacy evidence; never used to select the
  default.
- **No-inference risk:** low after approval, but it assumes a single organization
  default is valid for all source families. The repository provides no evidence
  for that assumption.

### PD-006-CAM-02 — source-family and direction mapping (recommended)

- **Mapping scope:** organization + obligation `source_kind` + AP/AR direction.
  `source_kind` and direction are already immutable Obligation identity/context.
  Currency is currently constrained to `IRR`; it is retained as evidence, not a
  new mapping dimension unless separately approved.
- **Control-account identity:** an Accounting-owned, tenant-scoped Account held
  by an immutable, approved mapping version. The decision must state the exact
  permitted Account types for payable and receivable mappings.
- **Single vs multiple / allocation:** one control account per Obligation and
  no account allocation. A split requires separately authorized source/obligation
  identities and a later explicit allocation contract.
- **Version/effective date:** immutable versions with non-overlapping effective
  intervals for the same scope; the selected version and account are pinned on
  each new Obligation.
- **Historical pinning:** new records retain the selected mapping version and
  Account; records that lack those fields retain section G classifications.
- **Schema / migration:** required. A data migration may create only the
  nonfinancial legacy provenance marker already authorized for CEP-006; it must
  not assign financial account identity to legacy records.
- **Posting / reconciliation:** a future separately authorized AP/AR producer
  selects the mapping once and pins it. Reconciliation reads the pinned
  evidence; it does not maintain a second mapping lookup.
- **Existing journals:** compatible as immutable journal evidence only.
- **No-inference risk:** low after approval. It makes the source-family scope
  explicit rather than assuming one account covers every AP or AR occurrence.

### PD-006-CAM-03 — direct account selected for each Obligation

- **Mapping scope:** individual Obligation.
- **Control-account identity:** an Accounting Account supplied during
  recognition and pinned on the Obligation, with no reusable mapping policy.
- **Single vs multiple / allocation:** one account; no allocation.
- **Version/effective date:** the account pin is historical, but no effective
  mapping version exists.
- **Historical pinning:** possible only for new records; section G remains for
  legacy records.
- **Schema / migration:** required; migration remains provenance-only.
- **Posting / reconciliation:** both consume the direct pin.
- **Existing journals:** preserved as evidence only.
- **No-inference risk:** account selection remains undefined at recognition and
  can become a second Subledger-owned financial policy. This conflicts with the
  preferred Accounting-owned contract.

### PD-006-CAM-04 — multi-account obligation allocation

- **Mapping scope:** unresolved; would require an allocation-slice identity.
- **Control-account identity:** multiple Accounting Accounts per Obligation.
- **Single vs multiple / allocation:** multiple accounts; allocation basis,
  signs, amounts, revisions, and rounding are all currently absent.
- **Version/effective date, historical pinning, schema, migration, posting, and
  reconciliation:** each requires substantial new behavior and evidence.
- **Existing journals:** cannot safely supply those rules.
- **No-inference risk:** high. This option is not sufficient to unblock
  CEP-006 without a separate financial-allocation Product Decision.

## I. Recommended option

Recommend **PD-006-CAM-02**, conditional on an explicit Human decision that
selects its exact scope and account eligibility rules.

It uses two existing immutable Obligation dimensions (`source_kind` and
`direction`), makes Accounting the owner of account identity and versioned
policy, pins the selected policy for new historical evidence, and gives Posting
and Reconciliation one shared source. It does not assume that a Billing payable
certificate, a future procurement AP source, and an AR claim must share a
single organization-wide account.

This recommendation is an architecture proposal, not a finding that the
repository already authorizes source-family mappings.

## J. Exact Human Decision required

Approve or reject the following bounded Product Decision:

```text
PD-006-CAM-02

1. Accounting owns an immutable, approved AP/AR control-account mapping version.
2. Mapping key: organization + Obligation.source_kind + Obligation.direction.
3. A mapping version identifies exactly one tenant-scoped Accounting Account.
4. The Human Decision states the permitted Account type for PAYABLE and
   RECEIVABLE mappings and nominates the account(s) for each initial source scope.
5. Mapping versions have non-overlapping effective intervals and are selected
   at Obligation recognition.
6. Each new Obligation pins its selected mapping version and Account.
7. One Obligation has one control account. No account allocation is authorized.
8. A split needs separately authorized source/obligation identities and a
   later Product Decision; it cannot be produced by CEP-006.
9. Existing Obligations and Reconciliation Runs receive no inferred financial
   account. They retain the section G legacy classifications.
10. A future authorized AP/AR posting producer and CEP-006 reconciliation use
    the same pinned mapping evidence. This decision does not activate posting.
```

If the Human chooses another option, the decision must state the same ten
points for that option, including exact mapping key, control-account identity,
account eligibility, effective dating, pinning, allocation, and legacy
treatment.

## K. CEP-006 implementation consequence

Until section J is explicitly authorized, `CEP-006` remains
`EXECUTION PARTIAL`. No schema or data migration may be created, and
`subledger_gl` must continue to fail closed.

After approval, the expected bounded CEP-006 implementation surface is:

```text
Accounting-owned mapping model/service and permission/audit contract
Subledger Obligation mapping/account historical pins
Schema migration and authorized provenance-only legacy migration
Mapping selection validation at recognition
Reconciliation reading pinned account evidence
Focused tenant, authorization, effective-date, historical, and reconciliation tests
```

An AP/AR operational posting producer remains outside this CEP unless separately
authorized. The implementation must not synthesize journal entries merely to
make reconciliation totals pass.

## L. Resume conditions

CEP-006 can resume only after all of the following are available:

1. The Human Decision Maker approves one option with the exact mapping and
   account-eligibility rules in section J.
2. The approval expressly authorizes the resulting schema and migration scope.
3. The canonical CEP-006 artifact set is reconciled to that approval without
   conflict.
4. The actual touch set, migration plan, tenant/permission controls, legacy
   classifications, and focused acceptance evidence are re-grounded.

`CEP-009`, `CEP-011`, and `CEP-013` remain `NOT STARTED`.

## M. Resolution record — 2026-10-15

The Human Decision Maker approved the recommended `PD-006-CAM-02` in the
subsequent final resume authorization. The approved canonical decision is
[PD-034](../../../architecture/BONIRA_PD_034_CONTROL_ACCOUNT_MAPPING.md). Therefore
`CEP-006-FINDING-003 / BLOCKER-PD` is **RESOLVED BY APPROVED CONTROL-ACCOUNT
PRODUCT DECISION**. This preparation record remains historical evidence of why the
decision was necessary; it is not rewritten as if the mapping had always existed.
