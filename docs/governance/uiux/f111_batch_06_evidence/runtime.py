"""BATCH-06 canonical Development fixtures and real authenticated HTTP controls."""
import json
import runpy
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
support = runpy.run_path(str(OUT.parent / "f111_batch_05_evidence/runtime.py"), run_name="b06_support")
snapshot, row_hashes, digest = (support[n] for n in ("snapshot", "row_hashes", "digest"))
Parsed = support["Parsed"]
support["login"].__globals__["BASE"] = "http://localhost:8009"
login = support["login"]
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.expenses.forms import ExpenseAllocationForm
from apps.expenses.models import Expense, ExpenseAllocation
from apps.expenses.services import add_expense_allocation, create_expense_draft
from apps.organizations.authorization import get_active_membership, has_business_permission
from apps.organizations.models import Organization
from apps.projects.models import Project, WBSNode, Activity, CBSNode, CostCenter, ProjectBudgetControl

BASE = "http://localhost:8009"
ALIASES = support["ALIASES"]
CODES = support["CODES"]
FIELDS = ("project", "wbs_node", "activity")

def save(name, value):
    (OUT/name).write_text(json.dumps(value,default=str,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def guard():
    assert settings.SETTINGS_MODULE == "config.settings.development" and settings.DEBUG
    assert connection.vendor == "postgresql" and connection.settings_dict["NAME"] == "construction_erp"
    assert connection.settings_dict["HOST"] in {"localhost","127.0.0.1","::1"}
    with connection.cursor() as cursor: cursor.execute("SET default_transaction_read_only = off")
    executor=MigrationExecutor(connection)
    assert not executor.migration_plan(executor.loader.graph.leaf_nodes())

def authority():
    rows=support["support"]["authority"]()
    for row in rows:
        org=Organization.objects.get(slug=row["organization"])
        u=User.objects.get(username=row["actor"])
        row["expenses_view"]=has_business_permission(user=u,organization=org,permission="expenses.view",allow_any_scope=True)
        row["expenses_allocate"]=has_business_permission(user=u,organization=org,permission="expenses.allocate",allow_any_scope=True)
    return rows

def sources():
    return {key:{
        "project":Project.objects.get(code=code),
        "wbs_node":WBSNode.objects.get(code=f"B06-W-{key}",project__code=code),
        "activity":Activity.objects.get(code=f"B06-A-{key}",project__code=code),
        "cbs_node":CBSNode.objects.get(structure_version__code=f"B06-S-{key}",code="C1"),
        "cost_center":CostCenter.objects.get(structure_version__code=f"B06-S-{key}",code="CC1"),
    } for key,code in CODES.items()}

def parent():
    return Expense.objects.get(source_reference="B06-RUNTIME-PARENT")

def path():
    return f"/expenses/{parent().pk}/"

def prepare():
    guard()
    initial={"models":snapshot(),"rows":row_hashes(),"authority":authority()}
    save("PREPARATION_BEFORE.json",initial)
    org=Organization.objects.get(slug="demo-construction-01")
    save("PREFLIGHT.json",{
        "authority":initial["authority"],"expenses":list(Expense.objects.filter(project__code__in=list(CODES.values())).values("id","project__code","status","source_reference")),
        "governing_budgets":list(ProjectBudgetControl.objects.values("project__code","governing_budget__status")),
        "wbs":WBSNode.objects.count(),"activities":Activity.objects.count(),
        "missing":"Accepted governing budgets and dedicated synthetic parent; existing roles/scopes reused unchanged",
    })
    assert all(r["expenses_view"] and r["expenses_allocate"] and not r["staff"] and not r["superuser"] for r in initial["authority"])
    assert not WBSNode.objects.filter(code__startswith="B06-W-").exists()
    helper=runpy.run_path(str(ROOT/"tests/test_uiux_f111_pattern_allocation_scope.py"))["canonical_coding"]
    fixtures=[]
    with transaction.atomic():
        for key,code in CODES.items():
            project=Project.objects.select_related("organization").get(code=code)
            tenant=project.organization
            actor=User.objects.get(username=f"account.{tenant.slug}.owner")
            approver=User.objects.get(username=ALIASES[1] if tenant==org else "admin")
            assert actor!=approver and has_business_permission(user=approver,organization=tenant,permission="budgets.accept",project=project)
            row=helper(organization=tenant,project=project,actor=actor,approver=approver,key=key)
            fixtures.append({"key":key,"actor":actor.username,"approver":approver.username,"ids":{f:v.pk for f,v in row.items()},"labels":{f:str(v) for f,v in row.items()}})
        owner=User.objects.get(username=f"account.{org.slug}.owner")
        expense=create_expense_draft(organization=org,project=Project.objects.get(code=CODES["A"]),actor=owner,
            description="B06 synthetic allocation selector parent",amount=Decimal(60),incurred_on=date(2026,10,22),
            source_reference="B06-RUNTIME-PARENT",idempotency_key="B06-RUNTIME-PARENT")
    assert initial["authority"]==authority()
    save("FIXTURES.json",{"coding":fixtures,"parent":expense.pk,"temporary_authority":"NONE","authority_unchanged":True,
        "canonical_workflows":"WBS/Activity; cost structure/CBS/cost center/lock; estimate/item/approve; budget draft/classify/submit/independent accept; expense draft",
        "retention":"Synthetic Development fixtures retained with canonical audit history; no approval/posting of Expenses"})
    save("RUNTIME_BEFORE.json",{"models":snapshot(),"rows":row_hashes(),"authority":authority(),"database":connection.settings_dict["NAME"],"settings":settings.SETTINGS_MODULE,"pending_migrations":0})
    save("BROWSER_PAYLOAD.json",{"url":BASE+path(),"sources":{k:{f:str(v.pk) for f,v in r.items()} for k,r in sources().items()},"payload":payload()})
    print("Canonical preparation PASS; five coding contexts, one draft; no authority changes")

def payload(key="B"):
    return {f:str(v.pk) for f,v in sources()[key].items()}|{"amount":"10.00","allocation_basis_reference":"B06 runtime synthetic split"}

def small_snapshot():
    return {label:digest(list(model.objects.order_by("pk").values())) for label,model in (("expenses.Expense",Expense),("expenses.ExpenseAllocation",ExpenseAllocation),("audit.AuditEvent",AuditEvent))}

def http():
    guard();records=[];src=sources();org=parent().organization
    for alias,allowed in zip(ALIASES,("AB","ABCD",""),strict=True):
        request=login(alias);actor=User.objects.get(username=alias);m=get_active_membership(user=actor,organization=org)
        status,body,url=request(path());parsed=Parsed(body)
        expected_form=ExpenseAllocationForm(organization=org,membership=m)
        expected={f:[{"value":str(v),"label":str(l)} for v,l in expected_form.fields[f].choices] for f in FIELDS}
        if not allowed:
            assert status==404 and all(not expected_form.fields[f].queryset.exists() for f in FIELDS)
            assert all(str(r[f].pk) not in body for r in src.values() for f in ("wbs_node","activity"))
            records.append({"actor":alias,"case":"site-only parent read denied","status":status,"selector_querysets_empty":True,"scope_promotion":False})
            # Parent is project-owned; no grant allows this actor to reach the allocation form.
            for key in "ABCDX":
                # Obtain real CSRF from another accessible authenticated page.
                _,safe,_=request("/accounts/settings/");token=Parsed(safe).token
                before=small_snapshot();s,b,_=request(path()+"allocate/",payload(key)|{"csrfmiddlewaretoken":token})
                assert s==404 and small_snapshot()==before
                records.append({"actor":alias,"case":"site-only forced "+key,"status":s,"business_and_audit_unchanged":True})
            continue
        actual={f:parsed.fields[f] for f in FIELDS}
        assert status==200 and actual==expected,(status,actual,expected)
        def no_leaks(body):
            forbidden=[]
            # Shared project labels and legitimate site navigation can coincide in demo tenants.
            for key,r in src.items():
                if key in allowed:continue
                tokens=[str(r[f].pk) for f in FIELDS]+[str(r[f]) for f in ("wbs_node","activity")]
                if r["project"].name not in {src[k]["project"].name for k in allowed}:
                    tokens.append(r["project"].name)
                forbidden += [t for t in tokens if t in body]
            assert not forbidden,forbidden
            return forbidden
        no_leaks(body)
        for key,r in src.items():
            for f in FIELDS:
                assert (str(r[f].pk) in {o["value"] for o in actual[f]})==(key in allowed)
        records.append({"actor":alias,"case":"detail GET","status":status,"options":actual,"forbidden_metadata":[]})
        if allowed=="ABCD":continue
        cases=[]
        for key in "CDX":
            for f in FIELDS:
                cases.append((f"forced {key} {f}",payload(key) if f=="project" else payload()|{f:str(src[key][f].pk)},f))
        for f in ("wbs_node","activity"):
            cases.append((f"mixed authorized A {f}",payload()|{f:str(src["A"][f].pk)},f))
        for f in ("project","wbs_node","amount","allocation_basis_reference"):
            data=payload();data.pop(f);cases.append((f"missing {f}",data,f))
        cases += [("amount exceeds parent",payload()|{"amount":"61"},None),("wrong locked CBS structure",payload()|{"cbs_node":str(src["A"]["cbs_node"].pk)},"cbs_node")]
        for label,data,error in cases:
            form=ExpenseAllocationForm(data,organization=org,membership=m,expense=parent())
            valid=form.is_valid()
            if error:assert not valid and error in form.errors,(label,form.errors)
            else:assert valid,form.errors
            before=small_snapshot();s,b,_=request(path()+"allocate/",data|{"csrfmiddlewaretoken":parsed.token})
            assert s==400 and b=="" and small_snapshot()==before,(label,s)
            s,body,_=request(path());parsed=Parsed(body)
            assert s==200 and {f:parsed.fields[f] for f in FIELDS}==expected
            no_leaks(body)
            records.append({"actor":alias,"case":label,"status":400,"bare_response":True,"refreshed_get":200,"options":expected,"forbidden_metadata":[],"business_and_audit_unchanged":True,"real_authenticated_csrf":True})
        save("RUNTIME_HTTP.json",records)
    save("RUNTIME_HTTP.json",records)
    save("HTTP_SUMMARY.json",{"observations":len(records),"all_pass":True,"unauthorized_mutations":0,"same_tenant_cross_tenant_site_only":True})
    print("Live HTTP PASS:",len(records),"observations; bare 400 and refreshed GET")

def direct():
    guard();before=small_snapshot();records=[]
    for alias,keys in ((ALIASES[0],"CDX"),(ALIASES[2],"ABCDX")):
        for key in keys:
            denied=False
            try:add_expense_allocation(expense=parent(),actor=User.objects.get(username=alias),**sources()[key],amount=Decimal(10),allocation_basis_reference="B06 direct denial")
            except PermissionDenied:denied=True
            assert denied and small_snapshot()==before
            records.append({"actor":alias,"source":key,"denied":True,"mutations":0})
    save("DIRECT_SERVICE.json",records);print("Existing service denials PASS:",len(records))

def positive():
    guard();request=login(ALIASES[0]);_,body,_=request(path())
    before=ExpenseAllocation.objects.count();s,b,url=request(path()+"allocate/",payload()|{"csrfmiddlewaretoken":Parsed(body).token})
    assert s==200 and url==BASE+path() and ExpenseAllocation.objects.count()==before+1
    row=ExpenseAllocation.objects.get(expense=parent())
    assert row.project_id==sources()["B"]["project"].pk and row.expense.project_id!=row.project_id
    assert AuditEvent.objects.filter(action=AuditAction.EXPENSE_ALLOCATION_ADDED,entity_id=row.expense_id).count()==1
    save("RUNTIME_POSITIVE.json",{"allocation":row.pk,"parent":row.expense_id,"allocation_project":row.project_id,"parent_project":row.expense.project_id,"status":row.expense.status,"amount":row.amount,"real_authenticated_csrf":True,"approved_or_posted":False})
    print("Authorized real-CSRF A parent / B allocation PASS; draft only")

def after():
    guard();prep=json.loads((OUT/"PREPARATION_BEFORE.json").read_text());initial=json.loads((OUT/"RUNTIME_BEFORE.json").read_text());rows=row_hashes();current=snapshot()
    changed=[(m,pk) for m,rs in prep["rows"].items() if m!="sessions.Session" for pk,h in rs.items() if rows[m].get(pk)!=h]
    assert not changed,changed
    assert digest(authority())==digest(initial["authority"])
    deltas=[m for m,v in current.items() if v!=initial["models"][m]]
    assert set(deltas)<={"sessions.Session","audit.AuditEvent","expenses.ExpenseAllocation"},deltas
    positive=json.loads((OUT/"RUNTIME_POSITIVE.json").read_text())
    added=set(rows["expenses.ExpenseAllocation"])-set(initial["rows"]["expenses.ExpenseAllocation"])
    assert added=={positive["allocation"]}
    audits=set(rows["audit.AuditEvent"])-set(initial["rows"]["audit.AuditEvent"])
    assert len(audits)==1 and AuditEvent.objects.get(pk=next(iter(audits))).action==AuditAction.EXPENSE_ALLOCATION_ADDED
    save("RUNTIME_AFTER.json",current)
    save("RUNTIME_INTEGRITY.json",{"tables":len(current),"preexisting_rows_changed":changed,"runtime_deltas":deltas,
        "authorized_allocation":positive,"runtime_success_audits":1,"unauthorized_mutations":0,"authority_unchanged":True,
        "authority_fingerprint_before":digest(initial["authority"]),"authority_fingerprint_after":digest(authority()),
        "temporary_authority":"NONE; no cleanup needed","last_login_excluded":True,
        "preparation_additions":{m:len(set(rs)-set(prep["rows"][m])) for m,rs in initial["rows"].items() if set(rs)-set(prep["rows"][m])},
        "preparation_audits":len(set(initial["rows"]["audit.AuditEvent"])-set(prep["rows"]["audit.AuditEvent"]))})
    print("Runtime integrity PASS:",len(current),"tables; preexisting business rows and authority preserved")

if __name__=="__main__":
    {"prepare":prepare,"http":http,"direct":direct,"positive":positive,"after":after}[sys.argv[1]]()
