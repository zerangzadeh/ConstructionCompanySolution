Continue BONIRA V1 closure from the current clean `main`.

This is a ONE-SHOT execution package for CEP-057 and CEP-058.
Do not ask the Human for routine clarification. All Development-only Human/data choices needed for this synthetic closure are supplied here.

PACKAGE
Use the extracted directory:
`BONIRA_CEP057_058_SYNTHETIC_DEV_CLOSURE_V2/`

READ FIRST
1. `authority/DEV_SYNTHETIC_DATA_AUTHORIZATION_V2.md`
2. `VALIDATION_EXPECTATIONS.json`
3. `docs/DEV_LEAVE_POLICY_v2.md`
4. `docs/DEV_PAYROLL_YTD_BINDING_v2.md`
5. all CSV files under `data/`
6. `MANIFEST.json`

CURRENT PROGRAM INTENT
- CEP-057 and CEP-058 are the only remaining V1 PARTIAL CEPs.
- Real authoritative Development opening history for Leave and Payroll/YTD is ZERO.
- The supplied realistic synthetic rows are approved technical Development fixtures, not real organizational history.
- Existing CEP-029 identity authority and Decision-05 YTD/reset semantics remain authoritative.

EXECUTION RULE
Perform silent grounding first:
Git/Registry/canonical prompt hashes/dependencies/current implementation/evidence.

Then validate:
- package SHA-256 manifest;
- CSV schemas;
- internal source counts;
- control totals;
- correction lineage;
- dates/currency;
- synthetic-only authority.

IDENTITY
Resolve DEV-HR-001..010 exactly as authorized:
- preferred: map to the 10 verified CEP-029 Development WorkRelationships sorted by stable UUID;
- fallback: create 10 dedicated synthetic Development identities through existing canonical Development services if exactly 10 usable CEP-029 relationships are unavailable.
Persist the final mapping artifact.
Do not ask for identity confirmation.

CEP-057
- use `CEP057_LEAVE_OPENING_SYNTHETIC.csv`;
- use `CEP057_RECONCILIATION_CONTROL_SYNTHETIC.csv`;
- use `DEV-LEAVE-POLICY-v2`;
- validate policy/version/as-of/cutover/mapping;
- create/reuse required Development-only policy records through canonical services;
- execute bounded opening/backfill mechanics;
- prove row-count and signed-quantity reconciliation;
- prove repeatability/idempotency;
- prove exception behavior;
- prove rollback/recovery;
- run focused and affected regression tests;
- create/update evidence and completion report;
- reconcile Registry.

After CEP-057 is genuinely COMPLETE, continue immediately to CEP-058.

CEP-058
- use `CEP058_PAYROLL_YTD_SOURCE_SYNTHETIC.csv`;
- use `CEP058_COMPONENT_CROSSWALK_SYNTHETIC.csv`;
- use `CEP058_RECONCILIATION_CONTROL_SYNTHETIC.csv`;
- use `DEV-PAYROLL-YTD-BINDING-v2`;
- preserve Decision-05 operational YTD/reset semantics;
- resolve/create Development-only components exactly as authorized;
- retain the supplied SUPERSEDED -> replacement lineage;
- include only rows where `included_in_opening = YES`;
- validate year/as-of/cutover/mapping/component controls;
- execute bounded opening/YTD migration mechanics;
- prove no duplicate inclusion;
- prove correction lineage;
- prove repeatability/idempotency;
- prove reconciliation;
- prove rollback/recovery;
- run focused and affected regression tests;
- create/update evidence and completion report;
- reconcile Registry.

CANONICAL APPLICABILITY
For requirements specifically demanding non-zero real organizational history, use the approved Development applicability:
`N/A — ZERO AUTHORITATIVE DEVELOPMENT HISTORY`

Do not turn N/A into a false PASS.
Technical AC/DoD remain mandatory.

NO BACK-AND-FORTH FALLBACKS
- Missing persisted Leave policy -> create/reuse Development-only policy matching supplied document.
- Missing payroll component -> resolve exact code or create Development-only component using supplied operational kind.
- Identity mismatch -> use the authorized fallback synthetic identity creation.
- Synthetic row violates model validation -> deterministically repair to nearest valid Development value, preserve semantics/control totals, record evidence.
- Minimum additive Development schema migration strictly required by existing CEP scope -> authorized under the Human decision.
Do not stop for routine Human confirmation.

STOP ONLY IF
- repository state is unsafe/corrupt;
- proceeding would require Production action;
- a genuinely new material business/security/legal semantic not covered by the authorization is unavoidable.

GIT
Safe attributable actions authorized:
`git add`
`git commit`
`git push origin main`

Do not use merge/rebase/reset/clean/stash/force-push/new branch/worktree.

BOUNDARIES
No CEP-069..079.
No Production action.
No Production Certification.
No Production Human Sign-off.
No fabricated real history.
No statutory/legal/tax/insurance invention.
Do not weaken AC/DoD/tests.

FINAL RESPONSE ONLY
Return a compact final result with:
- CEP-057 status + AC/DoD;
- CEP-058 status + AC/DoD;
- focused/affected regression results;
- reconciliation results;
- Registry final V1 counts;
- Git checkpoint;
- only genuine remaining blocker, if one exists.

Target, if all canonical technical requirements pass:
`V1 = 68 COMPLETE / 0 PARTIAL / 0 BLOCKED`
