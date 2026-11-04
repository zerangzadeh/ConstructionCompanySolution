# Related Documents — Phase 2

**Status:** Contextual association implemented; automated validation PASS.
Required actual-Chrome verification and screenshots **BLOCKED** by disabled
local browser access in Work settings. Product Owner review pending. Neither
Phase 1 nor Phase 2 has Human visual acceptance.

## Implemented behavior

The existing shared «اسناد مرتبط» section now has two connected, permission-aware
actions: «بارگذاری سند جدید» and «پیوند سند موجود». Both reuse the existing
document icon, ERP buttons, RTL styles and page-specific Phase 1 placement.
The actions are available for an authorized empty section as well as a populated
one. Existing navigation, authorized counts, document details and protected
exact-version downloads remain in place.

| Source | New upload | Existing document | Success / cancellation destination |
|---|---|---|---|
| Project | PASS, exact Project only | PASS, same Document identity | Project Detail, Related Documents section |
| Contract | PASS, exact Contract only | PASS, same Document identity | Contract Detail, Related Documents section |
| Estimate | PASS, exact Estimate only | PASS, same Document identity | Estimate Detail, Related Documents section; authorized Project URL context retained |
| Expense | PASS, exact Expense only | PASS, same Document identity | Expense Detail, Related Documents section |
| Daily Report | PASS, exact Daily Report only | PASS, same Document identity | Daily Report Detail, Related Documents section |

PASS in this table describes isolated Django request/service tests, **not browser
or visual verification**. Each action has required-field validation, safe cancel
navigation and a successful submission tested for each of the five sources.

The upload path reuses the existing DMS upload template and creation service.
The source is resolved server-side and displayed using its business title/number,
Project name/code and applicable authorized Contract title/number. The source is
a restricted hidden field, never a repeated Project/Contract selector. Context
display does not create parent Project/Contract links. Only the explicitly chosen
source is associated.

The existing-document form reuses the shared searchable selector and its existing
Tom Select assets, with authorized title, document number, Persian type and current
version labels. Search accepts titles, numbers and references, including normalized
Persian/Arabic digits. Results use pages of 20 authorized documents and remote
search/pagination. A selected authorized result beyond the initial page survives
validation errors. No document or binary is copied when adding an association.

Successful submissions and cancellation use a canonical, server-generated source
URL ending in `#related-documents`. Validation errors retain the source, safe
cancel link and entered metadata; browsers require reselecting an upload after
an error. An expired form intent produces a Persian error and a refreshed intent
for retry. Contextual forms return HTTP 400 for invalid submissions and HTTP 403
for denied access; success uses the normal redirect and Persian message flow.

## Authorization, integrity and lifecycle

- Contextual forms, the picker and writes require both existing DMS view and
  upload authority, plus the exact source-domain and Project/Site scope. Download
  remains a separate permission. A view-only persona receives no mutation actions;
  an upload-only persona cannot use these contextual read-and-associate forms.
- Source identities are allowlisted to the five existing relationships and
  reloaded through canonical tenant/scope selectors and DMS target validation.
  Neither a URL nor its hidden field grants access. A signed, one-hour form intent
  binds actor, tenant, source type and source identity; permissions are still
  checked independently and rechecked inside the write transaction.
- Arbitrary return URLs, tenant inputs, additional target associations, mismatched
  hidden sources and forged intent are rejected. Navigation is generated from
  approved source routes. CSRF middleware remains enforced for both POST actions.
- The picker starts from the canonical DMS list selector, then executes canonical
  detail and association authorization before rendering each label. Every linked
  context must be authorized; compatibility-parity failures are excluded. Hidden
  candidates contribute no labels, counts or pagination totals. JSON is private,
  no-store; page offsets apply to authorized results only.
- Both typed and legacy direct links are checked for existing associations.
  Writes serialize on the existing Document row and execute the canonical
  `add_document_link` service atomically. Target scope is re-read under a target
  row lock. A retry cannot add duplicate links or change the current version.
  Database constraints remain authoritative for competing writes.
- Uploads execute canonical `create_document` in an atomic wrapper and retain
  canonical file validation, numbering, audit and typed/legacy creation. On
  rollback, only binary names tracked by that upload are cleaned up. No existing
  file, Document or version history is deduplicated or deleted.
- New versions retain their canonical quarantine/processing state. Success text
  explicitly says file delivery awaits safety evaluation. Phase 1 exposes no
  download action until the existing exact-version secure-download service allows
  it; direct delivery is also denied while quarantined. Adding a link does not
  mark any version clean or add a version.
- Archived, expired and sealed supplier-evidence documents are excluded by the
  existing authorities. Specialized pinned-version/RFQ evidence paths are
  untouched. Confidentiality classification is preserved; as recorded in the
  assessment, it does not introduce a new clearance ACL. No additional clearance
  policy or permissions are claimed by this work.
- Expected validation/database failures receive bounded Persian errors. Ordinary
  form labels and messages contain no UUIDs, model names, permission codes or raw
  database errors. IDs remain transport values in scoped URLs/hidden controls.

## Changed files

