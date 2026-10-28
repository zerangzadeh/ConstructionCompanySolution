"""Record objective Gate PASS only after all executed qualification and cleanup pass."""

import hashlib
import json
import re
import textwrap
from datetime import UTC, datetime
from pathlib import Path

import yaml

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[4]
PROD=OUT.parents[1]
PREFIX=OUT.relative_to(ROOT).as_posix()

def load(path):return json.loads(path.read_text('utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
 runtime=OUT/'runtime'
 result={name:load(runtime/(name+'.json')) for name in ['PITR_RESULT','CADENCE_CUSTODY_RESULT','WEB_OPERATIONS_RESULT','FINAL_RELEASE_IDENTITY','CURRENT_AUDIT_RECOVERY']}
 assert all(row['result']=='PASS' for row in result.values())
 assert load(runtime/'FINAL_APP_TESTS.json')['failed']==0
 assert load(runtime/'OPS_ACCESS_TESTS.json')['failed']==0
 assert load(OUT/'SHUTDOWN.json')['result']=='PASS'
 tests=int(re.search(r'Ran (\d+) tests',(runtime/'FINAL_APP_TESTS.txt').read_text('utf-8')).group(1))
 assert tests==52
 pitr=result['PITR_RESULT'];cadence=result['CADENCE_CUSTODY_RESULT'];web=result['WEB_OPERATIONS_RESULT'];identity=result['FINAL_RELEASE_IDENTITY'];audit=result['CURRENT_AUDIT_RECOVERY']
 gate=load(PROD/'GATE11_EVALUATION.json');before=load(OUT/'BEFORE_GATE11_EVALUATION.json')
 assert [row['requirement'] for row in gate['clauses']]==[row['requirement'] for row in before['clauses']]
 descriptions={
 'C1':'GATE10 PASS retained: all 44 approved representative cases/48 mappings. No CEP or UAT reopening.',
 'C2':'Nine required IMB contributors remain completed in their recorded scopes; current Production dispositions and technical deltas supplement retained evidence without rewriting CEPs.',
 'C3':'Current source verified; 52 affected Linux cases, Production envelope activation/calculation, final selected WSGI/HTTPS and actual complete native PITR/four-class recovery evidence available.',
 'C4':'Direct Human Production-scoped EXT0018/0020/0021/0022 dispositions recorded; all reproducible statutory, PITR/custody/cadence, target and operational/access qualifications PASS. Actual provider/endpoint/credential values are authorized cutover inputs.',
 'C5':'No unresolved in-scope readiness/certification blocker remains. All attributable failures repaired and affected checks passed; actual Production events and GATE12 sign-off are separate later actions.'}
 for clause in gate['clauses']:clause.update(status='SATISFIED',evidence=descriptions[clause['id']])
 gate.update(at=datetime.now(UTC).isoformat(),status='PASS',requirements_satisfied=5,requirements_total=5,
  overall_readiness='PRODUCTION_READINESS_GATE_QUALIFIED_NO_ACTUAL_DEPLOYMENT',
  root_boundary='NONE_FOR_GATE11; real activation/cutover and GATE12 Human Business Sign-off remain separate.',
  next_action='Human reviews the qualified release/evidence and supplies separate actual Production cutover or GATE12 EXT0026 sign-off authority when desired. No new EXT0018/0020/0021/0022 disposition is requested.',
  remaining_safe_executable_prerequisites_before_human_policy=[],remaining_blockers=[],
  production_dispositions='docs/governance/production/PRODUCTION_SCOPED_DISPOSITIONS_20261028.md',
  production_contract='docs/governance/production/PRODUCTION_RUNTIME_CONTRACT.json',
  production_scoped_qualification={name:PREFIX+'/runtime/'+name+'.json' for name in result},
  production_statutory_envelopes='docs/governance/production/PRODUCTION_STATUTORY_ENVELOPES.json',
  gate12='NOT_PASSED_EXT0026_HUMAN_BUSINESS_SIGNOFF_NOT_EXECUTED',
  final_human_production_certification='NOT_EXECUTED',production_action=False,git_writes=False)
 gate['qualification']['production_scoped_affected_tests']=tests
 gate['qualification']['final_https_cases']=identity['https_cases']
 gate['qualification']['production_diagnostics_https_cases']=web['https_cases']
 gate['qualification']['pitr_recovery_seconds']=pitr['recovery_seconds']
 gate['qualification']['pitr_rpo_protection_lags_seconds']=cadence['protection_lags_seconds']
 gate['safe_alternatives_exhausted']=['All required bounded technical deltas executed; no prerequisite left unexecuted. Prior qualified controls reused with source/environment limits.']
 (PROD/'GATE11_EVALUATION.json').write_text(json.dumps(gate,indent=2,ensure_ascii=False)+'\n','utf-8')

 old=(OUT/'BEFORE_PRODUCTION_READINESS_ASSESSMENT.md').read_text('utf-8')
 retained=old[old.index('## Required IMB and evidence map'):old.index('## Domain closure and current applicability')]
 report=f'''# Production readiness and GATE-11 executed determination

2026-10-28, Asia/Tehran. **GATE-11 PASS — 5/5 exact canonical conjuncts.**
Candidate main@c9fe1d7e7ed586ef96a2ee453a3490369d25e6a3 plus bounded
uncommitted changes, identified by the [1,611-file manifest](evidence/20261028_production_disposition/SOURCE_FREEZE.json).
The Registry owns live Gate state. No actual Production deployment or Human
Business Sign-off is inferred from this readiness evaluation.

## Canonical requirements and evidence

The exact Gate row, archive/member identities and Production phase dependencies
remain in [the recovered contract](evidence/20261028/SOURCE_CONTRACT.json) and
[external phase rows](evidence/20261028/EXTERNAL_PHASE_ROWS.json). The canonical
Pass Condition and dependency graph are unchanged.

| Clause | Exact canonical requirement | Result | Evidence |
| --- | --- | --- | --- |
'''
 for clause in gate['clauses']:
  report+=f"| {clause['id']} | {clause['requirement']} | PASS | {clause['evidence']} |\n"
 report+='''
The canonical evidence field says “Activated official statutory package where
applicable”; the same row says UTV lasts until production-equivalent evidence
exists and unlocks a future production release decision. Here the explicitly
approved Production envelope is activated and calculated through real services
in an isolated synthetic database. The row does not require customer Production
activation before this Gate. GATE-12/EXT0026 separately requires explicit Human
Business Sign-off. No actual external Production event is substituted or claimed.

'''+retained+f'''
## Production dispositions and technical closure

[The direct Human instruction](PRODUCTION_SCOPED_DISPOSITIONS_20261028.md) supplies
all four Production-scoped inputs. [The runtime contract](PRODUCTION_RUNTIME_CONTRACT.json)
records the exact selected objectives, topology, responsibility and custody rules.
Earlier non-production approvals retain their original scope and are supplemented,
not relabelled. All 79 completed CEPs and other existing Gate records remain unchanged.

| Dependency | Approved disposition | Executed qualification |
| --- | --- | --- |
| EXT-0018 | Exactly the adopted ordinary population/profile, official versioned sources, CUMULATIVE_YTD/openings, explicit classifications/insurance mappings, rounding and source-specific supersession | Four frozen Production parameter versions bound to Human authority; all validate; synthetic tax/insurance source import, activation, calculation and immutable traceability pass. Unsupported parameters, sources, population, scope and insecure settings fail closed. No real Payroll activation. |
| EXT-0020 | RPO 900s, RTO 3600s, capture <=900s, retention >=30 days, restore acceptance <=30 days; mandatory native WAL/PITR; all four classes; protected separated encrypted backup/key custody | Native pg_basebackup/pg_verifybackup, continuous WAL, target recovery with source stopped; complete {pitr['tables']}-table/{pitr['rows']}-row state including constraint/sequence hashes; {pitr['files_equal']} files across three file classes restored. RTO {pitr['recovery_seconds']:.3f}s. Two actual OS-timer captures {cadence['observed_intervals_seconds'][0]:.3f}s apart, protection lags {cadence['protection_lags_seconds'][0]:.3f}/{cadence['protection_lags_seconds'][1]:.3f}s. Missing WAL, corruption, wrong key and archive/key access negatives pass. |
| EXT-0021 | Current Debian12/CPython3.11.17/Django5.2.17/Psycopg3.3.5/PostgreSQL18.6 design, SCRAM/verify-full, Nginx HTTPS, sync Gunicorn/private socket/unprivileged process and protected single-host persistence/cache | {web['https_cases']} actual HTTPS cases across worker restart plus {identity['https_cases']} final source-identity-confirmed cases; release static/private delivery, authentication, CSRF, tenant denial, TLS/host/proxy and readiness probes pass. Existing compatible rollback retained. No HA/provider/capacity claim. |
| EXT-0022 | Human Decision Authority accepts all named operating/release/incident/security/recovery/access/runbook/activation roles; OP01..04, restricted durable qualification sink, 30-day diagnostics and held incident/release/recovery evidence | Real correlated authentication/authorization/document delivery, failed bootstrap/migration/readiness and backup/recovery receipts; response survives sink failure; records survive process restart. Existing named/scoped independent grants, expiry/revocation and audit pass. New current audit capture independently restores {audit['files_equal']} files, including {audit['actual_alert_receipts_covered']} actual alert/HTTP receipts and release/recovery metadata. |

Final affected Linux tests **{tests}/{tests} PASS**, deploy/drift checks PASS, Ruff
checks/format PASS. [Runtime outputs](evidence/20261028_production_disposition/runtime/)
and [completion report](evidence/20261028_production_disposition/COMPLETION_REPORT.md)
identify commands, attempts, source, controls and cleanup. Native OpenSSL CMS
AES-256-GCM supplies encryption/authentication; no custom cipher or new Python
dependency was added. Existing locks, dated supply-chain/SBOM/advisory evidence
and earlier 070/074/075/076/077 controls are retained with their original limits;
native OpenSSL package/binary integrity is additionally verified. No fresh advisory
scan, cold rebuild, broad regression or exhaustive security certification is claimed.

## Repairs and limits

The OpenSSL wrapper now passes the recipient explicitly, fixing an actual command
ordering defect. Qualification setup repairs cover initialization readiness,
the backup role's explicit TLS/SCRAM replication rule, a script-only directory's
execute access, the system Python tar API, and a test-client-only HTTPS redirect.
An inherited deployment driver read its head from an old source directory;
the final mounted source/manifest and HTTPS run now prove the actual candidate.
All failures and corrections are retained; none is waived as a pass.

Legacy Payment's completed retirement decision and qualification remain unchanged.
Financial calculations, domain ownership, tenant authorization, model/schema and
completed CEP contracts were not broadened. Statutory authorization is limited to
the exact reviewed parameter digests; future source/value changes need their own
review. Global registry architecture assertions previously attributed in fiscal
qualification remain outside this change; no global full-suite PASS is claimed.

The backup boundary is a separate protected filesystem in the isolated guest,
accepted by the Human instruction for qualification; it is not off-host disaster
or provider durability evidence. Synthetic/quiesced files and the measured
workload prove the executed objectives only. The live source is stopped for replay.
Future 30-day retention/cadence/restore operation is a continuing duty, not fabricated
elapsed evidence. No historical/source records or retained failed evidence were purged.

## Actual cutover, GATE-12 and continuing duties

The remaining real hostname/IP/provider/DNS/certificate identities/storage paths,
enterprise alert destination and real environment secrets are cutover bindings
under the approved design, not new GATE-11 blockers. The release owner must verify
those exact bindings and recovery set, distinct real keys/certificates, renewal
ownership, customer organization/roles/fiscal/GL/opening inputs, current statutory
applicability and compatible rollback/write coordination before separately
authorized deployment/migration/activation. See the [cutover procedure](PRODUCTION_REFERENCE_AND_CUTOVER.md).

Post-deployment duties include actual <=15-minute capture, >=30-day diagnostic/
backup retention, <=30-day restore acceptance, alerts/escalation/access review,
certificate renewal and governed audit retention. Physical disposal needs separate
authority. GATE-12 remains **NOT_PASSED: EXT0026 Human Business Sign-off NOT EXECUTED**.
Final Human certification is not issued. No actual Production deployment, database
mutation, Payroll activation, DNS/firewall/provider change or Git write occurred.
Owned services, timer and guest are stopped; private synthetic resources remain retained.
'''
 (PROD/'PRODUCTION_READINESS_ASSESSMENT.md').write_text(report,'utf-8')

 oldref=(OUT/'BEFORE_PRODUCTION_REFERENCE_AND_CUTOVER.md').read_text('utf-8')
 table=oldref[oldref.index('| Input |'):oldref.index('\n\nStatutory `NON_PRODUCTION_QUALIFICATION`')]
 reference=f'''# Approved Production reference and actual cutover procedure

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

{table}

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
'''
 (PROD/'PRODUCTION_REFERENCE_AND_CUTOVER.md').write_text(reference,'utf-8')

 registry_path=ROOT/'CEP_EXECUTION_REGISTRY.yaml';original=registry_path.read_text('utf-8');registry=yaml.safe_load(original)
 baseline=yaml.safe_load((OUT/'BEFORE_REGISTRY.yaml').read_text('utf-8'))
 assert registry['ceps']==baseline['ceps']
 live=registry['gates']['GATE-11']
 live.update(status='PASS',source='CANONICAL_GATE11_PASS_AFTER_PRODUCTION_SCOPED_DISPOSITIONS_AND_QUALIFICATION',evaluated_at='2026-10-28',requirements_satisfied=5,requirements_total=5,
  note='5/5 exact canonical conjuncts satisfied. Direct Human Production-scoped EXT0018/0020/0021/0022 dispositions and actual envelope/PITR/custody/cadence/target/operations/access qualification PASS. Completed CEPs and prior evidence scopes retained. No actual Production action, final Human certification, GATE12 sign-off or Git write.',
  production_dispositions=gate['production_dispositions'],production_scoped_qualification=gate['production_scoped_qualification'],
  exact_clauses={clause['id']:'PASS' for clause in gate['clauses']},remaining_blocker=None,
  production_action=False,final_human_production_certification='NOT_EXECUTED',gate12_human_signoff='NOT_EXECUTED')
 live['history'].append({'date':'2026-10-28','status':'PASS','reason':'Direct Human Production dispositions close policy inputs; 52 affected Linux tests, Production envelope synthetic activation/calculation, verified native complete WAL/PITR and four-class recovery, separated encrypted custody, real timer cadence, final source/HTTPS and durable operational/access evidence PASS. Exact C1-C5 satisfied; no actual external Production event is required by this Gate. No CEP reopened or Production/Git/Human Sign-off action.','evidence':PREFIX+'/COMPLETION_REPORT.md'})
 replacement=textwrap.indent(yaml.safe_dump({'GATE-11':live},sort_keys=False,allow_unicode=True,width=140),'  ')
 updated,matches=re.subn(r'(?ms)^  GATE-11:\n.*?(?=^[a-zA-Z_][a-zA-Z_0-9]*:)',lambda _:replacement,original);assert matches==1
 updated=updated.replace('pending_checkpoint_scope: PRODUCTION_READINESS_AND_RETIRED_LEGACY_DATA_20261028_UNCOMMITTED','pending_checkpoint_scope: PRODUCTION_READINESS_AND_PRODUCTION_SCOPED_QUALIFICATION_20261028_UNCOMMITTED')
 after=yaml.safe_load(updated)
 assert after['ceps']==baseline['ceps']
 assert all(after['gates'][key]==value for key,value in baseline['gates'].items() if key!='GATE-11')
 registry_path.write_text(updated,'utf-8')
 print('GATE11 PASS: exact C1-C5 5/5; all 86 CEP records and other Gate records unchanged')

if __name__=='__main__':main()
