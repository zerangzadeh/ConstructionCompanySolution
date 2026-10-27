# Shared target/design mapping — BONIRA-PE-NP-01

2026-10-27. One mapping for CEP-070 → CEP-074 and CEP-075. **NOT QUALIFIED
PRODUCTION-EQUIVALENT.** This document defines a candidate and a concrete
reference-design proposal; it is not Human approval, a second CEP registry,
Production topology, certification or a waiver of canonical acceptance.

## Authority and comparison basis

The byte-verified CEP-070/074/075 prompts, recovered PD-003/004/005,
SPEC-005/006, configuration matrix, dependency matrix and GATE-08/11 register
are identified by archive/member hashes in
[ENTRY](../evidence/SHARED_TARGET_20261027/ENTRY.json).
Repository-local prompts remain primary. The recovered specification/profile
sources are absent locally and were read from the approved consolidated archive.

SPEC-006 explicitly says `UNSPECIFIED PRODUCTION TOPOLOGY — DO NOT INVENT / DO
NOT CERTIFY`. Its required controls are explicit environment boundaries, TLS,
environment-scoped secrets, versioned migration/release and rollback evidence,
recovery integration, traceable monitoring/logging, tenant/object scope and
governed support access. It specifies no OS, process-server product, cloud,
host/replica count, orchestration, HA or failover design. The configuration
profile matrix contains business-policy keys, **no infrastructure defaults**.

PD-004 requires an explicit approved specification for topology, boundaries,
migration sequencing, rollback/roll-forward, secrets and activation gates.
CEP-075 §6 requires a production-equivalent scenario after topology selection;
§7 requires approved deployment-specification conditions. CEP-074 requires its
mandatory CEP-070 outcome and EXT-0020 verification condition. Similar local
components cannot establish those missing reference-design semantics.

Existing EXT-0020/0021 approvals deliberately select Development and expressly
do not establish equivalence. Current authority permits this mapping and new
isolated candidate-control qualification. It supplies no missing Production fact.

## Property mapping and classification

`ESTABLISHED` below means the stated fact is evidenced, **not** that its
Production counterpart is known. A classification applies to the precise
property/subproperty in its row. No unapproved difference is called permitted.

