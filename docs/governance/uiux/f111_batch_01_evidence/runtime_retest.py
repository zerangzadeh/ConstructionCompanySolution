"""Fresh Development Batch-01 observations; no persistent fixture preparation."""

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

ROOT = Path(__file__).resolve().parents[4]
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
from apps.billing.forms import (
    ComplianceEvidenceForm,
    GuaranteeForm,
    RetentionReleaseForm,
)
from apps.contracts.models import Contract
from apps.documents.models import Document, DocumentVersion
from apps.documents.services import (
    _validate_target_access,
    get_organization_document,
    get_organization_documents,
    typed_links_for_document,
)
from apps.organizations.authorization import (
    effective_role_assignments,
    effective_scope_grants,
    get_active_membership,
    has_business_permission,
)
from apps.organizations.models import Organization

OUT = Path(__file__).parent
BASE = "http://127.0.0.1:8003"
ALIAS = "uiux.persona.project-manager"
assert settings.SETTINGS_MODULE == "config.settings.development"
assert connection.vendor == "postgresql"
assert connection.settings_dict["HOST"] in ("localhost", "127.0.0.1", "::1")
with connection.cursor() as cursor:
    cursor.execute("SET default_transaction_read_only = on")


def save(name, data):
    (OUT / name).write_text(
        json.dumps(data, ensure_ascii=False, default=str, indent=2), encoding="utf-8"
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


def ground():
    user = User.objects.get(username=ALIAS)
    org = Organization.objects.get(slug="demo-construction-01")
    member = get_active_membership(user=user, organization=org)
    capabilities = [
        "guarantees.manage",
        "compliance_evidence.manage",
        "retention_releases.create",
        "documents.view",
    ]
    authority = {
        "actor": ALIAS,
        "staff": user.is_staff,
        "superuser": user.is_superuser,
        "organization": org.slug,
        "membership": str(member.pk),
        "roles": list(
            effective_role_assignments(member).values_list("role__code", flat=True)
        ),
        "grants": list(
            effective_scope_grants(member).values(
                "id", "scope_type", "project_id", "site_id", "starts_at", "ends_at"
            )
        ),
        "capabilities": {
            p: has_business_permission(
                user=user, organization=org, permission=p, allow_any_scope=True
            )
            for p in capabilities
        },
    }
    assert not user.is_staff and not user.is_superuser
    assert all(authority["capabilities"].values())
    objects = {"contracts": {}, "versions": {}, "document_contexts": []}
    for key, project_code in zip(
        "ABCDX",
        ["PRJ-01-01", "PRJ-01-02", "PRJ-01-03", "PRJ-01-04", "PRJ-02-01"],
        strict=True,
    ):
        contract = Contract.objects.get(
            project__code=project_code,
            contract_number__endswith="-05",
            status="active",
            party__isnull=False,
        )
        document = Document.objects.get(
            organization=contract.organization,
            document_number="DOC-000001"
            if key in "AX"
            else {"B": "DOC-000003", "C": "DOC-000005", "D": "DOC-000007"}[key],
        )
        objects["contracts"][key] = {
            "id": str(contract.pk),
            "number": contract.contract_number,
            "title": contract.title,
        }
        objects["versions"][key] = {
            "id": str(document.current_version_id),
            "document": str(document.pk),
            "title": document.title,
        }
    mixed = []
    for document in Document.objects.filter(organization=org):
        allowed = []
        for link in typed_links_for_document(document):
            try:
                _validate_target_access(
                    actor=user, organization=org, target=link.target
                )
                allowed.append(True)
            except PermissionDenied:
                allowed.append(False)
        if any(allowed) and not all(allowed):
            mixed.append(str(document.pk))
        objects["document_contexts"].append(
            {"document": str(document.pk), "link_authorized": allowed}
        )
    objects["mixed_context_documents"] = mixed
    expected_documents = []
    for pk in get_organization_documents(user=user, organization=org).values_list(
        "pk", flat=True
    ):
        try:
            get_organization_document(user=user, organization=org, document_id=str(pk))
            expected_documents.append(pk)
        except PermissionDenied:
            continue
    objects["expected_version_ids"] = [
        str(pk)
        for pk in DocumentVersion.objects.filter(
            document_id__in=expected_documents
        ).values_list("pk", flat=True)
    ]
    return user, org, member, authority, objects


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


def http_retest():
    user, org, member, authority, objects = ground()
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    records = []

    def request(path, data=None):
        req = Request(
            BASE + path,
            data=None if data is None else urlencode(data).encode(),
            headers={"Referer": BASE + path},
        )
        try:
            response = opener.open(req, timeout=60)
        except HTTPError as exc:
            response = exc
        return response.status, response.read().decode("utf-8"), response.geturl()

    _, body, _ = request("/accounts/login/")
    command = "$c=Import-Clixml -LiteralPath ($env:LOCALAPPDATA+'/BONIRA/UIUXRuntimeAudit/credentials/uiux.persona.project-manager.clixml'); $c.GetNetworkCredential().Password"
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
            "username": ALIAS,
            "password": secret,
            "csrfmiddlewaretoken": Parsed(body).token,
        },
    )
    del secret
    assert status == 200 and "/accounts/login/" not in url and ALIAS in body

    def business_state():
        return {
            label: digest(list(apps.get_model(label).objects.order_by("pk").values()))
            for label in [
                "billing.ContractGuarantee",
                "billing.ContractComplianceEvidence",
                "billing.RetentionRelease",
                "audit.AuditEvent",
            ]
        }

    forbidden_contracts = list(
        Contract.objects.filter(
            project__code__in=["PRJ-01-03", "PRJ-01-04", "PRJ-02-01"]
        ).values_list("pk", "contract_number")
    )
    forbidden_versions = list(
        DocumentVersion.objects.filter(
            document__organization__slug="demo-construction-02"
        ).values_list("pk", flat=True)
    )
    forbidden_versions += [objects["versions"][key]["id"] for key in "CD"]

    def observe(label, path, data=None):
        before = business_state()
        status, body, _ = request(path, data)
        parsed = Parsed(body)
        matches = [
            str(token)
            for pair in forbidden_contracts
            for token in pair
            if str(token) in body
        ]
        matches += [str(pk) for pk in forbidden_versions if str(pk) in body]
        after = business_state()
        record = {
            "label": label,
            "path": path,
            "method": "POST" if data else "GET",
            "status": status,
            "options": {
                k: v
                for k, v in parsed.fields.items()
                if k in ("contract", "document_version", "evidence_document_version")
            },
            "errors": parsed.errors,
            "forbidden_metadata_matches": matches,
            "business_unchanged": before == after,
            "business_before": before,
            "business_after": after,
            "response_sha256": hashlib.sha256(body.encode()).hexdigest(),
        }
        records.append(record)
        save("RUNTIME_HTTP.json", records)
        assert status == 200 and not matches and before == after, label
        return parsed, record

    for surface, path, form_class, field in [
        (
            "guarantee",
            "/billing/guarantees/new/",
            GuaranteeForm,
            "evidence_document_version",
        ),
        (
            "compliance",
            "/billing/compliance-evidence/new/",
            ComplianceEvidenceForm,
            "document_version",
        ),
        (
            "retention",
            "/billing/retention-releases/new/",
            RetentionReleaseForm,
            "evidence_document_version",
        ),
    ]:
        parsed, record = observe(surface + " GET", path)
        assert {v["value"] for v in parsed.fields[field] if v["value"]} == set(
            objects["expected_version_ids"]
        )
        assert all(
            objects["contracts"][key]["id"]
            in {v["value"] for v in parsed.fields["contract"]}
            for key in "AB"
        )
        data = {
            "contract": objects["contracts"]["A"]["id"],
            field: objects["versions"]["A"]["id"],
        }
        if surface == "guarantee":
            data |= {
                "guarantee_type": "performance",
                "exposure_side": "received",
                "instrument_reference": "B01-RUNTIME-REJECT",
                "issuer_name": "Runtime control",
                "amount": "1",
                "issued_on": "2026-10-01",
                "effective_from": "2026-10-01",
                "expiry_kind": "dated",
                "expires_on": "2027-10-01",
                "reason": "Bounded security negative",
            }
        elif surface == "compliance":
            data |= {
                "evidence_kind": "clearance",
                "reference": "B01-RUNTIME-REJECT",
                "issuing_authority": "Runtime control",
                "effective_from": "2026-10-01",
                "expiry_kind": "dated",
                "expires_on": "2027-10-01",
                "reason": "Bounded security negative",
            }
        else:
            data |= {"release_date": "2026-10-22", "amount": "1"}
        valid = form_class(data=data, organization=org, membership=member, actor=user)
        assert valid.is_valid(), (surface, valid.errors.as_json())
        record["otherwise_valid_payload_checked_without_save"] = True
        for key in "CDX":
            parsed, record = observe(
                surface + " forbidden Contract " + key,
                path,
                data
                | {
                    "contract": objects["contracts"][key]["id"],
                    "csrfmiddlewaretoken": parsed.token,
                },
            )
            assert parsed.errors, surface
            parsed, record = observe(
                surface + " forbidden Version " + key,
                path,
                data
                | {
                    field: objects["versions"][key]["id"],
                    "csrfmiddlewaretoken": parsed.token,
                },
            )
            assert parsed.errors, surface
        invalid = data.copy()
        invalid.pop("reason" if surface != "retention" else "amount")
        parsed, record = observe(
            surface + " invalid redisplay",
            path,
            invalid | {"csrfmiddlewaretoken": parsed.token},
        )
        assert parsed.errors
    save("RUNTIME_HTTP.json", records)
    save(
        "RUNTIME_RESULT.json",
        {
            "observations": len(records),
            "all_available_controls": "PASS",
            "mixed_link_runtime": "PENDING_NO_EXISTING_QUALIFYING_DOCUMENT",
            "authority": authority,
        },
    )
    print(
        "Available runtime HTTP controls PASS:",
        len(records),
        "; mixed-link runtime remains pending",
    )


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "before":
        _, _, _, authority, objects = ground()
        executor = MigrationExecutor(connection)
        pending = len(executor.migration_plan(executor.loader.graph.leaf_nodes()))
        save(
            "RUNTIME_BEFORE.json",
            {
                "at": timezone.now(),
                "authority": authority,
                "objects": objects,
                "models": snapshot(),
                "settings": settings.SETTINGS_MODULE,
                "database": connection.settings_dict["NAME"],
                "engine": connection.vendor,
                "pending_migrations": pending,
            },
        )
        print(
            "Read-only runtime baseline recorded; pending migrations:",
            pending,
            "; mixed-context documents:",
            len(objects["mixed_context_documents"]),
        )
    elif mode == "http":
        http_retest()
    elif mode == "after":
        _, _, _, authority, objects = ground()
        before = json.loads((OUT / "RUNTIME_BEFORE.json").read_text(encoding="utf-8"))
        models = snapshot()
        deltas = {
            k: {"before": v, "after": models[k]}
            for k, v in before["models"].items()
            if v != models[k]
        }
        save(
            "RUNTIME_AFTER.json",
            {
                "at": timezone.now(),
                "models": models,
                "deltas": deltas,
                "authority_unchanged": json.loads(json.dumps(authority, default=str))
                == before["authority"],
                "objects_unchanged": json.loads(json.dumps(objects, default=str))
                == before["objects"],
            },
        )
        print("Runtime model deltas:", list(deltas))
