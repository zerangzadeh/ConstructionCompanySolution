# CEP-032 — Human Decision: Commercial Tender/Bid source and lifecycle

Decision authority: Human Decision Authority, 2026-10-18. This bounded decision supplements frozen PD-019 and SPEC-019 for CEP-032 only. It does not change unrelated CEP Scope/AC/DoD or activate EXT-0004/GATE-03.

Commercial owns Contractor Tender/Bid pre-award lifecycle and persistence. CEP-032 may introduce the minimum persistent Commercial Tender/Bid model and development/non-production migration required by its existing Scope/AC/DoD. The prior CEP-032 Migration Impact `NONE` is superseded for that bounded purpose. No production migration, cutover, deployment, or sign-off is authorized.

Procurement RFQ remains Procurement authority and is not the Contractor Tender/Bid source. Contract and Guarantee records remain post-award authorities and may not substitute for pre-award Tender/Bid persistence.

Governed states: `DRAFT`, `SUBMITTED`, `UNDER_REVIEW`, `WON`, `LOST`, `WITHDRAWN`, `CANCELLED`. Valid transitions are `DRAFT → SUBMITTED/CANCELLED`, `SUBMITTED → UNDER_REVIEW/WITHDRAWN`, and `UNDER_REVIEW → WON/LOST/WITHDRAWN`. `WON`, `LOST`, `WITHDRAWN`, and `CANCELLED` are terminal. Submitted records retain history; material post-submission changes create a new governed revision/version rather than overwriting prior submitted state.

`WON` records only a Commercial outcome. No transition infers award, contract creation, Procurement authority, accounting effect, scoring, ranking, or automatic approval. Downstream contract creation remains governed by its own domain and CEPs. The bounded status/detail activation condition in EXT-0004 remains closed until its required configuration evidence exists; development implementation must fail closed where that condition is applicable.
