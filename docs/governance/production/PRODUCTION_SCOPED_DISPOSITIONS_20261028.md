Repository: `E:\Construction_Company_Solution`
Branch: `main`

## Current state

Known authoritative state:

- 79/79 CEP COMPLETE.
- Legacy Payment retirement decision implemented and qualified.
- Legacy Payment population is no longer a Production bootstrap condition.
- GATE-11 = NOT_PASSED, exactly 3/5 canonical conditions satisfied.
- C1, C2, C3 are satisfied.
- Remaining:
  - C4 = required Production-scoped external evidence.
  - C5 = no unresolved blocker.
- No actual Production deployment/cutover is authorized by this instruction.
- GATE-12 Human Business Sign-off remains separate.

Do not revisit Legacy Payment.
Do not reopen completed CEPs.
Do not perform another readiness/planning round.

# HUMAN PRODUCTION-SCOPED DISPOSITION

The Human Decision Authority now supplies the required Production-scoped dispositions for EXT-0018, EXT-0020, EXT-0021 and EXT-0022.

These are authoritative Production policy/design selections for GATE-11 qualification.

They do NOT themselves authorize actual Production deployment, cutover or GATE-12 sign-off.

---

# EXT-0018 — Production Payroll applicability

Approve the adopted and qualified EXT-0018 statutory mapping for Production use **within exactly the population and applicability scope already reviewed**.

Production contract:

- governed official versioned sources;
- effective-dated statutory policies;
- `CUMULATIVE_YTD` tax calculation;
- governed opening/prior-YTD values;
- explicit tax component classifications;
- explicit insurance classes/component mappings;
- adopted rounding policy where statute is silent;
- explicit retroactivity/supersession semantics;
- fail-closed unsupported populations/components/sources;
- immutable source/review/runtime traceability.

The existing Human-adopted expert review is the Production applicability basis.

No broader population or legal interpretation is authorized.

Codex may construct and qualify the Production-scoped statutory envelope.

Actual Production activation remains a cutover action.

---

# EXT-0020 — Production recovery disposition

Approve:

- Production RPO: **15 minutes**
- Production RTO: **60 minutes**
- Backup/capture interval: **maximum 15 minutes**
- Backup retention: **minimum 30 days**
- Restore acceptance test: **at least every 30 days**
- Recovery coverage: all four governed classes:
  - PostgreSQL
  - business documents/media
  - reconstructable configuration metadata
  - governed audit/operational evidence

## PITR

Production PostgreSQL must support:

`PITR / WAL-based point-in-time recovery`

Qualify it in production-equivalent non-production.

## Backup custody

Production contract requires:

- backup copy outside the active database/application storage boundary;
- access-restricted protected storage;
- backup encryption/protection;
- integrity verification;
- credential/key custody separate from backup payload;
- no secret/key contents in evidence;
- independently testable restore.

For GATE-11 qualification, an isolated second protected storage boundary is acceptable.

Actual Production provider/path is a cutover configuration input.

## Authority

Human Decision Authority is accountable for recovery objectives and acceptance.

---

# EXT-0021 — Production target/configuration selection

Approve the current qualified BONIRA Linux design as the initial Production reference:

- Debian 12
- CPython 3.11.17
- Django 5.2.17
- Psycopg 3.3.5
- PostgreSQL 18.6
- SCRAM
- PostgreSQL TLS `verify-full`
- Nginx HTTPS termination
- Gunicorn synchronous WSGI
- private Gunicorn Unix socket
- unprivileged application process
- explicit Production settings
- protected persistent storage
- environment-scoped private secrets
- release-specific static roots
- single-host shared file cache

Approved initial topology:

`single application host/reference boundary + isolated PostgreSQL service/network boundary`

No HA, replica, multi-host application tier, multi-host cache or provider-specific guarantee is claimed.

Actual Production:

- hostname/IP;
- infrastructure provider;
- DNS;
- certificate identity;
- concrete storage paths;

are cutover configuration values and do not change the approved architecture.

Legacy Payment retirement decision remains authoritative.

No zero-population or Legacy Payment readiness condition may be reintroduced.

---

# EXT-0022 — Production operations disposition

Human Decision Authority accepts Production accountability for:

- Release/Deployment Authority
- Operations Authority
- Incident/Escalation Authority
- Security Authority
- Backup/Recovery Acceptance Authority
- Support/Access-Revocation Authority
- Runbook/Change Authority
- Activation/Go-No-Go Authority

