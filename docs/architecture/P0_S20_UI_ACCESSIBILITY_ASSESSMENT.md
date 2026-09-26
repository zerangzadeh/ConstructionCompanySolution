# P0-S20 UI/accessibility assessment and deferred-remediation handoff

**Status:** ASSESSMENT COMPLETE — actual UI remediation deferred.

**Recorded:** 2026-09-26. **Scope:** documentation-only assessment of the
centralized workbench journey against the current runtime, recent Q04 decisions
and the [UI guidelines](../ui-guidelines.md). This record changes no template,
view, service, permission, schema, migration, workflow or runtime behavior.

## 1. Recommendation and boundary

P0-S20 records **defer actual workbench UI changes until the relevant
authorization model is accepted and implemented**. The workbench remains the
recommended first remediation journey because it is mature, tested and is the
highest-value intersection of permissions, candidacy, assignment, project/site
context and workflow action. It is not safe to redesign its authority-dependent
states while the current runtime and the target Q04/P1.1 model differ.

This deferral does not declare the current UI conformant, accept an ADR, close the
Q04 review gate or authorize P1.1. It prevents presentation work from implying
target access semantics that the server does not yet enforce.

## 2. Current implementation and target dependencies

| Concern | Verified current state | Target decision / dependency | UI consequence |
| --- | --- | --- | --- |
| Membership roles | `OrganizationMembership.role_definition` is one foreign key; the workbench reads permissions from that one role. | Membership-scoped independent multi-role assignments with permission union. | Do not add multi-role labels, filters, editors or explanations yet. |
| Tenant role separation | Current protected role codes and single-role membership remain compatibility behavior. | Tenant Owner, Tenant Admin / Local Admin and Tenant Manager are independent roles; no implicit inheritance. | Do not redesign membership or workbench affordances around target role names or implied authority. |
| Project/site scope | Workbench items are tenant-, subject-permission- and candidacy/assignment-scoped. Project/site filter choices query tenant projects/sites; no per-user grant intersection exists. | Q04-A/B/C and proposed S07/P1.1 require explicit membership-linked grants and effective project/site intersection. | Do not present filters, counts or context as proof of effective object authorization. |
| Self-Approval / Protected Operations | Runtime applies currently configured separation and domain permissions; no final Q04-G operation-classification/policy UI exists. | Protected Operations never permit Self-Approval; eligible business operations require explicit platform/Tenant policy and audit. | Do not add Self-Approval controls, warnings, badges or policy explanations before the authoritative service state exists. |
| Fallback / unresolved work | Current routing has compatibility fallback behavior and the personal workbench shows assigned, claimed or active-candidate items. | Q04-H H1 filters primary and fallback candidates through complete eligibility and retains visible unresolved work for authorized recovery. | Do not add an unresolved queue, fallback state or administrative recovery action before runtime ownership and permissions exist. |
| Workbench UI | Persian RTL page, filters, counts, source links, assignment reasons, actions, history, pagination and permission-safe action omission are implemented and directly tested. | UI guidelines require fuller context, state, keyboard, focus, touch, concurrency and accessibility behavior. | Preserve the workbench as the first future remediation journey; separate semantic-neutral debt from authorization-dependent UI. |

Authoritative current/target evidence remains the proposed
[project/site authorization ADR](ADR_P0_S07_PROJECT_SITE_AUTHORIZATION.md), the
[Q04 packet](P0_S14_Q04_PRODUCT_OWNER_DECISION_PACKET.md), the
[workflow/permission matrix](WORKFLOW_AND_PERMISSION_MATRIX.md), current models,
services and tests. All Q04 review-result fields remain `OPEN` and S07 remains
`PROPOSED`.

## 3. Rework comparison

| Option | Expected rework | Disposition |
| --- | --- | --- |
| Implement presentation remediation now | Low for purely semantic HTML and generic focus/touch improvements, but medium-high overall because role, scope, action availability, Self-Approval and unresolved-work states will change after P1.1/Q04 implementation. It also risks normalizing current tenant-wide filter semantics. | Not selected for P0-S20. |
| Assess/document now and remediate after authorization implementation | Low implementation rework. Accessibility debt remains temporarily, but its safe and blocked parts are explicit and can become acceptance criteria for the later journey. | Selected. |

## 4. Safe-now backlog, not implemented by P0-S20

The following presentation-only improvements are stable across likely backend
changes, but this assessment does not implement them:

- table caption and correct column-header scope;
- `aria-current` for the active workbench view and clearer accessible labels;
- visible keyboard focus, predictable focus after an error, and live-region
  announcement of existing success/error results;
- `aria-busy` and duplicate-submit feedback without weakening server idempotency;
- touch targets suitable for mobile use and responsive containment;
- distinct first-use and filtered-empty explanations;
- consistent use of existing Jalali, Persian-number and mixed-direction patterns;
- template tests for headings, table semantics, keyboard-visible controls,
  permission-safe action omission and error feedback.

These items may be pulled into a separately authorized small shared-accessibility
package if delaying them creates an unacceptable accessibility risk. Such a
package must not change visible authority, eligible records or action semantics.

## 5. UI work that must wait

- multi-role display, filtering, assignment or administration;
- Tenant Owner / Tenant Admin / Tenant Manager badges, action sets or implied
  inheritance;
- grant-aware project/site selectors, context visibility, counts and denial
  explanations;
- target eligibility/SoD explanations or action availability;
- Q04-G Self-Approval policy, Protected Operation classification, warnings,
  confirmations and audit views;
- Q04-H fallback indicators, unresolved-work queue and administrative recovery;
- any UI statement claiming Q04, S07 or P1.1 conformance.

## 6. Acceptance evidence and next bounded session

The later workbench-remediation session should start only after its required
authorization inputs are accepted and implemented. Its bounded acceptance set is:

1. server-derived effective role, permission, object-scope, candidacy/assignment,
   delegation and separation state;
2. grant-aware project/site options with no inaccessible names or counts;
3. authoritative Self-Approval/Protected Operation state where applicable;
4. authoritative unresolved-work visibility and recovery permissions if included;
5. keyboard, focus, RTL, Jalali, mobile/touch, empty/loading/error/concurrency and
   permission-safe browser/template tests.

The next bounded session is **not P0 integrated acceptance**. It should first
record actual Q04 accountable-review evidence and ADR dispositions, or execute a
separately approved P1.1 authorization package after those gates close. Remaining
P0 implementation sessions must be re-estimated and renumbered after the gates
resolve. A later explicitly authorized UI session can then remediate the workbench
against implemented server semantics.

## 7. Validation and exclusions

P0-S20 used targeted static inspection of the Roadmap, Playbook, UI guidelines,
Q04/S07 authorization records, current membership model, workbench service/view/
templates and direct workbench tests. No browser claim, WCAG conformance claim,
application test, migration, dependency or runtime validation is made because no
executable artifact changed.

