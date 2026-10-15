# BONIRA — Codex Project Execution Policy

**Status:** ACTIVE  
**Scope:** Entire BONIRA repository  
**Applies to:** All Codex implementation sessions, including CEP execution  
**Default branch:** `main`

---

## 1. Purpose

This file defines the persistent repository-level execution policy for Codex.

Unless an explicit Human Authorization or CEP-specific instruction overrides a rule in this file, Codex MUST follow this policy in every session.

The purpose is to:

- keep implementation work on the local `main` working tree by default;
- avoid unnecessary branch/worktree proliferation;
- preserve human control over Git history and remote publication;
- keep CEP execution bounded, auditable, and fail-closed;
- prevent accidental production, migration, authorization, or scope expansion.

---

## 2. Default Git Execution Model

The default execution branch is:

```text
main
```

For normal CEP implementation, Codex MUST work directly on the current local `main` working tree.

Codex MUST NOT create, by default:

```text
new branch
CEP branch
Git worktree
temporary integration branch
detached implementation branch
```

A separate branch/worktree may be created only when explicitly authorized by the Human Decision Maker or explicitly required by an approved execution prompt.

---

## 3. Default Git Permissions

Codex MAY use read-only Git commands required for grounding and inspection, including:

```text
git status
git diff
git log
git show
git branch
git rev-parse
git ls-files
```

Codex MUST NOT execute the following unless explicitly authorized by the Human Decision Maker:

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

Codex MUST NOT discard, overwrite, or destroy unrelated user work.

Destructive Git operations such as:

```text
git reset --hard
git clean -fd
forced checkout
force push
history rewrite
```

are prohibited unless separately and explicitly authorized for a specific purpose.

---

## 4. Normal BONIRA Development Workflow

The default workflow is:

```text
local main
→ execute authorized CEP
→ run tests
→ produce evidence
→ leave approved product changes in the local working tree
→ STOP
```

After several CEPs, the Human Decision Maker may manually perform or separately authorize:

```text
git add
git commit
git push
```

Codex MUST NOT assume that completion of a CEP grants Git commit or push authority.

---

## 5. One CEP Per Session

Unless Human Authorization explicitly says otherwise:

```text
ONE CODEX SESSION = ONE CEP
```

After completing or stopping the authorized CEP, Codex MUST stop.

Codex MUST NOT automatically start the next CEP.

---

## 6. Required CEP Execution Sequence

Every CEP implementation MUST follow this sequence:

```text
Repository Grounding
→ Canonical Source Verification / Recovery
→ Actual Execution Touch Set
→ Implementation
→ Focused Tests
→ Required Regression
→ Evidence
→ Completion Report
→ STOP
```

No product mutation may occur before Repository Grounding and Actual Execution Touch Set discovery.

---

## 7. Repository Grounding

Before product mutation, Codex MUST record at minimum:

```text
current branch
current HEAD
git status --short
git diff --name-status
git diff --stat
```

Codex MUST inspect the actual repository before assuming file paths, models, services, migrations, or implementation seams.

Package-level expected code surfaces are hints only.

If the working tree contains unrelated changes:

```text
DO NOT DISCARD THEM
DO NOT OVERWRITE THEM
```

If safe bounded execution cannot continue without risking unrelated work:

```text
STOP BEFORE MUTATION
```

and report an explicit blocker.

---

## 8. Canonical Source Policy

Repository-local absence of a canonical source does NOT automatically prove that the canonical source does not exist.

Before declaring a source blocker, Codex MUST check the approved consolidated canonical execution materials available to the project.

Codex MUST NOT infer missing Product Decisions, business rules, financial authority, posting rules, migration semantics, acceptance criteria, or domain ownership.

Preserve:

```text
NO APPROVED POLICY
→ NO INFERRED BUSINESS BEHAVIOR
```

If canonical sources conflict materially:

```text
STOP BEFORE MUTATION
```

---

## 9. Actual Execution Touch Set

Before implementation, Codex MUST explicitly record the exact intended mutation surface.

Where applicable, include:

```text
files
models
schema
migrations
services
selectors
forms
views
templates
queries
shared contracts
utilities
tests
settings
configuration
```

Codex MUST remain inside the authorized CEP scope.

Discovery of adjacent defects or opportunities does NOT authorize fixing them.

---

## 10. Scope Control

Codex MUST NOT:

```text
expand CEP scope
change Product Decisions
change Acceptance Criteria
change Definition of Done
change CEP DAG dependencies
activate downstream CEPs
invent missing business semantics
perform unrelated refactoring
```

unless separately authorized.

A CEP completion report does not itself authorize any downstream CEP.

---

## 11. Migration Policy

A CEP marked:

```text
Migration Impact = NONE
```

MUST NOT create a schema or data migration.

If a migration becomes genuinely necessary despite canonical `NONE`:

```text
STOP BEFORE MODEL / MIGRATION MUTATION
```

and request bounded Human resolution.

Where migration code or preparation is explicitly authorized, that does NOT authorize:

```text
production migration
irreversible production data change
production cutover
```

Production migration always requires separate Human Authorization.

---

## 12. Production Boundary

Unless separately authorized, Codex MUST NOT execute:

```text
production deployment
production cutover
production migration
production database mutation
production certification
production rollback
```

Development and non-production implementation authorization does not imply production authority.

---

## 13. Human Sign-off

Human Sign-off is never inferred from passing tests, CEP completion, audit evidence, UAT-like automated checks, or successful integration.

