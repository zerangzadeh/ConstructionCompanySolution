import os, subprocess, sys, time
from pathlib import Path

root=Path(__file__).resolve().parent
repo=root/'source'
pg=Path('D:/Program Files/PostgreSQL/18/bin')
port=(root/'db-port.txt').read_text()
selections=[
 ('focused',[
  'apps/daily_reports/test_return_revisions.py::ReturnRevisionTests',
  'apps/daily_reports/test_b03_final_remediation.py::B03FinalRemediationTests',
  'apps/daily_reports/test_workflow.py::DailyReportWorkflowTests',
  'tests/test_b04_final_remediation.py','tests/test_b04_remediation.py',
  'tests/test_equipment_operations_workspace.py','apps/safety/test_cep027_review.py',
  'apps/quality/test_cep027_review.py','apps/safety/test_cep079_hse_scope.py',
 ]),
 ('return_race',['apps/daily_reports/test_return_revisions.py::ReturnConcurrencyTests']),
 ('labor_race',['apps/daily_reports/test_b03_final_remediation.py::B03LaborConcurrencyTests']),
 ('approval_race',['apps/daily_reports/test_workflow.py::DailyReportConcurrencyTests']),
]
for label,tests in selections:
    target='test_gate_'+label
    subprocess.run([str(pg/'createdb.exe'),'-h','127.0.0.1','-p',port,'-U','gate_local','-T','gate_migrated_template',target],check=True)
    env=dict(os.environ,GATE_TEST_DB=target)
    start=time.monotonic()
    with (root/f'tests-{label}.log').open('w',encoding='utf-8') as log:
        proc=subprocess.run([sys.executable,'-m','pytest','--ds=gate_settings',*tests,'--reuse-db','-q','--tb=short',f'--junitxml={root/f"tests-{label}.xml"}'],cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT)
    (root/f'tests-{label}-exit.txt').write_text(str(proc.returncode))
    print(f'{label}: exit {proc.returncode}, {time.monotonic()-start:.1f}s',flush=True)
    print('\n'.join((root/f'tests-{label}.log').read_text(encoding='utf-8').splitlines()[-12:]),flush=True)
    if proc.returncode:
        sys.exit(proc.returncode)
