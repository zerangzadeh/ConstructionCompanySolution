# Approved Production reference and actual cutover procedure

2026-10-28. [Production-scoped Human dispositions](PRODUCTION_SCOPED_DISPOSITIONS_20261028.md)
and [runtime contract](PRODUCTION_RUNTIME_CONTRACT.json) select the initial design.
[GATE-11 PASS](GATE11_EVALUATION.json) records executed readiness qualification.
Actual Production deployment/cutover and GATE-12 Human Business Sign-off remain separate.

## Qualified design and bindings

Debian12, CPython3.11.17, Django5.2.17, Psycopg3.3.5 and PostgreSQL18.6;
single application host plus isolated PostgreSQL service/network. SCRAM and
verify-full CA/hostname verification; no published DB port. Nginx HTTPS replaces
forwarded scheme and talks only to the sync Gunicorn private Unix socket.
The app is unprivileged with read-only root, dropped capabilities and no privilege
escalation. ASGI exists but is not the chosen process; no application queue is activated.
Release-specific public static roots are disjoint from protected documents/media,
configuration, audit/operations, cache, backup and key custody. The shared file
cache is single-host only. No HA, replica, multi-host or provider guarantee follows.

Use [production.env.example](production.env.example); supply every real value from
a private environment-scoped source. The explicit Gunicorn diagnostics binding is
`--config python:config.gunicorn_production`, with BONIRA_OPERATIONS_SINK pointing
to an existing owner-only directory in the governed audit/operational recovery class
and BONIRA_OPERATIONS_ENVIRONMENT=production. Qualification uses the distinct
production-equivalent-qualification value. No credential values belong in evidence.
Missing/insecure sink bindings reject worker startup. The diagnostic health command
retains production_readiness=NOT_VALIDATED; Gate authority is not a health endpoint.

The Human Decision Authority accepts the eight named operating/release/incident/
security/recovery/access/runbook/activation responsibilities. Reuse OP01..04 and
the approved technical signal catalogue; no business KPI/SLA/financial alert is added.
Bind the enterprise destination to these fixed sanitized signals before real
activation, verify receipts, and preserve named/scoped grants, independent approval,
least privilege, expiry/revocation and usage audit. Diagnostics retain at least
30 days; release/incident/recovery evidence remains held until governed disposal.
Accounting/statutory/business audit retention is unchanged.

## Qualified recovery contract

RPO 15 minutes; RTO 60 minutes; capture spacing <=15 minutes; backup retention
>=30 days; restore acceptance at least every30 days. Cover PostgreSQL plus documents/
media, configuration metadata and governed audit/operational evidence together.
WAL/PITR is mandatory. Logical pg_dump alone is not PITR.

Reuse the executed [native base/WAL helper](evidence/20261028_production_disposition/guest_pitr.py)
and [bounded capture executor](evidence/20261028_production_disposition/guest_capture_once.py)
with approved target bindings. `pg_basebackup -Fp -X stream` uses a distinct
replication-only SCRAM credential over verify-full; verify the native manifest with
pg_verifybackup. Configure wal_level=replica, archive_mode=on, archive_timeout=60s
and an archive command that reports success only after a complete immutable segment
copy (or exact same existing bytes). The backup role needs an explicit hostssl
replication rule restricted to the service network. Retain the verified base and
continuous WAL chain for the complete required recovery window; never independently
purge a base or WAL segment needed by retained points.

The qualified OS timer runs at60s, comfortably within the900s contract under its
measured workload. [Cadence/control execution](evidence/20261028_production_disposition/guest_cadence.py)
uses an exclusive capture lock, preserves failure receipts, and stops the owned
timer after qualification. Real installation/bindings are an authorized deployment
operation, not a service claimed to remain running here. Alert on backup/recovery
failure and verify protected-capture lag; a future due date is not proof of a run.

Keep encrypted copies outside active DB/app storage, in restricted protected
storage. [OpenSSL CMS adapter](../../../scripts/production_recovery.py) uses
AES-256-GCM and public recipient certificates, authenticates before publishing
decrypted output, never overwrites accepted outputs, and enforces private disjoint
boundaries. Private recovery keys/credentials remain in separate owner-restricted
custody, absent from backup payload/evidence. App and backup-writer access denials,
corruption/wrong-key refusal and missing-WAL failure are qualified. The accepted
qualification boundary is a second filesystem; choose actual provider/path and
custody bindings before activation. It does not claim off-host disaster durability.

For consistent four-class captures, coordinate writes or capture governed immutable
file versions and their database cutoff. Include the operational sink and release/
incident/recovery receipts in the audit class. Preserve cutoff/version/hash metadata.
Recover base plus continuous WAL into a fresh private workspace with recovery.signal,
restore_command and the reviewed target. The real drill stops the source and proves
a post-base commit included/a later commit excluded, then all rows/constraints/
sequences/files equal. Never downgrade a live database or expose unverified plaintext.
Maintain a compatible process/schema rollback binding and a separate roll-forward/
recovery decision for changed schema/new writes; never discard finalized history.

