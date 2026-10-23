"""Actual cookie/CSRF HTTP; credentials, tokens and response bodies stay in memory."""
from configure import *  # noqa: F403
import hashlib
import subprocess
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPCookieProcessor
from uuid import uuid4

from apps.accounting.models import FinancialStatementRun
from apps.payroll.models import PayrollInput, StatutoryCalculation
from apps.procurement.models import SupplierPortalSubmissionReceipt, QuoteRevisionEvidence
from apps.subledgers.models import SettlementAllocation
from apps.projects.models import Project

BASE = "http://127.0.0.1:8000"
sessions, observations = {}, []


def request(alias, path, data=None, *, csrf=True, payload=None):
    if alias not in sessions:
        jar = CookieJar()
        sessions[alias] = (build_opener(HTTPCookieProcessor(jar)), jar)
        request(alias, "/accounts/login/")
        assert all(c.isalnum() or c in ".-" for c in alias)
        command = "$c=Import-Clixml -LiteralPath ($env:LOCALAPPDATA+'/BONIRA/UIUXRuntimeAudit/credentials/" + alias + ".clixml'); [Console]::Write($c.GetNetworkCredential().Password)"
        secret = subprocess.run(["pwsh", "-NoProfile", "-Command", command], capture_output=True, text=True, check=True).stdout
        status, _, final = request(alias, "/accounts/login/", {"username": alias, "password": secret})
        del secret
        assert status == 200 and "/accounts/login/" not in final
    opener, jar = sessions[alias]
    headers = {"Referer": BASE + path}
    body = None
    if data is not None:
        data = dict(data)
        if csrf:
            data["csrfmiddlewaretoken"] = next(c.value for c in jar if c.name == "csrftoken")
        if payload is None:
            body = urlencode(data).encode()
        else:
            boundary = "WaveC" + uuid4().hex
            body = b""
            for key, value in data.items():
                body += f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="upload"; filename="bid.pdf"\r\nContent-Type: application/pdf\r\n\r\n'.encode() + payload + b"\r\n"
            body += f"--{boundary}--\r\n".encode()
            headers["Content-Type"] = "multipart/form-data; boundary=" + boundary
    try:
        response = opener.open(Request(BASE + path, data=body, headers=headers), timeout=30)
    except HTTPError as exc:
        response = exc
    return response.status, response.read(), response.geturl()


def check(alias, path, expected, label, data=None, **kwargs):
    status, body, final = request(alias, path, data, **kwargs)
    observations.append({"actor": alias, "path": path, "method": "GET" if data is None else "POST", "case": label,
                         "status": status, "expected": expected, "passed": status in expected,
                         "final_path": urlsplit(final).path, "response_sha256": hashlib.sha256(body).hexdigest()})
    save("HTTP.json", observations)
    assert status in expected, observations[-1]
    return body, final


