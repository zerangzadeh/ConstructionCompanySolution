import os,json,sys
from pathlib import Path
import django
django.setup()
from django.db import connection,transaction
from django.test import Client
from apps.projects.test_command_center import CommandCenterTests,scoped_reader
from apps.organizations.models import BusinessPermission,OrganizationRole
from apps.projects.models import Project,ProjectSite,WBSNode,Activity
from apps.contracts.models import Contract
from apps.daily_reports.models import DailyReport
from apps.equipment.services import create_equipment,assign_equipment
from apps.equipment.models import EquipmentAssignmentStatus
from apps.equipment.p8_services import record_usage
from datetime import date,timedelta
from decimal import Decimal
from django.utils import timezone
from apps.accounts.models import User
root=Path(__file__).resolve().parent
assert connection.settings_dict['NAME']=='project_redesign_original'
assert not User.objects.exists()
with transaction.atomic():
 f=CommandCenterTests();f.client=Client();f.setUp()
 member=f.organization.memberships.get(user=f.owner);member.role_definition.permissions.add(*BusinessPermission.objects.filter(is_active=True))
 f.project.name='مجتمع مسکونی باغستان';f.project.code='PRJ-001';f.project.estimated_budget=Decimal('9875000000');f.project.status='active';f.project.end_date=date(2027,9,22);f.project.save()
 f.organization.name='شرکت سازه‌گستر پارس';f.organization.save(update_fields=['name'])
 from apps.organizations.models import OrganizationSettings
 setting,_=OrganizationSettings.objects.get_or_create(organization=f.organization);setting.timezone='Asia/Tehran';setting.save(update_fields=['timezone'])
 sibling=Project.objects.create(organization=f.organization,code='PRJ-002',name='پروژه هم‌شرکت محدود')
 empty=Project.objects.create(organization=f.organization,code='PRJ-003',name='پروژه آماده برنامه‌ریزی')
 site=ProjectSite.objects.create(organization=f.organization,project=f.project,code='SITE-01',name='کارگاه مرکزی باغستان')
 for i,title in enumerate(['آماده‌سازی و تجهیز کارگاه','عملیات سازه','معماری و تکمیل'],1):
  node=WBSNode.objects.create(organization=f.organization,project=f.project,code=str(i),title=title)
  Activity.objects.create(organization=f.organization,project=f.project,wbs_node=node,site=site,code=f'A-{i}',name=title,status='active' if i==1 else 'planning')
 DailyReport.objects.create(organization=f.organization,project=f.project,site=site,reporting_date=date(2026,11,12),work_performed='اجرای قالب‌بندی و بررسی آرماتورهای سقف',created_by=f.owner)
 for i,status in [(2,'active'),(3,'draft'),(4,'completed')]:Contract.objects.create(organization=f.organization,project=f.project,contract_number=f'CON-{i}',title='قرارداد اجرای مرحله '+str(i),counterparty_name='پیمانکار نمونه',status=status)
 eq=create_equipment(organization=f.organization,actor=f.owner,code='CRANE-01',name='جرثقیل برجی باغستان',category='ماشین‌آلات بالابر')
 deploy=assign_equipment(organization=f.organization,actor=f.owner,equipment=eq,project=f.project,site=site,start_date=timezone.localdate()-timedelta(days=5))
 from apps.equipment.services import transition_equipment_assignment_status
 if deploy.status!='active':transition_equipment_assignment_status(organization=f.organization,actor=f.owner,assignment=deploy,target_status='active',effective_date=timezone.localdate()-timedelta(days=4))
 deploy.refresh_from_db()
 usage=record_usage(organization=f.organization,actor=f.owner,equipment=eq,deployment=deploy,started_at=timezone.now()-timedelta(hours=2),ended_at=timezone.now(),runtime_hours=Decimal('2'),source_key='REDESIGN-USAGE')
 eq2=create_equipment(organization=f.organization,actor=f.owner,code='EQ-OTHER',name='تجهیز پروژه دیگر',category='ماشین‌آلات')
 deploy2=assign_equipment(organization=f.organization,actor=f.owner,equipment=eq2,project=sibling,start_date=timezone.localdate())
 restricted,_,_=scoped_reader(f.organization,f.project,['projects.view'],username='redesign-restricted')
 codes=list(BusinessPermission.objects.filter(is_active=True).values_list('code',flat=True))
 scoped,_,_=scoped_reader(f.organization,f.project,codes,username='redesign-project-reader')
 # Fixture-created outside tenant remains an explicit foreign source.
 from apps.organizations.models import Organization,OrganizationSettings
 foreignorg=Organization.objects.create(name='شرکت مستقل',slug='redesign-foreign');OrganizationSettings.objects.create(organization=foreignorg)
 foreignproject=Project.objects.create(organization=foreignorg,code='FOREIGN',name='پروژه خارج از شرکت')
 actors={'owner':f.owner,'restricted':restricted,'scoped':scoped}
 data={'actors':{k:str(u.pk) for k,u in actors.items()},'organization':str(f.organization.pk),'project':str(f.project.pk),'empty':str(empty.pk),'sibling':str(sibling.pk),'foreign':str(foreignproject.pk),'equipment':str(eq.pk),'other_equipment':str(eq2.pk),'deployment':str(deploy.pk),'site':str(site.pk)}
(root/'fixtures.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
print('Isolated synthetic project, WBS, activities, assignments and explicit roles seeded.')
