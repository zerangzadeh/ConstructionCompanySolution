# BATCH-03 — remaining site-only runtime closure

Date: 2026-10-22, Asia/Tehran. Decision: **BATCH_03_RUNTIME_VERIFIED_RESOLVED**.
**UIUX-F-123 and UIUX-F-124 = RUNTIME_VERIFIED_RESOLVED / RESOLVED.**

This closes only the missing site-only runtime control under the Human's explicit
Development reference-actor provisioning authorization and the
[BATCH-03 contract](UIUX_F111_PATTERN_REMEDIATION_PLAN.md#batch-03).
The [original implementation report](UIUX_F111_BATCH_03_REMEDIATION_REPORT.md)
and all its pending-at-that-time evidence remain unchanged as execution history.

## Grounding and accepted evidence

Branch `main`; HEAD and local `origin/main` remain
`43ac319c6e73e48ca9626461b73987922c498ec3`, divergence 0/0. The ten dirty product
files and existing untracked evidence/fixtures were re-grounded without Git writes.
BATCH-01/F-121 and BATCH-02/F-122 remain runtime-resolved. The accepted BATCH-03
manifest, product/test/configuration sources, authorization services and prior
evidence match their recorded hashes: **no drift**. Accepted automated tests,
regression attribution, P-17/organization runtime negatives/positives and
representative browser checks were **not repeated**.
[Entry, source hashes and canonical authorization review](f111_batch_03_runtime_closure_evidence/ENTRY.json).

Actual touch set: this new report and its new evidence directory; current closure
metadata for F-123/F-124 only; one canonical Development reference account,
membership, existing-role assignment, SITE grant, resolved quarantine record,
four canonical audit events and authentication/session bookkeeping. No product,
test, model, migration, setting, template, permission or role catalogue changed.

## Canonical reference actor

No existing active nonstaff/nonsuperuser identity had both capabilities with
effective SITE-only authority. The all-tenant follow-up review confirms that the
new reference is the only qualifying actor. Existing catalogue roles containing
both permissions were compared; `operations_manager` has the smallest capability
set among eligible roles: **395 existing permissions**. Assigning that existing
role to one SITE is supported by canonical role/scope services. No new role,
permission, permission combination, inheritance policy or Product Decision was
needed. The full capability set is retained in evidence; it is not represented
as a two-permission custom role.

Existing tenant owner `account.demo-construction-01.owner` created and assigned
the reference, independently approved by existing `uiux.persona.tenant-admin`.
Both already held the required canonical account/assignment/grant authority and
Organization scope; their own authority did not change. `create_organization_account`
initially quarantined the new membership. `assign_membership_role` and
`grant_membership_scope` established explicit authority with dual control and
resolved quarantine. `initialize_personal_password` performed the canonical
mandatory first-password initialization. No account flags were bypassed.

| Reference component | Retained Development value |
| --- | --- |
| Username | `uiux.reference.batch03.site-only` |
| User | `d33f6622-277c-4c4a-b029-f09e2c66fb77`; active; nonstaff; nonsuperuser |
| Membership | `78945e45-ca3c-47ac-97de-bb8c85e64b00`; active in `demo-construction-01` |
| Existing role | `operations_manager` |
| Independent role assignment | `95a11c98-c3f7-4cff-bb91-59b593a74a42` |
| SITE grant | `190285aa-a4f7-44bf-8e8f-30d33f5b579a`; `PRJ-01-01 / SITE-01` |
| Grant target | `eef2f5d7-dc51-44d3-8414-8dc480f500c0` within Project `58f517da-2139-45ac-8b7b-4f3d3a3d26e8` |
| Required capabilities | `payable_measurements.record` and `payable_certificates.create`: present |
| Effective scope | Exactly one SITE grant; zero Project grants; zero Organization grants |

The `project_id` on the SITE grant identifies its parent and does not constitute
a Project grant. Canonical checks deny both Organization scope and Project-only
authority for that parent. Before/after evidence records absent identity,
quarantined account, assigned role before scope, final full capability set, exact
grant and authority fingerprint. The final fingerprint is unchanged throughout
the runtime retest. [Provisioning stages and fingerprint](f111_batch_03_runtime_closure_evidence/PROVISIONING.json),
[all-tenant review and four canonical audit events](f111_batch_03_runtime_closure_evidence/AUTHORITY_REVIEW.json).

The account remains as the authorized persistent Development reference, clearly
labeled `BATCH_03_SITE_ONLY_RUNTIME_REFERENCE` in assignment/grant reasons.
Its generated credential is stored only in a current-user DPAPI-protected
PSCredential outside the repository; no password, cookie or CSRF token appears
in evidence. Retention does not authorize business use, other batches or production.

An initial harness query used a nonexistent `ProjectSite.deleted_at` field and
failed **before any write**. The harness was corrected to the existing active-site
schema and rerun; the failed attempt is retained. No product source changed.

## Missing runtime controls

A fresh checkout process served loopback `localhost:8006`, `--noreload`,
`config.settings.development`, PostgreSQL `construction_erp`; zero pending
migrations. [Server identity](f111_batch_03_runtime_closure_evidence/SERVER.json).
Actual login and CSRF middleware handled every POST. Each otherwise-valid payload
failed only its protected source field. No new business fixture was necessary:
existing qualifying payable subcontracts/items A/B/C/D/X were reused.

| Finding | Independently completed missing controls |
| --- | --- |
| F-123 — Payable Measurement | GET exposes only blank ContractItem choice; forced A/B/C/D/X items rejected; missing-date plus unauthorized-source redisplay remains empty; complete responses exclude source UUIDs, model labels, numbers, descriptions/titles and sibling line identifiers. |
| F-124 — Payable Certificate | GET exposes only blank Contract choice; forced A/B/C/D/X Contracts rejected; missing-period-start plus unauthorized-source redisplay remains empty; complete responses exclude Contract/item UUIDs, labels, numbers, descriptions/titles and sibling line identifiers. |

**14/14 live observations PASS**, seven for each finding. Sources belonging to
the granted site's parent Project, same-tenant siblings/other Projects and the
other tenant are all absent. Per-request model digests show no changes.
[Detailed HTTP evidence](f111_batch_03_runtime_closure_evidence/RUNTIME_HTTP.json),
[runtime log](f111_batch_03_runtime_closure_evidence/runtime.txt).

An additional site-only browser opening was unavailable because local browser use
is disabled in Work settings. No setting was changed and no new browser proof is
claimed. The contract's representative browser evidence for both selectors is
already accepted, unchanged and retained; the sole outstanding site-only negative
is now covered by authenticated live HTTP on each route.
[Additional browser attempt](f111_batch_03_runtime_closure_evidence/BROWSER_ATTEMPT.json).

## Integrity and closure

Before/provisioned/runtime-after comparisons cover all **519 model tables**.
After provisioning, only session bookkeeping changes; User `last_login` is
excluded from its identity digest. All **518 non-session models' pre-existing
rows remain identical**, excluding only the exact new canonical reference rows.
All prior audits and authorities, BATCH-01/02 fixtures, P-17 and organization
actor records are preserved. Four new canonical audits record account creation,
role assignment, scope grant and password initialization. There is **no payable
measurement/certificate or other business mutation**, source change, unauthorized
success audit or runtime authority change.
[Runtime before](f111_batch_03_runtime_closure_evidence/RUNTIME_BEFORE.json),
[runtime after](f111_batch_03_runtime_closure_evidence/RUNTIME_AFTER.json),
[integrity verification](f111_batch_03_runtime_closure_evidence/RUNTIME_VERIFICATION.json).

Only F-123/F-124 current statuses and appended closure metadata change. Their
original static confirmation, problem/source evidence and prior implementation
attempt remain. Every other finding entry, all old reports/evidence and every
product/test/configuration file remain unchanged. New evidence scripts pass Ruff
lint/format; YAML, links, whitespace, scope and preservation checks pass.
Accepted application validation is reused because no relevant drift exists.
[Closure verification](f111_batch_03_runtime_closure_evidence/VERIFICATION.json),
[evidence index](f111_batch_03_runtime_closure_evidence/INDEX.json).

Only the newly launched server was stopped; no port 8006 listener remains.
[Cleanup](f111_batch_03_runtime_closure_evidence/SERVER_CLEANUP.json).
Migration expected/created/executed: **NO**. BATCH-04..09 = **NOT_EXECUTED**;
Wave C = **NOT_STARTED**. No Production, CEP-078/079, Git add/commit/push,
financial action, Human Sign-off, Production Certification or Production Cutover.

**BATCH_03_RUNTIME_VERIFIED_RESOLVED — STOP.**
