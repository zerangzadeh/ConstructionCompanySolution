"""Bounded Development BATCH-02 canonical unblock and missing runtime evidence."""

import hashlib
import json
import runpy
import struct
import subprocess
import sys
import zlib
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent
PRIOR = ROOT / "docs/governance/uiux/f111_batch_02_evidence"
helpers = runpy.run_path(str(PRIOR / "runtime_retest.py"), run_name="helpers")
old = runpy.run_path(
    str(
        ROOT
        / "docs/governance/uiux/f111_batch_02_runtime_closure_evidence/close_runtime.py"
    ),
    run_name="old_helpers",
)
from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.billing.commercial_services import (
    create_compliance_evidence,
    decide_compliance_evidence,
    submit_compliance_evidence,
)
from apps.billing.models import ContractComplianceEvidence
from apps.contracts.models import Contract
from apps.documents.models import DocumentProcessingAssessment, DocumentVersion
from apps.documents.services import (
    create_document,
    record_document_processing_assessment,
)
from apps.organizations.access_services import (
    assign_platform_role,
    revoke_platform_role,
)
from apps.organizations.authorization import has_platform_role
from apps.organizations.models import PlatformRoleAssignment, PlatformRoleCode

MARKER = "BATCH_02_RUNTIME_CLOSURE_FIXTURE"
OPERATOR = "account.demo-construction-03.viewer"
assert settings.SETTINGS_MODULE == "config.settings.development"
assert connection.settings_dict["NAME"] == "construction_erp"
assert connection.settings_dict["HOST"] in ("localhost", "127.0.0.1", "::1")


