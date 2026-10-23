"""Real authenticated HTTP with cookie-bound CSRF; no cookies or credentials saved."""
import hashlib
from http.cookiejar import CookieJar
import json
from pathlib import Path
import re
import runpy
import subprocess
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import build_opener, HTTPCookieProcessor, Request

OUT = Path(__file__).resolve().parent
R = runpy.run_path(str(OUT / "runtime.py"), run_name="http_support")
from apps.projects.models import Project
from apps.audit.models import AuditEvent
from apps.organizations.models import Organization

BASE = "http://127.0.0.1:8015"
sessions = {}
records = []

def request(alias, path, data=None, *, raw_csrf=True):
    if alias not in sessions:
        jar = CookieJar()
        opener = build_opener(HTTPCookieProcessor(jar))
        sessions[alias] = (opener, jar)
        request(alias, "/accounts/login/")
        program = "$c=Import-Clixml -LiteralPath ($env:LOCALAPPDATA+'/BONIRA/UIUXRuntimeAudit/credentials/" + alias + ".clixml'); $c.GetNetworkCredential().Password"
        secret = subprocess.run([r"C:\Users\azera\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe", "-NoProfile", "-Command", program], capture_output=True, text=True, check=True).stdout.strip()
        status, body, url = request(alias, "/accounts/login/", {"username": alias, "password": secret})
        del secret
        assert status == 200 and "/accounts/login/" not in url, (alias,status,url)
    opener, jar = sessions[alias]
    if data is not None:
        data = dict(data)
        if raw_csrf:
            data["csrfmiddlewaretoken"] = next(c.value for c in jar if c.name == "csrftoken")
    req = Request(BASE + path, data=None if data is None else urlencode(data,doseq=True).encode(), headers={"Referer": BASE+path})
    try:
        response = opener.open(req,timeout=40)
    except HTTPError as exc:
        response = exc
    return response.status, response.read(), response.geturl()

def check(scenario, alias, path, case, data=None, expected=None, *, raw_csrf=True):
    status, body, final_url = request(alias,path,data,raw_csrf=raw_csrf)
    text = body.decode("utf-8",errors="replace")
    filename = None
    if status < 500 and "<main" in text:
        main = re.search(r"<main\b[^>]*>.*</main>",text,re.S).group(0)
        main = re.sub(r'<input[^>]*name="csrfmiddlewaretoken"[^>]*>',"<!-- CSRF omitted -->",main)
        filename = f"http_{len(records)+1:03}.html"
        (OUT/filename).write_text(main,encoding="utf-8")
    records.append({"scenario":scenario,"actor":alias,"path":path,"case":case,"method":"POST" if data is not None else "GET","csrf":raw_csrf if data is not None else None,"status":status,"final_path":urlsplit(final_url).path,"sha256":hashlib.sha256(body).hexdigest(),"html":filename,"expected":expected,"passed":expected is None or status in expected})
    R["save"]("HTTP.json",records)
    assert status != 500, (scenario,alias,path,"server failure")
    return status, text

