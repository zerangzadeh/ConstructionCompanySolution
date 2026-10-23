"""Authenticated, CSRF-aware real HTTP boundary checks with in-memory secrets."""
import json
import subprocess
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import build_opener, HTTPCookieProcessor, Request

from entry import ROOT, OUT, guard, save
from apps.organizations.models import OrganizationMembership
from apps.projects.models import Project
from apps.procurement.models import SupplierPortalGrant, RequestForQuotation
from apps.procurement.portal_services import get_supplier_portal_rfq_context
from django.core.exceptions import PermissionDenied

guard()
BASE = "http://127.0.0.1:8000"
fixture = json.loads((OUT / "PORTAL_FIXTURE.json").read_text(encoding="utf-8"))
sessions = {}
rows = []


def request(alias, path, data=None):
    if alias not in sessions:
        jar = CookieJar()
        opener = build_opener(HTTPCookieProcessor(jar))
        opener.open(BASE + "/accounts/login/").read()
        password = subprocess.check_output([str(ROOT / ".venv-2/Scripts/python.exe"), str(OUT.parent / "rv007_controlled_time/credential.py"), alias], text=True)
        payload = urlencode({"username": alias, "password": password, "csrfmiddlewaretoken": next(c.value for c in jar if c.name == "csrftoken")}).encode()
        del password
        response = opener.open(Request(BASE + "/accounts/login/", data=payload, headers={"Referer": BASE + "/accounts/login/"}))
        assert "/accounts/login/" not in response.geturl()
        response.read()
        sessions[alias] = opener, jar
    opener, jar = sessions[alias]
    payload = None
    if data is not None:
        payload = urlencode(dict(data, csrfmiddlewaretoken=next(c.value for c in jar if c.name == "csrftoken"))).encode()
    try:
        response = opener.open(Request(BASE + path, data=payload, headers={"Referer": BASE + path}), timeout=30)
    except HTTPError as exc:
        response = exc
    return response.status, urlsplit(response.geturl()).path, response.read().decode()


def check(alias, path, expected, case, redirect=False, data=None):
    status, final, body = request(alias, path, data)
    passed = status in expected and (final != urlsplit(path).path if redirect else final == urlsplit(path).path)
    rows.append({"actor": alias, "path": path, "case": case, "status": status, "final": final, "method": "POST" if data is not None else "GET", "passed": passed})
    save("HTTP_CONTROLS.json", rows)
    assert passed, rows[-1]
    return body


external = fixture["external"]
fresh = fixture["path"]
body = check(external, fresh, [200], "fresh authenticated exact invitation context")
assert "WCD-PORTAL-RFQ" in body and "ارسال پیشنهاد" in body
check(external, "/procurement/portal/grants/f83ba13d-b9cf-45a3-ac94-8e0cfb80eef0/", [404], "old expired grant remains denied")
other = RequestForQuotation.objects.exclude(organization__slug="demo-construction-01").first()
assert other
check(external, f"/procurement/portal/grants/{other.pk}/", [404], "foreign opportunity identifier cannot become a portal grant")
check("uiux.persona.tenant-admin", fresh, [404], "tenant membership never becomes external principal")
check("uiux.persona.tenant-admin", fresh + "submit/", [404], "manipulated external write denied", data={"supplier_reference": "UIUX_TEST_ONLY_DENIED"})
for path in ("/payroll/", "/projects/", f"/procurement/rfqs/{fixture['rfq']}/buyer/"):
    check(external, path, [200], "external has no implicit tenant authority", redirect=True)
check("uiux.persona.tenant-admin", "/organizations/platform/roles/", [403], "tenant admin cannot read Platform catalogue")
body = check("admin", "/organizations/platform/roles/", [200], "separate Platform Admin localized catalogue")
assert 'for="organization-filter">شرکت</label>' in body
foreign = Project.objects.exclude(organization__slug="demo-construction-01").first()
unassigned = Project.objects.get(organization__slug="demo-construction-01", code="PRJ-01-03")
for project in (foreign, unassigned):
    check("uiux.audit.project", f"/projects/{project.pk}/", [403, 404], "foreign tenant or unassigned Project denied")
body = check("uiux.persona.project-operations", "/projects/?start_date_from=1404%2F01%2F01&start_date_to=1404%2F12%2F29", [200], "existing Jalali date bounds keep intended projects")
assert "PRJ-01-01" in body and "PRJ-01-02" in body
body = check("uiux.audit.project", "/quality/?identified_at_from=1404%2F01%2F01&identified_at_to=1404%2F12%2F29", [200], "existing Quality Jalali bounds retain same row")
assert "QLT-01-01-01" in body
for alias, path in (("uiux.persona.project-operations", "/projects/?start_date_from=1499%2F01%2F01"), ("uiux.audit.project", "/quality/?identified_at_from=1499%2F01%2F01")):
    body = check(alias, path, [200], "future date bound excludes historical records")
    assert ("PRJ-01-01" if path.startswith("/projects/") else "QLT-01-01-01") not in body.split('<main')[1]
old = SupplierPortalGrant.objects.select_related("principal__user").get(pk="f83ba13d-b9cf-45a3-ac94-8e0cfb80eef0")
try:
    get_supplier_portal_rfq_context(actor=old.principal.user, grant=old)
except PermissionDenied:
    pass
else:
    raise AssertionError("Expired context service must deny")
assert OrganizationMembership.objects.filter(user__username=external).count() == 0
save("HTTP_SUMMARY.json", {"count": len(rows), "all_passed": all(r["passed"] for r in rows), "expired_service_denied": True, "external_memberships": 0, "successful_business_posts": 0})
print(f"Authenticated HTTP: {len(rows)}/{len(rows)} PASS; external membership 0.")
