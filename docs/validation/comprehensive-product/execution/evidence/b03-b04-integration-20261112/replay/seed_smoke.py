import importlib, json, secrets
from datetime import date
from common import root, guard
from django.db import transaction
from apps.accounts.models import User
from apps.daily_reports.test_return_revisions import ReturnFixture
from apps.equipment.models import Equipment, EquipmentAssignment
from apps.equipment.p8_models import OperatorEquipmentQualification
from apps.workforce.models import EmployeeQualification

guard()
assert not User.objects.exists()
with transaction.atomic():
    f = ReturnFixture(); f.setUp(); f.entries(f.report); first=f.submit()
    codes = ['safety_incidents.view','safety_incidents.record_decide','quality_issues.view','quality_issues.record_decide']
    reviewer,_,_=f.member('gate-hse-reviewer',codes,site=f.site)
    sibling,_,_=f.member('gate-hse-sibling',codes,site=f.sibling)
    records={}
    for app,noun,number,kind,severity in [('safety','incident','incident_number','near_miss','low'),('quality','issue','issue_number','defect','minor')]:
        service=importlib.import_module(f'apps.{app}.services')
        review=importlib.import_module(f'apps.{app}.record_review')
        obj=getattr(service,f'create_{app}_{noun}')(organization=f.organization,actor=f.owner,project=f.project,site=f.site,description='شرح آزمون یکپارچگی',**{number:f'GATE-{app}', 'occurred_at' if app=='safety' else 'identified_at':f.moment(9),f'{noun}_type':kind,'severity':severity})
        revision=getattr(review,f'submit_{app}_record')(organization=f.organization,actor=f.owner,**{f'{noun}_id':obj.pk},reason='ارسال آزمون یکپارچگی')
        records[app]={'id':str(obj.pk),'submission':str(revision.pk),'status':obj.status}
    eq=Equipment.objects.create(organization=f.organization,code='GATE-EQ',name='بیل آزمون یکپارچگی',category='ماشین‌آلات')
    deployment=EquipmentAssignment.objects.create(organization=f.organization,equipment=eq,project=f.project,site=f.site,status='active',start_date=f.day)
    qualification=EmployeeQualification.objects.create(organization=f.organization,employee=f.employee,kind='certificate',title='صلاحیت آزمون',issued_on=f.day,valid_until=date(2027,1,1),recorded_by=f.owner)
    OperatorEquipmentQualification.objects.create(organization=f.organization,equipment=eq,employee=f.employee,workforce_qualification=qualification,effective_from=f.day,created_by=f.owner)
    password=secrets.token_urlsafe(28)
    actors=[f.author,f.reviewer,f.owner,reviewer,sibling]
    for actor in actors:
        actor.set_password(password);actor.save(update_fields=['password'])
    result={'password':password,'ids':{'org':str(f.organization.pk),'report':str(first.pk),'hash':first.submission_hash,'equipment':str(eq.pk),'deployment':str(deployment.pk),'employee':str(f.employee.pk)},'records':records,'actors':{k:v.username for k,v in [('author',f.author),('reviewer',f.reviewer),('owner',f.owner),('hse',reviewer),('sibling',sibling)]}}
    (root/'actors.json').write_text(json.dumps(result),encoding='utf-8')
print('Synthetic smoke fixture ready: sealed Daily Report, submitted Safety/Quality, active equipment deployment and operator qualification.')
