"""SP031-only Development confirmation. No product or authority mutations."""
import os
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
import django
django.setup()

import hashlib
import html
import json
import re
import runpy
import subprocess
from datetime import date
from urllib.parse import urlencode
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.organizations.models import Organization
from apps.organizations.authorization import (effective_role_assignments, effective_scope_grants, get_active_membership, has_business_permission)
from apps.projects.models import Project
from apps.workforce.models import Employee, EmployeeTrainingRecord, TrainingRequirement, TrainingOutcome
from apps.workforce.forms import EmployeeTrainingRecordForm
from apps.workforce.services import create_training_requirement, record_employee_training

support = runpy.run_path(str(OUT.parent/'f111_batch_08_evidence/runtime.py'), run_name='sp031_support')
snapshot, row_hashes, digest, Parsed = (support[n] for n in ('snapshot','row_hashes','digest','Parsed'))
login = support['login']
BASE = 'http://localhost:8013'
login.__globals__['BASE'] = BASE
PATH = '/workforce/foundation/training-records/create/'
ALIASES = ('uiux.persona.project-manager','uiux.persona.tenant-admin','uiux.reference.batch03.site-only')
PERMISSION = 'workforce_qualifications.manage'
CODES = dict(zip('ABCDX', ('PRJ-01-01','PRJ-01-02','PRJ-01-03','PRJ-01-04','PRJ-02-01'), strict=True))

