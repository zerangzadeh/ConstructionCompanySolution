# BONIRA UI/UX Reference Persona Retention — Checkpoint 14

## Decision

Status: `REFERENCE_PERSONA_DISPLAY_REQUIREMENT_AMENDED`

The Product Decision Authority clarified that persistent reference personas do **not** require
Persian display titles in the product UI.

Checkpoint 13 remains valid for persona retention and reuse, except for the Persian-title requirement.

## Superseded requirement

The following Checkpoint 13 requirement is withdrawn:

`Persian display title is mandatory in the UI.`

It is replaced with:

`A stable persona/account identifier is sufficient.`

The UI may use:

- technical username;
- Persona ID;
- existing human-readable name;
- or another stable existing label.

No language-specific display label is mandatory.

## Unchanged decisions

- 26 reference personas remain defined.
- Provisioned reference personas remain persistent.
- Validation completion does not trigger deletion/deactivation.
- Role/scope mapping remains traceable.
- Persona does not equal Role.
- Credentials/secrets remain forbidden in governance artifacts and UI.
- Authority must not be broadened to force PASS.
- Impersonation remains unauthorized.
- Runtime scenario count remains 33.
- RV-033 remains in the runtime plan.

## RV-033 effect

RV-033 must validate discoverability/reusability of reference personas using stable account/persona identifiers.

It must **not** fail merely because a Persian display title is absent.

## Existing audit impact

- Static audit rerun: `NO`
- Existing 108 findings changed automatically: `NO`
- Persona count changed: `NO`
- Scenario count changed: `NO`
- Product code changed by this documentation amendment: `NO`
- User accounts changed: `NO`
- Roles/permissions changed: `NO`
- CEP-078 executed: `NO`
- CEP-079 executed: `NO`
- Git write: `NO`

## Closure

Checkpoint result:

`REFERENCE_PERSONA_RETENTION_POLICY_AMENDED_NO_PERSIAN_TITLE_REQUIREMENT`
