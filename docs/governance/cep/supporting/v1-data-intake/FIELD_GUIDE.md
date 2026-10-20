# Intake CSV field guide

M = mandatory. C = conditional, only when the stated fact exists. M* = mandatory for an includable row/group; if unknown, retain the row as EXCEPTION with an ID/reason and leave the unsupported value blank. Blank never means zero, none, approved or matched. These are evidence-exchange columns, not an executable import API. The original extract and independent controls remain authoritative.

Shared document-level fields and approval references are completed in the two Human input forms. Every CSV column is mapped below; AC numbers refer to each unchanged canonical prompt §23. DoD phrases identify obligations in §24, not new criteria. AC4 requires Codex migration/retry evidence after real inputs; filling these forms does not pass it.

For INFORMATIONAL Payroll evidence, monetary amount/currency/total fields are not applicable: leave them blank with an explicit non-monetary disposition/reason. Count these separately and retain original non-monetary values/units in source evidence. They never contribute monetary YTD. Identity CSVs are conditional files; their M fields apply only when an actual missing link or evidenced correction is supplied.

## CEP057_LEAVE_OPENING_TEMPLATE.csv

HR-057-01/02/03/04/05; AC 1,2,3,5,6,7; DoD: Evidenced target, mapping/exceptions, history, reconciliation and cutover.

| Column | Required | Meaning | Resolution ID |
| --- | --- | --- | --- |
| `dataset_reference` | M | Stable source extract/document identifier; same as the Human input packet. | HR-057-01 |
| `dataset_version` | M | Exact approved extract version, unchanged on retry. | HR-057-01 |
| `organization_reference` | M | Existing tenant reference identifying source ownership; Codex verifies through authenticated tenant authority. | HR-057-01 |
| `source_record_id` | M | Original stable unique row identifier within this dataset. | HR-057-01 |
| `source_version` | M | Original record version; do not substitute a generated target version. | HR-057-01 |
| `source_employee_key` | M | Original employee key; existing exact CEP-029 link or separately evidenced missing link. | HR-057-03 |
| `evidence_reference` | M | Retrievable source document/version/section proving this opening. | HR-057-01 |
| `leave_category` | M | Approved policy category code; no inferred category. | HR-057-02 |
| `signed_quantity` | M* | Exact evidenced signed Decimal; unknown value is blank plus an EXCEPTION, never zero. | HR-057-01 |
| `unit` | M* | days or minutes matching policy; no automatic conversion. | HR-057-02 |
| `policy_version_reference` | M* | Approved policy document/version and section, resolvable to an effective BONIRA policy. | HR-057-02 |
| `as_of` | M | Opening balance date, matching the packet. | HR-057-04 |
| `effective_on` | M | Approved target opening effective date; explicitly distinguish from as_of if different. | HR-057-04 |
| `cutover_on` | M | Bounded Development cutover date, matching the packet. | HR-057-04 |
| `disposition` | M | INCLUDED, EXCLUDED or EXCEPTION; data-owner assertion to be validated. | HR-057-05 |
| `exception_reference` | C | Stable exception/exclusion ID when disposition is EXCLUDED or EXCEPTION. | HR-057-05 |
| `exception_reason` | C | Specific reason for exclusion, missing evidence or ambiguity. | HR-057-05 |
| `related_source_record_reference` | C | Original replaced/corrected/overlapping record reference when present. | HR-057-04 |

## CEP057_IDENTITY_LINK_TEMPLATE.csv

HR-057-03; AC 2,3,5,7; DoD: Mapping/exceptions and retained history.

