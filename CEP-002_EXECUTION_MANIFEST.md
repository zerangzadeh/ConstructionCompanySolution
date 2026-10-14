# CEP-002 Execution Manifest

## 2026-10-14 authorized resumption grounding (before product mutation)

- Branch: `main`; HEAD: `967861037bba4a8e376f3ba0adf46763662eae9c` (completed CEP-001 state).
- `git status --short`: `ROADMAP.md` modified; CEP-002 governance/evidence files, PD-032 decision/freeze files, and `output/cep-002/` untracked. These pre-existing user changes are preserved.
- `git diff --stat`: `ROADMAP.md | 18 ++++++++++++++++++` (tracked diff only).
- Freeze gate: `BONIRA_PD_032_CANONICAL_HOME.md` explicitly FROZEN; its SHA-256 matches `BONIRA_PD_032_FREEZE_RECORD.md`. Original `BONIRA-PD-FREEZE-v1.0` PD-001..PD-031 archive hash matches the sealed hash in the addendum record. No original freeze mutation.
- Actual Execution Touch Set for resumption: `config/urls.py`, `config/settings/base.py`, `core/home.py`, `core/views.py`, `templates/home.html`, `templates/base.html`, `templates/components/navigation_links.html`, `apps/organizations/views.py`, `apps/organizations/middleware.py` (invalid-selection leakage correction found by CEP-002 test), focused Home and redirect tests; CEP-002 evidence artefacts and `ROADMAP.md` for closeout. No financial dashboard, permission catalog, migration, original freeze, or other CEP mutation.
- Earlier sections below record the historical pre-freeze execution stop; they are not the status of this authorized resumption.

## Resumed execution and verification result

- Final remediation grounding: branch `main`, HEAD `967861037bba4a8e376f3ba0adf46763662eae9c`; `git status --short`, `git diff --name-status` and `git diff --stat` recorded before additional mutation. Product touch set remained CEP-002 / IMB-0003; no Git index or history mutation.
- Final Actual Execution Touch Set adds only `core/test_home_browser.py` and `output/cep-002/browser_probe.mjs` plus synthetic-fixture screenshots to the earlier Home/redirect/shell/security correction and current CEP-002 evidence/ROADMAP files. No production model, migration, permission grant/catalog, workflow or financial product code was changed.
- Fresh isolated database `test_cep002_isolated_20261014`, normal migrations, no `--reuse-db` or `--no-migrations`: 68 collected, 53 passed, 15 failed, 0 skipped, 0 xfailed in 1820.02s. This resolves the prior reusable-test-DB `DuplicateTable` issue as an environment collision, but **not** the 15 failures. `apps/procurement/tests.py::ProcurementFixtureMixin` and `apps/financials/tests.py::FinancialReportTests` directly create legacy memberships without current effective role assignments/scope grants. Correcting those shared cross-domain fixtures is beyond CEP-002 scope (EV-015).
- Headless Chrome live-server runtime: normal, empty, no-context, unauthorized and error Home at 1440×900 and 390×844; no material horizontal overflow, RTL and mobile navigation/profile usable, unauthorized context hidden, financial dashboard separate. One browser test passed in 58.64s; ten synthetic-fixture screenshots retained (EV-016).
- Final focused Home/browser/account/organization/CEP-001 security suite: 54 passed, 0 failed, 0 skipped, 0 xfailed in 86.04s. Ruff check/format, Django system check and no-migration dry run pass (EV-017).
- Regression attribution (`CEP-002_REGRESSION_ATTRIBUTION.md`) classified all 15 broader failures as Category B, cross-domain legacy fixture debt. Every workflow failure stops in purchase-request creation and every financial failure stops in common project setup; no changed CEP-002 behavior is reached (EV-018).
- Final verdict: **EXECUTION COMPLETE**. AC 6/6 PASS; canonical DoD PASS; responsive/mobile is PASS within the tested browsers/widths, not exhaustive certification. The 15 Category B findings are separately recorded and do not block CEP-002.

- Historical `BLOCKER-PD` → frozen PD-032 → implementation resumed. Product touch set stayed within IMB-0003; the sole additional middleware line prevents unauthorized invalid-session Home from leaking a fallback organization's name.
- Focused Home/account/organization-switch/CEP-001 security suite: 53 passed, 0 failed, 0 skipped, 0 xfailed (EV-011). The prior interrupted runs are not treated as PASS.
- Earlier broader workflow/financial regression attempt: 51 passed, 15 failed under `--no-migrations`; migrated one-test setup hit `DuplicateTable` in the reused test database (EV-012/013). These were historical intermediate results; EV-015 supplies the fresh migrated diagnosis.
- Earlier Ruff check and format check, Django system check, migration dry run and `git diff --check` passed. At that earlier checkpoint browser verification was UTV and the execution verdict was **PARTIAL**. EV-016 subsequently verified the browser behavior, and the current final verdict is **EXECUTION COMPLETE** as recorded above. Human Sign-off remains NOT EXECUTED.

