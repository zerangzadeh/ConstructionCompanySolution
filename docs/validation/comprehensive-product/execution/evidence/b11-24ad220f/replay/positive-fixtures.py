from sweep import *
from datetime import date
from django.db import transaction
from apps.equipment.services import create_maintenance_record
from apps.expenses.services import create_expense_category
from apps.materials.services import create_material_category
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.authorization import permission_supports_object_scope
from apps.projects.models import Project
from b09_seed import persona
import sys
actors,sources=load_fixtures()
path=ROOT/os.environ.get('B11_FIXTURE_FILE','private-fixtures.json')
fixture=json.loads(path.read_text())
out={}
def call(k,fn):
 try:
  with transaction.atomic():
   result=fn()
  if result and hasattr(result,'_meta'):
   fixture['sources'][k]=[result._meta.label,str(result.pk)]
  out[k]='PASS'
 except Exception as exc:
  out[k]=type(exc).__name__
  import traceback
  traceback.print_exc()
f,fo=actors['field'];u,o=actors['ops']
call('maintenance',lambda:create_maintenance_record(organization=fo,actor=f,equipment=sources['field-equipment'],record_number='B11-MAINT',maintenance_type='inspection',summary='بازرسی نمونه',scheduled_date=date(2026,11,13),project=sources['field-main-project'],site=sources['field-main-site']))
call('expense-category',lambda:create_expense_category(organization=o,actor=u,code='B11-EXP',name='دسته هزینه آزمایشی'))
call('material-category',lambda:create_material_category(organization=o,actor=u,code='B11-MAT',name='دسته مصالح آزمایشی'))
out['statutory_prepare_supports_scope']=permission_supports_object_scope(P.TAXPAYER_INVOICES_PREPARE)
out['compliance_prepare_supports_scope']=permission_supports_object_scope(P.CONTRACTOR_COMPLIANCE_PREPARE)
path.write_text(json.dumps(fixture),encoding='utf-8')
write('supplemental-fixtures.json',out)
print(out)