| File | Phase 2 change |
|---|---|
| `apps/documents/association.py` | New bounded orchestration around existing source and DMS services; authorized choices and atomic association |
| `apps/documents/contextual_views.py` | Upload, existing-document form and authorized-choice request handlers |
| `apps/documents/forms.py` | Context-bound subclasses of existing forms; signed intent and shared searchable selector |
| `apps/documents/urls.py` | Three contextual routes within the existing Documents namespace |
| `apps/documents/presentation.py` | Permission-aware contextual action URLs on the Phase 1 read projection |
| `templates/components/related_documents.html` | Two actions in the existing section |
| `templates/documents/upload.html` | Reuse upload form with fixed source context and source return |
| `templates/documents/association_context.html` | Shared business-context presentation |
| `templates/documents/contextual_link.html` | Compact existing-document form using shared components |
| `apps/documents/static/documents/related_documents.css` | Section actions and responsive context/form styles using existing ERP tokens |
| `apps/documents/test_contextual_association.py` | 21 focused request/service tests, including five-source subtests |
| `docs/validation/related-documents-phase2.md` | This completion report |

No five-source business view/template edits were needed in Phase 2. Existing
Phase 1 integrations consume the shared component. No models, migrations,
permission definitions, dependencies, relationship registry changes, workflow
changes, unlink/reassignment controls or Product Surface expansion were added.
Canonical DMS services and specialized evidence workflows were not edited.

## Automated verification

Final combined suite: **53/53 PASS in 173.430 seconds**, using a dedicated,
retained PostgreSQL test database, separate from the application's database:

- Phase 2 contextual tests: **21/21 PASS**.
- Phase 1 related-document regressions: **14/14 PASS**.
- Existing DMS service regressions: **12/12 PASS**.
- Existing DMS target-scope regressions: **6/6 PASS**.

Coverage includes all ten contextual success paths, per-source validation/cancel,
exact-one association, duplicate retry, foreign targets/documents, forged context,
unsafe return URLs, view/upload/download separation, project/site restrictions,
transaction-time authority revocation, all-linked-context filtering, legacy/typed
parity, paginated search, selected-value retention, expired intent, real CSRF,
quarantine/secure delivery, unchanged version identity, and atomic database/file
rollback. Phase 1 tests continue to exercise all five Detail responses, navigation,
empty states, source roundtrips, authorized counts and exact clean-version actions.

Django system checks, affected template compilation, Ruff check/format and
whitespace validation: PASS. No new JavaScript was introduced.

The two pre-existing processing tests identified in the Phase 1 report remain
**BASELINE TEST DEBT**, not PASS: their unchanged legacy-role fixture fails at
Project creation before reaching processing assertions. They were not changed
or included in the 53 passing tests. The final run covers quarantine refusal and
authorized clean-version delivery through working fixtures and canonical services.
See Phase 1 `baseline-test-debt.json` for the earlier attribution evidence.

Evidence under `output/related-documents-phase2/`:

- `verification.txt`: final combined run.
- `checks.txt`: final lint, system and template checks.
- `baseline.json`, `baseline/`: exact Phase 1 starting bytes and Git grounding.
- `implementation.diff`, `touch-set.json`: Phase 2-only changes and final hashes.
- `browser-verification.json`: browser blocker and pending viewport matrix.

Earlier `focused-tests*.txt` retain development failures corrected before the
final run: iterator/prefetch use, search matching and test-helper assumptions.
They are not final verification results.

## Browser verification and screenshots

The actual Chrome tool was attempted and rechecked. It reports local browser use
disabled in Work settings. No native/CLI browser bypass, substitute browser
assertions or fabricated screenshots were used.

| Source page and both contextual forms | 1440 px | 1024 px | 390 px |
|---|---|---|---|
| Project | BLOCKED | BLOCKED | BLOCKED |
| Contract | BLOCKED | BLOCKED | BLOCKED |
| Estimate | BLOCKED | BLOCKED | BLOCKED |
| Expense | BLOCKED | BLOCKED | BLOCKED |
| Daily Report | BLOCKED | BLOCKED | BLOCKED |

**Screenshots:** none captured. Before/after source snapshots are available in
the evidence directories; they are not screenshots. Responsive wrapping, actual
selector search/scroll, keyboard/focus behavior, visual placement, messages and
real-browser upload/download/cancellation journeys remain unverified.

When Chrome is enabled, verify each page's two actions at all three widths with
isolated non-production records: populated/empty sections, permission personas,
fixed context, long titles, search and additional pages, validation/retry,
cancellation, success return, duplicate retry and quarantined delivery refusal.
Capture before/after screenshots and confirm Phase 1 navigation remains usable.
Then request Product Owner visual review; no visual acceptance is presumed.

## Preservation and limitations

Starting branch `main`, HEAD/upstream
`560bc3c9f136a3b76c6816dc127a80d74bcb7a1d`. Existing uncommitted work was retained.
No commit, push, new dependency, application-database migration or production
operation was performed. Tests use isolated non-production data.

Canonical per-document authorization is deliberately retained for picker options
and Phase 1 rows. Large candidate sets and later authorized pages can incur
repeated validation/query cost; no persistent permission cache or weakened
authorization shortcut was introduced. Remote picker search/pagination requires
the existing JavaScript enhancement; without it, the native fallback exposes only
the initial authorized page (plus an authorized retained selection on retry).

Implementation stops here for Product Owner review, with the browser gate
explicitly BLOCKED and Human visual acceptance still pending.
