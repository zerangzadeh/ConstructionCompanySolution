"""Wave C Development evidence. Never serialize credentials or HTTP cookies."""
import hashlib
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(os.environ['TEMP']) / 'bonira-wave-c-tools'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
import django
django.setup()
import yaml
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from apps.organizations.models import Organization, OrganizationRole
from apps.organizations.authorization import effective_role_assignments, effective_scope_grants, get_active_membership, has_business_permission
from apps.accounts.models import User

BASE = 'http://127.0.0.1:8015'
support = runpy.run_path(str(OUT.parent / 'sp031_f128_remediation_evidence/runtime.py'), run_name='wave_c_support')
snapshot, row_hashes, digest, Parsed = (support[n] for n in ('snapshot', 'row_hashes', 'digest', 'Parsed')) if 'snapshot' in support else (support['state'].__globals__['snapshot'], support['state'].__globals__['row_hashes'], support['digest'], support['Parsed'])
login = support['login']
login.__globals__['BASE'] = BASE

def login(alias):
    from http.cookiejar import CookieJar
    from urllib.request import build_opener, HTTPCookieProcessor, Request
    from urllib.error import HTTPError
    from urllib.parse import urlencode
    jar=CookieJar()
    opener=build_opener(HTTPCookieProcessor(jar))
    def request(path,data=None):
        if data is not None:
            token=next(c.value for c in jar if c.name=='csrftoken')
            data=data|{'csrfmiddlewaretoken':token}
        req=Request(BASE+path,data=None if data is None else urlencode(data).encode(),headers={'Referer':BASE+path})
        try: response=opener.open(req,timeout=45)
        except HTTPError as exc: response=exc
        return response.status,response.read().decode(),response.geturl()
    request('/accounts/login/')
    command="$c=Import-Clixml -LiteralPath ($env:LOCALAPPDATA+'/BONIRA/UIUXRuntimeAudit/credentials/"+alias+".clixml'); $c.GetNetworkCredential().Password"
    secret=subprocess.run([r'C:\Users\azera\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe','-NoProfile','-Command',command],capture_output=True,text=True,check=True).stdout.strip()
    status,body,url=request('/accounts/login/',dict(username=alias,password=secret))
    del secret
    assert status==200 and '/accounts/login/' not in url
    return request

def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, default=str, indent=2)+'\n', encoding='utf-8')

def guard():
    assert settings.SETTINGS_MODULE == 'config.settings.development' and settings.DEBUG
    assert connection.vendor == 'postgresql' and connection.settings_dict['NAME'] == 'construction_erp'
    assert connection.settings_dict['HOST'] in ('localhost', '127.0.0.1', '::1')
    ex = MigrationExecutor(connection)
    assert not ex.migration_plan(ex.loader.graph.leaf_nodes())
    with connection.cursor() as cursor:
        cursor.execute('SET default_transaction_read_only = off')

def files():
    names = subprocess.check_output(['git', 'ls-files'], cwd=ROOT, text=True).splitlines()
    names += [str(p.relative_to(ROOT)).replace('\\', '/') for parent in ('docs/governance/uiux', 'graphify-out', 'tests', 'protected_documents') for p in (ROOT/parent).rglob('*') if p.is_file() and OUT not in p.parents and '__pycache__' not in p.parts]
    return {n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in sorted(set(names)) if (ROOT/n).is_file()}

def ground():
    guard()
    assert not (OUT/'ENTRY.json').exists()
    save('ENTRY.json', dict(branch=subprocess.check_output(['git','branch','--show-current'],text=True).strip(), head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(), upstream=subprocess.check_output(['git','rev-parse','@{upstream}'],text=True).strip(), status=subprocess.check_output(['git','status','--short'],text=True), diff_stat=subprocess.check_output(['git','diff','--stat'],text=True), index_sha256=hashlib.sha256((ROOT/'.git/index').read_bytes()).hexdigest(), settings=settings.SETTINGS_MODULE, database={k:connection.settings_dict[k] for k in ('ENGINE','HOST','PORT','NAME')}, pending_migrations=0, authority='User attached Wave C end-to-end brief; supersedes audit observation-only mechanics for bounded fixes and synthetic preparation only', initial_touch_set=['wave_c_evidence/', 'UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md', 'UIUX_RUNTIME_VALIDATION_RESULTS.yaml append Wave C', 'UIUX_FINDINGS_REGISTER.yaml append evidence/findings', 'UIUX_ROOT_PATTERN_IMPACT_MAP.yaml append Wave C'], migration='NO', production=False, cep078079='NOT_EXECUTED', git_writes='NOT_EXECUTED'))
    save('FILES_BEFORE.json', files())
    save('RUNTIME_ENTRY.json', dict(models=snapshot(), rows=row_hashes()))
    inventory()

