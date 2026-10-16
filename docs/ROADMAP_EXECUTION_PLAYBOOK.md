# BONIRA CEP Execution Playbook

## 1. Purpose

This manual describes how Codex executes one explicitly authorized CEP. It is
procedural; it does not grant scope, set product policy, or define live CEP state.
The [CEP Program Authority](governance/CEP_PROGRAM_AUTHORITY.md) explains the
source hierarchy. Historical P0–P10 session logs are retained in Git checkpoint
`a4a18a1` and their architecture/decision/closeout packets; P0–P10 are not the
current execution queue.

## 2. Authority hierarchy

`Agents.md` supplies persistent architecture and invariants, while
`docs/governance/BONIRA_CODEX_PROJECT_EXECUTION_POLICY.md` supplies detailed
generic repository execution rules. The canonical CEP package/prompt supplies
scope, AC, DoD, migration impact, and stop conditions. Explicit Human
Authorization permits only the bounded work it names. The Registry owns current
CEP state, the Roadmap owns delivery direction, and code/migrations/tests define
implementation reality. Completion Reports and evidence prove individual
results. This Playbook overrides none of those sources.
Historical generic instructions embedded in a prompt cannot override newer
governing generic mechanics unless they are explicitly package-specific and
materially affect that CEP.

## 3. Mandatory session context — C0

Before product mutation, read `Agents.md`,
`docs/governance/BONIRA_CODEX_PROJECT_EXECUTION_POLICY.md`,
`CEP_EXECUTION_REGISTRY.yaml`, the relevant `ROADMAP.md` section, the canonical
CEP contract/prompt, explicit Human Authorization, the minimum relevant
canonical source set, current Git state, and the previous compact handoff when
relevant. Record the exact acceptance and STOP conditions. C0 is mandatory for
each CEP in a queue. Load direct code/test evidence next; expand to adjacent
sources only for a material risk trigger.

## 4. Repository grounding

Record branch, HEAD, `origin/main`, `git status --short`, `git diff
--name-status`, and `git diff --stat` before mutation. Preserve unrelated changes.
If HEAD or `origin/main` changed since `repository_state.last_reconciled_head`,
inspect the commit boundary and reconcile repository/Git-integration metadata
before product mutation. Repository reality takes precedence over a document
assumption, but it never expands CEP scope or supplies authorization.

## 5. Canonical CEP contract loading

For CEP-001 through CEP-079, first load
`docs/governance/cep/PROMPTS/CEP-xxx_EXECUTION_PROMPT.md`, then verify its
byte-level SHA-256 against the matching record in
`docs/governance/cep/CEP_PROMPT_MANIFEST.yaml`. Load the prompt's referenced
frozen decisions, dependency and gate conditions, AC, DoD, migration impact,
regression, and evidence requirements next. A missing local prompt may be
recovered only from approved consolidated execution materials. If its identity
cannot be established, stop before mutation.

The canonical prompt owns the package-specific contract. `Agents.md`, the
Execution Policy, and this Playbook own generic repository mechanics. If a
historical generic prompt instruction materially conflicts with current governing
generic mechanics, and it is not explicitly package-specific, current governing
mechanics apply. If it is explicitly package-specific and materially affects the
CEP, stop with
`BLOCKER-PROMPT-GOVERNANCE-CONFLICT`, record the exact conflict, and obtain
bounded Human resolution. Do not reconstruct upstream Audit 01–20, review, gap
analysis, backlog, decisions, or the dependency graph.

## 6. Human Authorization validation

Match explicit Human Authorization to the CEP ID, bounded scope, migration
permission, execution mode, and current Registry record. `ELIGIBLE`,
`NEXT-CANDIDATE`, `READY`, or dependency-satisfied does not authorize execution.
Codex may record an explicit Human decision in the Registry; it cannot issue or
infer authorization.

## 7. Dependency and gate validation

Verify the canonical prerequisite set, current Registry state, applicable gate
evidence, and repository reality. Gate PASS, Human Sign-off, production approval,
and a global authorization frontier are never inferred. If sources materially
conflict, stop with `BLOCKER-REGISTRY-CONFLICT` and identify the exact conflict.

