# CEP-042-FINDING-001 — source recognition mapping persistence

Current status: RESOLVED by HUMAN-CEP042-PERSISTENCE-20261018.
Historical entry result: FAILED AT ENTRY before product mutation; original evidence below retained.

Baseline: `main` at `90a1b2803936f5a95ce5322151c492ee7bafef11`, matching local
`origin/main` and remote `main`; initially clean. The completed Human checkpoint
contains CEP-035/037. Its metadata reconciliation is complete and is not a blocker.

## Requirement and implementation evidence

CEP-042 sections 6, 18, 23 and 24 require source-specific journal draft mapping,
pinned source/mapping versions, correction/reversal and reconciliation for
IMB-0056/0057/0059/0060. Section 16 prohibits schema/data migrations. SPEC-002
defines recognition owners and eligible occurrence families; it does not supply
tenant ledger accounts or an executable versioned account mapping.

The actual seams were inspected, including model fields in the configured local
development PostgreSQL environment; no relevant migration is pending. See
`CEP-042_REPOSITORY_SEAMS.json` and source identities in `CEP-042_ENTRY.json`.

| Existing seam | Why it does not provide the required mapping |
| --- | --- |
| `apps/accounting/models.py`, `ControlAccountMappingVersion`; `services.py`, `create_control_account_mapping_version` | Explicitly AP/AR policy: one control account, only `payable`/`receivable`. It does not define debit/credit or component/event mapping for Inventory, Payroll, Fixed Assets or Direct Expense. |
| `apps/treasury/models.py`, `TreasuryAccountMappingVersion` | Maps a Treasury account to cash/clearing accounts. Reusing it would misclassify recognition as cash settlement and cross the Treasury ownership boundary. |
| `apps/payroll/models.py`, `FinancialHandoffProposal.mapping_reference`; `financial_handoff_services.py`, `prepare_financial_handoff` | Retains a text reference and component source lines. It neither resolves a mapping version nor supplies mapped Accounting lines. Nonempty text is not proof of an approved executable mapping. |
| `apps/fixed_assets/models.py`, `FixedAssetClassVersion.account_mapping_reference` | Versioned asset class contains a text reference, not an Accounting mapping or its ledger lines. |
| `apps/inventory/p8_models.py`, `DownstreamCostSourceEnvelope`; `p8_services.py`, `supply_cost_envelope` | Retains valuation amount/currency/source version, without Accounting account mappings. |
| `apps/expenses/models.py`, `Expense` | Approved/versioned expense and allocation evidence exist; no recognition mapping relation or ledger-line mapping exists. |
| `apps/organizations/policy_specs.py` | Closed policy catalog has no source-recognition account-mapping policy. Adding arbitrary JSON to an unrelated policy is not a governed reuse contract. CEP-042 section 20 does not authorize inferred configuration semantics. |
| `apps/accounting/models.py`, `JournalEntry`/`JournalLine` | Existing target can retain source identity and journal lines. Those output records and audit metadata do not replace the missing reusable, immutable input mapping version. |

Repository-wide mapping-model/account-field search found no other applicable
mapping authority. Approved consolidated recovery sources were read: frozen
PD-009/011/012/014/030, SPEC-002, the four IMB rows, integration contracts,
package card, dependency edges and GATE-05. None supplies an approved existing
no-migration mapping store. This is not a missing repository search result being
treated as proof that canonical sources do not exist.

## Impact and safe resolution

All four source adapters need an explicit, versioned Accounting-owned mapping.
Implementing durable tenant mappings here requires at least additive mapping
version/line persistence (and any necessary governed catalog migration), outside
the current `Migration Impact = NONE` contract. No model, service, permission,
migration, source data, target journal or posting contract was changed.

Resolve with bounded Human authorization for the minimum additive
Development/Non-Production Accounting source-mapping persistence and necessary
catalog migrations, plus a migration-only canonical prompt amendment and manifest
rehash; or provide an approved existing no-migration mapping contract. Preserve
Scope/AC/DoD, dependencies and all recognition owners. Do not invent account
numbers, debit/credit rules, tenant mapping values, AP routes or production
authority. Actual mapping content must be explicit and validated; absent or
unsupported mappings remain fail-closed. Any later semantic ambiguity requires
its own specific evidence-supported resolution.

Affected acceptance: 24/24 BLOCKED; 0/24 claimed PASS. Scoped DoD NOT MET.
CEP-008 prerequisite baseline: 10 tests and 28 subtests PASS; this does not prove
CEP-042 implementation. GATE-05 remains NOT_PASSED and exit-only.

The serial queue stops at this failed entry under Agents.md section 13 and the
Execution Policy section 8. Dependency-ready independent packages remain listed
for later entry review; no eligibility, activation or production approval is inferred.

## Resolution — 2026-10-18

RESOLVED by HUMAN-CEP042-PERSISTENCE-20261018. The prior blocked entry is historical; bounded additive non-production mapping persistence and migration-only prompt amendment are now authorized. Original hash, amended hash and unchanged non-migration sections are retained in CEP-042_AMENDMENT.json. No business/accounting treatment or posting rule was approved by this migration decision.
