# P1-S14 remaining decision packet

**Prepared:** 2026-09-28. **Final disposition:** 2026-09-29.
**Status:** P1-S14 COMPLETE; D14-10/D14-11 REVISED BY PRODUCT OWNER.

This packet records the P1-S14 Configuration Authority decisions. The
Product Owner decision that `OrganizationSettings` is the sole owner of every
organization-level configurable setting is **ACCEPTED AND CLOSED**. It is not
reopened here. The final Product Owner decision removes professional review as a
global development gate and authorizes the versioned policy/localization foundation.

No statutory/accounting fact is validated by this packet. Unknown regulated values
remain unset/inactive and affected behavior fails closed.

## 1. S04-S06 dispositions

### D14-01 — S04 Accounting/posting ADR

**Exact decision required:** dispose
[`ADR_P0_S04_ACCOUNTING_POSTING.md`](ADR_P0_S04_ACCOUNTING_POSTING.md) as target
architecture for Accounting-only journal authority, operational-source ownership,
source/version/event identity, idempotent posting, immutable reversal/replacement,
period controls, reconciliation and legacy `Payment` containment.

| Option | Practical consequence |
| --- | --- |
| A — Accept after Q01/Q02 evidence | Establishes the target ownership and interface contract while retaining separate implementation, pilot, migration and release gates. Does not approve a chart of accounts, rate, filing behavior or package implementation. |
| B — Accept with explicit revisions | Establishes only the revised text. The Product Owner must list every changed clause; affected dependency and consistency review must occur before acceptance. |
| C — Reject or defer | P1-S14 remains blocked because currency/fiscal/configuration consumers lack an accepted financial boundary; P2/P3 remain blocked as well. |

**Recommended default:** A, only after Q01/Q02 decisions and qualified evidence are
attached. The ADR already preserves operational-domain ownership and prevents a
parallel mutable ledger.

**Minimum Product Owner decision:** `D14-01 = A`, or `B` with exact replacement
clauses, or `C` with the reason. For A/B, identify the accepted ADR revision/date.

**Recorded decision:** the Product Owner held D14-01 `PENDING` until D14-04 through
D14-11 were incorporated into the architecture baseline, then directed Option A if
no contradiction remained. The incorporation and consistency review found no
contradiction. **D14-01 is therefore Option A — ACCEPTED AS TARGET ARCHITECTURE.**
This is not implementation authorization; the professional-evidence gate below
remains blocking.

### D14-02 — S05 Budget/project-cost ADR

**Exact decision required:** dispose
[`ADR_P0_S05_BUDGET_PROJECT_COST.md`](ADR_P0_S05_BUDGET_PROJECT_COST.md) as target
architecture for immutable accepted budget baselines, explicit CBS/cost-center
classification, separate commitment/accrual/actual/paid/forecast facts, source
lineage and containment of editable Project totals.

| Option | Practical consequence |
| --- | --- |
| A — Accept after Q01/Q02 evidence | Establishes the semantic ownership boundary and prevents budget/cash/actual conflation. Detailed budget policy, pilot and P4 implementation remain separately gated. |
| B — Accept with explicit revisions | Permits a different target boundary, but every revised baseline, classification, recognition or reconciliation clause must be stated and reviewed for S04 consistency. |
| C — Reject or defer | P1-S14 remains blocked where currency/fiscal/valuation configuration must serve future project-cost facts; P4 design remains without an accepted authority model. |

**Recommended default:** A, while explicitly retaining P4 budget-policy and
migration gates and the Q01 valuation boundary below.

**Minimum Product Owner decision:** `D14-02 = A`, or `B` with exact replacement
clauses, or `C` with the reason. For A/B, identify the accepted ADR revision/date.

**Recorded decision:** **D14-02 = Option A — ACCEPTED AS TARGET ARCHITECTURE**, with
all independent P4 policy, pilot, migration and implementation gates preserved.

### D14-03 — S06 Regulatory/contract-policy ADR

