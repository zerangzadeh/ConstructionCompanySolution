# BONIRA UI/UX Reference Persona Retention — Checkpoint 13

## Decision

Status: `PERSISTENT_REFERENCE_PERSONA_POLICY_APPROVED`

Human Product Decision Authority decided that UI/UX personas, once provisioned, must remain reusable
reference identities instead of disposable test fixtures.

## Approved rules

- 26 persona definitions remain the canonical runtime persona set.
- Provisioned persona accounts are persistent.
- Validation completion is not a cleanup/deletion trigger.
- Persian display titles are mandatory.
- Reference personas must be visible in a governed administration/reference-persona UI.
- Role/scope mapping remains evidence-based and traceable.
- `Persona ≠ Role`.
- Credentials/secrets are never stored in governance artifacts or displayed in the UI.
- Authority must not be broadened solely to make a runtime scenario pass.
- Impersonation / `Login as` is not authorized by this decision.

## Runtime plan impact

A targeted governance/UI scenario is added:

`RV-033 — Reference persona catalogue and reusable identity administration`

Audit-specific runtime scenario count becomes: `33`

Wave count remains: `5`

RV-033 belongs to Wave A because it concerns administration/global governance UX.

## Cleanup policy change

Previous disposable-test cleanup assumptions are superseded for reference persona accounts.

New rule:

`RETAIN → RECONCILE → RESET SECRETS IF NEEDED → REVERIFY BEFORE REUSE`

Scenario-specific business records still follow owning-domain cleanup rules.

## UI requirement

A governed product surface must allow authorized administrators to view reference personas using Persian labels.

Minimum visible information:

- Persona ID;
- Persian display title;
- provisioning/readiness state;
- organization/context summary;
- role/scope summary;
- validation coverage/readiness summary.

Technical username is secondary.

Credentials/tokens/session values are forbidden in this UI.

## Documents revised

- `UIUX_AUDIT_CHARTER.md`
- `UIUX_RUNTIME_PERSONA_DATA_MATRIX.yaml`
- `UIUX_RUNTIME_VALIDATION_MATRIX.yaml`
- `UIUX_RUNTIME_VALIDATION_EXECUTION_PLAYBOOK.md`
- `UIUX_RUNTIME_VALIDATION_ENTRY_CHECKLIST.md`
- `UIUX_PERSONA_COVERAGE_RATIONALE.md`

New canonical documents:

- `UIUX_REFERENCE_PERSONA_RETENTION_POLICY.md`
- `UIUX_REFERENCE_PERSONA_CATALOGUE.yaml`

## Existing audit impact

- Static audit rerun: `NO`
- Existing 108 findings automatically changed: `NO`
- Existing root patterns reset: `NO`
- Product code changed by this documentation update: `NO`
- User accounts created by this documentation update: `NO`
- Roles/permissions changed: `NO`
- CEP-078 executed: `NO`
- CEP-079 executed: `NO`
- Production action: `NO`

## Closure

Checkpoint result:

`REFERENCE_PERSONA_RETENTION_POLICY_FROZEN`

Next engineering work must confirm or implement the governed UI surface for reference personas and
reconcile currently provisioned audit identities with the canonical catalogue without deleting them.
