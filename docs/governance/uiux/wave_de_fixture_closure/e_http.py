"""Real-login read controls for the representative responsive audit."""
import json
import subprocess
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import build_opener, HTTPCookieProcessor, Request
from entry import OUT, ROOT, guard, save
from apps.projects.models import Project
from apps.organizations.models import OrganizationMembership
from apps.procurement.models import RequestForQuotation, SupplierPortalGrant

guard()
BASE = "http://127.0.0.1:8000"
sessions = {}
rows = []

def get(alias, path):
    if alias not in sessions:
        jar = CookieJar()
        opener = build_opener(HTTPCookieProcessor(jar))
        opener.open(BASE + "/accounts/login/").read()
        secret = subprocess.run([str(ROOT / ".venv-2/Scripts/python.exe"), str(OUT.parent / "rv007_controlled_time/credential.py"), alias], capture_output=True, text=True, check=True).stdout
        payload = urlencode({"username":alias, "password":secret, "csrfmiddlewaretoken":next(c.value for c in jar if c.name=="csrftoken")}).encode()
        del secret
        response = opener.open(Request(BASE + "/accounts/login/", data=payload, headers={"Referer":BASE + "/accounts/login/"}))
        assert "/accounts/login/" not in response.geturl()
        response.read()
        sessions[alias] = opener
    try:
        response = sessions[alias].open(BASE + path, timeout=30)
    except HTTPError as exc:
        response = exc
    body = response.read().decode()
    return response.status, urlsplit(response.geturl()).path, body

def check(alias, path, expected, case, redirect=False):
    status, final, body = get(alias, path)
    passed = status in expected and (final != path if redirect else final == path)
    rows.append({"actor":alias,"path":path,"case":case,"status":status,"expected":expected,"final":final,"passed":passed})
    save("E_HTTP.json", rows)
    assert passed, rows[-1]
    return body

objects = json.loads((OUT / "E_OBJECT_MAP.json").read_text(encoding="utf-8"))
external = "uiux.wcd.external"
check(external, f"/procurement/portal/grants/{objects['portal'][0]['id']}/", [404], "expired external grant fails closed")
check(external, "/payroll/", [200], "external identity has no implicit tenant payroll access", redirect=True)
check(external, f"/procurement/rfqs/{objects['rfqs'][0]['id']}/buyer/", [200], "external cannot enter buyer workspace", redirect=True)
assert not OrganizationMembership.objects.filter(user__username=external).exists()
project_c = Project.objects.get(organization__slug="demo-construction-01", code="PRJ-01-03")
check("uiux.audit.project", f"/projects/{project_c.pk}/", [403,404], "project A reader cannot read project C")
foreign = Project.objects.exclude(organization__slug="demo-construction-01").first()
assert foreign
check("uiux.audit.project", f"/projects/{foreign.pk}/", [403,404], "foreign tenant identifier denied")
check("uiux.wavec.commercial", "/commercial/create/", [200], "existing Commercial create form permission")
check("uiux.wavec.documents", "/documents/", [200], "Document Control permitted list")
check("uiux.wavec.payroll", "/payroll/", [200], "Payroll specialist permitted workbench")
check("uiux.persona.inventory", "/inventory/", [200], "Inventory reader permitted list, no mutation claim")
check("uiux.wavec.controls", f"/projects/{objects['project']}/controls/", [200], "Project Controls explicit assigned project")
check("uiux.wavec.controls", f"/projects/{project_c.pk}/controls/", [403,404], "Project Controls unassigned project denied")
check("uiux.wavec.buyer", f"/procurement/rfqs/{objects['rfqs'][0]['id']}/buyer/", [200], "protected Buyer representative")
other_rfq = RequestForQuotation.objects.exclude(organization__slug="demo-construction-01").first()
assert other_rfq
check("uiux.wavec.buyer", f"/procurement/rfqs/{other_rfq.pk}/buyer/", [403,404], "Buyer foreign tenant denied")
check("uiux.persona.project-manager", "/equipment/operations/", [403], "project scopes do not become organization workbench authority")
check("account.demo-construction-01.owner", "/equipment/operations/", [200], "existing organization scope permits Equipment workbench")
check("account.demo-construction-01.owner", "/accounting/statements/", [200], "existing organization authority permits statement filter")
check("uiux.persona.tenant-admin", "/organizations/platform/roles/", [403], "Tenant Admin remains separate from Platform Admin")
check("admin", "/organizations/platform/roles/", [200], "separate Platform Admin role catalog")
save("E_HTTP_SUMMARY.json", {"count":len(rows),"all_passed":all(r['passed'] for r in rows),"business_posts":0,"external_membership_created":False})
print(len(rows), "Wave E server controls PASS")
