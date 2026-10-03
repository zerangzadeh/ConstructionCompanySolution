# ADR P0-S06: Regulatory rules, contract terms and tenant billing settings

**Date:** 2026-09-25. **Status: ACCEPTED AS TARGET ARCHITECTURE ON 2026-09-28;
P1-S14 GOVERNANCE CLOSED 2026-09-29; P6-S01–S06 OWNERSHIP/SNAPSHOT CORRECTION
IMPLEMENTED 2026-10-02 WITH ACCEPTANCE PENDING; P6-S26–S32 BOUNDED CONSUMERS
IMPLEMENTED 2026-10-03 WITH ACCEPTANCE PENDING; RULE VALUES/LIVE ACTIVATION STILL
GATED.**

> Implementation reconciliation: P6-S01–S06 replaces the historical
> `BillingPolicy` evidence described below with `TenantBillingConfiguration`,
> `ContractTermVersion`, the existing reviewed `PlatformPolicyVersion` plus active
> Tenant selection, and pinned claim evidence. See
> [the implementation packet](P6_S01_S06_BILLING_TERMS_REGULATORY_IMPLEMENTATION.md).
> P6-S26–S32 now reuses the same authority for policy-pinned taxpayer invoices,
> contractor-compliance assessments and provider-neutral export/test evidence;
> see the [bounded implementation packet](P6_S26_S32_TAXPAYER_CONTRACTOR_COMPLIANCE_IMPLEMENTATION.md).
> Sections describing the former schema remain historical rationale, not current
> runtime behavior.

