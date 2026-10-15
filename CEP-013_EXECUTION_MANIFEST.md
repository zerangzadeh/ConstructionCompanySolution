# CEP-013 execution manifest

## Grounding and authorization

- Human authorization: CEP-013 / IMB-0102, Development on local `main`; no dependency addition, upgrade, removal or replacement without canonical authorization.
- Branch: `main`; HEAD: `533fbd52e38dd448973ba4cc618e5faa44b01fec`.
- Before mutation, `git status --short`, `git diff --name-status`, and `git diff --stat` were recorded. Existing CEP-006/009/011 and unrelated changes were preserved.
- Canonical sources checked: consolidated `packages/CEP-013.md`, `prompts/CEP-013_EXECUTION_PROMPT.md`, acceptance coverage register ACC-0610–0615, final master backlog IMB-0102, Product Review Audit 18 remediation RMB-0601–0605, and repository release-certification evidence.
- The package-design draft authorization/branch instructions are superseded by the explicit Human authorization and persistent local-`main` Git policy; its six AC, DoD, scope and no-migration boundary remain governing.

## Actual execution touch set

- Product code, dependencies, lock, CI, models, schema, migrations, settings and tests: **NONE**.
- Documentation/evidence: this manifest, CEP-013 acceptance/evidence/change manifests, completion report, and the CEP-013 roadmap disposition.

## CEP-013-FINDING-001 — BLOCKER-PD / BLOCKER-SPEC

Audit 18 `RMB-0602` explicitly requires a **production-specific dependency set/platform target**, an **approved index/mirror source**, enforced hash acquisition and installation attestation. The committed `requirements-lock.txt` targets CPython 3.11 Windows x86-64 and has SHA-256 `ec2f92a67b0f64ab2045364b6ed9fcef9a17aab5f74d18f8080ee74388525e12`. Neither that lock nor the checked canonical materials approve the production operating platform or acquisition index/mirror. The local virtual environment is not an approved production identity and `pip check` reports unrelated host-leaked `nltk` optional requirements; the earlier isolated clean-runtime proof is limited to the historical Windows target.

The required CI acquisition/SCA/SBOM/provenance gate cannot be made production-specific without choosing those missing parameters. Choosing public PyPI, a private mirror, Windows or Linux, or treating the historical 16-package lock as the production set would infer security policy. No schema or dependency change is needed to resolve the **decision**. A bounded Human decision must identify the production Python/OS/architecture target, the exact direct production and development/test dependency sets, and the approved acquisition index or mirror (including access/trust arrangement). It should identify the accountable security/release owner and disposition path for vulnerability and license findings, including whether any exception is permitted; no exception is presumed.

STOP before product/configuration mutation. The six canonical AC and scoped DoD remain open. No scan result, production readiness, or regression PASS is claimed. Resume only after the decision and repository re-grounding.

## Human approval and resumed actual touch set

The Human Decision Maker approved `CEP-013_SUPPLY_CHAIN_DECISION.md` for Development implementation on local `main`. The missing production acquisition/platform decision is resolved; no application package/version change, migration, production action, Human Sign-off or Git write is authorized. Re-grounding confirmed the same branch/HEAD and dirty predecessor changes. The existing Windows lock remains historical. A read-only cross-platform pip resolution selected the same 16 versions, with eight packages in the Linux runtime set and 16 in the Linux development set; the two native Linux wheel hashes differ from the Windows lock. A read-only OSV batch query returned no IDs for those 16 exact versions at query time, but that alone is not the final SCA/evidence gate.

Resumed intended touch set: `requirements-prod-linux.lock`, `requirements-dev-linux.lock`; `security/supply_chain/` image, license and vulnerability policy/evidence configuration; a focused `scripts/supply_chain.py` validation/acquisition tool and tests; `.github/workflows/` CI gate; `output/cep-013/` focused evidence; CEP-013 manifest/AC/evidence/change/completion reports and the affected `ROADMAP.md` disposition. No application model, schema, migration, view, service, permission or Tenant path is in scope.

## Resumed implementation and current disposition

