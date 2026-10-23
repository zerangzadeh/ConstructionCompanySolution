# BONIRA UI/UX Reference Persona Retention Policy

## Status

`APPROVED — AMENDED BY CHECKPOINT 14`

Decision owner: Human Product Decision Authority  
Latest checkpoint: `UIUX_REFERENCE_PERSONA_RETENTION_CHECKPOINT_14.md`

## 1. Purpose

BONIRA runtime personas are persistent governed reference identities for UI/UX validation,
regression testing, demonstrations and future product verification.

A persona is not automatically a BONIRA business role.

`Persona ≠ Role`

## 2. Retention rule

For every provisioned reference persona:

- keep the persona catalogue entry;
- keep the reference account unless an explicit governance decision retires it;
- keep its approved membership/role/scope mapping traceable;
- do not delete or deactivate it merely because one validation wave completed;
- do not broaden its authority simply to make a scenario pass;
- do not store credentials, tokens, cookies or secrets in governance artifacts.

Temporary scenario transactions may still be cleaned up according to the owning domain's rules.
The persistent persona account itself is not ordinary disposable test data.

## 3. Display identity rule

There is **no requirement** for a Persian display title in the product UI.

A reference persona may be identified in the UI by:

- stable technical username;
- Persona ID;
- or an available human-readable display name.

The product must not require a separate Persian title solely for audit/reference-persona purposes.

Existing Persian labels in governance documents are descriptive metadata only.

## 4. UI visibility requirement

Reference personas must remain discoverable through an appropriate governed administrative UI surface
or equivalent existing user/access-management surface.

At minimum, an authorized administrator should be able to identify:

- the persona/account;
- provisioning/readiness state;
- organization/context;
- role/scope summary;
- validation readiness/coverage state where the product exposes such audit metadata.

Credentials and authentication secrets must never be shown.

A `Login as` / impersonation function is **not** authorized by this policy.

## 5. Account naming

A stable technical alias should be used where a dedicated account is required, for example:

`uiux.persona.payroll`

Existing already-provisioned audit accounts may be retained and reconciled rather than renamed if
renaming would damage evidence continuity.

## 6. Role and scope rule

Reference persona provisioning must prefer:

1. existing canonical business roles;
2. existing governed role combinations;
3. explicit existing scope grants.

Do not create a new product role merely because a persona exists.

If a persona cannot be represented by existing authority without violating governance:

- keep the persona in the catalogue;
- mark it `NOT_PROVISIONED`, `BLOCKED_*`, or `NEEDS_PRODUCT_REVIEW`;
- do not bypass authorization.

## 7. Lifecycle states

Recommended persona lifecycle states:

- `DEFINED`
- `READY_TO_PROVISION`
- `PROVISIONED`
- `PARTIAL`
- `BLOCKED`
- `NEEDS_PRODUCT_REVIEW`
- `RETIRED_BY_DECISION`

Validation completion alone is not a retirement reason.

## 8. Reuse

A provisioned persona may be reused for later UI/UX waves, regression validation,
responsive/accessibility sweeps, demo/staging verification and future governed acceptance preparation.

Before reuse, effective permissions, scope and relevant scenario data must be re-verified.

## 9. Cleanup

Cleanup after validation is:

`RETAIN → RECONCILE → RESET SECRETS IF NEEDED → REVERIFY BEFORE REUSE`

Only scenario-specific disposable data follows domain cleanup/reversal rules.

## 10. Product boundary

This policy does not itself:

- create or rename users;
- create roles;
- grant permissions;
- change authorization semantics;
- require a Persian display title;
- authorize impersonation;
- authorize Production provisioning;
- execute CEP-078 or CEP-079.


## 11. Historical evidence supersession

Historical runtime-preparation manifests are evidence and must not be rewritten merely because later
governance decisions supersede an instruction they contain.

Checkpoint 15 supersedes earlier persona cleanup instructions by reference.

Current rule:

`RETAIN → RECONCILE → RESET SECRETS IF NEEDED → REVERIFY BEFORE REUSE`

The following historical evidence remains immutable:

- `runtime_evidence/diagnostics/ENTRY_PREPARATION_20261021.json`
- `runtime_evidence/diagnostics/P14_PRE_MUTATION_MANIFEST_20261021.json`

Their earlier revoke/deactivate cleanup instructions are historical and no longer operational authority.

See:
`runtime_evidence/RETENTION_SUPERSESSION_CHECKPOINT_15.md`