**Exact decision required:** dispose
[`ADR_P0_S06_REGULATORY_CONTRACT_POLICY.md`](ADR_P0_S06_REGULATORY_CONTRACT_POLICY.md)
as target architecture separating effective-dated regulatory rule versions,
versioned contract commercial terms and Tenant presentation/configuration, with
applied-version lineage and immutable historical snapshots.

| Option | Practical consequence |
| --- | --- |
| A — Accept after Q01/Q02 evidence | Establishes the owner/version/snapshot boundary and prevents mutable `BillingPolicy` defaults from becoming certified legal rules. Rule values, sources, precedence and regulated integrations remain separately gated. |
| B — Accept with explicit revisions | Allows a revised ownership or version contract, but every affected field owner, precedence rule and historical-correction consequence must be supplied and reviewed. |
| C — Reject or defer | P1-S14 remains blocked; no safe regulatory-version or contract-term foundation may be implemented and current `BillingPolicy` remains compatibility behavior only. |

**Recommended default:** A. It is the narrowest boundary that preserves legal
source provenance and historical calculation reproducibility without inventing a
rate or rule.

**Minimum Product Owner decision:** `D14-03 = A`, or `B` with exact replacement
clauses, or `C` with the reason. For A/B, identify the accepted ADR revision/date.

**Recorded decision:** **D14-03 = Option A — ACCEPTED AS TARGET ARCHITECTURE.** This
accepts the ownership/version/snapshot separation, not any statutory rate, rule
value, precedence outcome, filing behavior or implementation package.

## 2. Q01 product/accounting policy decisions

### D14-04 — Currency scope

**Exact decision required:** choose the product currency boundary for Tenant base
configuration, transactions and later accounting/settlement.

| Option | Practical consequence |
| --- | --- |
| A — IRR-only product | Lowest implementation and reconciliation complexity, but prevents foreign-currency contracts/settlement and makes later expansion more disruptive. Rial/Toman display still requires explicit labeling and conversion-for-display rules. |
| B — One operational base currency per Tenant, multi-currency-ready records | Keeps each Tenant's authoritative base currency explicit, requires every monetary fact to carry a currency, and preserves future foreign-currency expansion without enabling FX accounting now. Cross-currency calculation/posting is blocked until a reviewed FX policy exists. |
| C — Full multi-currency from first financial release | Supports transaction, settlement and reporting currencies plus rates, sources, gains/losses and revaluation, but materially enlarges P1/P2/P3 scope and professional-review burden. |

**Recommended default:** B. It avoids an IRR hard-code and avoids pretending that
FX accounting is already approved. No implicit conversion or Tenant-selected
arbitrary currency precision is permitted.

**Minimum Product Owner decision:** select A/B/C; state the permitted Tenant base
currency set for initial release; confirm that Toman, if displayed, is a labeled
presentation unit rather than an ambiguous stored currency; and for B confirm that
cross-currency operations fail closed until separately approved.

**Recorded decision:** **D14-04 = Option B.** Every Tenant has one explicit base
currency; initial support and canonical monetary storage/display are IRR. Toman is
neither a display denomination nor an accounting currency in the current scope.
The architecture remains multi-currency-ready, but FX transactions, conversion,
revaluation and exchange-rate accounting are disabled. Unsupported conversion
fails closed; no exchange rate may be inferred or silently applied. A later
formally accepted accounting design is required to change this boundary.

### D14-05 — Fiscal and calendar boundary

**Exact decision required:** choose canonical storage/time semantics, display
calendar ownership and the calendar in which a Tenant fiscal-year boundary is
defined.

| Option | Practical consequence |
| --- | --- |
| A — Gregorian storage/display/fiscal boundary only | Simplest, but does not meet the Persian-first Jalali operating expectation. |
| B — Canonical UTC instants and ISO/Gregorian dates; Tenant display calendar and explicit fiscal-boundary calendar | Keeps storage/interchange deterministic, supports Jalali presentation and permits the fiscal boundary to be stated in its actual calendar. Requires calendar type plus effective boundary/version, not an ambiguous month/day pair. |
| C — Store Jalali-formatted values as primary data | Creates interoperability, ordering and validation risk and duplicates date semantics across integrations; conversion defects become historical-data defects. |

