"""Isolated non-authoritative selector source through existing workforce services."""
import json
from pathlib import Path
import sys
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
sys.path.insert(0, str(ROOT / 'docs/governance/uiux/rv007_controlled_time'))
from support import guard, REAL_NOW
from django.db import transaction
from apps.accounts.models import User
from apps.organizations.models import Organization
from apps.workforce.models import Employee, EmployeeQualification, QualificationKind
from apps.workforce.services import create_employee, record_employee_qualification, revoke_employee_qualification
from apps.equipment.p8_models import MaintenancePlan

guard()
org = Organization.objects.get(slug='demo-construction-01')
actor = User.objects.get(username='account.demo-construction-01.owner')
marker = 'UIUX_TEST_ONLY_NON_AUTHORITATIVE'
path = OUT / 'EQUIPMENT_FIXTURE.json'
if sys.argv[1] == 'prepare':
    assert not path.exists()
    assert not Employee.objects.filter(organization=org, employee_number='CEP078-UIUX-SELECTOR').exists()
    assert not EmployeeQualification.objects.filter(organization=org).exists()
    with transaction.atomic():
        employee = create_employee(organization=org, actor=actor, employee_number='CEP078-UIUX-SELECTOR', first_name='آزمون انتخاب وابسته', last_name=marker)
        qualification = record_employee_qualification(organization=org, actor=actor, employee=employee, kind=QualificationKind.QUALIFICATION, title=marker, issuer=marker, reference_number='CEP078-UIUX-SELECTOR')
    result = {'at': REAL_NOW(), 'employee': employee.pk, 'qualification': qualification.pk, 'source_count_before': 0, 'existing_plans': list(MaintenancePlan.objects.filter(organization=org, active=True).values('id','equipment_id','name')), 'marker': marker, 'purpose': 'Existing Employee-to-source-qualification selector only; no operator qualification, equipment authorization, certification, User link, assignment or business operation created', 'canonical_defaults': 'Existing generic qualification enum; optional source dates remain None; no validity or regulatory rule invented', 'cleanup': 'Revoke only new source via canonical lifecycle after read-only actual browser checks; retain immutable isolated employee/source/audit', 'result': 'PASS'}
    path.write_text(json.dumps(result, default=str, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
else:
    data = json.loads(path.read_text(encoding='utf-8'))
    qualification = EmployeeQualification.objects.get(pk=data['qualification'], organization=org)
    event = revoke_employee_qualification(organization=org, actor=actor, qualification=qualification, occurred_on=REAL_NOW().date(), reason=marker+'; disposable selector source cleanup; never an operational qualification')
    assert not qualification.is_valid_on(REAL_NOW().date())
    (OUT/'EQUIPMENT_CLEANUP.json').write_text(json.dumps({'at':REAL_NOW(), 'employee':data['employee'], 'qualification':data['qualification'], 'event':event.pk, 'canonical_source_revoked':True, 'operator_qualification_created':False, 'result':'PASS'}, default=str, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print('Isolated canonical Equipment selector source:', sys.argv[1], 'PASS')
