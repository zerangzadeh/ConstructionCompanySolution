# Related Documents — Phase 3

**Current status.** Chrome detail layout checks passed for all eight surfaces at
1440, 1024 and 390 px after the anchor correction. Two Phase 3 presentation
defects were corrected. Live interaction verification is partial because Chrome
repeatedly detached or timed out. Phase 3 Product Owner visual acceptance is pending.

The Phase 3 request confirms Product Owner visual acceptance of Phases 1/2.
Their accepted implementation is preserved. Their dated validation reports were
not rewritten, and this report does not grant Phase 3 Human visual acceptance.

## Final UX verification follow-up — 2026-11-04

Chrome was initially disabled in Work settings. It became available after the
user asked to continue. Verification used actual Chrome against an isolated
loopback preview seeded with synthetic records in a clone of the retained test
database. The CSS and form-label changes apply to the Phase 3 evidence experience.

### Reproduced defects and corrections

| Defect observed in Chrome | Correction | Retest |
|---|---|---|
| The sticky header covered «شواهد و مستندات» after navigating to the evidence anchor. On Guarantee, the heading began about 39 px from the top at all three widths, beneath the 60/88 px header. | The shared stylesheet gives only `#document-evidence` a responsive scroll margin based on the existing header heights. | Heading visible at all 24 Detail/width combinations. On Guarantee, the heading begins about 91 px on mobile and 119 px at tablet/desktop widths. |
| The Contractual Record picker reported options ready for a reference query but displayed «گزینه‌ای یافت نشد». The server matched the document reference while the picker scored only the label. | Authorized Phase 3 version labels include the business reference when present. UUID- and SHA-256-shaped references are omitted from labels. | At 390 px, `UX-PINNED` displayed v1 and v2. Enter selected the clean v1 with its title and version visible in the control. |

### Chrome verification matrix

The three width columns cover populated Detail pages. At each width, Chrome
confirmed one evidence navigation link, the visible anchored heading, the shared
document icon, RTL, pinned and current version labels, and zero page-level
horizontal overflow. The synthetic records displayed no raw UUID or hash in
main content. Form columns report separate live coverage. A limited check does
not close a row's remaining interaction or persona scenarios.

| Surface | 1440 px Detail | 1024 px Detail | 390 px Detail | Observed browser interactions |
|---|---|---|---|---|
| Safety Incident | PASS | PASS | PASS | Mobile anchor click, submitted review and quarantine display, authorized witness view and return. Chrome delivered clean v1 bytes while v2 was quarantined. Draft multiselect rendered at 390 px. |
| Quality Issue | PASS | PASS | PASS | Mobile quarantined witness view and return. Download action absent for that witness. Draft multiselect rendered at 390 px. |
| Material | PASS | PASS | PASS | Mobile authorized witness view and return. Registration form rendered at 390 px with current version choices and stale-version guidance. |
| Field Observation | PASS | PASS | PASS | Mobile authorized witness view and return. Draft clean-version picker rendered at 390 px. |
| Contractual Record | PASS | PASS | PASS | Mobile reference search and keyboard choice of v1 passed. Browser POST returned 400 for a blank-after-trimming label. |
| Contract Guarantee | PASS | PASS | PASS | Finalized witness and governed revision section visible. Create picker rendered at 390 px. |
| Contract Compliance Evidence | PASS | PASS | PASS | Mobile authorized witness view and return. Create picker rendered at 390 px. |
| Retention Release | PASS | PASS | PASS | Finalized witness and governed correction section visible. Create picker rendered at 390 px. |

**Screenshots.** The before/after pairs are in
[Chrome captures](../../output/related-documents-phase3/final-ux-verification/chrome/).
Use the `before-<surface>-<width>.jpg` and `verified-<surface>-<width>.jpg`
pairs. The desktop Guarantee pair shows the heading moving below the header.
The reference-search screenshot records the matching exact versions. Captures
show synthetic records. The paired views are from the same fixture database.

- [Guarantee before, 1440 px](../../output/related-documents-phase3/final-ux-verification/chrome/before-guarantee-1440.jpg)
- [Guarantee after, 1440 px](../../output/related-documents-phase3/final-ux-verification/chrome/verified-guarantee-1440.jpg)
- [Contractual reference picker, 390 px](../../output/related-documents-phase3/final-ux-verification/chrome/verified-reference-search-390.jpg)

### Regression and remaining verification

