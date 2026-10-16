# BONIRA — Codex Project Execution Policy

**Status:** ACTIVE  
**Role:** Detailed repository execution policy  
**Scope:** Entire BONIRA repository  
**Default execution branch:** `main`

## 1. Purpose and non-authority

This policy answers: **How may Codex operate in this repository?** It owns
generic repository execution, Git, working-tree, queue, validation, evidence,
efficiency, and communication controls.

This policy does **not** define:

- CEP Scope, Acceptance Criteria, or Definition of Done;
- package-specific migration or evidence requirements;
- live CEP lifecycle, authorization, Gate, UTV, or execution-frontier state;
- Human Authorization, Human Sign-off, or Production Certification;
- Roadmap direction, dependency design, or Product Decisions.

Those belong to the authorities identified below. An explicit, bounded Human
Authorization may override a generic rule only for the specific operation it
names. Silence and historical authorization are not overrides.

## 2. Governance precedence and responsibilities

Use the following responsibility model:

1. `docs/governance/CEP_PROGRAM_AUTHORITY.md` defines the source hierarchy.
2. `Agents.md` defines persistent architecture, invariants, and repository entry
   rules.
3. This policy defines detailed generic repository execution rules.
4. `docs/ROADMAP_EXECUTION_PLAYBOOK.md` defines the procedure for executing one
   authorized CEP.
5. The canonical CEP prompt defines package-specific Scope, AC, DoD, migration,
   evidence, and package stop conditions.
6. `CEP_EXECUTION_REGISTRY.yaml` is the sole live CEP-state authority.
7. `ROADMAP.md` defines delivery direction.
8. Completion Reports and cited evidence record execution results.
9. Code, migrations, tests, and configured environment behavior define
   implementation reality.

Do not let a policy, Playbook, Roadmap, snapshot, or Completion Report claim live
Registry authority. Do not reconstruct package scope from a lower authority.

## 3. Default Git execution model

The default implementation branch is the current local `main`. Work directly in
that working tree for normal repository and CEP work.

Do not create or switch to a branch, CEP branch, worktree, temporary integration
branch, or detached implementation branch unless the Human Decision Maker gives
explicit, bounded authorization for that operation. A new session alone is not a
reason to change branch or worktree.

The normal workflow is:

```text
local main
→ perform authorized work
→ run required validation and collect evidence
→ leave changes uncommitted
→ STOP
→ Human later performs or separately authorizes a Git checkpoint
```

## 4. Git permissions

Use read-only Git commands when needed for grounding, inspection, or validation,
including:

```text
git status
git diff
git log
git show
git branch
git rev-parse
git ls-files
```

Unless explicitly authorized for the named operation, do not execute:

```text
git add
git commit
git push
git merge
git rebase
git cherry-pick
git reset
git clean
git stash
git tag
```

Destructive checkout, `git reset --hard`, `git clean -fd`, force push, history
rewrite, or discarding unrelated changes requires separate, narrow, unambiguous
Human Authorization. Never infer Git-write authority from CEP completion.

## 5. Dirty working-tree protection

Existing modifications and untracked files belong to the user unless established
otherwise. Preserve them. Do not discard, overwrite, restage, reformat, relocate,
or absorb unrelated work.

Inspect overlap before mutation. If authorized work cannot proceed without risking
unrelated changes, stop before mutation and report the exact collision. Do not use
stash, reset, clean, destructive checkout, or a new worktree as an automatic
workaround.

Multiple completed CEP changes may intentionally coexist on local `main`. Their
presence is not by itself a blocker when scope and collision safety remain clear.

## 6. Repository grounding

Before product mutation, record at minimum:

```text
current branch
current HEAD
origin/main when available
git status --short
git diff --name-status
git diff --stat
```

Inspect the actual repository seam before choosing files, models, services,
migrations, or tests. Package file lists are hints, not substitutes for grounding.

For CEP work, compare repository state with applicable Registry metadata. A HEAD
change does not itself change execution, authorization, completion, or Gate state.
Reconcile path/repository metadata only when authorized and supported by evidence.

## 7. Scope and authorization control

Implement only explicitly requested and authorized scope. Do not use ambiguity to:

- expand a CEP or ordinary task;
- alter Product Decisions, AC, DoD, or the dependency graph;
- activate downstream work;
- perform unrelated refactoring;
- invent business, financial, security, regulatory, or migration semantics;
- infer Human Sign-off, Gate PASS, Production Certification, or production action.

