# CEP-058 Payroll/YTD opening — source-owner response

Complete the Value column or cite existing approved document/version/section.
Repeat the year block for each distinct tenant interval. Empty fields remain
unresolved. `M` is mandatory; `C` is conditional. Supply actual finalized evidence
and independent controls. This supplies source facts and concrete interval
bindings, not Human Sign-off, statutory approval or production cutover.

Basis: canonical CEP-058 §§9/22–24, PD-031, SPEC-013/030, IMB-0080, EXT-0017,
HR-058-01..05. CSV fields are defined in [FIELD_GUIDE.md](FIELD_GUIDE.md).

Already approved by Decision-05: separate signed EARNING, ALLOWANCE, DEDUCTION,
REIMBURSEMENT and EMPLOYER buckets; INFORMATIONAL stays non-monetary. Reset uses
an explicitly approved versioned tenant Payroll-year interval. Corrections
supersede prior contributions without double inclusion. Do not reapprove these
semantics, identity foundations, Treasury authority, taxable/insurable categories
or statutory rates. Supply only missing source bindings and concrete year dates.

| Fill-in field | Required / meaning | HR ID | AC / DoD obligation | Value or document/version/section |
| --- | --- | --- | --- | --- |
| organization_reference | M; existing Development tenant owning the source | HR-058-01 | AC1/2/6; evidenced target | |
| eligible_population_definition | M; employees/episodes, source periods and finalized states included, exclusions | HR-058-01 | AC1/2/6; evidenced target | |
| dataset_reference | M; original system/document and extract identifier | HR-058-01 | AC1/2/5; history | |
| dataset_version | M; exact approved extract version | HR-058-01 | AC1/4/5; versioned process/repeatability | |
| source_extract_attachment | M; unmodified original history/opening extract | HR-058-01 | AC1/2/5; evidenced target/history | |
| source_approval_reference | M; approver/authority/date and exact dataset/version covered | HR-058-01 | AC1/6; evidenced target | |
| finalized_result_line_evidence | M; source periods/results/lines, finalization and retained state/version evidence | HR-058-01 | AC1/2/5/6; finalized target/history | |
| currency_unit_scale_reference | M; source currency and units/scale for each monetary group; no implicit currency/conversion | HR-058-01 | AC1/3/6; target/reconciliation | |
| correction_chain_reference | C; correction/reversal/replacement/supersession links and source state evidence when present; otherwise NONE | HR-058-01/05 | AC1/2/4/5/7; history/repeatability | |
| native_source_lineage_reference | C; genuine BONIRA line UUIDs/digests only if they already exist; otherwise external stable references | HR-058-01 | AC1/4/5; source/history/repeatability | |
| existing_identity_crosswalk_reference | M; exact applicable CEP-029 tenant/employee/relationship rows | HR-058-02 | AC2/3/5/7; mapping/exceptions | |
| missing_employee_links_attachment | C; link CSV only for missing external keys/evidenced corrections; otherwise NONE | HR-058-02 | AC2/3/5/7; mapping/exceptions | |
| effective_episode_evidence | M; source period's applicable WorkRelationship episode; identify ambiguous/cross-episode periods | HR-058-02 | AC2/3/5/7; mapping/history | |
| external_component_crosswalk_reference | C; completed crosswalk or existing approved mapping for external keys; native mappings need no reapproval | HR-058-03 | AC1/2/3/6; approved target/mapping | |
| component_meaning_sign_evidence | M; source documentation tying each eligible key to its existing component/kind and signed source meaning | HR-058-03 | AC1/2/3/6; approved target | |
| component_mapping_effective_interval | C; existing mapping interval/inclusivity where effective-dated; otherwise explicit applicability evidence | HR-058-03 | AC1/2/6; mapping/history | |
| unresolved_component_ambiguity | C; exact external key, meaning/sign uncertainty, affected IDs and missing evidence; otherwise NONE | HR-058-03 | AC1/2/6; target/exceptions | |
| existing_mapping_or_bounded_ruling_reference | C; reuse approved mapping; only unresolved business ambiguity needs its exact bounded ruling | HR-058-03 | AC1/2/6; approved target | |
| payroll_year_code | M; explicit tenant Payroll-year code, not assumed calendar/fiscal year | HR-058-04 | AC1/4/6/7; versioned process/cutover | |
| payroll_year_version | M; exact approved version | HR-058-04 | AC1/4/5/6; versioned process/history | |
| payroll_year_starts_on | M; inclusive ISO date | HR-058-04 | AC1/4/6/7; reset/cutover | |
| payroll_year_ends_on | M; inclusive ISO date | HR-058-04 | AC1/4/6/7; reset/cutover | |
| payroll_year_approval_reference | M; existing approved interval or approval of these concrete dates; no reset-mechanism reapproval | HR-058-04 | AC1/4/6/7; approved target/cutover | |
| source_calendar_and_conversion | M; original calendar, tenant timezone and conversion evidence where converted | HR-058-04 | AC1/5/6; source/history/cutover | |
| as_of | M; exact source cutoff date within the approved interval | HR-058-04 | AC1/4/6/7; source/cutover | |
| source_inclusion_boundary | M; included period range and eligible source state/version rule, endpoint inclusivity, treatment of later finalized/corrected records | HR-058-04 | AC1/4/6/7; source/cutover | |
| opening_coverage_definition | M; what history the opening represents and its relationship to later native results | HR-058-04 | AC1/4/6/7; exclusive source authority | |
| overlap_treatment_reference | M; approved exclusion/supersession binding for opening versus later results, preventing double inclusion | HR-058-04 | AC1/4/6/7; exclusive authority/repeatability | |
| development_cutover_boundary | M; approved bounded Development transition date/condition, or explicit no-authority-switch scope with source reference | HR-058-04 | AC6/7; rollback/cutover | |
| cutoff_coverage_approval_reference | M; approval covering as_of, inclusion, coverage and overlap | HR-058-04 | AC1/4/6/7; rollback/cutover | |
| reconciliation_controls_attachment | M; independent source counts and signed totals by mapped component/kind/currency/unit | HR-058-05 | AC2/3/4/5/7; reconciliation/repeatability | |
| control_report_version_reference | M; independent source report/version and completeness evidence | HR-058-05 | AC2/3/5/7; reconciliation/history | |
| superseded_reversed_excluded_ids_reference | M; exact source IDs/versions and reasons/state evidence, or explicit NONE and zero controls | HR-058-05 | AC2/3/4/5/7; history/reconciliation | |
| unresolved_exception_ids_reference | M; missing mappings/lineage/amounts and other exceptions with IDs/reasons, or NONE with zero controls | HR-058-05 | AC2/3/7; exceptions/reconciliation | |
| control_approval_reference | M; approval covering source counts/totals/dispositions | HR-058-05 | AC2/3/7; reconciliation | |

Return source/control CSVs, this response, conditional link/crosswalk files and
the referenced evidence. Native internal IDs/digests are Codex-resolvable from
genuine existing records; no invented runs/results/lines may stand in for external
history. Current Development has no components or finalized Payroll lines, so an
external mapping must remain explicit pending actual contract review. Supply the
source meaning; the Human is not asked to design a database schema.

Codex must still implement/validate the actual source-to-target path and prove
AC1–7 and full DoD: versioned migration, mapping/exceptions, retained history,
reconciliation, retry/repeatability and rollback/cutover boundaries. Source
submission and preparation tests do not establish completion or statutory PASS.
