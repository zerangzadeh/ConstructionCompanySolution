# Leave and Payroll opening data intake

Prepared 2026-10-20 for **Development / Non-Production**. These blank templates
collect the remaining evidence for CEP-057 and CEP-058. Return actual source
records and existing approved documents. An existing document/version/section can
answer several fields. No example people, balances or payroll amounts are supplied.

## What to return

| Package | Files to complete and supporting documents | Resolution / canonical obligation |
| --- | --- | --- |
| Leave | [Opening rows](CEP057_LEAVE_OPENING_TEMPLATE.csv), [source controls](CEP057_RECONCILIATION_CONTROL_TEMPLATE.csv), [Human input](CEP057_HUMAN_INPUT.md), original approved extract and referenced policy/approval/control evidence | HR-057-01/02/04/05; AC1–7; evidenced target, reconciliation, history, versioned migration and rollback/cutover DoD |
| Leave, only missing links | [Identity links](CEP057_IDENTITY_LINK_TEMPLATE.csv), only for external keys absent from the existing CEP-029 crosswalk or evidenced corrections | HR-057-03; AC2/3/5/7; mapping/exception DoD |
| Payroll | [Finalized/opening history](CEP058_PAYROLL_YTD_SOURCE_TEMPLATE.csv), [source controls](CEP058_RECONCILIATION_CONTROL_TEMPLATE.csv), [Human input](CEP058_HUMAN_INPUT.md), original approved extract and finalized result/line, year, approval and control evidence | HR-058-01/04/05; AC1–7; finalized target/history, versioned migration, reconciliation, repeatability and rollback/cutover DoD |
| Payroll, only missing links | [Employee links](CEP058_EMPLOYEE_LINK_TEMPLATE.csv), only for missing external keys or evidenced corrections | HR-058-02; AC2/3/5/7; mapping/exception DoD |
| Payroll, external keys | [Component crosswalk](CEP058_COMPONENT_CROSSWALK_TEMPLATE.csv) or existing approved equivalent; retain unresolved meanings explicitly | HR-058-03; AC1/2/3/6; approved target/mapping DoD |

The [field guide](FIELD_GUIDE.md) defines **every CSV column**, mandatory and
conditional fields and its HR/AC/DoD mapping. The Human input forms map every
document-level field. Complete one packet per tenant/dataset/version and one
policy block per Leave policy or year block per Payroll interval. Never combine
tenant populations in a control total.

The existing [CEP-029 crosswalk](../../evidence/CEP-029_SOURCE_TARGET_MAPPING.csv)
already supplies 10 Employee → Person → WorkRelationship links, all confirmed
against current Development targets. Identify an exact existing row; Codex will
resolve genuine internal identifiers. Do not resubmit identity foundations.
External keys still need evidence connecting them to those rows.

## Format and validation

- CSV: UTF-8, comma separated, one header row, quoted commas/newlines, identifiers
  preserved as text. XLSX with one named table/sheet per CSV, or JSON arrays with
  the same keys, are equally acceptable. Supply a field mapping if the original
  export uses different headings. Preserve the original extract unchanged.
- `M` fields are mandatory. `C` fields are required only when the stated fact
  exists. `M*` fields are required for includable rows; missing/ambiguous values
  stay blank with an explicit exception ID/reason. Blank does not mean zero or
  not applicable. In the Human forms, state `NONE` or `NOT APPLICABLE` explicitly
  with an evidence reference where a rule does not apply.
- Use ISO `YYYY-MM-DD` dates and timestamps with timezone. Identify the original
  calendar and conversion evidence. Leave policy end is exclusive; Payroll-year
  start/end and employment episode end are inclusive. Define each source cutoff's
  inclusivity explicitly. No calendar-year or fiscal-year default applies.
- Preserve signed finite decimals, currency and units. Leave supports at most
  four fractional places and absolute quantity below 10,000,000,000; the current
  Payroll preparation supports at most two and absolute amount below 10^22.
  If the original exceeds these limits, retain it unchanged as an exception for
  contract review. Do not round, convert days/minutes, change signs or convert
  currency to make a row fit.
- Stable source record/version IDs, retrievable evidence and tenant/effective
  identity must be provable. Duplicate IDs, unmatched keys, ambiguous policies,
  unknown amounts, zero Leave openings without a disposition, overlapping
  openings and unresolved corrections remain explicit exceptions.
- Independent source counts/totals must identify their contributing row IDs.
  `ELIGIBLE`, `EXCLUDED`, `EXCEPTION` are disjoint supplied dispositions whose
  counts sum to `SOURCE_POPULATION` within each grouping; Codex revalidates them.
  Reversed/superseded Payroll subset controls are non-additive diagnostics, not
  extra population rows. Reversed monetary lines retain their original signs;
  replacement and supersession chains must prevent duplicate contribution.
- Group Leave controls by category, policy/version and unit; Payroll by mapped
  component, operational kind, currency and unit. Unknown classification belongs
  in a separately identified exception group. Supply explicit zero-count controls
  for absent exclusions/exceptions. Unknown exceptional totals stay blank with a
  reason. A genuinely empty dataset is a stated external fact requiring scope
  review; header-only templates or demo records cannot establish migration PASS.

INFORMATIONAL Payroll lines remain separately counted non-monetary evidence.
Their monetary amount/currency/total cells are not applicable and may be blank
with that stated disposition; they never enter monetary YTD totals. Preserve any
original non-monetary value/unit in the unchanged source evidence.

Return sensitive source data through the authorized project handoff with only
necessary personnel fields. These repository templates contain no personal or
monetary data. Codex will retain only necessary sanitized evidence in Git.

## What Codex will do next

Codex will verify source ownership, approval, completeness, tenant membership,
identity/policy/year/cutoff and independent controls; keep exceptions identifiable;
then review the actual source-to-target contract. Both existing preparation
services are **read-only**. External Payroll openings cannot be turned into
fabricated native finalized results. Any required adapter/backfill and target
contract review remains Codex work within canonical scope and authority.

After entry is proved, execute CEP-057 and independently CEP-058 serially:
rehearsal/import, complete source-target reconciliation, retries/idempotency,
rollback/cutover boundary, focused tests and affected checks, evidence and Registry
closeout. Returned inputs and passing previews do not themselves complete a CEP
or pass GATE-06. No production action, statutory activation, Human Sign-off or
Production Certification is included.

## Authority and discovery

The supplied `../V1_HUMAN_RESOLUTION_PACK_20261020.md` defines HR-057/058 IDs;
its opening V1 counts/CEP-065 section are dated history. Current state comes from
the [Registry](../../../../../CEP_EXECUTION_REGISTRY.yaml). Canonical
[CEP-057](../../PROMPTS/CEP-057_EXECUTION_PROMPT.md) and
[CEP-058](../../PROMPTS/CEP-058_EXECUTION_PROMPT.md) §§9/22–24 remain unchanged.
[Decision-05](../CONSOLIDATED_HUMAN_AUTHORIZATION_20261017.txt) already establishes
operational kinds and the versioned Payroll-year reset mechanism; no reapproval
of these, identity foundations, Treasury authority or statutory values is asked.

[Discovery evidence](DISCOVERY_AND_VALIDATION.json) records sources, hashes and
read-only counts. The supplied Human resolution pack was pre-existing untracked
Human work and is preserved outside this checkpoint; its hash identifies the
local authority used. The templates/forms here contain the complete HR-057/058
return requirements without depending on that file being tracked.