def save(name, value):
    (OUT / name).write_text(
        json.dumps(value, default=str, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def files():
    return {
        name: sha(ROOT / name)
        for name in git(
            "ls-files", "--cached", "--others", "--exclude-standard"
        ).splitlines()
        if (ROOT / name).is_file()
        and not name.startswith(OUT.relative_to(ROOT).as_posix() + "/")
    }


def state():
    models = helpers["snapshot"]()
    related_ids = [
        str(pk) for pk in PlatformRoleAssignment.objects.values_list("pk", flat=True)
    ]
    related_ids += [
        str(pk)
        for pk in DocumentVersion.objects.filter(
            document__reference__startswith=MARKER
        ).values_list("pk", flat=True)
    ]
    related_ids += [
        str(pk)
        for pk in ContractComplianceEvidence.objects.filter(
            reference__startswith=MARKER
        ).values_list("pk", flat=True)
    ]
    authority = {
        name: value
        for name, value in models.items()
        if name.startswith(("organizations.", "accounts."))
        and name != "organizations.PlatformRoleAssignment"
    }
    return {
        "at": timezone.now(),
        "models": models,
        "authority_fingerprint": helpers["digest"](authority),
        "authority_models": authority,
        "platform_assignments": list(
            PlatformRoleAssignment.objects.order_by("pk").values()
        ),
        "processing_assessments": list(
            DocumentProcessingAssessment.objects.order_by("pk").values()
        ),
        "document_versions": [
            {
                "id": str(v.pk),
                "document": str(v.document_id),
                "sha256": v.sha256,
                "available": v.is_available,
                "stored_file_exists": v.file.storage.exists(v.file.name),
            }
            for v in DocumentVersion.objects.order_by("pk")
        ],
        "compliance_evidence": list(
            ContractComplianceEvidence.objects.order_by("pk").values()
        ),
        "audit": list(
            AuditEvent.objects.filter(entity_id__in=related_ids)
            .order_by("created_at", "pk")
            .values()
        ),
        "effective_operations": has_platform_role(
            User.objects.get(username=OPERATOR), PlatformRoleCode.PLATFORM_OPERATIONS
        ),
        "runtime_actors": helpers["preflight"]()["authority"],
    }


def before():
    accepted = json.loads((PRIOR / "INDEX.json").read_text(encoding="utf-8"))
    assert all(sha(ROOT / name) == expected for name, expected in accepted.items())
    previous = json.loads(
        (
            ROOT
            / "docs/governance/uiux/f111_batch_02_runtime_closure_evidence/ENTRY.json"
        ).read_text(encoding="utf-8")
    )
    assert all(
        sha(ROOT / name) == expected
        for name, expected in previous["source_hashes"].items()
    )
    sources = old["inspect_sources"]()
    assert all(row["writer"] and row["approver"] for row in sources)
    assert not ContractComplianceEvidence.objects.exists()
    assert not DocumentProcessingAssessment.objects.exists()
    actors = list(
        User.objects.filter(username__in=("admin", "superuser", OPERATOR)).values(
            "id", "username", "is_active", "is_staff", "is_superuser"
        )
    )
    assert len(actors) == 3 and all(a["is_active"] for a in actors)
    assert all(a["is_superuser"] for a in actors if a["username"] != OPERATOR)
    assert not next(a for a in actors if a["username"] == OPERATOR)["is_superuser"]
    assert not PlatformRoleAssignment.objects.filter(user__username=OPERATOR).exists()
    save(
        "ENTRY.json",
        {
            "at": timezone.now(),
            "branch": git("branch", "--show-current"),
            "head": git("rev-parse", "HEAD"),
            "upstream": git("rev-parse", "@{upstream}"),
            "divergence": git(
                "rev-list", "--left-right", "--count", "HEAD...@{upstream}"
            ),
            "dirty": git("status", "--short"),
            "diff_names": git("diff", "--name-status"),
            "diff_stat": git("diff", "--stat"),
            "accepted_source_evidence_drift": [],
            "accepted_validation_repeated": False,
            "actors": actors,
            "sources": sources,
            "authority": "Human 2026-10-22 bounded BATCH-02 canonical readiness-review execution",
            "touch_set": [
                "one temporary Operations assignment plus canonical revocation",
                "two synthetic documents/versions and truthful scanner assessments",
                "two canonical clearance create/submit/independent approval histories",
                "BATCH-02 runtime HTTP/browser sessions",
                "closure evidence/report and F-122 only",
            ],
            "no_product_code_schema_or_permission_semantics_changes": True,
        },
    )
    save("FILES_BEFORE.json", files())
    save("BEFORE.json", state())
    (OUT / "REGISTER_BEFORE.txt").write_bytes(
        (ROOT / "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml").read_bytes()
    )
    (OUT / "CLOSURE_REPORT_BEFORE.txt").write_bytes(
        (
            ROOT / "docs/governance/uiux/UIUX_F111_BATCH_02_RUNTIME_CLOSURE_REPORT.md"
        ).read_bytes()
    )
    print(
        "Entry PASS; accepted source/evidence unchanged; authority and audit baseline retained"
    )


def synthetic_png():
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\0\xff\xff\xff"))
        + chunk(b"IEND", b"")
    )


def scan():
    path = OUT / (MARKER + ".png")
    path.write_bytes(synthetic_png())
    scanner = Path(
        "C:/ProgramData/Microsoft/Windows Defender/Platform/4.18.26090.9-0/MpCmdRun.exe"
    )
    result = subprocess.run(
        [
            str(scanner),
            "-Scan",
            "-ScanType",
            "3",
            "-File",
            str(path),
            "-DisableRemediation",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    record = {
        "at": timezone.now(),
        "scanner": str(scanner),
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "input_sha256": sha(path),
        "size": path.stat().st_size,
        "fixture": path.name,
        "content": "deterministic 1x1 white RGB PNG; IHDR, IDAT, IEND only; no metadata or external content",
    }
    save("SCAN.json", record)
    assert result.returncode == 0, record
    assert "no threats" in result.stdout.lower(), record
    print("Synthetic PNG scanner PASS; no threats; original bytes retained")


def provision():
    from django.core.files.uploadedfile import SimpleUploadedFile

    before_state = json.loads((OUT / "BEFORE.json").read_text(encoding="utf-8"))
    assert state()["authority_fingerprint"] == before_state["authority_fingerprint"]
    scanned = json.loads((OUT / "SCAN.json").read_text(encoding="utf-8"))
    payload = (OUT / scanned["fixture"]).read_bytes()
    assert (
        payload == synthetic_png()
        and hashlib.sha256(payload).hexdigest() == scanned["input_sha256"]
    )
    assert scanned["exit_code"] == 0 and "no threats" in scanned["stdout"].lower()
    admin, approver, operator = (
        User.objects.get(username=alias) for alias in ("admin", "superuser", OPERATOR)
    )
    with connection.cursor() as cursor:
        cursor.execute("SET default_transaction_read_only = off")
    assignment = None
    fixtures = []
    try:
        task_start = timezone.now()
        assignment = assign_platform_role(
            actor=admin,
            approver=approver,
            target=operator,
            role=PlatformRoleCode.PLATFORM_OPERATIONS,
            reason=MARKER + ": Development-only preparation",
            starts_at=task_start,
            ends_at=task_start + timedelta(hours=1),
        )
        save("ASSIGNED.json", state())
        assert has_platform_role(operator, PlatformRoleCode.PLATFORM_OPERATIONS)
        for source in json.loads((OUT / "ENTRY.json").read_text(encoding="utf-8"))[
            "sources"
        ]:
            contract = Contract.objects.select_related("organization", "project").get(
                pk=source["contract"]
            )
            writer = User.objects.get(username=source["writer"])
            independent = User.objects.get(username=source["approver"])
            assert writer.pk != independent.pk
            with transaction.atomic():
                doc = create_document(
                    organization=contract.organization,
                    actor=writer,
                    document_type="general",
                    title=MARKER + " " + source["key"] + " synthetic Development only",
                    reference=MARKER + "_" + source["key"],
                    description="Synthetic scanner-verified fixture; no statutory or real clearance validity.",
                    upload=SimpleUploadedFile(
                        MARKER + ".png", payload, content_type="image/png"
                    ),
                    target=contract.project,
                )
                version = doc.current_version
                assert not version.is_available
                with version.file.open("rb") as stored:
                    stored_bytes = stored.read()
                assert (
                    stored_bytes == payload
                    and version.sha256 == scanned["input_sha256"]
                )
                assessment = record_document_processing_assessment(
                    version=version,
                    actor=operator,
                    verdict="clean",
                    adapter_code="microsoft-defender-development-fixture",
                    adapter_version="4.18.26090.9-0",
                    provider_reference=MARKER,
                    details={
                        "scan_exit_code": 0,
                        "scan_evidence": "SCAN.json",
                        "synthetic_fixture_only": True,
                        "signature_version": "1.461.140.0",
                        "byte_sha256": scanned["input_sha256"],
                    },
                )
                assert (
                    version.is_available and assessment.input_sha256 == version.sha256
                )
                evidence = create_compliance_evidence(
                    organization=contract.organization,
                    actor=writer,
                    contract=contract,
                    evidence_kind="clearance",
                    reference=MARKER + "_" + source["key"],
                    issuing_authority="Synthetic Development fixture - no statutory validity",
                    effective_from=date(2026, 10, 22),
                    expiry_kind="dated",
                    expires_on=date(2026, 10, 23),
                    document_version=version,
                    reason=MARKER
                    + ": BATCH-02 source-positive and tenant-negative controls only",
                )
                submit_compliance_evidence(
                    organization=contract.organization, actor=writer, evidence=evidence
                )
                decide_compliance_evidence(
                    organization=contract.organization,
                    actor=independent,
                    evidence=evidence,
                    approved=True,
                    reason=MARKER
                    + ": independent synthetic Development fixture approval",
                )
                evidence.refresh_from_db()
                assert (
                    evidence.status == "approved"
                    and evidence.approved_by_id == independent.pk
                )
                fixtures.append(
                    {
                        "key": source["key"],
                        "organization": str(contract.organization_id),
                        "project": str(contract.project_id),
                        "contract": str(contract.pk),
                        "document": str(doc.pk),
                        "version": str(version.pk),
                        "assessment": str(assessment.pk),
                        "clearance": str(evidence.pk),
                        "reference": evidence.reference,
                        "writer": writer.username,
                        "approver": independent.username,
                        "available": version.is_available,
                        "sha256": version.sha256,
                    }
                )
            save(
                "FIXTURES.json",
                {"assignment": str(assignment.pk), "fixtures": fixtures},
            )
        save("PREPARED.json", state())
    finally:
        if assignment is not None:
            revoke_platform_role(
                actor=admin,
                approver=approver,
                assignment_id=assignment.pk,
                reason=MARKER
                + ": preparation ended; revoke temporary Operations duty and retain history",
            )
            assert not has_platform_role(operator, PlatformRoleCode.PLATFORM_OPERATIONS)
            save("REVOKED.json", state())
        with connection.cursor() as cursor:
            cursor.execute("SET default_transaction_read_only = on")
    print(
        "Canonical preparation PASS; two approved scanner-backed sources; Operations revoked"
    )


if __name__ == "__main__":
    {"before": before, "scan": scan, "provision": provision}[sys.argv[1]]()
