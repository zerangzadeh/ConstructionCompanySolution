# CEP-014 Execution Manifest

## Authority and canonical identity

- Explicit authorization: `CEP-014-AUTH-2026-10-16`, issued by the Human
  Decision Authority / Product Owner in this execution session. Scope is
  development/non-production only; deployment, production migration/cutover,
  Human Sign-off, Production Certification, Git add/commit/push/merge, and
  scope expansion are excluded.
- Canonical prompt:
  `docs/governance/cep/PROMPTS/CEP-014_EXECUTION_PROMPT.md`.
- Prompt SHA-256: `a9c142eee2cf324b495080ff919eb2d5941b79f0feca78a1dad5260278c0a9e4`;
  it matches the immutable `CEP-014` manifest record.
- Canonical sources were read from the approved consolidated source archives:
  `UIA-014`, `UIA-039`, and `UIA-040` require clear normal/Tenant/Platform/
  technical-admin separation; `PD-016` preserves explicit role/person and
  scope authority, while `PD-024` authorizes no profile-specific behavior.

## Repository grounding — 2026-10-16

- Branch: `main`.
- Start HEAD and `origin/main`: `ae3be0335a76b0d08fa5ed330770b9b2fe089060`.
- The baseline worktree contained the pre-existing user change to
  `CEP_EXECUTION_REGISTRY.yaml`, reconciling `repository_state` from
  `a4a18a1a762a2720e5627cc86b2e2d1e0ad60134` to the current HEAD. It is
  preserved and does not collide with the additive CEP-014 lifecycle record.
- CEP-001 and CEP-017 are `CLOSED_VERIFIED`; CEP-014 is recorded
  `SATISFIED`/`ELIGIBLE`. `GATE-01` is `PASS`. `GATE-02` is `NOT_READY` only
  because CEP-014 is its outstanding exit-gate contributor, so it does not
  prevent authorized build work.
- Migration impact: `NONE`.

## Actual execution touch set before product mutation

| Surface | Intended bounded change | Migration |
| --- | --- | --- |
| `templates/components/navigation_links.html` | Keep Tenant Administration company/permission-scoped and remove the Platform Administration entry from the shared tenant/mobile navigation. | None |
| `templates/base.html` | Add the existing Platform Administration destinations as a clearly separate desktop-only Platform/technical control entry; make the technical Django Admin boundary explicit without changing its guard. | None |
| `core/test_cep017_navigation.py` | Update the shared-navigation register assertion to recognize the separately positioned platform entry. | None |
| `core/test_cep014_administration.py` | Add focused template and direct-route authorization/boundary tests. | None |
| `docs/governance/cep/{manifests,evidence,reports}` and `CEP_EXECUTION_REGISTRY.yaml` | Record required CEP evidence and closeout only. | None |

No models, migrations, services, permission catalogue entries, role definitions,
route definitions, or business/workflow behavior are in the touch set.

## Completion resume — 2026-10-17

- The corrected assertion is valid. A Platform Admin without an active Tenant
  membership is denied `organizations:settings` by the existing active-tenant
  middleware with a safe login/organization-selection redirect (`302`). The
  canonical requirement is fail-closed access without protected-object leakage;
  it does not prescribe `403` for this missing-context condition. Changing the
  expected result from `403` to `302` therefore records existing governed
  behavior rather than hiding a product defect.
- The fully initialized disposable database
  `test_cep014_verify_20261017` ran the corrected focused suite: **8 passed in
  11.41s**.
- Browser/accessibility runtime evidence remains UTV under the canonical CEP-014
  rule. The template evidence confirms the Platform surface is desktop-only;
  no browser-runtime PASS is claimed.