**Recommended default:** B. Instants remain timezone-aware and Tenant timezone is
used only for business-date derivation/presentation. Fiscal periods later belong
to Accounting; `OrganizationSettings` owns the Tenant defaults and localization
choice, not posted-period history.

**Minimum Product Owner decision:** select A/B/C; for B select the initial display
calendar and fiscal-boundary calendar policy, and confirm that later changes are
effective-dated and never rewrite finalized history.

**Recorded decision:** **D14-05 = Option B.** Persist timestamps in UTC and use
ISO/Gregorian-compatible internal date storage/processing. The user interface
displays Jalali dates. Every Tenant requires explicit fiscal-calendar
configuration. Calendar presentation remains separate from persistence, and
effective-dated changes never rewrite historical dates or transaction meaning.

### D14-06 — Precision and rounding

**Exact decision required:** approve where precision comes from, when rounding
occurs, the default rounding method and how regulated exceptions are versioned.

| Option | Practical consequence |
| --- | --- |
| A — One Tenant-wide scale/method | Easy to operate but incorrect for mixed money, quantity, unit-price, percentage and regulated calculation contexts. |
| B — Platform-governed type/currency scales plus versioned domain rounding policies | Uses `Decimal`, keeps money/quantity/rate precision distinct, rounds only at declared boundaries, records method/scale and supports reviewed regulatory exceptions. More policy metadata and tests are required. |
| C — Free per-Tenant arbitrary formulas | Flexible but creates audit, comparability and safety risk and conflicts with the bounded declarative-policy rule. |

**Recommended default:** B. Use a closed platform catalogue of rounding methods;
no binary float, silent fallback or intermediate rounding. The exact default
method and regulated line-versus-document rounding must be confirmed by the
accounting/legal reviewer rather than inferred here.

**Minimum Product Owner decision:** select A/B/C; for B approve the closed-catalogue
model and provide or delegate to the named accounting reviewer the exact default
method, money/quantity/rate scales and rounding boundaries. The decision is not
complete while those values are `OPEN`.

**Recorded decision:** **D14-06 = Option B.** Precision policy is platform-governed
and versioned by domain; arbitrary Tenant formulas are prohibited. Policies must
distinguish money, quantities, rates/percentages, intermediate calculations and
final document totals, with explicit traceable method, scale and rounding points.
Final accounting/legal values remain **«نیازمند بررسی قانونی/حسابداری»** until
professionally validated; none is inferred by this decision.

### D14-07 — Valuation policy

**Exact decision required:** decide whether P1-S14 establishes any financial
inventory/project-cost valuation behavior or only the authority boundary for a
later reviewed policy.

| Option | Practical consequence |
| --- | --- |
| A — Operational quantity only until P8.1/P2 review | P1-S14 introduces no FIFO, weighted-average, standard-cost or revaluation behavior. Future valuation is a versioned Inventory/Accounting policy, not a miscellaneous Tenant setting. Financial inventory/project-cost outputs remain unavailable until approved. |
| B — Select one valuation method now | Enables earlier financial costing, but requires detailed handling for returns, transfers, negative stock, landed cost, close/reopen and source-to-GL reconciliation plus professional evidence. |
| C — Tenant-selectable multiple methods now | Maximum flexibility but substantially increases migration, reconciliation, comparability and control complexity. |

**Recommended default:** A for P1-S14. This is a deliberate initial-scope decision,
not a silent zero-value or implied valuation method.

**Minimum Product Owner decision:** select A/B/C. For A, explicitly confirm that
P1-S14 and current Inventory remain non-authoritative for financial valuation. For
B/C, supply the exact method/scope and accounting-review evidence before S05 can be
accepted.

