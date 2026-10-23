# BONIRA UI/UX Runtime Validation Entry Checklist

Baseline target: `43ac319c6e73e48ca9626461b73987922c498ec3`

Latest governance reconciliation checkpoint: `UIUX_REFERENCE_PERSONA_DOCUMENTATION_RECONCILIATION_CHECKPOINT_15.md`

## Before execution

- [ ] Historical evidence manifests remain immutable; superseded cleanup instructions are overridden by Checkpoint 15 rather than rewritten.
- [ ] `runtime_evidence/RETENTION_SUPERSESSION_CHECKPOINT_15.md` is present and governs persona-retention cleanup.

- [ ] Persistent reference personas are retained after validation unless explicitly retired by governance decision.
- [ ] Every provisioned reference persona has a stable persona/account identifier; no language-specific display title is required.
- [ ] Reference persona credentials/secrets are outside governance artifacts and must not be displayed in UI.
- [ ] Reference-persona authority uses actual governed roles/scopes; Persona is not treated as a product Role.
- [ ] No cleanup plan deletes/deactivates reference persona accounts merely because a wave completed.
- [ ] `RV-033` is treated as a product/UI requirement: a governed reference-persona catalogue surface must be confirmed or implemented before it can PASS.

- [ ] Runtime environment is non-production.
- [ ] Exact runtime Git SHA is recorded.
- [ ] If SHA differs from the frozen baseline, affected UI drift has been reconciled.
- [ ] Base URL and browser/version are recorded.
- [ ] Personas are mapped only to actual identities/portal grants needed by their scenarios.
- [ ] Effective permissions, organization/project/site/object scope are evidenced rather than inferred from titles.
- [ ] `Tenant Owner ≠ Tenant Admin ≠ Platform Admin`.
- [ ] `Timekeeping ≠ Payroll`.
- [ ] `HSE/Safety ≠ Quality/QA-QC`.
- [ ] `Inventory/Storekeeping ≠ Equipment/Fleet`.
- [ ] `Contract/Commercial ≠ Procurement Buyer ≠ Billing/Settlement`.
- [ ] `Project Manager ≠ Project Controls/Technical Office ≠ Project Operational User`.
- [ ] External Supplier/Partner portal identity is not treated as an ordinary tenant member.
- [ ] Owner/Platform Admin accounts are not used as least-privilege shortcuts.
- [ ] No password, token, cookie, session or secret is written to audit evidence.
- [ ] Scenario-required data/lifecycle states exist before that scenario starts.
- [ ] Mutating scenarios use non-production, disposable/reversible records and governed services.
- [ ] Screenshot/evidence naming is prepared.
- [ ] Remediation remains disabled during validation.
- [ ] Blocked/UTV targets remain explicit; they never silently become PASS.
- [ ] Missing persona-critical product surface is recorded as `NEEDS_PRODUCT_REVIEW`, not invented.
- [ ] CEP-078/CEP-079 status is not inferred from this audit.

## Specialist readiness additions

| Persona | Required readiness before |
| --- | --- |
| P-20 Payroll Specialist | RV-018, RV-025 |
| P-21 Personnel Decree / Employment Records Specialist | RV-015, RV-029 |
| P-22 Inventory / Storekeeper | RV-009, RV-025 |
| P-23 Contracts & Commercial Specialist | RV-030, RV-025 |
| P-24 Project Controls / Technical Office | RV-006, RV-031, RV-025 |
| P-25 Quality / QA-QC Specialist | RV-020, RV-025 |
| P-26 External Supplier / Partner Portal User | RV-032, RV-025 |

## Scenario-specific notes

### RV-029
Verify the canonical internal employment-record management surface before execution.
If domain services support employment-record management but no governed internal user surface exists,
record `NEEDS_PRODUCT_REVIEW`; do not fabricate a route.

### RV-032
External portal validation requires a real non-production invitation/grant with a second
tenant/opportunity available for isolation comparison. Do not broaden tenant membership to simulate it.

## Start decision

Runtime readiness remains **scenario-scoped**.

Existing Wave-A identities/data stay valid only for scenarios already proven during entry review.
New personas/scenarios require their own bounded readiness check before execution.

This checklist does not authorize remediation, Product Decisions, CEP-078, CEP-079,
Production actions, permission bypass or Git writes.
