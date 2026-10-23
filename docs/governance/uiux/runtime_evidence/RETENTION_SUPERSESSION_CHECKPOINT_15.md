# BONIRA Runtime Evidence Retention Supersession — Checkpoint 15

## Status

`ACTIVE_SUPERSESSION`

This file does not rewrite historical evidence. It records which earlier cleanup instructions are no longer operational.

## Superseded instructions

The following historical evidence/guidance contains pre-Checkpoint-13/14 cleanup language:

1. `runtime_evidence/README.md`
   - earlier guidance to revoke assignments/scopes and inactivate memberships after validation.

2. `runtime_evidence/diagnostics/ENTRY_PREPARATION_20261021.json`
   - historical plan for account deactivation and access revocation after validation.

3. `runtime_evidence/diagnostics/P14_PRE_MUTATION_MANIFEST_20261021.json`
   - historical plan to revoke access, change membership status and potentially deactivate the user.

These files remain historical evidence.

## Current governing rule

For provisioned reference persona identities:

`RETAIN → RECONCILE → RESET SECRETS IF NEEDED → REVERIFY BEFORE REUSE`

Do not automatically:

- delete the reference account;
- deactivate it because validation completed;
- revoke its approved persona role/scope merely as generic test cleanup.

Explicit governance/security action may still suspend, revoke or retire an identity when independently justified.

Scenario-specific disposable business data continues to follow its owning-domain cleanup rules.

## Evidence integrity

Historical JSON manifests MUST NOT be rewritten to erase their original state.

Where the runtime evidence README still contains the old cleanup rule, add a visible note pointing to this
Checkpoint 15 supersession; do not falsify the historical timeline.