| Column | Required | Meaning | Resolution ID |
| --- | --- | --- | --- |
| `dataset_reference` | M | Stable source extract/document identifier; same as the Human input packet. | HR-057-03 |
| `dataset_version` | M | Exact approved extract version, unchanged on retry. | HR-057-03 |
| `organization_reference` | M | Existing tenant reference identifying source ownership; Codex verifies through authenticated tenant authority. | HR-057-03 |
| `source_employee_key` | M | Only an external key not already exactly covered by CEP-029, or an evidenced correction. | HR-057-03 |
| `employee_reference` | M* | Existing BONIRA Employee UUID/reference; Codex may resolve from genuine crosswalk evidence. | HR-057-03 |
| `person_reference` | M* | Existing Person UUID/reference; no name/email inference. | HR-057-03 |
| `work_relationship_reference` | M* | Existing WorkRelationship UUID/reference for the effective episode. | HR-057-03 |
| `episode_start` | M* | Evidence-backed inclusive WorkRelationship effective start. | HR-057-03 |
| `episode_end` | C | Evidence-backed inclusive end if the episode ended; blank means open only when proved. | HR-057-03 |
| `existing_crosswalk_reference` | M* | CEP-029_SOURCE_TARGET_MAPPING.csv row identified by tenant, employee and relationship; or explicit correction evidence. | HR-057-03 |
| `evidence_reference` | M | Document/version proving external-key association and effective episode. | HR-057-03 |
| `approval_reference` | M | Existing approval of association/correction; no fresh identity-foundation approval requested. | HR-057-03 |
| `exception_reference` | C | Unresolved association/ambiguity ID; leave unsupported target values blank. | HR-057-03 |
| `exception_reason` | C | Exact unresolved linkage or authoritative correction reason. | HR-057-03 |

## CEP057_RECONCILIATION_CONTROL_TEMPLATE.csv

HR-057-05; AC 2,3,7; DoD: Source-target reconciliation, exceptions.

| Column | Required | Meaning | Resolution ID |
| --- | --- | --- | --- |
| `dataset_reference` | M | Stable source extract/document identifier; same as the Human input packet. | HR-057-05 |
| `dataset_version` | M | Exact approved extract version, unchanged on retry. | HR-057-05 |
| `organization_reference` | M | Existing tenant reference identifying source ownership; Codex verifies through authenticated tenant authority. | HR-057-05 |
| `control_id` | M | Stable independent source-control row ID. | HR-057-05 |
| `control_scope` | M | SOURCE_POPULATION, ELIGIBLE, EXCLUDED, EXCEPTION; Payroll also allows non-additive SUBSET_REVERSED and SUBSET_SUPERSEDED. | HR-057-05 |
| `leave_category` | M* | Approved category grouping; unknown category retained separately. | HR-057-05 |
| `policy_version_reference` | M* | Exact approved policy/version group. | HR-057-05 |
| `unit` | M* | days or minutes, grouped separately. | HR-057-05 |
| `source_row_count` | M | Independent nonnegative integer count for this group; explicit zero for absent excluded/exception populations. | HR-057-05 |
| `signed_quantity_total` | M* | Exact independent source total for this group; unknown exceptional total stays blank with reason. | HR-057-05 |
| `as_of` | M | Same approved cutoff as the source packet. | HR-057-05 |
| `record_ids_reference` | M | Report/list identifying every contributing source row/version; explicit NONE for a proved empty group. | HR-057-05 |
| `exclusion_exception_reason` | C | Reason for EXCLUDED/EXCEPTION groups or unavailable amounts/classification. | HR-057-05 |
| `control_evidence_reference` | M | Independent source control report/document and exact version/section. | HR-057-05 |
| `approval_reference` | M | Approval of source completeness, totals and listed dispositions. | HR-057-05 |

## CEP058_PAYROLL_YTD_SOURCE_TEMPLATE.csv

HR-058-01/02/03/04/05; AC 1,2,3,4,5,6,7; DoD: Finalized evidence, versioned process, mapping, history, reconciliation/repeatability and cutover.