Scope: P0.1/PPC-01/PPC-06, following the
[S05 handoff](../ROADMAP_EXECUTION_PLAYBOOK.md#compact-p0-s06-handoff).
[Roadmap P1.2](../../ROADMAP.md#p12-configuration-and-master-governance-corrections)
owns the correction; P6.3 and other consumers retain their separate gates.
Target ownership follows the [Data Model](DATA_MODEL.md#4-master-data-catalogue)
and [effective-history rules](DATA_MODEL.md#8-effective-dating-and-snapshots).
S04/S05 are accepted as target architecture. This ADR supplies their
applied-version lineage; section 7 incorporates the later Product Owner currency,
calendar, valuation and filing-scope decisions without choosing a statutory rate,
recognition rule, tax/insurance value or activated filing behavior.

## 1. Current evidence and correction boundary

- [BillingPolicy](../../apps/billing/models.py) is one mutable tenant row with
  numbering/period/precision, tax/insurance, retention and advance-recovery fields.
  [update_billing_policy](../../apps/billing/services.py) validates permission,
  locks the organization/policy and saves supplied allowed fields.
- In the same service, `_policy_snapshot` copies 14 fields; `create_progress_claim`
  stores that snapshot. `recalculate_progress_claim` accepts only drafts and uses
  the saved policy, verified measurements and baseline rates. Recalculation can
  change draft measurement results; it does not resolve policy from the live row.
- `create_progress_claim_revision` and `_copy_returned_claim_revision` carry the
  original policy snapshot. Existing tests cover rounding/adjustments, revision
  source reuse and immutable submitted/returned history in
  [billing tests](../../apps/billing/tests.py). These were inspected, not run.
- **Stored versus effective behavior:** `tax_basis`/`insurance_basis` accept
  `gross` or `net_before_tax`, but the inspected recalculation loop always uses
  gross. `allow_partial_periods`/`allow_late_measurements` are saved/snapshotted,
  with no consuming branch found in Billing Python code. `period_boundary` does
  have a creation-time check; it is not evidence that all period options work.
  Retention/recovery caps are applied per calculation with `min(amount, cap)`;
  zero caps yield zero, not unlimited or a proven cumulative contract balance.
- [Migration 0003](../../apps/billing/migrations/0003_progressclaim_claimadjustment_progressclaimitem_and_more.py)
  introduced these fields and claim snapshots. Current claims lack dedicated
  party/currency snapshot fields, as documented in the
  [Billing architecture](BILLING_AND_PROGRESS_CLAIMS.md#ownership-and-data-model).

These narrow findings inform future acceptance tests; they do not authorize fixes
in S06. Historical results must retain their actual calculation semantics, even
when saved metadata described an unimplemented choice. No current rate or default
is certified as legally correct.

## 2. Proposed ownership of every policy field

| Existing field(s) | Target authority and boundary |
| --- | --- |
| `claim_number_scope` | Tenant numbering settings with versioned scheme and collision-safe allocation; issued identifiers remain unchanged. |
| `money_decimal_places` | Tenant currency/precision settings constrained by accepted currency and applicable regulatory calculation rules; display preferences cannot override calculation precision. |
| `period_boundary`, `allow_partial_periods`, `allow_late_measurements` | Tenant defaults for new contracts; accepted contract-term version owns the resolved commercial schedule/measurement terms. Billing enforces registered eligibility rules; regulatory constraints remain applicable. |
| `tax_rate`, `tax_basis` | Reviewed effective-dated regulatory rule version plus validated applicability facts. Contract tax presentation/classification may be input, never an unrestricted override of a mandatory rule. |
| `insurance_rate`, `insurance_basis` | Reviewed regulatory rule/applicability where statutory; explicitly classified contract terms where a commercial deduction. The generic legacy field is insufficient to decide which meaning applies. |
| `retention_rate`, `retention_cap` | Contract-term version: basis, rate, cap meaning/currency/scope, release conditions and calculation order. Distinct statutory withholding, if applicable, remains separately identified. |
| `advance_recovery_rate`, `advance_recovery_cap` | Contract-term version and authoritative advance/recovery evidence; define per-claim versus cumulative cap and outstanding-advance limit before implementation. |
| `allow_negative_corrective_claims` | Tenant-configured Billing correction policy using registered transitions; bounded by contract/regulatory constraints, permissions and approval. A boolean cannot grant authority or alter finalized history. |

Platform/Tenant owns organization settings; Contracts owns commercial terms;
governed regulatory configuration owns approved rule versions and provenance;
Billing owns claim calculation, resolved snapshots and application evidence.
Accounting, Treasury and AP/AR retain financial authority under
[S04](ADR_P0_S04_ACCOUNTING_POSTING.md); cost projections consume the resulting
source lineage under [S05](ADR_P0_S05_BUDGET_PROJECT_COST.md).

No competing settings row or generic tenant expression engine. Reuse existing
organization-setting ownership during the P1.2 correction. Proposed rule families
are platform-registered typed parameters/calculators, not tenant Python, SQL or
network callbacks. Annual VAT/tax, invoice schemas, payroll/employee insurance and
contractor clearance stay within Roadmap scope; this session designs the shared
contract, not those rules. All unverified rules remain **«نیازمند بررسی قانونی»**.

## 3. Effective versions and deterministic resolution

Regulatory versions record rule family, jurisdiction/applicability, effective
interval, source publication/reference and retained evidence, publication/recording
times, optional review evidence, units/currency and calculator/schema version. Distinguish
the time a rule applies from the time the system learned/approved it. Proposed
interval convention is `[valid_from, valid_to)`; actual dates and date-selection
rules require review. Contract versions retain signed/amendment evidence, scope,
effective interval and accepted terms. Tenant setting changes retain actor/time
and versions wherever calculation or identity depends on them.

Proposed lifecycle: `draft -> in_review -> published/accepted`, or returned draft/
rejected with reason. Publication freezes content and approval evidence. A successor
records supersession/correction links; never edit a published payload or erase its
historical interval. Controlled activation/withdrawal evidence determines eligible
versions without deleting prior selections. Publishing a retroactive correction
requires an impact list and review, not automatic rewriting of past claims.

For each rule family the platform defines the applicability dimensions, relevant
business date and supported basis/order. The reviewed rule determines whether that
date is performance, invoice, payment or another event; do not assume claim creation
date, calendar year, tenant timezone or receipt date universally decides it.

Resolution at draft creation or an explicit new revision:

1. Resolve authenticated tenant and validate project, contract, baseline, party
   and required applicability facts; select eligible accepted contract terms.
2. Resolve the rule-family business date and exactly one approved applicable
   regulatory version for each required family. Select versioned tenant settings.
   Missing, unverified, overlapping or conflicting applicability blocks affected
   acceptance; never use zero or the latest version as a silent fallback.
3. Apply mandatory regulatory constraints, accepted contract inputs and resolved
   settings through a registered calculator. Commercial defaults only fill fields
   while preparing terms; an accepted contract is not dynamically inherited from
   later tenant defaults. Unknown rule combinations or unspecified order are errors.
4. Save the resolved versions and material inputs/results with the draft. A period
   crossing a rule/term boundary requires an explicitly supported split or reviewed
   single-date policy; never blend rates or choose a boundary automatically.

Tenant-specific versions, applicability facts, terms and snapshots are tenant
scoped. Shared legal source material may later be a separately approved platform
catalogue; it grants no tenant access or automatic applicability. Tenant activation
and calculation evidence must remain explicit and isolated.

## 4. Calculation and historical snapshot contract

Retain source UUID/version/line and measurement cutoff; tenant/project/contract and
party identity snapshots; source currency/unit, relevant dates/calendar/timezone;
settings, term, rule and calculator versions; rates, bases, adjustment order/sign,
rounding stages, cap scope/prior consumption and resulting gross/adjustment/net
amounts. Keep rejection/selection explanations and approval/audit evidence.
Use Decimal with explicit percent-versus-fraction semantics and conversion rules.
Version links enable lineage; immutable input/output snapshots preserve historical
meaning if source labels or masters later change.

Recalculation of an existing draft uses its pinned policy package. Refreshing
terms/rules is an explicit previewed revision with a reason and result diff, not
an incidental recalculation. At submission, validate package eligibility and any
live cumulative balance evidence. If stale, require an explicit recalculation/new
revision and renewed review; never alter submitted totals during approval.
Approved/returned history and submission snapshots remain immutable.

Where cumulative caps are approved, lock/re-read the authoritative contract/advance
balance and define submission reservations and approval/release behavior. Concurrent
claims cannot consume the same remaining allowance. Changing a term version cannot
reset consumed balances. Per-claim and cumulative caps are distinct semantics;
neither is selected merely by migrating the legacy field.

Publication/activation, claim acceptance and correction services recheck membership,
tenant lifecycle, object scope, business permissions and separation inside atomic
transactions. Use a consistent lock order for version-selection controls, contract,
cap balances and claim. Prevent conflicting published selections with constraints
where expressible and serialized validation for registered applicability rules.
Persist transition, resolved evidence, workflow completion and audit together.
Stable tenant/aggregate/action/request identities make retries idempotent; changed
payload with the same key conflicts. A rule upgrade never reposts the same source
event: downstream financial correction follows S04 reversal/replacement contracts.

Preparation, publication/activation, contract amendment and claim revision require
separately defined permissions and maker/checker policy. Optional professional
evidence is metadata, not a mandatory actor or approval step.
Future implementation must register codes, catalog/default grants and service/view
checks with negative tests. Existing `COMPANY_SETTINGS_CHANGE` is current evidence,
not authorization for every future role. Use existing workflow services. Recorded
Q04 selections govern project/support/privileged paths. Final G3 — Revised with Protected Operations prohibits
Self-Approval for Protected Operations while allowing platform/tenant configuration
for non-protected business operations; named security/workflow/legal
review and risk evidence remain open. Suspended/cancelled lifecycle rules
and protected-source read/export checks remain mandatory.

## 5. Containment and correction sequence

1. Accept the ownership ADR, resolve Q01/Q02 and define effective-date,
   basis/order and cap semantics before affected behavior is activated.
2. In approved P1.2 work, expand settings/contract/rule version support and the
   resolved-package contract. Inventory policy readers/writers, forms/Django Admin,
   migrations, fixtures and financial consumers before switching authority.
3. Preserve `BillingPolicy`, original JSON snapshots, submission evidence and
   migration history. Treat the legacy row as provenance/default input, not proof
   of a signed contract or reviewed statutory rule. Never mass-publish its rates.
   Historical snapshot links may identify a labeled legacy package; do not invent
   source dates, reviewer approvals, currency or legal validity from current settings.
4. Compare old/new results by claim and adjustment using the actual legacy gross
   basis, per-claim caps and calculator behavior. Flag saved-but-unapplied fields
   and missing evidence as exceptions. Explain intended differences and approve
   the correction; no silent historical recalculation or forced balancing entry.
5. Switch one policy authority per new document. Existing draft/returned packages
   stay pinned or move through an explicit approved revision. New documents cannot
   bypass unresolved regulatory inputs through legacy fallback. Reconcile source,
   snapshot, adjustment and posting lineage before rollout.
6. Rehearse rollback without deleting accepted versions or reverting financial
   history. After accepted/posted use, prefer controlled forward correction;
   any authority rollback must preserve and reconcile those documents. Remove
   compatibility only after dependency/retention checks, validation and separate
   explicit approval. Q03 and P0.2 recovery gates still apply.

## 6. Static review cases and implementation gates

These are hypothetical software-contract examples, not legal rates or runtime tests.

| Case | Expected result |
| --- | --- |
| Legacy gross 60; tax 10%, insurance 5%, retention 10% capped at 3, recovery 10% capped at 2 | +6 -3 -3 -2 = -2 adjustments; net 58. Reproduces the inspected test's arithmetic, not certification of the rules. |
| Claimed `net_before_tax` with legacy gross 60 | Legacy results retain gross-basis evidence. A future reviewed basis/order change must be previewed and versioned; the metadata label alone cannot justify a changed historical result. |
| Hypothetical rule R1 ends at date D; R2 begins at D | Under the approved half-open interval proposal, an applicable date before D selects R1 and D selects R2. A previously pinned R1 claim stays R1; a crossing-period claim requires a supported reviewed rule. |
| A cumulative cap is explicitly approved at 100, consumed 80; two claims each request 15 | Serialized consumption/reservation allows only 20 more in total; the second result is limited or rejected under the approved policy. No automatic cap reset on term revision. |
| Later retroactive correction or tenant-default change | Retain original package; produce an impact list and explicit revision/adjustment path. Same request retries do not create duplicate versions, cap consumption or journals. |

Section 7 records the Product Owner's Q01 currency/calendar/valuation/precision
boundary and Q02 export/source-hierarchy decisions. The final 2026-09-29 decision
makes professional evidence optional policy-version metadata and removes a named
reviewer or professional acceptance as a global development gate. No external
legal research or professional validation occurred here; actual source versions
and regulated values remain absent, so affected activation stays unset and fails
closed. Policy-specific date selection, insurance classification, rule
precedence/order, cap meaning and retroactive correction treatment remain
decisions before affected design acceptance.
Q04 selections are recorded but its named review/evidence gate remains, and the
full [S03 input register](../ROADMAP_EXECUTION_PLAYBOOK.md#unresolved-parameters-and-latest-gates)
retains D01/D03-D05/Q03. This ADR is accepted as target architecture by section 7;
no package implementation or release acceptance is implied.

Required future tests: complete field semantics; version/date boundaries and gaps/
overlaps; saved snapshot stability under policy/master changes; corrected basis/
rounding/caps; concurrent publication and cap use; idempotency, audit rollback and
tenant/project/permission denials; returned-revision history; migration differences
and rollback; producer-to-snapshot-to-GL reconciliation. Preserve existing Billing
regressions until an approved behavior change replaces them.

Alternatives declined: retain one mutable row for all authorities; copy its rates
as approved law/contract terms; always select the latest policy; or allow arbitrary
tenant formulas. Explicit versions require migration/review effort but retain
explainable history. Reuse Decimal, Django/PostgreSQL transactions/constraints and
existing settings/workflow/audit mechanisms; own applicability/calculation rules.
No package, new app, external service or generic rule-engine dependency is approved.

## 7. P1-S14 Product Owner disposition and incorporated Q01/Q02 baseline

**D14-03 Option A accepts this ADR as target architecture.** Effective-dated
regulatory rules, versioned contract commercial terms and Tenant configuration
remain separate owners; finalized history retains applied-version lineage and
snapshots. No mutable `BillingPolicy` value becomes certified law or contract
merely through this acceptance.

The initial filing boundary is preparation, validation and controlled export for
human filing or external-system submission across taxpayer invoices, VAT/tax,
payroll tax, employee insurance, contractor insurance/clearance and statutory
books/reports. Autonomous filing is out of scope. Official identifiable sources by
version/publication/effective date are primary authority; versioned professional
interpretation may supplement but never silently replace them. Vendor docs, blogs
and informal material are not authority.

Actual official sources/applicable versions remain required where an affected
regulated policy explicitly declares provenance mandatory or makes a source-backed
claim. Professional evidence is optional and
creates no application role or global development gate. Unknown precision or
rounding facts remain unset/inactive and **«نیازمند بررسی قانونی/حسابداری»**. This
acceptance authorized no statutory rate, precedence result, rule activation,
filing, implementation or migration. P6-S26–S32 later received separate bounded
implementation authority; it still supplies no official value, live provider or
production activation.