Unless explicitly performed by the Human Decision Maker:

```text
Human Sign-off = NOT EXECUTED
```

---

## 14. Testing and Evidence

Codex MUST execute the tests required by the canonical CEP/IMB.

Use the smallest representative test set that proves the authorized Acceptance Criteria and affected regression behavior.

Do not run enormous unrelated suites merely for ceremony.

If a test failure occurs, classify it using evidence:

```text
CEP REGRESSION
BASELINE TEST DEBT
TEST INFRASTRUCTURE DEBT
UNRELATED FAILURE
UTV
```

Do not label a failure as baseline without sufficient attribution.

Do not claim a full regression PASS when only representative regression was executed.

---

## 15. Baseline Debt

Pre-existing repository defects may remain outside a CEP if they are demonstrably unrelated.

Codex MUST:

- preserve evidence of attribution;
- avoid silently fixing unrelated debt;
- avoid converting baseline failures into CEP failures without evidence;
- avoid using baseline debt as an excuse for an actual CEP regression.

---

## 16. Completion States

Every CEP must end with exactly one execution state:

```text
EXECUTION COMPLETE
EXECUTION PARTIAL
EXECUTION FAILED
```

### EXECUTION COMPLETE

Use only when:

```text
canonical AC satisfied
Scoped DoD satisfied
required tests satisfied
required regression satisfied or validly attributed
required lint/system checks satisfied
no unresolved in-scope blocker
no unauthorized semantics introduced
```

### EXECUTION PARTIAL

Use when implementation exists but required validation, evidence, or bounded completion remains unresolved.

### EXECUTION FAILED

Use when the CEP cannot safely or validly proceed or complete.

---

## 17. Stop-Before-Mutation Conditions

Codex MUST stop before product mutation when any of the following applies:

```text
material canonical-source conflict
required Product Decision is unresolved
unsafe repository baseline
unresolvable unrelated working-tree collision
migration required outside authorization
scope conflict
missing authority for business semantics
```

A local documentation absence alone is not sufficient until approved consolidated sources have been checked.

---

## 18. Financial Authority Protection

Codex MUST preserve domain authority boundaries.

Examples:

```text
Treasury = Cash Authority
Accounting = GL Authority
AP = Payables Authority
AR = Receivables Authority
Payroll = Payroll Authority
Inventory = Stock / Inventory Value Authority
Project Controls = Project Cost Authority
```

Reporting/read models are read/projection authorities only unless a canonical rule explicitly states otherwise.

Codex MUST NOT introduce:

```text
parallel financial authority
silent posting path
implicit financial correction
generic model-save → journal behavior
competing source of truth
```

---

## 19. No-Inference Guardrails

Preserve fail-closed behavior.

Examples:

```text
NO APPROVED PRODUCER CONTRACT
→ NO PROJECT COST FACT
```

```text
NO ACCOUNTING RECOGNITION OWNER
→ NO INFERRED POSTING
```

```text
NO STATUTORY EVIDENCE
→ NO CURRENT STATUTORY ACTIVATION
```

```text
NO APPROVED BUSINESS RULE
→ DO NOT INVENT ONE
```

---

## 20. CEP Completion Report

Every CEP final report should include, where applicable:

```text
CEP ID
Execution Status
Branch
Start HEAD
End HEAD
Authorization
Repository Grounding
Canonical Source Status
Actual Execution Touch Set
Product Files Changed
Migration Required
Migration Executed
Acceptance Criteria Result
Scoped DoD
Focused Tests
Regression
Lint / Ruff
Django / System Checks
Migration Drift
Open Findings
Baseline Failures
Unauthorized Product Semantics
Human Sign-off
Production
Git add
Git commit
Git push
Git merge
Next CEP
```

Unless explicitly authorized:

```text
Git add = NOT EXECUTED
Git commit = NOT EXECUTED
Git push = NOT EXECUTED
Git merge = NOT EXECUTED
Next CEP = NOT STARTED
```

---

## 21. Git Checkpoint Model

The preferred BONIRA workflow is to let multiple completed CEP changes accumulate safely on local `main`, then allow the Human Decision Maker to perform a Git checkpoint.

Example:

```text
main
├── CEP-006 changes
├── CEP-009 changes
├── CEP-011 changes
│
└── Human Git Checkpoint
    → git status
    → git add
    → git commit
    → git push
```

Codex must not independently create that checkpoint unless separately authorized.

---

## 22. Explicit Override Rule

An explicit Human Authorization or approved CEP-specific execution prompt may override part of this policy.

Any override must be:

```text
explicit
bounded
specific to the requested operation
```

Silence is not an override.

Historical authorization is not automatically reusable for a materially different action.

---

## 23. Default Session Instruction

At the beginning of every Codex session in this repository, apply:

```text
REPOSITORY POLICY ACTIVE

Default execution branch:
main

Do not create branch/worktree unless explicitly authorized.

Do not execute git add/commit/push/merge unless explicitly authorized.

Preserve unrelated work.

Execute only the explicitly authorized CEP.

Follow:
Repository Grounding
→ Canonical Verification
→ Actual Execution Touch Set
→ Implementation
→ Tests
→ Evidence
→ Completion Report
→ STOP
```

---

## 24. Current Repository Execution Convention

Following the completed CEP integration checkpoint, the project convention is:

```text
CEP implementation happens directly on local main.
Human retains control of commit and push.
```

This convention remains active until explicitly changed by the Human Decision Maker.

---

**End of BONIRA Codex Project Execution Policy**