def inventory():
    guard()
    fixture=json.loads((OUT.parent/'UIUX_RUNTIME_FIXTURE_REGISTRY.yaml').read_text(encoding='utf-8'))
    org=Organization.objects.get(slug='demo-construction-01')
    rows=[]
    for p in fixture['personas']:
        alias=p.get('identity')
        u=User.objects.filter(username=alias).first() if alias else None
        m=get_active_membership(user=u,organization=org) if u else None
        rows.append(dict(persona=p['persona'],actor=alias,active=bool(u and u.is_active),membership=str(m.pk) if m else None,staff=bool(u and u.is_staff),superuser=bool(u and u.is_superuser),roles=list(effective_role_assignments(m).values('role__code')) if m else [],scopes=list(effective_scope_grants(m).values()) if m else []))
    role_rows=[]
    for role in OrganizationRole.objects.order_by('code'):
        role_rows.append(dict(code=role.code,permissions=list(role.permissions.order_by('code').values_list('code',flat=True))))
    counts={m._meta.label:m._base_manager.count() for m in apps.get_models() if m._meta.app_label in ('accounting','procurement','workforce','payroll','documents','timekeeping','commercial','contracts','subledgers')}
    save('INVENTORY.json',dict(personas=rows,roles=role_rows,counts=counts))
    print('Inventory:',len(role_rows),'roles;',len(counts),'domain model counts; saved without secrets')

def prepare():
    from datetime import date, timedelta
    from django.db import transaction
    from django.utils import timezone
    from apps.projects.models import Project
    from apps.procurement.models import PurchaseRequest, PurchaseOrder
    from apps.procurement.rfq_services import create_rfq, add_rfq_line, submit_rfq_for_issue, issue_rfq
    from apps.procurement.portal_services import create_supplier_portal_invitation, accept_supplier_portal_invitation
    from apps.accounting.reporting import retain_statement
    guard()
    assert not (OUT/'FIXTURES.json').exists()
    made = dict(rfqs={}, statements={}, external={'status':'BLOCKED_AUTHORIZATION_FIXTURE','reason':'Canonical supplier_portal.invitations_manage excluded from every default role; actual owner invitation service denied. Entire initial preparation transaction rolled back, including external account.'}, temporary_authority='NONE', role_permission_changes=[], canonical_roles_created=0)
    with transaction.atomic():
        for key,code in [('A','PRJ-01-01'),('C','PRJ-01-03'),('X','PRJ-02-01')]:
            project=Project.objects.get(code=code)
            org=project.organization
            actor=User.objects.get(username=f'account.{org.slug}.owner')
            req=PurchaseRequest.objects.filter(project=project,status='approved').order_by('pk').first()
            assert req and req.items.exists()
            supplier=PurchaseOrder.objects.filter(project=project).select_related('supplier').first().supplier
            rfq=create_rfq(organization=org,actor=actor,project=project,purchase_request=req,rfq_number='WAVE-C-RFQ-'+key,title='Wave C synthetic opportunity '+key,closing_at=timezone.now()+timedelta(days=2),earliest_opening_at=timezone.now()+timedelta(days=3))
            item=req.items.first()
            add_rfq_line(organization=org,actor=actor,rfq=rfq,purchase_request_item=item,quantity=item.quantity)
            submit_rfq_for_issue(organization=org,actor=actor,rfq=rfq)
            version=issue_rfq(organization=org,actor=actor,rfq=rfq,suppliers=[supplier],idempotency_key='WAVE-C-ISSUE-'+key)
            invitation=version.invitations.get()
            made['rfqs'][key]=dict(id=str(rfq.pk),project=code,number=rfq.rfq_number,invitation=str(invitation.pk))
        for key,slug in [('A','demo-construction-01'),('X','demo-construction-02')]:
            org=Organization.objects.get(slug=slug)
            actor=User.objects.get(username='account.demo-construction-01.accountant' if key=='A' else f'account.{slug}.owner')
            statement=retain_statement(organization=org,actor=actor,kind='trial_balance',ends_on=date(2026,10,22))
            made['statements'][key]=str(statement.pk)
    save('FIXTURES.json',made)
    save('RUNTIME_BEFORE.json',dict(models=snapshot(),rows=row_hashes()))
    print('Canonical preparation: three synthetic RFQs/invitations; two immutable statement projections. External portal BLOCKED. No role/permission changes.')

