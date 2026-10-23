# F-111 BATCH-01 runtime closure attempt — UIUX-F-121 only

Date: 2026-10-22, Asia/Tehran. Result:
**BATCH_01_RUNTIME_CLOSURE_BLOCKED_ENVIRONMENT**.

## Authority and grounding

The Human authorized only the remaining mixed-link DMS and representative browser
checks, including one minimum Development-only fixture if no qualifying Document
existed. The [BATCH-01 contract](UIUX_F111_PATTERN_REMEDIATION_PLAN.md) and
[accepted implementation report](UIUX_F111_BATCH_01_REMEDIATION_REPORT.md) remain
unchanged. No implementation or accepted test scenario was repeated.

Branch `main`; HEAD and local `origin/main` remain
`43ac319c6e73e48ca9626461b73987922c498ec3`. Billing forms SHA-256:
`7ac807b38539bdc7a3d40768a1af3cbab4d57b7a1d68948654b6308a474b4a94`;
Billing views SHA-256:
`e17cfa099bc42797433b3a06672b3c01dfce5437e8eca749404e6786eb2e8c10`.
Both match accepted BATCH-01 evidence. Existing dirty product files and all old
evidence were captured before fixture creation; see
[entry capture](f111_batch_01_runtime_closure_evidence/ENTRY.json).

The existing nonstaff, nonsuperuser P17 Project Manager has the same active
membership, explicit A/B Project grants, roles and four required commercial/DMS
capabilities as the accepted retest. No authorization record changed.
The existing ordinary tenant owner qualified to create/link the fixture using
the canonical services. Settings are `config.settings.development`, PostgreSQL
database `construction_erp`, local host, zero pending migrations.

Actual touch set: this new report; new
`f111_batch_01_runtime_closure_evidence/`; the F-121 register entry only; and the
explicitly authorized synthetic Development Document/file and canonical link,
numbering and audit records. No product or test source changed.

## Minimum Development fixture

Preflight found no existing qualifying mixed-context Document. Exactly one
Document and one immutable 624-byte synthetic PDF version were created, labelled
**BATCH_01_RUNTIME_CLOSURE_FIXTURE**, through `create_document` and
`add_document_link`. Both calls used the existing tenant owner, inside one outer
transaction, with ordinary canonical authorization and auditing.

- Document: `16f0f334-780d-4790-99b9-25ed3aee785c`.
- Version: `9382e409-ef26-43c0-9d54-8c50f2bd4041`.
- Context A: `PRJ-01-01`, authorized for P17.
- Context C: `PRJ-01-03`, unauthorized for P17, in the same tenant.
- File contains only an explicit synthetic marker; no real or sensitive content.

Canonical storage and services created one Document, one version, two legacy
links, two typed Project links, the necessary numbering increment and two audit
events (`document.uploaded`, `document.link_added`). No roles, permissions, grants,
processing assessments or unrelated records were created. The labelled fixture
is retained in Development for reproducible retesting; no deletion occurred.

Before adding C, the same version appeared in all three limited-actor form
querysets and the canonical detail reader allowed it. After adding C, the
canonical list excluded it, the detail reader denied it, and all three limited
create forms excluded it. The existing organization-authorized writer could still
select it in all three forms. Thus the negative isolates linked-context authority,
rather than an unrelated lifecycle or processing filter. See
[fixture proof and exact model deltas](f111_batch_01_runtime_closure_evidence/FIXTURE.json).

## Missing mixed-link runtime evidence — PASS

A fresh process from this checkout served only Development on `127.0.0.1:8003`
with `--noreload`. Actual authentication and CSRF middleware were used. Credentials,
cookies, session material and CSRF tokens remained transient; no raw HTML was saved.

Six new live observations cover one GET and one otherwise-valid mixed-version
POST with an authorized Contract on each of Guarantee, Compliance Evidence and
Retention Release. All GET and invalid-POST responses exclude the mixed fixture's
Document/version IDs and unique title. The manipulated version is rejected with
field errors; each response is HTTP 200 with scoped redisplay.

Contract/version HTML option sets remain identical to the accepted GET evidence:
Guarantee 6/4; Compliance Evidence 6/4 (its distinct `document_version` field);
Retention Release 2/4, retaining payable-subcontract filtering. Same-tenant C/D
and cross-tenant X Contract numbers/UUIDs and protected version UUIDs are absent
from the complete new responses. Generic recurring demo document titles are not
treated as distinctive leak indicators. Prior accepted cross-tenant POST evidence
is preserved rather than rerun. See
[live observations](f111_batch_01_runtime_closure_evidence/HTTP_MIXED_LINK.json).

Snapshots compare all 519 model tables. After the authorized fixture creation,
the runtime login changes only the session table (user `last_login` is excluded
from the User digest). During the six observations all model digests, including
commercial business and audit records, remain identical. No unauthorized business
mutation or success audit occurs. See
[integrity proof](f111_batch_01_runtime_closure_evidence/RUNTIME_INTEGRITY.json).
The newly launched server was stopped after the checks; existing processes were
not stopped. Source/evidence preservation, the new script's Ruff/format checks,
report links and whitespace checks pass; see
[verification](f111_batch_01_runtime_closure_evidence/VERIFICATION.json).

## Representative browser evidence — blocked

The browser control tool returned **“Local browser use is disabled in Work
settings”** when listing the in-app browser tabs. Recorded status:
**BROWSER_RUNTIME_BLOCKED_ENVIRONMENT**. No setting was changed or bypassed.

Guarantee and Retention representative browser interactions and DOM option
observations remain incomplete. The new parsed HTTP option evidence is supplemental;
it does not replace browser observations. No screenshot or browser PASS is claimed.
Compliance's accepted live-route evidence is preserved and supplemented by its
mixed-link live GET/POST. See
[browser blocker](f111_batch_01_runtime_closure_evidence/BROWSER.json).

## Disposition and safety boundary

UIUX-F-121 remains **OPEN**, with
`REMEDIATION_IMPLEMENTED_PENDING_RUNTIME_RETEST`. The mixed-link gap is closed;
the representative browser gap remains. No `RUNTIME_VERIFIED_RESOLVED` status is
issued. All original static, implementation, automated and runtime evidence is
preserved, including the accepted 18 tests/67 subtests, 45 regression passes,
13 attributed baseline failures, checks and 24 prior HTTP observations.

No BATCH-02..09, Wave C, broad UI work, Production action, CEP-078/079, Git
add/commit/push, Product Decision, authorization change, Documents authorization
code change, commercial service change, or schema/migration change occurred.
Only the single explicitly authorized Development closure fixture was prepared.
