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

## 2026-10-20 authorized Mission continuation — pre-mutation

main/origin/remote @a942a081ba6de0858a0de707a473c2ed29c607b6; product tree clean, own disposable tooling only.026/062 COMPLETE and GATE02 PASS;068 canonical SHA reverified. PD027/029 and SPEC018 package/IMB/dependency/ESS sources recovered only where absent locally, source archive hashes retained in original068_ENTRY and shared verification. PD029: ESS request/read orchestration only; Treasury advance never Employee Loan. User sequence and standing authority apply. EXT0016 monetary activation held; no policy/rate/cap/multiplier/approval depth or attachment policy supplied. Build/verification may proceed.

Actual touch set: existing workforce ess_timekeeping.py/forms.py/views.py and2 existing Timekeeping templates for Mission create/list/detail/submit and minimal own routing status read; new test_cep068_mission.py; retained test_cep068.py only replaces obsolete unconditional Mission-unavailable assertion with explicit revoked source-permission denial. No overtime implementation/assertion weakening, no model/schema/permission grants/source-domain service mutation. Existing Manager review remains native Timekeeping; no ESS review path or financial routing invocation. Optional project/site stay within existing tenant/object scope; Person/current WorkRelationship supplies Employee and episode bounds. Category is explicit existing native request metadata, not monetary classification/approval. Source-linked062 effect references supply own routing status only; protected amounts, reviewer/policy/security and target-domain records remain unavailable through ESS. No approved attachment policy means no upload capability.

Preserve prior overtime screenshots/HTML/browser verification byte-for-byte; hashes recorded before mutation in068_OVERTIME_PRESERVATION.json. Capture Mission synthetic fixtures in a distinct folder, render desktop/mobile with isolated headless QA, inspect screenshots and retain honest runtime limits. Actual conditional source-linkage/transaction/no-financial-write proof and affected ESS/identity regression required. No migration, configured business-data or Production action;057/058/065 blockers and069..079 exclusion preserved.

Current full-package closeout:44 distinct current focused/affected cases PASS;26 subtests;18 Mission responsive screenshots and visual review PASS.27 overtime artifacts byte-identical. Source identity revalidated against the initially qualified relationship at audit; own routing query selects only route/event-kind, no financial-target read. Final UI list status uses native Persian display labels. No schema/migration, actual monetary activation or Production action. Historical partial entries above remain dated history, not current state.
