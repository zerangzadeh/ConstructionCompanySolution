# P10-S18–S21 Release Certification Decision Packet

**Status:** **P10-CERT01–P10-CERT43 OPTION A PRODUCT OWNER ACCEPTED;
P10-S18–S21 CERTIFICATION EXECUTION AUTHORIZED; CANDIDATE FROZEN BUT S18 BLOCKED
BY THE ACCEPTED MIGRATION WINDOW. NO PRODUCTION AUTHORITY.**

**Date:** 2026-10-07.

**Verified prerequisite:** `P10-S02–S17 = Product Owner accepted`.

**Authority:** this is the single authoritative Product Owner decision packet for
`P10-S18–S21`. It is governed by `ROADMAP.md`, the P10 session map in
`docs/ROADMAP_EXECUTION_PLAYBOOK.md`, the accepted P10 S01–S06, S07–S13 and
S14–S17 packets, and the directly affected readiness, deployment, migration,
recovery, Tenant-isolation, permission, privacy and security authorities cited
here. Code, migrations and tests remain authoritative for current behavior.

**Current effect:** on 2026-10-07 the Product Owner accepted
`P10-CERT01`–`P10-CERT43 = Option A` and authorized P10-S18–S21 certification
execution only. The Product Owner subsequently supplied RPO/RTO, migration-window,
workload, environment-classification and named-owner parameters. Candidate
`P10-RC1-20261007-E0E078C9` is frozen at commit
`0db3ac9a9fa70e8a857ef0867d532be5206a14c4`, its hashed dependency lock remains
verified, and PostgreSQL 18.6 backup/restore tools plus an isolated disposable
database/DMS topology are available, as recorded in the
[S18 candidate manifest](P10_S18_CERTIFICATION_CANDIDATE_MANIFEST.md). S18 remains
`BLOCKED` after an `FC-3` gate failure: its clean migration crossed the accepted
30-minute limit, and the stopped run therefore did not prove backup, restore or
DB/DMS coherence.
S19–S21 evidence execution did not start. This acceptance authorizes no runtime
feature change, migration
against production, deployment, cutover, traffic, customer data, production
credential, production restore or production activation. `P10-S22+` remains
separately gated.

### Authoritative inputs and current baseline

- [Roadmap](../../ROADMAP.md) and the
  [execution playbook](../ROADMAP_EXECUTION_PLAYBOOK.md) define the official
  four-session envelope and keep S22–S24 separate.
- The accepted [S01–S06](P10_S01_S06_GOVERNED_METRICS_AND_REPORTING_DECISION_PACKET.md),
  [S07–S13](P10_S07_S13_RECONCILIATION_AND_EXCEPTION_DECISION_PACKET.md) and
  [S14–S17](P10_S14_S17_PROJECT_CLOSEOUT_COORDINATION_DECISION_PACKET.md)
  packets preserve source authority, explicit non-values, immutable history,
  Tenant/permission/SoD, DMS custody and downstream no-effect rules.
- The [readiness audit](PRODUCT_CAPABILITY_AND_READINESS_AUDIT.md) sections 15 and
  19 still require MFA, production storage/scanning, reproducible dependencies,
  backup/restore, observability, retention/export, support access, performance and
  operational evidence before the first production Tenant.
- The [P0 readiness review](P0_S21_READINESS_AND_UNRESOLVED_RISK_REVIEW.md)
  records provider/residency/operator, numeric RPO/RTO, evidence-lifecycle and
  integrated-acceptance parameters as open. Later bounded feature acceptance did
  not fabricate those operational decisions.
- The [workflow operations runbook](WORKFLOW_OPERATIONS.md) requires verified
  backup, retained code revision, isolated PostgreSQL testing, disposable-copy
  reverse rehearsal and compatible-code or coherent-restore rollback; reverse
  no-op data migrations are not a full rollback.
- The [Tenant lifecycle/support ADR](ADR_P0_S11_TENANT_LIFECYCLE_ENTITLEMENTS_SUPPORT.md),
  [domain/data authority](DOMAIN_AND_DATA_MODEL.md) and
  [workflow/permission matrix](WORKFLOW_AND_PERMISSION_MATRIX.md) preserve active/
  suspended/cancelled Tenant behavior, protected operations, source/DMS ownership,
  least privilege and separation rules.
- Current production settings require explicit secrets/hosts/database values and
  PostgreSQL `verify-full` TLS, but the audit records no immutable deployment
  contract, reproducible hashed lock, measured recovery, load test or production
  certification. Those absences are gates, not implied passes.

## 1. Exact S18–S21 decomposition

| Session | Exact bounded outcome | Entry and stop condition |
| --- | --- | --- |
| `P10-S18` | Freeze one release-candidate manifest and certification basis: included/excluded capabilities and migrations, build/dependency/config fingerprints, named certification owners, numeric recovery and load parameters, gate catalogue, evidence schema and failure/waiver rules. | Requires Product Owner acceptance of the decisions in this packet and an approved release-candidate manifest. Stop if scope, source authority, hosting/recovery parameters, owner independence or evidence retention is missing. No build, dependency, provider or runtime implementation is authorized. |
| `P10-S19` | Execute non-production PostgreSQL migration, rollback/reapply, backup, coherent database/DMS restore and recovery rehearsals against isolated certification environments; record integrity, compatibility and measured RPO/RTO evidence. | Requires S18-frozen artifacts, production-representative infrastructure, verified pre-test backups and named technical/recovery owners. Any data loss, fabricated history, unreconciled restore, unsafe rollback path or missing numeric recovery objective blocks the gate. No production database or storage may be used. |
| `P10-S20` | Execute approved performance/load and Tenant-isolation certification: representative volume/concurrency journeys, query/resource budgets, endurance/headroom, cross-Tenant/project/site/object/support-access attacks and lifecycle-state negatives. | Requires S19 migration/restore evidence sufficient to create the representative environment and an approved workload/volume profile. Unknown coverage, aggregate leakage, authorization bypass, unsafe saturation or an unmet material threshold is explicit failure, never a pass. |
| `P10-S21` | Execute security, privacy, permission/SoD, supply-chain, deployment-setting, DMS/export/retention and audit certification; consolidate immutable evidence and classify every finding; issue only `ELIGIBLE_FOR_P10-S22`, `BLOCKED` or `FAILED` for the frozen candidate. | Requires complete S18–S20 evidence and independent security/privacy review. Stop on any non-waivable blocker, expired/invalid waiver, missing evidence or changed candidate fingerprint. S21 may hand evidence to S22; it cannot approve release, recommend production activation or perform cutover. |

