# Production reference, release and cutover contract

2026-10-28. Prepared against `main@c9fe1d7e7ed586ef96a2ee453a3490369d25e6a3`.
This is the deployable reference and reviewable input contract. Actual Production
selection/ownership remains subject to the exact external evidence listed in
[the readiness assessment](PRODUCTION_READINESS_ASSESSMENT.md). This document
grants no activation, infrastructure, statutory, migration or deployment authority.

## Qualified reference

Reuse [BONIRA-PE-NP-01](../cep/supporting/SHARED_PRODUCTION_EQUIVALENT_TARGET_PROFILE.md)
and its [Human approval](../cep/supporting/BONIRA-PE-NP-01_HUMAN_APPROVAL_20261027.md).
Debian 12, CPython 3.11.17, Django 5.2.17 and Psycopg 3.3.5, with hash-locked
Linux dependencies and the retained immutable application/base image identities.
Nginx terminates TLS, overwrites forwarded scheme with HTTPS and connects only
to the private Gunicorn synchronous WSGI Unix socket. The app runs unprivileged
with a read-only root, dropped capabilities and no privilege escalation. ASGI
exists but is not the selected network process. No queue or scheduler is activated.

PostgreSQL 18.6 is on the isolated application network, with no published DB port,
SCRAM and `verify-full` trust verification. Separate application/migration
provisioning responsibilities prevent runtime superuser/creator privileges.
The reference uses a shared single-host file cache; a multi-host deployment
requires a separately qualified shared cache. No provider, HA/failover, replica,
capacity or durability guarantee follows from this single-host qualification.

Release-specific static roots are separate from private media, protected
documents, configuration metadata, operational evidence, cache and backup roots.
Static alone is served directly by the proxy. Document delivery requires existing
authentication, tenant membership, permission and version/object checks. Private
paths and environment/key files retain restricted ownership and access modes.
Database/network credentials and certificates remain outside source and evidence.

[production.env.example](production.env.example) covers actual settings inputs.
Replace every placeholder in a private environment-scoped source. Verify hostname,
CA chain, certificate expiry/renewal ownership, secure SMTP delivery, path ACLs,
trusted proxy isolation and both positive and negative TLS connections against
the selected target. No environment dump belongs in evidence. Configure HSTS
subdomains/preload only after confirming the selected host's certificate scope.

## Release and migration procedure

The release owner records source SHA plus the source manifest, dependency locks,
base/application image digests, SBOM/advisory evidence, environment/configuration
revision, migration graph and approved activation authority. Preserve a verified
previous release, static tree and database/config binding before candidate work.
Retain failures separately. A candidate is not ready because its process starts.

1. Verify the exact approved release/configuration and current dependency evidence.
   Verify private secret/key sources and disjoint storage; reject placeholders,
   insecure settings, unexpected source deltas or incompatible migration history.
2. Run the existing `check --deploy --fail-level WARNING`,
   `makemigrations --check --dry-run`, `showmigrations --plan` and
   `migrate --plan` in the intended configured non-production candidate first.
   A production invocation requires separate authorization and the approved
   production connection; no Development database result establishes its state.
3. Capture a complete verified recovery set for all four classes before cutover:
   database, business document/media evidence, reconstructable configuration
   metadata, and governed audit/operational evidence. Secret/key recovery uses a
   separate protected custody contract; do not put credentials in public bundles.
4. Review graph ordering, prechecks and expected catalog/schema effects.
   Six migrations added after the original Linux qualification are covered by
   [current release evidence](evidence/20261028/). Never fake applied migrations.
   Apply only the reviewed plan under the applicable target authorization.
   Fresh bootstrap is currently blocked by the Development-only Legacy Payment
   guards in documents 0012 and billing 0018. A migrated fixture or a switch to
   Development settings is not Production bootstrap evidence. Obtain the explicit
   empty-target/populated-target disposition contract, implement only its approved
   path and qualify it in non-production before claiming deployability from empty.
5. Collect release static assets into a fresh release root; start the candidate
   WSGI service with its private socket and explicit production settings. Confirm
   exact source, Python/dependency, DB version, role, TLS and schema identity.
6. Check HTTPS redirect/HSTS, allowed-host rejection, forged-proxy rejection,
   CSRF, authenticated private delivery, cross-tenant denials and static hashes.
   Run `operational_health`; it checks DB/cache only and correctly reports
   `production_readiness=NOT_VALIDATED`. Record both probes even on failure.
7. Verify release-specific accounting/statutory configuration through the governed
   services below. Record reconciliations, approvals and current source versions.
   Do not introduce a model-save posting path or enable an unapproved package.
8. Route traffic only after explicit target go/no-go authority. Record activation,
   owner, time, version/configuration/migration state and observed outcomes.

