Repository: `E:\Construction_Company_Solution`  
Branch: `main`

## Human Authority

`BONIRA-PE-NP-01` is approved as the bounded production-equivalent **non-production reference design**.

Approved reference:

- Debian 12 / CPython 3.11.17 Linux release contract from CEP-013
- current BONIRA source
- PostgreSQL 18.6 with verified TLS
- production settings
- synchronous WSGI with a qualified deployable WSGI server
- HTTPS boundary
- single-host shared cache
- isolated protected static/media/private storage
- environment-scoped non-production secrets
- existing governed deployment, rollback, recovery and EXT-0022 operating controls

Permitted non-production differences:

- synthetic data
- isolated endpoints
- synthetic credentials/certificates
- lower scale with no SLA/capacity claim
- single-host topology
- no external business effects
- no Production HA/failover/provider/storage/key-custody claim

Windows Development evidence is supporting evidence only; the approved reference remains Linux.

## Objective

**Complete the remaining executable CEP program for this target:**

`CEP-070 → CEP-074`
and
`CEP-075`

Do not stop merely because the preferred runtime is not already provisioned.

## Autonomous execution rule

Work continuously until the canonical AC/DoD for CEP-070, CEP-074 and CEP-075 are satisfied or a genuinely impossible external dependency remains.

If an environment/tool/runtime prerequisite is missing:

1. first reuse an existing repository-supported isolated environment;
2. otherwise provision the smallest safe isolated non-production environment compatible with the approved profile;
3. install/configure ordinary Development-only tooling or dependencies when necessary and reversible;
4. if one implementation approach fails, diagnose it, repair it or use another contract-equivalent safe approach;
5. create disposable databases, TLS material, protected directories, services and synthetic fixtures as required;
6. execute actual deployment, rollback, backup/restore, isolation, TLS, static/media, secret-loading and acceptance scenarios;
7. fix attributable product/test/configuration defects and continue;
8. regenerate valid evidence rather than stopping for missing historical artifacts;
9. recompute eligibility immediately after every prerequisite closes and continue into the next CEP.

Do **not** return merely because `next_executable_frontier=[]`; work backward through its prerequisites.

Do not ask again for topology, permitted differences, RPO/RTO, EXT-0020, EXT-0021 or EXT-0022 decisions already approved.

## Required sequence

### A. Finish CEP-070

Qualify the approved target against canonical CEP-070 AC/DoD.

If it passes, mark CEP-070 COMPLETE and immediately continue.

### B. Execute CEP-074

Once CEP-070 prerequisite is satisfied:

- perform fresh target-specific recovery qualification;
- prove required integrity, accessibility, tenant isolation and evidence;
- verify approved RPO/RTO/recovery controls within the canonical scope;
- fix failures and repeat affected checks until PASS.

If AC/DoD are satisfied, mark CEP-074 COMPLETE.

### C. Finish CEP-075

On the same approved target:

- perform actual deployment;
- validate exact build/runtime/configuration;
- validate HTTPS/TLS, WSGI, static/media, secrets and protected paths;
- execute rollback to the previous verified build and return to the candidate where required;
- verify migration history/source preservation and tenant/security boundaries;
- fix attributable failures and rerun only affected checks.

If canonical AC/DoD are satisfied, mark CEP-075 COMPLETE.

### D. Reconcile

After execution:

- update existing evidence/reports;
- reconcile Registry;
- reconcile GATE-08 / GATE-11 strictly from actual evidence;
- recompute `next_executable_frontier`.

## Do not stop for

- missing local packages or Development tooling
- disposable environment creation
- test/fixture failures
- path/ACL/TLS/certificate problems
- local service startup/configuration
- evidence-format problems
- ordinary implementation defects
- failed first attempts
- missing reproducible evidence that can be regenerated
- absence of the originally preferred provisioning method when another approved equivalent method is safely available

Fix or work around these within the approved design and continue.

## Hard stop only

Stop only if completion requires one of these and no safe non-production alternative exists:

- unavailable external infrastructure/account/credential that cannot be provisioned locally;
- destructive or irreversible host action;
- Production access/action;
- security/authorization weakening;
- a genuinely new Product/Domain/Accounting/Regulatory decision not covered by existing approvals;
- final Human Sign-off / Production Certification.

Before declaring such a blocker, exhaust all safe contract-equivalent Development alternatives and record what was actually attempted.

## Boundaries

Development / Non-Production only.

No Production deployment or cutover.  
No weakening AC/DoD.  
No fabricated evidence.  
No re-execution of unrelated COMPLETE CEPs.  
No broad audit/full regression unless an attributable failure genuinely requires it.  
No Git commit/push unless separately authorized.

## Completion condition

The preferred result of this session is:

- `CEP-070 COMPLETE`
- `CEP-074 COMPLETE`
- `CEP-075 COMPLETE`

Continue autonomously until that state is reached wherever technically possible.

Final response only after execution:

- CEP-070 AC/DoD/status
- CEP-074 AC/DoD/status
- CEP-075 AC/DoD/status
- environment actually used
- defects resolved
- tests/runtime checks
- Gate changes
- exact remaining blocker, only if genuinely unavoidable
- `next_executable_frontier`

Do not stop for another planning or decision-preparation round.