## 8. Execution touch set

Before implementation, name the actual intended files, models, schema,
migrations, services, selectors, forms, views, templates, queries, shared
contracts, tests, and configuration. Expected package surfaces are hints; inspect
the repository seam. Preserve unrelated user work.

## 9. Scope control

Implement only the canonical CEP scope. Record an unexpected adjacent defect as
a Finding with evidence; do not absorb it into this CEP. Do not alter Product
Decisions, canonical AC/DoD, the dependency graph, or downstream authority.
Repository findings may require a narrower fix or a stop, not implicit expansion.

## 10. Migration rules

Respect the canonical migration impact. If it is `NONE` and a schema or data
migration becomes necessary, stop before model/migration mutation with
`BLOCKER-MIGRATION` until bounded Human resolution. Authorized development
migrations or rehearsals do not authorize production migration or cutover.
Preserve finalized history and use approved expand/migrate/switch/validate/
contract boundaries.

## 11. Test and regression rules

Run the smallest focused tests that prove the change, then the regression and
checks required by the canonical contract and affected risk. Attribute failures
with evidence as CEP regression, pre-existing/baseline debt, test infrastructure
or environment failure, unrelated failure, or UTV. Never claim full regression
PASS from representative checks. Do not rerun known heavy validations for
procedural completeness.

## 12. Evidence rules

Retain commands, test outcomes, relevant database/migration context, source
revisions, audit/security/tenant evidence, and limitations needed to support the
AC/DoD claim. Use the CEP's completion report and referenced evidence manifests;
do not duplicate a live ledger in the Roadmap or this Playbook. Missing evidence
stays `UNVERIFIED` rather than becoming invented certainty.

## 13. Finding and blocker rules

Record the finding, affected criterion, reproducible evidence, classification,
scope impact, and safe next action. Update the Registry for material `BLOCKED`,
`PARTIAL`, `FAILED`, `RESUMED`, and `BLOCKER_RESOLVED` events. A blocked CEP
cannot be marked complete. Apply the authorized queue stop rule in `Agents.md`;
other work may proceed only under separate valid authorization and dependencies.

## 14. Registry synchronization

Read the Registry at every CEP session start. Record applicable `AUTHORIZED`
only from an explicit Human decision, and update material `STARTED`, `BLOCKED`,
`PARTIAL`, `FAILED`, `RESUMED`, `BLOCKER_RESOLVED`,
`MIGRATION_STATE_CHANGED`, `MATERIAL_UTV_CHANGED`, `COMPLETE`,
`CLOSED_VERIFIED`, and `GIT_INTEGRATED` events. Preserve history. Recalculate
summary fields from CEP records at closeout. Do not infer Gate PASS, Human
Sign-off, Production Certification/Cutover, or a next authorized CEP.

## 15. AC and DoD closure

Evaluate every implementation-required AC and the scoped DoD against evidence.
Record required focused tests, regression, lint/system checks, blockers and
remaining UTV. `EXECUTION COMPLETE` requires supported criteria and no unresolved
in-scope blocker or unauthorized behavior; otherwise report `EXECUTION PARTIAL`
or `EXECUTION FAILED` under `Agents.md`.

## 16. UTV handling

Keep untested or unavailable validation explicit, including browser, load,
concurrency, environment, UAT, or production checks. State whether canonical
AC/DoD permit deferral. A UTV is not a PASS and cannot silently satisfy a
production gate.

## 17. Completion Report

Before the final report, update and reconcile `CEP_EXECUTION_REGISTRY.yaml` and
`CEP-xxx_COMPLETION_REPORT.md`; recalculate Registry counts. Report the exact
execution state, AC/DoD evidence, tests/regression and attribution, UTV,
blockers, touched files, migration and Git facts. Update `ROADMAP.md` only for a
material change to direction, sequencing, phase disposition, or future scope.

## 18. Git integration semantics