The selected non-browser run passed **101/101 in 541.147 seconds** before the
fixes and **101/101 in 649.330 seconds** afterward. It covered 14 Phase 1,
21 Phase 2, 21 Phase 3, 18 DMS service and target-scope, 10 Safety/Quality record
review and 17 Product Surface tests. Ruff, Django system checks, whitespace
validation and 12 affected template compilations also passed. The 25 inherited setup errors remain separately documented
baseline debt from the original broad run. Those classes were outside the
selected reruns and are excluded from the passing count.

The preview was derived from the current test schema without applying migrations.
Both preview servers were stopped and the disposable database clone was removed.
The evidence directory
`output/related-documents-phase3/final-ux-verification/` contains Chrome
measurements, screenshots, regression logs and the follow-up diff. Local
`main` started at `06bcee2ffd31302091388b3738eca38f840500a6` with earlier
Phase 3 and unrelated warehouse work already present. The follow-up changes two
presentation files, this report and its evidence. Git integration and production
operations were outside this package.

Chrome intermittently lost control of the preview and timed out during follow-up
interactions. The latest retry reached the synthetic restricted account but timed
out before collecting its Detail state. The full width-by-form and role matrix remains incomplete. Use the
checklist below for remaining live validation and record a separate result for
each scenario. Phase 1/2 acceptance carries forward. **Phase 3 Product Owner
visual acceptance is NOT ISSUED.**

### Manual visual UAT checklist

Use isolated synthetic records at **1440, 1024 and 390 px**. Compare with the
accepted BONIRA section, form and button styles. For each scenario record the
persona, width, result and screenshot. Use N/A where a lifecycle action does not
exist.

- [ ] Open the contextual navigation. Verify the evidence heading clears the
  sticky header, the document icon and Vazirmatn are consistent, and long text,
  dropdown menus and action buttons stay inside the page at 100% zoom.
- [ ] Open the exact witness and return to the owning section. Download clean
  pinned v1 with v2 present. Check a user with view but no download authority,
  and verify expired, archived, sealed, quarantined and cross-tenant behavior.
- [ ] Check empty and restricted views. Confirm no hidden title, count, ID or file
  metadata. Inspect form labels, messages and visible options for raw UUIDs,
  hashes, model names and permission codes.
- [ ] Tab through each applicable picker. Search by title, number and business
  reference. Use arrows, Enter and Escape. Verify chosen version, error
  presentation, cancellation, safe return and finalized-state restrictions.

| Surface | Remaining journey to complete across the three widths |
|---|---|
| Safety Incident | Draft multi-select and submit, then verify the resulting review revision and immutable submitted evidence. |
| Quality Issue | Draft multi-select, validation, cancel and review submission with the same evidence boundaries. |
| Material | Verify current-version-only submission and stale-selection rejection while keeping existing historical pins visible. |
| Field Observation | Attach a clean exact version as a permitted draft actor and verify replay and submitted-state restrictions. |
| Contractual Record | Verify the rendered Persian validation and cancel path, then register a labelled draft witness. Check non-document lineage separately. |
| Contract Guarantee | Test authorized create/revision pickers and return. Confirm original finalized witness stays pinned. |
| Contract Compliance Evidence | Test create/revision pickers, validation and return with the permitted commercial role. |
| Retention Release | Test create/correction pickers, authorized clearance links, validation and return. Confirm original release history stays pinned. |

## Domain verification and implementation matrix

Relationships and lifecycle were inspected in current models, services and actual
Detail templates before editing each domain. The source graph supplied orientation;
current implementation, rather than the older graph, supplied authority.

