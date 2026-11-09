# MVP-04B — RFQ comparison and award configuration UX remediation

**2026-11-03 · Bounded non-production UI/workflow remediation.**
**Product Owner visual acceptance: PENDING.**

## Authority and entry

Explicit user request in the pasted attachment: continue uncommitted `main`,
remediate only the RFQ Commercial Scope/comparison-and-award configuration journey,
use the supplied Persian RFQ dashboard as visual direction, preserve domain and
F1–F4 semantics, create no migrations, and stop without commit or push.
The image supplies visual direction; it does not authorize new RFQ fields or
business behavior.

Entry branch `main`; HEAD and `origin/main` both
`b97fcc45a92737b83e9c3ffb14b589cfdc4250d7`, divergence 0/0. The working tree already
contained PR detail, Contract/Billing and Module Selector work. These changes
were preserved. [Entry status](../../../output/mvp-04b-ux/entry-status.txt),
[entry diff names](../../../output/mvp-04b-ux/entry-diff-names.txt),
[entry diff stat](../../../output/mvp-04b-ux/entry-diff-stat.txt).

Agents.md, Execution Policy, UI guidelines, canonical color system and the actual
RFQ forms/views/services/models/tests were read progressively. Existing graphify
index was queried and actual source inspected. This is an explicit bounded UI
remediation, not a new CEP execution/lifecycle event. Registry, Roadmap, canonical
prompts, release authority and production state are unchanged.

## Previous problem and resulting journey

Previously, after selecting PR items into an RFQ, the user had to leave the Draft
workspace, name and classify a technical scope, manually re-enter member quantities
and individually choose three flags before returning to issue. The normal one-item
case required the same separate form as a lot. Technical revision/scope language
obscured the actual task of configuring comparison and award.

The workspace now shows the existing RFQ rows directly with PR quantity, RFQ-line
ceiling, editable quantity to source, inherited unit and independent-selection
control. Full quantities are prefilled without trailing decimal zeros. Split and
alternate controls are in native per-row disclosures. One explicit
`تأیید و ذخیره تنظیمات` action prepares all displayed independent-item settings
through the existing domain service. Loading, refreshing and navigating never
persists a definition.

New journey:

`Approved PR → Draft RFQ → select existing PR items → review quantities and
selection settings in the Draft workspace → explicitly confirm/save → submit for
issue → select suppliers → issue`.

RFQ identity, source PR, project, dates, selected items, settings, current state,
issue prerequisites and issued versions remain in the RFQ detail journey. The
existing dedicated URL remains valid for group creation, correction and next-version
preparation. Issued settings remain read-only; addenda use the existing route and
permission. The normal case no longer needs the separate technical form.

## Business terminology

| Presentation | Wording |
| --- | --- |
| Main section | نحوه استعلام و انتخاب تأمین‌کننده |
| Quantity being sourced | مقدار استعلام |
| Original RFQ line limit | سقف قلم در استعلام |
| Independent award | انتخاب مستقل |
| Split award | امکان تقسیم خرید |
| Alternates | پیشنهاد جایگزین مجاز / پذیرش پیشنهاد جایگزین |
| Lot | گروه خرید |
| Group action | ایجاد گروه خرید |
| Current settings | تنظیمات نسخه جاری |
| History | نسخه‌های قبلی تنظیمات استعلام |

Technical model/field names and code values are retained internally. Generated
line identifiers are resolved to material names in current/history presentation.
Revision numbers, hashes and fingerprints are not primary business labels.
Service errors are translated at the RFQ presentation boundary.

## Actual touch set

Product:

- `apps/procurement/scope_presentation.py`: row configuration form, stable mapping
  to existing RFQ/PR identities, versioned settings/history projections.
- `apps/procurement/commercial_scope_forms.py`: business labels, prefilled member
  quantities, explicit member checkboxes, editable existing group settings; legacy
  POST names/contracts retained.
- `apps/procurement/commercial_scope_views.py`: dispatch explicit item confirmation
  through the existing service; retain append/replace behavior and authorize every
  route with the same read/project and change/addendum authority.