def http():
    import re
    from urllib.parse import urlencode
    from apps.projects.models import Project
    from apps.contracts.models import Contract
    from apps.commercial.models import TenderBid
    from apps.inventory.models import Warehouse
    from apps.documents.services import get_organization_documents
    from apps.documents.models import Document
    from apps.workforce.models import Employee
    guard()
    phase=sys.argv[2] if len(sys.argv)>2 else 'before'
    fixtures=json.loads((OUT/'FIXTURES.json').read_text())
    org=Organization.objects.get(slug='demo-construction-01')
    projects={k:Project.objects.get(code=c) for k,c in [('A','PRJ-01-01'),('C','PRJ-01-03'),('X','PRJ-02-01')]}
    actor=User.objects.get(username='uiux.audit.project')
    docs={}
    docs['A']=get_organization_documents(user=actor,organization=org).first()
    docs['C']=Document.objects.get(pk='f64e5b6b-a99e-4501-895b-7ef68cc75c95')
    docs['X']=Document.objects.get(pk='52127753-fe11-4fe6-bc8b-a072549d7c31')
    records=[]
    sessions={}
    tokens={}
    def request(scenario,alias,path,case,data=None):
        if alias not in sessions: sessions[alias]=login(alias)
        if data is not None and tokens.get(alias): data=data|{'csrfmiddlewaretoken':tokens[alias]}
        status,body,url=sessions[alias](path,data)
        parsed=Parsed(body)
        if parsed.token: tokens[alias]=parsed.token
        clean=re.sub(r'<input[^>]*name="csrfmiddlewaretoken"[^>]*>', '<!-- CSRF omitted -->',body)
        main=re.search(r'<main\b[^>]*>(.*)</main>',clean,re.S)
        # Retain only main content, not unnecessary global profile/navigation data.
        filename=f'{phase}_http_{len(records)+1:03}.html'
        (OUT/filename).write_text(main.group(0) if main else '<!-- Non-rendered protected response; SHA retained -->',encoding='utf-8')
        records.append(dict(scenario=scenario,actor=alias,path=path,case=case,method='POST' if data is not None else 'GET',status=status,final_path=url.removeprefix(BASE),response_sha256=hashlib.sha256(body.encode()).hexdigest(),html=filename,errors=parsed.errors,selects=parsed.fields))
        save(phase+'_HTTP.json',records)
        return parsed
    viewer='uiux.audit.project';manager='uiux.persona.project-manager';accountant='account.demo-construction-01.accountant';site='uiux.reference.batch03.site-only'
    for alias in (() if phase=='before2' else (viewer,manager,site)):
        for key,r in fixtures['rfqs'].items():
            p=f"/procurement/rfqs/{r['id']}/buyer/"
            parsed=request('RV-007',alias,p,'buyer scope '+key)
            for action in ('prepare_comparison','finalize_award'):
                path=p+action+'/'
                parsed=request('RV-007',alias,path,'action authorization '+key+' '+action)
                request('RV-007',alias,path,'manipulated action POST '+key+' '+action,{'csrfmiddlewaretoken':parsed.token,'rfq':r['id'],'project':str(projects['X'].pk)})
    for path in ['/inventory/','/inventory/custody/','/inventory/valuation/']:
        request('RV-009',viewer,path,'quantity/custody/value read')
    for k,p in projects.items():
        w=Warehouse.objects.filter(project=p,archived_at__isnull=True).first()
        if w: request('RV-009',viewer,f'/inventory/{w.pk}/','warehouse scope '+k)
    for alias in (accountant,viewer,manager):
        for path in ['/accounting/statements/','/accounting/statements/?kind=trial_balance&ends_on=1405%2F07%2F30']+[f'/accounting/statements/{r}/' for r in fixtures['statements'].values()]:
            parsed=request('RV-011',alias,path,'statement authority and tenant')
        request('RV-011',alias,'/accounting/statements/?kind=invalid&ends_on=invalid','invalid redisplay')
        request('RV-011',alias,'/accounting/statements/run/','manipulated invalid run',{'csrfmiddlewaretoken':parsed.token,'kind':'invalid','ends_on':'invalid','organization':str(projects['X'].organization_id)})
    for alias in (viewer,accountant):
        request('RV-013',alias,'/subledgers/','settlement workbench; empty obligation baseline')
    for path in ['/workforce/departments/','/workforce/positions/','/workforce/teams/','/workforce/employees/create/','/workforce/foundation/']:
        parsed=request('RV-015',viewer,path,'retained read subset / unauthorized administration')
        if path.endswith('create/'):
            request('RV-015',viewer,path,'manipulated employee POST',{'csrfmiddlewaretoken':parsed.token,'organization':str(projects['X'].organization_id),'first_name':'Wave C denied','last_name':'Synthetic'})
    for path in ['/timekeeping/','/timekeeping/calendars/new/']:
        parsed=request('RV-017',viewer,path,'attendance read / calendar authority')
        if path.endswith('new/'):
            request('RV-017',viewer,path,'manipulated calendar POST',{'csrfmiddlewaretoken':parsed.token,'code':'WAVE-C-DENIED','name':'Synthetic denied','organization':str(projects['X'].organization_id)})
    for path in ['/payroll/','/payroll/statutory/','/payroll/financial-handoffs/']:
        request('RV-018',viewer,path,'unauthorized control only; no specialist substitution')
    for path in ['/documents/','/documents/mine/','/documents/upload/']:
        parsed=request('RV-028',viewer,path,'document read / protected write')
        if path.endswith('upload/'):
            request('RV-028',viewer,path,'manipulated upload POST',{'csrfmiddlewaretoken':parsed.token,'title':'WAVE-C-DENIED','organization':str(projects['X'].organization_id)})
    for k,d in docs.items():
        if not d: continue
        for suffix in ('','versions/add/','links/add/'):
            parsed=request('RV-028',viewer,f'/documents/{d.pk}/'+suffix,'document scope '+k)
            if suffix:request('RV-028',viewer,f'/documents/{d.pk}/'+suffix,'manipulated document POST '+k,{'csrfmiddlewaretoken':parsed.token,'document':str(d.pk),'project':str(projects['X'].pk)})
    request('RV-029',viewer,'/workforce/ess/employment/','unlinked own-identity fails closed')
    for k,p in projects.items():
        employee=Employee.objects.filter(organization=p.organization,archived_at__isnull=True).first()
        request('RV-029',viewer,f'/workforce/employees/{employee.pk}/','employee tenant '+k)
    for path in ['/contracts/','/contracts/contractual-records/','/commercial/']:
        request('RV-030',viewer,path,'commercial read')
    for k,p in projects.items():
        c=Contract.objects.filter(project=p,deleted_at__isnull=True).first()
        t=TenderBid.objects.filter(project=p).first()
        if c:
            for suffix in ('','commercial-review/'):
                request('RV-030',viewer,f'/contracts/{c.pk}/'+suffix,'contract scope '+k)
        if t:
            for suffix in ('','revise/','evidence/'):
                parsed=request('RV-030',viewer,f'/commercial/{t.pk}/'+suffix,'tender scope '+k)
                if suffix:request('RV-030',viewer,f'/commercial/{t.pk}/'+suffix,'manipulated commercial POST '+k,{'csrfmiddlewaretoken':parsed.token,'project':str(projects['X'].pk),'title':'WAVE-C-DENIED'})
    for alias in (viewer,manager,site):
        for k,p in projects.items():
            for suffix in ('','comparison/','exceptions/','cost-reconciliation/'):
                request('RV-031',alias,f'/projects/{p.pk}/controls/'+suffix,'controls scope '+k)
        for path in ['/estimates/','/estimates/create/']:
            request('RV-031',alias,path,'estimate read/create authority')
    for path in ['/procurement/portal/accept/']+[f"/procurement/rfq-invitations/{r['invitation']}/portal/" for r in fixtures['rfqs'].values()]:
        parsed=request('RV-032',viewer,path,'internal account negative; no external persona claim')
        request('RV-032',viewer,path,'manipulated portal negative',{'csrfmiddlewaretoken':parsed.token,'token':'WAVE-C-INVALID-TOKEN','invited_email':'wave-c@example.invalid'})
    save('BROWSER_INPUT.json',dict(base=BASE,docs={k:str(d.pk) for k,d in docs.items() if d},rfqs=fixtures['rfqs'],statements=fixtures['statements'],project_a=str(projects['A'].pk)))
    print(phase,'HTTP observations',len(records),'statuses', {s:sum(r['status']==s for r in records) for s in sorted({r['status'] for r in records})})

