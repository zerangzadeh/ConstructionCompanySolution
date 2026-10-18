# CEP-043-FINDING-001 — liability enrollment and AP source reversal persistence

**HISTORICAL BLOCKER-MIGRATION — RESOLVED by HUMAN-CEP043-PERSISTENCE-20261018.**
Original failed entry and evidence below are retained. Migration-only canonical
amendment verified in CEP-043_AMENDMENT.json. No product mutation has occurred;
the separate semantic review is recorded in CEP-043-FINDING-002.

## Governing requirement and affected criteria

CEP-043 sections 6/23/24 require source-family-specific enrollment, retained
source/version, AP idempotency, correction/reversal, failure/retry and source-target
reconciliation (six AC, IMB-0061). Section 16 states `Migration Impact = NONE`
and requires a finding before an unavoidable schema migration. Execution Policy
section 13 and Playbook section 10 prohibit exceeding that boundary.

PD-009/030, SPEC-002/029, IMB-0061 and the approved INT-B07 contract permit only
explicitly enrolled finalized Payroll liabilities; they supply no actual tenant
liability family, AP party/payee, due-date or payment-grouping mapping. EXT-0013
is activation-only. Its absence alone does not prevent framework construction.
GATE-05 is NOT_PASSED and exit-only here; it is not this entry blocker.

## Reproducible repository evidence

Baseline: main `da01c850b6fbacf41c793548426cb53e9bbc6813`, equal to origin/main
and remote main. Relevant configured Development migrations are current.
`CEP-043_REPOSITORY_SEAMS.json` records model fields, physical table presence,
registered sources, policy codes and unchanged baseline guard hashes without
reading business rows. `CEP-043_ENTRY.json` records recovered canonical sources
and byte hashes. All 79 local prompt hashes and prerequisite sets verify.

| Existing seam | Limit on safe reuse |
| --- | --- |
| Payroll `FinancialHandoffProposal`, `FinancialHandoffLine`, `FinancialHandoffReview`; `financial_handoff_services.py` | Immutable source proposals and review, not enrolled AP input policy. Liability preparation discards `mapping_reference`; employee number is retained as a proposal payee reference, not an approved BusinessParty/AP link. Review accepts the proposal, without an AP family/party/date/grouping mapping contract. |
| Payroll acknowledgements/reconciliations | Retain downstream references and observation evidence. They do not approve enrollment or reverse an AP obligation. Adding arbitrary policy/reversal JSON would invent authority in observation records. |
| AP `Obligation`; `recognize_obligation` | Existing identity/version/line-key uniqueness and Accounting control-account pin are reusable target capabilities. The resolver catalog has Billing certificate/claim and supplier-match sources; it has no Payroll adapter/enrollment. Target snapshots are output evidence, not approved reusable input mapping policy. |
| AP `SupplierInvoiceAPReversal` | Sole retained AP source-reversal relation. `clean()` explicitly permits only `procurement.supplier_invoice_match.v1`; replacement FK targets `SupplierInvoiceMatch`. AP outstanding/settlement/aging consumers depend on this relation. Reusing it for Payroll would repurpose supplier-specific history and broaden its contract. |
| AP settlement/write-off reversals | Reverse cash allocations or governed write-offs. Neither is a Payroll source correction; using either would invent financial treatment. |
| Accounting `ControlAccountMappingVersion` | Maps source kind/direction to a control account. It does not enroll a Payroll liability family or define payee, source occurrence, due date or grouping. |
| Accounting CEP-042 `RecognitionMappingVersion` / `SourceRecognitionDraft` | Account-pair mappings and GL draft lineage. They cannot be repurposed as AP enrollment or AP obligation reversal; that risks duplicate Payroll recognition. |
| Closed platform policy catalog | No Payroll-to-AP enrollment schema/consumer exists. Unrelated statutory, monetary, profile or Treasury mappings do not authorize that behavior. |

Repository-wide model/mapping searches and canonical recovery found no applicable
approved no-migration enrollment/correction store. Code-only adapter/empty-catalog
construction can deny activation, but cannot prove the required durable enrolled
source-to-target correction/reversal lifecycle. A caller-supplied mapping, source
review or audit payload cannot silently become the missing approved policy.

## Scope impact and resolution

The bounded safe implementation needs explicit versioned enrollment/mapping
evidence and Payroll-specific AP source correction/reversal retention integrated
with AP readers. The existing supplier-specific reversal record cannot be
silently generalized or treated as Payroll history. New additive persistence
would exceed the current migration contract; no model, migration, source adapter,
permission, policy value or business data has been changed.

Required resolution: bounded Human authorization for the minimum additive
Development/Non-Production enrollment and Payroll AP reversal persistence and
necessary migrations, plus a migration-only canonical prompt amendment and
manifest rehash; alternatively, an approved existing no-migration contract that
provides these retained authorities. No liability family, payee, amount, date,
grouping, GL posting rule or production activation should be inferred by that
resolution. Actual family activation still requires EXT-0013 evidence.

AC 1–6: BLOCKED, 0/6 PASS. Scoped DoD: NOT MET. Implementation/integration,
retry/reversal/reconciliation validation: NOT EXECUTED. Prerequisite baseline:
10 tests / 28 subtests PASS only. Prior Payroll authorization fixture debt and
performance/concurrency UTV are preserved; they are not the blocker.

Serial queue stopped on this material entry blocker. Other dependency-ready CEPs
remain unreviewed and are not declared eligible. No Git writes, schema/data
migrations, production action, Human Sign-off or certification.
