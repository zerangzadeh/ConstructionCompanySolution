"""Authorized Development-only F-121 runtime closure; no product changes."""

import hashlib
import json
import runpy
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent
PRIOR = ROOT / "docs/governance/uiux/f111_batch_01_evidence"
context = runpy.run_path(str(PRIOR / "runtime_retest.py"), run_name="closure_helpers")
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.documents.models import Document, DocumentType
from apps.documents.services import (
    _validate_target_access,
    add_document_link,
    create_document,
    get_organization_document,
    get_organization_documents,
    typed_links_for_document,
)
from apps.organizations.authorization import get_active_membership
from apps.projects.models import Project

MARKER = "BATCH_01_RUNTIME_CLOSURE_FIXTURE"
assert settings.SETTINGS_MODULE == "config.settings.development"
assert connection.settings_dict["NAME"] == "construction_erp"
assert connection.settings_dict["HOST"] in ("localhost", "127.0.0.1", "::1")
ENTRY = json.loads((OUT / "ENTRY.json").read_text(encoding="utf-8"))
for name, expected in ENTRY["source_hashes"].items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected


def save(name, data):
    (OUT / name).write_text(
        json.dumps(data, ensure_ascii=False, default=str, indent=2), encoding="utf-8"
    )


def state():
    return context["snapshot"]()


def authority():
    actor, org, member, current, objects = context["ground"]()
    assert json.loads(json.dumps(current, default=str)) == ENTRY["authority"]
    return actor, org, member, objects


def form_classes():
    return (
        (
            "guarantee",
            context["GuaranteeForm"],
            "evidence_document_version",
            "/billing/guarantees/new/",
        ),
        (
            "compliance",
            context["ComplianceEvidenceForm"],
            "document_version",
            "/billing/compliance-evidence/new/",
        ),
        (
            "retention",
            context["RetentionReleaseForm"],
            "evidence_document_version",
            "/billing/retention-releases/new/",
        ),
    )


def selection_visibility(actor, org, document):
    member = get_active_membership(user=actor, organization=org)
    return {
        name: form(organization=org, actor=actor, membership=member)
        .fields[field]
        .queryset.filter(pk=document.current_version_id)
        .exists()
        for name, form, field, _ in form_classes()
    }


def synthetic_pdf():
    # One blank page with an explicit synthetic marker; no business content.
    stream = b"BT /F1 10 Tf 30 100 Td (BATCH_01_RUNTIME_CLOSURE_FIXTURE - synthetic only) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 200] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length "
        + str(len(stream)).encode()
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    content = b"%PDF-1.4\n"
    offsets = [0]
    for number, value in enumerate(objects, 1):
        offsets.append(len(content))
        content += f"{number} 0 obj\n".encode() + value + b"\nendobj\n"
    start = len(content)
    content += b"xref\n0 6\n0000000000 65535 f \n"
    content += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    return (
        content
        + f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()
    )


