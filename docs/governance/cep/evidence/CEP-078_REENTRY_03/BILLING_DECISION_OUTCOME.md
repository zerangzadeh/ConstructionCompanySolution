# Billing positive-state Human decision evaluation — 2026-10-23

Direct Human authority permits isolated Development-only commercial/regulatory test
sources **only** where mandatory values already follow approved data, canonical
configuration or defined defaults. It explicitly forbids invented statutory values,
rules, contractual terms, approvals and bypassed lifecycle. Test label would be
`UIUX_TEST_ONLY_NON_AUTHORITATIVE`; it does not issue statutory correctness or
Production approval.

Outcome: **populated ProgressClaim detail remains UTV / material source blocker**.

- Current live state: zero ProgressClaim, zero ContractTermVersion and zero version
  of `receivable-claim-regulatory`; four approved baselines exist. See
  [BILLING_STATE.json](BILLING_STATE.json). Existing baseline status is insufficient.
- Searched live canonical source/version rows, code-owned policy specification,
  repository architecture/governance/configuration/seed and retained evidence. A
  numeric value appearing in an isolated test is not approved source evidence.
- `apps/organizations/policy_specs.py:176` requires `tax_rate`, `tax_basis`,
  `insurance_rate`, `insurance_basis`. The rate specs explicitly approve only the
  Decimal-string schema/range, **not** a statutory value. There are no approved
  defaults for either rate or applicability basis. Allowed alternatives `gross` /
  `after_contractual` do not select one. No source justifies a zero-rate substitution.
- `apps/organizations/policy_services.py:326` publishes a regulatory version only
  with `EXTERNAL_AUTHORITY` source basis, a linked source and accepted professional
  review evidence. A synthetic label cannot honestly satisfy those assertions.
- `docs/architecture/ADR_P0_S06_REGULATORY_CONTRACT_POLICY.md:69` assigns rate/basis
  ownership to reviewed effective-dated regulatory/applicability evidence; legacy
  fields alone cannot choose the statutory/commercial meaning.
- Contract-term service/schema define zero/unconfigured defaults for some commercial
  fields, but establishing a term alone cannot unblock claim creation. No partial
  commercial approval or existing contract modification was manufactured while the
  mandatory regulatory prerequisite remains unresolved.

Exact missing authority/evidence: supported effective `tax_rate` and `insurance_rate`,
their approved calculation/applicability bases, external source provenance and
accepted review required by the existing lifecycle. Resolving this requires source
evidence/Product-Regulatory decisions beyond technical UI fixes. No policy value,
formula, threshold, legal interpretation or acceptance was inferred. No financial,
commercial, regulatory or statutory record was changed for this sub-scenario.

Independent CEP-078 browser checks continue. Billing empty-list/preparation surfaces
are bounded actual evidence; they do not prove populated claim detail.