| Column | Required | Meaning | Resolution ID |
| --- | --- | --- | --- |
| `dataset_reference` | M | Stable source extract/document identifier; same as the Human input packet. | HR-058-01 |
| `dataset_version` | M | Exact approved extract version, unchanged on retry. | HR-058-01 |
| `organization_reference` | M | Existing tenant reference identifying source ownership; Codex verifies through authenticated tenant authority. | HR-058-01 |
| `source_record_id` | M | Original stable source record ID, unique within the dataset. | HR-058-01 |
| `source_version` | M | Original exact source version retained across retries. | HR-058-01 |
| `source_employee_key` | M | Original key tied to an exact evidenced effective employment episode. | HR-058-02 |
| `source_period` | M | Original payroll period code/reference, not an assumed calendar month. | HR-058-01 |
| `period_start` | M | Inclusive original period start with calendar conversion evidence. | HR-058-04 |
| `period_end` | M | Inclusive original period end; effective episode must qualify. | HR-058-04 |
| `result_reference` | M | Genuine finalized payroll result reference. | HR-058-01 |
| `line_reference` | M | Genuine stable finalized line reference within the result. | HR-058-01 |
| `source_state` | M | Exact source finalization/reversal/supersession state, retaining source vocabulary. | HR-058-01 |
| `finalization_evidence_reference` | M* | Document/version proving finalized result and state. | HR-058-01 |
| `external_component_key` | M | Original component key; native component reference allowed for native sources. | HR-058-03 |
| `signed_amount` | M* | Exact source signed Decimal; retain reversal signs, never net/flip signs by guess. | HR-058-01 |
| `currency` | M* | Original currency for monetary lines; no implicit IRR or conversion. | HR-058-01 |
| `unit` | M* | Original amount unit/scale; INFORMATIONAL evidence keeps its own non-monetary unit. | HR-058-01 |
| `correction_of_reference` | C | Original corrected source record/version when present. | HR-058-01 |
| `reversal_of_reference` | C | Original reversed source record/version when present. | HR-058-01 |
| `replacement_for_reference` | C | Original replaced source record/version when present. | HR-058-01 |
| `evidence_reference` | M | Retrievable source document/version/section for the row. | HR-058-01 |
| `stable_source_digest` | C | Genuine source-provided digest if available; Codex may compute a separate intake file hash. | HR-058-01 |
| `native_source_line_reference` | C | Existing BONIRA finalized PayrollResultLine UUID only if real; never fabricate for external history. | HR-058-01 |
| `as_of` | M | Exact approved source cutoff matching the year/cutoff packet. | HR-058-04 |
| `disposition` | M | INCLUDED, EXCLUDED or EXCEPTION; validate against original state and correction chain. | HR-058-05 |
| `exception_reference` | C | Stable unresolved/excluded source ID when applicable. | HR-058-05 |
| `exception_reason` | C | Specific unfinalized/unsupported/mapping/correction/coverage issue. | HR-058-05 |

## CEP058_EMPLOYEE_LINK_TEMPLATE.csv

HR-058-02; AC 2,3,5,7; DoD: Mapping/exceptions and historical traceability.

| Column | Required | Meaning | Resolution ID |
| --- | --- | --- | --- |
| `dataset_reference` | M | Stable source extract/document identifier; same as the Human input packet. | HR-058-02 |
| `dataset_version` | M | Exact approved extract version, unchanged on retry. | HR-058-02 |
| `organization_reference` | M | Existing tenant reference identifying source ownership; Codex verifies through authenticated tenant authority. | HR-058-02 |
| `source_employee_key` | M | Only an external key not already exactly covered by CEP-029, or an evidenced correction. | HR-058-02 |
| `employee_reference` | M* | Existing BONIRA Employee UUID/reference; Codex may resolve from genuine crosswalk evidence. | HR-058-02 |
| `person_reference` | M* | Existing Person UUID/reference; no name/email inference. | HR-058-02 |
| `work_relationship_reference` | M* | Existing WorkRelationship UUID/reference for the effective episode. | HR-058-02 |
| `episode_start` | M* | Evidence-backed inclusive WorkRelationship effective start. | HR-058-02 |
| `episode_end` | C | Evidence-backed inclusive end if the episode ended; blank means open only when proved. | HR-058-02 |
| `existing_crosswalk_reference` | M* | CEP-029_SOURCE_TARGET_MAPPING.csv row identified by tenant, employee and relationship; or explicit correction evidence. | HR-058-02 |
| `evidence_reference` | M | Document/version proving external-key association and effective episode. | HR-058-02 |
| `approval_reference` | M | Existing approval of association/correction; no fresh identity-foundation approval requested. | HR-058-02 |
| `exception_reference` | C | Unresolved association/ambiguity ID; leave unsupported target values blank. | HR-058-02 |
| `exception_reason` | C | Exact unresolved linkage or authoritative correction reason. | HR-058-02 |