The four sessions are one certification tranche for one immutable candidate. A
new commit, dependency lock, migration, environment class, enabled capability or
security-relevant configuration after the freeze invalidates affected evidence
and requires a documented delta assessment and rerun. S18–S21 does not include
the independent readiness review in S22, Product Owner UAT/release recommendation
in S23, or final closeout/approval preparation in S24.

## 2. Certification ownership model

| Role | Accountable responsibility | Prohibited combination or implication |
| --- | --- | --- |
| Product Owner | Select the bounded candidate scope and business workload; accept the decision register; name owners; accept only eligible Medium/Low residual risk; later hold production go/no-go authority after S22–S24. | Cannot turn missing evidence or a non-waivable blocker into pass. Acceptance of this packet is not production activation. |
| Release Certification Owner | Own the S18–S21 gate matrix, evidence completeness, candidate fingerprint, finding classification and S21 disposition. Must be independent of the actor who implemented the material area under review. | Cannot execute production release, self-approve own material implementation, or accept legal/security/privacy risk alone. |
| Authorized Technical Maintainer | Build the immutable candidate and execute approved non-production migration/reapply, configuration checks and certification commands. | Execution supplies no Product Owner, security, recovery or production authority. |
| Database and Recovery Owner | Own backup coherence, PostgreSQL migration/restore procedure, recovery scenario execution, integrity reconciliation and measured RPO/RTO. | The operator who performs a material restore cannot be its sole witness/acceptor. No direct production exercise is implied. |
| Performance Owner | Own approved volume/concurrency model, test data, harness, threshold calculation, bottleneck evidence and reproducibility. | Cannot silently lower a threshold after observing a result. |
| Tenant and Authorization Reviewer | Own the route/service/object matrix, cross-Tenant/project/site tests, Tenant lifecycle negatives, Platform/support-access checks and permission-registry scope assessment. | Must not be the sole implementer of the authorization path being certified. |
| Security and Privacy Reviewer | Own threat model, identity/session, supply-chain, secrets, settings, upload/DMS/export, logging, privacy, retention and vulnerability disposition. | Cannot waive a Critical/High security, privacy, Tenant, permission or SoD failure. External professional review remains required where law, contract or risk requires it. |
| Domain and Data Owners | Attest included source authority, invariants, migration reconciliation and no automatic downstream effect for their domain. | Cannot grant P10 ownership of source facts or weaken accepted source/DMS authority. |
| Evidence Custodian | Store the signed/hash-pinned evidence index and restricted artifacts under approved retention/hold/access controls. | Cannot copy unrestricted Tenant or sensitive payload into a broadly visible certification package. |
| Authorized Release Manager / Incident Commander | Later execute an explicitly approved production plan and may stop/rollback on a predefined trigger. | These roles receive no execution authority from S18–S21; they are named now only to prevent an ownerless later release. |

One person may hold more than one operational role only where the table's
independence rules still hold and the conflict is recorded. Product Owner,
Certification Owner, Security/Privacy Reviewer and Recovery witness are distinct
for material decisions unless an approved external independence exception exists;
such an exception cannot satisfy a statutory or contractual independence rule.

## 3. Certification basis and selected release scope

Certification applies to a single immutable **release-candidate manifest**, not
the repository in the abstract and not the entire roadmap. Before S19 it must pin:

- candidate ID, source revision, immutable build artifact and dependency-lock/
  SBOM hashes;
- Python, Django, Psycopg and PostgreSQL 18.6 versions; OS/image, settings module,
  database extensions, TLS and storage classes;
- every included capability, user journey, URL/service boundary, permission code,
  migration and data store, and every explicit exclusion;
- selected Tenant/project/site/lifecycle profiles, sensitive-data classes,
  production topology and first-release operating hours;
- approved source/domain owners, legal/accounting/security/privacy approvals that
  apply, and every required reconciliation for included financial flows;
- numeric RPO/RTO by approved scenario, the workload/volume/concurrency profile,
  performance thresholds and evidence-retention periods; and
- known debt, compensating controls, approved waivers, expiry and remediation
  owners.

The manifest may exclude an unready optional capability, but only if routes,
permissions, migrations, data, UI/navigation, jobs and operational procedures
prove that it is disabled and unreachable. A mandatory shared control cannot be
excluded merely by omitting its UI. Any included flow that depends on a gated
provider, scheduler, queue, integration, AI capability or automatic downstream
effect is blocked; S18–S21 cannot implement that dependency.

## 4. Clean migration and rollback/reapply gates

All migration evidence uses isolated PostgreSQL 18.6 databases created for
certification. Never point tests or rehearsal commands at production.

