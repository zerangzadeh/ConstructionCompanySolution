Authority:

The Human Decision Authority has reviewed and adopted the following AI-assisted expert findings for the bounded non-production CEP-069 qualification.

This is the governing Human decision for implementation. The AI analysis is supporting material; the decisions below are Human-adopted.

# EXT-0018 — Adopted Payroll Statutory Review

Package:

`EXT0018-IR-1405-20261027-REVIEW-v1`

Cutoff:

`1405/08/05 — 2026-10-27`

Disposition:

`APPROVED_WITH_CONDITIONS`

Activation:

`AUTHORIZED_FOR_NON_PRODUCTION_AFTER_CONDITIONS_IMPLEMENTED_AND_VERIFIED`

No Production activation, final Production certification or final Human Sign-Off is authorized.

## 1. Applicability scope

This mapping applies to the bounded qualification population of ordinary employees subject to:

- Iranian Labour Law payroll rules;
- compulsory Social Security coverage;
- ordinary payroll income-tax treatment.

Do not generalize this mapping to special statutory populations without a separate rule/source, including:

- special insurance classes;
- self-employed persons;
- foreign nationals;
- statutory exempt populations;
- special public-sector payroll classes;
- other exceptional employment/insurance categories.

The runtime must fail closed when a population cannot be mapped to an approved statutory class.

## 2. Payroll tax thresholds

Adopt the retained official 1405 annual Payroll tax source values already present in the EXT-0018 source package.

Do not replace source-native annual thresholds with fabricated monthly statutory thresholds.

The source package and its hashes remain the authority for exact numerical brackets and exemption values.

## 3. Tax calculation basis — HUMAN DECISION

Approved calculation basis:

`CUMULATIVE_YTD`

For the general qualification scope, payroll tax must be calculated cumulatively from the start of the tax year.

Required runtime semantics:

1. determine cumulative taxable payroll income through the current payment;
2. apply the annual exemption and progressive annual brackets against cumulative taxable income;
3. calculate cumulative tax liability;
4. subtract tax already withheld for prior periods in the same tax year;
5. current-period withholding equals the resulting outstanding amount, subject to governed correction rules;
6. preserve prior-period and opening-YTD information when an employee enters the system during the tax year;
7. known legally relevant multi-source income must not be silently treated as zero where the applicable process requires it.

Conceptually:

`current_withholding = cumulative_tax_due - prior_withholding`

The implementation must not use:

`annual exemption/brackets ÷ 12`

as the universal statutory method.

A monthly derived display or estimate may exist only if it does not replace cumulative statutory computation.

If required YTD/opening data are unavailable, fail closed or require an explicit governed opening balance; do not invent zero history.

## 4. Taxable-component mapping

Use explicit versioned component classifications.

Each payroll component must map to one of the governed classifications supported by the reviewed source package, for example:

- taxable payroll component;
- statutory non-taxable/non-included component;
- conditionally taxable component;
- unsupported/unreviewed component.

Unsupported components must fail closed.

Do not reuse Billing VAT semantics for Payroll income tax.

The effective-date boundary of later tax amendments must be preserved. Do not retroactively rewrite finalized periods unless the governing source expressly requires retroactive treatment.

## 5. Social Security class — HUMAN DECISION

For the bounded ordinary compulsory-insurance qualification population, adopt:

- employee Social Security share: `7%`
- employer Social Security share: `20%`
- government financing share: `3%`
- unemployment insurance: additional `3% employer-paid`, only where the employee/population is legally covered by unemployment insurance

Do not model the government 3% share as an employee deduction.

Do not universally apply unemployment insurance to excluded populations.

Represent applicability through an explicit insurance class/profile rather than one hard-coded universal percentage.

Suggested governed profile identifier:

`IR_SSO_ORDINARY_EMPLOYEE_1405`

## 6. Insurance contribution base mapping

For the bounded ordinary-worker profile:

Components explicitly supported by the retained reviewed Social Security source may participate in the contribution base according to that source.

Use versioned component mappings rather than name-based inference.

The reviewed mapping must distinguish at minimum:

- insured remuneration;
- non-insured remuneration;
- conditionally insured remuneration;
- unsupported/unreviewed component.

Unsupported components fail closed.

Preserve:

