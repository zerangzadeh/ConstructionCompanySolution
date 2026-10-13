# CEP-001 Execution Manifest

- Authorization: AUTH-BATCH-001, CEP-001 only, development/non-production build.
- Repository baseline: `main` at `d75a9334d8e27683159c5f756725c0540651ec43`.
- Pre-existing worktree changes: deletion of `docs/architecture/PRODUCT_CAPABILITY_AND_READINESS_AUDIT.md` and untracked `docs/architecture/history/`; preserve both.
- Prerequisite CEPs/external dependencies: none in the canonical prompt. Entry implementation authorization is supplied by AUTH-BATCH-001. GATE-01 is an exit gate, not evidence of sign-off.

## Repository grounding before product mutation

Inspected: `ROADMAP.md` (P1.1), `docs/architecture/ADR_P0_S07_PROJECT_SITE_AUTHORIZATION.md`, `docs/architecture/WORKFLOW_AND_PERMISSION_MATRIX.md`, `docs/ui-guidelines.md`; `config/settings/base.py`, `config/urls.py`; `apps/organizations/{models,authorization,access_services,services,views,forms,decorators,middleware,admin,urls,apps}.py`; `apps/projects/{models,services,views,forms,admin,urls,tests}.py`; `apps/accounts/{admin,views,services,middleware,urls,test_admin}.py`; representative tenant Admin registrations in `apps/accounting/admin.py`, `apps/parties/admin.py`, `apps/documents/admin.py`, and the repository-wide Admin registration inventory; `apps/organizations/{test_p1_1_authorization,test_admin}.py`; `pytest.ini`.

Repository reality: P1.1 already supplies active membership, role permission, project/site grant checks, and project/site selectors. `scope_queryset` relies on its caller to filter by organization; given an unfiltered queryset and an organization grant it can return other tenants' rows. Many Django Admin registrations use default global querysets, so platform superuser status currently exposes tenant records without explicit tenant authority. Project/site business routes already call tenant selectors. The repository commit matches the canonical prompt's design baseline. The repository's roadmap uses P1.1 numbering rather than CEP numbering; this package is a bounded security hardening of that foundation, not authorization for another roadmap item. Canonical source titles outside this repository are represented by the supplied CEP prompt; no missing source is treated as implemented evidence.

## Actual execution touch set

| Surface | Existing models/components affected | Expected files |
| --- | --- | --- |
| Shared scope contract | `OrganizationMembership`, `MembershipScopeGrant`, `Organization`, `Project`, `ProjectSite`; no model-field changes | `apps/organizations/authorization.py` |
| Django Admin tenant boundary | Existing tenant-owned Admin registrations and platform technical catalog; no new role hierarchy | Shared Admin guard in `core/`, Admin site configuration in `config/`, targeted `apps/organizations/admin.py` or `apps/accounts/admin.py` adjustments only if needed |
| Company/project/site service, forms, deep links, search | Existing project selectors/services, organization context and Admin search/form entry points | `apps/projects/services.py`, `apps/organizations/services.py`, relevant Admin configuration only where tests reveal a gap |
| Tests | Permission, tenant isolation, service, direct URL, Admin list/search/detail, UI/template regression | New focused CEP-001 tests under `apps/organizations/` and existing targeted test updates only if contract changes require them |
| Configuration | Django Admin site registration if shared guard is used | `config/settings/base.py`; no other setting is planned |
| Schema/migrations/data | None planned or authorized by canonical migration impact | None |
| Documentation/evidence | Existing roadmap disposition and five required CEP artifacts | `ROADMAP.md`, `CEP-001_EXECUTION_MANIFEST.md`, `CEP-001_ACCEPTANCE_MAPPING.csv`, `CEP-001_EVIDENCE_MANIFEST.csv`, `CEP-001_CHANGE_MANIFEST.csv`, `CEP-001_COMPLETION_REPORT.md` |

The shared guard must fail closed for tenant-owned Admin models without a mapped business permission and must leave platform-only identity/catalog operations separate. It must not treat session context, `is_staff`, `is_superuser`, or a platform role as tenant authority. Any unavoidable schema change or material mismatch with these boundaries requires a finding before proceeding.

Focused pre-change baseline: two existing authorization/project selector tests were started with `.venv/Scripts/python.exe`; result will be recorded in the evidence manifest. The `python` command on PATH is a Microsoft Store alias and cannot run project checks.

## Execution reconciliation (2026-10-13)

- A dedicated `cep/CEP-001-tenant-object-scope` branch was created after this pre-mutation manifest; the baseline commit stayed unchanged and the pre-existing documentation move was preserved.
- Actual code touch set: `core/admin.py`, `config/admin_config.py`, `config/settings/base.py`, `apps/organizations/authorization.py`, `apps/organizations/admin.py`, `apps/audit/admin.py`, and `apps/organizations/test_cep001_security.py`. Project services/forms/views and account code were inspected but needed no edit. No model, schema, migration or application data was changed.
- Focused baseline pytest was interrupted when first-time test database setup proved slow. A no-migrations shortcut could not create an existing GiST constraint because it omits PostgreSQL extension migrations. The normal disposable test database setup completed once; final focused tests passed with database reuse.
- `CEP-001-FINDING-001 / BLOCKER-SECURITY` at the first execution closeout: existing `_legacy_scope_compatibility` in `apps/organizations/authorization.py` gave an unmigrated, unquarantined active Membership with no scope grant organization-wide service scope while Admin denied it. The 2026-10-14 remediation below removes that implicit service authorization without changing records or the legacy role-read compatibility.
- `CEP-001-FINDING-002 / BLOCKER-EXTERNAL` at the first execution closeout: the then-supplied canonical prompt named `GATE-01` without its criteria or disposition, and repository search found no definition. The later Human-supplied final closure prompt provides the authoritative Foundation Stability definition and required IMBs; final disposition appears below.