- Both Linux locks pin the existing package versions, with eight runtime and 16 development packages. The selected Linux Psycopg binary and Ruff wheel hashes differ from the historical Windows lock. Direct runtime requirements and development/test requirements remain separate. No application package was added, removed or version-changed.
- The official Python image tag resolved to pinned OCI index digest `sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89` and `linux/amd64` manifest digest `sha256:8a00ecb83ed9d0864dfd102a1bdb2067fda907ceb30bb86d09da9ee558b19590`; the gate checks both against the registry and fails on drift.
- `scripts/supply_chain.py` validates exact sets and secret/index configuration, acquires both wheelhouses with pip's `--require-hashes` from approved HTTPS PyPI, resolves each offline, verifies every artifact hash/identity, queries OSV for every exact package/version, writes separate CycloneDX SBOMs and license inventories, and records a fail-closed result. No runtime Tenant or permission surface was added. The committed CI workflow pins its actions and build image, performs offline Linux installation and focused/system checks after the gate, signs the wheelhouse archive, and verifies its attestation in a separate job. Dependabot proposes reviewed updates without auto-merge.
- Local focused tests: 9 passed (`output/cep-013/focused-results.xml`); Ruff check/format, Django `check`, migration drift and lock/config check passed. The two-set local gate verified online/offline hash acquisition, image identity, SBOM and OSV queries. OSV returned zero IDs for the 16 exact versions at that timestamp. It then correctly reported **BLOCKED: 16 unreviewed license artifacts** (`output/cep-013/gate/gate-result.json`). The exact inventory is in `CEP-013_LICENSE_DISPOSITION_PACKET.md` and machine-readable evidence.
- No Linux container runtime is available in this checkout. The committed CI has not run because no Git push/remote action is authorized, so its hash-checked Linux installation, signed attestation verification and configuration regression remain UTV. No claim of a production or runtime PASS is made. The current local `pip check` reports host-leaked NLTK optional requirements and is not release-lock evidence.

**CEP-013-FINDING-002 / BLOCKER-PD:** Exact license disposition is required for all 16 selected wheels before the configured build gate can pass. The `psycopg` and `psycopg-binary` artifacts declare LGPL-3.0-only; neither compatibility nor an exception can be inferred by Codex. The Product Owner, with legal review where required, must review the exact wheel text/hash and record each decision. Unknown/rejected artifacts remain blocked. This is an artifact-level decision under the approved policy, not authority to change package versions. CEP-013 is EXECUTION PARTIAL; AC-01 and scoped DoD remain open, and the queue stays stopped.

## Final remediation checkpoint — 2026-10-16

Human authorization removed only `psycopg-binary==3.3.5` from the two Linux hash locks; pure `psycopg==3.3.5` and every other package version/hash remain fixed. The supply-chain exact-set validator and focused test reflect 7 runtime and 15 development wheels. Exact-artifact approvals for those 15 wheels are recorded in `security/supply_chain/license_approvals.json`. The historical Windows lock and `requirements-db.txt` are untouched. The manual pure-runtime verification run 38803595706 remains valid. Local final gate passed; GitHub run 38806288348 passed the dependency gate, offline install and focused checks but failed signed attestation because GitHub does not offer persistence for this user-owned private repository. Provenance verification was skipped. AC-01/scoped DoD remain open; no production or Human Sign-off action.

The final local representative permission-decorator regression passed 2/2. The broader permission-registry check failed 4 tests in unrelated accumulated repository state. A targeted Tenant database regression was attempted with `--reuse-db` but produced no result within a bounded run and was stopped; it is not reported as PASS.

## Final blocker closure — 2026-10-16

The targeted Tenant isolation test `CEP001SecurityTests.test_wrong_tenant_grant_cannot_authorize_membership` passed 1/1 against a fresh disposable PostgreSQL 18.6 cluster after full migrations. The earlier local no-migrations setup error was superseded; no CEP-013 regression was attributable. Canonical `packages/CEP-013.md`, ACC-0610 and IMB-0102 scoped DoD require provenance evidence and verifiable artifact identity, not GitHub-hosted signed attestation. Retained run/artifact, commit, image, lock, SBOM and archive SHA-256 evidence were verified as recorded in `output/cep-013/final-blocker-closure.md`. The GitHub private-repository attestation persistence failure remains a release-stage limitation; no signed attestation or production readiness is claimed. AC-01–AC-06 and scoped development DoD now PASS. CEP-013 and AUTH-BATCH-002 are EXECUTION COMPLETE; no downstream CEP, Human Sign-off or production deployment began.