def inventory_persona():
    import secrets
    from django.db import transaction
    from apps.organizations.services import create_organization_account
    from apps.organizations.access_services import assign_membership_role, grant_membership_scope
    from apps.accounts.services import initialize_personal_password
    guard()
    org=Organization.objects.get(slug='demo-construction-01')
    owner=User.objects.get(username='account.demo-construction-01.owner')
    independent=get_active_membership(user=User.objects.get(username='admin'),organization=org)
    alias='uiux.persona.inventory'
    secret=secrets.token_urlsafe(30)
    with transaction.atomic():
        u,m=create_organization_account(organization=org,actor=owner,username=alias,temporary_password=secret,role='viewer')
        assignment=assign_membership_role(organization=org,actor=owner,membership_id=m.pk,role='viewer',approver_membership_id=independent.pk,reason='Wave C P-22 persistent inventory read persona. Existing viewer only; organization read scope required by canonical custody/valuation gates. No inventory mutations.')
        grant=grant_membership_scope(organization=org,actor=owner,membership_id=m.pk,scope_type='organization',approver_membership_id=independent.pk,reason='Wave C P-22 organization-wide inventory read workspaces require organization scope. Shared P-01 remains project scoped.')
        initialize_personal_password(user=u,new_password=secret)
    command="$v=[Console]::In.ReadToEnd()|ConvertFrom-Json; $s=ConvertTo-SecureString $v.password -AsPlainText -Force; $c=[pscredential]::new($v.alias,$s); $p=Join-Path $env:LOCALAPPDATA ('BONIRA/UIUXRuntimeAudit/credentials/'+$v.alias+'.clixml'); if(Test-Path -LiteralPath $p){throw 'Credential exists'}; $c|Export-Clixml -LiteralPath $p"
    subprocess.run([r'C:\Users\azera\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe','-NoProfile','-Command',command],input=json.dumps(dict(alias=alias,password=secret)),capture_output=True,text=True,check=True)
    del secret
    save('INVENTORY_PERSONA.json',dict(persona='P-22',actor=alias,role='viewer',scope='organization',membership=m.pk,assignment=assignment.pk,scope_grant=grant.pk,persistent=True,temporary_authority=False,existing_role_permission_count=80,explicitly_excluded='No stock/value mutation, no posting, no private employee/payroll access',authorization='User permits minimum existing canonical role/scope assignments; Checkpoint 15 retains persistent reference accounts',credential_storage='Windows current-user DPAPI outside repository'))

