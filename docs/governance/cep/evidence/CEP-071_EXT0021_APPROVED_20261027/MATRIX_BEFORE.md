# EXT-0021 — consolidated Human Decision Request

2026-10-27, rechecked at checkpoint `de6e20863896e7587e58bf917f807cea75f95b7a`.
**PENDING; no proposed selection below is approved.** Approve or amend this one
bounded non-production deployment contract and supply the target/configuration
references in the final column. No Production execution or sign-off is requested.

PD-004 and SPEC-006 require an explicitly approved deployment specification;
CEP-075 additionally requires the selected target's production equivalence.
The [source/configuration facts and prepared procedure](CEP-071_DEPLOYMENT_PREPARATION.md)
are already established and are not decisions to repeat. The configuration
profile matrix defines no deployment default; Small/Standard/Enterprise labels
cannot select a deployment or business behavior.

| Remaining decision | Safe bounded non-production proposal, pending approval | Smallest missing decision / external reference |
| --- | --- | --- |
| Target environment/profile | Reuse the approved CEP-013 CPython 3.11.17 / Debian 12 / linux-amd64 runtime/dependency contract and package current candidate source at its recorded HEAD, with explicit production settings and synthetic data in a disposable non-production environment. Current Windows CPython 3.11.1 request evidence is a separate preparation profile. | Designate target/location and approved deployment-design reference; explicitly identify equivalence boundaries and differences for the CEP-075 scenario. No provider, host count or HA choice is inferred. |
| Deployment topology | Retain Django/PostgreSQL, required TLS entry, configured SMTP and shared cache; add no worker unless the actual runtime requires one. | Approve component placement, TLS termination/trusted-proxy boundary and dependency endpoint/config references. Local synthetic endpoint names are not deployed facts. |
| Deployment process | Use existing `config.wsgi:application` with explicit `DJANGO_SETTINGS_MODULE=config.settings.production`, immutable candidate/previous artifacts and the prepared precheck/stop/start/validate/recovery procedure. ASGI is also request-verified; no additional server dependency is installed. | Supply target launcher/service-manager/runtime-identity reference and permission to operate the disposable target. Exact executable commands can then be completed by Development; a production-capable process server is not established by the repository. |
| Static/media storage | Separate release-specific static, retained legacy media and protected DMS roots. Keep media private by default, use existing authorized DMS delivery and never expose the protected root. Preserve previous static and existing bytes. | Supply dedicated path/mount and ownership references, static serving contract and any approved legacy-media delivery contract. Storage durability/access/backup coverage require actual target evidence. |
| Secrets custody/reference | Inject dedicated disposable non-production credentials through process environment; preserve no-production-dotenv behavior and TLS verification. Reuse the Human Decision Authority as accountable custodian if this extension is approved; Codex uses scoped references only. | Approve custody/injection and rotation/revocation owner/reference for this target. Supply references through the approved mechanism, never secret values in this matrix or evidence. No Production secret store is needed for bounded qualification. |
| Rollback owner | Extend the established Human Decision Authority accountable owner / Codex technical executor arrangement to this deployment. Retain previous artifact/config/static; require explicit database compatibility before rollback, otherwise stop for the governed recovery/roll-forward path. | Approve that bounded ownership extension and the target recovery/compatibility reference. EXT-0020 recovery numbers/target are not transferred to deployment or Production. |
| Deployment/acceptance authority | Reuse the Human Decision Authority for non-production activation and drill/evidence acceptance, with Codex technical execution, as already established for EXT-0022. | Extend that existing authority to EXT-0021 and approve the selected scenario/acceptance contract. No need to name a different owner or reapprove OP-01..04; their existing approval remains bounded to EXT-0022. |

Decision rows are `HUMAN_DECISION`; actual location/configuration/launcher/storage/
custody references are `AUTHORITATIVE_EXTERNAL_INPUT`. They form one target-contract
request, not seven successive approval rounds. Ordinary executable steps and
target defects remain Development work after selection.

`DEVELOPMENT_RESOLVABLE` and `REPRODUCIBLE_EVIDENCE`: current settings guards,
environment schema, actual WSGI/ASGI request execution, static preparation and
release/rollback/acceptance procedure are resolved for the available synthetic
profile; [timestamped proof](../evidence/CEP-071_EXT0021_REENTRY_20261027/REQUEST_EXECUTION.json).
No selected-target deployment/recovery or CEP-075 execution is claimed.

`PRODUCTION_ONLY`: Production installation/release attestation, deployment,
cutover, operational certification and Human Sign-off remain separately gated.
Those clauses do not prevent valid non-production qualification once this target
contract is established. This request changes no PD, CEP Scope/AC/DoD or dependency.