- `apps/procurement/rfq_workspace.py`: integrate configuration context, business
  state copy and PR quantity relation loading.
- `apps/procurement/rfq_ui.py`: business wording for existing preparation errors.
- `apps/procurement/templates/procurement/rfq_detail.html`: coherent local journey and integrated
  configuration; issue prerequisites and issued-version framing.
- `apps/procurement/templates/procurement/rfq_configuration.html`: existing-item table, progressive
  advanced options, group entry point, contextual guidance and settings history.
- `apps/procurement/templates/procurement/configuration_entries.html`: shared current/historical
  business projection, including exact saved member quantities and inherited units.
- `apps/procurement/templates/procurement/scope_form.html`: compatible group selection/editing route.
- `apps/accounts/static/css/erp_rfq_configuration.css`: scoped responsive geometry
  using existing canonical color tokens and shared controls.

Verification:

- `tests/test_rfq_configuration_ux.py`, `tests/test_rfq_configuration_browser.py`,
  `scripts/verification/rfq_configuration_browser.mjs`,
  `scripts/verification/rfq_configuration_validate.py` (test-only retained-FK cleanup,
  hard-guarded to the dedicated disposable database).
- Existing scope/preparation tests use the new business labels and explicit member
  selection; connected downstream tests use the embedded row confirmation.
- Legacy scope/preparation browser evidence and connected financial-lineage evidence
  are redirected into this remediation's output tree to preserve historical artifacts.
- This report and `output/mvp-04b-ux/`.

## Preserved authority and intentionally retained constraints

No model, schema, migration, scope producer/issue service, comparison/award service,
quote behavior, authorization implementation, workflow/SoD rule or source-to-pay
calculation is changed. `RFQCommercialScopeDefinition` and all canonical domain
identifiers remain unchanged.

The adapter calls `define_rfq_commercial_scope()` with the existing expected
revision, source fingerprint, version and idempotency key. The service still locks
and re-reads, reauthorizes inside the transaction, validates source membership and
quantities, versions the immutable definition and appends its audit event. Stable
source-row ordering and replay against the original persisted definition prevent
repeated submissions from remapping quantities. Definition pinning/freezing,
version issue, addenda and award calculation remain domain-owned.

- Defaults are editable presentation values; explicit POST confirmation remains
  mandatory where the existing RFQ requires it. Legacy optional-scope RFQs keep
  their existing issue contract.
- Quantity to source must be positive, at most the existing RFQ-line quantity and
  within the existing decimal limits. Partial sourcing does not mutate the RFQ
  line or PR quantity.
- Independent, split and alternate flags remain separate; combined split/alternate
  settings and existing non-independent line settings are retained. A line cannot
  split without independent award, as already required by the domain.
- Groups explicitly select existing members with their prefilled quantities.
  Their own comparison quantity and unit remain required by the current lot
  contract; these are distinct from member identities/units.
- Append preserves other entries; replace corrects the same named entry. Creating
  a group does not silently delete or convert previously saved independent scopes.
  The guidance states this. Configuring a group before ordinary row confirmation
  produces the intentional group only, without inferred independent line scopes.
- Multiple existing scopes for one item, original codes, unedited groups and older
  definitions remain intact. No new deduplication/allocation rule is invented.
- Missing/stale/invalid required configuration still blocks issue atomically;
  the supplier form and unchanged issue service remain authoritative.

## Visual direction and frontend foundation

[Supplied reference](../../../output/mvp-04b-ux/reference.png) guides the blue section
hierarchy, white surfaces, item-centred comparison settings, contextual help and
secondary group action. The accepted BONIRA shell/Module Selector and real RFQ
workflow are retained. Unsupported reference controls such as a different creation
wizard, tender method or invented save/create action are not introduced. The help
rail follows the existing RTL workspace composition beside the configuration;
it stacks below the main content at narrower widths.