def delta():
    from datetime import date
    from django.core.exceptions import PermissionDenied
    from django.db import transaction
    from apps.audit.models import AuditEvent
    from apps.accounting.reporting import build_statement
    from apps.inventory.p8_services import valuation_reconciliation
    from apps.documents.services import get_organization_document, get_document_version_for_download
    from apps.procurement.rfq_services import get_organization_rfq
    from apps.procurement.portal_services import create_supplier_portal_invitation
    from apps.procurement.models import RequestForQuotationInvitation
    from apps.projects.models import Project
    guard()
    org=Organization.objects.get(slug='demo-construction-01')
    foreign=Organization.objects.get(slug='demo-construction-02')
    fixture=json.loads((OUT/'FIXTURES.json').read_text())
    inp=json.loads((OUT/'BROWSER_INPUT.json').read_text())
    records=[]
    for alias,paths in [
        ('uiux.persona.inventory',['/inventory/','/inventory/custody/','/inventory/valuation/']),
        ('account.demo-construction-01.accountant',['/subledgers/']),
        ('uiux.audit.project',[f"/contracts/1c869bb0-cb4b-4a47-8210-87167b90ee6f/commercial-review/",f"/projects/{inp['project_a']}/controls/",f"/procurement/rfqs/{fixture['rfqs']['A']['id']}/buyer/"]),
    ]:
        request=login(alias)
        for path in paths:
            status,body,url=request(path)
            assert status==200,(alias,path,status)
            records.append(dict(actor=alias,path=path,status=status,method='GET',sha256=hashlib.sha256(body.encode()).hexdigest()))
        if alias=='uiux.persona.inventory':
            for path in ['/inventory/valuation/','/inventory/custody/']:
                before=AuditEvent.objects.count()
                status,body,url=request(path,{'organization':str(foreign.pk)})
                assert status==405,(path,status)
                assert AuditEvent.objects.count()==before
                records.append(dict(actor=alias,path=path,status=status,method='POST',case='valid CSRF, read-only method rejected; no audit mutation'))
    direct=[]
    def outcome(alias,case,expected,call):
        actor=User.objects.get(username=alias)
        try:
            with transaction.atomic():
                value=call(actor)
                transaction.set_rollback(True)
        except PermissionDenied:
            result='DENIED'
        else:
            result='ALLOWED_ROLLED_BACK'
        assert result==expected,(alias,case,result)
        direct.append(dict(actor=alias,case=case,result=result,persisted_delta=0))
    for alias in ['uiux.persona.inventory','uiux.audit.project']:
        outcome(alias,'separately protected valuation reconciliation','DENIED',lambda u:valuation_reconciliation(organization=org,actor=u))
    for alias in ['uiux.audit.project','uiux.persona.project-manager','account.demo-construction-01.accountant']:
        for tenant,label in [(org,'same tenant'),(foreign,'cross tenant')]:
            allowed=alias.endswith('.accountant') and tenant==org
            outcome(alias,'statement '+label,'ALLOWED_ROLLED_BACK' if allowed else 'DENIED',lambda u,t=tenant:build_statement(organization=t,actor=u,kind='trial_balance',ends_on=date(2026,10,22)))
    for key,r in fixture['rfqs'].items():
        outcome('uiux.persona.project-manager','RFQ '+key,'ALLOWED_ROLLED_BACK' if key=='A' else 'DENIED',lambda u,r=r:get_organization_rfq(user=u,organization=org,rfq_id=r['id']))
    for key,id in inp['docs'].items():
        outcome('uiux.audit.project','document '+key,'ALLOWED_ROLLED_BACK' if key=='A' else 'DENIED',lambda u,id=id:get_organization_document(user=u,organization=org,document_id=id))
    for alias in ['account.demo-construction-01.owner','uiux.persona.tenant-admin','uiux.persona.project-manager']:
        outcome(alias,'portal invitation management','DENIED',lambda u:create_supplier_portal_invitation(organization=org,actor=u,rfq_invitation=RequestForQuotationInvitation.objects.get(pk=fixture['rfqs']['A']['invitation']),invited_email='wave-c@example.invalid',expires_at=__import__('django.utils.timezone',fromlist=['now']).now()+__import__('datetime').timedelta(hours=1)))
    # Exercise real protected binary downloads; retain no document content.
    request=login('uiux.audit.project')
    for key,id in inp['docs'].items():
        # The retained helper decodes text; independent authenticated opener is not
        # needed to establish safe version lookup and denial; no file is exported.
        outcome('uiux.audit.project','download version '+key+' (A: unavailable safety assessment; C/X: scope)','DENIED',lambda u,id=id:get_document_version_for_download(document=get_organization_document(user=u,organization=org,document_id=id),version_id=str(get_organization_document(user=u,organization=org,document_id=id).current_version_id),actor=u))
    save('DELTA_HTTP.json',records)
    save('DIRECT_SERVICE.json',direct)
    print('Delta HTTP',len(records),'direct service',len(direct),'expected outcomes PASS')

