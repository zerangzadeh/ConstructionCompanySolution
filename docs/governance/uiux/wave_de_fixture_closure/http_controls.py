"""Normal Development login/CSRF cookie controls; no business mutations."""
import hashlib
import json
import subprocess
import sys
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPCookieProcessor

from entry import guard, OUT, ROOT, save
from apps.workforce.models import WorkRelationship
from apps.payroll.models import Payslip
from apps.knowledge.models import KnowledgePublicationVersion

guard()
BASE = "http://127.0.0.1:8000"
sessions = {}
rows = []

def request(alias, path, data=None):
    if alias not in sessions:
        jar = CookieJar()
        sessions[alias] = build_opener(HTTPCookieProcessor(jar)), jar
        request(alias, "/accounts/login/")
        secret = subprocess.run([str(ROOT / ".venv-2/Scripts/python.exe"), str(OUT.parent / "rv007_controlled_time/credential.py"), alias], capture_output=True, text=True, check=True).stdout
        code, body, final = request(alias, "/accounts/login/", {"username":alias, "password":secret})
        del secret
        assert code == 200 and "/accounts/login/" not in final
    opener, jar = sessions[alias]
    if data is not None:
        data = dict(data, csrfmiddlewaretoken=next(c.value for c in jar if c.name == "csrftoken"))
    try:
        response = opener.open(Request(BASE + path, data=None if data is None else urlencode(data).encode(), headers={"Referer":BASE + path}), timeout=30)
    except HTTPError as exc:
        response = exc
    return response.status, response.read(), response.geturl()

def check(alias, path, expected, case):
    status, body, final = request(alias, path)
    row = {"actor":alias, "path":path, "method":"GET", "status":status, "expected":expected, "case":case, "passed":status in expected, "final_path":urlsplit(final).path, "body_sha256":hashlib.sha256(body).hexdigest()}
    rows.append(row)
    save("HTTP.json", rows)
    assert row["passed"], row
    return body.decode()

own = "uiux.persona.project-operations"
curator = "account.demo-construction-01.owner"
tenant_admin = "uiux.persona.tenant-admin"
reader = "uiux.audit.project"
f = json.loads((OUT / "RV021_FIXTURE.json").read_text(encoding="utf-8"))
version = f["version"]
for route in ("/workforce/ess/", "/workforce/ess/profile/", "/payroll/ess/"):
    check(own, route, [200], "explicit linked own subject and existing permissions")
slip = Payslip.objects.filter(organization__slug="demo-construction-01").first()
assert slip
check(own, f"/payroll/ess/payslips/{slip.pk}/", [403,404], "another employee finalized payslip unavailable")
other = WorkRelationship.objects.filter(organization__slug="demo-construction-01").exclude(person__user__username=own).first()
foreign = WorkRelationship.objects.exclude(organization__slug="demo-construction-01").first()
assert other and foreign
for target in (other, foreign):
    check(own, f"/workforce/ess/profile/{target.pk}/", [403,404], "other worker / foreign tenant relationship unavailable")
check("uiux.wavec.time", "/payroll/ess/", [403], "linked identity without payroll ESS permission remains denied")
check(reader, "/workforce/ess/", [403], "unlinked identity remains denied")
check(curator, f"/knowledge/publications/{version}/", [200], "prepared publication article")
check(curator, f"/knowledge/publications/{version}/history/", [200], "authorized source traceability")
text = check(reader, f"/knowledge/publications/{version}/", [403], "project-only reader cannot expand to organization-scoped knowledge")
assert "درخواست انتشار در سکوی مشترک" not in text
check(reader, f"/knowledge/publications/{version}/history/", [403,404], "reader without history grant cannot open traceability")
check(tenant_admin, "/knowledge/platform/promotions/", [403], "tenant administration is not platform authority")
text = check("admin", "/knowledge/platform/promotions/", [200], "separately assigned platform admin sees sanitized queue")
assert f["source"] not in text and f["version"] not in text
# A fresh platform-only login has no active tenant context. It may not read a source.
status, _, final = request("admin", f"/knowledge/publications/{version}/history/")
rows.append({"actor":"admin", "case":"platform session has no implicit tenant source access", "status":status, "final_path":urlsplit(final).path, "passed":"/knowledge/publications/" not in urlsplit(final).path})
save("HTTP.json", rows)
assert rows[-1]["passed"]
save("HTTP_SUMMARY.json", {"count":len(rows), "all_passed":all(r["passed"] for r in rows), "business_post_count":0, "real_login_cookie_csrf":True, "secrets_persisted":False})
print(len(rows), "Development HTTP controls PASS")
