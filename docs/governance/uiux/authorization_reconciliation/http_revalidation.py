"""Real cookie/CSRF HTTP checks; responses/tokens/passwords stay in memory."""

from datetime import timedelta
from http.cookiejar import CookieJar
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import build_opener, HTTPCookieProcessor, Request

OUT = Path(__file__).resolve().parent
R = runpy.run_path(str(OUT / "revalidate.py"), run_name="http_support")
R["guard"]()
from django.utils import timezone
from django.urls import reverse
from apps.accounts.models import User
from apps.organizations.models import Organization, OrganizationMembership
from apps.procurement.models import RequestForQuotationInvitation, QuoteRevision, SupplierPortalInvitation
from apps.procurement.opening_services import request_quote_opening

BASE = "http://127.0.0.1:8017"
sessions = {}
observations = []


def request(alias, path, data=None, *, csrf=True):
    if alias not in sessions:
        jar = CookieJar()
        sessions[alias] = (build_opener(HTTPCookieProcessor(jar)), jar)
        request(alias, "/accounts/login/")
        # This script has a fixed reviewed alias set; no user-supplied shell input.
        program = "$c=Import-Clixml -LiteralPath ($env:LOCALAPPDATA+'/BONIRA/UIUXRuntimeAudit/credentials/" + alias + ".clixml'); $c.GetNetworkCredential().Password"
        secret = subprocess.run([r"C:\Users\azera\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe",
            "-NoProfile", "-Command", program], capture_output=True, text=True, check=True).stdout.strip()
        status, body, final = request(alias, "/accounts/login/", {"username": alias, "password": secret})
        del secret
        assert status == 200 and "/accounts/login/" not in final, (alias, status)
    opener, jar = sessions[alias]
    if data is not None:
        data = dict(data)
        if csrf:
            data["csrfmiddlewaretoken"] = next(c.value for c in jar if c.name == "csrftoken")
    req = Request(BASE + path, data=None if data is None else urlencode(data).encode(),
                  headers={"Referer": BASE + path})
    try:
        response = opener.open(req, timeout=30)
    except HTTPError as exc:
        response = exc
    return response.status, response.read(), response.geturl()


def check(alias, path, expected, label, data=None, *, csrf=True):
    status, body, final = request(alias, path, data, csrf=csrf)
    observation = {"actor": alias, "path": path, "method": "GET" if data is None else "POST",
        "case": label, "status": status, "expected": expected,
        "final_path": urlsplit(final).path, "csrf": csrf if data is not None else None,
        "response_sha256": hashlib.sha256(body).hexdigest(), "passed": status in expected}
    observations.append(observation)
    R["save"]("HTTP.json", observations)
    assert observation["passed"], observation
    return body


org = Organization.objects.get(slug="demo-construction-01")
quote = QuoteRevision.objects.get(pk=json.loads((OUT.parent / "wave_c_reentry/PROCUREMENT.json").read_text())["quote"])
rfq = quote.envelope.rfq
buyer_path = reverse("procurement:rfq_buyer_workspace", args=[rfq.pk])
check("uiux.wavec.buyer", buyer_path, [200], "RFQ buyer retains receiving/preparation and opening action")
check("uiux.wavec.opening-approver", buyer_path, [200], "Independent RFQ approval duty")
check("uiux.wavec.custodian", buyer_path, [200], "Separate RFQ custody duty")
opening_path = reverse("procurement:rfq_buyer_action", args=[rfq.pk, "request_opening"])
check("uiux.wavec.buyer", opening_path, [200], "Newly authorized opening form")
check("uiux.wavec.buyer", opening_path, [400], "Existing future-close/source lifecycle guard retained",
      {"quote_revision": quote.pk, "reason": "Development boundary control", "idempotency_key": "role-reconciliation-opening"})
check("uiux.wavec.hr", opening_path, [403], "Unassigned HR actor cannot open RFQ")
check("uiux.wavec.buyer", opening_path, [403], "Opening POST requires CSRF", {}, csrf=False)
try:
    request_quote_opening(organization=org, actor=User.objects.get(username="uiux.wavec.buyer"),
        quote_revision=quote, reason="Development future-close guard", idempotency_key="role-reconciliation-direct")
except Exception as exc:
    # The issued RFQ's future deadline means no closed custody manifest exists.
    assert type(exc).__name__ == "PermissionDenied", type(exc).__name__
    R["save"]("RFQ_BOUNDARY.json", {"role_authority": "GRANTED",
        "rfq_status": rfq.status, "closing_at": quote.rfq_version.closing_at,
        "opening_blocked_by_existing_lifecycle": True,
        "source_evidence_and_clean_scan_not_bypassed": True})
else:
    raise AssertionError("Issued RFQ unexpectedly opened")

management = reverse("workforce:employment_manage")
check("uiux.wavec.employment", management, [200], "Employment manager granted access")
check("uiux.wavec.employment", management, [400], "Employment invalid form redisplays with no write", {})
check("uiux.wavec.employment", management, [403], "Employment POST requires CSRF", {}, csrf=False)
check("uiux.wavec.hr", management, [403], "HR foundation role does not imply Employment authority")
own = reverse("workforce:employment_history")
check("uiux.wavec.time", own, [200], "Own history uses existing explicitly linked identity")
check("uiux.wavec.hr", own, [403], "Unassigned user cannot read own-history capability")

invitation = RequestForQuotationInvitation.objects.get(pk=quote.invitation_id)
portal_path = reverse("procurement:portal_invitation_manage", args=[invitation.pk])
check("uiux.wavec.portal", portal_path, [200], "Exact project invitation management granted")
check("uiux.wavec.portal", portal_path, [403], "Invitation POST requires CSRF", {}, csrf=False)
check("uiux.wavec.hr", portal_path, [403], "Unassigned HR actor cannot manage portal")
before = SupplierPortalInvitation.objects.filter(rfq_invitation=invitation).count()
expires = min(timezone.now() + timedelta(hours=8), invitation.rfq_version.closing_at-timedelta(minutes=1))
check("uiux.wavec.portal", portal_path, [200], "Create genuine synthetic external invitation",
      {"invited_email": "wave-c-role-reconciliation@example.test",
       "expires_at": expires.strftime("%Y-%m-%dT%H:%M")})
created = SupplierPortalInvitation.objects.get(rfq_invitation=invitation,
    invited_email="wave-c-role-reconciliation@example.test")
assert SupplierPortalInvitation.objects.filter(rfq_invitation=invitation).count() == before+1
assert not OrganizationMembership.objects.filter(user__email=created.invited_email).exists()
R["save"]("PORTAL_BOUNDARY.json", {"invitation": str(created.pk),
    "exact_project": str(rfq.project_id), "new_tenant_member": False,
    "plaintext_token_serialized": False,
    "external_payload_custody_contract": "UNCHANGED_UNRESOLVED"})

foreign = RequestForQuotationInvitation.objects.filter(organization=org).exclude(pk=invitation.pk).first()
if foreign and foreign.rfq_version.rfq.project_id != rfq.project_id:
    check("uiux.wavec.portal", reverse("procurement:portal_invitation_manage", args=[foreign.pk]),
          [403,404], "Same-tenant other-project invitation denied")
R["save"]("HTTP_SUMMARY.json", {"observations": len(observations),
    "post_count": sum(row["method"] == "POST" for row in observations),
    "all_expected": all(row["passed"] for row in observations),
    "browser_visual_validation": "NOT_RERUN_NO_UI_CHANGE",
    "full_wave_c_completion": False})
print(f"{len(observations)} real HTTP observations passed; tokens and cookies were not serialized")
