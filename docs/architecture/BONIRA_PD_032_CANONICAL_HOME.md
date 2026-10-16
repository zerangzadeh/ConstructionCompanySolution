# PD-032 — Canonical Home ownership, route and bounded composition

This is the approved successor addendum to the canonical Product Decision register, limited to PD-032. The sealed v1.0 register remains the authority for PD-001 through PD-031.

**Decision status:** FROZEN — PD-032 addendum only

**Decision authority:** Human/Product Owner instruction, “BONIRA — CEP-002 Home Decision Canonicalization,” 2026-10-14. It explicitly approves the semantics in [CEP-002_HOME_GOVERNANCE_RESOLUTION.md](../governance/cep/supporting/CEP-002_HOME_GOVERNANCE_RESOLUTION.md).

**Freeze authority:** Human/Product Owner command `APPROVE PRODUCT DECISION FREEZE — PD-032 ADDENDUM`, 2026-10-14. See [the addendum freeze record](BONIRA_PD_032_FREEZE_RECORD.md).

**Scope:** `IMB-0003` / `CEP-002` only. This record grants no additional implementation, production, migration or Human Sign-off authority.

## Register identity and freeze boundary

The reconstructed latest `BONIRA_PRODUCT_DECISION_FREEZE_CONSOLIDATED_LATEST.zip` in `E:\ERP_Construction_Documents\New Version\BONIRA_TRUE_LATEST_STATE_RECONSTRUCTION_20261013\Consolidated_Packages` contains `BONIRA_FINAL_PRODUCT_DECISION_REGISTER.md`. Its final governing sequence is `PD-001` through `PD-031`; `PD-016` is **Logical Role vs Person Separation**. Thus `PD-032` is the next valid sequential Product Decision ID. The provisional `PD-HOME-CANDIDATE-001` is retired as a proposal identifier and is not a governing PD.

The historical register has freeze ID `BONIRA-PD-FREEZE-20261012T002549+0330`, version `v1.0`, with 31 frozen decisions. Its rule requires explicit Product Owner freeze authority. The later command `APPROVE PRODUCT DECISION FREEZE — PD-032 ADDENDUM` freezes this successor decision only. PD-032 is **not part of the sealed v1.0 freeze**; no v1.0 count, hash, manifest or freeze record is rewritten. The addendum has its own ID, version and integrity evidence in the linked freeze record.

## Approved decision

The canonical authenticated Home is `/`, route name `home`. Login, organization switching and the shared shell identity link target it when implemented. It is a neutral, Persian-first, permission-aware entry into BONIRA. The existing `financials:dashboard` is not Home and remains a separately permissioned legacy financial workspace under its existing financial authorization.

Home may compose only authorized workspace/navigation links, an assigned-work entry, active organization context, permitted alert links and profile controls. It creates no KPI, business fact, new authority, cross-domain aggregate or source of truth. Presentation may vary only by explicit effective permissions, object scopes and existing approved role assignments. Job title, profile label, username and company size grant nothing. Multiple roles compose applicable permissions without inventing a composite role. `PD-016` continues to govern role/person separation only.

| Home element | Existing authority/source | Bound |
| --- | --- | --- |
| Workspace links | Existing named routes and `apps.organizations` effective permission/scope services | The destination rechecks its own backend authorization; Home visibility is not a grant. |
| Assigned-work entry | Existing `workflows:workbench` and workbench authorization | Link only; no new count, copied work item or Home-owned queue. |
| Organization context | Validated active organization and membership from organization middleware/services | No tenant business query without active authorized context. |
| Alert entry | Existing permissioned `support:notifications` route | Link only; no new alert aggregate. |
| Profile controls | Authenticated user and `accounts:settings` | Own profile only. |