def main():
    assert settings.SETTINGS_MODULE == "config.settings.development" and settings.DEBUG
    org = Organization.objects.get(slug="demo-construction-01")
    financial = json.loads((OUT / "FINANCIAL_FLOW.json").read_text())
    payroll = json.loads((OUT / "PAYROLL_FLOW.json").read_text())
    tender = json.loads((OUT / "TENDER_FLOW.json").read_text())
    portal = json.loads((OUT / "PORTAL_FIXTURE.json").read_text())
    accountant, hr, specialist, commercial, external = "account.demo-construction-01.accountant", "uiux.wavec.hr", "uiux.wavec.payroll", "uiux.wavec.commercial", portal["external_user"]
    statement = "/accounting/statements/" + financial["statement"] + "/"
    check(accountant, statement, [200], "Populated statement and progressive audit metadata")
    foreign = FinancialStatementRun.objects.exclude(organization=org).first()
    assert foreign
    check(accountant, f"/accounting/statements/{foreign.pk}/", [404], "Cross-tenant statement identifier denied")
    check(hr, statement, [403], "Same-tenant HR cannot read financial statement")
    workbench, _ = check(accountant, "/subledgers/", [200], "Settlement uses source selector rather than pasted UUID")
    assert b'<select name="treasury_movement_id"' in workbench and b'<input name="treasury_movement_id"' not in workbench
    allocations = SettlementAllocation.objects.filter(organization=org).count()
    allocate = f'/subledgers/obligations/{financial["obligation"]}/allocate/'
    check(accountant, allocate, [403], "Allocation POST requires CSRF", {}, csrf=False)
    check(accountant, allocate, [404], "Malformed movement identifier is bounded, not HTTP 500", {"treasury_movement_id": "invalid"})
    check(hr, allocate, [403], "Unauthorized allocation denied", {})
    check(accountant, allocate, [200], "Over-allocation preserves fully consumed source", {"treasury_movement_id": financial["movement"], "amount": "1", "effective_date": timezone.localdate().isoformat(), "reason": LABEL, "idempotency_key": "wcd-http-overalloc"})
    assert SettlementAllocation.objects.filter(organization=org).count() == allocations
    fixed = f'/payroll/runs/{payroll["fixed_run"]}/'
    source = f'/payroll/runs/{payroll["variable_run"]}/inputs/new/'
    check(specialist, fixed, [200], "Finalized ordinary Payroll")
    check(hr, fixed, [403], "Payroll-only data denied to HR persona")
    body, _ = check(specialist, source, [200], "Approved source and rule controls only")
    for field in ["source_uuid", "source_reference", "source_version", "source_status", "source_payload_json"]:
        assert ('name="' + field + '"').encode() not in body
    input_count = PayrollInput.objects.filter(organization=org).count()
    check(specialist, source, [403], "Payroll source POST requires CSRF", {}, csrf=False)
    check(specialist, source, [200], "Forged source invalid redisplay", {"timesheet": str(uuid4()), "rule": payroll["rule"]})
    assert PayrollInput.objects.filter(organization=org).count() == input_count
    check(specialist, "/payroll/statutory/", [200], "Four canonical prerequisite states visible")
    count = StatutoryCalculation.objects.filter(organization=org).count()
    body, _ = check(specialist, "/payroll/statutory/calculations/new/", [200], "Absent statutory authority fails closed", {"run": payroll["fixed_run"], "kind": "payroll_tax", "record_kind": "original", "reason": LABEL})
    assert "نسخه مقرراتی پلتفرمِ منتشرشده و مؤثر وجود ندارد".encode() in body
    assert StatutoryCalculation.objects.filter(organization=org).count() == count
    check(specialist, "/payroll/financial-handoffs/", [200], "Prepared proposals and explicit exceptions")
    detail = f'/commercial/{tender["tender"]}/'
    check(commercial, detail, [200], "Tender immutable lifecycle history")
    check(commercial, "/commercial/create/", [400], "Project-scoped actor cannot omit project", {"opportunity_code": "WCD-NO-PROJECT", "title": LABEL})
    project = Project.objects.exclude(organization=org).first()
    check(commercial, "/commercial/create/", [400], "Cross-tenant project rejected by authorized selector", {"opportunity_code": "WCD-FOREIGN", "title": LABEL, "project": str(project.pk)})
    check(hr, detail, [403], "Unauthorized Tender access denied")
    grant = f'/procurement/portal/grants/{portal["grant"]}/'
    check(external, grant, [200], "External context without membership")
    check(hr, grant, [404], "Internal identity cannot impersonate external principal")
    check(external, grant + "submit/", [403], "External submission requires CSRF", {}, csrf=False)
    check(external, grant + "submit/", [400], "Actual primary file is mandatory", {"idempotency_key": "wcd-http-missing"})
    payload = (OUT / "synthetic_primary_bid.pdf").read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    data = {"idempotency_key": "wcd-http-primary", "source_reference": "WCD-HTTP", "integrity_fingerprint": digest}
    _, first = check(external, grant + "submit/", [200], "Actual multipart payload retained with server authority", data, payload=payload)
    _, replay = check(external, grant + "submit/", [200], "Identical payload replay returns same receipt", data, payload=payload)
    assert first == replay
    receipt = SupplierPortalSubmissionReceipt.objects.get(pk=urlsplit(first).path.rstrip("/").split("/")[-1])
    evidence = QuoteRevisionEvidence.objects.get(quote_revision=receipt.quote_revision)
    with evidence.document_version.file.open("rb") as retained:
        assert hashlib.sha256(retained.read()).hexdigest() == digest
    assert evidence.canonical_sha256 == receipt.quote_revision.integrity_fingerprint == digest
    before = SupplierPortalSubmissionReceipt.objects.filter(organization=org).count()
    check(external, grant + "submit/", [400], "Changed bytes cannot reuse idempotency key", {**data, "integrity_fingerprint": ""}, payload=payload + b"\n% changed payload")
    check(external, grant + "submit/", [400], "Client digest mismatch is rejected", {**data, "idempotency_key": "wcd-http-mismatch", "integrity_fingerprint": "a" * 64}, payload=payload)
    assert SupplierPortalSubmissionReceipt.objects.filter(organization=org).count() == before
    assert not org.memberships.filter(user__username=external).exists()
    save("PORTAL_INTEGRITY.json", {"receipt": str(receipt.pk), "evidence": str(evidence.pk), "server_sha256": digest, "stored_bytes_verified": True, "state": evidence.sealed_custody.state, "no_tenant_membership": True, "replay_same_receipt": True})
    print(f"Real HTTP: {len(observations)}/{len(observations)} expected controls PASS")


if __name__ == "__main__":
    main()
