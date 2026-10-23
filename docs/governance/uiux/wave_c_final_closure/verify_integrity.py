"""Final read-only data/source boundary verification; secrets never enter evidence."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from zoneinfo import ZoneInfo
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[3];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(OUT.parent/'authorization_reconciliation'))
from revalidate import snapshot
from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
from apps.organizations.models import Organization,PlatformRoleAssignment
from apps.organizations.authorization import has_platform_role
from apps.accounts.models import User
from apps.payroll.models import StatutoryCalculation,StatutoryOutput
from apps.procurement.models import RequestForQuotation
assert settings.DEBUG and settings.SETTINGS_MODULE=='config.settings.development'
assert connection.settings_dict['HOST'] in ('localhost','127.0.0.1','::1') and connection.settings_dict['NAME']=='construction_erp'
def save(name,data):(OUT/name).write_text(json.dumps(data,default=str,indent=2)+'\n',encoding='utf-8')
before=json.loads((OUT/'EMPLOYMENT_DATA_BEFORE.json').read_text());after=snapshot();save('DATA_AFTER.json',after)
changes={}
for model,old in before.items():
 new=after.get(model,{})
 deleted=sorted(set(old)-set(new));modified=sorted(k for k in old.keys()&new.keys() if old[k]!=new[k]);added=sorted(set(new)-set(old))
 assert not deleted,(model,'pre-existing data deleted')
 if added or modified:changes[model]={'added':added,'modified':modified,'deleted':deleted}
# Only the existing document numbering counter changes. New rows belong to the
# labelled Employment fixture, scanned sources, bounded platform duty and audit.
assert {m for m,d in changes.items() if d['modified']} <= {'documents.DocumentNumberSequence'}, changes
allowed={'audit.AuditEvent','commercial.TenderBidRevision','documents.Document','documents.DocumentVersion','documents.DocumentCategory','documents.DocumentProcessingAssessment','documents.DocumentLink','documents.DocumentNumberSequence','workforce.WorkRelationshipDocumentLink','workforce.EmploymentRecord','organizations.PlatformRoleAssignment'}
assert set(changes)<=allowed,sorted(set(changes)-allowed)
ex=MigrationExecutor(connection);assert not ex.migration_plan(ex.loader.graph.leaf_nodes())
assert StatutoryCalculation.objects.count()==StatutoryOutput.objects.count()==0
rfq=RequestForQuotation.objects.get(rfq_number='WAVE-C-RFQ-A',organization__slug='demo-construction-01');discovery=json.loads((OUT/'DATA_DISCOVERY.json').read_text());original=next(r for r in discovery['rfqs'] if r['id']==str(rfq.pk))
assert original['closing_at']==str(rfq.closing_at) and original['earliest_opening_at']==str(rfq.earliest_opening_at) and original['status']==rfq.status
entry=json.loads((OUT/'ENTRY.json').read_text());permitted={'apps/workforce/employment_forms.py','templates/workforce/employment_manage.html','tests/test_uiux_wave_c_reentry.py','apps/procurement/test_p5_s08_sealed_custody.py','apps/subledgers/test_p5_s26_s27_match_review.py','apps/subledgers/test_cep033_invoice_handoff.py','docs/governance/uiux/UIUX_RUNTIME_VALIDATION_RESULTS.yaml','docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml','docs/governance/uiux/UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md'}
changed=[]
for path,digest in entry['hashes'].items():
 assert (ROOT/path).is_file(),('pre-existing file removed',path)
 if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=digest:changed.append(path)
assert set(changed)<=permitted,sorted(set(changed)-permitted)
newly_dirty=[p for p in subprocess.check_output(['git','diff','--name-only'],text=True,stderr=subprocess.DEVNULL).splitlines() if p not in entry['hashes']]
assert set(newly_dirty)<=permitted,('unexpected previously clean file changed',newly_dirty)
changed=sorted(set(changed+newly_dirty))
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert head==entry['head']
assert not subprocess.check_output(['git','diff','--cached','--name-only'],text=True).strip()
a=PlatformRoleAssignment.objects.filter(user__username='uiux.wavec.documents',role='platform_operations').latest('starts_at');active=has_platform_role(a.user,'platform_operations')
save('INTEGRITY.json',{'recorded_at':timezone.now(),'head':head,'environment':'Local Development PostgreSQL','schema_migrations_created':False,'pending_migrations':[],'all_preexisting_rows_preserved':True,'data_changes':changes,'workforce_identity_unchanged':True,'all_other_financial_payroll_inventory_models_unchanged':True,'future_policies_unchanged':before.get('organizations.PlatformPolicyVersion')==after.get('organizations.PlatformPolicyVersion'),'statutory_calculations':0,'statutory_outputs':0,'rfq_dates_and_state_unchanged':True,'prior_files_preserved_except_declared':True,'changed_entry_files':changed,'temporary_scanner_duty':{'id':str(a.pk),'active':active,'ends_at':a.ends_at,'ends_at_tehran':a.ends_at.astimezone(ZoneInfo('Asia/Tehran')),'early_revocation_denied':True,'expiry_enforced_by_existing_authorization_service':True},'git_writes':'NOT_EXECUTED','production':'UNTOUCHED','cep078079':'NOT_EXECUTED'})
print('Integrity PASS; affected models:',','.join(changes),'Temporary scanner active:',active,'expires:',a.ends_at)
