# B04 final remediation and retest

**12 November 2026 · MVP · `main` at `24ad220f0376cb0b6232b745938b35433843a32d`**

| B04 checkpoint | Planned | PASS | FAIL | BLOCKED | NOT_RUN |
|---|---:|---:|---:|---:|---:|
| Prior bounded retest | 66 | 61 | 1 | 4 | 0 |
| Final remediation retest | 66 | 66 | 0 | 0 | 0 |

All five previously non-passing rows passed. Directly affected equipment cost rows were checked again using a Chrome-created usage record. The other row results carry forward from the prior B04 evidence. The final result is technically ready for Product Owner acceptance on the verified B04 source baseline. Formal Product Owner acceptance and Human Sign-off remain pending. [Final 66-row overlay](B04_FINAL_REMEDIATION_RETEST.csv) · [Prior retest](B04_RETEST_RESULTS.csv)

| Defect | Correction and observed result |
|---|---|
| BON-DEF-0026 · P1 | Safety and Quality now offer contextual decisions on submitted records using their existing permissions and source-owned services. An independent reviewer approved each record, after which the existing closure action succeeded. Before approval, the detail showed the prerequisite and the server rejected a forced close. Separate records completed return, correction, resubmission through DMS and rejection with recorded reasons. Creator, reader, sibling-site, foreign and missing-CSRF requests were denied. Stale conflicting decisions were rejected. Exact approval replay retained one decision revision. The original evidence version remained pinned. |
| BON-DEF-0027 · P1 | The accepted Equipment contract defines interval or meter-delta usage evidence. The existing MVP form is interval-based. Positive operating hours may be less than elapsed time and cannot exceed it. The transaction locks the asset, compares timezone-aware instants and rejects intersecting intervals for that asset. Adjacent intervals and exact retries are valid. Chrome rejected 20 hours in two hours and a separate otherwise-valid overlap with Persian field errors. Concurrent writers produced one usage for an overlap, and an exact concurrent retry produced one usage and one audit event. Existing historical records were retained. |
| BON-DEF-0028 · P2 | Chrome activated the existing deployment, selected a qualified operator, and saved a two-hour usage record. The service derived the deployment because exactly one authorized active option covered the entire interval. An explicit deployment worked for a site recorder without an operator. A sibling-site forgery wrote nothing, and the focused tests rejected an expired operator. A reviewer finalized the Chrome-created allocation and independently reviewed the handoff. Exact replay retained one envelope. The proposal was **2.000 h × 125,000 IRR/h = 250,000 IRR**. GL, Treasury, payment request and Project Cost actual counts did not change. |

[Equipment decision packet, §§4 and 6](../../../architecture/P8_S18_S23_EQUIPMENT_OPERATIONS_DECISION_PACKET.md) · [Defect register](../DEFECT_REGISTER.md)

The new MVP record decisions enforce independence inside the locked domain transaction against both the original creator and the latest submitter. An existing compatibility call without a submitted revision remains available to internal callers. Formal decisions leave operational resolution or verification intact. Returned records use the existing correction service and resubmit through the existing DMS control. The existing closed-record protection remains in force.

Deployment selection is checked again at save against the equipment, tenant, authorized project/site, active status and local dates covered. If there is no eligible option, the UI requires an active deployment. If multiple options are eligible, the service requires an explicit selection. The existing assignment exclusion constraint prevents overlapping active assignments for the same asset, so a legitimate multiple-option interval could not be provisioned on PostgreSQL. Operator selection is optional. An operator supplied by the user must have current equipment and Workforce qualification covering the interval. Usage remains append-only through the MVP form, and no historical backfill or edit path was introduced.

Chrome 156 exercised the affected paths at 1440, 1024 and 390 CSS px. The 57 observations retained Persian RTL, one main landmark and no page overflow. The decision and correction pages use the existing compact form and record history patterns. The usage and cost forms expose business labels for the new links. [Browser and database evidence](evidence/b04-final-remediation-24ad220f/) · [Concurrency witness](evidence/b04-final-remediation-24ad220f/concurrency.json)

**Verification:** 34 focused and affected tests and 23 subtests passed on isolated PostgreSQL. Django checks, migration drift, Ruff lint and format passed. The runtime used the 457-migration B04 clone, and `migrate --noinput` reported no pending committed migrations. The dirty checkout’s concurrent `daily_reports.0009_revision_guards` failed on an unescaped `%R` placeholder in psycopg during an isolated migration attempt. The concurrent files were preserved. Validation used a read-only export of committed `main` plus the exact B04 source files below. The full working-tree migration and the earlier from-zero migration remain unverified for release. [Test output](evidence/b04-final-remediation-24ad220f/final-tests.log) · [Migration error](evidence/b04-final-remediation-24ad220f/concurrent-migration-error.txt) · [Source hashes](evidence/b04-final-remediation-24ad220f/source-baseline.json)

| Changed files | Purpose |
|---|---|
| `apps/equipment/usage_context.py`, `apps/equipment/p8_services.py` | Interval, replay, locking, authorized deployment and operator validation. |
| `apps/equipment/forms.py`, `apps/equipment/views.py`, `apps/equipment/cost_services.py` | Usage form and site scope through the cost proposal journey. |
| `apps/safety/record_review.py`, `apps/safety/urls.py`, `apps/safety/views.py`, `apps/safety/templates/safety/detail.html` | Safety decision and correction controls and transaction checks. |
| `apps/quality/record_review.py`, `apps/quality/urls.py`, `apps/quality/views.py`, `apps/quality/templates/quality/detail.html` | Quality decision and correction controls and transaction checks. |
| `core/record_review.py`, `templates/components/record_decision_page.html`, `templates/components/record_review_history.html` | Shared form, decision checks and history presentation. |
| `tests/test_b04_final_remediation.py`, `tests/test_b04_remediation.py` | Focused PostgreSQL tests and the existing error-feedback regression updated for field errors. |
| `DEFECT_REGISTER.md`, `DEFECT_REGISTER.csv`, `execution/B04_REMEDIATION_REPORT.md`, `execution/B04_FINAL_REMEDIATION_RETEST.csv`, `execution/evidence/b04-final-remediation-24ad220f/` | Current disposition, evidence and preserved prior results. Paths in this row are relative to `docs/validation/comprehensive-product/`. |

No open B04 remediation decisions remain for the three authorized defects. Formal product and visual acceptance remains with the Product Owner. The historical MVP matrix, prior B04 overlay, and Wave 01–B03 evidence were preserved. No new migration files, production actions, existing Development/demo data writes, Git commit or push. B05 was not started.
