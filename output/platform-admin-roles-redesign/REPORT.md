# Platform Admin roles and permissions redesign

Date: 2026-11-07 (Asia/Tehran). Branch: `main`. Starting HEAD and local
`origin/main`: `1d3593a91536477fcfd146a522701980b9ebf205`.

## Scope and working-tree preservation

Implemented the explicit UI redesign request for `/organizations/platform/roles/`
and its existing tenant-role/member-assignment destinations. This is a bounded
Human-authorized UI task, not CEP execution. The attached dashboard images guide
visual composition; their example data and controls do not define capabilities.

The working tree was already dirty. Overlapping sources were copied to
`baseline/` before editing; `baseline/status.txt` and `baseline/dirty-files.txt`
record the starting state. Existing work remains in place. No branch, worktree,
commit, push, production operation, model change, migration, permission code,
RBAC calculation, or business service change was introduced by this task.

A concurrent dashboard redesign appeared during this session. In
`platform_console.py`, its dashboard archived-count filter changed from
`status=archived OR archived_at IS NOT NULL` to `status=archived`. That unrelated
hunk is retained, not part of this task. `existing-files.patch` records changes
since the captured baseline and therefore includes this concurrent hunk; only
the member-selector additions in that module belong to the roles redesign.

## Changed files

| File | Change |
| --- | --- |
| `apps/organizations/views.py` | Platform-only list filters, default read view, selected-role redirect, readable existing validation messages, and permission-aware assignment controls. Existing tenant resolution, POST payloads and service calls remain authoritative. |
| `apps/organizations/platform_console.py` | Presentation context for the existing authorized tenant selector. |
| `apps/organizations/role_presentation.py` | Registry-based permission grouping, bounded ten-role pagination, role protection/availability presentation and existing searchable-selector composition. |
| `apps/organizations/static/organizations/role_workspace.css` | Opt-in responsive role workspace using BONIRA tokens, visible focus and sticky editing actions. |
| `apps/organizations/static/organizations/role_workspace.js` | Permission search, selected-only filtering, disclosure/count updates and unsaved-change protection. |
| `templates/organizations/platform_roles.html` | New platform-only master-detail workspace. The existing tenant-admin role catalogue template is retained. |
| `templates/organizations/platform_roles_navigation.html` | Three clearly distinguished existing destinations and selected navigation state. |
| `templates/organizations/platform_member_roles.html` | Searchable tenant selection and explicit administrative target context alongside existing member search/history. |
| `templates/organizations/member_authorization.html` | Platform-only target context and presentation of existing authorized assign/revoke controls. Tenant workspace behavior is retained. |
| `apps/organizations/test_platform_roles_ui.py` | Focused UI, tenant scope, protected/retired role, save, validation, stale-version and read-only inspector regressions. |
| `apps/accounts/static/css/tailwind.css` | Existing CSS build output regenerated while retaining pre-existing source changes. |

Evidence and repeatable local verification helpers are contained in this output directory.

## Delivered behavior and reuse

- System/global roles, tenant-specific roles and member assignments use their
  existing routes. System and global-custom records retain their existing scope;
  the type filter distinguishes them without omitting existing records.
- The right-hand role list supports server-side name/code search, type/status
  filters, stable ordering and ten-record pagination. Selection reveals a read
  view; editing and creating are explicit actions.
- Permissions use the exact existing form queryset. Their actual
  `PERMISSION_RESOURCES` ownership/enforcement modules determine their domain
  groups. Persian group headings are presentation labels, not new permissions.
  Native `details` groups are collapsed initially and display selected/total counts.
- Persian-label and exact technical-code search search all groups, reveal matching
  rows and restore previous disclosures when cleared. Selected-only filtering,
  an empty result state and live counts are included. Hidden rows retain native
  successful form controls and are never dropped from the submitted selection.
- Protected role permissions remain locked. Existing unavailable/retired
  assignments are visible and make the role read-only to avoid silently dropping
  records that its existing form cannot resubmit. Archived roles remain inspectable.
  Existing self-elevation and role restrictions continue to run in the services.
- Edit mode retains the original CSRF token, `role_id`, administrative target,
  `expected_updated_at`, reason and named action. The existing audit services own
  every outcome. The successful redirect returns to the saved role in read mode.
- Save/Cancel stick to the viewport while editing. Field/form errors reuse shared
  accessible components. Internal navigation uses `BoniraFeedback.confirm` for
  unsaved changes; browser reload/close uses native `beforeunload`. Archive uses
  the existing declarative SweetAlert2 integration. No approval workflow was added.
- Tenant selectors reuse `SearchChoiceSelect`, the already bundled Tom Select
  assets and `field_choices.js`; ordinary native selection remains available
  without JavaScript. Selecting the administrative target never switches the
  active session tenant. Member search retains its existing username semantics.
- Assignment and revocation reuse `MembershipRoleAssignmentForm`, the existing
  `assign_membership_role`/`revoke_membership_role` services, target-tenant
  authorization and existing independent approval. Read-only inspectors do not
  receive mutation controls.
