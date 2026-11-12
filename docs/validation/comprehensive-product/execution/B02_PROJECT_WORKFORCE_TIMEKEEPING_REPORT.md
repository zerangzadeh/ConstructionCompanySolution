# B02 Projects, Workforce and Timekeeping

**Wave 02 · 2026-11-10 Asia/Tehran · MVP · `865fa3f3f7868e81b0aafba05d2683b28fe33b1e`**

| Scenario | Planned | Evidence recorded | PASS | FAIL | BLOCKED | NOT_RUN | NEEDS_PO_REVIEW |
|---|---:|---:|---:|---:|---:|---:|---:|
| UAT-02 | 23 | 23 | 20 | 3 | 0 | 0 | 0 |
| UAT-04 | 32 | 32 | 27 | 2 | 3 | 0 | 0 |
| CV-TIME-01 | 13 | 13 | 6 | 5 | 2 | 0 | 0 |
| Total | 68 | 68 | 53 | 10 | 5 | 0 | 0 |

All 68 planned IDs have execution evidence, including the five blocked rows. The adjudicated parent-row coverage is **63/68 (92.6%)**. The denominator is the original B02 worklist. The three observed supplemental child steps preserve their Phase A parents and are excluded from that denominator. PASS means the verified primary row behavior passed within the observed variants. Separate dimension columns retain unexercised assertions and open design review.

| Dimension | PASS | FAIL | NOT_RUN | NEEDS_PO_REVIEW |
|---|---:|---:|---:|---:|
| FUNCTIONAL | 64 | 1 | 3 | 0 |
| BUSINESS_LOGIC | 59 | 6 | 3 | 0 |
| DESIGN_CONFORMANCE | 52 | 3 | 11 | 2 |
| NAVIGATION_UX | 48 | 4 | 16 | 0 |
| AUTHORIZATION | 67 | 1 | 0 | 0 |
| PO_ACCEPTANCE | 0 | 0 | 68 | 0 |

## Business and authorization

- **Projects and sites.** Invalid date order was rejected and the entered code survived validation. Valid project dates, budgets, site/phase ancestry and transitions reconciled with persisted and audit data. Site detail carried both context keys to workforce and timekeeping. Gallery capture used a generated image, the expected document version, typed project and site links and a synthetic clean assessment. Foreign gallery and protected bytes were denied. Controls comparison, exceptions and CSV covered the no-source fixture. Populated budget comparison and export amounts remain unexercised.
- **Workforce and work logs.** Chrome created and edited a non-login worker with an explicit relationship. It exercised both assignment entry points, scoped choices, team creation/archive, assignment completion and the distinct planned/actual dates. A 2 h 35 min work log persisted 155 minutes and retained the scoped allocation. Independent review and the non-financial 155-minute preview left attendance separate.
- **Attendance and requests.** Calendar, shift, holiday and break persisted independently. A separate reviewer finalized attendance. Normal correction kept the original timestamp and used a linked replacement. Overtime duplicate overlap was rejected. The Mission branch completed submission and independent approval. Leave without a reservation remained draft and showed the prerequisite. Positive reservation-backed leave submission and review are BLOCKED.
- **Time integrity.** Attendance, leave, mission, overtime and correction entry stored UTC wall time for a Tehran tenant. 08:00 on 1405/08/10 became 08:00 UTC, or 11:30 Tehran, instead of 04:30 UTC. A separate correction approval wrote finalized intervals with a 45-minute overlap. Relative durations such as 95 and 155 minutes reconciled. [Time-zone witness](evidence/wave-02-865fa3f3/timezone-witness.json) · [Correction and overlap](evidence/wave-02-865fa3f3/timekeeping-close/browser-and-state.json)
- **Scope.** Restricted and foreign direct routes and mutations were checked where applicable. Same-tenant sibling correction GET returned 200 to the site-limited actor, while a subsequent POST created no request. The tested foreign record and protected image requests were denied. The Payroll and full Workforce entry checks were lightweight denial probes.

## Design and navigation

Chrome captured 111 rendered observations. The index records Persian RTL, landmark and viewport measurements, actual headings, fields, actions and breadcrumbs. Representative layouts ran at 1440, 1024 and 390 CSS pixels. A keyboard-operated Jalali picker and mobile filter disclosure worked. The independent Projects list and hub retain the §30 reference decision. Assignment completion lost its filters, a partial Controls role received a link to a denied destination, and approved correction detail lacked the replacement link. [Page conformance](evidence/wave-02-865fa3f3/PAGE_CONFORMANCE.md) · [Page index](evidence/wave-02-865fa3f3/page-index.csv)

| Defect | Severity | Finding |
|---|---|---|
| BON-DEF-0004 | P1 | Time entry persists wall time as UTC |
| BON-DEF-0005 | P1 | Approval permits overlapping finalized attendance |
| BON-DEF-0006 | P2 | Correction form reveals ungranted record existence |
| BON-DEF-0007 | P1 | WBS child rejected for a valid parent |
| BON-DEF-0008 | P2 | Ending assignment loses list context |
| BON-DEF-0009 | P2 | Approved correction omits replacement link |
| BON-DEF-0010 | P2 | Project hub links to a denied Controls page |

The project-list observation from **UIUX-F-018** remains present. It retains its historical ID. Calendar weekday input and action language (UIUX-F-002/F-003/F-004), Controls wording (UIUX-F-019), separation of setup and daily actions (UIUX-F-040), workforce filter position (UIUX-F-108) and the MVP employee detail landmark (UIUX-F-131) were rechecked in their observed variants. UIUX-F-041 raw exception-code recurrence was not adjudicated with a populated exception. The full-HR variant of UIUX-F-049 was excluded. [Historical findings](../../../governance/uiux/UIUX_FINDINGS_REGISTER.yaml)

## Open Product Owner decisions

- Establish the independent visual baseline for Projects list and hub under §30, including the duplicate detail affordances.
- Decide the intended MVP exposure of employee archive, image upload and image viewing. The matrix and Product Surface list the routes as active. The rendered MVP field detail offered no positive controls, so those three rows are BLOCKED.
- Confirm the MVP operator handoff for reservation-backed leave and the remaining field-flow and time vocabulary review. Record acceptance as an explicit decision.

The 70-case focused run produced **61 passes and 9 setup errors** in the old gallery fixture. A diagnostic rerun of the same nine gallery tests passed with the existing organization-owner creation service substituted in the isolated test process. Keep the original run outcome distinct. [Focused suite](evidence/wave-02-865fa3f3/focused-tests.log) · [Gallery diagnostic](evidence/wave-02-865fa3f3/gallery-diagnostic.log)

[Derived MVP matrix](../TEST_EXECUTION_MATRIX_MVP.csv) · [Defect register](../DEFECT_REGISTER.md) · [Run manifest](evidence/wave-02-865fa3f3/RUN_MANIFEST.md) · [Row reconciliation](evidence/wave-02-865fa3f3/row-summary.json)