- statutory work-day basis;
- 29/30/31-day handling where applicable;
- statutory minimum basis;
- statutory maximum/cap basis;
- effective dates and population exceptions.

Do not infer contribution treatment merely because a component is taxable or non-taxable. Tax and Social Security classifications are independent dimensions.

## 7. Housing/currentness correction

The earlier retained source observation concerning housing allowance must not be treated as final currentness if superseded by a later authoritative 1405 source.

Where the adopted review identifies a later authoritative housing amount/effective date:

- retain the earlier source as historical evidence;
- add the superseding source as a new immutable statutory version;
- apply the new version from its legally effective date;
- do not overwrite the historical source package.

If the authoritative superseding source itself is not retained with provenance/hash, acquire and retain it before activation.

## 8. Rounding — HUMAN GOVERNANCE POLICY

The retained statutory sources do not establish a sufficiently explicit universal rounding rule for every Payroll calculation stage.

Therefore approve the following bounded implementation policy for non-production qualification:

- internal calculations: high-precision Decimal arithmetic;
- no intermediate rounding unless a specific statutory/source rule requires it;
- final monetary statutory liability/withholding amount: round to whole IRR;
- rounding mode: `ROUND_HALF_UP`;
- scale: `0`;
- stage: `FINAL_LIABILITY`;

This is a Human-approved accounting/system policy where the reviewed statutory source is silent.

It must **not** be represented as a statutory rule.

If a later authoritative source specifies another rounding method for a particular calculation, that source-specific rule overrides this fallback policy for that calculation/version.

Suggested representation:

`rounding_mode = ROUND_HALF_UP`
`rounding_scale = 0`
`rounding_stage = FINAL_LIABILITY`
`authority_type = HUMAN_POLICY_WHERE_STATUTE_SILENT`

## 9. Retroactivity / supersession

Do not use one universal successor rule.

Each statutory source version must independently record:

- publication/issue date;
- legal effective date;
- supersedes relationship;
- whether treatment is prospective or retroactive;
- correction requirement for already processed periods.

If a source is legally effective from an earlier date than its publication/receipt date, create a later source version with the earlier legal effective date and perform governed delta/recalculation where required.

If a source amendment is explicitly prospective from issuance, do not rewrite earlier finalized periods.

No historical statutory evidence may be mutated.

## 10. Source/version governance

Every active Payroll statutory rule must be traceable:

`runtime parameter`
→ `statutory mapping`
→ `versioned policy`
→ `review decision`
→ `official source`
→ `source hash`

Missing source, missing accepted review, ambiguous effective date or unsupported population/component must fail closed.

Do not substitute model knowledge or undocumented defaults.

## 11. Filing/output schema

The existing BONIRA statutory source-package schema may be used as the internal governance envelope.

It is not an official INTA/SSO filing schema.

CEP-069 does not gain live statutory filing/export scope from this approval.

Any live filing/export format requires its own authoritative versioned schema/reference.

## 12. Conditions required before activation

Before non-production activation:

1. retain any missing superseding authoritative source identified by the adopted review, including provenance and hash;
2. implement `CUMULATIVE_YTD` tax calculation;
3. implement governed opening/prior-YTD handling;
4. implement explicit tax component classification;
5. implement `IR_SSO_ORDINARY_EMPLOYEE_1405` or equivalent governed insurance profile;
6. implement separate tax and insurance component mappings;
7. implement the approved fallback rounding policy;
8. preserve effective-date and supersession semantics;
9. verify fail-closed behavior for unsupported sources, populations and components;
10. run a fresh statutory delta qualification against the reviewed package.

## Human disposition

These findings and mappings are adopted by the Human Decision Authority.

Codex is authorized to implement all Development/non-production changes necessary to satisfy these adopted conditions, construct the governed schema1 payloads, perform source-linked activation in an isolated non-production environment, and execute CEP-069 acceptance verification.

Do not stop merely because implementation changes are required.

Fix attributable implementation, test, fixture, migration or evidence issues and continue.

Stop only for a genuinely new unsupported statutory interpretation, unavailable authoritative source, Production-only action or final Production Human Sign-Off.

After implementation:

`revalidate EXT-0018 → activate governed package in Non-Production → execute CEP-069 → verify AC/DoD → reconcile Registry/GATE-11`

No Git write unless separately authorized.