Discovery of an adjacent defect creates a finding with evidence, not authority to
fix it. If safe implementation requires a material decision outside current
authority, stop and request bounded Human resolution.

## 8. Default session and CEP queue model

**Default: one CEP per session.** After that CEP completes or stops, stop unless
the Human Authorization explicitly lists a multi-CEP queue.

Multiple CEPs may run in one session only when:

- every CEP is explicitly listed in Human Authorization;
- every CEP is individually authorized;
- its dependencies and gates are satisfied;
- repository collision and sequencing safety are verified;
- execution is serial by default.

Parallel CEP execution requires separate explicit Human Authorization after
dependency and repository-collision review.

For an authorized serial queue, each CEP remains separately scoped and validated.
Advance only when the prior CEP ends `EXECUTION COMPLETE`. Stop the entire queue
when a CEP is `EXECUTION PARTIAL`, `EXECUTION FAILED`, blocked before mutation, or
has a materially unresolved blocker. Report all remaining CEPs as `NOT STARTED`.

Queue membership does not waive canonical identity, authorization, dependency,
Gate, migration, security, tenant, evidence, or production controls. A completed
CEP never automatically authorizes the next CEP.

## 9. CEP procedure boundary

For every authorized CEP, follow `docs/ROADMAP_EXECUTION_PLAYBOOK.md`. It owns the
step-by-step procedure for grounding, contract loading, authorization/dependency
verification, touch-set discovery, implementation, focused validation, regression,
evidence, Registry reconciliation, Completion Report, and STOP behavior.

This policy controls the generic permission and safety boundary around that
procedure; it does not repeat the package-specific contract.

## 10. Canonical prompt lookup

Normal lookup is:

1. Locate `docs/governance/cep/PROMPTS/CEP-xxx_EXECUTION_PROMPT.md` or the path
   registered in `docs/governance/cep/CEP_PROMPT_MANIFEST.yaml`.
2. Verify the prompt's byte-level SHA-256 against the manifest.
3. Load relevant frozen/canonical sources referenced by the prompt.
4. Only if the repository prompt is unavailable, use approved consolidated
   canonical recovery materials.
5. If canonical identity remains unavailable, stop before product mutation.

Do not reconstruct Scope, AC, DoD, migration impact, or dependency semantics from
`ROADMAP.md`, `docs/PROJECT_STATUS.md`, Completion Reports, memory, or historical
P-phase documents.

Repository-local absence does not prove canonical-source nonexistence. Check the
approved consolidated source before declaring a source blocker. Never invent
missing Product Decisions, financial authority, posting rules, domain ownership,
or migration semantics.

## 11. Prompt versus generic policy conflict

Do not modify canonical prompt content to modernize old generic instructions.
Package-specific contract semantics remain authoritative. Current `Agents.md`,
this policy, and the CEP Playbook govern generic repository mechanics.

When an old prompt's generic branch, worktree, Git, or execution convention
conflicts with current repository policy, current policy governs unless the prompt
instruction is materially package-specific. If classification is unsafe or a
package-specific conflict is material, stop before mutation with
`BLOCKER-PROMPT-GOVERNANCE-CONFLICT` and record the exact conflict.

## 12. Actual Execution Touch Set

Before implementation, record the exact intended mutation surface, including as
applicable:

```text
files and modules
models and schema
migrations and data movement
services and selectors
forms, views, templates, and queries
shared contracts and utilities
tests and fixtures
settings and configuration
documentation and evidence
```

Inspect the real implementation seam. Keep the touch set bounded. An adjacent
improvement is not authorized merely because it is convenient.

## 13. Migration and schema boundary

Respect the canonical migration impact. If a package states `Migration Impact =
NONE`, do not create schema or data migrations. If a migration becomes genuinely
necessary, stop before model or migration mutation and request bounded Human
resolution.

Authorization for migration code, tooling, rehearsal, or development execution
does not authorize production migration, irreversible data change, contract-step
removal, or cutover. Preserve expand → migrate/backfill → switch → validate →
explicitly approved contract sequencing where replacement is authorized.

Never silently mutate finalized history or infer missing backfill semantics.

## 14. Production and Human Sign-off boundaries

Unless separately authorized, do not perform production deployment, cutover,
migration, database mutation, certification, rollback, or irreversible action.