## HISTORICAL SNAPSHOT — SUPERSEDED EXECUTION STATE

- Authorization: `AUTH-BATCH-001`, CEP-002 only, development/non-production build.
- Repository baseline: `main` at `967861037bba4a8e376f3ba0adf46763662eae9c` (the handoff's design baseline is `d75a9334d8e27683159c5f756725c0540651ec43`).
- Worktree: clean before this controlled documentation closeout.
- Prerequisite CEPs/external dependencies: none in the canonical prompt.
- Entry authorization: supplied by `AUTH-BATCH-001`; `GATE-01` remains an exit gate and is not claimed passed.

## Repository grounding before product mutation

- The actual landing route is `financials:dashboard`; `LOGIN_REDIRECT_URL`, organization selection, and the shell brand link target it.
- `templates/base.html` already supplies an authenticated RTL shell with a header, sidebar, mobile navigation, organization context, and profile/settings controls. `templates/components/navigation_links.html` uses existing business-permission visibility checks.
- `templates/financials/dashboard.html` is an existing financial compatibility landing with project, contract, estimate, payment, and financial aggregate displays. Its data comes from `apps/financials/services.py::get_organization_dashboard`, which aggregates tenant-scoped domain records.
- Existing focused tests cover the financial dashboard's active-organization requirement, rendering, and tenant-scoped aggregates in `apps/financials/tests.py`; authentication redirect tests depend on the current target in `apps/accounts/tests.py`.
- Migration impact: none for the inspected implementation.

## Actual Execution Touch Set

| Surface | Disposition |
| --- | --- |
| `templates/base.html`; `templates/components/navigation_links.html` | Inspected only; existing shared-shell implementation. |
| `templates/financials/dashboard.html`; `apps/financials/views.py`; `apps/financials/services.py`; `apps/financials/urls.py`; `config/settings/base.py` | Inspected only; existing financial compatibility landing and redirect contract. |
| Application code, templates, services, URLs, permissions, migrations | No product mutation: blocked before implementation. |
| CEP-002 artefacts and `ROADMAP.md` | Controlled documentation of grounding and blocker only. |

## Finding

### CEP-002-FINDING-001 / BLOCKER-PD — RESOLVED

At execution grounding, the approved canonical outcome required role-aware Home to replace the legacy financial compatibility landing, while prohibiting invented KPI or universal-management-dashboard behavior. The repository contained that landing, but the governing Home decision was not available in the checkout. The original `BLOCKER-REPOSITORY` label and its implied treatment of `PD-016` as a Home specification were incorrect: the reconstructed latest frozen decision register identifies `PD-016` as **Logical Role vs Person Separation**. Home decision ownership was the gap.

Changing the existing financial landing or redirect target without that missing authoritative design would either invent the role-aware Home or silently retain the expressly superseded compatibility landing. Both are outside CEP-002 authority. Per the blocker rule, no product code was changed.

## Governance resolution

The Human/Product Owner approved the Home semantics on 2026-10-14. [PD-032](docs/architecture/BONIRA_PD_032_CANONICAL_HOME.md) records the canonical route, permitted composition, states, authority/data sources and legacy financial dashboard disposition. The separate command `APPROVE PRODUCT DECISION FREEZE — PD-032 ADDENDUM` froze only this decision under [a successor freeze record](docs/architecture/BONIRA_PD_032_FREEZE_RECORD.md). `BLOCKER-PD` is **RESOLVED**; no other scoped Product Decision/specification blocker was identified. Historical source-package reference regeneration remains a documentation follow-up governed by PD-032's correction layer, not an open Product Decision. CEP-002 implementation has not resumed. `PD-016` remains role/person policy only.

## Governance evidence after the execution stop

- The reconstructed latest Product Decision freeze package ends at `PD-031`; its v1.0 freeze requires an explicit Product Owner freeze command for a new governing decision. The next ID is `PD-032` (EV-005).
- The reconstructed latest UI/IMB/CEP sources identify `WS-01`, `UIA-001/012/013/021`, `IMB-0003` and CEP-002 with ambiguous `PD-016` Home attribution. PD-032 supplies a narrow correction layer; original sealed package files and hashes are unchanged (EV-006).
- The Human/Product Owner message approving `CEP-002_HOME_GOVERNANCE_RESOLUTION.md` is provenance for the **approved** semantics, not a Product Decision freeze or product implementation (EV-007).
- The later explicit Product Owner freeze command and addendum freeze record establish `PD-032 = FROZEN` without changing the original v1.0 freeze (EV-008). The original register archive and frozen PD-032 document hashes are checked separately (EV-009).
