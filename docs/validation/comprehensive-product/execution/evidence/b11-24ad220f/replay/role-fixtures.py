from sweep import *
from django.db import transaction
from apps.accounts.models import User
from apps.workforce.models import WorkTeam
from b09_seed import persona
actors,sources=load_fixtures()
p=ROOT/'private-fixtures.json'
fixture=json.loads(p.read_text())
org=actors['field'][1]
class Tenant:
 organization=org
with transaction.atomic():
 member=persona(Tenant(),'b11-requests-person',['attendance.view','leave_mission.view','overtime.view','attendance.correct','authorization.roles.view'])
 emp=sources['field-employee']
 emp.user=member
 emp.save(update_fields=['user'])
 manager=persona(Tenant(),'b11-manager',['attendance.view','leave_mission.review','overtime.review'])
 from apps.workforce.models import Employee
 lead=Employee.objects.create(organization=org,user=manager,employee_number='B11-LEAD',first_name='سرپرست',last_name='آزمایشی')
 team=emp.work_team
 if team:
  team.lead=lead
  team.save(update_fields=['lead'])
 else:
  team=WorkTeam.objects.create(organization=org,code='B11-TEAM',name='اکیپ آزمایشی',lead=lead)
  emp.work_team=team
  emp.save(update_fields=['work_team'])
 catalog=persona(Tenant(),'b11-role-reader',['authorization.roles.view'])
fixture['actors'].update({name:[str(u.pk),str(org.pk)] for name,u in [('requests-person',member),('team-manager',manager),('role-reader',catalog)]})
p.write_text(json.dumps(fixture),encoding='utf-8')
print('Explicit My Requests, team manager and authorization-catalog actors created.')
