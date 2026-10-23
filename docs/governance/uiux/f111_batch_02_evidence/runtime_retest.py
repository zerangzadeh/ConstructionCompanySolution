"""BATCH-02 Development observations; no fixtures or authority writes."""

import hashlib
import json
import os
import subprocess
import sys
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
from django.apps import apps
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from apps.accounts.models import User
from apps.billing.commercial_services import get_compliance_evidence
from apps.billing.forms import RetentionReleaseForm
from apps.billing.models import ContractComplianceEvidence
from apps.contracts.models import Contract
from apps.organizations.authorization import (
    effective_role_assignments,
    effective_scope_grants,
    get_active_membership,
    has_business_permission,
)
from apps.organizations.models import Organization

BASE = "http://127.0.0.1:8004"
PATH = "/billing/retention-releases/new/"
LIMITED = "uiux.persona.project-manager"
POSITIVE = "uiux.persona.tenant-admin"
assert settings.SETTINGS_MODULE == "config.settings.development"
assert connection.vendor == "postgresql"
assert connection.settings_dict["HOST"] in ("localhost", "127.0.0.1", "::1")
with connection.cursor() as cursor:
    cursor.execute("SET default_transaction_read_only = on")


def save(name, data):
    (OUT / name).write_text(
        json.dumps(data, ensure_ascii=False, default=str, indent=2) + "\n",
        encoding="utf-8",
    )


def digest(value):
    return hashlib.sha256(
        json.dumps(value, default=str, sort_keys=True).encode()
    ).hexdigest()


def snapshot():
    result = {}
    for model in apps.get_models():
        fields = [f.attname for f in model._meta.concrete_fields]
        if model._meta.label == "accounts.User":
            fields.remove("last_login")
        rows = list(model._base_manager.order_by("pk").values_list(*fields))
        result[model._meta.label] = {"count": len(rows), "sha256": digest(rows)}
    return result


def preflight():
    org = Organization.objects.get(slug="demo-construction-01")
    authority = []
    for alias in (LIMITED, POSITIVE):
        user = User.objects.get(username=alias)
        membership = get_active_membership(user=user, organization=org)
        try:
            count = get_compliance_evidence(actor=user, organization=org).count()
        except PermissionDenied:
            count = "DENIED"
        authority.append(
            {
                "actor": alias,
                "staff": user.is_staff,
                "superuser": user.is_superuser,
                "membership": membership.pk,
                "roles": list(
                    effective_role_assignments(membership).values_list(
                        "role__code", flat=True
                    )
                ),
                "grants": list(
                    effective_scope_grants(membership).values(
                        "scope_type", "project__code", "starts_at", "ends_at"
                    )
                ),
                "permissions": {
                    permission: has_business_permission(
                        user=user,
                        organization=org,
                        permission=permission,
                        allow_any_scope=True,
                    )
                    for permission in (
                        "retention_releases.create",
                        "compliance_evidence.view",
                    )
                },
                "canonical_reader": count,
            }
        )
        assert not user.is_staff and not user.is_superuser
        assert all(authority[-1]["permissions"].values())
    assert authority[0]["canonical_reader"] == "DENIED"
    all_evidence = ContractComplianceEvidence.objects.count()
    qualifying = list(
        ContractComplianceEvidence.objects.filter(
            evidence_kind="clearance", status="approved"
        ).values(
            "id", "reference", "organization__slug", "project__code", "contract_id"
        )
    )
    executor = MigrationExecutor(connection)
    pending = len(executor.migration_plan(executor.loader.graph.leaf_nodes()))
    assert pending == 0
    return {
        "at": timezone.now(),
        "authority": authority,
        "all_evidence_count": all_evidence,
        "qualifying_clearances": qualifying,
        "settings": settings.SETTINGS_MODULE,
        "database": connection.settings_dict["NAME"],
        "database_host": "loopback",
        "pending_migrations": pending,
        "fixture_preparation": "NOT_AUTHORIZED_NOT_PERFORMED",
        "runtime_positive": "PENDING_NO_QUALIFYING_SOURCE"
        if not qualifying
        else "READY",
        "runtime_same_and_cross_tenant_negatives": "PENDING_NO_QUALIFYING_SOURCES"
        if not qualifying
        else "REQUIRES_SOURCE_REVIEW",
    }


