# P6-S21–S25 Guarantee, Clearance, Exposure, and Release Implementation

**Date:** 2026-10-03  
**Status:** Product Owner accepted 2026-10-03. P6-S26–S32 subsequently became
Product Owner accepted; P6-S33–S38 subsequently became implementation complete /
acceptance pending; P6-S39+ remains unauthorized.

## Delivered boundary

This bounded tranche adds contract-commercial controls without creating a second
contract, party, document, workflow, subledger, or accounting authority:

- `ContractGuarantee` records contract-linked bid, performance,
  advance-payment, and retention guarantees. Every version pins the Tenant,
  project, contract, counterparty identity snapshot, currency, amount, explicit
  issued/received exposure side, validity facts, and one immutable clean
  `DocumentVersion`.
- A stable series and linked predecessor preserve correction, renewal, and
  release history. Approved versions are immutable. An approved correction or
  renewal supersedes an active predecessor; approved release evidence closes the
  active version without deleting or rewriting it.
- `ContractComplianceEvidence` records insurance or clearance evidence with the
  same Tenant/project/contract/party and DMS controls. Effective dates and either
  an explicit expiry date or an explicit open-ended fact are stored. The record
  has no inferred Article 38, statutory, deduction, payment, or accounting effect.
- Dated active evidence is operationally due after its recorded expiry date.
  Expiry refresh is locked, audited, Tenant-local-date aware, and idempotent.
  No grace period, warning threshold, renewal interval, or notification rule is
  inferred.
- Exposure is a read model over effective, unexpired active guarantees. It groups
  Decimal face amounts by currency, issued/received side, and guarantee type.
  Different currencies and opposing sides are never netted.
- `RetentionRelease` is limited to payable subcontracts with accumulated approved
  retention deductions and an approved effective `ContractTermVersion` that
  explicitly enables release and states an exact release cap. A term may require
  only pinned contractual evidence or additionally an approved effective
  clearance record. Missing authority, evidence, clearance, cap, or retained
  balance fails closed.
- Linked replacement and zero-value cancellation preserve retention-release
  correction history. Approval re-locks the contract and release rows and rejects
  stale balance snapshots, preventing concurrent over-release.

Guarantee, compliance, and retention-release approval use the shared workflow
runtime with code-owned subject adapters and domain commands. Submission is
idempotent. Acting requires an active membership, the dedicated permission,
current work-item candidacy, and strict submitter/approver separation. Domain
transition, work-item completion, predecessor disposition, and audit evidence
commit atomically.

## Financial and legal boundary

These records are commercial control and evidence only:

- guarantee approval, expiry, renewal, or release creates no AP/AR obligation,
  supplier invoice, payment, cash instrument, Project Cost fact, posting proposal,
  or journal;
- retention release does not modify a payable certificate or its deductions and
  does not recognize or settle AP;
- no Iranian rate, guarantee percentage, Article 38 interpretation, clearance
  effect, grace period, provider behavior, or statutory filing rule is encoded;
- no bank/insurer/provider integration, scheduler, notification infrastructure,
  taxpayer integration, contractual claim/EOT, or production activation is added.

## Schema, permissions, workflow, and UI

- `contracts.0007` adds the explicit retention-release requirement and Decimal cap
  to immutable contract-term versions; existing versions default to unconfigured
  and therefore deny release.
- `billing.0012` creates guarantee, compliance-evidence, and retention-release
  authorities with version/correction lineage, conditional active-version
  uniqueness, nonnegative/positive amount constraints, and operational indexes.
- `organizations.0086` adds twelve view/manage/submit/approve permission codes,
  default management-role grants, registry entries, and project-object scope.
- `workflows.0025` registers three code-owned strict-separation starter workflows.
- Persian-first RTL screens provide a combined exposure/expiry workbench, lists,
  evidence and calculation detail, creation, submission, work-item decision,
  correction/renewal/release, retention replacement/cancellation, and expiry
  refresh paths. Server authorization remains authoritative.

## Verified acceptance evidence

- The full migration chain created a clean PostgreSQL test schema including the
  four new migrations. The focused commercial-control suite passed first on that
  schema and then passed after final expansion: **9 passed**. Coverage includes
  guarantee activation/release and exposure, dated expiry, compliance renewal,
  unsafe/missing evidence, explicit term and clearance requirements, release
  calculations and caps, correction history, permissions, Tenant isolation,
  workflow candidacy/SoD, audit rollback atomicity, RTL UI, and concurrent
  over-release prevention.
- The retained P6-S14–S20 payable-certificate module passed: **11 passed**,
  including its PostgreSQL duplicate-period concurrency test and AP/Accounting
  boundary regressions.
- Django system check and migration-drift check passed. Targeted Ruff check and
  formatting passed.
- The focused permission-catalog/database/role-default checks passed: **3 passed,
  11 subtests passed**. The broader permission-registry module still has its three
  pre-existing material/document-link architecture failures
  (`MaterialRelationship`/typed document-link coverage,
  `MATERIAL_DOCUMENTS_LINK` enforcement reference, and historic namespace
  mismatches). They are outside this tranche and were not modified or masked.

## Assumptions and open gates

- `expires_on` is the recorded last effective date; the operational state becomes
  overdue after that date. Open-ended validity must be explicitly selected. No
  legal extension or notice period follows from either fact.
- Exposure means active face amount only. It is not risk-weighted, probability-
  adjusted, collateral-valued, converted, netted, or posted.
- Release capacity is the lesser of retained value not already released and the
  remaining explicit contract-term release cap. This is a conservation control,
  not an Article 38 or accounting interpretation.
- A clean immutable DMS version is required for every guarantee, compliance, and
  release record. The tranche does not create or upload source documents itself.
- The Product Owner accepted P6-S21–S25 on 2026-10-03 based on the verified
  implementation, validation evidence and documented boundaries in this packet.
  Acceptance covers only the implemented guarantee, insurance/clearance evidence,
  exposure reporting and retention-release scope.
- The documented materials/document-link/platform-policy permission-registry gaps
  remain separate unresolved issues. This acceptance neither accepts nor resolves
  them.
- P6-S01–S13 acceptance remains open; P6-S14–S20 acceptance is unchanged. This
  acceptance did not itself authorize P6-S26+. That tranche later proceeded
  under a separate bounded authorization. Neither acceptance authorizes AP/AR obligation creation, Accounting
  journals or automatic posting, Treasury/cash actions, statutory or legal
  interpretation, FX conversion, invented exposure/risk rules, external
  integrations, notification infrastructure or production activation.

## Next authorized session

No later P6 session was authorized by this closeout. P6-S26–S32 subsequently
proceeded under separate bounded Product Owner authorization and is now recorded
in the [taxpayer/contractor-compliance packet](P6_S26_S32_TAXPAYER_CONTRACTOR_COMPLIANCE_IMPLEMENTATION.md).
Official schemas/values, live credentials/provider behavior, legal/accounting
activation and production controls remain gated. P6-S33–S38 claims/EOT later
proceeded under separate authorization; P6-S39+ remains
unauthorized.