def fixture():
    limited, org, _, objects = authority()
    pending = MigrationExecutor(connection)
    assert not pending.migration_plan(pending.loader.graph.leaf_nodes())
    candidates = objects["mixed_context_documents"]
    before = state()
    writer = User.objects.get(username="account.demo-construction-01.owner")
    assert writer.username in ENTRY["existing_eligible_fixture_writers"]
    if candidates:
        document = Document.objects.get(organization=org, pk=candidates[0])
        mode, single = "REUSED_EXISTING", None
    else:
        assert not Document.objects.filter(organization=org, reference=MARKER).exists()
        project_a = Project.objects.get(organization=org, code="PRJ-01-01")
        project_c = Project.objects.get(organization=org, code="PRJ-01-03")
        _validate_target_access(actor=limited, organization=org, target=project_a)
        try:
            _validate_target_access(actor=limited, organization=org, target=project_c)
        except PermissionDenied:
            pass
        else:
            raise AssertionError("C must be unauthorized")
        with connection.cursor() as cursor:
            cursor.execute("SET default_transaction_read_only = off")
        with transaction.atomic():
            document = create_document(
                organization=org,
                actor=writer,
                document_type=DocumentType.GENERAL,
                title=MARKER,
                reference=MARKER,
                description="Development-only synthetic F-121 mixed A/C context control; no real or sensitive content.",
                target=project_a,
                upload=SimpleUploadedFile(
                    f"{MARKER}.pdf", synthetic_pdf(), content_type="application/pdf"
                ),
                audit_metadata={"runtime_fixture": MARKER},
            )
            single = selection_visibility(limited, org, document)
            assert all(single.values()), single
            get_organization_document(
                user=limited, organization=org, document_id=str(document.pk)
            )
            add_document_link(document=document, actor=writer, target=project_c)
        with connection.cursor() as cursor:
            cursor.execute("SET default_transaction_read_only = on")
        mode = "CREATED_MINIMUM_DEVELOPMENT_FIXTURE"
    links = []
    for link in typed_links_for_document(document):
        try:
            _validate_target_access(actor=limited, organization=org, target=link.target)
            allowed = True
        except PermissionDenied:
            allowed = False
        links.append(
            {
                "target_type": link.target_type,
                "target_id": str(link.target.pk),
                "limited_actor_authorized": allowed,
            }
        )
    assert any(link["limited_actor_authorized"] for link in links)
    assert any(not link["limited_actor_authorized"] for link in links)
    list_absent = (
        not get_organization_documents(user=limited, organization=org)
        .filter(pk=document.pk)
        .exists()
    )
    assert list_absent
    try:
        get_organization_document(
            user=limited, organization=org, document_id=str(document.pk)
        )
    except PermissionDenied:
        detail_denied = True
    else:
        raise AssertionError("Mixed document detail must deny")
    limited_visible = selection_visibility(limited, org, document)
    writer_visible = selection_visibility(writer, org, document)
    assert not any(limited_visible.values()) and all(writer_visible.values())
    after = state()
    deltas = {
        name: {"before": value, "after": after[name]}
        for name, value in before.items()
        if value != after[name]
    }
    allowed = {
        "documents.Document",
        "documents.DocumentVersion",
        "documents.DocumentNumberSequence",
        "documents.DocumentLink",
        "projects.ProjectDocumentLink",
        "audit.AuditEvent",
    }
    assert set(deltas) <= allowed, list(deltas)
    audit = list(
        AuditEvent.objects.filter(entity_id=document.pk).values(
            "id", "action", "entity_type"
        )
    )
    save(
        "FIXTURE.json",
        {
            "label": MARKER,
            "mode": mode,
            "document_id": document.pk,
            "version_id": document.current_version_id,
            "writer": writer.username,
            "links": links,
            "single_authorized_context_form_visibility_before_second_link": single,
            "mixed_context_limited_form_visibility": limited_visible,
            "writer_positive_form_visibility": writer_visible,
            "canonical_list_absent": list_absent,
            "canonical_detail_denied": detail_denied,
            "synthetic_content_sha256": document.current_version.sha256,
            "file_size": document.current_version.file_size,
            "fixture_audit_events": audit,
            "processing_assessment_created": False,
            "qualification": "Same immutable version selectable on all three forms with A only and by existing organization writer with A/C; exclusion isolates linked-context authority, not file processing status.",
            "retention": "Retained as labelled Development-only runtime closure fixture; no cleanup deletion performed.",
            "model_deltas": deltas,
        },
    )
    save("POST_FIXTURE_BASELINE.json", {"models": after, "authority_unchanged": True})
    print("Mixed-context canonical controls PASS; fixture:", document.pk)