| Gate | Required evidence | Pass rule |
| --- | --- | --- |
| `MIG-01` Clean apply | Empty database, frozen code/dependencies/config, `migrate --plan`, full migration apply, ledger/catalog/constraint/index/trigger inspection and Django deployment checks. | One deterministic clean apply reaches the expected leaf migrations with no drift, collision, fabricated business record or manual SQL repair. |
| `MIG-02` Upgrade rehearsal | Restored representative pre-candidate database at the approved prior baseline; row/amount/count/hash/control totals before and after; timed migration and lock/downtime observations. | Forward apply preserves Tenant/source/history invariants and remains within the approved maintenance/downtime plan. |
| `MIG-03` Failure atomicity | Deliberate safe failure at approved boundaries, process interruption procedure and post-failure integrity/ledger inspection. | Failure produces no partial authoritative state, split audit evidence, cross-Tenant association or unrecoverable ledger ambiguity. |
| `MIG-04` Rollback decision tree | Per-migration reversibility inventory; point-of-no-return; compatible-code rollback path; write-stop criteria; backup-restore path; named decision/execution owners. | Every failure window has one tested, time-bounded recovery action. A Django reverse operation is not called a data rollback when data migrations are irreversible or reverse no-op. |
| `MIG-05` Bounded rollback/reapply | Dependency-safe reverse only for migrations explicitly proved reversible, otherwise restore the coherent pre-change backup; then reapply the frozen candidate. | Schema/data/catalog/permission state matches its expected baseline after rollback and the expected candidate after reapply, with immutable history unchanged. |
| `MIG-06` Reconciliation | Tenant counts, public IDs, permission catalogue/default grants, source/control totals, finalized histories, audit chains, DMS pins and selected financial reconciliations. | All approved control totals and hashes reconcile. Missing, unknown or inaccessible rows remain explicit and block the relevant assertion. |
| `MIG-07` Operational envelope | Recorded duration, longest lock, transaction/connection pressure, required write stop, operator commands, abort triggers and cleanup. | Measured behavior fits the approved release window and does not rely on an untested live reverse or destructive contraction. |

No migration may infer a Tenant, permission grant, source owner, approval,
financial value, document status, closeout state or other accepted history from
absence, a legacy zero/default or a mutable label. Schema contraction, migration
history squash/reset and deletion of compatibility fields are outside this
tranche unless already part of the frozen, separately authorized candidate.

## 5. Backup, restore and recovery evidence

A successful backup job is not recovery evidence. The coherent recovery set must
cover the PostgreSQL database, DMS originals and immutable versions, object
metadata/manifests, encryption/key references, release artifact, dependency lock,
configuration inventory, migration ledger and restoration procedure. Secrets and
raw keys are never copied into the evidence packet.

Minimum scenarios are:

1. candidate migration/deployment failure requiring application rollback with an
   expanded compatible schema or coherent pre-change restore;
2. database loss/corruption and point-in-time or latest-good recovery supported by
   the selected platform;
3. DMS/object loss or unavailability with database-to-byte/hash reconciliation;
4. incomplete/mismatched database and object restore, which must fail closed and
   expose the mismatch rather than report success;
5. credential/key unavailability and controlled recovery with separated custody;
6. selected provider/availability-zone/region failure according to the approved
   hosting decision; and
7. Tenant suspension/cancellation, retention, legal hold and export evidence after
   restore, without restoring revoked memberships or support access.

Each exercise restores into a new isolated environment, records backup start/end,
recovery point, incident declaration, usable-service time, measured data loss and
outage, operator/witness, artifact hashes, commands/tool versions and reconciliation
results. Recovery passes only when measured RPO and RTO meet Product Owner-approved
numeric objectives for the scenario and all Tenant, permission, audit, source and
DMS integrity checks pass. Because the current authorities still record numeric
RPO/RTO, provider/residency and recovery-owner parameters as open, S21 cannot
return eligible until those facts are approved and measured.

## 6. Performance/load thresholds and test environment

### 6.1 Required environment and workload

Use a production-equivalent isolated environment: the selected production build,
settings and TLS behavior; PostgreSQL 18.6/Psycopg 3; the same database, compute,
network and private-storage classes; the same proxy/process topology; and no
debug toolbar, test-only cache or stronger unrecorded resource. Any variance needs
an approved conservative equivalence argument before execution.

The Product Owner-approved workload manifest must provide numeric values for:
active Tenants, members and concurrent sessions; projects/sites; memberships and
object scopes; documents/versions/bytes; workflow/work-item candidates; master,
transaction, audit, reporting/reconciliation and closeout row counts; peak read/
write/report/export mix; largest permitted upload/export; and daily/peak growth.
Synthetic data must preserve distribution, lifecycle and relationship shape but
contain no real personal or secret data.

### 6.2 Recommended thresholds

The recommendation is one 30-minute warm steady-state run at approved peak, one
15-minute run at **130% of approved peak**, and one **two-hour endurance** run at
approved peak. After cache warm-up:

| Journey class | Recommended service threshold |
| --- | --- |
| Ordinary authenticated list/detail/search/navigation | p95 <= 2.0 s; p99 <= 4.0 s |
| Ordinary validated create/update/transition | p95 <= 3.0 s; p99 <= 6.0 s |
| Heavy synchronous governed report/reconciliation/closeout read | p95 <= 10 s; p99 <= 20 s |
| Approved bounded synchronous export/import/document operation | p95 <= 30 s; every request <= 60 s or its lower approved product limit |

Across each run: zero invariant, cross-Tenant, permission, deadlock or data-loss
errors; zero unexpected 5xx in critical journeys; total unexpected request errors
below 0.1%; database connection utilization below 80%; steady CPU below 75%; no
swap/thrash, connection-pool exhaustion or unbounded memory/queue growth; and the
130% run degrades safely without violating security or corrupting state. A journey
with an already stricter accepted query budget retains the stricter budget. New or
changed hot paths require recorded SQL counts/plans and must avoid query growth
proportional to unauthorized cross-Tenant data.

Thresholds are fixed before the measured run. If the approved first-release
workload exceeds this profile, the stricter business requirement governs. If a
threshold is unmet, the result is fail; the Product Owner may narrow and refreeze
the release envelope, then rerun, but cannot retroactively lower the threshold to
convert the same evidence to pass.

## 7. Tenant-isolation certification

The Certification Owner maintains a route/service/object matrix for every
included capability. At minimum, focused PostgreSQL tests and targeted adversarial
review must prove:

- no cross-Tenant list/detail/search/count/aggregate/cache/export/download, guessed
  public-ID, form relationship, service command, Admin, audit, error or timing leak;
- project/site/object scope intersection on list, mutation, drill-through,
  workflow candidacy, reporting and export, including aggregate/small-cell paths;
- active membership and Tenant state rechecked at view and service boundaries;
  suspended Tenants cannot mutate and cancelled Tenants cannot use normal access;