| Property | Classification | Established value / proposed mapping / qualification boundary |
| --- | --- | --- |
| Application architecture/source | ESTABLISHED | Current synchronous Django modular monolith, PostgreSQL/Psycopg, templates and collected static; 1,510 current product source hashes frozen at main `de6e20863896e7587e58bf917f807cea75f95b7a`. |
| Available local OS/runtime | ESTABLISHED | Windows build 26200, CPython 3.11.1, Django 5.2.17, Psycopg 3.3.5 using its binary implementation/libpq 18.4 (`180004`). Existing `.venv-2`; no installed WSGI/ASGI process-server package. The approved Linux contract uses pure Psycopg/system libpq; matching package version does not establish artifact equality. |
| Existing release-runtime identity | ESTABLISHED | CEP-013 already qualified CPython 3.11.17 / Debian 12 / linux-amd64, pure Psycopg and system libpq; image `python@sha256:8fb0b110b022c70cbe09d3ff1fb313654f31f9c814abb0d48180af56d906a199`; `requirements-prod-linux.lock` is the dependency contract. This is prior build evidence, not a running local target or approved Production topology. |
| Reference OS/runtime designation | HUMAN_APPROVAL_REQUIRED | Proposed reference: reuse that existing Linux release artifact and current source, rather than claim Windows/3.11.1 equality. A reference designation and permitted-difference mapping must be explicit; neither is present. |
| Execution resource for proposed Linux reference | EXTERNAL_ENVIRONMENT_REQUIRED | No Docker/Podman executable; WSL executable reports subsystem not installed. The Linux artifact was previously exercised in CI, not this host. No OS/virtualization install, reboot or CI write/dispatch was inferred. An existing designated isolated Linux/container resource would resolve this once its reference is approved. Linux is the repository-supported proposal, **not an invented canonical OS requirement**. |
| PostgreSQL transport/control mechanics | ESTABLISHED | New private native PostgreSQL 18.6 cluster, loopback only, SCRAM, mandatory TLS, explicit certificate trust and `verify-full`; actual TLS and rejection probes in CONTROLS. Existing service/configuration/business database untouched. |
| PostgreSQL Production version/topology | PRODUCTION_ONLY | Actual Production version, placement, replica/PITR/failure-domain design remain unspecified; no equality or operational guarantee claimed. Proposed non-production version is the already exercised 18.6. |
| Shared cache control | ESTABLISHED | Existing Django FileBasedCache, separate restricted root; actual write/read from distinct processes. Sufficient only for a single-host cache control. Redis/Celery are future architecture, not mandatory here. No LocMem/Dummy substitution or multi-host claim. Production cache/backend topology is not established. |
| Application entrypoints | ESTABLISHED | `config.wsgi:application` and `config.asgi:application`; production settings used explicitly, DEBUG/personas false, complete middleware unchanged. Networked ASGI is not selected or required merely because an entrypoint exists. |
| Deployable application/TLS server reference | HUMAN_APPROVAL_REQUIRED | Repository-supported interface proposal: synchronous WSGI, actual HTTPS boundary and explicit production settings; qualify a deployable process server against the approved reference. No Production server product is established. The local stdlib WSGI/TLS harness proves transport/config controls only and is expressly excluded as a Production process-server qualification. No fabricated server/provider value is proposed. Ordinary server engineering follows reference selection, without a further equivalent-options planning round. |
| Network/TLS mechanics | ESTABLISHED | Direct loopback HTTPS with an explicit per-client synthetic trust root; PostgreSQL certificate validation; no global trust change. Forwarded-proto trust disabled. Actual host/CSRF/HSTS/protected-path checks. No external ingress, proxy header-stripping, public certificate lifecycle or Production trust claim. |
| Static/media/document boundaries | ESTABLISHED | 153 collected assets in a dedicated static root; separate media/private/cache roots and recursive restricted Windows DACL. Exact asset bytes checked over HTTPS; legacy media and private document paths denied. New synthetic files only; existing business media not relocated. Linux permissions/durable mounts need target-specific execution on a Linux reference. |
| Secrets/configuration mechanics | ESTABLISHED | Production settings consume process environment without dotenv. New synthetic database/application/TLS credentials are generated privately for this run, never printed or committed. Existing private Development secret source is unchanged; its prior qualification is retained. No Production credentials/provider are inferred. |
| Backup/recovery policy already approved | ESTABLISHED | EXT-0020 supplies RPO 900s, RTO 3600s, backup interval 900s, retention/restore-test interval 30 days, no PITR for current synthetic Development; all four classes; Human Decision Authority accountable/acceptance owner and Codex session executor. Do not request these values or owners again. Existing 23 focused methods and 20 ERP recovery checks remain evidence for their actual unchanged scope. |
| New target recovery-control mechanics | ESTABLISHED | Existing backup adapter exercised through verified PostgreSQL TLS plus separate document/media, configuration metadata and operational-log trees. Small synthetic control fixture restores exact Decimal values and copied-file hashes. This is new target-control evidence, **not** CEP-074, current ERP restore qualification, a new RPO/RTO PASS or replacement for the retained full ERP proof. |
| Logging/monitoring integration | ESTABLISHED | Existing fixed-field request telemetry and read-only `operational_health`, actual DB/cache health and failed-dependency exit; correlated records retained in a private sink. Existing approved EXT-0022 OP-01..04/CEP-076 evidence is retained, not rerun. No new tool/threshold/on-call/SLA is selected. Health remains `production_readiness: NOT_VALIDATED`. |
| Deployment/rollback path | ESTABLISHED | Existing approved build/config/collectstatic/health/failure rejection and previous verified build/config/process reactivation; 075 retained seven-step, 15-HTTP Development result. Same-source/schema compatibility only. New TLS target checks do not retroactively reclassify the old HTTP deployment drill. Qualified reference deployment/rollback must run after reference approval. |
| Access/isolation controls | ESTABLISHED | Loopback listeners, new private cluster/files, restricted recursive DACL, non-superuser application credential, authenticated Django middleware, no trusted client tenant identifier. Prior ERP restored tenant/permission denials retained. No claim that a two-row infrastructure fixture is ERP tenant-isolation evidence. Support/emergency access remains governed by existing services/Operating Specification. |
| Permitted differences and equivalence scope | HUMAN_APPROVAL_REQUIRED | Proposal: synthetic tenant dataset; isolated addresses and per-target certificates/secrets; lower scale/no capacity claim; no external business effects; no destructive Production recovery. Host/provider/HA/storage-failure/OS/server differences cannot silently be permitted. Explicitly approve the reference comparison and allowed differences; reject or leave required mismatches unqualified. |
| Actual Production policy/storage/key custody/operation | PRODUCTION_ONLY | Production RPO/RTO/PITR/retention, off-host durability/encryption/key recovery, activation, real credentials/TLS lifecycle, continuous operation and final certification remain outside current authority. No canonical extra requirement for encryption/HA/region drills is manufactured for these non-production packages from historical findings. |

## Development and reproducible work disposition

