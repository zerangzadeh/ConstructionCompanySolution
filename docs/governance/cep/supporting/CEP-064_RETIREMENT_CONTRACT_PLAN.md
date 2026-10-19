# Development retirement contract plan

Status: PREPARED ORDER ONLY; destructive migrations are not installed or executed.
The exact twelve-condition Human gate remains mandatory. The source population
decision is final: zero authoritative history, all existing rows excluded demo/test.

1. Retain a verified Development dump and restoration manifest. Recheck that the
   checkpoint covers the final pre-contract state before any destructive mutation.
2. Preserve each source Payment UUID, original values, allocations, old Billing
   settlement values, document-link UUIDs and audit identifiers. Preparation is
   `documents.0012_legacy_payment_reference_preparation`; current DMS references
   resolve to Documents-owned retained evidence using the original UUIDs.
3. Require the readiness evidence to contain twelve PASS results bound to the
   actual candidate code/migration digest. Latest Human authority permits valid non-CEP registry attribution;
   required attributable failures still block. Validate source/snapshot equality again immediately before contract.
4. Prepare the Billing contract migration after `billing.0017` and `documents.0012`:
   delete only the obsolete `ClaimSettlementAllocation` model/table. Its source
   values must already be included in the retained snapshots. Current allocations
   belong to `subledgers.SettlementAllocation`, which remains intact.
5. Prepare the Payment contract migration after that Billing migration and both
   reference-preparation migrations: delete old Payment document links, old
   Payment allocations, then Payment. Preserve historical migration definitions
   and the `payments` migration label through a migration-only compatibility
   package so a clean database can still traverse the original dependency graph.
   That package must expose no runtime business models, routes or permission
   surface. Treasury `PaymentRequest` and all Treasury/Subledger tables remain.
6. Remove the obsolete runtime app, model declarations, disabled compatibility
   facades, forms, templates, URLs and obsolete permission/default-grant consumers.
   Retain audit action labels and explicit retired-source interpretation. Keep
   migration-era string labels where required to rebuild historical schema.
7. Rehearse the complete candidate graph from zero on a separate local database
   before applying the contract to configured Development. Verify final absence
   of old tables, presence of retained DMS evidence and current Treasury tables,
   focused and affected regression, system/drift checks, no active old imports,
   replacement flows, no double counting and audit/document interpretation.
8. Only all twelve readiness PASS results permit configured Development contract
   execution. Repeat every required post-removal check before COMPLETE=YES.

Current boundaries: preparation/reference migrations only; no old table/model/app
removal, no source-row deletion, no Production action, no CEP-069..079 execution.
The final destructive candidate graph has not been rehearsed and remains
UNVERIFIED. The prepared reference graph is a separate validation result.

Follow-up2026-10-20: refreshed523-table recovery PASS. Preflight found an active
Reporting dependency on billing.ClaimSettlementAllocation and full seed Quality
record-review failure after Safety was fixed. Full destructive graph remains
UNVERIFIED and is not executed under the exact Human STOP rule. See
CEP-064_REHEARSAL_PREFLIGHT.json. No new source contract is installed.