Execution completion, commit, push, merge, and integration to `main` are
distinct. Record Human Git activity only from Git evidence. A direct Human
commit/push to `main` uses `integration_method: DIRECT_COMMIT_TO_MAIN` and
`merged_to_main: false` unless an actual merge occurred. Keep the execution
baseline SHA distinct from the later integration commit SHA. Do not run Git
write operations without specific Human authority.

## 19. Handoff and next CEP

Provide a compact handoff with the result, evidence, changed files, current
Registry frontier, unresolved decisions/UTV, and the next safe action. A
completed CEP does not automatically authorize another. A multi-CEP queue may
advance only when every CEP is explicitly listed and authorized and the prior
CEP reaches `EXECUTION COMPLETE`, subject to the queue rule in the Execution
Policy.

## 20. STOP conditions

Stop before product mutation for missing/contradictory authorization, material
Registry/repository conflict, unsatisfied canonical dependency or gate, absent
canonical scope/AC/DoD, or required unapproved migration. Stop the queue on a
partial, failed, blocked, or materially unresolved CEP. Record evidence and the
exact blocker; do not substitute a Roadmap/Playbook status for Human authority.

## Historical link compatibility

Older architecture packets link to the anchors below. Their full dated session
records remain in the committed Playbook at `a4a18a1` (for example,
`git show a4a18a1:docs/ROADMAP_EXECUTION_PLAYBOOK.md`) and the linked source
packets. These anchors preserve navigation without making that diary current
execution procedure.

<a id="27-p0-s02-decision-packet-and-s03-handoff"></a>
<a id="28-p0-s03-release-assumptions-and-s04-handoff"></a>
<a id="29-p0-s04-accounting-posting-adr-proposal-and-s05-handoff"></a>
<a id="30-p0-s05-budget-and-project-cost-adr-proposal-and-s06-handoff"></a>
<a id="31-p0-s06-regulatory-and-commercial-policy-adr-proposal-and-s07-handoff"></a>
<a id="32-p0-s07-projectsite-authorization-adr-proposal-and-handoff"></a>
<a id="33-p0-s08-private-document-storage-adr-proposal-and-s09-handoff"></a>
<a id="34-p0-s09-dms-domain-link-adr-proposal-and-s10-handoff"></a>
<a id="35-p0-s10-asyncoutbox-adr-proposal-and-s11-handoff"></a>
<a id="36-p0-s11-tenant-lifecycle-adr-proposal-and-s12-handoff"></a>
<a id="37-p0-s12-future-network-privacy-adr-proposal-and-handoff"></a>
<a id="38-p0-s13-p01-adr-review-packet-and-handoff"></a>
<a id="39-p0-s14-q04-product-owner-decision-packet-and-handoff"></a>
<a id="40-p0-s15-q04-decision-recording-and-review-handoff"></a>
<a id="41-final-q04-g-product-owner-decision-and-handoff"></a>
<a id="43-membership-scoped-multi-role-authorization-rule"></a>
<a id="44-p0-s16-q04-accountable-review-pending-record"></a>
<a id="45-p0-s17-q04-reviewer-assignment-record"></a>
<a id="46-p0-s18-q04-final-accountable-reviewer-and-independence-override"></a>
<a id="47-p0-s19-q04-review-outcome-recording-from-s18-handoff"></a>
<a id="8-p2-session-map--38-sessions"></a>
<a id="compact-p0-s04-handoff"></a>
<a id="compact-p0-s05-handoff"></a>
<a id="compact-p0-s06-handoff"></a>
<a id="p0-d01-initial-customer-segment"></a>
<a id="p0-d02-financial-authority-boundary"></a>
<a id="p0-d03-hosting-residency-and-operational-ownership"></a>
<a id="p0-d04-recovery-objectives"></a>
<a id="p0-d05-saas-packaging-entitlements-and-quotas"></a>
<a id="p0-d06-audit-findings-priorities-and-implementation-authority"></a>
<a id="s03-approval-evidence-and-current-decisions"></a>
<a id="unresolved-parameters-and-latest-gates"></a>
