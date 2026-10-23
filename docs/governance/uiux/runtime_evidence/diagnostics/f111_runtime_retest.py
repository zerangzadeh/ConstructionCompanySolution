"""Bounded Development HTTP verification; no ORM mutation or persisted secrets."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django
django.setup()
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
from apps.accounts.models import User
from apps.organizations.models import Organization
from apps.organizations.authorization import (
    get_active_membership, effective_scope_grants, effective_role_assignments,
    has_business_permission, membership_has_scope,
)
from apps.projects.models import Project, ProjectSite, ProjectPhase
from apps.procurement.models import PurchaseRequest

OUT = Path(__file__).parent
ALIAS = "uiux.persona.project-manager"
BASE = "http://127.0.0.1:8002"
assert settings.SETTINGS_MODULE == "config.settings.development"
assert connection.vendor == "postgresql"
assert settings.DATABASES["default"]["HOST"] in ("localhost", "127.0.0.1", "::1")

def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

def digest(data):
    return hashlib.sha256(json.dumps(data, default=str, sort_keys=True).encode()).hexdigest()

def snapshot():
    result = {}
    with connection.cursor() as cur:
        cur.execute("SET default_transaction_read_only = on")
    for model in apps.get_models():
        fields = [f.attname for f in model._meta.concrete_fields]
        if model._meta.label == "accounts.User":
            fields.remove("last_login")
        rows = list(model._base_manager.order_by("pk").values_list(*fields))
        result[model._meta.label] = {"count": len(rows), "sha256": digest(rows)}
    return result

def ground():
    user = User.objects.get(username=ALIAS)
    org = Organization.objects.get(slug="demo-construction-01")
    member = get_active_membership(user=user, organization=org)
    projects = {k: Project.objects.get(code=c) for k,c in zip("ABCDX", ["PRJ-01-01","PRJ-01-02","PRJ-01-03","PRJ-01-04","PRJ-02-01"])}
    perms = ["daily_reports.create", "equipment_assignments.create", "purchase_orders.create", "project_assignments.create", "expenses.create", "estimates.create"]
    grants = list(effective_scope_grants(member).values("id","scope_type","project_id","site_id","starts_at","ends_at"))
    authority = {"alias": ALIAS, "is_staff": user.is_staff, "is_superuser": user.is_superuser, "active": user.is_active,
      "organization": org.slug, "membership_id": str(member.pk), "membership_status": member.status,
      "roles": list(effective_role_assignments(member).values_list("role__code", flat=True)), "grants": grants,
      "permissions": {p:has_business_permission(user=user, organization=org, permission=p, allow_any_scope=True) for p in perms},
      "project_scope": {k:membership_has_scope(member, project=p) for k,p in projects.items()}}
    assert not user.is_staff and not user.is_superuser
    assert authority["project_scope"] == {"A":True,"B":True,"C":False,"D":False,"X":False}
    assert all(authority["permissions"].values()), authority["permissions"]
    objects = {}
    for k,p in projects.items():
        objects[k] = {"project": {"id":str(p.pk),"code":p.code,"name":p.name},
          "sites":list(ProjectSite.objects.filter(project=p).values("id","code","name")),
          "phases":list(ProjectPhase.objects.filter(site__project=p).values("id","code","name")),
          "requests":list(PurchaseRequest.objects.filter(project=p, status="approved").values("id","request_number","title"))}
    return authority, objects

if __name__ == "__main__" and sys.argv[1] == "before":
    authority, objects = ground()
    state = snapshot()
    executor = MigrationExecutor(connection)
    save("F111_RETEST_BEFORE.json", {"at":timezone.now(), "authority":authority,"objects":objects,"models":state,
      "settings":settings.SETTINGS_MODULE,"database":connection.settings_dict["NAME"],"engine":connection.vendor,
      "pending_migrations":len(executor.migration_plan(executor.loader.graph.leaf_nodes())),
      "product_files":{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for app in ("daily_reports","equipment","procurement","workforce") for p in (ROOT/"apps"/app/"forms.py", ROOT/"apps"/app/"views.py")},
      "historical_evidence":{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ("records","screenshots","diagnostics") for p in (ROOT/"docs/governance/uiux/runtime_evidence"/folder).iterdir() if p.is_file() and not p.name.startswith(("F111_","f111_"))}})
    print(json.dumps({"authority":authority,"models":len(state),"pending_migrations":len(executor.migration_plan(executor.loader.graph.leaf_nodes()))},default=str))

if __name__ == "__main__" and sys.argv[1] == "http":
    from html.parser import HTMLParser
    from http.cookiejar import CookieJar
    from urllib.request import build_opener, HTTPCookieProcessor, Request
    from urllib.error import HTTPError
    from urllib.parse import urlencode
    from apps.equipment.models import Equipment
    from apps.parties.models import BusinessParty, PartyRoleType
    from apps.workforce.models import Employee
    from apps.daily_reports.forms import DailyReportForm
    from apps.equipment.forms import EquipmentAssignmentForm
    from apps.procurement.forms import PurchaseOrderForm
    from apps.workforce.forms import EmployeeAssignmentForm

    class Parsed(HTMLParser):
        def __init__(self, body):
            super().__init__(convert_charrefs=True)
            self.fields = {}; self.current = None; self.option = None; self.token = None
            self.errors = []; self.error_depth = 0
            self.feed(body)
        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag == "input" and a.get("name") == "csrfmiddlewaretoken": self.token = a.get("value")
            if tag == "select":
                self.current = a.get("name"); self.fields[self.current] = []
            if tag == "option" and self.current:
                self.option = {"value": a.get("value", ""), "label": ""}
                self.fields[self.current].append(self.option)
            if (tag == "ul" and "errorlist" in a.get("class", "")) or (tag == "p" and "erp-field-error" in a.get("class", "")): self.error_depth += 1
        def handle_endtag(self, tag):
            if tag == "select": self.current = None
            if tag == "option": self.option = None
            if tag in ("ul", "p") and self.error_depth: self.error_depth -= 1
        def handle_data(self, data):
            if self.option is not None: self.option["label"] += data
            if self.error_depth and data.strip(): self.errors.append(data.strip())

    authority, objects = ground()
    records = []; opener = build_opener(HTTPCookieProcessor(CookieJar()))
    def request(path, data=None):
        req = Request(BASE + path, data=None if data is None else urlencode(data).encode(), headers={"Referer": BASE + path})
        try: response = opener.open(req, timeout=30)
        except HTTPError as exc: response = exc
        body = response.read().decode("utf-8")
        return response.status, body, response.geturl()
    def tokens(k):
        obj=objects[k]
        return [obj["project"]["id"],obj["project"]["code"]] + ([obj["project"]["name"]] if k in "CD" else []) + [str(r["id"]) for t in ("sites","phases","requests") for r in obj[t]] + [r["request_number"] for r in obj["requests"]]
    forbidden = {k:tokens(k) for k in "CDX"}
    def observe(label, path, data=None, allow_echo=None, expected=200):
        status, body, url = request(path, data)
        parsed=Parsed(body)
        matches={k:[t for t in ts if t in body and t != allow_echo] for k,ts in forbidden.items()}
        item={"label":label,"method":"GET" if data is None else "POST","path":path,"status":status,"url":url,"fields":parsed.fields,"errors":parsed.errors,"unauthorized_matches":matches,"response_sha256":hashlib.sha256(body.encode()).hexdigest()}
        records.append(item); save("F111_RETEST_HTTP.json",records)
        if any(matches.values()): raise RuntimeError("CRITICAL_SECURITY_REGRESSION" if matches["X"] else "REMEDIATION_FAILED")
        assert status == expected, (label,status)
        return parsed,body,item
    # Existing DPAPI credential passes only through process memory and HTTP login.
    _,body,_ = request("/accounts/login/")
    cmd = "$c=Import-Clixml -LiteralPath ($env:LOCALAPPDATA+'/BONIRA/UIUXRuntimeAudit/credentials/uiux.persona.project-manager.clixml'); $c.GetNetworkCredential().Password"
    secret = subprocess.run([r"C:\Users\azera\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe","-NoProfile","-Command",cmd],capture_output=True,text=True,check=True).stdout.strip()
    status,body,url = request("/accounts/login/",{"username":ALIAS,"password":secret,"csrfmiddlewaretoken":Parsed(body).token})
    del secret
    assert status == 200 and "/accounts/login/" not in url
    assert ALIAS in body
    paths={"daily":"/daily-reports/create/","equipment":"/equipment/assignments/create/","order":"/procurement/orders/create/","workforce":"/workforce/assignments/create/"}
    forms={"daily":DailyReportForm,"equipment":EquipmentAssignmentForm,"order":PurchaseOrderForm,"workforce":EmployeeAssignmentForm}
    org=Organization.objects.get(slug="demo-construction-01"); user=User.objects.get(username=ALIAS)
    member=get_active_membership(user=user,organization=org)
    equip=Equipment.objects.filter(organization=org, archived_at__isnull=True).first()
    supplier=BusinessParty.objects.filter(organization=org,roles__role=PartyRoleType.SUPPLIER,roles__is_active=True).first()
    employee=Employee.objects.filter(organization=org,archived_at__isnull=True,status="active").first()
    def payload(surface,key,child=None):
        o=objects[key]; child=objects[child or key]; today=timezone.localdate().isoformat()
        data={"project":o["project"]["id"]}
        if surface == "daily": return data|{"site":str(child["sites"][0]["id"]),"phase":str(child["phases"][0]["id"]),"reporting_date":today,"labor_count":"1","work_performed":"F111 bounded runtime negative control"}
        if surface == "equipment": return data|{"site":str(child["sites"][0]["id"]),"equipment":str(equip.pk),"start_date":today}
        if surface == "order": return data|{"purchase_request":str(child["requests"][0]["id"]),"supplier":str(supplier.pk),"order_number":"F111-RUNTIME-REJECT-20261022","order_date":today}
        return data|{"site":str(child["sites"][0]["id"]),"employee":str(employee.pk),"start_date":today}
    protected_models=["daily_reports.DailyReport","equipment.EquipmentAssignment","equipment.Equipment","procurement.PurchaseOrder","procurement.PurchaseRequest","workforce.EmployeeProjectAssignment","audit.AuditEvent"]
    def business_state():
        return {label:{"count":apps.get_model(label).objects.count(),"sha256":digest(list(apps.get_model(label).objects.order_by("pk").values()))} for label in protected_models}
    for surface,path in paths.items():
        parsed,_,item=observe(surface+" initial",path)
        assert {o["value"] for o in parsed.fields["project"] if o["value"]} == {objects[k]["project"]["id"] for k in "AB"}
        valid=forms[surface](data=payload(surface,"A"),organization=org,membership=member)
        assert valid.is_valid(), (surface,valid.errors.as_json())
        item["otherwise_valid_authorized_payload_checked_without_save"]=True
        for key in "CDX":
            data=payload(surface,key)|{"csrfmiddlewaretoken":parsed.token}
            pre=business_state(); parsed,_,item=observe(surface+" reject "+key,path,data)
            post=business_state(); item["submitted_protected_ids"]={k:v for k,v in data.items() if k in ("project","site","phase","purchase_request")}
            item["business_state_before"]=pre; item["business_state_after"]=post
            item["business_unchanged"]=pre==post
            save("F111_RETEST_HTTP.json",records)
            assert parsed.errors and pre==post
            print(surface,key,"HTTP",item["status"],"invalid/safe/no mutation")
        if surface in ("daily","equipment","order"):
            pre=business_state(); parsed,_,item=observe(surface+" mixed A with C child",path,payload(surface,"A","C")|{"csrfmiddlewaretoken":parsed.token})
            item["business_unchanged"]=pre==business_state(); assert parsed.errors and item["business_unchanged"]
    for key in "ABCDX":
        p=objects[key]["project"]["id"]
        parsed,body,item=observe("workforce sites "+key,"/workforce/assignments/sites/?"+urlencode({"project":p}))
        item["safe_response_body"]=body
        assert all(str(s["id"]) in body for s in objects[key]["sites"]) if key in "AB" else not any(str(s["id"]) in body for s in objects[key]["sites"])
        for source,field in (("expenses","phase"),("estimates","phase"),("estimates","contract")):
            parsed,body,item=observe(source+" context "+field+" "+key,"/organizations/context/form-options/?"+urlencode({"project":p,"source":source,"field":field}))
            item["safe_response_body"]=body
            if key in "CDX": assert json.loads(body)=={"options":[]}
        parsed,_,item=observe("direct "+key,"/projects/"+p+"/",allow_echo=p if key in "CDX" else None,expected=403 if key in "CDX" else 200)
    for term in ("PRJ-01","PRJ-02"):
        _,body,item=observe("global search "+term,"/search/?"+urlencode({"q":term}))
        if term=="PRJ-01": assert all(objects[k]["project"]["id"] in body for k in "AB")
    for surface,path in (("expense","/expenses/create/"),("estimate","/estimates/create/")):
        parsed,_,item=observe(surface+" known-good",path)
        assert {o["value"] for o in parsed.fields["project"] if o["value"]}=={objects[k]["project"]["id"] for k in "AB"}
    save("F111_RETEST_HTTP.json",records)
    print("HTTP observations:",len(records),"PASS")

if __name__ == "__main__" and sys.argv[1] == "after":
    authority,objects=ground(); models=snapshot()
    before=json.loads((OUT/"F111_RETEST_BEFORE.json").read_text(encoding="utf-8"))
    deltas={k:{"before":v,"after":models[k]} for k,v in before["models"].items() if v!=models[k]}
    file_changes=[p for p,h in before["product_files"].items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
    historical_changes=[p for p,h in before["historical_evidence"].items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
    normalized=json.loads(json.dumps(authority,default=str))
    save("F111_RETEST_AFTER.json",{"at":timezone.now(),"authority":authority,"authority_unchanged":normalized==before["authority"],"models":models,"model_deltas":deltas,"product_changes":file_changes,"historical_changes":historical_changes})
    print(json.dumps({"authority_unchanged":normalized==before["authority"],"model_deltas":deltas,"product_changes":file_changes,"historical_changes":historical_changes}))
