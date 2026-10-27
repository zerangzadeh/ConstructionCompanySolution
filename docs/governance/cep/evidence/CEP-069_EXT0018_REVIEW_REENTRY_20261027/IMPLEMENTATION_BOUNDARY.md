# EXT-0018 implementation and qualification boundary

Governing Human decision: the retained `ADOPTED_EXPERT_REVIEW.md`, not an AI
legal opinion. Human disposition remains `APPROVED_WITH_CONDITIONS`.

The source-linked qualification supports ordinary Labour Law employees with
compulsory SSO and ordinary payroll income tax. Explicit component mappings cover
BASE remuneration for tax and BASE/HOUSING insured remuneration. These are exact
qualification component codes, not a name/kind inference for tenant components.
Other components and unresolved conditional benefit classifications fail closed.
The later tax amendment is retained with its prospective 2026-10-19 boundary;
its existence does not supply missing benefit-specific applicability facts.
No live filing schema, filing service, wage-generation or posting scope is added.

`statutory_governance` is a versioned optional extension to the two existing
policy parameter contracts inside the existing schema1 source-package envelope.
It retains source hashes, issue/publication/legal dates, source-specific
supersession/correction treatment, Human review reference/hash, population/profile
and parameter-to-source links. Only `config.settings.development` with DEBUG true
can resolve these explicitly non-production parameters. This restriction cannot
be removed merely by publishing a policy; Production needs separate authority.

The additive Payroll migration creates immutable `StatutoryPayrollContext` facts
per finalized run/employee. The existing statutory-review business permission
governs recording through `record_statutory_context`. All four monetary opening
and external-source fields are mandatory; explicit verified zeros are permitted,
missing values are not defaulted. Prior totals cover all sources through the day
before the current period. External amounts are additional current-period income
and withholding. Evidence reference/hash, reviewer, tax-year interval, population,
profile, unemployment applicability and insured work days are required.

Payroll and tenant rows are locked before critical mutation; employee locking
serializes YTD calculations. Runtime rejects mismatched tenants, unavailable
reviewed facts, contradictory known prior totals, earlier unreconciled finalized
Payroll, and overlapping/later calculations. This bounded contract supports one
chronologically reconciled payment per period. Same-period additional payments,
backdated insertion and negative withholding require governed reconciliation;
there is no implicit refund, clamp-to-zero or erase-history path. A mistaken
immutable context requires a governed Payroll replacement and new context.

Tax uses source-native annual exemption/brackets, translated from million IRR
to IRR and from gross annual thresholds to post-exemption bracket coordinates.
It never divides by 12. Decimal precision is 60 during calculation; bracket
slices remain unrounded. Prior and current external withholding are subtracted
before whole-IRR final HALF_UP rounding. Insurance applies daily floor/cap times
explicit insured days (including 29/30/31), keeps government financing separate,
and includes employer unemployment only where explicitly covered. Each payer's
final liability is rounded once. The fallback is a Human system policy where
statute is silent, not a claimed statutory rounding requirement.

The housing source correction changes the retained entitlement observation from
9,000,000 to 30,000,000 IRR monthly from 1405/01/01. It preserves the earlier
observation, issue/publication dates and original v1 package. The statutory
engine consumes finalized Payroll amounts; it does not rewrite those earnings.
The qualification uses explicit synthetic replacement Payroll inputs and records
an immutable statutory correction linked to its predecessor. No historical
business Payroll is changed. Unsupported proration or benefit-tax semantics are
not invented.

Actual qualification imports/publishes four governed source packages into a
unique disposable database, executes native calculations, verifies effective
boundaries/history and correction deltas, then removes that database. The
unchanged empty test template and configured Development business database are
not migrated or activated. That business database therefore has the new migration
pending and zero Payroll source packages; qualified isolated activation is not
represented as a persistent business-environment installation.

The Human conditional review is retained as such. After conditions are proved,
a distinct accepted **technical verification** record enables the existing
source-package publication mechanism under the Human's prior authorization.
Its identity/qualification/independence text expressly claims no new Human
decision, external professional credential, or independence certification.
The original conditional record and source hashes remain traceable in runtime
snapshots. Production certification, final Human Sign-off and Git writes remain
unexecuted.