- a URL/form/body/CSV/header organization identifier never selects authority;
- Platform Admin, Superuser, support personnel, position, assignment, project role
  and workflow candidacy grant no implicit Tenant business permission;
- support access is purpose-, time-, scope- and approver-bounded, audited and
  revoked on expiry; restored data does not reactivate access;
- related records share Tenant and project context, with database constraints and
  transaction rechecks where race-sensitive; and
- logs, metrics, errors, backups and certification artifacts neither expose nor
  mix Tenant data.

Any unexplained missing test cell or inaccessible evidence is `BLOCKED`, not
pass. Sampling can supplement but cannot replace the complete included-boundary
matrix.

## 8. Security, privacy and permission certification

S21 must record evidence for all included controls:

1. current threat model and data-flow inventory, including trust boundaries,
   privileged roles, support access, uploads/downloads, exports, backups and logs;
2. production `check --deploy`, secret/TLS/host/cookie/CSRF/proxy settings review,
   least-privilege database/storage accounts and environment separation;
3. privileged-user MFA, password/reset/session/recovery policy, privilege-change
   audit/alert evidence and removal/revocation behavior;
4. reproducible dependency lock, SBOM, license inventory, vulnerability and secret
   scans, patch/triage owner and disposition of every finding;
5. private encrypted storage, key custody/rotation/recovery, short-lived protected
   download, upload type/size/quarantine/scan behavior and fail-closed unavailable
   scanner/provider states;
6. privacy minimization, masking, purpose and object scope, export/download audit,
   logging/error scrubbing, retention/hold/disposal and backup-expiry behavior;
7. complete permission catalogue/default-role/enforcement mapping for included
   capabilities; denied service/view/Admin/HTMX paths; privilege escalation and
   membership/role change audit;
8. accepted SoD on system/security/authorization and material business actions,
   including no self-approval or emergency/support bypass;
9. append-only audit integrity, correlation, clock/timezone, restricted viewing,
   monitoring/alert exercise and tenant-safe incident diagnostics; and
10. independent targeted penetration review of Tenant/object authorization,
    session/CSRF, ID enumeration, uploads/downloads, exports, Admin/support access
    and privilege escalation.

If an included path depends on currently absent MFA, production object storage,
malware scanning, observability/alerting, retention/export operations or support
controls recorded by the readiness audit, that gap is a certification blocker.
S18–S21 may test or classify such work only; it cannot implement it.

## 9. Failure, blocker and waiver rules

### 9.1 Result vocabulary

Each gate and finding has exactly one status:

- `PASS` — objective evidence satisfies the frozen criterion;
- `FAIL` — evidence proves the criterion is not satisfied;
- `BLOCKED` — required decision, environment, owner, approval or evidence is
  missing/unknown/unavailable;
- `NOT_APPLICABLE` — the frozen scope and evidence prove that the criterion cannot
  apply; omission alone is insufficient; or
- `ACCEPTED_EXCEPTION` — a known, bounded Medium/Low residual risk has an approved
  waiver. This status remains visible and never becomes `PASS`.

Overall S21 disposition is:

- `ELIGIBLE_FOR_P10-S22` only when all applicable gates pass or have valid
  waivable accepted exceptions and there is no non-waivable blocker;
- `FAILED` when an applicable criterion is disproved; or
- `BLOCKED` when required facts/evidence/approvals are missing.

### 9.2 Failure and blocker classes

| Class | Meaning | Required disposition |
| --- | --- | --- |
| `FC-0 Evidence invalid` | Candidate/environment fingerprint changed, test target is uncertain, evidence is missing/unknown, or execution is not reproducible. | `BLOCKED`; refreeze or restore trustworthy evidence before any technical conclusion. |
| `FC-1 Control breach` | Tenant/object isolation, authorization, SoD, security, privacy, DMS/source authority, secret or audit-integrity failure. | `FAIL`; non-waivable and remove exposure/fix/rerun. |
| `FC-2 Data/recovery breach` | Migration corruption/fabrication, unsafe rollback, incoherent restore, missed RPO/RTO or unreconciled finalized history. | `FAIL`; non-waivable and fix/rerun the whole affected chain. |
| `FC-3 Release-quality failure` | Included functional, concurrency, performance, accessibility or operational threshold is not met. | `FAIL`; fix/rerun, or remove the capability from a newly frozen candidate and prove disablement. Critical/High is non-waivable. |
| `FC-4 Approval/operations missing` | Required legal/accounting/security/privacy decision, owner, runbook, monitoring or environment is absent. | `BLOCKED`; omission cannot be classified as pass or N/A. |
| `FC-5 Known unrelated debt` | A pre-existing finding is demonstrably outside the frozen scope and shared privilege/runtime paths. | Separate debt, visible in evidence. It becomes FC-1/FC-3 when scope mapping proves release impact. |
| `FC-6 Bounded residual risk` | A known Medium/Low issue has complete impact evidence and does not touch a non-waivable control. | Eligible only for `ACCEPTED_EXCEPTION` under section 9.4. |

Severity is based on credible impact/exploitability and scope, not on a scanner
label alone. Related lower-severity findings are assessed cumulatively; several
Medium findings may form a High blocker.

### 9.3 Non-waivable blockers

No waiver is permitted for:

- cross-Tenant/project/site/object disclosure or mutation, privilege escalation,
  authorization bypass, missing default-deny enforcement or accepted SoD breach;
- Critical/High security or privacy exposure, hard-coded/exposed secret, insecure
  production TLS/database setting, absent privileged MFA for an included release,
  or an exploitable dependency without an effective approved fix/containment;
- data loss/corruption, fabricated history, source-authority collision, broken
  finalized/audit lineage, unreconciled permission catalogue or DMS byte/hash
  authority failure;
- clean migration failure, unsafe/unknown rollback path, incoherent restore,
  inability to meet approved RPO/RTO or unproved backup recovery;
- missing legal/accounting/security/privacy approval required for included scope;
- automatic downstream effect, provider/queue/integration/AI behavior or
  production action outside explicit authority; or
