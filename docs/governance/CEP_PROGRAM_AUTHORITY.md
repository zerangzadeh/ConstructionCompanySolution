# BONIRA CEP Program Authority

## Origin and purpose

BONIRA's controlled CEP delivery program was derived through Audit 01–20,
Product Review, Domain / Technical Review, Gap Analysis, the Remediation Master
Backlog, Product Decisions and their freeze, dependency analysis, CEP package
design, and canonical CEP execution prompts. These are upstream governance and
evidence artifacts. An ordinary CEP session uses the approved results; it does
not reconstruct or rerun that analysis.

P0–P10 are historical executed development phases. Current controlled
implementation and remediation proceed through CEPs. Historical phase records
and residual capability descriptions do not form an execution queue.

## Authority boundaries

| Question | Authority |
| --- | --- |
| What is implemented? | Product code, migrations, and tests, verified against the configured environment. |
| What may one CEP change and how is it accepted? | That CEP's canonical package/prompt: scope, acceptance criteria, Definition of Done, and execution contract. |
| What is the current CEP state? | Root `CEP_EXECUTION_REGISTRY.yaml`: lifecycle, recorded authorization, blockers, completion, UTV, Git integration, and execution frontier. |
| What is the program's delivery direction? | Root `ROADMAP.md`: CEP structure, dependency-ordered direction, residual and future scope. |
| How may Codex operate in the repository? | `Agents.md` supplies persistent invariants and `docs/governance/BONIRA_CODEX_PROJECT_EXECUTION_POLICY.md` supplies detailed generic execution policy. |
| How is an authorized CEP executed? | `docs/ROADMAP_EXECUTION_PLAYBOOK.md`, subject to `Agents.md`, the Execution Policy, and the canonical contract. |
| What proves one execution result? | Its `CEP-xxx_COMPLETION_REPORT.md` and cited evidence. |
| What records older project observations? | `docs/PROJECT_STATUS.md` and the retained historical architecture/decision/closeout packets. |
| What persists across Codex sessions? | Root `Agents.md` and the active detailed Execution Policy. |

The canonical CEP contract and explicit Human Authorization must be obtained for
the specific session. A repository search that does not find an upstream source
does not establish its absence; use approved consolidated execution materials
when applicable. Do not infer missing scope, decisions, or dependency edges.

## Human authority and execution boundary

Only the Human Decision Authority may issue implementation or production
authorization, Human Sign-off, or Production Certification. Codex may record
explicit decisions but may not issue or infer them. Gate PASS also requires its
applicable explicit authority and evidence. `ELIGIBLE`, `READY`,
`NEXT-CANDIDATE`, and dependency-satisfied labels do not grant authorization.
Execution completion, commit, push, merge, and integration to `main` are distinct
events.

For the live program state, read the Registry at session start. If the Registry,
repository, and explicit Human evidence materially conflict, stop with
`BLOCKER-REGISTRY-CONFLICT` before product mutation.