**Recorded decision:** **D14-07 = Option A.** P1-S14 and current Inventory may own
physical quantities and operational facts but establish no authoritative financial
valuation method. FIFO, weighted average, specific identification and every other
accounting valuation method remain outside authority until separately approved
with accounting evidence.

## 3. Q02 legal/accounting evidence decisions

### D14-08 — Filing versus export boundary

**Exact decision required:** choose what the product legally purports to do in the
initial release for statutory/tax/insurance/accounting outputs.

| Option | Practical consequence |
| --- | --- |
| A — Evidence-backed export only | Product prepares reviewed exports/reports and retains source/version evidence; a qualified human or external system remains responsible for filing. Lowest representation and integration risk. |
| B — Assisted submission | Product transmits to selected authorities/providers and records requests/responses, but requires separately approved credentials, schemas, idempotency, operations and legal acceptance. |
| C — Product-managed filing/system of record | Broadest customer promise and highest legal, operational, security, availability and professional-signoff burden. |

**Recommended default:** A for the first release. Each export must be labeled with
scope, rule/source versions and a warning where professional validation is not
complete. B/C require later separately authorized integration packages.

**Minimum Product Owner decision:** select A/B/C separately for each intended
filing family (at minimum taxpayer invoice, VAT/tax, payroll tax, employee
insurance, contractor insurance/clearance and accounting books), or explicitly
mark that family out of initial release.

**Recorded decision:** **D14-08 = Option A for the initial release** across taxpayer
invoices, VAT/tax, payroll tax, employee insurance, contractor insurance/clearance
and statutory books/reports. The product boundary is preparation, validation and
controlled generation/export for human filing or external-system submission. It
does not claim autonomous filing; any later submission capability needs separate
design, legal validation and formal acceptance.

### D14-09 — Authoritative versioned sources

**Exact decision required:** approve the admissible source hierarchy and minimum
evidence stored for every legal/accounting rule version.

| Option | Practical consequence |
| --- | --- |
| A — Official primary sources are authoritative; secondary sources are commentary only | Strongest provenance. Requires source owner, issuing authority, identifier/title, publication/version/effective dates, retrieval date, immutable reference or retained copy/hash where permitted, applicability notes and supersession links. |
| B — Reviewed professional interpretation may be authoritative when primary text is ambiguous | More operationally usable, but the interpretation, author/qualification, scope, assumptions, linked primary sources and approval must be versioned and cannot silently replace the primary text. |
| C — Vendor/blog/current-practice summaries may directly drive rules | Fastest but unacceptable provenance and update risk for regulated calculations. |

**Recommended default:** A plus B only as an explicitly reviewed interpretation
layer. C must never activate a regulated rule.

**Minimum Product Owner decision:** approve the A/B hierarchy; name the accountable
source owner for accounting and for legal/regulatory material; identify the
official publisher/source class for each initial filing family; and approve the
minimum version/provenance fields. Actual sources and versions must then be
provided and reviewed—this policy decision alone does not satisfy the evidence
gate.

**Recorded decision:** **D14-09 = Option A with limited Option B.** Identifiable
official legal/regulatory sources by version, publication or effective date are
primary authority. A versioned professional interpretation may supplement an
official source only when it cites that source and records author/reviewer, scope
and assumptions; it never silently replaces the official authority. Vendor docs,
blogs and informal material are not authority. Actual sources and applicable
versions are still **OPEN / REQUIRED EVIDENCE** before any rule is verified.

### D14-10 — Optional accounting/legal review evidence

**Final Product Owner decision:** a `Professional Reviewer` is not a mandatory
application role, runtime actor, approval authority or development prerequisite.
External professional review may be attached to a source/policy version as optional
governance evidence. It records identity, qualification, scope, independence,
date, disposition and limitations when actually supplied, but grants no ERP role or
configuration authority.

Configuration authority belongs to Platform Admin, Tenant Owner and Tenant Admin
under the explicit boundary below. Government, tax, insurance, legal and other
external authorities are source issuers, not system actors.

### D14-11 — Development and activation disposition