def main():
    project = {k:str(Project.objects.get(code=v).pk) for k,v in [("A","PRJ-01-01"),("C","PRJ-01-03"),("X","PRJ-02-01")]}
    old = json.loads((OUT.parent/"wave_c_evidence/FIXTURES.json").read_text(encoding="utf-8"))
    domain = json.loads((OUT/"DOMAIN_FIXTURES.json").read_text(encoding="utf-8"))
    doc = json.loads((OUT/"DOCUMENT_SCAN.json").read_text(encoding="utf-8"))
    unauthorized = "uiux.persona.inventory"
    matrix = {
        "RV-007":("uiux.wavec.buyer",[f"/procurement/rfqs/{old['rfqs']['A']['id']}/buyer/",f"/procurement/rfqs/{old['rfqs']['A']['id']}/buyer/capture/",f"/procurement/rfqs/{old['rfqs']['A']['id']}/buyer/prepare_comparison/"]),
        "RV-015":("uiux.wavec.hr",["/workforce/","/workforce/departments/","/workforce/foundation/","/workforce/departments/create/","/workforce/positions/create/","/workforce/teams/create/","/workforce/employees/create/"]),
        "RV-017":("uiux.wavec.time",["/timekeeping/","/timekeeping/calendars/new/","/timekeeping/holidays/new/","/timekeeping/attendance/new/","/timekeeping/attendance/import/"]),
        "RV-018":("uiux.wavec.payroll",["/payroll/","/payroll/configuration/","/payroll/configuration/employment/new/","/payroll/configuration/rules/new/","/payroll/runs/new/",f"/payroll/runs/{domain['payroll']['run']}/","/payroll/statutory/","/payroll/statutory/calculations/new/","/payroll/financial-handoffs/","/payroll/financial-handoffs/new/"]),
        "RV-028":("uiux.wavec.documents",["/documents/","/documents/upload/",f"/documents/{doc['document']}/",f"/documents/{doc['document']}/download/"]),
        "RV-030":("uiux.wavec.commercial",["/commercial/","/commercial/create/","/contracts/"]),
        "RV-031":("uiux.wavec.controls",[f"/projects/{project['A']}/controls/",f"/projects/{project['A']}/controls/comparison/",f"/projects/{project['A']}/controls/exceptions/",f"/projects/{project['A']}/controls/cost-reconciliation/"]),
    }
    for scenario,(actor,paths) in matrix.items():
        for path in paths:
            check(scenario,actor,path,"specialist GET",expected=[200])
        # All form/action paths also receive a fully invalid CSRF-bearing POST.
        for path in [p for p in paths if any(c in p for c in ("/new/","/create/","/capture/","/prepare_comparison/","/upload/"))]:
            check(scenario,actor,path,"invalid redisplay + foreign identifier",{"project":project["X"],"site":"not-a-site","relationship":project["X"],"organization":"foreign","integrity_fingerprint":"invalid"},expected=[200,400,403,404])
            check(scenario,unauthorized,path,"same-tenant unauthorized POST",{"project":project["A"]},expected=[403,404])
        protected = paths[1] if len(paths)>1 else paths[0]
        check(scenario,actor,protected,"missing CSRF rejects",{},expected=[403],raw_csrf=False)
    for key in ("C","X"):
        check("RV-007","uiux.wavec.buyer",f"/procurement/rfqs/{old['rfqs'][key]['id']}/buyer/",key+" scope",expected=[403,404])
    for key in ("C","X"):
        for suffix in ("comparison/","exceptions/","cost-reconciliation/"):
            check("RV-031","uiux.wavec.controls",f"/projects/{project[key]}/controls/{suffix}",key+" project scope",expected=[403,404])
    check("RV-007","uiux.reference.batch03.site-only",f"/procurement/rfqs/{old['rfqs']['A']['id']}/buyer/","site-only cannot expand RFQ scope",expected=[403,404])
    for actor in ("uiux.wavec.hr","uiux.persona.inventory"):
        check("RV-029",actor,"/workforce/employment/","management capability denied without exact code",expected=[403])
        check("RV-029",actor,"/workforce/ess/employment/","unlinked own-history fail closed",expected=[403])
    # Specialist cannot cross into sensitive Workforce capabilities merely by HR setup.
    for path in ("/workforce/foundation/labor-rates/create/","/workforce/foundation/performance/create/"):
        check("RV-015","uiux.wavec.hr",path,"sensitive Workforce denial",expected=[403,404])
    for key in ("C","X"):
        docid = json.loads((OUT.parent/"wave_c_evidence/BROWSER_INPUT.json").read_text(encoding="utf-8"))["docs"][key]
        for suffix in ("","download/"):
            check("RV-028","uiux.wavec.documents",f"/documents/{docid}/{suffix}",key+" object-scope denial",expected=[403,404])
        check("RV-028","uiux.wavec.documents",f"/documents/{docid}/versions/add/",key+" manipulated object POST",{"organization":project["A"]},expected=[403,404])
    # Successful form writes already retained in HTTP_INITIAL_COMPLETE.json, with
    # final redirect paths /workforce/departments/ and /timekeeping/. No duplicate fixtures.
    check("RV-018","uiux.wavec.payroll","/payroll/configuration/employment/new/","project-site refresh preserves input",{"project":project["A"],"_refresh_context":"1","source_reference":"preserve synthetic field"},expected=[200])
    # Retest all currently blocked authority/policy paths without manufacturing positives.
    for scenario,path in [("RV-011","/accounting/statements/"),("RV-013","/subledgers/")]:
        check(scenario,"account.demo-construction-01.accountant",path,"policy/source gate remains",expected=[200])
    check("RV-032","uiux.wavec.commercial",f"/procurement/rfq-invitations/{old['rfqs']['A']['invitation']}/portal/","invitation permission remains unassignable",expected=[403])
    R["save"]("HTTP_SUMMARY.json",{"observations":len(records),"unexpected":[r for r in records if not r["passed"]],"csrf_bearing_posts":sum(r["method"]=="POST" and r["csrf"] for r in records)})
    print("Real HTTP:",len(records),"observations;",sum(not r["passed"] for r in records),"unexpected statuses")

if __name__ == "__main__":
    main()
