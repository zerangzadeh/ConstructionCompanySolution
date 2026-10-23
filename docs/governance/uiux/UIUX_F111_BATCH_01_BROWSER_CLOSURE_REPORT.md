# F-111 BATCH-01 browser closure — UIUX-F-121 only

Date: 2026-10-22, Asia/Tehran. Decision:
**BATCH_01_RUNTIME_VERIFIED_RESOLVED**.

The Human authorized the remaining representative browser verification only.
The [approved BATCH-01 contract](UIUX_F111_PATTERN_REMEDIATION_PLAN.md),
[implementation report](UIUX_F111_BATCH_01_REMEDIATION_REPORT.md), and
[previous runtime closure attempt](UIUX_F111_BATCH_01_RUNTIME_CLOSURE_REPORT.md)
are preserved unchanged. Their accepted automated, regression, 24 HTTP, six
mixed-link HTTP, cross-tenant, manipulated-POST and integrity evidence was not
rerun. Compliance Evidence required no additional browser interaction.

## Grounding and runtime

Branch `main`; HEAD and local upstream `origin/main`:
`43ac319c6e73e48ca9626461b73987922c498ec3`. No fetch or Git write occurred.
Billing forms SHA-256:
`7ac807b38539bdc7a3d40768a1af3cbab4d57b7a1d68948654b6308a474b4a94`;
Billing views SHA-256:
`e17cfa099bc42797433b3a06672b3c01dfce5437e8eca749404e6786eb2e8c10`.
Both match the accepted baseline. Existing dirty product files remain unchanged.

[ENTRY.json](f111_batch_01_browser_closure_evidence/ENTRY.json) records current
dirty state, source hashes, effective authority, retained fixture and source
objects. Its capture includes this attempt's newly created evidence directory;
it does not claim a clean working tree. Read-only grounding confirms the existing
active nonstaff, nonsuperuser `uiux.persona.project-manager`, unchanged membership,
Project Manager role, explicit A/B grants and four commercial/DMS capabilities.
The retained mixed A/C Document and version remain
`16f0f334-780d-4790-99b9-25ed3aee785c` and
`9382e409-ef26-43c0-9d54-8c50f2bd4041`; their synthetic PDF hash is unchanged.
All business/audit model digests match the accepted post-fixture baseline.

A fresh process served this checkout at `127.0.0.1:8003`, `--noreload`, using
`config.settings.development`, local PostgreSQL `construction_erp`, zero pending
migrations. Python 3.11.1 used the existing repository dependency directory.
No installation, settings, schema or migration change occurred. The retained
in-app browser session was already authenticated; the account-summary UI proved
its username matches P-17. No credential access or login was needed. See
[browser actor proof](f111_batch_01_browser_closure_evidence/BROWSER_ACTOR.json)
and [server record](f111_batch_01_browser_closure_evidence/SERVER.json).

## Representative browser observations — PASS

Browser tab creation and control worked in this attempt. The historical disabled
browser records remain intact. Actual browser DOM enumeration inspected every
option, including its UUID value and label, and compared complete protected
option sequences with the accepted live HTTP evidence, including blank options.

| Browser route | Nonblank Contract choices | Nonblank version choices | Result |
| --- | --- | --- | --- |
| `/billing/guarantees/new/` | Six, A/B only | Four authorized versions | PASS |
| `/billing/retention-releases/new/` | Two A/B payable subcontracts | Four authorized versions | PASS |

On each form, both existing A and B Contracts were selected in turn, the
authorized B DocumentVersion was selected, and both protected controls were
opened. These were local form interactions only; no form was submitted.
The complete DOM contained none of the C/D/X Contract UUIDs or distinctive
numbers, protected C/D/X Document/version UUIDs, or retained mixed-link fixture
Document UUID, version UUID or unique label. Exact option equality proves no
additional protected option was rendered. Recurring generic demo titles shared
by authorized and unauthorized Documents are not falsely classified as forbidden
labels. No raw HTML, cookie, CSRF token or session secret was saved.

Evidence:

- [Complete sanitized DOM option observations](f111_batch_01_browser_closure_evidence/BROWSER_OBSERVATIONS.json).
- [Guarantee accessibility tree](f111_batch_01_browser_closure_evidence/guarantee_accessibility.txt)
  and [Retention accessibility tree](f111_batch_01_browser_closure_evidence/retention_accessibility.txt).
- Guarantee [Contract screenshot](f111_batch_01_browser_closure_evidence/guarantee_contract_options.png)
  and [DocumentVersion screenshot](f111_batch_01_browser_closure_evidence/guarantee_document_options.png).
- Retention [Contract screenshot](f111_batch_01_browser_closure_evidence/retention_contract_options.png)
  and [DocumentVersion screenshot](f111_batch_01_browser_closure_evidence/retention_document_options.png).

Screenshots show the real controls and selections. Native expanded-menu overlays
are not included by the screenshot API; the complete option lists are proved by
the browser DOM and accessibility records, rather than inferred from screenshots.

## Integrity, preservation and disposition

[Runtime integrity](f111_batch_01_browser_closure_evidence/RUNTIME_INTEGRITY.json)
compares all 519 model tables before/after browser work: **zero model deltas**,
with the accepted User `last_login` digest exclusion. Business, audit, fixture,
role, permission, membership and scope records are unchanged. Server request logs
contain only GETs for Guarantee, account settings and Retention; no Compliance
interaction or business POST occurred. The temporary browser tab was closed and
only the newly created server PID was stopped; port 8003 has no remaining listener.
See [cleanup](f111_batch_01_browser_closure_evidence/SERVER_CLEANUP.json).

UIUX-F-121 is **RESOLVED**, `runtime_status: RUNTIME_VERIFIED_RESOLVED`.
Its original static confirmation and historical implementation/runtime attempts
are retained, with the previous register entry also captured separately.
[Verification](f111_batch_01_browser_closure_evidence/VERIFICATION.json) records
source/evidence preservation, other finding preservation, bounded scope, evidence
checks and final hashes. The new evidence manifest hashes the closure artifacts.

Actual touch set: this new report, new
`f111_batch_01_browser_closure_evidence/`, and UIUX-F-121's register entry only.
No product/test source, fixture, authorization, prior evidence, BATCH-02..09,
Wave C, CEP-078/079, Production or Git add/commit/push work occurred.