| Domain / Detail | Actual persisted witness | Display and navigation | Selection / registration implemented | Authority retained |
|---|---|---|---|---|
| Safety Incident | `review_revisions → revision.evidence → document_version` | Section after incident facts, before operational actions; each row identifies its review revision/state | Searchable exact-version multiselect in draft record-review submission | `submit_safety_record`; record-submit permission, existing same-project/site validation; immutable revision evidence. No generic incident DocumentLink |
| Quality Issue | `review_revisions → revision.evidence → document_version` | Section after quality facts, before operational actions; review revision/state preserved | Searchable exact-version multiselect in draft record-review submission | `submit_quality_record`; record-submit permission, existing same-project/site validation; immutable revision evidence. No hidden Compliance target |
| Material | `document_links → MaterialDocumentLink.document_version` | Below existing material form; contextual evidence navigation | Register the explicitly selected **current** version through existing DMS association; stale selections rejected | Existing `add_document_link`, DMS view/upload, Materials view and `material_documents.link`; existing exact historical pins remain unchanged |
| Field Observation | `evidence_links → FieldObservationEvidenceLink.document_version`, with stored hash | Replaces UUID/hash-only DMS evidence list in the existing supporting-record area | Searchable exact clean-version selection while draft/capture-authorized | `attach_field_evidence`; existing draft, capture, scope, clean processing and operation-key rules |
| Contractual Record | `evidence_links → ContractualRecordEvidence.document_version` | Upgrades existing evidence area; retains separate lineage/non-document references | Label plus searchable exact-version selection on draft only | `add_contractual_evidence`; prepare authority, source validation and append-only evidence. No generic Contract/Project association |
| Contract Guarantee | `evidence_document_version` | Section near commercial evidence/effective dates; replaces UUID witness field | Existing create/revise form now uses authorized searchable version choices | Existing guarantee create/revision/approval services and finalized history |
| Contract Compliance Evidence | `document_version` | Same commercial section and version-aware row | Existing create/revise form now uses authorized searchable version choices | Existing commercial compliance services; distinct from the MVP-hidden Compliance app |
| Retention Release | `evidence_document_version`; separate governed clearance FK | Displays release witness; authorized business labels/links replace clearance and lineage UUIDs | Existing create/correction form now uses authorized searchable version choices | Existing release/correction/clearance services, calculations, approval and financial boundaries |

All eight Detail variants have one contextual «شواهد و مستندات» navigation entry
and one compact evidence section when its source/DMS read boundary allows it.
Rows use the existing document icon, ERP surfaces/buttons and Persian RTL styles.
They show authorized title, document number, Persian type, exact «نسخه شاهد»,
owner/review status and processing availability. «نسخه جاری سند» appears separately
when different. The row markup uses wrapping utilities; actual fit inside narrow
supporting-record columns remains visually unverified.

Evidence view is a read-only, source-bound DMS projection using the same pinned
row and canonical delivery service. Its return link resolves to the owning record's
`#document-evidence` section. The route verifies that the exact version is actually
persisted for that source; a merely accessible unrelated version cannot be viewed
through a forged source context. It contains no generic mutation controls.

Empty and restricted evidence share a neutral visible-empty state. Hidden witnesses
produce no title, number, ID, file metadata, row or count. No total evidence count
is rendered. Authorized quarantined witnesses show their state and have no download
action. Archived, expired, sealed or otherwise denied documents contribute no row.

## Selection, permissions and security

- Existing `SearchChoiceSelect`, its existing Tom Select assets, shared form/error
  components and canonical DMS selectors are reused. No library, model, migration,
  permission definition, relationship type or parallel DMS was introduced.
- Picker labels contain document title/number/type and the exact version, including
  availability. The selected label remains visible in the control before submission.
  Search uses titles/numbers/references and normalized Persian/Arabic digits.
  Remote pagination exposes pages of 20 authorized versions without hidden totals.
- Canonical DMS list results are only candidates. Detail-equivalent all-linked-context
  authorization runs before exposing labels. Expiry, archive, sealed evidence,
  tenant/scope isolation and typed/legacy parity remain enforced. Download authority
  is checked separately through `get_document_version_for_download`; no storage URL
  or bypass delivery path is returned.
- Domain registration permissions remain distinct from DMS upload permission.
  Safety/Quality review submission, contractual preparation and observation capture
  use their existing source-owned authority. Material association additionally
  requires the existing DMS upload and material-link permissions. No role implies
  another permission and no document view permission implies download.
- Registration targets come from an allowlisted, tenant/permission-scoped source
  resolver. A signed one-hour form intent binds actor, organization, kind and source.
  CSRF remains required. Unsafe return URLs and forged context are rejected; safe
  return URLs are generated from source routes. Errors retain the source/cancel link,
  and authorized selections survive ordinary validation rerenders.
- Source and DMS eligibility are rechecked inside the registration transaction,
  followed by the authoritative source service. Material registration locks the
  Document before checking that the selected version is still current; concurrent
  version advancement is rejected rather than silently pinning the newer version.
- Safety/Quality evidence remains revision-owned. Submitting evidence changes record
  review status through its existing submission command, without approving the
  review or changing the separate operational incident/issue status. Finalized or
  submitted records receive no generic evidence mutation action.
- Observation and commercial selection retain their existing clean-version
  requirement. Safety/Quality, contractual and Material services can register an
  otherwise authorized quarantined witness under their existing rules; this does
  not make its bytes deliverable. No new clean-processing requirement or clearance
  ACL was invented. Confidentiality classification and existing specialized privacy
  rules remain unchanged.