def integrity():
    guard()
    before=json.loads((OUT/'RUNTIME_ENTRY.json').read_text())
    current=dict(models=snapshot(),rows=row_hashes())
    differences={m:current['models'][m]['count']-before['models'][m]['count'] for m in current['models'] if current['models'][m]!=before['models'][m]}
    changed=[(m,pk) for m,rows in before['rows'].items() if m!='sessions.Session' for pk,h in rows.items() if current['rows'][m].get(pk)!=h]
    allowed={'accounts.User','organizations.OrganizationMembership','organizations.MembershipRoleAssignment','organizations.MembershipScopeGrant','organizations.AuthorizationMigrationIssue','audit.AuditEvent','sessions.Session','procurement.RequestForQuotation','procurement.RequestForQuotationLine','procurement.RequestForQuotationVersion','procurement.RequestForQuotationVersionLine','procurement.RequestForQuotationInvitation','accounting.FinancialStatementRun','accounting.FinancialStatementLineSnapshot'}
    assert not changed,changed
    assert set(differences)<=allowed,differences
    assert differences.get('accounts.User')==differences.get('organizations.OrganizationMembership')==differences.get('organizations.MembershipRoleAssignment')==differences.get('organizations.MembershipScopeGrant')==1
    assert differences.get('procurement.RequestForQuotation')==3
    assert differences.get('accounting.FinancialStatementRun')==2
    audits=apps.get_model('audit.AuditEvent').objects.exclude(pk__in=before['rows']['audit.AuditEvent'])
    from collections import Counter
    counts=Counter(audits.values_list('action',flat=True))
    save('INTEGRITY.json',dict(models=len(current['models']),deltas=differences,preexisting_rows_changed=changed,audit_actions=counts,role_permission_definitions_unchanged=all(before['models'][m]==current['models'][m] for m in current['models'] if m in ['organizations.OrganizationRole','organizations.BusinessPermission'] or 'permission' in m.lower()),temporary_authority='NONE',retained_reference='P-22 inventory Viewer with organization scope; explicit user authority and Checkpoint 15',unauthorized_business_mutations=0,portal_failed_preparation_rolled_back=True,excluded_fields=['accounts.User.last_login'],new_rows={m:sorted(set(current['rows'][m])-set(before['rows'][m])) for m in differences if m!='sessions.Session'}))
    save('RUNTIME_AFTER.json',current['models'])
    print('Integrity:',len(current['models']),'models; no preexisting row changes;',dict(counts))

