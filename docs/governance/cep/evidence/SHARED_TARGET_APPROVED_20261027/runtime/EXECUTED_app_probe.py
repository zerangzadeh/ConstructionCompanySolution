"""Executed inside the approved Linux application runtime, not Production."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import socket
import sys
import traceback
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, "/app")
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.production"

import django

django.setup()

import psycopg
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection, connections
from django.db.migrations.loader import MigrationLoader
from django.urls import reverse

from scripts.cep070_erp_recovery_proof import fingerprint

OUT = Path("/evidence")
STATE = Path("/state")


def stamp():
    return datetime.now(UTC).isoformat()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def db_options():
    db = settings.DATABASES["default"]
    assert db["NAME"].startswith("pe_") and db["HOST"] == "db"
    result = dict(db["OPTIONS"])
    result.update(
        host=db["HOST"],
        port=db["PORT"],
        user=db["USER"],
        password=db["PASSWORD"],
        options="-c timezone=UTC",
    )
    assert result["sslmode"] == "verify-full"
    return result


def schema_identity():
    with connection.cursor() as cursor:
        cursor.execute("SELECT app,name FROM django_migrations ORDER BY app,name")
        rows = cursor.fetchall()
    assert set(rows) == set(MigrationLoader(None).graph.nodes)
    return {
        "nodes": len(rows),
        "sha256": hashlib.sha256(json.dumps(rows).encode()).hexdigest(),
    }


def full_fingerprint():
    value = fingerprint(db_options(), settings.DATABASES["default"]["NAME"])
    # Hash/compare every definition in the existing engine-normalized method;
    # retain compact evidence rather than 9,507 repeated SQL definitions.
    value.pop("constraint_definitions")
    return value


def identities():
    from apps.accounts.models import User
    from apps.documents.models import Document
    from apps.organizations.models import Organization

    result = []
    for username, slug in [
        ("document-owner", "document-company"),
        ("other-document-user", "other-document-company"),
    ]:
        actor = User.objects.get(username=username)
        organization = Organization.objects.get(slug=slug)
        document = (
            Document.objects.filter(organization=organization)
            .order_by("created_at")
            .first()
        )
        assert document is not None
        result.append((actor, organization, document))
    return result


def run(action, phase):
    assert settings.SETTINGS_MODULE == "config.settings.production"
    assert not settings.DEBUG and not settings.REFERENCE_PERSONA_CATALOGUE_ENABLED
    assert platform.python_version() == "3.11.17"
    assert psycopg.pq.__impl__ == "python"
    db_options()
    if action == "identity":
        freeze = json.loads(Path("/app/SOURCE_FREEZE.json").read_text())
        assert all(digest(Path("/app") / path) == want for path, want in freeze.items())
        assert not Path("/app/.env").exists() and "dotenv" not in sys.modules
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_user,version()")
            user, version = cursor.fetchone()
            assert "PostgreSQL 18.6" in version
            cursor.execute(
                "SELECT ssl,version,cipher FROM pg_stat_ssl WHERE pid=pg_backend_pid()"
            )
            tls = cursor.fetchone()
            assert tls[0]
            cursor.execute(
                "SELECT rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=current_user"
            )
            assert cursor.fetchone() == (False, False, False)
        call_command("check", deploy=True, fail_level="WARNING")
        info = {
            "at": stamp(),
            "os_release": Path("/etc/os-release").read_text(),
            "python": platform.python_version(),
            "django": django.get_version(),
            "psycopg": psycopg.__version__,
            "pq_impl": psycopg.pq.__impl__,
            "libpq": psycopg.pq.version(),
            "postgresql": version,
            "db_tls": {"version": tls[1], "cipher": tls[2]},
            "role": user,
            "role_not_superuser": True,
            "settings": settings.SETTINGS_MODULE,
            "dotenv_loaded": False,
            "debug": False,
            "personas": False,
            "source_files": len(freeze),
            "schema": schema_identity(),
            "production_authorized": False,
        }
        write(OUT / (phase + "_IDENTITY.json"), info)
    elif action == "collectstatic":
        call_command("collectstatic", interactive=False, verbosity=0)
        assets = {
            p.relative_to(settings.STATIC_ROOT).as_posix(): digest(p)
            for p in Path(settings.STATIC_ROOT).rglob("*")
            if p.is_file()
        }
        assert len(assets) >= 153
        write(OUT / (phase + "_STATIC.json"), assets)
    elif action == "fresh-write":
        from apps.accounts.models import User
        from apps.documents.services import (
            add_document_version,
            record_document_processing_assessment,
        )

        actor, organization, document = identities()[0]
        before = document.versions.count()
        upload = SimpleUploadedFile(
            "target-" + phase + ".pdf",
            b"%PDF-1.7\nBONIRA approved Linux " + phase.encode(),
            content_type="application/pdf",
        )
        add_document_version(document=document, actor=actor, upload=upload)
        document.refresh_from_db()
        version = document.current_version
        record_document_processing_assessment(
            version=version,
            actor=User.objects.get(username="recovery-fixture-operator"),
            verdict="clean",
            adapter_code="synthetic-approved-linux-fixture",
        )
        assert document.versions.count() == before + 1
        write(
            STATE / "configuration_metadata" / "fresh-write.json",
            {
                "profile": "BONIRA-PE-NP-01",
                "phase": phase,
                "acknowledged_at": stamp(),
                "version_sha256": version.sha256,
                "version": str(version.pk),
                "source_head": os.environ["BONIRA_SOURCE_HEAD"],
                "secret_bytes": "NOT_CAPTURED",
            },
        )
        with (STATE / "audit_operational" / "qualification.jsonl").open("a") as handle:
            handle.write(
                json.dumps(
                    {
                        "at": stamp(),
                        "event": "synthetic.version.acknowledged",
                        "phase": phase,
                    }
                )
                + "\n"
            )
    elif action == "fingerprint":
        value = full_fingerprint()
        write(OUT / (phase + "_FINGERPRINT.json"), value)
        print(
            json.dumps(
                {
                    "tables": len(value["tables"]),
                    "rows": sum(t["rows"] for t in value["tables"].values()),
                    "constraints": value["constraints_count"],
                }
            )
        )
    elif action == "validate":
        from apps.documents.models import DocumentVersion
        from apps.documents.services import (
            add_document_version,
            get_document_version_for_download,
            get_organization_document,
        )
        from apps.projects.models import Project

        before = full_fingerprint()
        files_before = {
            p.relative_to(STATE / "document_media").as_posix(): digest(p)
            for p in (STATE / "document_media").rglob("*") if p.is_file()
        }
        checks = []

        def check(name, condition):
            checks.append({"check": name, "status": "PASS" if condition else "FAIL"})
            assert condition, name

        people = identities()
        for actor, organization, document in people:
            selected = get_organization_document(
                user=actor, organization=organization, document_id=str(document.pk)
            )
            check("restored tenant authorized document", selected.pk == document.pk)
            for version in document.versions.all():
                selected_version = get_document_version_for_download(
                    document=document, version_id=str(version.pk), actor=actor
                )
                with selected_version.file.open("rb") as handle:
                    check(
                        "restored immutable version bytes",
                        hashlib.sha256(handle.read()).hexdigest() == version.sha256,
                    )
            other = next(p for p in people if p[1].pk != organization.pk)
            for attempted_org in [organization, other[1]]:
                try:
                    get_organization_document(
                        user=actor,
                        organization=attempted_org,
                        document_id=str(other[2].pk),
                    )
                except PermissionDenied:
                    check("cross-tenant read denied", True)
                else:
                    check("cross-tenant read denied", False)
            try:
                add_document_version(
                    document=other[2],
                    actor=actor,
                    upload=SimpleUploadedFile(
                        "denied.pdf",
                        b"%PDF-1.7\nDenied",
                        content_type="application/pdf",
                    ),
                )
            except PermissionDenied:
                check("cross-tenant version write denied", True)
            else:
                check("cross-tenant version write denied", False)
        project = Project.objects.get(organization=people[1][1], code="RECOVERY-B")
        check(
            "exact Decimal project values",
            project.estimated_budget == Decimal("123456.78")
            and project.actual_budget == Decimal("123.45"),
        )
        marker = json.loads(
            (STATE / "configuration_metadata" / "fresh-write.json").read_text()
        )
        check(
            "latest acknowledged synthetic write recovered",
            DocumentVersion.objects.filter(
                pk=marker["version"], sha256=marker["version_sha256"]
            ).exists(),
        )
        check(
            "validation and denied writes preserve complete state",
            before == full_fingerprint(),
        )
        check("denied writes preserve protected filesystem", files_before == {
            p.relative_to(STATE / "document_media").as_posix(): digest(p)
            for p in (STATE / "document_media").rglob("*") if p.is_file()
        })
        write(
            OUT / (phase + "_VALIDATION.json"),
            {
                "at": stamp(),
                "result": "PASS",
                "checks": checks,
                "schema": schema_identity(),
                "versions": DocumentVersion.objects.count(),
                "scope": "EXECUTED_APPROVED_NONPRODUCTION_ERP_FIXTURE_ONLY",
            },
        )
    elif action == "http-fixture":
        first, other = identities()
        write(
            STATE / "http-fixture.json",
            {
                "own": reverse(
                    "documents:version-download",
                    args=[first[2].pk, first[2].current_version_id],
                ),
                "other": reverse(
                    "documents:version-download",
                    args=[other[2].pk, other[2].current_version_id],
                ),
                "own_sha256": first[2].current_version.sha256,
            },
        )
    elif action == "cache-write":
        from django.core.cache import cache

        cache.set("approved-target-proof", "shared-across-processes", 300)
    elif action == "cache-read":
        from django.core.cache import cache

        assert cache.get("approved-target-proof") == "shared-across-processes"
    elif action == "tls-negative":
        cases = []
        original = db_options()
        for name, overrides in [
            ("non-TLS PostgreSQL rejected", {"sslmode": "disable"}),
            (
                "untrusted CA rejected",
                {"sslrootcert": "/etc/ssl/certs/ca-certificates.crt"},
            ),
            (
                "wrong hostname rejected",
                {"host": "untrusted.invalid", "hostaddr": socket.gethostbyname("db")},
            ),
            ("wrong password rejected", {"password": "wrong-synthetic-password"}),
        ]:
            try:
                with psycopg.connect(
                    **(original | overrides),
                    dbname=settings.DATABASES["default"]["NAME"],
                ):
                    pass
            except psycopg.OperationalError:
                cases.append({"check": name, "status": "PASS"})
            else:
                raise AssertionError(name)
        write(
            OUT / (phase + "_TLS_NEGATIVE.json"),
            {"at": stamp(), "checks": cases, "result": "PASS"},
        )
    elif action == "history":
        write(OUT / (phase + "_HISTORY.json"), schema_identity())
    else:
        raise ValueError("Unknown bounded probe")
    connections.close_all()


if __name__ == "__main__":
    action, phase = sys.argv[1:3]
    try:
        run(action, phase)
    except Exception as exc:  # noqa: BLE001 -- retain sanitized failed-attempt evidence
        frames = [
            {"file": Path(f.filename).name, "line": f.lineno, "function": f.name}
            for f in traceback.extract_tb(exc.__traceback__)[-8:]
        ]
        write(
            OUT
            / (
                phase
                + "_"
                + action
                + "_FAILED_"
                + datetime.now(UTC).strftime("%H%M%S")
                + ".json"
            ),
            {
                "at": stamp(),
                "result": "FAILED",
                "type": type(exc).__name__,
                "frames": frames,
            },
        )
        raise RuntimeError(
            "Bounded Linux probe failed; inspect retained private diagnostics and sanitized evidence"
        ) from None
