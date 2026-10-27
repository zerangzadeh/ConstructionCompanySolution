# EXT-0021 — remaining Human decisions

2026-10-27. Only unresolved target/authority choices; source facts, environment
schema and prepared mechanics are in [deployment preparation](CEP-071_DEPLOYMENT_PREPARATION.md).
PD-004 / SPEC-006 require explicit selection; these rows are not approvals.
One bounded answer may cover both the production design and its designated
non-production equivalent. No Production execution authority is requested.

| Unresolved item | Minimum decision / authoritative reference needed |
| --- | --- |
| Deployment target/environment | Identify selected environment(s), designated disposable drill target and evidence that its boundaries represent the approved production design |
| Topology | Approve the actual app/database/TLS-proxy/cache/SMTP/storage arrangement, including only components actually required; supply target configuration references |
| Process contract | Select launcher/service-manager and runtime identity/bind/trusted-proxy contract; approve the prepared release/validation procedure and target-specific start/stop/switch commands |
| Static/media contract | Approve actual durable paths/mount owners, static serving and legacy media access contract; protected DMS bytes remain outside all public serving roots |
| Secrets contract | Identify approved environment-scoped injection/custody and rotation/revocation owner/reference; process env and no production dotenv are already enforced |
| Rollback/acceptance ownership | Name release, activation, rollback/roll-forward and acceptance authorities; approve target-specific compatibility/recovery decision and evidence acceptance contract |

After selection, exact target mechanics and reproducible deployment/recovery
evidence can proceed within Development authority. Environment-specific facts
are AUTHORITATIVE_EXTERNAL_INPUT; deployment/cutover/certification on Production
remain PRODUCTION_ONLY. No row grants Human Sign-off or Gate PASS.