class Parsed(HTMLParser):
    def __init__(self, body):
        super().__init__(convert_charrefs=True)
        self.fields, self.current, self.option, self.token = {}, None, None, None
        self.errors, self.error_depth = [], 0
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("name") == "csrfmiddlewaretoken":
            self.token = attrs.get("value")
        if tag == "select":
            self.current = attrs.get("name")
            self.fields[self.current] = []
        if tag == "option" and self.current:
            self.option = {"value": attrs.get("value", ""), "label": ""}
            self.fields[self.current].append(self.option)
        if tag == "p" and "text-red-700" in attrs.get("class", ""):
            self.error_depth += 1

    def handle_endtag(self, tag):
        if tag == "select":
            self.current = None
        if tag == "option":
            self.option = None
        if tag == "p" and self.error_depth:
            self.error_depth -= 1

    def handle_data(self, data):
        if self.option is not None:
            self.option["label"] += data
        if self.error_depth and data.strip():
            self.errors.append(data.strip())


def http():
    records = []
    for alias in (LIMITED, POSITIVE):
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

        status, body, _ = request("/accounts/login/")
        # Existing user-protected credentials remain transient; never log the result.
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

        def observe(label, data=None, *, actor_alias=alias):
            before = snapshot()
            status, body, url = request(PATH, data)
            parsed = Parsed(body)
            after = snapshot()
            deltas = [name for name in before if before[name] != after[name]]
            record = {
                "actor": actor_alias,
                "label": label,
                "path": PATH,
                "method": "POST" if data else "GET",
                "status": status,
                "clearance_options": parsed.fields.get("clearance_evidence"),
                "errors": parsed.errors,
                "model_deltas": deltas,
                "response_sha256": hashlib.sha256(body.encode()).hexdigest(),
                "authenticated_csrf_middleware": True,
                "claim": "AVAILABLE_CONTROL_ONLY_NO_QUALIFYING_CLEARANCE",
            }
            records.append(record)
            save("RUNTIME_HTTP.json", records)
            assert status == 200 and url == BASE + PATH and not deltas
            assert parsed.fields["clearance_evidence"] == [
                {"value": "", "label": "---------"}
            ]
            return parsed

        parsed = observe(
            "limited GET"
            if alias == LIMITED
            else "organization/view GET without source; positive PENDING"
        )
        if alias == LIMITED:
            org = Organization.objects.get(slug="demo-construction-01")
            actor = User.objects.get(username=alias)
            member = get_active_membership(user=actor, organization=org)
            form = RetentionReleaseForm(
                organization=org, actor=actor, membership=member
            )
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
            assert valid.is_valid()
            invalid = data.copy()
            invalid.pop("amount")
            parsed = observe(
                "limited missing amount redisplay",
                invalid | {"csrfmiddlewaretoken": parsed.token},
            )
            assert parsed.errors
            parsed = observe(
                "nonexistent UUID POST; supplemental only, NOT same/cross-tenant proof",
                data
                | {
                    "clearance_evidence": str(uuid4()),
                    "csrfmiddlewaretoken": parsed.token,
                },
            )
            assert parsed.errors
    print(
        "Available live controls:",
        len(records),
        "PASS; qualifying source controls PENDING",
    )


if __name__ == "__main__":
    if sys.argv[1] == "before":
        state = preflight()
        save("RUNTIME_BEFORE.json", state | {"models": snapshot()})
        print(
            "Read-only preflight: evidence records",
            state["all_evidence_count"],
            "; pending migrations",
            state["pending_migrations"],
        )
    elif sys.argv[1] == "http":
        http()
    elif sys.argv[1] == "after":
        before = json.loads((OUT / "RUNTIME_BEFORE.json").read_text(encoding="utf-8"))
        after = snapshot()
        deltas = [name for name in after if after[name] != before["models"][name]]
        assert set(deltas) <= {"sessions.Session"}, deltas
        save(
            "RUNTIME_INTEGRITY.json",
            {
                "models_compared": len(after),
                "deltas": deltas,
                "user_last_login_excluded": True,
                "business_audit_authority_unchanged": True,
                "preflight": preflight(),
            },
        )
        print("Runtime integrity PASS; only authentication/session bookkeeping allowed")
