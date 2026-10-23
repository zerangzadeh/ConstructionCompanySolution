# BONIRA UI/UX Static Audit Coverage Review

## 1. Baseline and governance alignment

Static UI/UX review is pinned to:

`main @ 43ac319c6e73e48ca9626461b73987922c498ec3`

The review has now been reconciled against the pinned `ROADMAP.md`, `Agents.md`,
`CEP_EXECUTION_REGISTRY.yaml`, and `docs/ui-guidelines.md`.

This audit does not reopen completed V1 CEPs, execute CEP-069..079, authorize
Production, change business/domain authority, or authorize remediation.

## 2. Why the route count is not the screen count

The original inventory discovered **383 route-derived screen candidates**.

Static source review has now proved at least **6**
of those candidates are POST-only Safety/Quality transition endpoints that render
inside the Detail surface and redirect after mutation. They are now classified as
`ACTION_ENDPOINT`, not independent screens.

Therefore the current inventory has **377**
remaining rendered-screen candidates after confirmed reclassification. Additional
candidates may still be reclassified during runtime/source expansion.

This distinction is important: route existence is not screen existence, and UI
visibility is not authorization.

## 3. Direct static coverage

- Directly reviewed rendered-surface candidates: **102**
- Remaining user-surface candidates after confirmed reclassification: **377**
- Direct review ratio: **27.1%**
- Modules with at least one directly reviewed representative surface: **33/33**
- Findings: **108**
- HIGH: **73**
- MEDIUM: **35**
- CRITICAL: **0**
- Root patterns: **25**
- Positive internal reference patterns: **19**

The purpose of this review is not to pretend that 102 pages equal
all remaining surfaces. It establishes whether the systemic taxonomy is stable enough
to move from broad static discovery to controlled runtime validation.

## 4. Module coverage

| Module | Candidate surfaces | Direct static reviewed | Direct review |
| --- | ---: | ---: | ---: |
| Accounting | 18 | 9 | 50.0% |
| Accounts | 8 | 2 | 25.0% |
| Audit | 1 | 1 | 100.0% |
| Billing | 29 | 9 | 31.0% |
| Commercial | 5 | 2 | 40.0% |
| Compliance | 5 | 3 | 60.0% |
| Contracts | 8 | 2 | 25.0% |
| Core | 3 | 2 | 66.7% |
| Daily Reports | 13 | 2 | 15.4% |
| Documents | 7 | 1 | 14.3% |
| Equipment | 24 | 7 | 29.2% |
| Estimates | 3 | 3 | 100.0% |
| Expenses | 12 | 1 | 8.3% |
| Financials | 2 | 2 | 100.0% |
| Fixed Assets | 13 | 1 | 7.7% |
| Inventory | 13 | 3 | 23.1% |
| Knowledge | 11 | 7 | 63.6% |
| Materials | 9 | 2 | 22.2% |
| Organizations | 14 | 2 | 14.3% |
| Parties | 7 | 1 | 14.3% |
| Partner Qualification | 1 | 1 | 100.0% |
| Payroll | 27 | 5 | 18.5% |
| Procurement | 22 | 4 | 18.2% |
| Projects | 17 | 3 | 17.6% |
| Quality | 3 | 1 | 33.3% |
| Reporting | 8 | 3 | 37.5% |
| Safety | 3 | 1 | 33.3% |
| Subledgers | 6 | 1 | 16.7% |
| Support | 9 | 2 | 22.2% |
| Timekeeping | 17 | 2 | 11.8% |
| Treasury | 7 | 5 | 71.4% |
| Workflows | 7 | 2 | 28.6% |
| Workforce | 45 | 10 | 22.2% |

Every discovered module now has at least one directly reviewed representative surface.

## 5. Page-type coverage

| Page type | Candidate count | Direct static reviewed |
| --- | ---: | ---: |
| ADMIN | 10 | 1 |
| CREATE | 125 | 19 |
| DASHBOARD | 5 | 4 |
| DETAIL | 67 | 27 |
| EDIT | 13 | 0 |
| ESS | 23 | 2 |
| HOME | 1 | 1 |
| LIST | 55 | 17 |
| OTHER | 7 | 1 |
| REPORT | 3 | 1 |
| REVIEW | 22 | 1 |
| SEARCH | 1 | 1 |
| SETTINGS | 7 | 2 |
| WORKSPACE | 38 | 25 |

`EDIT` siblings are currently under-represented as separate routes because many reuse
the same form classes/templates already inspected through Create/Detail surfaces.
They remain runtime/representative-equivalence candidates, not automatically accepted.