**Final Product Owner decision:** D14-11 is **CLOSED AS A GLOBAL DEVELOPMENT
GATE**. No reviewer-issued acceptance is required to continue P1-S14/P1-S15 or
unrelated ERP development. This does not validate an unknown legal/accounting fact.

Actual regulated/accounting behavior may activate only from published,
effective-dated policy/configuration owned by an authorized Platform or Tenant
role. Source provenance is mandatory only where that policy explicitly declares a
source requirement; it is otherwise optional metadata and never blocks ordinary
Tenant configuration. Missing policy, unknown required parameters, a missing
explicitly-required source, unsupported applicability or an inactive version
fails closed. Optional professional evidence never substitutes for required
source/version traceability.

## 4. Final configuration-authority boundary

The accepted flow is:

`Official/External Source -> Versioned Platform Policy/Localization Catalogue -> Tenant Policy Selection -> Tenant Operational Configuration`

- Platform Admin owns source metadata, allowed policy structures and Platform-owned
  localization versions; this does not mean every actual value is predetermined by
  Platform.
- Tenant Owner approves/selects important Tenant policy choices within that space.
- Tenant Admin applies approved choices and enters/maintains authorized operational
  Tenant values within field-specific constraints.
- `OrganizationSettings` remains the sole Tenant owner for direct organization
  settings; effective-dated shared policy is stored separately and referenced.
- Tenants cannot create arbitrary formulas or unrestricted legal/accounting rules.
- Unknown regulated values remain draft/unset/inactive; consumers fail closed.

| Configurable field/family | Authoritative record | Platform Admin authority | Tenant Owner authority | Tenant Admin authority |
| --- | --- | --- | --- | --- |
| Logo, language/locale, timezone and project/contract/site/document prefixes | `OrganizationSettings` | Defines code-owned validation and allowed boundaries | May maintain through `company_settings.change` | May maintain through `company_settings.change` |
| Current base currency and fiscal-year start month/day | `OrganizationSettings` | Defines structure and validation boundaries; current implementation supports IRR only | May maintain within the supported boundary; approves any future important policy selection | Enters/maintains supported operational values |
| Display-calendar and fiscal-calendar policy options | `PlatformPolicyVersion` plus `TenantPolicySelection`; resulting direct Tenant setting remains in `OrganizationSettings` where applicable | Defines/publishes allowed, versioned options | Approves the selected published option | Applies the approved selection; no arbitrary override |
| Precision categories, rounding methods and rounding boundaries | `PlatformPolicyVersion` plus `TenantPolicySelection`; later field-specific Tenant configuration where explicitly authorized | Defines/publishes structures and any Platform-owned values; unknown values remain unset | Approves important policy/business choices | May enter permitted Tenant values or apply an approved option; cannot define arbitrary formulas |
| Tax/regulatory/accounting rule-set version, filing/export mode and insurance/regulatory configuration | `PlatformPolicyVersion` plus `TenantPolicySelection`; field-specific Tenant configuration where authorized | Defines structures, Platform/localization values and whether provenance is required | Approves applicability/selection | May enter/apply effective Tenant values within RBAC and validation constraints; missing required configuration fails closed |

The P1-S15 foundation records selection/application and retains direct operational
values in `OrganizationSettings`; it does not add a generic unrestricted Tenant
parameter bag, copy policy parameters into settings or activate a consuming
domain. A later field-specific package may add controlled, effective-dated Tenant
values when required. Such a consumer switch is separately authorized and must not
introduce a second authority or dual write.

| Concept | Current architectural representation | Boundary |
| --- | --- | --- |
| External regulatory source | `PolicySource` | External provenance only; never an ERP actor or configuration authority |
| Platform/localization policy | `PlatformPolicy` and `PlatformPolicyVersion` | Platform-owned structure/version and any Platform-owned values |
| Tenant-specific configuration | `OrganizationSettings`, `TenantPolicySelection`, or a future field-specific versioned record | Entered/approved/applied only by authorized Tenant roles; never merged into source metadata |
| Runtime transaction data | Consuming domain record plus applied policy/configuration version snapshot | Business fact; finalized history is not reinterpreted when configuration changes |
| Optional governance/evidence metadata | `PolicyReviewEvidence` | Optional traceability only; no role, approval authority or global gate |