def populated_statement():
    from datetime import date
    from decimal import Decimal
    from django.db import transaction
    from django.core.exceptions import PermissionDenied,ValidationError
    from apps.accounting.models import FiscalPeriod,Account,JournalEntry
    from apps.accounting.services import create_journal,add_journal_line,submit_journal,post_journal
    from apps.accounting.reporting import retain_statement
    guard()
    assert not (OUT/'POPULATED_STATEMENT.json').exists()
    org=Organization.objects.get(slug='demo-construction-01')
    accountant=User.objects.get(username='account.demo-construction-01.accountant')
    reviewer=User.objects.get(username='uiux.persona.tenant-admin')
    marker='WAVE-C-SYNTHETIC-STATEMENT'
    assert not JournalEntry.objects.filter(source_key=marker).exists()
    try:
        with transaction.atomic():
            period=FiscalPeriod.objects.get(organization=org,status='open',starts_on__lte=date(2026,10,22),ends_on__gte=date(2026,10,22))
            debit=Account.objects.get(organization=org,code='5100',is_posting=True,archived_at__isnull=True)
            credit=Account.objects.get(organization=org,code='2100',is_posting=True,archived_at__isnull=True)
            j=create_journal(organization=org,actor=accountant,period=period,kind='manual',document_date=date(2026,10,22),accounting_date=date(2026,10,22),description='Wave C synthetic Development-only statement presentation control, 1 IRR; no source recognition or settlement',source_key=marker,evidence_reference='Wave C user-authorized synthetic Development fixture')
            add_journal_line(organization=org,actor=accountant,journal=j,account=debit,line_number=1,debit=Decimal('1'))
            add_journal_line(organization=org,actor=accountant,journal=j,account=credit,line_number=2,credit=Decimal('1'))
            submit_journal(organization=org,actor=accountant,journal=j)
            post_journal(organization=org,actor=reviewer,journal=j,reason='Wave C synthetic 1 IRR test record; independent existing approver; Development only')
            r=retain_statement(organization=org,actor=accountant,kind='trial_balance',ends_on=date(2026,10,22))
            assert r.lines.count()==2
    except (PermissionDenied,ValidationError,ValueError) as exc:
        save('POPULATED_STATEMENT.json',dict(status='BLOCKED',service_error=str(exc),rolled_back=True,policy_changes=[],scope='No posting policy or business rule invented; empty projection and isolated positive tests retained'))
        print('Populated statement preparation blocked by canonical service; transaction rolled back')
    else:
        save('POPULATED_STATEMENT.json',dict(status='PREPARED',journal=str(j.pk),statement=str(r.pk),source_lines=2,amount='1 IRR',preparer=accountant.username,independent_poster=reviewer.username,service_chain=['create_journal','add_journal_line x2','submit_journal','post_journal','retain_statement'],new_policy='NONE',cleanup='Retain immutable synthetic Development journal and statement; never silently delete posted history'))
        data=json.loads((OUT/'FIXTURES.json').read_text());data['statements']['populated']=str(r.pk);save('FIXTURES.json',data)

