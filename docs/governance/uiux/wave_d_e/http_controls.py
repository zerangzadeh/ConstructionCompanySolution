"""Real-cookie Development read controls; no successful business POSTs."""
import hashlib
import json
import subprocess
import sys
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPCookieProcessor

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT.parent / "rv007_controlled_time"))
from support import guard, ROOT
from django.apps import apps
from apps.organizations.authorization import effective_scope_grants
from apps.organizations.models import OrganizationMembership
from apps.workforce.models import WorkRelationship
from apps.workflows.models import WorkflowVersion


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


guard()
BASE = "http://127.0.0.1:8000"
sessions = {}
observations = []


def request(alias, path, data=None):
    if alias not in sessions:
        jar = CookieJar()
        sessions[alias] = build_opener(HTTPCookieProcessor(jar)), jar
        request(alias, "/accounts/login/")
        secret = subprocess.run([str(ROOT / ".venv-2/Scripts/python.exe"), str(OUT.parent / "rv007_controlled_time/credential.py"), alias], capture_output=True, text=True, check=True).stdout
        status, _, final = request(alias, "/accounts/login/", {"username":alias,"password":secret})
        del secret
        assert status == 200 and "/accounts/login/" not in final
    opener, jar = sessions[alias]
    if data is not None:
        data = dict(data)
        data["csrfmiddlewaretoken"] = next(c.value for c in jar if c.name == "csrftoken")
    try:
        response = opener.open(Request(BASE + path, data=None if data is None else urlencode(data).encode(), headers={"Referer":BASE + path}), timeout=30)
    except HTTPError as exc:
        response = exc
    return response.status, response.read(), response.geturl()


def check(alias, path, expected, case):
    status, body, final = request(alias, path)
    row = {"actor":alias,"path":path,"method":"GET","status":status,"expected":expected,"case":case,"passed":status in expected,"final_path":urlsplit(final).path,"body_sha256":hashlib.sha256(body).hexdigest()}
    observations.append(row)
    save("HTTP.json",observations)
    assert row["passed"],row
    return body.decode()


reader, manager, own, admin = "uiux.audit.project", "uiux.persona.project-manager", "uiux.wavec.time", "uiux.persona.tenant-admin"
org_slug = "demo-construction-01"
scope_rows = {}
for alias in (reader,manager,own,admin):
    membership = OrganizationMembership.objects.get(user__username=alias,organization__slug=org_slug)
    scope_rows[alias] = list(effective_scope_grants(membership).values("scope_type","project_id","site_id"))
save("SCOPES.json",{"note":"Live effective_scope_grants is authoritative; initial READINESS.json scope list used an absent reverse-name fallback and is not scope evidence.","actors":scope_rows})
for app, model_name, business_field in (("safety","SafetyIncident","incident_number"),("quality","QualityIssue","issue_number")):
    model = apps.get_model(app,model_name)
    a = model.objects.get(organization__slug=org_slug,project__code="PRJ-01-01")
    b = model.objects.get(organization__slug=org_slug,project__code="PRJ-01-02")
    c = model.objects.get(organization__slug=org_slug,project__code="PRJ-01-03")
    foreign = model.objects.exclude(organization__slug=org_slug).first()
    check(reader,f"/{app}/{a.pk}/",[200],f"{app} own project reader")
    check(reader,f"/{app}/{b.pk}/",[403,404],f"{app} reader cannot read unauthorized sibling project")
    check(manager,f"/{app}/{b.pk}/",[200],f"{app} manager own authorized lifecycle form")
    check(manager,f"/{app}/{c.pk}/",[403,404],f"{app} manager cannot read project C")
    assert foreign is not None
    text = check(manager,f"/{app}/{foreign.pk}/",[403,404],f"{app} cross-tenant denial")
    assert getattr(foreign,business_field) not in text
check(own,"/workforce/ess/",[200],"Explicit linked own ESS dashboard")
check(own,"/workforce/ess/profile/",[200],"Own linked profile")
other = WorkRelationship.objects.filter(organization__slug=org_slug).exclude(person__user__username=own).first()
assert other
check(own,f"/workforce/ess/profile/{other.pk}/",[403,404],"ESS rejects another worker relationship identifier")
check(own,"/payroll/ess/",[403],"Retained linked identity lacks payroll own-history grant; not positive evidence")
check(reader,"/workforce/ess/",[403],"No explicit person link fails closed")
v = WorkflowVersion.objects.filter(organization__slug=org_slug,status="published").first()
check(admin,f"/workflows/administration/versions/{v.pk}/",[200],"Existing tenant-admin workflow view authority")
foreign = WorkflowVersion.objects.exclude(organization__slug=org_slug).first()
assert foreign
check(admin,f"/workflows/administration/versions/{foreign.pk}/",[404],"Workflow cross-tenant identifier unavailable")
check(admin,"/knowledge/platform/promotions/",[403],"Tenant Admin cannot access Platform Admin queue")
save("HTTP_SUMMARY.json",{"count":len(observations),"all_passed":all(r["passed"] for r in observations),"business_post_count":0,"real_login_cookie_csrf":True,"credentials_saved":False})
print(len(observations),"authenticated HTTP read controls PASS")
