"""Prepare current browser-only checks from retained canonical scenario inputs."""
import json
from pathlib import Path
OUT = Path(__file__).resolve().parent
rows = []
def add(actor, persona, scenarios, paths):
    for path in paths:
        rows.append(dict(actor=actor, persona=persona, scenarios=scenarios, path=path,
                         expected='Authorized current prepared state, single main/H1, labels, keyboard focus, Persian RTL and bounded horizontal overflow; no domain submission',
                         viewports=[[1440,900],[1024,768],[390,844]]))

add('uiux.persona.project-operations','P-01 ordinary + P-02 existing operational scope + P-09 explicitly linked self', [1,2,4,5,6,16,23,25], ['/', '/accounts/settings/', '/search/?q=CEP078-no-matching-source', '/projects/', '/daily-reports/create/', '/workforce/ess/', '/payroll/ess/'])
add('uiux.audit.project','P-01 scoped viewer; P-11 Safety and P-25 Quality distinct read perspectives', [2,3,4,5,9,20,23,24,25], ['/', '/search/?q=PRJ', '/inventory/', '/inventory/custody/', '/inventory/valuation/', '/safety/05ae790e-993c-4cc0-9036-521d65283f02/', '/quality/0715f881-12b0-4171-b784-264252597b24/', '/quality/'])
add('uiux.persona.project-manager','P-17 managerial scope; not a substitute for P-04 fleet operator', [2,4,19,20,25,31], ['/', '/equipment/operations/', '/equipment/maintenance/', '/equipment/cost/', '/safety/49ad2950-c4d2-48d2-97f5-9aa5e6daf847/', '/quality/cbf6257e-907a-423f-9aa9-d194fdcf62f4/'])
add('uiux.wavec.buyer','P-03 actual buyer/opening assignments', [7,25], ['/procurement/rfqs/7dd5036e-e20a-481a-ad43-dabaa692a166/buyer/'])
add('uiux.persona.inventory','P-22 retained scoped Inventory viewer', [9,25], ['/inventory/', '/inventory/custody/', '/inventory/valuation/'])
add('uiux.persona.treasury','P-06 existing Treasury/AP-AR authority', [12,13], ['/treasury/movements/new/', '/treasury/operations/', '/subledgers/'])
add('uiux.wavec.hr','P-08 HR specialist', [15,24], ['/workforce/departments/', '/workforce/positions/', '/workforce/teams/', '/workforce/employees/create/', '/workforce/foundation/', '/workforce/employees/4a7132ca-e702-41a0-9868-28a3747a7dcf/'])
add('uiux.wavec.time','P-10 Timekeeping specialist; explicit own employment identity', [17,29], ['/timekeeping/', '/timekeeping/calendars/new/', '/workforce/ess/employment/'])
add('uiux.wavec.payroll','P-20 Payroll specialist', [18,25], ['/payroll/', '/payroll/runs/e8cb4c8c-4dd0-44a6-8fc0-d55fb065ee3e/', '/payroll/statutory/', '/payroll/financial-handoffs/'])
add('uiux.wavec.documents','P-19 Document Controller', [28,25], ['/documents/', '/documents/ca7ca134-a6e5-4a5c-8bd5-68e3b56a9251/'])
add('uiux.wavec.employment','P-21 Employment Records specialist', [29], ['/workforce/employment/'])
add('uiux.wavec.commercial','P-23 Commercial specialist', [30,25], ['/contracts/', '/contracts/contractual-records/', '/commercial/', '/commercial/571c67f4-2796-4487-9207-4793f0c83a75/', '/commercial/create/'])
add('uiux.wavec.controls','P-24 Project Controls specialist', [6,31,25], ['/projects/58f517da-2139-45ac-8b7b-4f3d3a3d26e8/controls/', '/projects/58f517da-2139-45ac-8b7b-4f3d3a3d26e8/controls/comparison/', '/projects/58f517da-2139-45ac-8b7b-4f3d3a3d26e8/controls/exceptions/', '/projects/58f517da-2139-45ac-8b7b-4f3d3a3d26e8/controls/cost-reconciliation/', '/estimates/', '/estimates/create/'])
add('uiux.persona.tenant-admin','P-16 Tenant Admin; P-13 explicit Workflow admin; never Platform substitute', [4,21,22,26,27,33,25], ['/organizations/members/', '/organizations/roles/', '/workflows/administration/versions/521eb6af-b641-4c39-9024-c60c1ed2fda0/'])
add('account.demo-construction-01.owner','P-15 Owner; existing Knowledge curator and finance reviewer, not accounting specialist substitute', [2,4,11,21,25,26], ['/', '/accounting/statements/', '/accounting/statements/096c3e8b-1322-44a5-9bc5-2a953f64c82b/', '/knowledge/publications/a4468fd4-72fb-4410-91fb-b8f83d0d46d8/', '/knowledge/publications/a4468fd4-72fb-4410-91fb-b8f83d0d46d8/history/'])
add('admin','P-18 explicit Platform Admin, platform context only', [4,21,26,27,33,25], ['/organizations/platform/roles/', '/knowledge/platform/promotions/'])
add('uiux.wcd.external','P-26 non-member exact portal grant', [32,25], ['/procurement/portal/grants/dacde271-a02f-4d09-842d-3fb5695033a4/', '/procurement/portal/receipts/4d620464-f4a8-4adf-ad30-b8400f38bd12/'])

for n, row in enumerate(rows, 1):
    row['id'] = f'CEP078-R3-SURFACE-{n:03d}'
(OUT / 'BROWSER_PLAN.json').write_text(json.dumps({'scope':'Both Chrome and Edge; browser-only dimensions of the retained 33 journey inputs, no domain state changes; supplementary/missing variants remain explicit', 'source':'../CEP-078_REENTRY_02/EXT0024_MATRIX.json; current actor permissions; retained source-owned fixture paths in wave_c_reentry/wave_c_final_closure/wave_de_fixture_closure/wave_e_targeted_closure', 'rows':rows},indent=2)+'\n',encoding='utf-8')
print(len(rows), 'prepared surface checks per browser; all three viewports')
