# UI/UX runtime evidence preparation

This directory is local audit preparation for the frozen UI/UX baseline
`43ac319c6e73e48ca9626461b73987922c498ec3`. No runtime scenario has been executed.
Preparation diagnostics are not RV result records or CEP-078/CEP-079 evidence.

## Directories

- `records/`: completed evidence records, only after authorized scenario execution.
- `screenshots/`: screenshots captured during authorized runtime validation.
- `diagnostics/`: entry preparation and gate verification evidence.

## Screenshot convention

`RV-<scenario>__<persona>__<state>__<viewport>__<sequence>.png`

Examples (filenames only; no screenshots have been captured here):

- `RV-001__P-01__login__1440x900__01.png`
- `RV-002__P-01__home-normal__1440x900__01.png`
- `RV-024__P-14__closeout-landmarks__390x844__01.png`

Use ASCII characters only. Never include usernames, email addresses, person names,
organization identifiers, UUIDs, tokens, or session values in screenshot filenames.
Viewports: desktop `1440x900`, narrow `1024x768`, mobile `390x844`.

## Evidence record convention

Use sequential IDs `RV-EV-001`, `RV-EV-002`, and so on. Store each as
`records/RV-EV-<sequence>.yaml` using the existing
[`UIUX_RUNTIME_EVIDENCE_RECORD_TEMPLATE.yaml`](../UIUX_RUNTIME_EVIDENCE_RECORD_TEMPLATE.yaml).
Do not create placeholder results or claim PASS before execution.

Record the runtime SHA, environment, base URL, browser/version, viewport, persona,
effective permissions and context, preconditions, expected and actual results,
keyboard/focus observations, screenshot paths, and explicit result. Use exactly the
result vocabulary in the frozen runtime validation matrix.

## Prepared identities and limitations

- `P-01-PROJECT`: `uiux.audit.project`, active membership in
  `demo-construction-01`, existing `viewer` role, explicit project grant to
  `PRJ-01-01`. Intended for RV-002 and RV-005. This is the narrowest existing
  ordinary read role; its permission catalogue was not changed.
- `P-01-EMPTY`: `uiux.audit.empty`, active ordinary authentication identity without
  any tenant membership or scope. Intended for the RV-003 empty state.
- Preserve `account.demo-construction-01.supervisor` with zero scope grants for
  no-workspace behavior and `account.demo-construction-02.owner` with its existing
  two valid memberships for no-context behavior.
- Unauthorized-context prerequisites use the prepared project's user's absence
  of membership in another existing demo tenant. No session manipulation or
  runtime exercise has been performed during preparation.
- Error-state coverage is `UTV_RUNTIME_ERROR_STATE`. No fault was injected; this
  limitation alone does not block the remaining runtime validation.
- `P-14-REPORTING`: `uiux.audit.reporting`, active membership in
  `demo-construction-01`, currently quarantined with no effective permissions,
  role assignments, or scope grants. The Human-authorized tenant-only role
  `uiux_runtime_reporting_test` contains the 22 existing permissions required by
  the actual creation/detail/reconciliation guards. No existing business role
  was changed, and the test role has no independent assignments.
- RV-024 remains blocked: neither existing tenant role assigner holds the entire
  proposed test-role permission set, which `assign_membership_role` requires.
  Platform Admin role-catalogue authority does not waive this check. No case was
  created, and no role/scope grant bypass was attempted. The final permission set
  was fixed before assignment; no permission staging was used.
- Employee Detail readiness was established by a read-only invocation of its
  decorated Django view with membership-validated context. The least eligible
  existing non-platform identity was `account.demo-construction-02.owner` in
  `demo-construction-02`. HTTP status was 200; no body was saved and no
  accessibility interaction was performed. Reporting endpoints remain unexercised.

Dedicated passwords were initialized through existing APIs. Windows current-user
DPAPI-protected PSCredential files are stored outside this repository under
`%LOCALAPPDATA%/BONIRA/UIUXRuntimeAudit/credentials/`. Do not copy decrypted values
into evidence, terminal output, screenshots, or source control.

> **SUPERSEDED BY CHECKPOINT 15 — provisioned reference persona identities are retained and reused. See RETENTION_SUPERSESSION_CHECKPOINT_15.md.**
>
> Current rule: **RETAIN → RECONCILE → RESET SECRETS IF NEEDED → REVERIFY BEFORE REUSE**.
> The following paragraph is historical guidance only, not operational authority.
> See [Checkpoint 15 retention supersession](RETENTION_SUPERSESSION_CHECKPOINT_15.md).

Retain prepared identities for authorized runtime validation. Afterwards, revoke
actual dedicated assignments/scopes with `revoke_membership_role` and
`revoke_membership_scope`, using independent approval where required; set the
dedicated membership inactive through `update_organization_membership`, retaining
its role definition. Archive only the test-only role with
`archive_organization_role`. Retain the authentication identity and audit history
unless an approved account lifecycle policy permits further action. No business
records were created or changed. If the case is later created, retain it explicitly
as the Development fixture identified by operation key
`uiux-runtime-entry-rv024-20261021`; no destructive case deletion is inferred.