Desktop uses a compact semantic table with contained scrolling when necessary.
At 390px, the same rows become labelled item blocks with usable quantities and
full-width award controls; native disclosures expose advanced options. DOM and
reading order remain RTL. Shared form-field error associations and native
keyboard controls are retained.

No new product JavaScript, dependency, remote asset, Select2, jQuery, dialog
framework or navigation authority is added. Tom Select, SweetAlert2, local fonts,
Tailwind and Product Surface-filtered navigation remain the accepted foundation.
The Tailwind rebuild is byte-identical: SHA-256
`1557718110d6b93881f67e22cdd899a14383474c20640c85d79a535df6957470`.

## Validation and browser evidence

Consolidated selection: **43 PASS, 13 FAIL, one additional teardown ERROR;
20 subtests PASS**, across **56 distinct test methods**. This is not a full-suite
PASS. [Run log](../../../output/mvp-04b-ux/final-tests.txt),
[JUnit](../../../output/mvp-04b-ux/final-tests.xml).

Failure attribution and follow-up:

- **Nine BASELINE TEST DEBT cases** in the older P5-S11 comparison fixtures fail
  during `setUp` at protected quote-opening permission enforcement, before any
  changed form/view/presentation path executes. Eight relevant fixture, domain,
  authorization and pytest configuration files are byte-identical to HEAD. The
  existing fail-closed authorization was preserved. These legacy test bodies
  remain unverified; no fixture permission grants or product rules were changed.
- **TEST INFRASTRUCTURE DEBT**: default transactional teardown cannot truncate
  through the retained `payments_payment` FK. This affected two scope/RFQ concurrency
  tests and the already baseline-failing comparison concurrency fixture's teardown.
  A bounded verification wrapper applies the already qualified browser-fixture
  `CASCADE` cleanup policy only to `test_bonira_f2_20261102`, preserving application
  history protections and all production/development data.
- Two old browser tests needed updated assertions/selectors: a hidden technical
  line-scope name was still expected as visible text, and a disclosure selector
  added for the RFQ line picker had also been added to the general PR picker.
  Both test expectations were corrected; persisted-domain assertions remain.

[Failure classification and unchanged-source hashes](../../../output/mvp-04b-ux/regression-attribution.json).
The two connected source-to-pay tests pass, including exact split allocations,
source lineage and unchanged financial-row hashes. Scope/issue service,
HTTP/CSRF/tenant/project/suspension, navigation, Product Surface and Module Selector
presentation checks pass in the consolidated selection.

Final targeted rerun: **6/6 PASS**, including the two scope/RFQ concurrency tests,
the compatible scope/addendum browser journey, both preparation browser tests and
the fresh final-template browser matrix. [Final rerun log](../../../output/mvp-04b-ux/final-browser-concurrency.txt),
[final rerun JUnit](../../../output/mvp-04b-ux/final-browser-concurrency.xml).

Combined coverage: **47 distinct affected tests PASS; nine unchanged legacy
comparison fixture failures remain attributed baseline debt**. Repeated tests are
not counted twice. No full-repository regression PASS is claimed.
[Machine-readable reconciliation](../../../output/mvp-04b-ux/validation-summary.json).

Final installed **Chrome/156.0.8078.48: 17/17 new cases PASS** at 1440, 1024 and
390px. No JavaScript exceptions, console errors, external product requests,
unexpected HTTP/asset failures or horizontal page overflow. Expected validation
responses are retained as evidence. The saved definition and issued-version
assertions pass after the browser exits. [Browser results](../../../output/mvp-04b-ux/browser/results.json),
[browser command result](../../../output/mvp-04b-ux/browser/command.txt).
Legacy [scope/addendum](../../../output/mvp-04b-ux/legacy-scope-browser/)
and [preparation](../../../output/mvp-04b-ux/preparation-browser/) captures are
preserved separately. Their final test methods pass in the targeted rerun.

