# CEP-041 Execution Manifest

## Grounding and actual execution touch set â€” before product mutation

Baseline: clean `main`, HEAD/local `origin/main`/remote `refs/heads/main` all
`f7e89e43726b1494baf40017e6b1276657e224cf`. Registry repository metadata still
names `21476e7`; the intervening direct commit contains only CEP-049 and its
closeout. Its integration is reconciled from Git evidence, without claiming a
merge. Standing non-production authority and this session's bounded add/commit/
push authority apply. No branch/worktree or production action is authorized.

Canonical prompt SHA-256:
`9c568ab27c05fd92da56c3c899ab629c62ac90d058e183da25daec48f4e9f27a`, verified
against the local manifest. CEP-006 is COMPLETE; its final validation disposition
and native immutable comparison evidence exist. EXT-0012/GATE-03 govern tolerance
activation only. IMB-0045 recovered read-only from the approved consolidated master
backlog explicitly permits this hook with auto-acceptance disabled when policy is
absent. No approved source-family reconciliation tolerance was recovered. Existing
AP invoice-match tolerances have a different grain and are not aggregate
reconciliation policy. No rate, threshold, policy schema or authority is inferred.

Frontier recomputation reads every current canonical prompt's direct prerequisites,
entry gate and external phase, rather than trusting the three-item handoff. The
older Registry NOT_ELIGIBLE records explicitly say NOT_YET_EVALUATED. Additional
normal-build/GATE-02 candidates are CEP-036/041/053/055/056. Packages requiring
prior-wave/schema/authority/verification proof remain entry-unverified. CEP-028
remains PARTIAL/BLOCKER-DATA. CEP-041 is selected for its narrow existing service
seam; CEP-052 needs a persisted package/import engine and CEP-022/ESS/indexation
have wider lifecycle/UI/schema surfaces. No dependency graph is changed.

Actual intended product touch set: `apps/reporting/reconciliation.py` (explicit
tolerance-resolution hook, retained policy absence/version, exception/audit
evidence); `apps/reporting/test_cep041.py` (domain and persisted service/history
tests); `apps/reporting/test_p10_s07_s13.py` (replace the unsafe arbitrary-tolerance
expectation with the canonical fail-closed expectation). No models, migrations,
source records, settings, permissions, routes, templates or UI changes.

Governance touch set: this manifest, CEP-041 acceptance/evidence CSVs, change CSV,
completion report, a frontier evidence JSON, and root Registry. Baseline focused
PostgreSQL reconciliation regression: 25/25 PASS (`manage.py test
apps.reporting.test_p10_s07_s13 --keepdb --noinput`). Required validation: focused
unit/model/service/reconciliation history, affected existing regression, Ruff,
Django check, schema drift and diff whitespace. Runtime performance/concurrency
and browser/accessibility remain UTV; no activation or production claim.

## Validation closeout

7 new tests and 25 inherited affected regression cases PASS on PostgreSQL (32 total).
Ruff check/format, Django check, migration drift and diff whitespace PASS. Exact
catalogue comparison remains zero-only. Source/native policy absence is explicit,
with immutable tie-out version/hash, audit and exception evidence. No active
source-family tolerance or migration was introduced. See the Completion Report.
