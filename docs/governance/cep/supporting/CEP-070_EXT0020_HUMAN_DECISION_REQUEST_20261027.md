# EXT-0020 consolidated Human Decision Request

Status: RESOLVED FOR BOUNDED DEVELOPMENT SCOPE by
`CEP-070_EXT0020_HUMAN_APPROVAL_20261027.md`. The original request below is
preserved as historical preparation; only the subsequent explicit response is
approval authority, including its exclusion of production equivalence.
Prepared 2026-10-27 against `main` at
`79f6a1e8b264b09f7a3177d5a9a95b6e49dd7ce4`, preserving the existing uncommitted
prerequisite work. This request changes no policy, Registry state or CEP contract.

## FACT_ALREADY_ESTABLISHED

- The recovery matrix already identifies four governed classes: transactional
  PostgreSQL data; business document/media evidence; deployment/configuration
  recovery metadata; and audit/operational evidence under its governing logging
  policy. No new data-class decision is needed.
- The canonical acceptance requirements are already **integrity, accessibility,
  tenant isolation and required evidence after restore**. Backup evidence,
  executed restore, integrity validation and exception records are required.
  These criteria need no replacement Human definition.
- The available preparation mechanism uses an offline/quiescent PostgreSQL
  custom-format dump and three separate filesystem trees: `document_media`,
  `configuration_metadata`, `audit_operational`. It rejects production mode,
  overlapping paths and overwrites, records failures, and never reports a
  capture as restore verification. It implements no scheduler, retention
  lifecycle, PITR or encryption/key-recovery mechanism.
- Current Development proof used Windows / loopback PostgreSQL 18.6, new isolated
  source/restore databases and synthetic private files. Twenty checks passed:
  525 tables / 7,754 rows, 9,507 constraints, nine sequences, two tenants, three
  immutable document versions, exact Decimal budgets and cross-tenant denials.
  Disposable databases/files were removed; the configured business database was
  not opened. The empty current `test_construction_erp` schema was a read-only
  clone source, never the restore destination.
- The observed dump/capture step was 0.964 seconds and database restore step
  10.262 seconds. Neither is an end-to-end RTO or operational RPO/PITR proof.
  The existing run explicitly says `production_equivalent: false` and
  `cep074_executed: false`.
- Historical P10-S18 accepted **15-minute RPO / 60-minute RTO** as certification
  targets for its old candidate, explicitly excluding a production SLA. They
  are available for explicit carry-forward approval, not current EXT-0020
  defaults. The current canonical recovery matrix still says
  **UNSPECIFIED — DO NOT INVENT** for all six objective/cadence columns.
- Existing `.env` / private libpq or process-environment handling supplies
  Development connection material. Capture references identify the synthetic
  preparation and operator provenance; they do not establish approved protected
  recovery storage, secret/key recovery or accountable ownership.

## HUMAN_APPROVAL_REQUIRED

One response can approve common values for all four classes and list only any
class-specific exceptions. Backup retention here concerns recovery copies; it
does not replace document/audit retention or authorize deletion.

