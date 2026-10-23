"""B07 Development-only canonical fixtures, real HTTP and integrity evidence."""
import json
import runpy
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
support = runpy.run_path(str(OUT.parent/'f111_batch_06_evidence/runtime.py'), run_name='b07_support')
snapshot, row_hashes, digest, Parsed = (support[n] for n in ('snapshot','row_hashes','digest','Parsed'))
login = support['login']
login.__globals__['BASE'] = 'http://localhost:8010'
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.expenses.forms import RecurringExpenseTemplateForm
from apps.expenses.models import Expense, RecurringExpenseTemplate
from apps.expenses.services import create_recurring_expense_template, propose_recurring_expense
from apps.organizations.authorization import get_active_membership, has_business_permission
from apps.organizations.models import Organization
from apps.projects.models import Project

BASE='http://localhost:8010'
PATH='/expenses/recurrences/'
ALIASES=support['ALIASES']
CODES=support['CODES']

def save(name,data):
    (OUT/name).write_text(json.dumps(data,default=str,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def guard():
    assert settings.SETTINGS_MODULE=='config.settings.development' and settings.DEBUG
    assert connection.vendor=='postgresql' and connection.settings_dict['NAME']=='construction_erp'
    assert connection.settings_dict['HOST'] in {'localhost','127.0.0.1','::1'}
    with connection.cursor() as c:c.execute('SET default_transaction_read_only = off')
    e=MigrationExecutor(connection)
    assert not e.migration_plan(e.loader.graph.leaf_nodes())

def authority():
    rows=support['authority']()
    for r in rows:
        r['recurrences_manage']=has_business_permission(user=User.objects.get(username=r['actor']),organization=Organization.objects.get(slug=r['organization']),permission='expenses.recurrences_manage',allow_any_scope=True)
    return rows

def sources():
    return {k:RecurringExpenseTemplate.objects.select_related('project').get(source_reference_prefix='B07-RUNTIME-'+k) for k in CODES}

def prepare():
    guard()
    before={'models':snapshot(),'rows':row_hashes(),'authority':authority()}
    save('PREPARATION_BEFORE.json',before)
    assert all(r['recurrences_manage'] and not r['staff'] and not r['superuser'] for r in before['authority'])
    fixtures=[]
    with transaction.atomic():
        for key,code in CODES.items():
            project=Project.objects.select_related('organization').get(code=code)
            org=project.organization
            actor=User.objects.get(username=f'account.{org.slug}.owner')
            existing=RecurringExpenseTemplate.objects.filter(project=project).first()
            if existing:
                template=existing;created=False
            else:
                template=create_recurring_expense_template(organization=org,project=project,actor=actor,description='B07 synthetic recurring template '+key,amount=Decimal('12.50'),classification='direct',frequency='monthly',starts_on=date(2026,10,22),ends_on=date(2026,12,22),source_reference_prefix='B07-RUNTIME-'+key)
                created=True
            fixtures.append({'key':key,'id':template.pk,'project':project.pk,'project_code':code,'project_name':project.name,'description':template.description,'actor':actor.username,'created':created,'qualifying':template.is_active and template.starts_on==date(2026,10,22)})
    assert before['authority']==authority()
    save('FIXTURES.json',{'templates':fixtures,'temporary_authority':'NONE','authority_unchanged':True,'retained':'Five synthetic Development templates, canonical create service; no Expense proposal or financial transaction'})
    save('RUNTIME_BEFORE.json',{'models':snapshot(),'rows':row_hashes(),'authority':authority(),'settings':settings.SETTINGS_MODULE,'database':connection.settings_dict['NAME'],'pending_migrations':0})
    save('BROWSER_PAYLOAD.json',{'base':BASE,'path':PATH,'templates':fixtures,'create_payload':payload()})
    print('Preparation PASS: five canonical synthetic templates; existing authority unchanged')

def payload(key='B'):
    return {'project':str(sources()[key].project_id),'description':'B07 rejected synthetic runtime create','amount':'10.00','classification':'direct','frequency':'monthly','starts_on':'2026-10-22','ends_on':'2026-12-22','source_reference_prefix':'B07-REJECTED'}

def small():
    return {m._meta.label:digest(list(m.objects.order_by('pk').values())) for m in (RecurringExpenseTemplate,Expense,AuditEvent)}

def http():
    guard();src=sources();records=[];org=Organization.objects.get(slug='demo-construction-01')
    for alias,allowed in zip(ALIASES,('AB','ABCD',''),strict=True):
        request=login(alias)
        member=get_active_membership(user=User.objects.get(username=alias),organization=org)
        expected=[{'value':str(v),'label':str(l)} for v,l in RecurringExpenseTemplateForm(organization=org,membership=member).fields['project'].choices]
        def observe(label,path=PATH,data=None,expected_status=200):
            before=small();status,body,url=request(path,data);parsed=Parsed(body)
            assert status==expected_status,(alias,label,status)
            assert small()==before,(alias,label,'state changed')
            if status==200:
                assert parsed.fields['project']==expected,(alias,label,parsed.fields,expected)
                import re
                clean=re.sub(r'href="[^\"]*[?&](?:amp;)?next=[^\"]*"','',body)
                clean=re.sub(r'<input[^>]*name="next"[^>]*>','',clean)
                for key,t in src.items():
                    tokens=[str(t.pk),t.description]
                    if key in allowed:
                        assert all(v in clean for v in tokens),(alias,label,key)
                        assert str(t.project_id) in {r['value'] for r in parsed.fields['project']}
                    else:
                        assert all(v not in clean for v in tokens),(alias,label,key)
                        assert str(t.project_id) not in {r['value'] for r in parsed.fields['project']}
                        if key!='A' or allowed:
                            assert str(t.project_id) not in clean,(alias,label,key,'project UUID')
                        # Demo project display names repeat; compare only distinguishable labels.
                        permitted_names={r['label'] for r in expected}
                        if not allowed:permitted_names.add(src['A'].project.name)
                        if not any(t.project.name in n for n in permitted_names) and (key!='A' or allowed):
                            assert t.project.name not in clean,(alias,label,key,'project name')
            else:
                assert all(t.description not in body for t in src.values())
            record={'actor':alias,'case':label,'status':status,'real_authentication_csrf':True,'business_and_success_audit_unchanged':True,'forbidden_metadata':[]}
            if status==200:
                record.update(options=parsed.fields['project'],templates_visible=[k for k,t in src.items() if str(t.pk) in body],field_errors=parsed.errors)
            records.append(record);save('RUNTIME_HTTP.json',records)
            return parsed
        parsed=observe('GET')
        if allowed=='ABCD':continue
        for key in 'CDX':
            query=urlencode({'project':src[key].project_id,'template':src[key].pk,'q':src[key].description})
            parsed=observe('query/filter '+key,path=PATH+'?'+query)
        for key in ('CDX' if allowed else 'ABCDX'):
            parsed=observe('forced Project '+key,data=payload(key)|{'csrfmiddlewaretoken':parsed.token})
            assert parsed.errors
        for field in ('description','project','starts_on'):
            data=payload();data.pop(field)
            parsed=observe('missing '+field,data=data|{'csrfmiddlewaretoken':parsed.token})
            assert parsed.errors
        for key in ('CDX' if allowed else 'ABCDX'):
            observe('forced template '+key,path=PATH+str(src[key].pk)+'/propose/?project='+str(src['A'].project_id),data={'occurrence_on':'2026-10-22','csrfmiddlewaretoken':parsed.token},expected_status=404 if key=='X' else 403)
        # Authorized controls render safely without creating a persistent proposal.
        if allowed:
            observe('authorized invalid occurrence',path=PATH+str(src['B'].pk)+'/propose/',data={'occurrence_on':'2026-11-23','csrfmiddlewaretoken':parsed.token},expected_status=400)
            observe('authorized proposal GET method guard',path=PATH+str(src['B'].pk)+'/propose/',expected_status=405)
    save('HTTP_SUMMARY.json',{'all_pass':True,'observations':len(records),'unauthorized_mutations':0,'no_successful_persistent_proposal_required':True})
    print('HTTP PASS:',len(records),'observations; actual authentication/CSRF; zero business/audit delta')

def direct():
    guard();before=small();records=[]
    for alias,keys in ((ALIASES[0],'CDX'),(ALIASES[2],'ABCDX')):
        actor=User.objects.get(username=alias)
        for key in keys:
            t=sources()[key]
            for operation in ('create','propose'):
                try:
                    if operation=='propose':propose_recurring_expense(template=t,occurrence_on=date(2026,10,22),actor=actor)
                    else:
                        data=payload(key);data.update(project=t.project,starts_on=date(2026,10,22),ends_on=date(2026,12,22))
                        create_recurring_expense_template(organization=Organization.objects.get(slug='demo-construction-01'),actor=actor,**data)
                except PermissionDenied:pass
                else:raise AssertionError((alias,key,operation,'allowed'))
                assert small()==before
                records.append({'actor':alias,'key':key,'operation':operation,'denied':True,'mutations':0})
    save('DIRECT_SERVICE.json',records);print('Direct denials PASS:',len(records))

def after():
    guard();prep=json.loads((OUT/'PREPARATION_BEFORE.json').read_text());before=json.loads((OUT/'RUNTIME_BEFORE.json').read_text());current=snapshot();rows=row_hashes()
    changed=[(m,pk) for m,rs in prep['rows'].items() if m!='sessions.Session' for pk,h in rs.items() if rows[m].get(pk)!=h]
    assert not changed,changed
    deltas=[m for m,v in current.items() if v!=before['models'][m]]
    assert set(deltas)<={'sessions.Session'},deltas
    assert digest(authority())==digest(before['authority'])
    save('RUNTIME_AFTER.json',current)
    save('RUNTIME_INTEGRITY.json',{'tables':len(current),'preexisting_business_rows_changed':changed,'runtime_deltas':deltas,'unauthorized_mutations':0,'runtime_success_audits':0,'authority_fingerprint_before':digest(before['authority']),'authority_fingerprint_after':digest(authority()),'authority_unchanged':True,'temporary_authority':'NONE; no revocation necessary','last_login_excluded':True,'preparation_additions':{m:len(set(rs)-set(prep['rows'][m])) for m,rs in before['rows'].items() if set(rs)-set(prep['rows'][m])}})
    print('Integrity PASS:',len(current),'tables; only sessions changed at runtime; authority unchanged')

if __name__=='__main__':
    {'prepare':prepare,'http':http,'direct':direct,'after':after}[sys.argv[1]]()
