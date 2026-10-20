# CEP-057 Leave opening — source-owner response

Complete the Value column, or cite an existing approved document's exact version
and section. Empty fields remain unresolved. Repeat policy blocks for each
category/version. `M` is mandatory; `C` is conditional as stated. References must
be retrievable and show the applicable approval; a filled reference string alone
does not prove approval. This response supplies source facts and bounded existing
policy selections, not Human Sign-off or production cutover.

Basis: canonical CEP-057 §§9/22–24, PD-026, SPEC-011, IMB-0075, EXT-0015,
HR-057-01..05. CSV fields are defined in [FIELD_GUIDE.md](FIELD_GUIDE.md).

| Fill-in field | Required / meaning | HR ID | AC / DoD obligation | Value or document/version/section |
| --- | --- | --- | --- | --- |
| organization_reference | M; existing Development tenant whose source is supplied | HR-057-01 | AC1/2/6; evidenced target | |
| eligible_population_definition | M; exact employees/episodes/categories included and scope exclusions | HR-057-01 | AC1/2/6; evidenced target | |
| dataset_reference | M; original system/document and extract identifier | HR-057-01 | AC1/2/5; history | |
| dataset_version | M; exact approved extract version | HR-057-01 | AC1/5; versioned process/history | |
| source_extract_attachment | M; unmodified actual extract and retrieval location | HR-057-01 | AC1/2/5; evidenced target/history | |
| source_approval_reference | M; approver/authority/date and exact source/version covered | HR-057-01 | AC1/6; evidenced target | |
| source_calendar_and_conversion | M; original calendar, timezone and conversion evidence where converted | HR-057-01/04 | AC1/5/6; source/cutover | |
| approved_policy_document | M; existing approved Leave Policy document and exact section | HR-057-02 | AC1/6; approved target | |
| policy_version_reference | M; version matching the row/control templates | HR-057-02 | AC1/5/6; approved target/history | |
| policy_approval_reference | M; approval, authority and effective version | HR-057-02 | AC1/6; approved target | |
| policy_effective_from | M; inclusive ISO date | HR-057-02 | AC1/6; approved target | |
| policy_effective_to | M; exclusive ISO date; interval must cover as_of and target effective date | HR-057-02 | AC1/6; approved target | |
| leave_category | M; policy category code | HR-057-02 | AC1/6; approved target | |
| unit | M; explicitly approved days or minutes | HR-057-02 | AC1/3/6; target/reconciliation | |
| entitlement_rule_reference | M; explicit entitlement amount/rule and source document | HR-057-02 | AC1/6; approved target | |
| accrual_preset | M; approved FULL_CREDIT, ZERO_ACCRUAL or POLICY_DEFINED, never a profile default | HR-057-02 | AC1/6; approved target | |
| accrual_rule_reference | C; mandatory for POLICY_DEFINED, otherwise explicit applicable rule or NONE with evidence | HR-057-02 | AC1/6; approved target | |
| negative_balance_floor | M; exact approved signed threshold in stated unit, not an assumed zero | HR-057-02 | AC1/6; approved target | |
| carry_forward_treatment | M; rule and explicit limit/unit, or approved non-applicability; blank is unknown | HR-057-02 | AC1/6; approved target | |
| expiry_treatment | M; rule/period/evidence or approved non-applicability | HR-057-02 | AC1/6; approved target | |
| existing_identity_crosswalk_reference | M; cite exact applicable CEP-029 tenant/employee/relationship rows, not a new identity foundation | HR-057-03 | AC2/3/5/7; mapping/history/exceptions | |
| missing_external_links_attachment | C; complete identity-link CSV only for missing source keys/corrections; otherwise state NONE | HR-057-03 | AC2/3/5/7; mapping/exceptions | |
| unresolved_identity_exception_reference | C; identify unsupported keys/episodes and evidence still missing | HR-057-03 | AC2/7; exceptions | |
| as_of | M; opening source balance date | HR-057-04 | AC1/6/7; source/cutover | |
| opening_effective_on | M; approved target effective date, including reason if different from as_of | HR-057-04 | AC1/6/7; source/cutover | |
| cutover_on | M; Development-only date and explicit affected source/target boundary | HR-057-04 | AC1/6/7; rollback/cutover | |
| opening_coverage_definition | M; what each quantity includes: entitlement, accrued, consumed, reserved, adjustments, carry-forward/expiry as applicable; explicitly identify exclusions | HR-057-04 | AC1/6/7; source/cutover | |
| source_inclusion_boundary | M; exact dates/events/states and inclusive/exclusive endpoints | HR-057-04 | AC1/6/7; source/cutover | |
| overlap_treatment_reference | M; approved treatment of opening versus subsequent target movements/reservations and source versions | HR-057-04 | AC1/6/7; exclusive authority/rollback | |
| zero_negative_overlapping_rows | C; existing approved dispositions and affected IDs when encountered; otherwise NONE; unresolved rows remain exceptions | HR-057-04 | AC1/2/6/7; target/exceptions | |
| cutoff_approval_reference | M; existing approval covering dates, coverage and overlap rule | HR-057-04 | AC1/6/7; rollback/cutover | |
| reconciliation_controls_attachment | M; completed control CSV or equivalent, with independent counts/signed totals by policy/category/unit | HR-057-05 | AC2/3/7; reconciliation | |
| control_report_version_reference | M; source report/version/section supporting totals and population completeness | HR-057-05 | AC2/3/5/7; reconciliation/history | |
| excluded_and_exception_ids_reference | M; IDs/versions/reasons and factual resolutions, or explicit NONE backed by zero controls | HR-057-05 | AC2/3/7; exceptions/reconciliation | |
| control_approval_reference | M; existing approval of controls and listed exclusions/exceptions | HR-057-05 | AC2/3/7; reconciliation | |

Return the three CEP057 CSVs (identity links only if needed), this response and
their evidence documents. Do not derive openings from leave request/demo history.
Unmatched rows remain explicit exceptions. Codex must still prove AC4 retry and
the full versioned-migration/history/reconciliation/rollback/repeatability DoD
after actual source validation. No blank template or source-owner response is an
execution result.
