# CEP-026 Execution Manifest

## Authority and baseline

- Authorization: `AUTH-BATCH-003`
- Scope: `CEP-026 — ESS own-data privacy boundary` / `IMB-0093` only
- Environment: Development / Non-Production
- Branch: `main`
- Baseline HEAD: `89ca8f28da8828a6ac4226baceb18d27c5d98f09`
- Baseline working tree: dirty with preserved CEP-016/CEP-017 changes and artefacts
- Prerequisites: `CEP-001 = COMPLETE`; `CEP-010 = COMPLETE`
- Entry gate: `GATE-01 = PASS`, recorded in `ROADMAP.md`
- Migration impact: `NONE`

## Canonical source verification

The Human authorization and canonical prompt were supplied separately. The named
prompt was recovered unmodified from the approved consolidated prompt pack already
available to the project. The attached CEP-026 archive supplied the referenced
PD-016, PD-025, PD-029, SPEC-014, SPEC-017, UIA-005, ESS field/security/capability,
and configuration materials. Historical `NOT AUTHORIZED` text is superseded only
by `AUTH-BATCH-003`; all scope, security, AC, DoD, migration and no-inference
controls remain in force.

## Repository grounding

- `Person.user` is the authoritative tenant-scoped User link and is unique per
  Organization when present.
- `WorkRelationship` is the effective-dated Person employment episode and may
  explicitly link one legacy `Employee`; no username, email or employee-number
  inference is required or permitted.
- CEP-011 already supplies employee-visible DMS policy, typed employment links,
  same-Person history rules, separate download authorization and download audit.
  Its private `_subject` resolver is document-specific and is the reuse seam.
- No coherent ESS personal-profile route exists. `NAV-006` is currently rendered
  unavailable. Existing Workforce screens are administrative and permissioned;
  they are not own-data ESS surfaces.
- Existing employee DMS list/detail/download routes enforce active Organization,
  source permissions, tenant filtering and direct-route reauthorization.
- Existing Payroll and Timekeeping operational routes are not reclassified as ESS
  by this package; CEP-026 grants no new authority over them.

## Actual Execution Touch Set

Product code and UI:

- `apps/workforce/ess_services.py` — shared authoritative identity/episode
  resolution, own-episode enforcement and masked read model.
- `apps/documents/employee_access.py` — consume the shared resolver without
  weakening existing DMS/source/download checks.
- `apps/workforce/views.py`, `apps/workforce/urls.py` — read-only ESS own-profile
  routes with direct-object enforcement.
- `apps/organizations/context_processors.py` and
  `templates/components/navigation_links.html` — expose `NAV-006` only when the
  same backend identity boundary resolves; visibility grants no authority.
- `templates/workforce/ess_profile.html` — Persian-first RTL-safe, responsive,
  read-only masked presentation.

Tests:

- `apps/workforce/test_cep026_ess_privacy.py` — service, permission, tenant,
  direct URL, masking, UI visibility and non-disclosure coverage.
- `core/test_cep017_navigation.py` — remove `NAV-006` from the static list of
  permanently unavailable targets now that CEP-026 conditionally implements it;
  all other CEP-017 navigation assertions remain unchanged.
- Existing focused CEP-010/CEP-011 regression tests are verification-only and
  are not intended mutation surfaces.

Documentation and evidence:

- `ROADMAP.md`
- `docs/architecture/DATA_MODEL.md`
- `docs/architecture/DOMAIN_AND_DATA_MODEL.md`
- `CEP-026_ACCEPTANCE_MAPPING.csv`
- `CEP-026_EVIDENCE_MANIFEST.csv`
- `CEP-026_CHANGE_MANIFEST.csv`
- `CEP-026_COMPLETION_REPORT.md`

## Explicit exclusions

- No model or migration change.
- No new role, permission, workflow, request lifecycle or editable ESS field.
- No username/email/employee-code identity inference.
- No Payroll/Timekeeping capability activation, deployment, production action,
  Human Sign-off, or other CEP.
