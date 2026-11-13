# B08 bounded execution surface

User authorization: pasted B08 mission; exactly 21 matrix rows, isolated PostgreSQL, Chrome, output validation and established-behavior defect remediation. No CEP lifecycle transition requested.

Initial surface: new B08 harness/settings/fixtures under ignored `.scratch/b08-validation/`; run-specific evidence and the two requested B08 reports; B08-only matrix cells and append-only defect findings where proved. No planned model/schema/migration/product behavior change. Any confirmed product defect will receive a narrow recorded touch-set delta before mutation.

Preserve incoming B03–B07 code, migrations, evidence, matrix rows and B05 closeout/B06 enhancement. No Git writes or production actions. Entry source fingerprints and dirty-state capture are adjacent.

## Confirmed defect B08-TZ-01

Final screenshot review proved the Reporting dashboard renders observation, cutoff and retained source timestamps in UTC although the configured organization timezone is Asia/Tehran. The retained UTC data and KPI values are correct. At the tested midnight boundary the screen shows 1405/08/21 21:07 instead of organization-local 1405/08/22 00:37. Preserve `retest/reporting-dashboard-390.png` as original defect evidence.

Bounded product touch: `apps/reporting/views.py`, dashboard render call only, using existing `core.organization_time.render_in_organization_time`; new `tests/test_b08_reporting.py` for organization-local midnight rendering, timezone restoration and read-only persistence. No model, schema, migration, metric, source cutoff, permission, hidden view, or financial behavior change. Original claims of automatic reporting PASS are superseded by this manual finding until independent retest.