## Remediation grounding and touch set (2026-10-14; before mutation)

- Branch and starting HEAD: `cep/CEP-001-tenant-object-scope` at `d75a9334d8e27683159c5f756725c0540651ec43`. The first CEP implementation was uncommitted. The unrelated pre-existing audit-document move remained untouched.
- Re-inspected the prior CEP changed code, tests, roadmap and evidence; current membership and scope models, `authorization.py`, project service/decorator/form paths, Admin guard, role/grant service, migrations `0030`–`0031`, P1.1 authorization tests and the canonical prompt. `git diff` against the baseline showed the previous CEP hardening and the separate audit-document move.
- Authorization flow before remediation: active user and Tenant Membership -> effective role or legacy role permission -> `membership_has_scope` or `scope_queryset` -> service/URL/form. For an unmigrated unquarantined Membership without any grant, `_legacy_scope_compatibility` produced organization-wide scope. The Admin guard independently denied that row. A migrated no-grant Membership already denied. For explicit project/site grants, service and Admin both restricted by object; an explicit Organization grant represented broad Tenant scope.
- Migration `0031` backfilled explicit Organization grants only for evidence-supported legacy owners and quarantined ambiguous roles. New owner bootstrap creates an explicit grant. Development database read-only count: 25 active Memberships, zero unmigrated without grants, 17 migrated without grants, all 17 quarantined. Production data was not inspected.
- The current remediation touch set was declared before mutation: `apps/organizations/authorization.py`, `core/admin.py`, `apps/organizations/test_cep001_security.py`, `ROADMAP.md`, `docs/architecture/WORKFLOW_AND_PERMISSION_MATRIX.md`, five CEP-001 artifacts and `output/cep-001/` evidence logs. Regression runs exposed legacy no-grant fixtures; before each expansion the touch set was extended to `apps/projects/tests.py`, `apps/accounts/test_admin.py` and `apps/organizations/tests.py`. Those extensions are CEP-001 test fixture corrections only.
- No model, schema, migration, application-data, Production or irreversible operation is in the touch set. At remediation time, the then-supplied prompts named `GATE-01` without defining it. The subsequent final closure prompt supplies its authoritative definition.

## Remediation result

- `membership_has_scope` and `scope_queryset` now derive all scope from effective explicit same-Tenant grants, including when a stored grant row has an inconsistent Tenant reference. The duplicate Admin-only legacy denial was removed, so Admin and service decisions share one policy. Legacy role permission read compatibility remains, but the role does not create object scope.
- Test cases cover explicit project/site grants, no grant, revoked grant, an inconsistent wrong-Tenant grant, missing business permission, Admin/service consistency and explicit Organization scope. Legacy fixtures expecting authorized access now create explicit Organization grants.
- Focused CEP tests: 10 passed. The expanded combined regression run found 18 stale organization fixtures while 121 other tests passed; after fixture correction, all 63 organization tests passed. Ruff check/format and Django system checks passed. See the completion report and evidence manifest for exact logs.
- `CEP-001-FINDING-001` is resolved at the code policy level. The subsequent closure verification supplies the gate definition and supersedes the earlier provisional gate assessment. Human Sign-off remains NOT EXECUTED.

## Final closure verification (2026-10-14)

- Branch and starting/ending HEAD remain `cep/CEP-001-tenant-object-scope` at `d75a9334d8e27683159c5f756725c0540651ec43`. CEP-001 code, tests, documentation and evidence remain uncommitted in the working tree. The pre-existing audit-document move remains separate and untouched.
- Before final validation, recorded `git status`, `git diff --stat` and full tracked `git diff` in `output/cep-001/final-prevalidation-git-diff.patch`. Untracked CEP source and evidence files are inventoried separately; Git does not include them in that diff.
- After documentation reconciliation, recorded the final tracked diff in `output/cep-001/final-working-tree-git-diff.patch`. No commit or branch change was made.
- Exact combined command: `.venv\Scripts\python.exe -m pytest apps/organizations/test_cep001_security.py apps/organizations/test_p1_1_authorization.py apps/organizations/test_admin.py apps/organizations/tests.py apps/projects/tests.py apps/accounts/test_admin.py --reuse-db -q --tb=line`. Development settings and disposable reused PostgreSQL test database; Python 3.11.1. Collected 140, passed 140, failed/skipped/xfailed 0, duration 244.82 seconds. The previous combined run collected 139 (121 passed, 18 failed); one new wrong-Tenant-grant test accounts for the count increase. The 18 legacy fixture defects were corrected before this clean final run.
- Separate final focused CEP security command covered the ten case A–F tests: 10 passed in 21.90 seconds. The combined run also covers 22 P1.1 authorization tests, 9 organization Admin tests, 63 organization service/tenant tests, 21 project service tests and 15 account Admin tests. Ruff and Django checks passed.
- The Human-supplied final closure prompt authoritatively defines `GATE-01` as Foundation Stability, a foundation stability gate requiring IMB-0001, IMB-0002, IMB-0003, IMB-0030, IMB-0052, IMB-0055 and IMB-0069. CEP-001 contributes IMB-0001 and IMB-0002 only; both have 6/6 Acceptance Criteria PASS and canonical DoD PASS. Global GATE-01 is pending the other required IMBs and is not claimed passed.
- Final status claim: CEP-001 **EXECUTION COMPLETE** for its bounded Development implementation and evidence. Global GATE-01 remains pending, Human Sign-off NOT EXECUTED, Production actions NOT EXECUTED, and CEP-002 NOT STARTED.