- missing/unknown evidence for any of the above. Unknown is not residual risk.

Other Critical/High functional, reliability or performance findings block the
frozen candidate. They are resolved by correction and rerun, or by explicitly
removing the capability from a newly frozen candidate with proof that no shared
dependency remains.

### 9.4 Waivable Medium/Low risk

A waiver requires the exact candidate and criterion, evidence-backed likelihood/
impact, affected Tenants/data/journeys, compensating controls, detection and
rollback, remediation owner/date, expiry no later than the next release or 90 days
(whichever is earlier), and approvals from the Product Owner, Certification Owner
and relevant Security/Privacy/Recovery/Domain owner. Expired waivers block.

The six inherited unrelated `apps.organizations.test_permission_registry`
failures remain separate known debt and do not automatically fail S18–S21. They
become certification blockers only if the frozen-scope assessment proves that a
failure maps to an included permission, default grant, route/service enforcement,
duplicate semantic authority or privilege path, or prevents the complete registry
suite from providing required included-scope assurance. Their tests and debt IDs
must remain visible; they may not be skipped, relabelled as pass or fixed under
this planning authority.

## 10. Release, rollback and production-activation authority

S18–S21 creates evidence only. Recommended authority is:

- after S22 independent review, S23 UAT/release recommendation and S24 final
  packet, the **Product Owner** alone records business production go/no-go;
- Security/Privacy, Recovery, Domain/Accounting/Legal owners retain veto authority
  over their non-waivable controls;
- the named **Authorized Release Manager** executes only the separately approved
  immutable production plan;
- the Authorized Release Manager or Incident Commander may stop traffic/change
  or invoke the preapproved safe rollback immediately on a trigger; stopping needs
  no Product Owner preapproval;
- the Database and Recovery Owner alone executes database restore with an
  independent witness; resumption requires revalidation and Product Owner go;
- implementers and the Certification Owner cannot self-authorize production; and
- any changed candidate, missed window, failed preflight or new material finding
  returns to no-go until explicitly reviewed.

The production-activation boundary is a separate, dated, candidate-specific
authorization after S22–S24. It must name artifact, environment, window, owner,
preflight, monitoring, rollback triggers, communications and customer-data scope.
No sentence in this packet, a green test, S21 eligibility or later certification
recommendation substitutes for that activation record. There is no automatic
deployment, cutover, migration, traffic switch or downstream effect.

## 11. Audit and evidence retention

The evidence index is immutable and hash-pins the candidate manifest, environment
fingerprint, commands/tool versions, timestamps/timezone, actors/witnesses,
criteria, raw-artifact locations/hashes, results, findings, waivers, reruns and
supersession. DMS owns retained bytes/versions; Audit owns important action
evidence. The index stores no secrets and minimizes Tenant/personal data. Access is
default-deny and separately permissioned for sensitive security/recovery evidence.

Recommended retention is **seven years after the candidate's last production use
or longer when contract, law, investigation or legal hold requires it**, subject
to final Privacy/Legal confirmation before S19. Raw high-volume load traces may be
reduced after 90 days only when the immutable summary, hashes, representative
diagnostics and reproducibility metadata remain; source personal/business payload
is retained only under its owning policy, not copied into certification evidence.
Superseded/failed evidence remains linked and cannot be silently replaced.

## 12. Complete Product Owner decision register

Every material choice has a stable ID. On 2026-10-07 the Product Owner accepted
Option A for every decision.