Passing tests, CEP completion, UAT-like automation, integration, or evidence does
not issue Human Sign-off. Unless the Human Decision Maker explicitly performs it:

```text
Human Sign-off = NOT EXECUTED
Production Certification = NOT EXECUTED
Production Cutover = NOT EXECUTED
```

## 15. Validation strategy

Run the smallest sufficient validation required by the canonical contract and
affected risk:

```text
focused tests
→ affected-boundary regression
→ broader validation only when materially triggered
```

Use unit tests for domain/service rules and integration tests for permissions,
tenant scope, isolation, transactions, and affected boundaries. Run Django checks
after relevant Django/configuration changes and Ruff checks/format validation when
applicable.

Do not run large unrelated suites for ceremony. Do not omit required high-risk
validation to save time or tokens. Reuse existing evidence only when the
implementation, schema, configuration, environment, and assumptions remain
materially unchanged.

Documentation-only changes normally require focused reference/link, stale-claim,
formatting/whitespace, and changed-document review—not application tests—unless a
concrete executable/configuration risk or explicit request requires them.

## 16. Regression and baseline-debt attribution

Classify failures with evidence as one of:

```text
CEP REGRESSION
BASELINE TEST DEBT
TEST INFRASTRUCTURE DEBT
UNRELATED FAILURE
UTV
```

Do not call a failure baseline because it is inconvenient. Show that changed CEP
behavior is not reached or otherwise provide sufficient attribution. Do not hide
an actual regression behind baseline debt. Preserve unrelated debt rather than
silently fixing it without authority.

Never claim full regression PASS when only representative regression ran. State
the actual coverage and remaining UTV.

## 17. Evidence handling

Evidence must be sufficient for the claim and no broader. Preserve relevant:

- commands and outcomes;
- branch, revisions, and dirty-state context;
- canonical source identity and hashes;
- database/migration environment;
- tenant, permission, security, concurrency, and financial assertions;
- test, regression, lint, system-check, and drift results;
- findings, limitations, and UTV.

Keep evidence free of secrets and unnecessary personal/sensitive data. Do not
convert missing evidence into PASS. Avoid duplicate ledgers: the Registry owns live
state, the Completion Report owns the execution result, and referenced artifacts
hold detailed evidence.

## 18. CEP completion states

Every CEP ends with exactly one:

```text
EXECUTION COMPLETE
EXECUTION PARTIAL
EXECUTION FAILED
```

`EXECUTION COMPLETE` requires all implementation-required canonical AC and scoped
DoD to be supported, required focused tests/regression and checks to pass or be
validly attributed, and no unresolved in-scope blocker or unauthorized semantics.

Use `EXECUTION PARTIAL` when bounded implementation exists but required validation,
evidence, or completion remains unresolved. Use `EXECUTION FAILED` when the CEP
cannot safely or validly proceed or complete. A blocker is never a PASS.

## 19. Completion Report requirements

Record, as applicable:

```text
CEP ID and execution state
branch and start/end HEAD
authorization and canonical-source status
repository grounding and actual touch set
product files and migrations
AC and scoped DoD results
focused tests and regression coverage
lint, system checks, and migration drift
findings, blockers, baseline debt, and UTV
unauthorized semantics check
Registry reconciliation
Human Sign-off and production status
Git branch/worktree and Git-write status
next CEP status
```

Unless specifically authorized, report:

```text
Branch: main
Git branch/worktree created: NO
git add: NOT EXECUTED
git commit: NOT EXECUTED
git push: NOT EXECUTED
git merge: NOT EXECUTED
Next CEP: NOT STARTED
```

## 20. Registry reconciliation

Read the Registry at every CEP session start. Update it only for evidence-supported
material lifecycle events and only within current authority. Preserve history;
never silently replace events or recalculate a desired narrative.

Do not infer or issue authorization, Gate PASS, Human Sign-off, Production
Certification, Production Cutover, global frontier, AC/DoD satisfaction, or Git
integration. A file move or policy refactor is not a CEP lifecycle event.

If Registry, repository reality, and explicit Human evidence materially conflict,
stop before product mutation with `BLOCKER-REGISTRY-CONFLICT` and identify the
exact conflict.

## 21. Findings, blockers, and blocked-work efficiency

Record the finding, affected criterion, reproducible evidence, classification,
scope impact, and safe next action. Do not bypass a real dependency or blocker for
throughput.

