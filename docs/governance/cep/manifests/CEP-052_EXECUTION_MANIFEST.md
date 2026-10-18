# CEP-052 Execution Manifest

## Grounding and actual execution touch set â€” before product mutation

2026-10-18: clean `main`, HEAD/`origin/main`/remote
`f37310fd5c3e6568e959849867427f96d5fd95cd`, after the authorized CEP-041
checkpoint. Reconcile its direct Git integration separately from its baseline.
Registry: 33 COMPLETE; CEP-025 COMPLETE with operational immutable YTD foundation;
GATE-02 PASS. Recomputed verified build frontier:
CEP-022/036/052/053/054/055/056. CEP-052 is the isolated backend candidate selected
for continuation. Hash `eaf9362eb18ab80b97f867b2c8d3ab2e20e458de5772173d28f85c464f66aa25`
matches the local canonical prompt manifest. Scope: package model/import/schema
version/effective dating/activation validation/evidence. Six canonical AC; unit,
model, service, affected regression, transaction and conditional migration evidence
required. UI/permissions/tenant tests are canonically N/A for this national-source
engine; existing platform policy-management authority is reused.

Recovered read-only sources (local equivalents absent): approved consolidated
PD freeze archive SHA-256
`1c11429f2e0cc16c61b585832537e5035d19d008bccefc4e94f6d18839047599`, PD-031;
required-specification archive SHA-256
`cf45d1f6db5821084205e3cdf0553cd68c036855cd4c1d5bbe1ee28c7e6693be`,
`BONIRA_PAYROLL_STATUTORY_SOURCE_PACKAGE_SPECIFICATION.md` (SPEC-030); master
backlog IMB-0082 and package card CEP-052. Current prompt governs its amended
CONDITIONAL migration boundary. PD-031/SPEC-030 require official sources,
classification/bases/caps/shares/YTD/rounding/retroactivity/schema/review/evidence.
They supply no current rates or new statutory formula. EXT-0018/GATE-03 remain
activation-only; no current source content or production sign-off is supplied.

Repository seam: Organizations already owns versioned national PlatformPolicy,
PolicySource, immutable published parameters, explicit source/review linkage and
publication authority. Payroll already consumes tax/insurance parameters with
explicit rounding, classification, exemptions/caps/shares and correction lineage.
It lacks an immutable import envelope tying those rules to schema/YTD/retroactivity
evidence. Reuse these authorities; do not create a parallel policy catalogue.
Source-authored YTD/retroactivity descriptions are retained evidence hooks, never
executable rules or inferred statutory YTD calculations. Unsupported cumulative
tax behavior continues to fail closed in the existing calculator.

Actual intended product touch set: `apps/payroll/models.py` (one append-only
StatutorySourcePackage linked one-to-one to existing policy version);
`apps/payroll/source_package_services.py` (strict versioned import, digest and
source/review validation, existing-policy activation and resolution);
`apps/payroll/statutory_services.py` (require/pin package at new calculation);
`apps/payroll/migrations/0007_statutorysourcepackage.py` (expand-only, no backfill);
`apps/payroll/test_cep052.py`, `apps/payroll/test_cep052_migration.py`;
`apps/payroll/test_p7_s23_s28_statutory_payroll.py` (synthetic fixture package
evidence only). Existing finalized history is not rewritten. No UI, new role,
permission, organization settings, financial posting or production activation.

Governance touch set: this manifest, CEP-052 acceptance/evidence/change manifests,
completion report, retained test/migration output and root Registry. Development
schema migration and rollback/reapply in the test database are bounded authority;
production data/migrations remain excluded. A package import binds existing
published-policy history, not a claim that an issuer or value is currently valid.

## Validation closeout

21 clean behavioral tests and one separate migration rollback/reapply test PASS.
Ruff, scoped formatting, Django check, drift and whitespace PASS. Initial import
error corrected; mixed transaction modes caused a content-type deserialization
setup collision, resolved by separate final runs. Actual output retained in the
evidence directory. Migration affects only the PostgreSQL test database; the
read-only development plan includes earlier pending workforce/YTD migrations.
The immutable envelope references existing policy publication/review audit and
retains its own importing actor, timestamp, reason and content digest. Current
Iranian statutory correctness/activation and production certification remain UTV.
