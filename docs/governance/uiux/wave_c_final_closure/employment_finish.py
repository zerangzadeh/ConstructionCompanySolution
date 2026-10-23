import json,os,sys
from pathlib import Path
from datetime import timedelta
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path.cwd()));out=Path('docs/governance/uiux/wave_c_final_closure');os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
import django;django.setup()
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import User
from apps.organizations.models import Organization,PlatformRoleAssignment
from apps.workforce.models import WorkRelationship,EmploymentRecord
from apps.workforce.employment_services import record_employment_version,own_employment_history
from apps.documents.models import Document
org=Organization.objects.get(slug='demo-construction-01');own=User.objects.get(username='uiux.wavec.time');manager=User.objects.get(username='uiux.wavec.employment')
rel=WorkRelationship.objects.select_related('person','legacy_employee').get(organization=org,person__user=own)
assert rel.legacy_employee.user_id==own.pk
fixture=json.loads((out/'EMPLOYMENT_FIXTURE.json').read_text());doc=Document.objects.get(pk=fixture['document']);versions=list(doc.versions.order_by('version_number'));assert len(versions)==2 and all(v.is_available for v in versions)
assert not EmploymentRecord.objects.filter(organization=org).exists()
today=timezone.localdate(timezone=ZoneInfo(org.settings.timezone));label=fixture['provenance']
with transaction.atomic():
 first=record_employment_version(actor=manager,organization=org,relationship=rel,record_key='WCF-EMPLOYMENT',kind='contract',effective_from=rel.effective_start,effective_to=today-timedelta(days=1),document_version=versions[0],reason=label)
 before={f.attname:getattr(first,f.attname) for f in first._meta.concrete_fields}
 second=record_employment_version(actor=manager,organization=org,relationship=rel,record_key='WCF-EMPLOYMENT',kind='contract',effective_from=today,effective_to=None,document_version=versions[1],reason=label,supersedes=first)
 first.refresh_from_db();assert before=={f.attname:getattr(first,f.attname) for f in first._meta.concrete_fields}
 history=own_employment_history(actor=own,organization=org);assert len(history.rows)==2 and {r.status_label for r in history.rows}=={'تاریخی','مؤثر'}
assignment=PlatformRoleAssignment.objects.filter(user__username='uiux.wavec.documents',role='platform_operations',revoked_at__isnull=True).latest('starts_at')
fixture.update(records=[str(first.pk),str(second.pk)],first_record_unchanged=True,versions=[r.version for r in history.rows],effective_dates=[{'from':r.effective_from,'to':r.effective_to,'status':r.status_label} for r in history.rows],temporary_platform_duty={'status':'TIME_BOUNDED_UNTIL_EXPIRY','id':str(assignment.pk),'ends_at':assignment.ends_at,'early_revocation':'DENIED: canonical revoke requires independent active Superuser; only one exists; no bypass','no_further_grant':True})
(out/'EMPLOYMENT_FIXTURE.json').write_text(json.dumps(fixture,default=str,indent=2)+'\n')
print('Populated own history PASS: 2 versions, effective/historical, original unchanged. Temporary scanner duty expires:',assignment.ends_at)