- Business-context fields never create additional Project/Contract links. Witness
  registration reuses the canonical Document and DocumentVersion identity/history.
  No new upload, unlink, reassignment, deletion or binary deduplication is added.
- Commercial revision forms previously had organization-only version choices.
  They now receive the actual actor/source and use canonical authorized choices;
  missing actor context fails closed. Clearance record labels/choices and visible
  lineage links use their existing commercial read authority. The version selector
  does not expose UUID/model-name option labels.

## Necessary compatibility correction

The observation retry test exposed an existing `AttributeError` in
`attach_field_evidence`: its replay check read `existing.observation_id`, but the
typed model field is `field_observation_id`. The single attribute reference was
corrected. An identical operation-key replay now returns the existing link;
different payloads retain the existing rejection. Hashing, permissions, lifecycle,
schema and immutable evidence behavior were not changed. The original bytes and
one-line diff are retained in the evidence baseline.

## Changed files and reuse

| Files | Change |
|---|---|
| `apps/documents/evidence.py` | Bounded source resolvers, authorized pinned rows, domain-specific picker eligibility |
| `apps/documents/evidence_forms.py` | Shared exact-version widget configuration and context-bound registration form |
| `apps/documents/evidence_registration.py` | Typed transactional orchestration around existing source services |
| `apps/documents/evidence_views.py`, `apps/documents/urls.py` | Scoped evidence view, choices and registration routes |
| `apps/documents/templatetags/document_evidence.py` | Shared presentation tags and commercial management visibility |
| `templates/components/{document_evidence,evidence_nav,pinned_evidence_row}.html` | Specialized shared section/navigation and pinned row |
| `apps/documents/templates/documents/{evidence_detail,evidence_register}.html` | Read-only witness view and existing-version registration form |
| `templates/{safety,quality}/detail.html` | Review-evidence placement/navigation |
| `apps/materials/templates/materials/material_form.html` | Material evidence placement/navigation |
| `apps/daily_reports/templates/daily_reports/field_observation_detail.html` | Evidence picker entry, pinned labels, Persian transition labels; removes hash-only business display |
| `apps/contracts/templates/contracts/contractual_record_detail.html` | Document-backed evidence section alongside retained lineage/non-document references |
| `apps/billing/forms.py`, `apps/billing/views.py` | Actor/source-aware commercial version choices and existing form callers |
| `apps/billing/templates/billing/{commercial_form,commercial_record_detail}.html` | Widget assets, pinned witness section and business-friendly authorized references |
| `apps/daily_reports/field_services.py` | Single replay field-name correction described above |
| `apps/documents/test_evidence_integration.py` | 21 focused tests with eight-domain and three-commercial-type subtests |
| `docs/validation/related-documents-phase3.md` | This report |

Existing Phase 1/2 projection, association/forms/views, shared related-document
templates/CSS/JavaScript and five business Detail templates were not changed.
Their routes remain intact. Canonical DMS services, models, link registry, storage,
review services, commercial calculations and approval workflows were not changed.

## Original implementation verification results

Final broad run: **126 attempted, 101 PASS, 25 ERROR**, 415.183 seconds.
This is **not a full regression PASS**.

| Coverage | Result |
|---|---|
| New Phase 3 integration/security tests | **21/21 PASS** |
| Phase 2 contextual-association regressions | **21/21 PASS** |
| Phase 1 related-document regressions | **14/14 PASS** |
| Existing DMS services / target-scope regressions | **18/18 PASS** |
| Existing Safety / Quality record-review regressions | **10/10 PASS** |
| Existing Product Surface policy/HTTP regressions | **17/17 PASS** |
| Existing Field Operations regression class | **6 setup errors — BASELINE TEST DEBT** |
| Existing Contractual Record regression class | **11 setup errors — BASELINE TEST DEBT** |
| Existing Commercial Control regression class | **8 setup errors — BASELINE TEST DEBT** |

All 25 errors occur in unchanged fixture `setUp` at `create_project`, before reaching
changed code or test bodies. Those fixtures create legacy memberships without the
current effective role/scope grants. The fixture modules, Project service and
authorization/model files were verified unchanged from HEAD. Attribution and every
affected test identity are recorded in `baseline-test-debt.json`. These tests were
not modified, bypassed or counted as PASS. Their domain bodies remain unverified
by those legacy classes; new isolated, explicitly granted fixtures exercise the
Phase 3 operations and real commercial create/revision requests instead.

