"""Authorized Development-only fixture; canonical DMS/Employment, genuine scanner."""
import hashlib,json,os,struct,subprocess,sys,zlib
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[3];sys.path.insert(0,str(ROOT));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
import django;django.setup()
from django.conf import settings
from django.db import connection,transaction
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.accounts.models import User
from apps.documents.models import DocumentCategory,Document
from apps.documents.services import create_document_category,create_document,add_document_version,record_document_processing_assessment
from apps.organizations.models import Organization
from apps.organizations.access_services import assign_platform_role,revoke_platform_role
from apps.workforce.models import WorkRelationship,EmploymentRecord
from apps.workforce.employment_services import record_employment_version,own_employment_history
assert settings.DEBUG and settings.SETTINGS_MODULE=='config.settings.development'
assert connection.settings_dict['HOST'] in ('localhost','127.0.0.1','::1') and connection.settings_dict['NAME']=='construction_erp'
def save(name,data): (OUT/name).write_text(json.dumps(data,default=str,indent=2)+'\n',encoding='utf-8')
# Existing model-level fingerprint machinery; importing does not reconcile authority.
sys.path.insert(0,str(OUT.parent/'authorization_reconciliation'))
from revalidate import snapshot
if not (OUT/'EMPLOYMENT_DATA_BEFORE.json').exists():
 save('EMPLOYMENT_DATA_BEFORE.json',snapshot())
org=Organization.objects.get(slug='demo-construction-01');manager=User.objects.get(username='uiux.wavec.employment');own=User.objects.get(username='uiux.wavec.time');owner=User.objects.get(username='account.demo-construction-01.owner');scanner_actor=User.objects.get(username='uiux.wavec.documents')
relationship=WorkRelationship.objects.select_related('person','legacy_employee').get(organization=org,person__user=own)
assert relationship.legacy_employee.user_id==own.pk
assert not EmploymentRecord.objects.filter(organization=org).exists()
label='UIUX_TEST_ONLY_NON_AUTHORITATIVE — Wave C final synthetic employment fixture'
category=DocumentCategory.objects.filter(organization=org,code__iexact='WCF-EMPLOYMENT').first() or create_document_category(organization=org,actor=owner,code='WCF-EMPLOYMENT',name='سوابق استخدام آزمایشی توسعه',description=label,employee_current_visible=True,employee_history_visible=True,employee_download_allowed=False)
def png(rgb):
 def chunk(kind,payload):return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload)&0xffffffff)
 return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\x00'+rgb))+chunk(b'IEND',b'')
document=Document.objects.filter(organization=org,reference='WCF-EMPLOYMENT-SYNTHETIC').first() or create_document(organization=org,actor=owner,document_type='general',title='سند مصنوعی قرارداد استخدام — فقط توسعه',reference='WCF-EMPLOYMENT-SYNTHETIC',target=relationship,category=category,upload=SimpleUploadedFile('employment-v1.png',png(b'\xee\xee\xee'),content_type='image/png'))
versions=list(document.versions.order_by('version_number'))
if len(versions)==1:
 versions.append(add_document_version(document=document,actor=owner,upload=SimpleUploadedFile('employment-v2.png',png(b'\xdd\xdd\xdd'),content_type='image/png')))
assert len(versions)==2
record={'provenance':label,'identity':'Explicit Employee.user + Person.user + WorkRelationship; reused unchanged','document':str(document.pk),'relationship':str(relationship.pk),'category':str(category.pk),'scanner_authority':'Existing PD-WC-07 bounded temporary processing duty; existing platform-duty service permits one active Superuser to grant a separate target; target is neither actor nor approver; no catalogue/default/tenant-role changes','scans':[]}
save('EMPLOYMENT_FIXTURE.json',record)
assignment=assign_platform_role(actor=User.objects.get(username='superuser'),approver=User.objects.get(username='superuser'),target=scanner_actor,role='platform_operations',reason='PD-WC-07 / final-closure authorized synthetic employment source scan only',ends_at=timezone.now()+timedelta(hours=1))
try:
 scanner=sorted(Path('C:/ProgramData/Microsoft/Windows Defender/Platform').glob('*/MpCmdRun.exe'))[-1]
 for version in versions:
  digest=hashlib.sha256(Path(version.file.path).read_bytes()).hexdigest();assert digest==version.sha256
  scan=subprocess.run([str(scanner),'-Scan','-ScanType','3','-File',version.file.path,'-DisableRemediation'],capture_output=True,text=True,timeout=55)
  assert scan.returncode==0 and 'found no threats' in scan.stdout.lower(), 'Genuine scanner did not return a clean result'
  assert hashlib.sha256(Path(version.file.path).read_bytes()).hexdigest()==digest
  assessment=record_document_processing_assessment(version=version,actor=scanner_actor,verdict='clean',adapter_code='microsoft-defender-mpcmdrun',adapter_version=scanner.parent.name,details={'exit_code':scan.returncode,'stdout_sha256':hashlib.sha256(scan.stdout.encode()).hexdigest(),'synthetic':True})
  record['scans'].append({'version':str(version.pk),'sha256':digest,'assessment':str(assessment.pk),'exit_code':scan.returncode,'scanner':str(scanner),'stdout':scan.stdout.strip()});save('EMPLOYMENT_FIXTURE.json',record)
finally:
 revoke_platform_role(actor=User.objects.get(username='superuser'),approver=User.objects.get(username='superuser'),assignment_id=assignment.pk,reason='Final synthetic employment scan complete; PD-WC-07 duty revoked')
 record['temporary_platform_duty']='REVOKED';save('EMPLOYMENT_FIXTURE.json',record)
today=timezone.localdate(timezone=ZoneInfo(org.settings.timezone));assert today>relationship.effective_start
with transaction.atomic():
 first=record_employment_version(actor=manager,organization=org,relationship=relationship,record_key='WCF-EMPLOYMENT',kind='contract',effective_from=relationship.effective_start,effective_to=today-timedelta(days=1),document_version=versions[0],reason=label)
 before={f.attname:getattr(first,f.attname) for f in first._meta.concrete_fields}
 second=record_employment_version(actor=manager,organization=org,relationship=relationship,record_key='WCF-EMPLOYMENT',kind='contract',effective_from=today,effective_to=None,document_version=versions[1],reason=label,supersedes=first)
 first.refresh_from_db();assert before=={f.attname:getattr(first,f.attname) for f in first._meta.concrete_fields}
 history=own_employment_history(actor=own,organization=org);assert len(history.rows)==2
 assert {r.status_label for r in history.rows}=={'تاریخی','مؤثر'}
record.update(records=[str(first.pk),str(second.pk)],first_record_unchanged=True,versions=[r.version for r in history.rows],effective_dates=[{'from':r.effective_from,'to':r.effective_to,'status':r.status_label} for r in history.rows]);save('EMPLOYMENT_FIXTURE.json',record)
print('Synthetic Development history: two append-only versions; real scan; explicit identity; temporary scanner duty revoked')