Every future consuming domain must pin or snapshot the applied policy and Tenant
configuration version. A later parameter change creates a new effective version
and must not silently rewrite finalized historical transactions.

## 5. Final gate reassessment

D14-01 through D14-09 remain accepted and internally consistent. Revised D14-10
and D14-11 remove only the obsolete mandatory-reviewer gate. Source provenance is
available and mandatory only for a policy explicitly marked as source-required;
it is not a prerequisite for ordinary Tenant configuration or generic development.

No statutory rate, Chart of Accounts, filing behavior, valuation method, precision
value or rounding value is asserted by this closeout.

## 6. Authorized split and P1-S14A implementation closeout

The Product Owner split P1-S14 into:

- **P1-S14A — Configuration Authority:** authorized only for
  regulatory-independent implementation; and
- **P1-S14B — Policy/source governance:** superseded by the final Product Owner
  decision recorded in sections 3-5; optional review evidence is not a global gate.

P1-S14A is complete. Migration `organizations.0036` makes new authoritative base
currency IRR and fails closed on missing/unsupported migration evidence without
conversion. The settings service no longer recreates configuration from legacy
fields or dual-writes timezone/currency. It locks the authoritative row, retains
active-Tenant/membership/business-permission enforcement and records before/after,
changed-field and authority audit evidence. Tenant creation writes settings only
to `OrganizationSettings`. Equipment, Safety and Quality timezone consumers are
switched to that authority. Legacy `Organization.timezone`/`currency` fields remain
present and are not removed or authoritative.

No tax/VAT rule, filing behavior, accounting precision/rounding value, inventory
valuation method, statutory numbering or other regulatory/accounting-sensitive
behavior was activated. Thirty targeted tests passed, as did Django system and
migration-state checks plus targeted Ruff checks. P1-S14A did not authorize the
legacy-field contract stage.

## 7. Historical P1-S14B execution gate recheck

**Rechecked:** 2026-09-29. The Product Owner instructed execution of P1-S14B, so
bounded package authorization is satisfied. Repository evidence was checked before
implementation. No record supplies the actual official source versions, a named
qualified independent reviewer with qualification/scope/independence evidence, or
the professional disposition required by D14-11. The professional review of the
affected S04-S06 baseline and any proposed accounting precision/rounding facts is
therefore also absent.

At that time the P1-S14B entry gate was **NOT SATISFIED**. In accordance with the
then-current D14-09 through
D14-11, no legal/accounting assertion, precision or rounding value, regulatory
rule, filing behavior, valuation policy, application code, schema, migration or
runtime behavior was changed. The next executable session is evidence intake and
recording against exact source and architecture versions; implementation may begin
only after the resulting D14-11 disposition closed or explicitly conditioned the
relevant scope. Sections 3-5 now supersede that global blocking interpretation.

## 8. Source and optional-review evidence register

The [P1-S14B evidence register](P1_S14B_PROFESSIONAL_EVIDENCE_REGISTER.md) is the
repository structure for source provenance and optional professional evidence. It
is not a global stage gate and creates no application actor.

## 9. P1-S14 closeout and P1-S15 handoff

P1-S14 is **COMPLETE**. P1-S14A established `OrganizationSettings` authority and
removed runtime dual-write/read-repair. The final governance decision defines the
internal authority hierarchy, versioned policy flow, source provenance and
fail-closed boundary without inventing regulated facts.

P1-S15 is authorized as the technical policy/localization foundation only:
versioned Platform policies, external-source metadata, optional review evidence,
Tenant Owner approval, Tenant Admin application, permission enforcement, audit and
policy-specific fail-closed resolution. It does not activate a regulatory calculation, filing,
precision/rounding value, valuation method, `BillingPolicy` migration or P1-S16.