Focused coverage includes review-owned registration, draft/finalized denials,
idempotent observation replay, exact v1 evidence after quarantined v2, authorized
v1 byte delivery, Material version drift before/after form validation, commercial
create/revision identity preservation, immutable history, cross-tenant/project/site
and all-context denials, view/download separation, CSRF, signed-context forgery,
safe cancellation/return, validation, audit rollback, quarantine, archive, expiry,
sealed exclusion and absence of technical witness labels.

Tests use the retained isolated PostgreSQL database
`test_bonira_related_documents_phase1_20261104`; schema setup reported **no migrations
to apply**. No application-database migration was executed. New Phase 3 fixtures
use temporary protected-file storage. Django checks, affected template compilation,
Ruff and whitespace validation are recorded in `checks.txt`.

Evidence directory: `output/related-documents-phase3/`:

- `regression-tests.txt`: complete final broad result, including the setup errors.
- `baseline-test-debt.json`: attribution, unchanged-file checks and counts.
- `checks.txt`: final static/system/template checks.
- `baseline.json`, `baseline/`, `implementation.diff`, `touch-set.json`: starting
  repository state, exact source snapshots, scoped changes and final hashes.
- `browser-verification.json`: browser blocker and viewport matrix.
- `focused-tests*.txt`: development runs, including corrected new-fixture/streaming
  harness errors and the observed retry defect; these do not replace the final run.

## Original implementation browser result

At implementation time Chrome was disabled in Work settings. The follow-up
above supersedes this historical browser status for the checks it completed.

| Detail page and applicable selection/revision forms | 1440 px | 1024 px | 390 px |
|---|---|---|---|
| Safety Incident | BLOCKED | BLOCKED | BLOCKED |
| Quality Issue | BLOCKED | BLOCKED | BLOCKED |
| Material | BLOCKED | BLOCKED | BLOCKED |
| Field Observation | BLOCKED | BLOCKED | BLOCKED |
| Contractual Record | BLOCKED | BLOCKED | BLOCKED |
| Contract Guarantee | BLOCKED | BLOCKED | BLOCKED |
| Contract Compliance Evidence | BLOCKED | BLOCKED | BLOCKED |
| Retention Release | BLOCKED | BLOCKED | BLOCKED |

**Screenshots:** none captured. Source snapshots are not screenshots. Actual layout,
focus/keyboard behavior, selector search/scroll/multiselect, status presentation,
navigation and browser registration/download usability are not visually verified.

After enabling Chrome, use isolated records to capture all eight Detail variants
and their applicable forms at all three widths. Check long labels, empty/restricted
states, clean/quarantined old/current versions, selected-version confirmation,
validation/cancel/return, read-only personas and finalized records. Product Owner
must review the new UI; automated tests do not grant visual acceptance.

## Remaining findings and bounded deferrals

1. **Arbitrary historical Material registration:** the existing application service
   pins the current version. Phase 3 safely exposes that operation only. Selecting
   an arbitrary older version for a new Material association needs a separately
   reviewed domain-service contract. Existing older witnesses remain readable.
2. **Review decisions/corrections:** Safety/Quality submission uses existing record
   review authority. No new review-approval/correction UI or mapping to operational
   review/closure was introduced. Legacy-unassessed/returned states are not coerced
   into draft. Further workflow UX needs separate bounded scope.
3. **Project/Contract matching policy:** Safety/Quality retain their explicit
   project/site evidence rules. Material is an organization master. Other owners
   retain their existing evidence rules and may accept a document from another
   context when every context is authorized. No blanket same-contract/project
   policy or inferred association was invented. A stricter policy requires a
   Product Owner/domain decision.
4. **Performance:** exact DMS authorization is retained per candidate. Large
   document/history sets can require many queries before constructing authorized
   picker pages. No persistent permission cache or weakened authorization shortcut
   was added. Remote search/pagination uses the existing JavaScript enhancement;
   the native fallback contains its initial authorized options and retained choices.
5. **Verification debt:** repair the 25 legacy fixtures separately, complete actual
   Chrome verification, and obtain Phase 3 Product Owner visual review. These
   limitations are not accepted residual risk or production authorization.

Starting branch `main`, HEAD/upstream
`06bcee2ffd31302091388b3738eca38f840500a6`; working tree was clean. Work remains
uncommitted. No commit, push, dependency installation, new migration, production
operation, unsupported relation or hidden HR/financial/RFQ workflow activation.

**Stopped for Product Owner review. Phase 3 visual acceptance is pending.**
