# P1-S14B professional evidence register

**Status:** ACTIVE SOURCE / OPTIONAL-REVIEW REGISTER — not a global stage gate.
**Recorded:** 2026-09-29. **Reframed:** 2026-09-29 by final Product Owner decision.

This register preserves legal/accounting source provenance and optional external
professional-review evidence. External authorities and professionals are not ERP
actors. Empty rows are not evidence. Their absence blocks only a policy that
explicitly declares provenance mandatory or a feature making a source-backed
regulatory claim—not ordinary Tenant configuration, generic architecture or
unrelated roadmap development.

## 1. Current evidence status

| Evidence class | Current repository state | Consequence |
| --- | --- | --- |
| Official source records | No real source/version record is registered. | A regulated/accounting-sensitive policy requiring that source cannot be published or applied. |
| Optional professional review | No real review artefact is registered. | No professional-validation claim may be made; development is not globally blocked. |
| D14-11 | Closed as a global development gate by Product Owner decision. | Explicit policy/configuration requirements and fail-closed controls govern affected activation. |

P1-S14 is complete. Unknown regulated values remain unset/inactive and no empty
template, Product Owner decision or optional review record validates them.

## 2. Official-source intake

Add one row per official source and version actually supplied. Do not name an
issuer, infer an applicable rule, or mark a source verified until its original
record exists. Platform Admin records provenance; the issuer is not an application
user and receives no role or configuration permission.

| Evidence ID | Assertion / filing family under review | Official issuer and source title | Stable identifier or retrieval location | Version, publication date and effective date | Applicable scope / assumptions | Accountable source owner | Supersession status | Review link | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| — | — | — | — | — | — | — | — | — | NOT SUPPLIED |

When a policy declares source provenance mandatory or makes a source-backed claim,
the supplied source set must cover every assertion it asks to activate. Other
authorized operational values may be entered without a source when their owning
policy permits it. The following scopes are provenance categories, not a
presumption that any rule exists or applies:

| Scope | Actual source evidence when the policy/claim requires provenance |
| --- | --- |
| Q01 currency and monetary representation | Official/legal or qualified accounting basis for any claim beyond the Product Owner's IRR/no-FX product boundary. |
| Q01 fiscal/calendar interpretation | Official/legal or qualified accounting basis for any claimed fiscal-period or historical-interpretation requirement. |
| Q01 precision and rounding | Versioned authoritative accounting/legal source for each proposed method, scale and rounding point, by value category. |
| Q01 inventory valuation | A source is required only if an authoritative financial valuation method is proposed; the current non-authoritative boundary supplies none. |
| Q02 taxpayer invoices and VAT/tax | Actual official sources for any validation/export claim proposed for that filing family. |
| Q02 payroll tax | Actual official sources for any validation/export claim proposed for that filing family. |
| Q02 employee insurance | Actual official sources for any validation/export claim proposed for that filing family. |
| Q02 contractor insurance and clearance | Actual official sources for any validation/export claim proposed for that filing family. |
| Q02 statutory books and reports | Actual official sources for any validation/export claim proposed for that filing family. |
| S04-S06 baseline assertions | Official source or reviewed accounting/legal basis for any regulated/accounting assertion the accepted architecture would treat as verified. |

## 3. Optional professional-review intake

Add review evidence only after it is actually supplied. It attaches to a policy or
source version as governance metadata; it grants no role, approval authority or
runtime permission and is not required for generic ERP development.

| Reviewer evidence ID | Reviewer or firm identity | Review discipline and scope | Qualification evidence / issuer / validity | Independence declaration | Conflict-of-interest assessment | Engagement or authority evidence | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| — | — | — | — | — | — | — | NOT SUPPLIED |

Each completed review must then be recorded separately:

| Review ID | Reviewer evidence ID | Reviewed artefact and immutable version/reference | Linked source evidence IDs | Review scope | Review date | Disposition | Conditions / limitations | Unresolved objections | Evidence location |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| — | — | — | — | — | — | — | — | — | NOT SUPPLIED |

If professional validation is claimed, record its actual coverage:

| Professional scope | Minimum artefacts to review |
| --- | --- |
| Accounting | S04 baseline; Q01 fiscal/calendar assertions; any proposed precision, rounding or valuation facts; and their linked source records. |
| Legal/regulatory | S06 baseline; Q02 filing/export assertions and source hierarchy; and their linked source records. |
| Cross-domain architecture | S05 baseline and the relevant S04/S06 boundaries, where the reviewer identifies accounting/legal consequences. |

## 4. D14-11 record

D14-11 is closed as a global development gate. A later professional disposition,
if supplied, is optional evidence for the exact policy/source versions it names and
does not become an ERP actor or universal release authority.

| Field | Required actual evidence | Current value |
| --- | --- | --- |
| Reviewer-issued disposition | Accepted, accepted with conditions, revision required, rejected, or pending. | NOT SUPPLIED — optional evidence |
| Reviewed versions | Immutable references for S04-S06, Q01/Q02 material and every relied-on source. | NOT SUPPLIED |
| Review evidence | Completed Review ID(s) and supporting artefact location(s). | NOT SUPPLIED |
| Date and scope | Actual review date and bounded subject coverage. | NOT SUPPLIED |
| Conditions, limitations and objections | Exact reviewer statement and closure evidence where applicable. | NOT SUPPLIED |

## 5. Evidence checklist before affected policy activation

Before publishing or applying a regulated/accounting-sensitive policy:

1. If the policy declares provenance required or makes a source-backed validation
   claim, supply official-source records for each assertion or filing family,
   including exact versions, dates, applicability and accountable owner.
2. The exact Platform policy version and controlled parameters being activated.
3. Tenant applicability, Tenant Owner approval and Tenant Admin application
   evidence where the policy is Tenant-selectable.
4. Optional professional evidence only when a professional-validation claim is
   intended; record qualifications, scope, disposition and limitations exactly.

Missing explicitly-required source or required policy/configuration fails closed.
This register authorizes no
statutory rate, formula, insurance rule, valuation method, precision/rounding value
or filing obligation.
