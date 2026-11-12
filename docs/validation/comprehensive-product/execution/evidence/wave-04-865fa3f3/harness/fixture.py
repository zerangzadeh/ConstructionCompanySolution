import json,secrets
from datetime import date,datetime,timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
from common import root,db,guard
from django.db import transaction
from django.utils import timezone
from tests.test_b02_remediation import B02Fixture
from apps.accounts.models import User
from apps.organizations.models import BusinessPermission
from apps.organizations.services import create_organization_with_owner
from apps.projects.models import ProjectPhase
from apps.projects.services import create_project,create_project_site
from apps.equipment.services import create_equipment,assign_equipment
from apps.equipment.p8_models import EquipmentMeter
from apps.equipment.p8_services import record_usage,record_meter_reading
from apps.workforce.models import EmployeeQualification
from apps.expenses.test_p4_s26_s30 import ExpenseControlTests
from apps.parties.models import BusinessParty

guard()
assert not User.objects.exists()
with transaction.atomic():
 f=B02Fixture();f.make_fixture()
 org,owner,project,site=f.organization,f.owner,f.project,f.site
 permissions=list(BusinessPermission.objects.filter(code__regex=r'^(equipment[^.]*|maintenance_records|safety_incidents|quality_issues|expenses|expense_categories|expense_recurrences|documents|work_items)\.').values_list('code',flat=True))
 permissions+=['projects.view','project_sites.view']
 reviewer,_,_=f.member('b04-reviewer',permissions)
 scoped,_,_=f.member('b04-scoped',permissions,site=site)
 wrong,_,_=f.member('b04-sibling',permissions,site=f.sibling)
 viewer,_,_=f.member('b04-reader',['equipment.view','equipment_assignments.view','equipment_operations.view','safety_incidents.view','quality_issues.view','expenses.view','documents.view'],site=site)
 other=User.objects.create_user(username='b04-foreign')
 foreign=create_organization_with_owner(owner=other,name='شرکت دوم آزمون B04',slug='b04-foreign')
 fp=create_project(organization=foreign,actor=other,code=project.code,name=project.name)
 fs=create_project_site(organization=foreign,project=fp,actor=other,code=site.code,name=site.name)
 second=create_project(organization=org,actor=owner,code='B04-P2',name='پروژه دوم B04')
 second_site=create_project_site(organization=org,project=second,actor=owner,code='B04-S2',name='کارگاه پروژه دوم')
 phase=ProjectPhase.objects.create(organization=org,site=site,code='B04-F1',name='فاز اصلی B04',status='active')
 equipment=create_equipment(organization=org,actor=owner,code='B04-EQ-BASE',name='بیل مکانیکی مبنا',category='خاکبرداری',ownership_type='owned')
 foreign_equipment=create_equipment(organization=foreign,actor=other,code='B04-EQ-BASE',name='بیل مکانیکی مبنا',category='خاکبرداری',ownership_type='owned')
 deployment=assign_equipment(organization=org,actor=owner,equipment=equipment,project=project,site=site,start_date=date(2026,11,12))
 meter=EquipmentMeter.objects.create(organization=org,equipment=equipment,kind='hours',name='ساعت موتور',unit='hour',created_by=owner)
 when=datetime(2026,11,12,8,tzinfo=ZoneInfo('Asia/Tehran'))
 record_meter_reading(organization=org,actor=owner,meter=meter,value=Decimal('100'),observed_at=when,source_key='B04-opening')
 usage=record_usage(organization=org,actor=owner,equipment=equipment,deployment=deployment,started_at=when,ended_at=when+timedelta(hours=3),runtime_hours=Decimal('3'),source_key='B04-cost-source')
 qualification=EmployeeQualification.objects.create(organization=org,employee=f.employee,kind='certificate',title='گواهی اپراتوری',issued_on=date(2026,1,1),valid_until=date(2027,1,1),recorded_by=owner)
 party=BusinessParty.objects.create(party_kind='company',organization=org,display_name='تامین کننده آزمون B04',created_by=owner,updated_by=owner)
 from apps.equipment.test_p8_s18_s23 import P8EquipmentOperationsTests
 stockfixture=P8EquipmentOperationsTests();stockfixture.organization=org;stockfixture.project=project;stockfixture.owner=owner
 spare,_=stockfixture._stock_issue(suffix='B04');stockfixture._post(spare)
 from apps.documents.models import DocumentType,DocumentProcessingVerdict
 from apps.documents.services import create_document,record_document_processing_assessment
 from apps.organizations.access_services import assign_platform_role
 from apps.organizations.models import PlatformRoleCode
 from django.core.files.uploadedfile import SimpleUploadedFile
 grantor=User.objects.create_superuser(username='b04-grantor');cosigner=User.objects.create_superuser(username='b04-cosigner');scanner=User.objects.create_user(username='b04-scanner')
 assign_platform_role(actor=grantor,approver=cosigner,target=scanner,role=PlatformRoleCode.PLATFORM_OPERATIONS,reason='Isolated synthetic scanner fixture')
 def document(tenant,actor,target,title,clean):
  d=create_document(organization=tenant,actor=actor,document_type=DocumentType.GENERAL,title=title,upload=SimpleUploadedFile('B04.pdf',b'%PDF-1.7\nB04 synthetic evidence',content_type='application/pdf'),target=target)
  if clean:record_document_processing_assessment(version=d.current_version,actor=scanner,verdict=DocumentProcessingVerdict.CLEAN,adapter_code='b04-fixture')
  return d
 clean=document(org,owner,site,'شاهد پاک B04',True)
 pending=document(org,owner,site,'شاهد معلق B04',False)
 foreign_doc=document(foreign,other,fs,'شاهد شرکت دیگر B04',True)
 # Reuse the existing accepted-budget fixture in its own tenant; no financial production data.
 exp=ExpenseControlTests();exp.setUp()
 password=secrets.token_urlsafe(28)
 actors=[owner,reviewer,scoped,wrong,viewer,other,exp.maker,exp.approver]
 for actor in actors:
  actor.set_password(password);actor.save(update_fields=['password'])
 values={'org':org,'project':project,'site':site,'sibling':f.sibling,'phase':phase,'second':second,'second_site':second_site,'foreign':foreign,'foreign_project':fp,'foreign_site':fs,'equipment':equipment,'foreign_equipment':foreign_equipment,'deployment':deployment,'meter':meter,'usage':usage,'employee':f.employee,'qualification':qualification,'party':party,'expense_org':exp.organization,'expense_project':exp.project,'wbs':exp.wbs,'cbs':exp.cbs,'cost_center':exp.cost_center,'budget':exp.budget,'spare':spare,'doc':clean,'v1':clean.current_version,'pending':pending.current_version,'foreign_version':foreign_doc.current_version}
 (root/db).mkdir(exist_ok=True)
 (root/db/'actors.json').write_text(json.dumps({'password':password,'ids':{k:str(v.pk) for k,v in values.items()},'actors':[a.username for a in actors]}),encoding='utf-8')
print('B04 fixture ready: independent authorized/scoped/restricted/foreign actors, equipment source and accepted expense budget')




