# CEP-017 Execution Manifest

## Authorization and recovered source status — 2026-10-16

- Authorization: `AUTH-BATCH-003`; resume authorizations: `CEP-017-RESUME-01`,
  `CEP-017-VERIFY-RESUME-02`, and `CEP-017-ENV-RECOVERY-03`.
- Branch: `main`; HEAD: `89ca8f28da8828a6ac4226baceb18d27c5d98f09`.
- Baseline `git status --short`, `git diff --name-status`, and `git diff --stat`: empty.
- Canonical execution prompt SHA-256: `C4B318780C224A2F9126B6B69E4123FD8ED6B6ECD4FE703155BA6E831424C400`.
- Recovered canonical UI-source archive SHA-256: `73FE660188E8937002618C455F6E71791EF31313688770D13DB1AE9264FFF515`.
- Prior `CEP-017` `BLOCKER-SPEC / BLOCKER-REPOSITORY`: **RESOLVED BY CANONICAL SOURCE RECOVERY**. The recovered navigation tree, workspace catalogue, role/workspace matrix, UI register, reconciliation, completion audit, and evidence index supply the exact canonical navigation/workspace architecture that was previously unavailable.

## Entry checks

- Direct prerequisite `CEP-002`: **EXECUTION COMPLETE** (current governed status and final review).
- `GATE-01`: **PASS** in the current authoritative `ROADMAP.md` Foundation reconciliation; older `AUTH-BATCH-001` snapshots are historical and not used as current gate authority.
- Migration impact: **NONE**. No schema or data migration is authorized or required.

## Repository grounding

The server-rendered application already has a Persian-first shared shell in `templates/base.html`, a duplicated desktop/mobile navigation component in `templates/components/navigation_links.html`, per-route backend permission enforcement, and a reusable `page_header` breadcrumb component. Existing navigation is permission-filtered but is organized around legacy route groupings rather than the canonical 43-node workspace tree. The mobile drawer uses a native disclosure but has no explicit close control or Escape handling. Existing direct URLs retain their views' authorization; this package does not alter them.

## Actual execution touch set before product mutation

| Surface | Intended change | Migration |
| --- | --- | --- |
| `templates/components/navigation_links.html` | Replace legacy menu grouping with the canonical 43-node architecture; retain only existing route links and their existing discoverability checks. | None |
| `templates/base.html` | Make the shared mobile drawer explicitly closable by backdrop, button, navigation selection, and Escape. | None |
| `templates/components/page_header.html` | Provide a consistent Home-first breadcrumb for page-header users. | None |
| `core/test_cep017_navigation.py` | Assert canonical node coverage, RTL shell/breadcrumbs, drawer semantics, and no new routes or permissions. | None |
| CEP-017 manifests and `ROADMAP.md` | Evidence and status closeout. | None |

Domain views, models, services, permission catalogues, migrations, route definitions, and backend authorization remain outside this touch set.

## Test-infrastructure recovery and final verification — 2026-10-16

The historical reused-database failure (`expenses_expense` already existed) and
the bounded fresh-database timeout are retained in the evidence manifest. The
isolated database `test_cep017_verify_20261016` was inspected directly: it had no
blocking session, its migration recorder was healthy, and its last completed
migration was `treasury.0007`. The next operation was `treasury.0008`.

Running that migration with progress output showed PostgreSQL idle in transaction
and waiting for the client after the final constraint statement, with no blocker;
the command then completed in 35.99 seconds and generated the repository's large
post-migrate content-type/permission catalogue. The remaining normal migration
chain completed successfully. The apparent setup stall was therefore baseline
test-initialization latency, principally migration and post-migrate permission
generation, not a connection, lock, schema-corruption, or CEP-017 application
failure.

The required focused/Home regression then passed 15 tests. An affected platform
navigation regression reached execution and found one stale expected Persian
heading; the rendered controls and authorization links were present under the
canonical CEP-017 heading. The test-only expectation was updated, and the final
combined regression passed 16 tests. No application implementation, model,
migration, route, permission, tenant-scope, or business-semantic change was made
during recovery.
