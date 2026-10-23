# Authorization Role Reconciliation and Platform Initial Grant

2026-10-22 — bounded Development implementation complete. Wider regression retains
four attributed registry failures. **Wave C remains blocked.**

Authority: [Human Product Decision](PRODUCT_DECISION.md). Branch `main`; start/end
HEAD and upstream `43ac319c6e73e48ca9626461b73987922c498ec3`. Existing Wave C work
was preserved. This is a bounded Product Decision task, not execution or closure of
another CEP. No canonical CEP prompt, dependency graph or live CEP lifecycle was
changed; the CEP Registry remains unchanged.

## Delivered behavior

- Reviewed 148 prior catalogue gaps: **147 explicit role mappings**, with
  `support.audit_reconcile` explicitly unassigned because no implemented
  enforcement path exists. All 663 catalogue codes appear in the
  [complete matrix](ROLE_PERMISSION_MATRIX.csv). The catalogue now has 28 roles:
  11 existing and 17 operational specialists. The specialist rationale is in the
  [decision record](PRODUCT_DECISION.md#matrix-review-rationale).
- Tenant Owner/Admin permission sets match HEAD exactly. Every other existing
  role has only its reviewed additions; new specialists have exactly their
  reviewed sets. The [matrix verification](MATRIX_SUMMARY.json) checks this against
  the original HEAD role definitions. Existing Support service/view permissions,
  previously absent from the registry, are registered without granting them to
  Owner/Admin. The unused audit code remains a documented catalogue exception.
- `apps/organizations/platform_grants.py` provides a dedicated transactional
  Initial Grant. It re-reads/locks active Platform Admin authority, active tenant,
  exact active receiver, approved active role/registered permissions and explicit
  tenant-owned scope. It rejects self-grants, duplicate assignments, broader or
  unrelated existing receiver scopes and grants for which ordinary tenant
  delegation has a lawful actor/independent approver pair.
- The existing role/scope records and correlated append-only audit events retain
  the platform actor, exact recipient, role permission snapshot, scope,
  before/after evidence, time and reason. No fake tenant assigning membership or
  second Platform approver is introduced. The trusted
  `manage.py platform_initial_grant` command calls the same service.
- `assign_membership_role()` and the ordinary authorization services are
  unchanged. Existing tenant creation already canonically establishes active
  membership, Tenant Owner assignment and Organization scope; regression verifies
  it without creating another bootstrap mechanism. Platform Admin/superuser/staff
  status alone does not create tenant business authority.
- Development test fixtures now contain explicit role/scope evidence. Historical
  blanket default-denial assertions were updated for the new operational matrix,
  retaining Owner/Admin denials and the existing domain tests. No product
  authorization contract was weakened to repair test setup.
- The newly accessible Supplier Portal management page exposed an existing
  missing required permission-message argument. Its one-line localized correction
  preserves tenant/project enforcement. **UIUX-F-132: runtime-verified resolved**,
  with a regression test and real GET/POST/CSRF/unauthorized/scope checks.

There are no new models, schema migrations, dependencies, Bootstrap Packages,
Platform Security approval workflows or parallel permission systems.

## Development reconciliation and affected Wave C

The existing code-owned catalogue synchronizer reconciled definitions, with audit
events for actual role-permission changes. Six exact scenario Initial Grants and
one isolated concurrency fixture grant were recorded. Five Development accounts
and memberships were added; existing buyer and explicitly linked workforce
identity were reused. Credential material remains in current-user Windows DPAPI
outside the repository and is absent from evidence.

- **RV-007:** opening/confidential permissions and independent custody/approval
  duties are assignable. The real issued RFQ closes on **2026-10-24**, so opening
  remains guarded by the existing close manifest, deadline and source/scan rules.
  No date, CLEAN verdict or confidential-source access was fabricated.
- **RV-029:** Employment manager and explicitly linked own-history actor are
  authorized. Real HTTP management/own-history access, invalid input and denial
  controls pass. Existing source-document policies remain enforced. No new
  employment record/document was manufactured; the full populated history journey
  was not rerun.
- **RV-032:** exact-project invitation management succeeds, including one real
  synthetic invitation POST, with no external tenant membership. Its plaintext
  token was not persisted. External original-payload custody/hash semantics remain
  unresolved and unchanged.

Accounting policy dates, AP/AR/Treasury source/mapping decisions, statutory
sources/schemas, Payroll payload selection and Tender activation are unchanged.
The current Wave C results/findings point to this bounded revalidation; previous
results and closed findings remain preserved. No full Wave C/CEP-078/079 closure is
claimed.

## Verification

| Check | Result |
| --- | --- |
| Final Initial Grant/matrix suite | **18 tests + 16 subtests PASS** |
| Protected-opening retest after fixture reconciliation | **9/9 PASS**, including concurrent requests/approvals |
| Affected selection, with subsequent fixture retests applied | **110/114 main tests PASS; 68 subtests PASS; 4 baseline registry failures** |
| Live Initial Grant race | One grant, one duplicate denial; one role and one scope record |
| Real authenticated HTTP | **18/18 expected observations**, including six POSTs |
| Existing domain integrity | 518 model fingerprints compared, excluding sessions; no pre-existing row deleted; financial, Payroll and Inventory models unchanged |
| Django check / migration drift | PASS / no changes detected |
| Ruff lint / new module format | PASS / PASS |
| Unrelated entry files / Git index and HEAD | Preserved |

The broad run initially had 105 passes and nine failures. Five Procurement fixture
failures were corrected and all nine protected-opening tests retested. The four
remaining failures are:

1. Duplicate registration of four existing Payroll models.
2. Existing resource-key/permission namespace mismatches.
3. Existing AST enforcement-reference gaps, plus the now explicitly documented
   catalogue-only Support audit placeholder.
4. Existing omission of `payroll.StatutorySourcePackage` from model registration.

[HEAD attribution](REGISTRY_BASELINE_DEBT.json) proves the unchanged duplicate and
namespace sets, existing enforcement gaps, and identical Payroll model omission.
These are retained debt, not a full-regression PASS or accepted production risk.
No full repository suite or new visual/accessibility audit was performed.

[Final verification](FINAL_VERIFICATION.json), [selected tests](VALIDATION_SELECTION.json),
[broad output](final.txt), [Initial Grant output](initial_grant_final.txt),
[opening retest](opening_retest.txt), [HTTP](HTTP.json),
[concurrency](CONCURRENCY.json), [data integrity](INTEGRITY.json),
[catalogue changes](CATALOG_CHANGES.json), [scenario grants](GRANTS.json).

## Handoff

Changes remain uncommitted on `main`. No branch/worktree creation, Git
add/commit/push/merge, production migration/deployment/cutover, Human Sign-off or
Production Certification occurred. The task's local runtime server is stopped;
other existing processes were preserved. Further Wave C work must honor the
remaining domain/source gates. No unrelated CEP was started.