| Field | Minimum decision; supported options and consequences |
| --- | --- |
| RPO | Carry forward **15 minutes**, or specify another maximum data-loss interval. The historical number is a target only; present manual snapshots do not demonstrate continuing coverage. |
| RTO | Carry forward **60 minutes**, or specify another maximum end-to-end recovery interval. The measured database restore step does not prove service recovery within either target. |
| PITR objective/window | **Complete-bundle recovery only; PITR not required**, accepting that intermediate times are unavailable; **or PITR required, window = ___**. Required PITR needs additional implementation and executed proof. |
| Backup frequency | **Every ___ minutes/hours**, requiring automation and evidence against the RPO; **or manual before each bounded drill only**, which provides no ongoing RPO guarantee. Approving a cadence is not evidence that it operates. |
| Retention objective | **___ days**, or an approved policy reference containing the duration, with class exceptions if needed. No approved current number exists. Implementation and proof follow; no purge is authorized by this request. |
| Restore-test frequency | **Every ___ days** (or an explicit approved cadence reference). A fresh governed drill follows when eligible; current evidence proves no recurring cadence. |
| Recovery target/environment | **Use the existing Windows / PostgreSQL 18.6 isolated synthetic setup as the starting qualification target**, with production-equivalence gaps remaining open; **or designate an isolated production-equivalent non-production target reference**. The first reuses working infrastructure; the second may require access/provisioning. Target approval cannot turn missing equivalence evidence into PASS. Codex derives exact disposable names, paths and version records. |
| Restore owner | Proposed: **the approving Human Decision Authority is accountable for this non-production qualification; Codex is its technical executor in this session**. Approve this bounded assignment or designate a different responsible owner/reference. This assigns no production operator. |
| Acceptance authority | Proposed: **the approving Human Decision Authority** for recovery-objective/qualification acceptance. Approve or designate another authority. Codex records objective technical results; no Human Sign-off is inferred. |
| Protected recovery-target / key-recovery references | **Approve local synthetic-only storage on the existing Development host, with Codex establishing and verifying restricted filesystem access and using existing private Development secret sources**, or supply approved non-secret **target storage/access and key/secret-recovery runbook references** for the designated target. Local provenance references will be generated from the approved decision and actual checks. The adapter is unencrypted; the local option establishes no encrypted-backup/key-custody or production storage qualification. Supply references only, never keys/passwords. |

## PRODUCTION_ONLY_LATER

Live production backup/restore/deployment, production storage/provider and real
key-custody qualification, production operator appointments, cutover, Human
Sign-off and final Production Certification remain outside this session. An
objective approval does not certify its implementation or waive CEP-070/074
entry conditions. If the chosen objectives or target require controls that can
be implemented and proved in non-production, that work proceeds before closure.

After the single response, record it as EXT-0020 authority for exactly its
approved scope; complete remaining authorized CEP-070 work and verify AC/DoD;
reconcile gates and execute CEP-074 only when its mandatory required outcome,
approved objectives and qualified environment are sufficient. Routine bounded
Development defects continue under the existing instruction. No broad
regression, production action or Git write is authorized.

**Single decision requested:** approve/edit the ten-row matrix in one response,
supplying the unresolved durations/cadences and any different owner/target or
protected references. An unfilled field remains unapproved.

## Evidence and authority

- Canonical `CEP-070_EXECUTION_PROMPT.md` and `CEP-074_EXECUTION_PROMPT.md`, verified
  against `CEP_PROMPT_MANIFEST.yaml` in this preparation. Hashes respectively:
  `7d3de81556e62ed46c5fe90d1742742c5d0f07caa5dcf4b7d19b549fe2139e82` and
  `7e723b4147d417418f6033b2185a843af92d14e297c649418624d805b34811b9`.
- `CEP_EXECUTION_REGISTRY.yaml`: CEP-070 PARTIAL; CEP-074 NOT_STARTED;
  EXT-0020 blocks CEP-070 production and CEP-074 verification. No eligibility or
  gate change is made by preparing this request.
- `docs/governance/cep/evidence/CEP-069_076_PREREQUISITES_20261026/CANONICAL_SOURCES.json`:
  approved recovery-only archive/member provenance. Specification archive hash
  and the recovery matrix/deployment/operating members reverified in this session.
  Recovery matrix SHA-256:
  `579ac8da6323078508b486410880b9affcee4842aea5e8fb57b2ea2e219a7494`.
- `docs/governance/cep/evidence/CEP-069_076_PREREQUISITES_20261026/ERP_RECOVERY.json`:
  retained current-ERP Development proof; no rerun or new certification.
- `docs/governance/cep/supporting/CEP-070_BACKUP_PREPARATION.md` and
  `scripts/backup_bundle.py`: implemented capture boundaries.
- `docs/architecture/P10_S18_CERTIFICATION_CANDIDATE_MANIFEST.md`, section 5,
  and `docs/architecture/P10_S19_S21_RELEASE_CERTIFICATION_EVIDENCE.md`, S19:
  historical targets and their bounded, production-blocked evidence.
