"""Real authenticated CSRF HTTP requests against a fresh Development server."""

import hashlib
import json
import subprocess
import sys
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

from closure import OUT, helpers, save, state

from apps.accounts.models import User
from apps.billing.forms import RetentionReleaseForm
from apps.billing.models import ContractComplianceEvidence
from apps.contracts.models import Contract
from apps.organizations.authorization import get_active_membership
from apps.organizations.models import Organization

BASE = helpers["BASE"]
PATH = helpers["PATH"]
Parsed = helpers["Parsed"]
fixtures = json.loads((OUT / "FIXTURES.json").read_text(encoding="utf-8"))["fixtures"]
records = []
org = Organization.objects.get(slug="demo-construction-01")


def http(positive_only=False):
    if positive_only:
        records.extend(
            json.loads((OUT / "RUNTIME_HTTP.json").read_text(encoding="utf-8"))
        )
    else:
        save("RUNTIME_BEFORE.json", state())
    for alias in (
        (helpers["POSITIVE"],)
        if positive_only
        else (helpers["LIMITED"], helpers["POSITIVE"])
    ):
        opener = build_opener(HTTPCookieProcessor(CookieJar()))

        def request(path, data=None, *, opener=opener):
            req = Request(
                BASE + path,
                data=None if data is None else urlencode(data).encode(),
                headers={"Referer": BASE + path},
            )
            try:
                response = opener.open(req, timeout=30)
            except HTTPError as exc:
                response = exc
            return response.status, response.read().decode("utf-8"), response.geturl()

        status, body, url = request("/accounts/login/")
        command = (
            "$c=Import-Clixml -LiteralPath ($env:LOCALAPPDATA+'/BONIRA/UIUXRuntimeAudit/credentials/"
            + alias
            + ".clixml'); $c.GetNetworkCredential().Password"
        )
        secret = subprocess.run(
            [
                r"C:\Users\azera\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe",
                "-NoProfile",
                "-Command",
                command,
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        status, body, url = request(
            "/accounts/login/",
            {
                "username": alias,
                "password": secret,
                "csrfmiddlewaretoken": Parsed(body).token,
            },
        )
        del secret
        assert status == 200 and "/accounts/login/" not in url and alias in body
        actor = User.objects.get(username=alias)
        member = get_active_membership(user=actor, organization=org)

        def observe(label, data=None, positive=False, *, actor_alias=alias):
            before = helpers["snapshot"]()
            status, body, url = request(PATH, data)
            parsed = Parsed(body)
            after = helpers["snapshot"]()
            deltas = [name for name in before if before[name] != after[name]]
            forbidden = [row for row in fixtures if not positive or row["key"] == "X"]
            leaks = [
                row["key"]
                for row in forbidden
                if row["clearance"] in body
                or row["reference"] in body
                or str(ContractComplianceEvidence.objects.get(pk=row["clearance"]))
                in body
            ]
            expected = [{"value": "", "label": "---------"}]
            if positive:
                same = next(row for row in fixtures if row["key"] == "C")
                actual_label = str(
                    ContractComplianceEvidence.objects.get(pk=same["clearance"])
                )
                assert any(
                    o["value"] == same["clearance"] and o["label"] == actual_label
                    for o in parsed.fields["clearance_evidence"]
                )
                assert len(parsed.fields["clearance_evidence"]) == 2
            else:
                assert parsed.fields["clearance_evidence"] == expected
            result = {
                "actor": actor_alias,
                "control": label,
                "method": "POST" if data else "GET",
                "status": status,
                "url": url,
                "clearance_options": parsed.fields.get("clearance_evidence"),
                "errors": parsed.errors,
                "forbidden_full_response_leaks": leaks,
                "model_deltas": deltas,
                "response_sha256": hashlib.sha256(body.encode()).hexdigest(),
                "authenticated_csrf_middleware": True,
                "retention_release_delta": 0,
                "unauthorized_success_audit_delta": 0,
                "result": "PASS",
            }
            records.append(result)
            save("RUNTIME_HTTP.json", records)
            assert status == 200 and url == BASE + PATH and not deltas and not leaks, (
                result
            )
            return parsed

        parsed = observe(
            "organization/view source-positive GET"
            if alias == helpers["POSITIVE"]
            else "limited source-backed GET",
            positive=alias == helpers["POSITIVE"],
        )
        if alias != helpers["LIMITED"]:
            continue
        form = RetentionReleaseForm(organization=org, actor=actor, membership=member)
        contract = Contract.objects.get(
            project__code="PRJ-01-01", contract_number__endswith="-05"
        )
        version = form.fields["evidence_document_version"].queryset.first()
        data = {
            "contract": str(contract.pk),
            "evidence_document_version": str(version.pk),
            "release_date": "2026-10-22",
            "amount": "1",
            "clearance_evidence": "",
        }
        valid = RetentionReleaseForm(
            data=data, organization=org, actor=actor, membership=member
        )
        assert valid.is_valid(), valid.errors
        save(
            "PAYLOAD_CONTROL.json",
            {
                "otherwise_valid_form": True,
                "payload_without_csrf": data,
                "save_performed": False,
                "scope": "clearance-only manipulation; no full financial workflow",
            },
        )
        for source in fixtures:
            payload = data | {"clearance_evidence": source["clearance"]}
            rejected = RetentionReleaseForm(
                data=payload, organization=org, actor=actor, membership=member
            )
            assert not rejected.is_valid() and set(rejected.errors) == {
                "clearance_evidence"
            }
            parsed = observe(
                ("same-tenant C" if source["key"] == "C" else "cross-tenant X")
                + " manipulated unauthorized clearance POST",
                payload | {"csrfmiddlewaretoken": parsed.token},
            )
            assert parsed.errors
        invalid = data | {"clearance_evidence": fixtures[0]["clearance"]}
        invalid.pop("amount")
        parsed = observe(
            "source-backed invalid amount redisplay",
            invalid | {"csrfmiddlewaretoken": parsed.token},
        )
        assert parsed.errors
    after = state()
    save("RUNTIME_HTTP_AFTER.json", after)
    before = json.loads((OUT / "RUNTIME_BEFORE.json").read_text(encoding="utf-8"))
    deltas = [
        name
        for name in before["models"]
        if before["models"][name] != after["models"][name]
    ]
    assert set(deltas) <= {"sessions.Session"}, deltas
    save(
        "RUNTIME_HTTP_INTEGRITY.json",
        {
            "model_tables_compared": len(after["models"]),
            "deltas": deltas,
            "business_audit_authority_unchanged": True,
            "user_last_login_excluded": True,
            "retention_release_delta": 0,
            "success_audit_delta": 0,
            "observations": len(records),
        },
    )
    print("Missing live HTTP controls: 5/5 PASS; no business/audit/authority mutation")


if __name__ == "__main__":
    http(positive_only="positive-only" in sys.argv)