`DEVELOPMENT_RESOLVABLE` TLS/shared-cache/production-settings/isolation mechanics
were implemented in a new restricted candidate using existing Python, Django,
PostgreSQL and Git-bundled OpenSSL. `REPRODUCIBLE_EVIDENCE` probes were executed,
not left as plans. Their final classifications are ESTABLISHED above.

[CONTROLS](../evidence/SHARED_TARGET_20261027/CONTROLS.json) records exact
runtime, timestamps, trust/cipher, measured results, limitations and shutdown.
The [harness](../evidence/SHARED_TARGET_20261027/qualify.py) creates only new
private resources, then stops its cluster and web process. No unattended service,
machine trust entry, package/dependency installation, product/schema migration,
existing database access or completed CEP re-execution occurs. Synthetic private
artifacts remain in the protected external run directory; the short-lived TLS
certificate is not a future deployment credential or custody solution.

Two failed attempts are retained. The first was native Windows inherited pipe
handles during `pg_ctl start`; its new cluster was stopped explicitly. The
second correctly returned HTTPS redirect because the WSGI reference harness
omitted the server-owned `HTTPS` flag. Harness repairs preserve all production
guards and the failed records. Neither was a product defect or a passed attempt.

Additional unselected server/provider installations would not supply an approved
reference or permit a missing difference. They are not prerequisite work that
can honestly settle the outstanding equivalence decision. Qualification on the
designated runtime and reference-specific ERP recovery/deployment are dependent
work, not currently executable work to be repeated against an arbitrary design.

## Single consolidated Target Profile Decision Request

**Requested decision:** approve one bounded non-production reference design and
its permitted differences for BONIRA-PE-NP-01, or identify the existing approved
reference that must govern it. The mapping and executed control evidence above
are the concrete review material. This is a design decision, not a request for
Production deployment, current Development reapproval or post-run Human Sign-off.

| Decision item | Repository-supported proposed value | Exact canonical requirement | Consequence of approval / designation | Consequence if unavailable |
| --- | --- | --- | --- | --- |
| Shared reference runtime and deployment boundary | Reuse CEP-013's pinned Debian 12/CPython 3.11.17 Linux release contract and current source; PostgreSQL 18.6 with verified TLS; explicit production settings; synchronous WSGI with a qualified deployable server and HTTPS boundary; single-host shared file cache only if that is the approved reference. Supply an existing isolated Linux/container resource, or an approved reference that explicitly resolves the observed Windows/runtime/server differences. No cloud/HA/host-count value is inferred. | PD-004: topology, boundaries, migration sequencing, rollback/roll-forward, secrets and activation gates require explicit approved specification. SPEC-006: topology unspecified; TLS and environment-scoped secrets mandatory. CEP-075 §6/7: production-equivalent scenario after topology selection and approved deployment-specification conditions. | Use this same profile for both chains; qualify the selected deployable server, runtime, TLS, storage/cache and config on the designated isolated target. Technical mechanics remain Codex work; no further planning/option-selection round. Approval alone is not equivalence PASS. | 075 AC1/AC2/full DoD and target-dependent 070 qualification remain blocked; 074 cannot bypass 070. Existing controls/evidence remain reusable only within their stated scope. |
| Scope of equivalence and allowed differences | Permit synthetic data, isolated endpoints/per-target synthetic credentials and certificates, lower scale with no capacity claim, and no external business effects. Define whether the single-host local storage/cache boundary represents the required reference; otherwise supply the required storage/failure-domain contract. Retain existing Development objectives/owners unchanged; no Production numbers or custody are selected. Windows-to-Linux/server/storage differences are not presumed equivalent. | CEP-070 AC1/AC5: governed data-class coverage and environment-specific evidence; CEP-074 §7 and AC1/AC2/DoD: approved production-equivalent environment, objectives and actual restore evidence; CEP-075 AC1/AC2/DoD: approved target, exact environment/version and actual deployment execution. SPEC-005: integrity, accessibility, tenant isolation and evidence after restore. | Execute target-specific backup/control qualification; close 070 only if every canonical implementation AC/DoD is supported; then execute 074. Independently finish 075 on the same qualified target. Required ERP isolation/reconciliation and rollback evidence must actually pass. | No equivalence designation or AC/DoD promotion from Windows probes or prior Development drills. Both chains remain at their genuine design/environment boundary. |

Only these missing reference/allowed-difference semantics require a Human
decision. Provisioning/access to the selected absent runtime is External.
Production-only facts remain deferred and are not requested as a prerequisite
for authorized non-production work. After the consolidated decision and target
availability, execution resumes automatically under the existing instruction.