def http():
    from http.cookiejar import CookieJar
    from urllib.error import HTTPError
    from urllib.parse import urlencode
    from urllib.request import HTTPCookieProcessor, Request, build_opener

    actor, org, member, objects = authority()
    fixture_info = json.loads((OUT / "FIXTURE.json").read_text(encoding="utf-8"))
    document = Document.objects.get(pk=fixture_info["document_id"])
    parsed_class = context["Parsed"]
    base = "http://127.0.0.1:8003"
    opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def request(path, data=None):
        req = Request(
            base + path,
            data=None if data is None else urlencode(data).encode(),
            headers={"Referer": base + path},
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
            "username": actor.username,
            "password": secret,
            "csrfmiddlewaretoken": parsed_class(body).token,
        },
    )
    del secret
    assert status == 200 and "/accounts/login/" not in url and actor.username in body
    baseline = state()
    observations = []
    forbidden = [str(document.pk), str(document.current_version_id), document.title]
    from apps.contracts.models import Contract
    from apps.documents.models import DocumentVersion

    for contract in Contract.objects.filter(
        project__code__in=["PRJ-01-03", "PRJ-01-04", "PRJ-02-01"]
    ):
        forbidden.extend([str(contract.pk), contract.contract_number])
    forbidden.extend(
        str(pk)
        for pk in DocumentVersion.objects.filter(
            document__organization__slug="demo-construction-02"
        ).values_list("pk", flat=True)
    )
    forbidden.extend(objects["versions"][key]["id"] for key in "CD")
    for name, form_class, field, path in form_classes():
        status, body, _ = request(path)
        parsed = parsed_class(body)
        expected = form_class(organization=org, actor=actor, membership=member)
        options = {
            key: value
            for key, value in parsed.fields.items()
            if key in ("contract", field)
        }
        for key, choices in options.items():
            assert {item["value"] for item in choices if item["value"]} == {
                str(pk)
                for pk in expected.fields[key].queryset.values_list("pk", flat=True)
            }
        assert status == 200 and not any(value in body for value in forbidden)
        observations.append(
            {
                "surface": name,
                "method": "GET",
                "status": status,
                "options": options,
                "protected_metadata_absent": True,
            }
        )
        data = {
            "contract": objects["contracts"]["A"]["id"],
            field: objects["versions"]["A"]["id"],
        }
        if name == "guarantee":
            data |= {
                "guarantee_type": "performance",
                "exposure_side": "received",
                "instrument_reference": "B01-CLOSURE-REJECT",
                "issuer_name": "Synthetic control",
                "amount": "1",
                "issued_on": "2026-10-01",
                "effective_from": "2026-10-01",
                "expiry_kind": "dated",
                "expires_on": "2027-10-01",
                "reason": "Mixed-context negative",
            }
        elif name == "compliance":
            data |= {
                "evidence_kind": "clearance",
                "reference": "B01-CLOSURE-REJECT",
                "issuing_authority": "Synthetic control",
                "effective_from": "2026-10-01",
                "expiry_kind": "dated",
                "expires_on": "2027-10-01",
                "reason": "Mixed-context negative",
            }
        else:
            data |= {"release_date": "2026-10-22", "amount": "1"}
        valid = form_class(data=data, organization=org, actor=actor, membership=member)
        assert valid.is_valid(), valid.errors.as_json()
        data[field] = str(document.current_version_id)
        invalid = form_class(
            data=data, organization=org, actor=actor, membership=member
        )
        assert not invalid.is_valid() and field in invalid.errors
        data["csrfmiddlewaretoken"] = parsed.token
        status, body, _ = request(path, data)
        parsed = parsed_class(body)
        assert (
            status == 200
            and parsed.errors
            and not any(value in body for value in forbidden)
        )
        for key, choices in options.items():
            assert parsed.fields[key] == choices
        assert baseline == state()
        observations.append(
            {
                "surface": name,
                "method": "POST",
                "case": "mixed_version_with_authorized_contract",
                "status": status,
                "otherwise_valid_payload": True,
                "errors": parsed.errors,
                "protected_metadata_absent": True,
                "options_unchanged": True,
                "business_and_audit_unchanged": True,
            }
        )
    after = state()
    save(
        "HTTP_MIXED_LINK.json",
        {
            "observations": observations,
            "runtime_models_unchanged_after_login": baseline == after,
            "models_after": after,
            "browser_substitution": False,
        },
    )
    pre_login = json.loads((OUT / "POST_FIXTURE_BASELINE.json").read_text())["models"]
    deltas = [key for key in after if after[key] != pre_login[key]]
    assert set(deltas) <= {"sessions.Session"}, deltas
    save(
        "RUNTIME_INTEGRITY.json",
        {
            "model_deltas_after_fixture": deltas,
            "business_and_audit_unchanged": True,
            "authority_matches_accepted": True,
            "source_hashes_match_accepted": True,
        },
    )
    print("6 mixed-link live HTTP observations PASS; browser evidence remains blocked")


if __name__ == "__main__":
    if sys.argv[1] == "fixture":
        fixture()
    elif sys.argv[1] == "http":
        http()