| ID | Realistic options | Recommendation and rationale | Session |
| --- | --- | --- | --- |
| `P10-CERT01` Envelope | A: S18–S21 only; B: include S22; C: include S22–S24/activation | **A.** Matches the official map and preserves independent review, UAT and activation gates. | All |
| `P10-CERT02` Certification meaning | A: candidate-specific evidence and S22 eligibility only; B: repository-wide production approval; C: automatic deploy signal | **A.** Makes the conclusion precise and non-operational. | All |
| `P10-CERT03` Scope basis | A: immutable included/excluded candidate manifest; B: latest branch; C: entire roadmap | **A.** Makes every assertion reproducible and bounded. | S18 |
| `P10-CERT04` Candidate changes | A: invalidate affected evidence and delta/rerun; B: accept latest silently; C: ignore non-code changes | **A.** Configuration, dependency and migration changes can alter risk. | S18–S21 |
| `P10-CERT05` Ownership | A: named model in section 2; B: implementer self-certifies; C: collective/unnamed ownership | **A.** Gives each critical gate an accountable owner. | S18 |
| `P10-CERT06` Independence | A: independent material reviewers/witnesses; B: same actor everywhere; C: independence only after incident | **A.** Preserves accepted SoD and credible certification. | All |
| `P10-CERT07` Environment | A: production-equivalent isolated certification environment; B: developer laptop; C: production itself | **A.** Gives relevant evidence without risking production. | S18–S21 |
| `P10-CERT08` Clean migration | A: deterministic empty PostgreSQL 18.6 apply and inspection; B: existing test DB only; C: migration-plan review only | **A.** Detects graph, bootstrap and PostgreSQL-specific faults. | S19 |
| `P10-CERT09` Upgrade rehearsal | A: representative prior baseline with reconciled before/after controls; B: clean apply only; C: production first run | **A.** Tests the actual deployment transition safely. | S19 |
| `P10-CERT10` Rollback | A: tested per-window decision tree, compatible-code or coherent restore; B: assume reverse migration; C: manual repair | **A.** Reflects irreversible/no-op migrations and protects history. | S19 |
| `P10-CERT11` Reapply | A: bounded rollback/restore then exact forward reapply; B: rollback only; C: untracked SQL | **A.** Proves repeatability and migration-ledger integrity. | S19 |
| `P10-CERT12` Migration failure | A: fail on data/history/authority/reconciliation ambiguity; B: warning; C: missing treated as empty | **A.** Prevents fabricated or partial production state. | S19 |
| `P10-CERT13` Backup set | A: coherent DB/DMS/manifest/key-reference/artifact/config set; B: database dump only; C: backup-success log | **A.** Restores the actual evidence system, not one component. | S19 |
| `P10-CERT14` Recovery objectives | A: scenario-specific numeric RPO/RTO approved before pass; B: best effort; C: infer from backup schedule | **A.** Converts recovery claims into measurable obligations. | S18–S19 |
| `P10-CERT15` Restore exercise | A: new isolated environment with operator and independent witness; B: inspect backup; C: restore over source | **A.** Proves usability without destroying evidence. | S19 |
| `P10-CERT16` Recovery scenarios | A: all seven scenarios in section 5 as applicable; B: database only; C: provider declaration | **A.** Covers schema, bytes, keys, tenancy and hosting failure. | S19 |
| `P10-CERT17` Restore pass | A: measured objectives plus full integrity reconciliation; B: service starts; C: partial data accepted | **A.** Availability without trustworthy data is not recovery. | S19 |
| `P10-CERT18` Workload profile | A: Product Owner-approved numeric volume/concurrency/journey mix; B: ad hoc sample; C: maximum theoretical | **A.** Ties performance to a real first-release promise. | S18–S20 |
| `P10-CERT19` Latency thresholds | A: section 6.2 fixed thresholds; B: compare with developer baseline only; C: no user threshold | **A.** Sets explicit usable-service budgets. | S20 |
| `P10-CERT20` Load shape | A: peak, 130% headroom and two-hour endurance; B: single-user smoke; C: uncontrolled stress only | **A.** Covers steady, surge and leak/exhaustion risk. | S20 |
| `P10-CERT21` Error/resources | A: explicit zero/security/invariant and bounded error/saturation limits; B: average latency only; C: visual judgment | **A.** Prevents a fast but unsafe pass. | S20 |
| `P10-CERT22` Query performance | A: retain stricter accepted budgets and inspect changed hot paths; B: global query count only; C: omit SQL evidence | **A.** Targets tenant-safe scaling and N+1 regressions. | S20 |
| `P10-CERT23` Threshold miss | A: fail, fix or narrow/refreeze/rerun; B: lower after result; C: waive all performance | **A.** Keeps evidence honest while allowing a smaller truthful release. | S20 |
| `P10-CERT24` Tenant matrix | A: complete included route/service/object matrix plus adversarial tests; B: sample models; C: UI checks | **A.** Tenant isolation is end-to-end and non-negotiable. | S20 |
| `P10-CERT25` Tenant lifecycle | A: active/suspended/cancelled and restored-access negatives; B: active only; C: status by UI | **A.** Certifies lifecycle enforcement at the server boundary. | S20 |
| `P10-CERT26` Platform/support access | A: no implicit access; purpose/time/scope grant and expiry; B: admin bypass; C: shared support login | **A.** Preserves Platform/Tenant separation and audit. | S20–S21 |
| `P10-CERT27` Security baseline | A: all controls in section 8; B: deploy check only; C: vulnerability scan only | **A.** Covers application, supply chain, data and operations together. | S21 |
| `P10-CERT28` Privileged identity | A: MFA and governed recovery/session/privilege change; B: password only; C: defer after launch | **A.** Matches the recorded first-production gate. | S21 |
| `P10-CERT29` DMS/data protection | A: private encrypted/scanned fail-closed storage and recovery; B: local files with policy note; C: public object links | **A.** Preserves DMS custody, privacy and integrity. | S19–S21 |
| `P10-CERT30` Permission/SoD | A: catalogue/default/enforcement matrix plus negative tests and accepted SoD; B: role-name review; C: Owner/Admin implicit | **A.** Certifies actual least privilege, not UI appearance. | S20–S21 |
| `P10-CERT31` Penetration review | A: independent targeted review of included boundaries; B: automated scanner only; C: post-launch | **A.** Tests attack paths automation does not establish. | S21 |
| `P10-CERT32` Gate vocabulary | A: PASS/FAIL/BLOCKED/N/A/ACCEPTED_EXCEPTION; B: red/amber/green without meaning; C: pass/skip | **A.** Keeps missing and waived evidence explicit. | All |
| `P10-CERT33` Unknown evidence | A: BLOCKED; B: pass with note; C: treat missing as zero/N/A | **A.** Preserves non-fabrication and auditability. | All |
| `P10-CERT34` Non-waivable blockers | A: section 9.3; B: Product Owner may waive all; C: security owner may waive all | **A.** Prevents risk acceptance from defeating core controls. | All |
| `P10-CERT35` Medium/Low waivers | A: bounded, multi-owner, expiring accepted exception; B: verbal acceptance; C: permanent blanket waiver | **A.** Makes residual risk visible, owned and temporary. | S18–S21 |
| `P10-CERT36` Six unrelated registry failures | A: separate debt unless frozen-scope mapping triggers blocker; B: silently ignore; C: automatic release blocker regardless of relevance | **A.** Preserves debt honestly while using evidence-based scope. | S18–S21 |
| `P10-CERT37` S21 conclusion | A: eligible for S22, failed or blocked only; B: production approved; C: automatic release recommendation | **A.** Preserves S22–S24 authority. | S21 |
| `P10-CERT38` Production go/no-go | A: Product Owner after S22–S24 and required veto-owner clearance; B: Certification Owner; C: CI pipeline | **A.** Separates evidence, business decision and execution. | Future gate |
| `P10-CERT39` Stop/rollback | A: named Release Manager/Incident Commander may stop immediately; Recovery Owner executes restore with witness; B: wait for committee; C: implementer discretion | **A.** Enables safe containment with accountable recovery. | Future gate |
| `P10-CERT40` Activation | A: separate dated candidate/environment/window authorization; B: certification auto-activates; C: deploy on merge | **A.** Enforces the production-activation boundary. | Future gate |
| `P10-CERT41` Evidence/retention | A: immutable minimized hash-pinned package, seven-year recommendation plus governing longer rule; B: transient CI log; C: unrestricted raw-data archive | **A.** Supports audit without unnecessary data duplication. | All |
| `P10-CERT42` Validation strategy | A: focused gate tests, one final full frozen-candidate suite, no repeated broad runs without trigger; B: unit only; C: repeatedly run everything | **A.** Provides release confidence with controlled cost. | S19–S21 |
| `P10-CERT43` Deferred capabilities | A: preserve S22+, AI/RAG/vector, providers, queues/schedulers, integrations, automatic effects and activation; B: certify stubs as live; C: absorb them | **A.** Prevents scope and authority expansion. | All |

