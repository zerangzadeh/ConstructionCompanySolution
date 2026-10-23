"""Independent F128 real HTTP matrix and full Development integrity evidence."""

import os
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()

import hashlib
import json
import re
import runpy
from datetime import date
from urllib.parse import urlencode

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.workforce.models import Employee, EmployeeTrainingRecord
from apps.workforce.services import record_employee_training

support = runpy.run_path(str(OUT.parent / "sp031_runtime_evidence/runtime.py"), run_name="f128_support")
guard, state, digest, Parsed, requirements, org, small = (
    support[n] for n in ("guard", "state", "digest", "Parsed", "requirements", "org", "small")
)
login = support["login"]
BASE = "http://localhost:8014"
login.__globals__["BASE"] = BASE
PATH = "/workforce/foundation/training-records/create/"
ALIASES = support["ALIASES"]
MARKER = "SP031-F128-CLOSURE"
ALLOWED = ("ABO", "ABCDO", "O")


def save(name, data):
    (OUT / name).write_text(json.dumps(data, default=str, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def employee():
    return Employee.objects.get(organization=org(), employee_number="EMP-001", archived_at__isnull=True)


def prepare():
    guard()
    assert not (OUT / "RUNTIME_BEFORE.json").exists()
    reqs = requirements()
    assert all(r.is_active and r.archived_at is None for r in reqs.values())
    assert not EmployeeTrainingRecord.objects.filter(notes__startswith=MARKER).exists()
    baseline = state()
    assert all(a["capability"] and not a["staff"] and not a["superuser"] for a in baseline["authority"])
    save("RUNTIME_BEFORE.json", baseline)
    save("FIXTURES.json", dict(created=[], authority_mutations=[], temporary_authority="NONE", reused_requirements={k:str(r.pk) for k,r in reqs.items()}, reused_synthetic_employee=str(employee().pk), actors=ALIASES))
    save("BROWSER_INPUT.json", dict(base=BASE, path=PATH, requirements={k:str(v.pk) for k,v in reqs.items()}, employee=str(employee().pk), notes=MARKER+" BROWSER authorized A", allowed=dict(zip(ALIASES,ALLOWED,strict=True))))
    print("Preparation PASS: existing six canonical requirements, synthetic Employee, three personas; zero fixture or authority writes")


def payload(key):
    return dict(employee=str(employee().pk), requirement=str(requirements()[key].pk) if key!="M" else "invalid-uuid", occurred_on="1405/07/30", outcome="attended", notes=MARKER+" denied control")


def http():
    guard()
    results=[]
    reqs=requirements()
    for alias, allowed in zip(ALIASES,ALLOWED,strict=True):
        request=login(alias)

        def observe(case,data=None,query=None,positive=None):
            before=small()
            ids=set(EmployeeTrainingRecord.objects.values_list("pk",flat=True))
            audit_ids=set(AuditEvent.objects.values_list("pk",flat=True))
            status,body,url=request(PATH+("?"+urlencode(query) if query else ""), data)
            assert status==200,(alias,case,status)
            parsed=Parsed(body)
            response=dict(actor=alias,case=case,method="POST" if data is not None else "GET",status=status,url=url,response_sha256=hashlib.sha256(body.encode()).hexdigest(),real_login_csrf=True)
            if positive:
                added=set(EmployeeTrainingRecord.objects.values_list("pk",flat=True))-ids
                added_audits=set(AuditEvent.objects.values_list("pk",flat=True))-audit_ids
                assert len(added)==len(added_audits)==1
                record=EmployeeTrainingRecord.objects.get(pk=added.pop())
                audit=AuditEvent.objects.get(pk=added_audits.pop())
                assert record.recorded_by.username==alias and record.requirement_id==reqs[positive].pk and record.employee_id==employee().pk
                assert audit.action==AuditAction.EMPLOYEE_TRAINING_RECORDED and audit.entity_id==str(record.pk)
                assert "/workforce/" in url and str(employee().pk) in url and "/create/" not in url
                response.update(authorized_success=True,record_id=str(record.pk),audit_id=str(audit.pk),requirement=positive,exactly_one_record_and_audit=True)
            else:
                expected={str(reqs[k].pk) for k in allowed}
                assert {o['value'] for o in parsed.fields['requirement'] if o['value']}==expected,(alias,case,parsed.fields)
                resolved=re.sub(r'<input[^>]*name="next"[^>]*>',"",body)
                resolved=re.sub(r'href="[^"]*[?&](?:amp;)?next=[^"]*"',"",resolved)
                leaks=[]
                for k,r in reqs.items():
                    if k not in allowed:
                        leaks += [v for v in (str(r.pk),r.name,r.code) if v in resolved]
                assert not leaks,(alias,case,leaks)
                assert small()==before,(alias,case,"unauthorized mutation")
                if data is not None:
                    assert parsed.errors,(alias,case,"missing error")
                response.update(options=parsed.fields['requirement'],errors=parsed.errors,protected_metadata=[],business_and_success_audit_unchanged=True)
                clean=re.sub(r'<input[^>]*name="csrfmiddlewaretoken"[^>]*>',"<!-- CSRF omitted -->",body)
                clean=re.sub(r'(<select\b[^>]*name="employee"[^>]*>).*?(</select>)',r'\1<!-- unrelated Employee labels omitted -->\2',clean,flags=re.S)
                filename=f"http_{len(results)+1:02}.html"
                (OUT/filename).write_text(clean,encoding="utf-8")
                response['html']=filename
            results.append(response)
            save("HTTP.json",results)
            return parsed

        parsed=observe("initial GET")
        for field in ("employee","requirement","occurred_on","outcome"):
            data=payload("A" if alias==ALIASES[1] else "O" if alias==ALIASES[2] else "B")
            data.pop(field)
            parsed=observe("missing "+field,data|{'csrfmiddlewaretoken':parsed.token})
        for key in ("CDX" if alias==ALIASES[0] else "X" if alias==ALIASES[1] else "ACDX"):
            parsed=observe("forced query "+key,query={'requirement':reqs[key].pk})
        for key in ("CDXMBO" if alias==ALIASES[0] else "XM" if alias==ALIASES[1] else "ABCDXMO"):
            parsed=observe("manipulated Requirement "+key,payload(key)|{'csrfmiddlewaretoken':parsed.token})
        if alias==ALIASES[1]:
            for key in "BO":
                data=payload(key)|{'notes':MARKER+" HTTP authorized "+key,'csrfmiddlewaretoken':parsed.token}
                observe("authorized valid "+key,data,positive=key)
    assert len(results)==40
    save("HTTP_SUMMARY.json",dict(all_pass=True,observations=len(results),authorized_successes=2,unauthorized_writes=0,protected_metadata_leaks=0))
    print("HTTP PASS: 40 independent observations; two authorized successes; no protected metadata or unauthorized mutations")


def direct():
    guard(); before=small(); results=[]
    for alias in ALIASES:
        actor=User.objects.get(username=alias)
        for key,req in requirements().items():
            try:
                with transaction.atomic():
                    record_employee_training(organization=org(),actor=actor,employee=employee(),requirement=req,occurred_on=date(2026,10,22),outcome="attended",notes=MARKER+" rollback-only direct")
                    transaction.set_rollback(True)
            except PermissionDenied: result="DENIED"
            else: result="ALLOWED_ROLLED_BACK"
            assert result==("ALLOWED_ROLLED_BACK" if alias==ALIASES[1] and key!="X" else "DENIED")
            assert small()==before
            results.append(dict(actor=alias,requirement=key,result=result,persisted_delta=0))
    save("DIRECT_SERVICE.json",results)
    print("Direct PASS: 18 expected outcomes; baseline domain authority retained; positive controls rolled back")


def after():
    guard(); before=json.loads((OUT/'RUNTIME_BEFORE.json').read_text()); current=state()
    deltas={m:current['models'][m]['count']-before['models'][m]['count'] for m in current['models'] if current['models'][m]!=before['models'][m]}
    assert set(deltas)<={'workforce.EmployeeTrainingRecord','audit.AuditEvent','sessions.Session'},deltas
    assert deltas['workforce.EmployeeTrainingRecord']==deltas['audit.AuditEvent']==3,deltas
    changed=[(m,pk) for m,rows in before['rows'].items() if m!='sessions.Session' for pk,h in rows.items() if current['rows'][m].get(pk)!=h]
    assert not changed,changed
    assert digest(before['authority'])==digest(current['authority'])
    records=list(EmployeeTrainingRecord.objects.filter(notes__startswith=MARKER).order_by('notes').values())
    assert len(records)==3 and all(r['recorded_by_id']==User.objects.get(username=ALIASES[1]).pk for r in records)
    assert {r['notes'] for r in records}=={MARKER+' HTTP authorized B',MARKER+' HTTP authorized O',MARKER+' BROWSER authorized A'}
    added_audits=set(current['rows']['audit.AuditEvent'])-set(before['rows']['audit.AuditEvent'])
    audit_rows=list(AuditEvent.objects.filter(pk__in=added_audits).values('id','action','entity_type','entity_id','actor_id','organization_id'))
    assert all(a['action']==AuditAction.EMPLOYEE_TRAINING_RECORDED and a['actor_id']==User.objects.get(username=ALIASES[1]).pk for a in audit_rows)
    assert {a['entity_id'] for a in audit_rows}=={str(r['id']) for r in records}
    save('RUNTIME_AFTER.json',current['models'])
    save('INTEGRITY.json',dict(tables=len(current['models']),runtime_deltas=deltas,authorized_training_records=records,authorized_success_audits=audit_rows,unauthorized_training_records=0,unauthorized_success_audits=0,preexisting_rows_changed=changed,authority_before=digest(before['authority']),authority_after=digest(current['authority']),temporary_authority='NONE',fixture_preparation_writes=0,last_login_excluded=True))
    print('Integrity PASS:',len(current['models']),'tables; exactly three authorized records/audits + sessions; preexisting data and authority unchanged')


if __name__=='__main__':
    {'prepare':prepare,'http':http,'direct':direct,'after':after}[sys.argv[1]]()