Native guidance: [PostgreSQL18 PITR](https://www.postgresql.org/docs/18/continuous-archiving.html),
[pg_basebackup](https://www.postgresql.org/docs/18/app-pgbasebackup.html),
[OpenSSL CMS](https://docs.openssl.org/3.0/man1/openssl-cms/).

## Release and customer inputs

1. Select the approved release/source manifest, locks, native/image digests,
   environment revision, migration graph and separately authorized target action.
   Verify private secrets/TLS renewal custody, disjoint storage, sink receipt and
   current vulnerability/source applicability. Qualification keys are not Production keys.
2. Capture/verify the complete recovery set and prior compatible process/config/
   static/schema binding. Run check --deploy --fail-level WARNING, makemigrations
   --check --dry-run, showmigrations --plan and migrate --plan on the intended
   configured connection. Review the exact plan; never fake migration history.
3. Under separate actual Production authority, coordinate writes and execute only
   that plan. The completed legacy-retirement decision remains unchanged; population
   is not an eligibility condition and physical disposal remains unauthorized.
4. Collect release static and start the chosen Gunicorn/Nginx service with explicit
   Production settings/private bindings. Verify actual source/schema/role/TLS identity,
   authenticated delivery, CSRF, tenant denials, Host/proxy/TLS negatives and real
   operational receipts. Failed readiness or security/integrity/reconciliation stops activation.
5. Activate only the approved statutory package applicable to the actual reviewed
   population/period under cutover authority. The Production envelope has a distinct
   reviewed scope/digest; non-production envelopes still reject Production settings.
   Unsupported sources/values/populations fail closed. Never change DEBUG or silently
   reinterpret finalized Payroll, GL, Treasury, AP/AR or Project Cost history.
6. Reconcile customer bootstrap/opening sources, release/configuration/migration
   state and actual access. Receive a recorded go/no-go decision before traffic/cutover.

| Input | Existing authority and validation | Required before affected use |
| --- | --- | --- |
| Organization/company | `apps.organizations.services.create_organization_with_owner`; atomic tenant and owner membership; organization profile/settings forms | Approved company identity, timezone, currency, fiscal and numbering settings |
| Users/roles | Organization account/invitation and membership-role services; registered business permissions and object scope | Named active memberships, explicit role assignments and independent maker/checker actors; platform role grants no tenant authority |
| Fiscal year/periods | `apps.accounting.forms` and accounting services | Approved date ranges, active periods and tenant-local fiscal context |
| Chart of accounts/GL | Account forms/services and existing posting registry | Approved active leaf accounts, explicit recognition mappings, currency/precision and rounding policy |
| Initial balances/data take-on | Existing Opening Import proposal/independent acceptance and reconciliation services | Approved source cutoff, source record/version, opening debit=credit, tenant/dimension reconciliation and independent acceptance |
| Year closing/roll-forward | `closing_forms.py`, `closing_services.py`; configuration versions and append-only executions | Distinct active equity summary/retained-earnings accounts per source year, successor year, zero summary balance, closed periods, frozen snapshots and independent approvals |
| Projects/sites/masters | Existing project/site/master services | Tenant-valid relationships; optional structures only where actually selected |
| Payroll statutory | Source-package services, `statutory_governance.py`, reviewed sources and effective-dated policy versions | Reviewed actual population/profile, mapped components, source-specific effective dates/supersession, explicit opening/YTD/external facts and approved activation scope |
| Integrations | Existing registered producer contracts and configuration | Keep unselected/unsupported integrations closed; no inferred accounting/cash/project-cost effect |
| Numbering/sequences | Existing domain numbering and database uniqueness/transaction controls | Organization-owned configuration and validated next numbers; never rewrite approved history |

No real customer import/source/cutoff was selected or executed here. Use existing
Opening Import/independent acceptance/reconciliation and domain services when
selected, with exact Decimal totals, source/version/cutoff and tenant/project/site
dimensions; do not build a generic financial importer or infer openings.

## Remaining actual actions

Hostname/IP/provider/DNS/certificate identity, concrete paths, real distinct secrets,
renewal ownership and the enterprise destination are cutover bindings under the
approved architecture. Verify them before separately authorized Production action.
No additional EXT0018/0020/0021/0022 disposition is requested for GATE-11.
After activation continue capture/restore/retention, receipt/escalation, certificate
renewal, access review and financial reconciliation duties. Disposal requires
separate retention/audit authority. GATE-12/EXT0026 Human Business Sign-off and
final Human certification remain NOT EXECUTED. No Git checkpoint was performed.