## CEP058_COMPONENT_CROSSWALK_TEMPLATE.csv

HR-058-03; AC 1,2,3,6; DoD: Approved cumulative target, source mapping.

| Column | Required | Meaning | Resolution ID |
| --- | --- | --- | --- |
| `dataset_reference` | M | Stable source extract/document identifier; same as the Human input packet. | HR-058-03 |
| `dataset_version` | M | Exact approved extract version, unchanged on retry. | HR-058-03 |
| `organization_reference` | M | Existing tenant reference identifying source ownership; Codex verifies through authenticated tenant authority. | HR-058-03 |
| `external_component_key` | M | Exact source component key; do not collapse distinct meanings. | HR-058-03 |
| `bonira_component_reference` | M* | Genuine existing component UUID/code if present; otherwise leave unresolved for Codex contract review. | HR-058-03 |
| `operational_kind` | M* | Decision-05 EARNING, ALLOWANCE, DEDUCTION, REIMBURSEMENT or EMPLOYER; INFORMATIONAL is non-monetary. | HR-058-03 |
| `source_meaning_reference` | M | Document/version/section proving component meaning and source sign. | HR-058-03 |
| `source_sign_convention` | M | Documented source sign convention; preserve signed values. | HR-058-03 |
| `effective_from` | M | Mapping applicability start from evidence. | HR-058-03 |
| `effective_to` | C | Mapping applicability end if bounded; state inclusivity in Human input. | HR-058-03 |
| `approval_reference` | M* | Existing mapping approval, or exact bounded ruling only for unresolved business ambiguity. | HR-058-03 |
| `ambiguity_reference` | C | Stable unresolved key/meaning/sign ambiguity ID. | HR-058-03 |
| `ambiguity_description` | C | Precise ambiguity and missing evidence; no guessed mapping. | HR-058-03 |

## CEP058_RECONCILIATION_CONTROL_TEMPLATE.csv

HR-058-05; AC 2,3,4,5,7; DoD: Reconciliation, history, repeatability and exceptions.

| Column | Required | Meaning | Resolution ID |
| --- | --- | --- | --- |
| `dataset_reference` | M | Stable source extract/document identifier; same as the Human input packet. | HR-058-05 |
| `dataset_version` | M | Exact approved extract version, unchanged on retry. | HR-058-05 |
| `organization_reference` | M | Existing tenant reference identifying source ownership; Codex verifies through authenticated tenant authority. | HR-058-05 |
| `control_id` | M | Stable independent source-control row ID. | HR-058-05 |
| `control_scope` | M | SOURCE_POPULATION, ELIGIBLE, EXCLUDED, EXCEPTION; Payroll also allows non-additive SUBSET_REVERSED and SUBSET_SUPERSEDED. | HR-058-05 |
| `bonira_component_reference` | M* | Exact mapped component reference, or unresolved external key retained as exception. | HR-058-05 |
| `operational_kind` | M* | Existing approved operational kind; ambiguity remains EXCEPTION. | HR-058-05 |
| `currency` | M* | Original source currency; do not mix currencies in a total. | HR-058-05 |
| `unit` | M* | Original amount unit/scale, or non-monetary unit for INFORMATIONAL evidence. | HR-058-05 |
| `source_row_count` | M | Independent nonnegative integer count for this group; explicit zero for absent excluded/exception populations. | HR-058-05 |
| `signed_amount_total` | M* | Exact independent source total for this group; unknown exceptional total stays blank with reason. | HR-058-05 |
| `as_of` | M | Same approved cutoff as the source packet. | HR-058-05 |
| `record_ids_reference` | M | Report/list identifying every contributing source row/version; explicit NONE for a proved empty group. | HR-058-05 |
| `exclusion_exception_reason` | C | Reason for EXCLUDED/EXCEPTION groups or unavailable amounts/classification. | HR-058-05 |
| `control_evidence_reference` | M | Independent source control report/document and exact version/section. | HR-058-05 |
| `approval_reference` | M | Approval of source completeness, totals and listed dispositions. | HR-058-05 |