A blocked CEP does not unnecessarily stop another explicitly authorized,
independent, non-colliding CEP outside the same stop-on-blocker queue. Evaluate
dependency and collision impact and proceed only when separate authority remains
valid. Within an authorized serial queue, apply the queue stop rule in section 8.

## 22. Human Git checkpoints

Multiple completed changes may accumulate on local `main`. The Human Decision
Maker may later perform or separately authorize a checkpoint:

```text
git status
git add
git commit
git push
```

Codex does not create the checkpoint without explicit authority. Git integration
is distinct from CEP execution completion and never grants downstream execution.

## 23. Engineering constraints

Non-negotiable priorities:

```text
Correctness and Quality
Data and Financial Integrity
Security and Tenant Isolation
Financial / Domain Authority Integrity
Auditability, Traceability, and Regulatory Safety
```

Subject to those controls, minimize elapsed time, compute/token cost, governance
overhead, operational complexity, repository churn, test duration, decision
latency, and blast radius. Preserve performance, scalability, concurrency safety,
maintainability, testability, backward compatibility, reversibility, and recovery.

If two approaches provide materially equivalent assurance, prefer the cheaper,
faster, narrower, and simpler one. Efficiency must never convert a required PASS
into an unsupported assumption.

## 24. Governance and resource efficiency

Every read, search, tool call, test, generated document, and approval cycle should
serve the requested outcome or materially reduce correctness, integrity, security,
authority, migration, regulatory, or production risk.

Use progressive inspection: file lists, `rg`, headings, narrow ranges, direct
code/tests, then adjacent sources only when a material risk triggers expansion.
Avoid rereading or restating evidence already established and still valid.

Keep one authoritative explanation per conclusion and link to it elsewhere. Do not
create duplicate status documents or repeat source recovery, decision packets, or
validation without a material reason.

Treat token allowance and elapsed time as finite project resources. Before a
materially expensive action, state its purpose and use a lower-cost equivalent when
it provides the required assurance. Stop when acceptance criteria are met.

Quality/correctness and integrity/security are non-negotiable. Time and cost are
optimized; governance overhead is minimized.

## 25. Build versus reuse

Reuse commodity capability; own strategic construction-ERP domain logic. Consider,
in order:

1. Python standard library;
2. Django/PostgreSQL built-ins;
3. an existing repository dependency;
4. a mature, secure, maintained third-party library;
5. custom code when strategic or when reuse is unsuitable.

For a significant dependency, evaluate maintenance/security history, trust and
adoption, documentation, version compatibility, SaaS license, transitive burden,
architecture fit, operational ownership, and exit risk. A Roadmap mention is not
installation authorization.

Never custom-build cryptographic/password primitives or OAuth/OIDC/SAML and similar
security protocols when trusted implementations exist. Do not replace sound custom
workflow, costing, posting, compliance, reconciliation, or other strategic BONIRA
logic merely because a generic package exists.

Skills and tools may aid analysis or validation; they do not define architecture,
grant scope, or replace verification against repository reality.

## 26. Documentation closeout

Documentation closeout is the final work step before reporting. Inspect and update
only affected authoritative documents. Preserve current-versus-target labels and
do not create duplicate live status or snapshot authorities.

Update `ROADMAP.md` only for a material change to delivery direction, dependency
planning, program disposition, or future scope. Update the Registry only for actual
supported lifecycle/state events or permitted path metadata. Session completion
alone does not grant Product Owner approval.

## 27. Execution communication

Use concise English unless the user requests otherwise. Lead with outcomes,
decisions, changed artifacts, validation, blockers, and next action. Do not narrate
routine reads, searches, edits, or tests.

Send intermediate updates only for a blocker, important decision, significant
architecture/domain finding, or material change in approach. Never omit a material
risk, failed validation, approval state, or required Human decision.

Final reports must state honestly what was and was not validated. Link to artifacts
instead of copying their contents when a concise reference is sufficient.

## 28. Explicit override and stop rule

An override must be explicit, bounded, unambiguous, and specific to the operation.
Historical authorization is not automatically reusable for different work.

Stop before product mutation for material canonical-source conflict, unresolved
required Product Decision, unsafe repository collision, missing business authority,
out-of-scope migration, tenant/security/financial integrity risk, or unresolved
governance precedence. Report the exact blocker and preserve evidence.
