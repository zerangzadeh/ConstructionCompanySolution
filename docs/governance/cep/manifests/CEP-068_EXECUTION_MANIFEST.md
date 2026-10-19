# CEP-068 execution manifest — 2026-10-19

IMB-0091; baseline existing main/origin/remote
`b412b09cc9f42c73f67007d13de9305353a8fae3`, clean before entry metadata.
Canonical prompt/SHA/package/source/dependency verification is recorded in
`../evidence/CEP-068_ENTRY.json`. Standing non-production authority applies to
the independent overtime sub-flow: CEP-026 COMPLETE and GATE-02 PASS. The
canonical CEP-062 edge applies only to Mission; it remains unsatisfied. EXT-0016
monetary activation remains unavailable. No conditional edge is removed.

Scope: add own overtime create/list/detail/submit to existing ESS Timekeeping
routes, forms and templates; delegate every state mutation to existing
Timekeeping services and reuse existing overtime permissions. Resolve explicit
User→Person→current WorkRelationship→Employee; restrict periods to that episode,
recheck source object scope, retain episode audit evidence, and reject forged
identity/policy/financial inputs. No new reviewer route, rate/cap/multiplier,
policy approval, Mission request or financial effect. Attachments remain absent
without an approved source attachment policy. No new workflow mechanism.

Exact intended touch set before implementation:

- `apps/workforce/ess_timekeeping.py`
- `apps/workforce/ess_timekeeping_forms.py`
- `apps/workforce/ess_timekeeping_views.py`
- `apps/workforce/templates/workforce/ess_timekeeping.html`
- `apps/workforce/templates/workforce/ess_timekeeping_detail.html`
- `apps/workforce/test_cep068.py` (new security/source workflow/UI tests)
- `docs/governance/cep/manifests/CEP-068_EXECUTION_MANIFEST.md`
- `docs/governance/cep/reports/CEP-068_COMPLETION_REPORT.md`
- `docs/governance/cep/evidence/CEP-068_*` (entry, AC/evidence/change manifests,
  actual test/check output, screenshots/browser observations, findings,
  provenance and document checks)
- `CEP_EXECUTION_REGISTRY.yaml` (058 Git reconciliation,068 lifecycle/frontier).
- `docs/governance/cep/reports/CEP-058_COMPLETION_REPORT.md` (checkpoint addendum).

Migration NONE: no model, schema, permission/grant, data migration or configured
business data changes. Existing source service/model code is read-only.
Tests must cover direct URLs, identity/tenant/object permission, CSRF, invalid
intervals, repeated submit, source-owned state/audit, empty/error/denied states,
Persian/RTL/Jalali, and affected ESS regression. Capture synthetic rendered
screenshots; do not promote them to full browser/accessibility/runtime UAT PASS.
If Mission linkage remains unavailable, report EXECUTION PARTIAL; no full
package completion or GATE-07 PASS.057/058/065/077 and GATE05/06/08 preserved.

Actual closeout: EXECUTION PARTIAL, full-package AC0/6, DoD not met.11 new
overtime tests plus21 affected ESS/identity tests PASS. Required screenshots and
representative browser review are blocked: browser tool reports local browser
use disabled in Work settings. No setting change or bypass; synthetic captured
HTML is not promoted to screenshot proof. Mission still unavailable pending062.
Ruff/format, Django checks and migration drift PASS. Original test import/fixture
failures retained; no unresolved test failure. No migration or configured data
mutation. See Completion Report for exact limitations and Git checkpoint facts.


## 2026-10-20 bounded overtime evidence follow-up

Baseline main96e3566 verified on origin/remote. Current Human V1 closure instruction;026 COMPLETE and GATE02 PASS. Canonical prompt hash reverified.062 conditional edge still blocks Mission because current NONE-migration contract lacks durable effect/target linkage. Actual touch set: existing overtime test execution/capture only, sanitized fixture HTML/screenshots/browser evidence, this manifest, completion report/evidence manifests and Registry. No product/model/service/permission/schema changes. Isolated headless fixture rendering supplies bounded screenshot/responsive evidence without changing Work/browser settings, controlling a signed-in browser, certifying authenticated runtime or inventing Mission/rate/policy. Full package remains PARTIAL until062 and Mission outcomes are proved.
