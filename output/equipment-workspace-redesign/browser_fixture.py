import os,sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
import django
django.setup()
from django.conf import settings
from django.db import connections
TEST_DB='test_bonira_equipment_workspace_ready_20261105'
connections.close_all()
settings.DATABASES['default']['NAME']=TEST_DB
connections['default'].settings_dict['NAME']=TEST_DB
with connections['default'].cursor() as c:
    c.execute('SELECT current_database()')
    assert c.fetchone()[0]==TEST_DB
from tests.test_warehouse_reference_list import WarehouseListFixture
from apps.organizations.models import BusinessPermission, MembershipScopeGrant
from apps.equipment.models import Equipment
from apps.equipment.p8_models import EquipmentWorkOrder
from django.utils import timezone
from datetime import timedelta
fixture=WarehouseListFixture()
fixture.make_fixture()
for actor in (fixture.owner,fixture.reader,fixture.denied):
    actor.set_password('equipment-browser-test-only')
    actor.save(update_fields=['password'])
fixture.reader_scope.membership.role_definition.permissions.add(BusinessPermission.objects.get(code='equipment_operations.view'))
MembershipScopeGrant.objects.create(organization=fixture.organization,membership=fixture.reader_scope.membership,scope_type='organization',reason='Isolated browser verification')
equipment=Equipment.objects.create(organization=fixture.organization,code='QA-EQ',name='تجهیز آزمون مرورگر با نام بلند برای بررسی نمایش در صفحه کوچک',category='ماشین‌آلات')
for index,status in enumerate(('draft','completed','cancelled')):
    EquipmentWorkOrder.objects.create(organization=fixture.organization,equipment=equipment,number=f'QA-WO-{index+1}',summary='دستورکار آزمایشی برای بررسی خوانایی متن بلند و نمایش ستون‌های جدول در موبایل',status=status,scheduled_for=timezone.localdate()-timedelta(days=1),created_by=fixture.owner)
print('ISOLATED TEST FIXTURE ONLY: ready',flush=True)
from django.core.management import call_command
call_command('runserver','127.0.0.1:8003',use_reloader=False)
