"""Live CSRF HTTP plus rolled-back identity denial probes; no inferred identities."""
import hashlib,json,os,sys
from pathlib import Path
from zoneinfo import ZoneInfo
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[3];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(OUT.parent/'wave_c_domain_resolution'))
from http_validation import request
from django.conf import settings
from django.db import transaction
from django.core.exceptions import PermissionDenied,ValidationError
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from apps.accounts.models import User
from apps.organizations.models import Organization
from apps.organizations.services import set_active_organization
from apps.workforce.models import EmploymentRecord,WorkRelationship,Employee
from apps.workforce.employment_services import own_employment_history
from apps.procurement.models import RequestForQuotation,QuoteRevisionEvidence
assert settings.DEBUG and settings.SETTINGS_MODULE=='config.settings.development'
org=Organization.objects.get(slug='demo-construction-01');own=User.objects.get(username='uiux.wavec.time');manager=User.objects.get(username='uiux.wavec.employment');rel=WorkRelationship.objects.select_related('legacy_employee','person').get(organization=org,person__user=own)
observations=[]
def save(name,data): (OUT/name).write_text(json.dumps(data,default=str,indent=2)+'\n',encoding='utf-8')
def observe(case,actor,path,expected,data=None):
 status,body,final=request(actor,path,data)
 observations.append({'case':case,'actor':actor,'path':path,'method':'POST' if data is not None else 'GET','status':status,'expected':expected,'passed':status==expected,'sha256':hashlib.sha256(body).hexdigest()});save('EMPLOYMENT_HTTP.json',observations)
 assert status==expected,observations[-1]
 return body.decode()
management=reverse('workforce:employment_manage');ownurl=reverse('workforce:employment_history')
text=observe('Populated management list','uiux.wavec.employment',management,200)
assert 'نسخه ۱' in text or 'نسخه 1' in text
text=observe('Selected relationship and business-labelled source','uiux.wavec.employment',management+'?relationship='+str(rel.pk),200)
assert 'سند مصنوعی قرارداد استخدام' in text
observe('Management employee detail','uiux.wavec.employment',reverse('workforce:employee_detail',args=[rel.legacy_employee_id]),200)
count=EmploymentRecord.objects.count()
text=observe('Invalid POST redisplays and writes nothing','uiux.wavec.employment',management,400,{'relationship':str(rel.pk),'reason':'UIUX_TEST_ONLY_NON_AUTHORITATIVE'})
assert EmploymentRecord.objects.count()==count
text=observe('Populated own current and historical versions','uiux.wavec.time',ownurl,200)
assert 'تاریخی' in text and 'مؤثر' in text and text.count('<article')==2
observe('Own actor cannot manage histories','uiux.wavec.time',management,403)
other=Employee.objects.filter(organization=org).exclude(pk=rel.legacy_employee_id).first();assert other
observe('Another employee detail denied','uiux.wavec.time',reverse('workforce:employee_detail',args=[other.pk]),403)
foreign=Employee.objects.exclude(organization=org).first();assert foreign
observe('Cross-tenant employee identifier denied','uiux.wavec.employment',reverse('workforce:employee_detail',args=[foreign.pk]),404)
observe('Same-tenant unauthorized own history denied','uiux.wavec.commercial',ownurl,403)
# The own-history endpoint accepts no employee selector: a forged selector must not widen it.
text=observe('Forged own-history employee selector cannot widen identity','uiux.wavec.time',ownurl+'?employee='+str(other.pk),200)
assert text.count('<article')==2
identity_before=list(Employee.objects.filter(pk=rel.legacy_employee_id).values())
probes=[]
for name,target in [('missing Employee.user',None),('mismatched Employee.user',User.objects.get(username='uiux.wavec.commercial'))]:
 with transaction.atomic():
  employee=Employee.objects.get(pk=rel.legacy_employee_id);employee.user=target;employee.save(update_fields=['user'])
  denied=False
  try: own_employment_history(actor=own,organization=org)
  except PermissionDenied: denied=True
  assert denied
  # Same-connection HTTP-layer probe sees the uncommitted negative fixture; rolled back entirely.
  client=Client();client.force_login(own);session=client.session;set_active_organization(session=session,organization=org);session.save()
  response=client.get(ownurl, HTTP_HOST="127.0.0.1");assert response.status_code==403
  probes.append({'case':name,'service':'PermissionDenied','http_layer':403,'rollback':True})
  transaction.set_rollback(True)
assert identity_before==list(Employee.objects.filter(pk=rel.legacy_employee_id).values())
records=list(EmploymentRecord.objects.filter(organization=org,record_key='WCF-EMPLOYMENT').select_related('document_version').order_by('version'));assert len(records)==2
integrity=[]
for r in records:
 digest=hashlib.sha256(Path(r.document_version.file.path).read_bytes()).hexdigest();assert digest==r.document_sha256==r.document_version.sha256
 integrity.append({'record':str(r.pk),'version':r.version,'source_version':str(r.document_version_id),'sha256':digest,'supersedes':str(r.supersedes_id) if r.supersedes_id else None,'effective_from':r.effective_from,'effective_to':r.effective_to})
try:records[0].reason='forged';records[0].save()
except ValidationError: immutable=True
else:raise AssertionError('Finalized history mutated')
save('EMPLOYMENT_CONTROLS.json',{'identity_probes':probes,'explicit_identity_preserved':True,'append_only_write_denied':immutable,'source_integrity':integrity,'no_real_person_or_production_data':True})
rfq=RequestForQuotation.objects.get(organization=org,rfq_number='WAVE-C-RFQ-A');now=timezone.now()
assert now<rfq.closing_at and now<rfq.earliest_opening_at
save('RFQ_REAL_TIME.json',{'status':'RV-007_PENDING_REAL_CLOSE_CONDITION','recorded_at':now,'rfq':str(rfq.pk),'state':rfq.status,'closing_at':rfq.closing_at,'earliest_opening_at':rfq.earliest_opening_at,'closing_at_tehran':rfq.closing_at.astimezone(ZoneInfo('Asia/Tehran')),'earliest_opening_at_tehran':rfq.earliest_opening_at.astimezone(ZoneInfo('Asia/Tehran')),'date_or_state_mutation':False,'opening_executed':False,'source_scan_or_duty_bypass':False,'post_close_obligations':'Close manifest/custody, independent protected opening, confidential comparison, tenant/scope/manipulated-action denials, integrity and desktop/mobile UI remain unexecuted until real prerequisites pass'})
print('Employment HTTP:',len(observations),'PASS; missing/mismatched identity probes rolled back; source hashes match. RFQ real-time gate retained.')