## 6. Taxonomy stability

The dominant systemic patterns are no longer local anomalies.

| Root pattern | Findings | Modules |
| --- | ---: | ---: |
| `RP-C01-TECHNICAL-LANGUAGE-LEAK` | 52 | 31 |
| `RP-C02-MODEL-REPRESENTATION-EXPOSED` | 30 | 18 |
| `RP-C13-OPERATIONAL-AUDIT-CONFLATION` | 23 | 12 |
| `RP-C05-TASK-GUIDANCE-DEFICIT` | 14 | 13 |
| `RP-C03-EXCESSIVE-TECHNICAL-INPUT` | 13 | 12 |
| `RP-C18-CASCADE-FILTERING-INCONSISTENT` | 13 | 9 |
| `RP-C19-DERIVABLE-DATA-REENTRY` | 12 | 10 |
| `RP-C07-WORKFLOW-NOT-JOURNEY-ORIENTED` | 9 | 7 |
| `RP-C04-WEAK-ACTION-HIERARCHY` | 8 | 8 |
| `RP-C11-INFORMATION-ARCHITECTURE-MISMATCH` | 6 | 6 |
| `RP-C14-SEMANTIC-LANDMARK-INCONSISTENCY` | 5 | 3 |
| `RP-C15-SHARED-FORM-PATTERN-BYPASS` | 5 | 3 |
| `RP-C08-WEAK-EMPTY-STATE` | 4 | 4 |
| `RP-C06-GENERIC-FORM-ACTION` | 3 | 3 |
| `RP-C12-POST_RENDER_LOCALIZATION` | 3 | 3 |

The highest-frequency patterns now span many modules. Recent static batches mostly
added affected surfaces to existing patterns instead of generating new pattern
families. This is the main reason the audit can now freeze a runtime validation plan.

## 7. Strong internal patterns worth preserving

BONIRA already contains better patterns that remediation should reuse:

- Expense and Estimate context-aware cascade filtering;
- Workforce Project→Site cascade with loading/error states;
- Employee known-account data reuse;
- Procurement and Support state-aware actions;
- Safety/Quality explicit «اقدام بعدی» pattern;
- Workforce Organization/Position chart visual language;
- Accounting Jalali reporting;
- query-preserving table sort and pagination;
- Daily Report task-grouped create form;
- Financial dashboard visual hierarchy, presentation only;
- polished BONIRA login surface, presentation quality only.

This matters because remediation should normalize toward BONIRA's strongest internal
patterns rather than replace the product with a new generic design system.

## 8. Static conclusions

Static evidence is sufficient to confirm that the principal UI/UX debt is systemic:

1. operational UI frequently speaks technical/governance/model language;
2. audit/traceability metadata is often mixed with ordinary business work;
3. dependent selectors are inconsistently cascade-filtered;
4. users are sometimes asked to enter derivable/system-generated data;
5. several workbenches have weak action/task hierarchy;
6. Home is a permission-safe destination directory rather than a role-aware ERP dashboard;
7. form, label, status, date and pagination shared infrastructure is not yet fully normalized;
8. visual quality is uneven: some Workforce/Login/Financial surfaces are substantially more polished than many workbenches.

Static evidence does **not** prove a business/domain defect. No current finding
requires a domain-policy change.

## 9. Static coverage decision

**Decision: STATIC_PATTERN_COVERAGE_SUFFICIENT_FOR_RUNTIME_VALIDATION_PLANNING**

This is not `FULL_UIUX_ACCEPTANCE` and is not `UX_READY_FOR_UAT`.

The next evidence phase should be bounded runtime/role validation of representative
journeys and states. Unreviewed sibling routes should be handled in one of three ways:

- `REPRESENTATIVE_EQUIVALENCE`: same shared template/form/pattern, verify through sampled runtime;
- `RUNTIME_REQUIRED`: behavior depends materially on role, state, context, viewport or data;
- `SOURCE_EXPANSION_REQUIRED`: static evidence is still insufficient to classify safely.

## 10. Relationship to CEP verification/UAT

The UI/UX runtime matrix is an audit plan only. It must not be represented as
CEP-078 execution, CEP-079 UAT, Production Certification or Human Sign-off.

At the frozen Registry baseline, CEP-078 and CEP-079 are not started and not eligible.
That governance state remains untouched by this audit.

## 11. Next step

Freeze and execute only the audit-specific `UIUX_RUNTIME_VALIDATION_MATRIX.yaml`
when a suitable runtime environment/test identities are available.

Remediation remains `NOT_STARTED`.