Technical tasks may be delegated to authorized operators without creating accounting/business authority.

Reuse the approved OP-01..04 operating/runbook contracts.

## Production signals

Approve the established technical signal catalogue for Production.

Required classes include:

- application availability/errors;
- DB/cache health;
- authentication/authorization/security failures;
- protected-document delivery failures;
- migration/deployment failures;
- backup/recovery failures;
- operational health/readiness;
- correlation/trace identifiers.

Do not invent business KPIs, SLA thresholds or financial alerts.

## Alert destination

For GATE-11 qualification:

approve a **restricted durable production-equivalent alert/evidence sink** with actual receipt verification.

For actual Production deployment, the organization-selected operational destination/SIEM/mail/monitoring endpoint will replace or bind to this sink without redefining application signal semantics.

Absence of the final enterprise endpoint must not block pre-deployment GATE-11 qualification.

## Retention

Production policy:

- operational diagnostic logs/alerts: minimum **30 days**;
- incident/release/deployment/recovery evidence: retain under governance/audit lifecycle until separately approved disposal;
- statutory/accounting/business audit records retain their existing domain retention rules.

The 30-day diagnostic policy does not authorize deletion of accounting/statutory/audit records.

## Access

Production support and emergency access:

- explicit named/scoped grants only;
- least privilege;
- expiry/revocation;
- no implicit Platform Admin business authority;
- traceable approval and usage evidence.

---

# Production secrets / TLS custody

Approve:

- no secrets in source/Git;
- no secrets in evidence artifacts;
- environment-scoped Production secret source;
- least-privilege service credentials;
- separate database/app/backup credentials;
- TLS private-key restricted custody;
- Production certificates/keys distinct from qualification credentials;
- named certificate renewal/ownership before actual activation.

Synthetic secrets/certificates may be used for GATE-11 qualification.

Actual values remain cutover inputs.

---

# GATE-11 EXECUTION AUTHORITY

These four Production-scoped dispositions satisfy the Human/external policy input requested by the readiness contract.

Do not merely record them and stop.

Immediately:

1. record the Production-scoped EXT-0018/0020/0021/0022 dispositions;
2. recompute C4;
3. implement any technical delta necessary to represent these policies;
4. execute all reproducible production-equivalent qualification required by C4;
5. qualify PITR/WAL recovery;
6. qualify protected separated backup/key-custody mechanics without exposing secrets;
7. qualify Production statutory envelope without actual Production activation;
8. qualify selected Production deployment/configuration contract;
9. qualify Production operational sink/receipt/access contracts;
10. repair attributable defects and repeat affected checks;
11. update canonical readiness/GATE evidence;
12. recompute C4 and C5;
13. continue until GATE-11 reaches its truthful canonical terminal state.

## Target

Expected result:

`C1 PASS`
`C2 PASS`
`C3 PASS`
`C4 PASS`
`C5 PASS`

therefore:

`GATE-11 = PASS`

---

# Anti-stop rules

Do not stop for:

- configuration implementation;
- Development/non-production provisioning;
- PITR setup;
- protected backup storage;
- alert sink creation;
- TLS certificates;
- synthetic secrets;
- test/fixture defects;
- evidence generation;
- statutory envelope implementation;
- migration/readiness validation;
- missing final provider hostname/IP/DNS where the architecture is already selected.

Resolve these and continue.

Do not request EXT-0018/0020/0021/0022 again.

---

# Hard stop only

Stop only if the canonical GATE-11 text expressly requires an **actual external Production event** that cannot truthfully be replaced by approved Production policy plus production-equivalent qualification.

If so:

- quote the exact canonical clause;
- identify the exact event;
- prove why it belongs to GATE-11 rather than GATE-12/cutover;
- complete every other requirement first.

A generic statement such as:

`Production evidence missing`

is not sufficient.

---

# Boundaries

No actual Production deployment.
No real Production DB mutation.
No customer cutover.
No real Production Payroll activation.
No Production DNS/firewall/provider modification.
No GATE-12 Human Business Sign-off.
No Git commit/push unless separately authorized.

---

# Final output

Return only:

- C1–C5 result individually;
- GATE-11 final status;
- Production dispositions recorded;
- PITR/recovery qualification;
- statutory Production-envelope result;
- target/deployment qualification;
- operations/alert/access qualification;
- defects fixed;
- remaining actual cutover/Production actions;
- GATE-12 status;
- exact canonical blocker only if GATE-11 is still not PASS;
- Git write status.

Do not return for another disposition/planning round.