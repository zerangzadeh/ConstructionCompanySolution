"""Real authenticated cookie/CSRF HTTP controls on temporary clocked Development."""
from support import *
from http.cookiejar import CookieJar
from urllib.request import Request, build_opener, HTTPCookieProcessor
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from apps.procurement.models import RequestForQuotation, QuoteRevision, QuoteOpeningEvent, CommercialComparison

guard()
BASE = "http://127.0.0.1:8017"
sessions = {}
observations = []
made = read("FIXTURE.json")

def request(alias, path, data=None, csrf=True):
    if alias not in sessions:
        jar = CookieJar()
        sessions[alias] = build_opener(HTTPCookieProcessor(jar)), jar
        request(alias, "/accounts/login/")
        secret = subprocess.run([str(ROOT / ".venv/Scripts/python.exe"), str(OUT / "credential.py"), alias], capture_output=True, text=True, check=True).stdout
        status, body, final = request(alias, "/accounts/login/", {"username": alias, "password": secret})
        del secret
        assert status == 200 and "/accounts/login/" not in final, (alias, status, final)
    opener, jar = sessions[alias]
    if data is not None:
        data = dict(data)
        if csrf:
            data["csrfmiddlewaretoken"] = next(c.value for c in jar if c.name == "csrftoken")
    try:
        response = opener.open(Request(BASE + path, data=None if data is None else urlencode(data).encode(), headers={"Referer": BASE + path}), timeout=30)
    except HTTPError as exc:
        response = exc
    return response.status, response.read(), response.geturl()

def check(alias, path, expected, case, data=None, csrf=True):
    status, body, final = request(alias, path, data, csrf)
    observations.append({"case": case, "actor": alias, "path": path, "method": "GET" if data is None else "POST", "status": status, "expected": expected, "passed": status == expected, "body_sha256": hashlib.sha256(body).hexdigest(), "final_path": urlsplit(final).path, "application_clock": read("CLOCK.json")})
    save("HTTP.json", observations)
    assert status == expected, observations[-1]
    return body.decode()

buyer, hr, site, foreign, approver = "uiux.wavec.buyer", "uiux.wavec.hr", "uiux.reference.batch03.site-only", "account.demo-construction-02.owner", "uiux.wavec.opening-approver"
base = "/procurement/rfqs/" + made["rfq"] + "/buyer/"
before = {"opening_events": QuoteOpeningEvent.objects.count(), "comparisons": CommercialComparison.objects.count(), "quotes": QuoteRevision.objects.count()}
text = check(buyer, base, 200, "Opened quote confidential populated comparison")
assert "1499.50000000" in text and "page-1-synthetic-unit-price" in text and "مرحله استعلام" in text
text = check(buyer, base + "prepare_comparison/", 200, "Exact permitted source and comparison scope choices")
assert made["revision"] in text and made["scope"] in text
check(buyer, base + "approve_opening/", 403, "Requester has no independent opening approval UI authority")
check(approver, base, 200, "Independent opening approver workspace without confidential values")
assert "1499.50000000" not in request(approver, base)[1].decode()
check(hr, base, 403, "Unauthorized same-tenant workspace denied")
check(site, base, 404, "Site-only scope cannot discover Project-level buyer workspace")
# Foreign owner has no stored login credential; direct-service cross-tenant
# denial is separately proved. HTTP proves buyer cannot resolve foreign IDs.
check(buyer, base + "execute_arbitrary_action/", 404, "Manipulated unregistered action denied")
foreign_rfq = RequestForQuotation.objects.exclude(organization__slug="demo-construction-01").first()
assert foreign_rfq
check(buyer, f"/procurement/rfqs/{foreign_rfq.pk}/buyer/", 404, "Buyer cannot read foreign tenant RFQ")
check(buyer, base + "request_opening/", 403, "CSRF-less opening POST denied", {"quote_revision": made["revision"], "reason": "RV007", "idempotency_key": "RV007-forged"}, csrf=False)
foreign_revision = QuoteRevision.objects.filter(envelope__rfq__rfq_number="WAVE-C-RFQ-A").first()
assert foreign_revision
check(buyer, base + "request_opening/", 400, "Forged other-RFQ quote rejected by RFQ-scoped form", {"quote_revision": str(foreign_revision.pk), "reason": "RV007", "idempotency_key": "RV007-forged-foreign"})
check(buyer, base + "request_opening/", 400, "Malformed quote selector bounded to validation", {"quote_revision": "not-a-uuid", "reason": "RV007", "idempotency_key": "RV007-forged-invalid"})
check(buyer, base + "prepare_comparison/", 400, "Invalid comparison redisplays without mutation", {})
after = {"opening_events": QuoteOpeningEvent.objects.count(), "comparisons": CommercialComparison.objects.count(), "quotes": QuoteRevision.objects.count()}
assert before == after
save("HTTP_SUMMARY.json", {"observations": len(observations), "all_expected": all(x["passed"] for x in observations), "business_counts_unchanged": before == after, "controls": before, "csrf_real_cookie_login": True, "credentials_or_cookies_saved": False})
print(len(observations), "real authenticated HTTP observations PASS; no business mutation.")
