# EXT-0021 — selected Development decision matrix

2026-10-27. **APPROVED for the existing minimum Development/non-production
profile only**, by direct Human instruction recorded in
[EXT-0021 Human authority](EXT-0021_HUMAN_APPROVAL_20261027.md).
The earlier proposed Linux deployment is not selected. The prior request is
retained in the [entry snapshot](../evidence/CEP-071_EXT0021_APPROVED_20261027/MATRIX_BEFORE.md).

| Matrix row | Approved repository-supported selection | Evidence / boundary |
| --- | --- | --- |
| Target environment/profile | Existing Windows `.venv-2` runtime and existing isolated loopback PostgreSQL test database; disposable local releases with synthetic file fixtures. | Existing EXT-0022 target and current CEP-071 evidence. No Production-equivalence claim or Linux/provider deployment inferred. |
| Deployment topology | Single session loopback Django application process and existing loopback test PostgreSQL, configured Development cache, existing local filesystem. | No host-count/HA, TLS proxy, external storage, network SMTP or shared-cache property inferred. Production guards remain separate and unchanged. |
| Deployment process | Existing stdlib loopback WSGI launcher and Django Development static handler; copied current source/config, collectstatic, checks, actual HTTP and dependency health; existing ASGI in-memory execution. | Explicit Development module with bounded DEBUG/persona disablement. No newly installed server or production-capable launcher claim. |
| Static/media storage | Separate local release static trees and separate retained media/protected fixture roots in a fresh restricted local child under `E:/BONIRA_Operations`. | Existing Windows DACL helper and existing local storage contract. Static bytes checked; legacy media/private roots never blanket served. No existing business media moved. |
| Secrets custody/reference | Existing private checkout `.env` and/or current injected process environment; original source stays in place, child values injected in memory only. | Existing ACL/loading guards. No `.env` copied into release/evidence, no credential/connection dump, no new secret source. Production never loads dotenv. |
| Rollback owner/process | Human Decision Authority accountable; Codex technical executor. Verify previous current-source build/config/static, reject candidate, reactivate previous and revalidate. | Same source/schema compatibility established by hashes and read-only migration-history identity. No database rollback, creation, migration or finalized-history mutation. Governed recovery applies if compatibility cannot be proved. |
| Deployment/acceptance authority | Human Decision Authority owns non-production deployment accountability and evidence acceptance; Codex executes this session. | Approval is policy/execution authority, not a fabricated post-run Human review or Human Sign-off. |

The [selected runbook](EXT-0021_DEVELOPMENT_RUNBOOK_20261027.md) supplies executable
mechanics. No target/custody/provider decision from the former request is asked
again for this bounded qualification. Ordinary Development defects and evidence
gaps are resolved under this approval.

`EXT-0021` is satisfied for the selected Development implementation/verification
components. Its Production condition remains unqualified. CEP-075's canonical
production-equivalent target property is **not established** by this approval or
by an ordinary Development deployment. Only that property and dependent final
completion may remain blocked; other executable component checks continue under
the Human clause-level continuation instruction. No PD, canonical prompt, AC/DoD
or dependency edge is rewritten. Actual Production deployment, secrets/storage,
cutover, final certification and Human Sign-off remain outside authority.
