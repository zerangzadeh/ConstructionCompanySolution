# CEP-070 non-production backup preparation

The standalone `scripts/backup_bundle.py` adapter captures PostgreSQL custom-format
dump bytes and three explicit filesystem trees. It does not connect through the
ERP, grant tenant permissions, restore a database, schedule jobs, manage retention,
select a production topology or certify recovery readiness. Existing PostgreSQL
and Python libraries provide capture; no dependency was added.

Use only an authorized operator's isolated, quiescent non-production inputs. Keep
all bundle bytes and configuration in a directory whose existing OS permissions
restrict access to authorized operators. The bundle is **not encrypted** by this
adapter. Production storage, encryption/key recovery, coordinated snapshots,
operating access and other environment-specific controls remain unqualified.
Configuration sources may be recovery metadata or references to approved secret
recovery material; do not copy credentials into repository evidence.

An operator-supplied JSON plan has these fields:

```json
{
  "environment": "non-production",
  "source_revision": "<exact 40-character source SHA>",
  "operator_reference": "<non-secret operator evidence reference>",
  "recovery_reference": "<non-secret recovery-plan reference>",
  "consistency_reference": "<non-secret isolated/quiescent-input reference>",
  "database_service": "<named libpq service>",
  "pg_dump": "<absolute approved pg_dump executable>",
  "roots": {
    "document_media": "<absolute local fixture root>",
    "configuration_metadata": "<absolute local fixture root>",
    "audit_operational": "<absolute local fixture root>"
  },
  "destination": "<new absolute bundle directory under a protected parent>",
  "command_timeout_seconds": "<explicit positive integer tool timeout>"
}
```

The placeholders require real input; this is not a runnable configuration. The
tool timeout is an execution bound, never an RPO/RTO/SLA or backup-frequency value.
libpq service/password files or process environment supply connection secrets;
inline credential-bearing connection strings are rejected. References establish
provenance only and are not proof of Human approval or cross-store consistency.

From the repository root run `python scripts/backup_bundle.py <private-plan.json>`.
The adapter refuses production mode, missing source classes, relative/overlapping
trees, links/reparse points and existing destinations. It captures files using
standard copying and verifies source/copy inventories. It never follows a supported
source link deliberately. Inputs must remain offline and controlled; this is not
an adversarial concurrent filesystem snapshot engine.

Inspect restricted `capture.json`. Zero tool exit plus non-empty dump bytes and
matching file inventories produce `CAPTURED_NOT_RESTORE_VERIFIED`, never PASS or
production readiness. Failure retains `FAILED` evidence and any partial bytes for
authorized investigation; do not treat that directory as a completed backup. A
retry uses a new destination. The adapter does not delete earlier captures.
Preflight rejection happens before bundle creation; the calling operator retains
the rejected invocation in the applicable restricted operational evidence path.

Inventory manifests inside the restricted bundle contain relative file names and
hashes. Published evidence contains only hashes/counts, source revision and
non-secret references. Raw PostgreSQL output/errors are suppressed. If evidence
cannot be persisted, the invocation fails; there is no success claim.

The CEP's `output/cep-070/run_rehearsal.py` creates two unique disposable databases
on the existing loopback PostgreSQL server. It captures/restores two synthetic
rows and compares synthetic files, then drops only those newly created databases.
It never opens the configured application database or runs Django migrations.
This proves basic adapter/format interoperability and fixture fidelity only:
actual ERP restore, tenant access after restore, operational logs, secrets/key
recovery, cross-store coherence, RPO/RTO/PITR and retention remain unverified.

`CEP-070-FINDING-001 / BLOCKER-EXTERNAL`: SPEC-005 and EXT-0020 retain unspecified
recovery objectives and unassigned responsibility. Supply approved objectives,
responsible owners and environment-specific backup/restore/access/integrity
evidence before certification review. Any production action and final Production
Certification still need their separate exact Human authority. GATE-11 is not PASS.

The 2026-10-27 `scripts/cep070_erp_recovery_proof.py` additionally rehearses current
ERP document/project recovery in two new disposable loopback databases and private
temporary file trees. It uses the existing Development credentials against only
the administrative database and disposable fixtures. Default provisioning applies
existing migrations to an empty fixture; an optional
`BONIRA_CEP070_TEMPLATE_DATABASE` names an empty `test_` database with no users or
organizations and the exact current migration graph. The template is read/cloned,
never migrated, flushed, disconnected or otherwise modified. A concurrent template
connection may prevent cloning; do not terminate another session to force success.
The restored database is always newly created. This is Development preparation,
not CEP-074 execution or qualification of a protected production-equivalent target.

## Approved EXT-0020 Development controls — 2026-10-27

The subsequent Human approval and exact Development policy are in CEP-070_EXT0020_HUMAN_APPROVAL_20261027.md and CEP-070_DEVELOPMENT_RECOVERY_POLICY.json. The original capture adapter remains unchanged; cep070_recovery_controls.py implements the approved supervised cadence, private Windows storage, minimum-retention receipts and due-test/failure controls. See CEP-070_DEVELOPMENT_RECOVERY_RUNBOOK.md for execution and limits. Fresh runtime results are in evidence/CEP-070_EXT0020_DEVELOPMENT_20261027/RESULT.json. Earlier unspecified Development-policy statements above are historical, superseded only within this bounded approval. Production objectives/equivalence/storage/key qualification remain unapproved/unproved.