def readiness():
    from django.db import transaction
    from django.core.exceptions import PermissionDenied
    from apps.commercial.services import create_tender_bid
    from apps.projects.models import Project
    from apps.organizations.models import BusinessPermissionCode
    guard()
    org=Organization.objects.get(slug='demo-construction-01')
    matrix={}
    for code in ['supplier_portal.invitations_manage','employment_records.manage','employment_records.view_own','time_calendars.manage','employees.create','payroll.prepare','documents.upload','project_controls.compare']:
        matrix[code]=list(OrganizationRole.objects.filter(permissions__code=code).values_list('code',flat=True))
    try:
        with transaction.atomic():
            tender=create_tender_bid(actor=User.objects.get(username='uiux.persona.project-manager'),organization=org,project=Project.objects.get(code='PRJ-01-01'),opportunity_code='WAVE-C-TENDER',title='Wave C synthetic opportunity',reason='Minimum synthetic Development fixture; existing canonical service and policy only')
            transaction.set_rollback(True)
    except PermissionDenied as exc:
        tender_result=dict(result='DENIED',reason=str(exc),transaction='ROLLED_BACK',activation_policy_modified=False)
    else:
        tender_result=dict(result='ALLOWED_ROLLED_BACK',id=str(tender.pk))
    save('READINESS.json',dict(permission_role_matrix=matrix,tender=tender_result,payroll_role_boundary='apps/accounts/management/commands/seed_account_data.py: _ensure_p7_demo_payroll_access: designated Development demo-owner-only assurance role; not a Payroll-only specialist bundle',employment_internal_routes='Only workforce/ess/employment/ exists; no internal management endpoint for employment_records.manage in workforce/urls.py',document_safety='Both P-19-authorized existing documents unavailable; get_document_version_for_download denies. Processing assessment requires Platform Operations plus actual scanner verdict; no mock CLEAN result was supplied.',temporary_authority='NONE',negative_portal_evidence='DIRECT_SERVICE.json; all three existing internal actors denied invitation-management service'))
    print('Readiness recorded; tender',tender_result['result'])

if __name__=='__main__':
    globals()[sys.argv[1]]()
