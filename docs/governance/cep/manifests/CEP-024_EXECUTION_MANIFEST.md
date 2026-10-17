# CEP-024 Execution Manifest

## Grounding and authority — 2026-10-17

- Branch and baseline: `main` at `76362e23fbbd18c5f280343ece064e95eeae4881`; `origin/main` matches the Registry reconciliation baseline.
- Standing authority: active for eligible current-governed non-production CEPs. The prompt's generic authorization text is superseded by current governance; its bounded security scope, AC/DoD, and `Migration Impact = NONE` remain authoritative.
- Canonical prompt: SHA-256 `88c0183c5fb8415c9d614f8999ddeed66cea1d424692431b047233a246000c97`, matching `CEP_PROMPT_MANIFEST.yaml`.
- Prerequisite and gates: CEP-001 is COMPLETE/CLOSED_VERIFIED; GATE-01 and GATE-02 are PASS. CEP-024 has no dependency or mutation collision with CEP-015, CEP-020, CEP-021, or CEP-022.
- Migration impact: `NONE`.

## Repository grounding

Timekeeping currently enforces tenant and project/site consistency in `TimesheetEntry`, scopes service actions through `require_business_permission`, and filters form querysets by active membership scope. The remaining bounded gap is a stale/cross-site combination: `TimesheetEntry.clean()` checks that an Activity belongs to the selected Project but does not require that a selected Site equals the Activity's optional Site. `TimesheetEntryForm` likewise lacks this cross-field invariant. The service relies on model validation, but must also reject the combination explicitly before persistence.

No data representation is required: the existing `project`, optional `site`, optional `activity`, and Activity site relationship are sufficient. The intended change enforces only the stated cascade/invariant; it does not infer an absent Site from Activity, modify activity/project assignment, alter permissions, or add UI behavior beyond returning the existing form error.

## Actual execution touch set before product mutation

- `apps/timekeeping/models.py`: require a selected Site to equal an Activity's assigned Site when that Activity is site-bound.
- `apps/timekeeping/services.py`: reject the same invalid Site/Activity combination before persistence while preserving current tenant/object-scope checks.
- `apps/timekeeping/forms.py`: apply the matching cross-field form error so the standard template returns a bounded user-visible rejection.
- `apps/timekeeping/test_cep024_scope.py`: focused allowed, denied, cross-tenant, direct-route and form tests.
- CEP-024 evidence, change manifest, completion report, and Registry closeout files.

No migration, model-field addition, assignment inference, data reconciliation, financial behavior, production action, Human Sign-off, or Git action is in scope.