def save(name, data):
    (OUT/name).write_text(json.dumps(data, default=str, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def guard():
    assert settings.SETTINGS_MODULE == 'config.settings.development' and settings.DEBUG
    assert connection.vendor == 'postgresql' and connection.settings_dict['NAME'] == 'construction_erp'
    assert connection.settings_dict['HOST'] in ('localhost','127.0.0.1','::1')
    executor = MigrationExecutor(connection)
    assert not executor.migration_plan(executor.loader.graph.leaf_nodes())
    with connection.cursor() as c:
        c.execute('SET default_transaction_read_only = off')

def org(): return Organization.objects.get(slug='demo-construction-01')
def projects(): return {k: Project.objects.get(code=v) for k,v in CODES.items()}
def requirements(): return {k: TrainingRequirement.objects.get(code='SP031-RUNTIME-'+k) for k in 'ABCDXO'}
def employee(): return Employee.objects.filter(organization=org(), archived_at__isnull=True).order_by('pk').first()

def authority():
    result=[]
    for alias in ALIASES:
        user=User.objects.get(username=alias)
        member=get_active_membership(user=user, organization=org())
        result.append(dict(actor=alias, membership=member.pk, staff=user.is_staff, superuser=user.is_superuser,
            roles=list(effective_role_assignments(member).order_by('pk').values()),
            grants=list(effective_scope_grants(member).order_by('pk').values()),
            capability=has_business_permission(user=user,organization=org(),permission=PERMISSION,allow_any_scope=True),
            organization_authority=has_business_permission(user=user,organization=org(),permission=PERMISSION),
            project_authority={k:has_business_permission(user=user,organization=org(),permission=PERMISSION,project=p) for k,p in projects().items()}))
    return result

def state(): return dict(models=snapshot(),rows=row_hashes(),authority=authority())
def small(): return {m._meta.label:digest(list(m.objects.order_by('pk').values())) for m in (TrainingRequirement,EmployeeTrainingRecord,AuditEvent)}

def prepare():
    guard()
    assert not (OUT/'PREPARATION_BEFORE.json').exists(), 'Preparation already recorded'
    assert not TrainingRequirement.objects.exists(), 'Review existing fixtures before preparing'
    assert employee() is not None
    before=state()
    assert all(r['capability'] and not r['staff'] and not r['superuser'] for r in before['authority'])
    save('PREPARATION_BEFORE.json',before)
    tracked=subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines()
    preserve=tracked+[str(p.relative_to(ROOT)) for p in (OUT.parent).rglob('*') if p.is_file() and OUT not in p.parents]
    save('FILES_BEFORE.json',{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in preserve if (ROOT/p).is_file()})
    save('GROUNDING.json',dict(branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        upstream=subprocess.check_output(['git','rev-parse','@{upstream}'],cwd=ROOT,text=True).strip(),
        status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),settings=settings.SETTINGS_MODULE,
        database={k:connection.settings_dict[k] for k in ('ENGINE','NAME','HOST','PORT')},pending_migrations=0,
        touch_set=['sp031_runtime_evidence/','UIUX_SP031_RUNTIME_CONFIRMATION_REPORT.md','UIUX_FINDINGS_REGISTER.yaml (append independent finding/status only)']))
    made=[]
    with transaction.atomic():
        for key in 'ABCDXO':
            p=projects().get(key)
            tenant=p.organization if p else org()
            actor=User.objects.get(username=f'account.{tenant.slug}.owner')
            req=create_training_requirement(organization=tenant,actor=actor,project=p,code='SP031-RUNTIME-'+key,
                name='SP031 synthetic requirement '+key,description='Synthetic Development-only SP031 confirmation')
            made.append(dict(key=key,id=req.pk,code=req.code,name=req.name,project=p.pk if p else None,organization=tenant.pk,actor=actor.username))
    save('FIXTURES.json',dict(created=made,reused_employee_id=employee().pk,authority_mutations=[],temporary_authority='NONE',
        site_note='TrainingRequirement has no site field; existing site-only actor must not inherit Project-only action authority'))
    after=state()
    assert digest(after['authority']) == digest(before['authority'])
    save('RUNTIME_BEFORE.json',after)
    save('BROWSER_INPUT.json',dict(base=BASE,path=PATH,requirements={k:str(v.pk) for k,v in requirements().items()},employee=str(employee().pk),outcome=TrainingOutcome.values[0]))
    print('Preparation: six canonical TrainingRequirements + six preparation audit events; existing Employee/Projects/roles/scopes reused')

def http():
    guard(); results=[]; reqs=requirements()
    for alias in ALIASES:
        request=login(alias)
        def observe(case,data=None,query=None):
            before=small()
            status,body,url=request(PATH+('?' + urlencode(query) if query else ''), data)
            assert status==200, (alias,case,status)
            parsed=Parsed(body)
            assert 'requirement' in parsed.fields
            observed={o['value'] for o in parsed.fields['requirement'] if o['value']}
            assert observed=={str(reqs[k].pk) for k in 'ABCDO'},(alias,case,observed)
            # Navigation may echo the caller-supplied query in `next`; it is not a resolved object disclosure.
            resolved=re.sub(r'<input[^>]*name="next"[^>]*>', '', body)
            resolved=re.sub(r'href="[^"]*[?&](?:amp;)?next=[^"]*"', '', resolved)
            assert str(reqs['X'].pk) not in resolved and reqs['X'].name not in body
            assert small()==before, (alias,case,'business or audit delta')
            if data is not None: assert parsed.errors, (alias,case,'no error')
            clean=re.sub(r'<input[^>]*name="csrfmiddlewaretoken"[^>]*>', '<!-- CSRF omitted -->', body)
            clean=re.sub(r'(<select\b[^>]*name="employee"[^>]*>).*?(</select>)', r'\1<!-- Unrelated Employee choices omitted -->\2', clean, flags=re.S)
            (OUT/f'http_{len(results)+1:02}.html').write_text(clean,encoding='utf-8')
            results.append(dict(actor=alias,case=case,status=status,method='POST' if data is not None else 'GET',
                options=parsed.fields['requirement'],errors=parsed.errors,cross_tenant_absent=True,
                business_and_success_audit_unchanged=True,real_authentication_csrf=True,response_sha256=hashlib.sha256(body.encode()).hexdigest(),
                html=f'http_{len(results)+1:02}.html'))
            save('HTTP.json',results)
            return parsed
        parsed=observe('initial GET')
        # A required-field failure must safely redisplay the same protected choices.
        parsed=observe('invalid required-field redisplay',{'requirement':str(reqs['A'].pk),'outcome':TrainingOutcome.values[0], 'csrfmiddlewaretoken':parsed.token})
        if alias != ALIASES[1]:
            for k in 'CDX':
                parsed=observe('forced GET '+k,query={'requirement':reqs[k].pk})
            for k in ('ACDXO' if alias==ALIASES[2] else 'BCDXO'):
                parsed=observe('manipulated Requirement '+k,dict(employee=str(employee().pk),requirement=str(reqs[k].pk),occurred_on='1405/07/30',outcome=TrainingOutcome.values[0],notes='SP031 synthetic denied control',csrfmiddlewaretoken=parsed.token))
                # Confirm denials reach the service for same-tenant valid forms.
                if k!='X':
                    assert any('اجازه' in e for e in parsed.errors),parsed.errors
    save('HTTP_SUMMARY.json',dict(observations=len(results),selector_same_tenant_scope='FAIL',cross_tenant='PASS',unauthorized_mutations=0))
    print('HTTP:',len(results),'observations; same-tenant protected IDs disclosed; cross-tenant excluded; all manipulated POSTs denied')

def direct():
    guard(); results=[]; before=small()
    for alias in ALIASES:
        actor=User.objects.get(username=alias)
        for key,req in requirements().items():
            try:
                with transaction.atomic():
                    record_employee_training(organization=org(),actor=actor,employee=employee(),requirement=req,occurred_on=date(2026,10,22),outcome=TrainingOutcome.values[0],notes='SP031 rollback-only direct control')
                    transaction.set_rollback(True)
            except PermissionDenied as exc: result='DENIED'; message=str(exc)
            else: result='ALLOWED_ROLLED_BACK'; message=''
            expected='ALLOWED_ROLLED_BACK' if alias==ALIASES[1] and key!='X' else 'DENIED'
            assert result==expected,(alias,key,result)
            assert small()==before
            results.append(dict(actor=alias,key=key,result=result,message=message,persisted_business_or_success_audit=0))
    save('DIRECT_SERVICE.json',results)
    print('Direct services:',len(results),'expected outcomes; no persistent training records/success audit')

def after():
    guard(); before=json.loads((OUT/'RUNTIME_BEFORE.json').read_text()); current=state()
    deltas=[m for m in current['models'] if current['models'][m]!=before['models'][m]]
    assert set(deltas)<={'sessions.Session'},deltas
    changed=[(m,pk) for m,rows in before['rows'].items() if m!='sessions.Session' for pk,h in rows.items() if current['rows'][m].get(pk)!=h]
    assert not changed
    assert digest(before['authority'])==digest(current['authority'])
    prep=json.loads((OUT/'PREPARATION_BEFORE.json').read_text())
    prep_deltas={m:before['models'][m]['count']-prep['models'][m]['count'] for m in before['models'] if before['models'][m]!=prep['models'][m]}
    assert prep_deltas=={'workforce.TrainingRequirement':6,'audit.AuditEvent':6},prep_deltas
    assert all(current['rows'][m].get(pk)==h for m,rows in prep['rows'].items() if m!='sessions.Session' for pk,h in rows.items())
    save('RUNTIME_AFTER.json',current['models'])
    save('INTEGRITY.json',dict(tables=len(current['models']),preparation_deltas=prep_deltas,runtime_deltas=deltas,
        preexisting_rows_changed=changed,authority_before=digest(before['authority']),authority_after=digest(current['authority']),
        unauthorized_training_records=0,runtime_success_audit_delta=0,training_requirements=TrainingRequirement.objects.count(),
        last_login_excluded=True,temporary_authority='NONE'))
    print('Integrity:',len(current['models']),'tables; preparation exactly 6 requirements + 6 audits; runtime sessions only; authority unchanged')

if __name__=='__main__':
    {'prepare':prepare,'http':http,'direct':direct,'after':after}[sys.argv[1]]()
