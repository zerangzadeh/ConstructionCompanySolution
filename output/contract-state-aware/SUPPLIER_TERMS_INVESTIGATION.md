# Supplier Contract Terms — CONFIRMED RULE (current implemented scope)

Investigation date: 2026-11-01. This finding concerns existing `ContractTermVersion`, not a permanent ban on all possible supplier commercial terms.

| Source | Evidence and interpretation |
| --- | --- |
| `docs/architecture/BILLING_AND_PROGRESS_CLAIMS.md:43` | Explicitly limits payable use to `Contract(direction=payable, type=subcontract)`. Defines immutable approved/superseded history. |
| `docs/architecture/P6_S14_S20_PAYABLE_CERTIFICATION_IMPLEMENTATION.md:4` | The bounded tranche is marked Product Owner accepted 2026-10-03. |
| Same packet, Delivered boundary (lines 14–19) and Product Owner acceptance (lines 83–89) | Existing payable subcontract authority and extending ContractTermVersion to payable subcontracts were part of the accepted boundary. This is affirmative scope evidence, beyond implementation absence. |
| `apps/contracts/services.py:62` / lines 95–104 | `create_contract_term_version` permits receivable contracts and rejects payable types other than subcontract with an explicit validation error. |
| `apps/contracts/models.py`, ContractTermVersion.clean, lines 388–405 | Repeats the boundary at model validation: payable use in this stage is subcontract only. |
| `apps/billing/payable_services.py`, `_locked_subcontract` | Payable measurement/certification requires payable subcontract and a reference party; new operations require active state. |
| `apps/billing/test_payable_certificates.py` | Existing measured-work, cumulative certificate, terms, maker/checker, scope and immutable history tests use payable subcontracts. These tests demonstrate the implemented supported path; they alone are not approval evidence for supplier exclusion. |
| New `apps/contracts/test_state_workspace.py::test_supplier_rule_enforced_by_service_and_model` | Supplier terms are rejected through both existing service and model validation. The new HTTP adapter also exposes no supplier term mutation. |

Conclusion: **SUPPLIER CONTRACT TERMS: CONFIRMED RULE** for the current accepted ContractTermVersion/payable-certification implementation. No DOMAIN GAP is inferred from the absence of supplier support in this specific mechanism. The supplier UI keeps an explanatory contract-type note and does not permanently erase the concept or activate another domain's financial path.

No Product Owner decision is needed merely to preserve this explicit current boundary. If BONIRA is to support a separate supplier-term mechanism or extend ContractTermVersion to suppliers, **PRODUCT OWNER DECISION REQUIRED** for bounded domain ownership, lifecycle, permissions/producer contracts and implementation authority. That extension was not performed by this task.