Ruff lint and formatting, Node syntax, Django system checks and source schema-drift
checks pass. [Ruff](../../../output/mvp-04b-ux/ruff.txt),
[system/build checks](../../../output/mvp-04b-ux/system-checks.txt),
[domain file preservation](../../../output/mvp-04b-ux/domain-preservation.txt),
[Tailwind build](../../../output/mvp-04b-ux/tailwind-build.txt),
[commands](../../../output/mvp-04b-ux/commands.txt).

Real installed Chrome is launched headless against a live Django server using
synthetic records in disposable PostgreSQL `test_bonira_f2_20261102`. Existing
migrations are applied/reused there. Sessions remain in process environment and
are not written into evidence. Cache and service workers are bypassed; external
requests are actively blocked with a negative control. Product pages must load
only local runtime assets, with no unexpected HTTP/asset or JS/console errors.
Expected validation 400s and the pre-existing `/favicon.ico` 404 are classified
separately.

The new browser matrix covers 17 cases: independent multiple lines at all three
widths; purchase groups at all three widths; a single independent line; partial
quantity; split; alternate; invalid quantity/flag combination and correction;
existing saved settings plus previous-version visibility; valid issue; missing
required settings at issue; viewer read-only; wrong-project and cross-tenant denial.
Persisted definitions, flags, exact member quantities, unchanged source quantities,
issued scope pinning and supplier invitations are asserted after browser actions.

Representative screenshots:

- [1440px workspace](../../../output/mvp-04b-ux/browser/normal-1440-before-top.png)
- [1440px configuration](../../../output/mvp-04b-ux/browser/normal-1440-before-configuration.png)
- [1024px configuration](../../../output/mvp-04b-ux/browser/normal-1024-saved-configuration.png)
- [390px item configuration](../../../output/mvp-04b-ux/browser/normal-390-before-configuration.png)
- [390px group form](../../../output/mvp-04b-ux/browser/group-390-group-configuration.png)
- [Saved history](../../../output/mvp-04b-ux/browser/saved-saved-configuration.png)
- [Issued RFQ](../../../output/mvp-04b-ux/browser/issued-top.png)
- [Validation errors](../../../output/mvp-04b-ux/browser/validation-errors-top.png)
- [Blocked issue](../../../output/mvp-04b-ux/browser/missing-blocked-top.png)

During iteration, focused testing found and corrected adapter replay ordering;
Chrome found and corrected narrow 1024px quantity controls. A history assertion
was corrected to accept the application's Latin-digit text rendered with Persian
glyphs. No persisted history quantity was changed by that assertion correction.

## Environment boundary

Django system check passes and `makemigrations --check --dry-run` reports no model
changes. The configured development database's read-only migration check reports
one pre-existing pending migration, `payroll.0010_cep069_reviewed_statutory_context`.
It is outside this RFQ remediation and was not applied. This does not constitute
Payroll activation or production authorization. See
[pending migration evidence](../../../output/mvp-04b-ux/development-pending-migrations.txt).
No configured development/customer data was mutated by verification.

## Closeout

Within this bounded remediation, with the explicitly attributed baseline debt above:

```text
COMMERCIAL SCOPE UX REMEDIATION: PASS
DUPLICATE ENTRY REMOVED: PASS
BUSINESS TERMINOLOGY: PASS
NORMAL RFQ FLOW SIMPLIFIED: PASS
ADVANCED LOT/SPLIT/ALTERNATE SUPPORT PRESERVED: PASS
DOMAIN SEMANTICS PRESERVED: PASS
RFQ ISSUE RULES PRESERVED: PASS
F1-F4 FRONTEND FOUNDATION PRESERVED: PASS
RESPONSIVE RTL: PASS
VISUAL REFERENCE CONFORMANCE: PASS
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
```

`VISUAL UX REMEDIATION: READY_FOR_HUMAN_REVIEW`.
Reference conformance means the adapted configuration hierarchy and visual direction;
it does not assert a pixel-identical replacement of the accepted BONIRA shell.

Product Owner visual acceptance: **PENDING**. Technical/reference conformance is
not Human visual acceptance. No Human Sign-off, Production Certification,
production deployment or migration, commit or push was performed. Stop after this
remediation; no next MVP package is started.