**Recorded Product Owner disposition:**
`P10-CERT01`–`P10-CERT43 = Option A`.

Before S19 evidence execution, the Product Owner must record the candidate ID and
scope, named owners/reviewers, production topology, numeric workload/volume model,
scenario-specific RPO/RTO, operating/release window and final retention/legal
parameters. A decision to accept Option A does not fabricate those facts.

## 13. Focused PostgreSQL and certification validation plan

Use uniquely named disposable databases and isolated storage prefixes; record and
verify exact targets before creation or disposal. Preserve and do not inspect,
migrate, reset or drop `test_construction_erp` or any production resource.

Minimum execution order and stop conditions:

1. **Freeze/preflight (S18):** validate manifest hashes, owners, environment,
   release-scope route/permission/migration inventory, open parameters and evidence
   access. Stop before execution if any mandatory parameter is open.
2. **Focused migration tests (S19):** migration graph/plan; clean apply; permission,
   catalogue, constraint and trigger state; prior-baseline upgrade; deliberate
   atomic failure; dependency-safe rollback or coherent restore; exact reapply;
   drift and control-total reconciliation.
3. **Focused recovery tests (S19):** coherent backup and each applicable scenario;
   DMS version/hash, key-reference, Tenant/lifecycle, permission, audit and
   finalized-history reconciliation; measured RPO/RTO and runbook timing.
4. **Focused Tenant tests (S20):** parameterized cross-Tenant/project/site/object
   negatives over every included service/view/form/Admin/HTMX/download/export and
   aggregate path; inactive membership, suspended/cancelled Tenant, Platform/
   support access, guessed IDs, logs/errors and concurrent relationship changes.
5. **Focused performance tests (S20):** representative data build validation,
   journey/query baselines, peak, 130% surge and endurance; PostgreSQL plans,
   locks/deadlocks, connection/CPU/memory/storage/error evidence and safe
   degradation. Any security/integrity error stops the run and fails the gate.
6. **Focused security/privacy tests (S21):** production-settings/deploy check,
   dependency/SBOM/license/vulnerability/secret checks, identity/session/CSRF,
   upload/download/DMS/export, logging/masking/retention, permission/SoD and
   targeted independent penetration cases.
7. **One final frozen-candidate run (S21):** the full PostgreSQL suite once, serial
   or with proved isolation, after focused gates are green; one clean migration
   and release preflight; no new implementation. A failure is classified, not
   retried until green without root cause and evidence.
8. **Evidence closeout:** local-link/stale-claim/whitespace/diff-hygiene review,
   hash/sign the evidence index, verify all failures and waivers, and issue only
   the S21 disposition defined in section 9.

Known heavy validations run once at the explicit certification checkpoint. Start
with focused cases and broaden earlier only when a shared-boundary failure or
candidate change supplies a recorded trigger. Test data and logs must be
synthetic/minimized and secret-free.

## 14. Preserved gates

The following remain explicitly unauthorized:

- `P10-S22+`, including independent final risk/readiness review, UAT finding
  triage, release recommendation, final closeout and any approval packet outcome;
- all AI, RAG, embeddings, vector search/analytics, predictive or autonomous
  capability;
- email/SMS/push or other providers, queues, schedulers, background delivery,
  external integrations, external BI/warehouse behavior and automated retry;
- every automatic project, contract, claim, document, asset, inventory, workflow,
  Knowledge, AP/AR, Treasury, Accounting, Project Cost, Payroll, regulatory or
  other downstream/financial/legal effect;
- any weakening of Tenant/object scope, source authority, permission/SoD, privacy,
  DMS custody/hash/retention, immutable history or fail-closed non-value rules;
- production credentials/data access, production migration/restore, deployment,
  cutover, traffic, customer onboarding and activation; and
- fixes for the six unrelated permission-registry failures unless separately
  authorized. Their classification rule is limited to `P10-CERT36`.

## 15. Exact bounded runtime-authorization wording

The Product Owner may use the following wording after recording acceptance and
the mandatory S18 parameters. It authorizes certification execution only, not
application-feature implementation or production:

> I accept `P10-CERT01`–`P10-CERT43 = Option A` as recorded in
> `docs/architecture/P10_S18_S21_RELEASE_CERTIFICATION_DECISION_PACKET.md` and
> authorize **P10-S18–S21 only** for the candidate-specific, non-production
> release-certification work defined there: freeze the approved release-candidate
> manifest and named ownership; execute isolated PostgreSQL 18.6 clean migration,
> representative upgrade, bounded rollback or coherent restore and exact reapply;
> execute coherent backup/restore and measured scenario-specific RPO/RTO
> rehearsals; execute the approved performance/load, Tenant-isolation, security,
> privacy, permission/SoD, DMS, supply-chain and audit gates; and retain the
> minimized immutable evidence package. Missing, unknown, unavailable or failed
> evidence remains `BLOCKED` or `FAIL` and cannot become pass. Non-waivable
> Tenant, authorization, SoD, privacy, DMS/source-authority, lineage, migration,
> restore, RPO/RTO and Critical/High security controls remain non-waivable. The six
> unrelated permission-registry failures remain separate known debt unless the
> frozen-scope assessment meets the blocker rule in `P10-CERT36`. S21 may conclude
> only `ELIGIBLE_FOR_P10-S22`, `BLOCKED` or `FAILED`. This authorization excludes
> feature/runtime implementation, production credentials or data, production
> migration/restore, deployment, cutover, traffic and activation; `P10-S22+`;
> AI/RAG/vector; providers; queues/schedulers; integrations; automatic downstream
> or financial/legal effects; and any weakening of accepted Tenant, permission/
> SoD, privacy, DMS, source-authority or immutable-history controls. Certification
> does not activate production and creates no automatic production action.

