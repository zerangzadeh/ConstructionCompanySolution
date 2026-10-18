# CEP-044-FINDING-001 — write-off source correction lineage

**HISTORICAL BLOCKER-MIGRATION — RESOLVED by HUMAN-CEP044-PERSISTENCE-20261019.**
Original entry finding and failed result below are retained. The authorized
migration-only amendment is recorded in [Amendment provenance](CEP-044_AMENDMENT.json);
it does not approve missing financial lifecycle semantics.

## Requirement and evidence

CEP-044 sections 6/13/23/24 require the governed write-off proposal, approval,
recognition handoff and reversal/correction lifecycle. PD-015 treats write-off as
an auditable economic occurrence with retained source identity and a
correction/reversal path. SPEC-024 requires a new governed occurrence for
reversal/correction and preserved history. The recognition-owner matrix assigns
both write-off and reversal/correction to Subledgers. The session instruction
also explicitly requires corrections/reversals/replacements to preserve lineage.

The local prompt's section 16 says **Migration Impact = NONE**. Execution Policy
section 13 and Playbook section 10 require a stop before an unavoidable schema or
data migration. CEP-043's migration authorization applies only to CEP-043.

Baseline: `main @ f0034b5589a2155547100aeac425f709c5e53722`, equal to
`origin/main` and remote main. Initial working tree/diffs were empty. That commit
contains the completed CEP-043 package despite its `cep-044` message. See
[entry/source identities](CEP-044_ENTRY.json) and
[model/physical-column inspection](CEP-044_REPOSITORY_SEAMS.json).

| Existing persistence | Safe reuse and limit |
| --- | --- |
| `WriteOffProposal` | Immutable proposal, obligation, positive amount, date, reason, actor, tenant and idempotency hash. No predecessor/corrects/supersedes/replacement relation or structured source correction context. |
| `WriteOffDecision` | One retained approval/rejection per proposal; cannot identify a separate replacement proposal. |
| `WriteOffReversal` | One reversal linked to the original decision. Retains actor, effective date, reason and optional journal, but has no replacement-proposal relation. |
| `Obligation` | Immutable upstream Billing/Procurement/Payroll identity/version and original amount. Sharing an obligation does not identify which of several write-offs a later proposal corrects. Rewriting its source snapshot would alter finalized upstream history. |
| `SourceRecognitionDraft.predecessor` | Reusable Accounting target lineage. It cannot establish an AP/AR replacement's authoritative source identity before/without a GL draft, or for a held/rejected replacement. Using it as source correction authority would move ownership into Accounting. |
| Workflow and audit records | Retain coordination, assignment, decisions and audit evidence. No approved contract makes their generic JSON the authoritative AP/AR replacement relation. They must not become a second financial source store. |

Both the Django model definitions and configured loopback Development PostgreSQL
columns confirm the missing source relation. Searches of write-off model consumers
found no separate approved AP/AR correction-link store. The approved consolidated
SPEC-024, PD-015/030, package, IMB records and recognition matrix were recovered
and hashed; no repository-local substitute or no-migration correction contract
was found. This conclusion concerns the write-off correction relation, not a
new financial recognition rule or a generalized AP reversal model.

Reversal alone can retain a link to the old decision. A replacement proposal
cannot retain which prior write-off it corrects using the current domain fields.
A reason-string convention, two unlinked actions, downstream GL predecessor,
or orchestration/audit JSON would not supply the required source-owned lineage.

## Narrow resolution

Authorize the minimum additive **AP/AR-owned write-off correction/replacement
source-lineage persistence**, with the necessary bounded Development /
Non-Production schema migration, and a migration-only amendment to CEP-044 plus
manifest rehash. A nullable predecessor relation on the immutable write-off
proposal is a candidate minimal implementation; exact constraints must be
verified at resumed seam review. Existing rows/history must remain unchanged;
no inferred historical pairing or backfill is authorized by this proposal.

Alternatively, provide an approved existing no-migration source-lineage contract
that meets the same requirements. No Scope/AC/DoD/dependency or financial owner
change, default permission grant, automatic threshold, production action or
generalized correction mechanism is requested. Any newly discovered material
business/financial ambiguity remains a separate stop condition.

The workflow catalog was also inspected. Its absence alone is **not** asserted
as an unavoidable migration: the existing system-catalog admin can provision
code-registered workflow types. No extra catalog migration authorization is
being requested on that basis.

## Result and continuation

AC 1–12: BLOCKED / NOT EXECUTED at package entry, **0/12 PASS**; scoped DoD NOT
MET. No product/model/schema/permission/catalog/tenant data was changed. New
implementation, financial reconciliation, workflow, integration and regression
validation were not executed. No migration or migration rehearsal ran.

Prerequisite baseline only: **8 tests + 28 subtests PASS**. Direct no-argument
approval/reversal calls still fail closed with the existing P3-S27-Q03 guard.
These checks do not satisfy CEP-044 AC or constitute lifecycle runtime evidence.
Existing baseline debt and performance/concurrency UTV remain preserved.

GATE-05 remains NOT_PASSED, exit-only for this package and not this entry blocker.
The serial queue stops on this unresolved migration boundary. Other frontier
candidates are dependency-ready only; independent collision/entry eligibility
has not been established or bypassed. No Git writes, production action, Human
Sign-off or Production Certification occurred.