Required presentation states are: normal; empty; no authorized workspace; no active context; unauthorized; error; and multi-role/multi-permission. Empty and error states disclose no protected object existence or sensitive facts. No active context leads safely to organization selection. No authorized workspace presents only account or connection options already available to that identity. A direct destination URL applies the same backend permission and object-scope checks as navigation. Multi-role Home deduplicates destinations and respects each destination's effective scope. Jalali-facing dates apply only if an approved Home element actually presents a date.

## Canonical reference correction layer

This decision is the Home authority over the sealed historical references below. The archived package files remain immutable history; their misleading `PD-016` Home source attribution is superseded by this narrow correction. `PD-016` remains cited where role/person composition is genuinely relevant. No scope, AC, DoD, DAG edge, prerequisite or `AUTH-BATCH-001` authorization is changed.

| Reconstructed latest source | Corrected reference interpretation |
| --- | --- |
| `BONIRA_FINAL_IMPLEMENTATION_MASTER_BACKLOG.csv`, `IMB-0003` Product Decision field (`PD-016`) | `PD-032` governs Home purpose, route, bounded content and states; `PD-016` governs only role/person composition. Keep the existing outcome and all six AC/DoD unchanged. |
| `BONIRA_IMPLEMENTATION_TRACEABILITY_MATRIX.csv`, `PD-016` source row covering `IMB-0003` | Retain that coverage only for role/person composition. On successor package regeneration, add a distinct `PD-032` source row covering Home ownership for `IMB-0003`; do not relabel the historical `PD-016` identity. |
| `BONIRA_TARGET_WORKSPACE_CATALOGUE.md`, `WS-01` dependency 16 and blocks 4, 6–10 | Add `PD-032` as Home authority and qualify `PD-016` as composition policy. The approved Home content is limited to links/entries and context. Existing wording about My Tasks/My Requests summaries, notification indicators or “aggregation only” does not authorize a Home-owned summary, count or aggregate. |
| `BONIRA_UI_ARCHITECTURE_REGISTER.csv`, `UIA-001`, `UIA-013`, `UIA-021` | Cite `PD-032` for canonical Home/landing. Retain `PD-016` for effective role/person composition only; retain other genuinely applicable references such as `PD-024` without inferring profile behavior. |
| `BONIRA_UI_ARCHITECTURE_REGISTER.csv`, `UIA-012`; `BONIRA_UI_WORKSPACE_ARCHITECTURE_RECONCILIATION.md`, `UI-ARCH-01` | Cite `PD-032` for the Home entry/route. Preserve `PD-016` for role/person policy and the existing shared-shell visual authority. |
| `BONIRA_TARGET_NAVIGATION_TREE.md`, `NAV-001` | Its canonical Home destination resolves to `/` / `home` under `PD-032`; the financial dashboard remains separate. No new navigation authority is created. |
| `BONIRA_CODEX_EXECUTION_PACKAGE_DESIGN_CONSOLIDATED_LATEST.zip`, `packages/CEP-002.md`; `BONIRA_CODEX_EXECUTION_PROMPT_CONSOLIDATED_LATEST.zip`, `prompts/CEP-002_EXECUTION_PROMPT.md` | Keep `PD-016` for its actual role/person purpose and add frozen `PD-032` as Home authority in successor source traceability. Scope, AC, DoD, DAG and authorization remain verbatim. |

The correction layer applies to the named records in their reconstructed latest packages. It does not assert that other cited IDs (`E2E-NAV-001/002`, `DTR-GAP-001`, `RMB-0703`) misuse PD-016; no change is made to their definitions or dependency topology. Source packages and their original checksums remain unmodified.

## Execution disposition

The missing Home semantics and mistaken PD-016 attribution are resolved by this frozen addendum and its authoritative reference correction layer. `BLOCKER-PD` is **RESOLVED**; no other Product Decision or specification blocker was identified in the scoped CEP-002 sources. Regeneration of historical source-package references is a documentation follow-up and does not alter the sealed packages or the governing addendum. CEP-002 implementation is **NOT RESUMED**. Human Sign-off is **NOT EXECUTED**.