That decision and bounded certification authorization were supplied on
2026-10-07. The mandatory S18 parameters were not supplied by the packet or the
authorization; the accepted fail-closed rules therefore stopped execution at the
S18 preflight.

## 16. Product Owner authorization and S18 execution record

### 16.1 Recorded ownership

| Responsibility | Recorded owner |
| --- | --- |
| Certification Acceptance Owner | Product Owner |
| Certification Owner / Coordinator | Authorized Technical Maintainer |
| Evidence Custodian | Authorized Technical Maintainer |
| Migration/Restore Executor | Authorized Technical Maintainer |
| Database/Recovery Executor | Authorized Technical Maintainer with database authority |
| Security/Tenant Isolation Reviewer | Independent authorized Security Reviewer |
| Performance Executor | Authorized Technical Maintainer |
| Stop/Rollback authority | Certification Executor or Security Reviewer when a non-waivable gate fails |
| Production Activation Owner | Not authorized by this tranche |

The Database/Recovery Executor is not the acceptance owner. Production activation
remains unassigned and prohibited. Certification Owner/Coordinator and Evidence
Custodian are now the Authorized Technical Maintainer. Production operator/
topology and any scenario-specific domain/legal/accounting reviewers still require
candidate-specific recording before evidence execution.

### 16.2 Numeric parameter reconciliation

The following exact packet values are accepted and frozen:

- ordinary list/detail/search/navigation: p95 <= 2.0 seconds and p99 <= 4.0
  seconds;
- ordinary validated mutation/transition: p95 <= 3.0 seconds and p99 <= 6.0
  seconds;
- heavy governed report/reconciliation/closeout read: p95 <= 10 seconds and p99
  <= 20 seconds;
- bounded synchronous export/import/document operation: p95 <= 30 seconds and
  every request <= 60 seconds or a stricter accepted product limit;
- load duration: 30-minute warm steady state at approved peak, 15 minutes at 130%
  of approved peak, and two hours endurance at approved peak;
- errors/resources: zero invariant, cross-Tenant, permission, deadlock or data-loss
  errors; zero unexpected 5xx in critical journeys; total unexpected request
  errors below 0.1%; database connections below 80%; steady CPU below 75%; no
  swap/thrash, pool exhaustion or unbounded memory/queue growth;
- evidence retention: seven years after last production use or longer under the
  governing contract/law/investigation/hold, subject to Privacy/Legal confirmation;
  raw load traces may be reduced after 90 days under section 11;
- certification recovery targets: RPO = 15 minutes and RTO = 60 minutes, without
  creating a production SLA;
- maximum planned migration/downtime window: 30 minutes, with the rollback
  decision before irreversible production activation and failure on overrun unless
  separately re-approved;
- workload identity: 50 baseline concurrent users, 100 peak, 130 surge, 10
  Tenants, 25 active users per Tenant and 10 representative projects per Tenant;
  and
- data shape: realistic records across every governed Reporting, Reconciliation
  and Closeout source domain; artificially tiny data cannot certify performance.

The test environment must record its exact topology/resources. When production-
equivalent capacity is unavailable, the only permitted classification is
`environment-qualified / production capacity certification still gated`.

### 16.3 S18 freeze/preflight evidence and disposition

The candidate-preparation result is recorded in
`P10_S18_CERTIFICATION_CANDIDATE_MANIFEST.md`:

- Candidate ID: `P10-RC1-20261007-E0E078C9`;
- final candidate commit:
  `0db3ac9a9fa70e8a857ef0867d532be5206a14c4`;
- frozen 1,134-path runtime/dependency fingerprint:
  `76cdbbddea7a03c0463fee4a1827c70f6fadf40dfd5c340cfc9bb4d3794d6b05`;
- included scope: all implemented runtime through accepted P10-S02–S17 plus the
  required certification documentation and dependency lock;
- exact migration heads and the documentation-only attestation boundary are
  listed in the manifest;
- `requirements-lock.txt` is hashed and exact for the recorded CPython 3.11/
  Windows x86-64 environment, and `pip install --require-hashes` succeeded in a
  new temporary environment; and
- PostgreSQL 18.6 with `CREATEDB` is reachable; PostgreSQL 18.6 `pg_dump` and
  `pg_restore` are verified at their recorded executable paths; and
- an isolated source/restore database plus DMS source/backup/restore topology was
  created without using `test_construction_erp` or production data.

The clean migration was stopped after crossing the accepted 30-minute maximum at
approximately 30 minutes 8 seconds. No database or DMS backup had yet been
created, so database restore, DMS restore and restored DB/DMS coherence remain
not passed. Both disposable databases and the isolated DMS root were cleaned up.

Disposition: **`P10-S18 = BLOCKED (FC-3 Release-quality failure: non-waivable
migration-window failure and incomplete backup/restore preflight)`**. Per the
accepted S18 stop condition, `P10-S19–S21` did not start.
`test_construction_erp` was not used, inspected, migrated, reset or claimed as
evidence. No backup/restore, RPO/RTO, migration/reapply, load, Tenant penetration,
security penetration or full PostgreSQL certification result is claimed.

### 16.4 Completed repository preflight checks

Using `.venv/Scripts/python.exe` after the unconfigured PATH alias failed:

- Django system check: **PASS**, no issues;
- migration drift (`makemigrations --check --dry-run`): **PASS**, no changes;
- targeted Ruff for `apps/reporting`, `apps/organizations`, `apps/audit` and
  `config`: **PASS**;
- Reporting template compilation: **PASS**, six templates;
- Reporting URL reversal: **PASS**, 18 routes; and
- `git diff --check`: **PASS** with line-ending warnings only.

These are preflight repository checks, not substitutes for the blocked candidate,
PostgreSQL migration/restore, performance, Tenant or security certification. The
six unrelated permission-registry failures remain separate known debt; they were
not repaired or reclassified. No waiver was requested or granted.