- No bulk permission selection is offered: the existing registry does not define
  a generally safe group-level grant contract. Individual edits preserve existing
  dependencies and restrictions through the existing server validation.

## Verification

The first focused run and its repeat passed **50 tests and 26 subtests**. The
final expanded run uses a fresh isolated PostgreSQL database,
`test_bonira_roles_redesign_20261107`, through `verify.py`; see `tests-final.log`.
The test selection includes the workspace tests, Platform Console tests,
P1.1 authorization tests and CEP-014 administration regressions.

Final expanded test result: **51 tests and 26 subtests PASS** in 1041.17 seconds,
including the initial database setup. All 454 existing repository migrations
were applied to the fresh isolated test database. The nine new workspace tests
passed. No new migration file was created. End HEAD matches the starting HEAD.

Django system checks, focused Ruff lint/format checks, whitespace checks and the
CSS build pass. `css-build.log` retains the non-blocking outdated Browserslist
metadata notice. No new dependency was installed.

### Browser evidence

Actual Chrome verification used the connected browser and the computer-use skill.
Read-only visual comparison used the existing development page. Mutation journeys
used synthetic `roles-browser-*` records only, served at `127.0.0.1:8016` from the
previous isolated test database `test_bonira_platform_completion_01a1b05d`.
Mutation journeys were confined to that test database; no development/production
role or assignment was changed. `browser_server.py` preserves the fixture setup
for repeatable review.

| Viewport | Document height, default view | Horizontal overflow | Initially open permission groups |
| --- | ---: | --- | ---: |
| 1440 × 1000 | 1559px | None | 0 |
| 1024 × 1000 | 2456px | None | 0 |
| 768 × 1000 | 2448px | None | 0 |
| 390 × 1000 | 3704px | None | 0 |

The original 1440px page measured **15180px**, with **670 expanded permission
checkboxes**. The redesigned default view is **89.7% shorter** at that width.
At mobile widths it uses a stacked list/detail composition; role links jump to
the detail and a return link goes back to the list. There is one document scroll
region, with no nested scrolling introduced by this workspace.

Browser journeys verified:

- Find and inspect a role; search Persian labels and technical codes across closed
  groups; show only selected permissions; reset/collapse groups.
- Edit the synthetic global role, select `projects.create`, save, reload and
  observe the persisted selection and count through the real server response.
- Cancel the shared unsaved-change dialog and retain edits.
- Submit a whitespace-only required name and observe field errors in the shared
  summary while retaining the form.
- Save another tab's edit, then submit the older version and observe rejection.
- Inspect protected Company Owner permissions: 670 displayed choices, zero
  editable permission checkboxes and a retained version token. Keyboard Enter
  opens the native disclosure.
- Search/select a tenant, edit its role description, save and observe only that
  target's role/result.
- Search a target member, assign Viewer with the existing independent approver,
  revoke that exact assignment and observe the actual revoked history and
  server-generated success message.
- Inspect mobile member authorization with no document overflow. Verify the
  editing Save button is inside the viewport at 1440px and after opening the
  editor at 390px (button bottom 988px within a 1000px viewport).

### Captures

See `screenshots/` for the supplied original before reference
(`before-provided-1920.png`) and after viewports at all four requested widths,
code search, protected roles, sticky desktop/mobile editing, unsaved confirmation,
validation, stale version, tenant save and member assignment/revocation.
Full-page Chrome capture timed out. The browser's before overview was reduced to
a narrow thumbnail; use the supplied original for legible before detail. After
captures show the inspected viewports, excluding browser scrollbars. Document
heights and requested viewport widths are read from the browser DOM.
The member-mobile resize-attempt capture retained a reduced pre-resize frame;
its no-overflow result is DOM evidence. Use `editing-mobile-390.jpg` for the
visually reviewed mobile editor. The temporary verification server and tabs were
closed, viewport overrides reset, and the original development roles tab restored.

## Limitations and acceptance

- Browser zoom shortcuts did not change the inspected tab's measured zoom.
  Actual 200% browser zoom remains unverified; the four requested responsive
  widths, keyboard disclosure and mobile editing were verified. The attempted
  capture is named `zoom-shortcut-attempt.jpg`, not proof of 200% zoom.
- Searchable tenant selection uses the qualified local-choice widget and existing
  allowed tenant choices. A new remote tenant lookup API is outside this task.
- Browser mutations and success messages were exercised on isolated synthetic
  fixtures; no real tenant permission change was performed.
- The default view is compact, while explicitly expanding many groups or selecting
  a large role's entire selected-permission set intentionally exposes more rows.
- No claim of Production Certification or Human/Product Owner visual acceptance
  is made. Product Owner visual acceptance remains pending.

Implementation and the scoped automated/browser checks are complete, with the
explicit 200% zoom verification limitation above. The work is ready for Human
visual review; it is not a Product Owner acceptance declaration.

Git add/commit/push/merge: **NOT EXECUTED**. Production operations: **NOT EXECUTED**.