Any unexpected migration, failed identity/preservation/reconciliation, TLS failure,
tenant/security failure, missing secret, failed readiness probe or failed protected
delivery stops activation. No time/user-volume/financial-risk threshold is invented.

Rollback first isolates the failed candidate and retains its logs. Restore the
previous verified process/config/static **with its compatible schema binding**.
The qualified current-release scenario switches between the retained pre-migration
synthetic database and a separately migrated clone; it does not downgrade a live
database or claim safety for old code against a new schema. After a real schema
change or new writes, use the reviewed roll-forward/recovery decision; restoration,
reversal or destructive rollback needs its own authorization and reconciliation.
Never silently discard posted/paid/audited history. Re-run the affected checks after
recovery and retain both failed and recovered evidence.

## Tenant and financial bootstrap inputs

Customer records are cutover inputs, not guessed defaults. Use existing forms,
services and explicit tenant context; do not bulk insert around invariants.

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

Statutory `NON_PRODUCTION_QUALIFICATION` envelopes intentionally reject production
settings. DEBUG must remain false. Do not change the scope string, switch Production
to Development, bypass `validate_governance`, or infer an authorized production
recognition/calculation policy. Reuse the adopted review; obtain an explicit
production-applicability/activation contract before a bounded implementation and
qualification of any production envelope. This remains an external policy boundary.

Production data migration is `NOT_YET_SELECTED / CUTOVER_INPUT`: no customer
source/cutoff/import volume or replacement is approved in the available authority.
When selected, use existing Opening Import/reconciliation and domain-specific
tools. Reconcile record counts, exact Decimal totals, source/version links,
tenant/project/site dimensions, finalized history, access and idempotent retries.
No generic import or destructive contract step is authorized here.

## Operations, go/no-go and post-deployment

Reuse EXT-0022 OP-01..04: registered DB/cache and HTTP/delivery failure signals,
correlation IDs, restricted durable log/alert receipts, incident evidence,
independent scoped support grants, actual expiry and revocation. Do not add a
financial event, threshold, severity scheme, SLA or 24x7 staffed rotation.
Approve the actual Production sink, retention/custody and escalation path before
activation. The 30-day diagnostic policy is presently approved only for
non-production; it does not select statutory business/audit retention or disposal.

The Production input record must identify release/deployment, database, recovery,
incident, security, support/revocation, runbook/change and activation authorities.
The existing Human Decision Authority is the established **non-production**
accountable owner; carrying that accountability into Production needs an explicit
appointment/acceptance, not a newly invented person or team.

Before go/no-go: close the external-production-evidence clause in the Gate
evaluation, select the exact release and environment, verify the production
configuration/certificates/credentials/storage and owners, review the recovery
set and compatible rollback/roll-forward decision, select customer data scope and
approve statutory applicability. GATE-11 certification review and GATE-12 Human
Business Sign-off remain separate; deployment/cutover always needs its own authority.

During cutover: confirm maintenance/write coordination; capture the approved
recovery set; apply the reviewed plan; reconcile bootstrap/migrated data; validate
identity, schema, HTTPS, protected routes, tenant/security and governed financial
flows; receive actual log/alert evidence; record an explicit activation decision.
Do not enable Payroll unless its production contract is approved and qualified.

After authorized deployment: retain source/config/migration/activation records,
perform authenticated tenant and reconciliation checks, prove actual operational
receipt/escalation and certificate/secret access, and perform the approved restore
acceptance. Future elapsed retention, recurring backup cadence, due restore tests,
certificate renewal and actual incident response are continuing operational duties;
no elapsed-time evidence, staffing or unattended service is claimed in this session.

## Smallest remaining Human input

One release-linked Production evidence disposition can resolve the Gate's external
clause, with four explicit entries: statutory applicability/production-envelope
policy (EXT-0018); recovery objectives, protection/key custody and responsible
acceptance (EXT-0020); selected actual target/configuration boundaries (EXT-0021);
and operating owners/sink/escalation/retention/access policy (EXT-0022). EXT-0021
must also resolve the proven Development-only Legacy Payment bootstrap boundary;
the narrow recommendation is an explicitly approved empty-target-only path with
zero-population checks and continued rejection of populated unapproved targets.

Recommended starting reference: reuse the qualified single-host Linux design and
existing accountable Human authority; review 15-minute RPO/capture spacing,
60-minute RTO and 30-day retention/test interval as **candidate Production values**.
These are measured/approved non-production values, not an assessment of Production
business loss tolerance. Production PITR, off-host recovery/key custody, certificate
lifecycle and actual operating destination must be selected explicitly. Reuse the
adopted statutory findings and verified conditions, without claiming broader legal
applicability or production activation. Approval of this input does not itself
deploy, activate, issue final certification or issue GATE-12 Human Sign-off.
