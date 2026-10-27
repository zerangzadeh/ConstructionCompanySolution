"""Isolated current-ERP recovery preparation, never CEP-074 or certification.

Only newly created loopback databases and private temporary synthetic files are
used. Existing migrations provision the fixture; migration behavior is not tested.
No configured business database is opened and no recovery objective is selected.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

import psycopg
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.db import connections
from django.test import override_settings
from psycopg import sql

from scripts.backup_bundle import BackupPlan, create_bundle, file_hash

OUT = ROOT / "docs/governance/cep/evidence/CEP-069_076_PREREQUISITES_20261026"
PG_BIN = Path(r"D:\Program Files\PostgreSQL\18\bin")
APPROVED_QUALIFICATION = os.environ.get("BONIRA_CEP070_APPROVED_QUALIFICATION") == "1"
if APPROVED_QUALIFICATION:
    OUT = ROOT / "docs/governance/cep/evidence/CEP-070_EXT0020_DEVELOPMENT_20261027"


def fingerprint(options, database):
    """Hash every complete row and retain schema/sequence equality evidence."""
    result = {"tables": {}, "sequences": {}}
    with psycopg.connect(**options, dbname=database) as conn:
        tables = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' "
            "ORDER BY tablename"
        ).fetchall()
        for (table,) in tables:
            rows = conn.execute(
                sql.SQL("SELECT row_to_json(t)::text FROM {} t").format(
                    sql.Identifier("public", table)
                )
            ).fetchall()
            data = sorted(row[0] for row in rows)
            result["tables"][table] = {
                "rows": len(data),
                "sha256": hashlib.sha256(json.dumps(data).encode()).hexdigest(),
            }
        sequences = conn.execute(
            "SELECT sequencename FROM pg_sequences WHERE schemaname='public' "
            "ORDER BY sequencename"
        ).fetchall()
        for (sequence,) in sequences:
            result["sequences"][sequence] = conn.execute(
                sql.SQL("SELECT last_value,is_called FROM {}").format(
                    sql.Identifier("public", sequence)
                )
            ).fetchone()
        raw_constraints = conn.execute(
            "SELECT c.relname,k.conname,k.contype,pg_get_constraintdef(k.oid), "
            "pg_get_expr(k.conbin,k.conrelid),pg_get_expr(i.indpred,i.indrelid), "
            "k.condeferrable,k.condeferred,k.convalidated,k.connoinherit "
            "FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "LEFT JOIN pg_index i ON i.indexrelid=k.conindid "
            "WHERE n.nspname='public' ORDER BY c.relname,k.conname"
        ).fetchall()
        constraints = []
        for (
            table,
            name,
            kind,
            definition,
            check_expr,
            predicate,
            *flags,
        ) in raw_constraints:
            expression = (
                check_expr if kind == "c" else predicate if kind == "x" else None
            )
            if expression:
                # PostgreSQL's own planner folds equivalent constant array casts
                # introduced by dump/reparse. Never rewrite financial predicates
                # with Python string substitutions or compare only row counts.
                plan = conn.execute(
                    sql.SQL(
                        "EXPLAIN (VERBOSE, FORMAT JSON) SELECT ({}) FROM {}"
                    ).format(sql.SQL(expression), sql.Identifier("public", table))
                ).fetchone()[0][0]["Plan"]
                expression = plan["Output"][0]
                definition = (
                    "CHECK" if kind == "c" else definition.split(" WHERE ", 1)[0]
                )
            constraints.append((table, name, kind, definition, expression, *flags))
        result["constraints_sha256"] = hashlib.sha256(
            json.dumps(constraints).encode()
        ).hexdigest()
        result["constraints_count"] = len(constraints)
        result["constraint_definitions"] = constraints
    return result


def run():
    assert settings.SETTINGS_MODULE == "config.settings.development"
    config = settings.DATABASES["default"]
    assert config["HOST"] in {"localhost", "127.0.0.1", "::1"}
    assert config["ENGINE"] == "django.db.backends.postgresql"
    assert connections["default"].connection is None
    original_name = config["NAME"]
    controls = None
    if APPROVED_QUALIFICATION:
        from scripts.cep070_recovery_controls import (
            RecoveryControls,
            secure_development_secret_source,
            verify_private_tree,
        )

        store = Path(os.environ["BONIRA_CEP070_PRIVATE_STORE"]).resolve()
        approved_parent = Path(ROOT.anchor) / "BONIRA_Recovery"
        assert store.is_relative_to(approved_parent.resolve())
        controls = RecoveryControls(store)
        secret_source = secure_development_secret_source(store)
    names = ["cep070_erp_" + kind + "_" + uuid4().hex[:16] for kind in ("src", "dst")]
    assert original_name not in names and len(set(names)) == 2
    options = dict(config.get("OPTIONS", {}))
    options.update(
        host=config["HOST"],
        port=config["PORT"],
        user=config["USER"],
        password=config["PASSWORD"],
    )
    result = {
        "started_at": datetime.now(UTC).isoformat(),
        "head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "fixture": "SYNTHETIC_CURRENT_ERP_DEVELOPMENT_ONLY",
        "configured_business_database_accessed": False,
        "production_equivalent": False,
        "cep074_executed": False,
        "production_certification": "NOT_EXECUTED",
        "objectives": "UNSPECIFIED_NO_RPO_RTO_OR_PITR_CLAIM",
        "migration_verification": "NOT_EXECUTED_EXISTING_SCHEMA_FIXTURE_ONLY",
        "status": "INCOMPLETE",
        "checks": [],
        "source_sha256": {
            name: file_hash(ROOT / name)
            for name in (
                "scripts/backup_bundle.py",
                "scripts/cep070_erp_recovery_proof.py",
                "apps/documents/services.py",
                "apps/documents/storage.py",
                "apps/documents/tests.py",
                "tests/retirement_fixtures.py",
            )
        },
    }
    created = []
    fixture = None
    if controls:
        result["approved_policy"] = controls.policy
        result["private_store_reference"] = str(controls.root)
        result["secret_source_access"] = secret_source
        result["source_sha256"].update(
            {
                name: file_hash(ROOT / name)
                for name in (
                    "scripts/cep070_recovery_controls.py",
                    "docs/governance/cep/supporting/CEP-070_DEVELOPMENT_RECOVERY_POLICY.json",
                    "docs/governance/cep/supporting/CEP-070_EXT0020_HUMAN_APPROVAL_20261027.md",
                )
            }
        )

    def check(label, condition):
        result["checks"].append(
            {"check": label, "status": "PASS" if condition else "FAIL"}
        )
        if not condition:
            raise AssertionError(label)

    try:
        with psycopg.connect(**options, dbname="postgres", autocommit=True) as admin:
            result["postgresql"] = admin.execute("SELECT version()").fetchone()[0]
            for name in names:
                template = os.environ.get("BONIRA_CEP070_TEMPLATE_DATABASE")
                if name == names[0] and template:
                    assert template.startswith("test_") and template != original_name
                    from django.db.migrations.loader import MigrationLoader

                    with psycopg.connect(**options, dbname=template) as cached:
                        assert (
                            cached.execute(
                                "SELECT count(*) FROM accounts_user"
                            ).fetchone()[0]
                            == 0
                        )
                        assert (
                            cached.execute(
                                "SELECT count(*) FROM organizations_organization"
                            ).fetchone()[0]
                            == 0
                        )
                        applied = set(
                            cached.execute(
                                "SELECT app,name FROM django_migrations"
                            ).fetchall()
                        )
                        assert applied == set(MigrationLoader(None).graph.nodes)
                    admin.execute(
                        sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                            sql.Identifier(name), sql.Identifier(template)
                        )
                    )
                    result["fixture_schema_source"] = (
                        "READ_ONLY_EMPTY_TEST_TEMPLATE_WITH_EXACT_CURRENT_MIGRATION_GRAPH"
                    )
                    result["template_database"] = template
                else:
                    admin.execute(
                        sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name))
                    )
                created.append(name)
        config["NAME"] = names[0]
        connections["default"].settings_dict["NAME"] = names[0]
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT current_database()")
            check(
                "source connection uses newly created fixture database",
                cursor.fetchone()[0] == names[0],
            )
            cursor.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
        call_command("migrate", interactive=False, verbosity=0)

        from apps.accounts.models import User
        from apps.documents.models import Document, DocumentVersion
        from apps.documents.services import (
            add_document_version,
            get_document_version_for_download,
            get_organization_document,
            record_document_processing_assessment,
        )
        from apps.documents.tests import DocumentServiceTests
        from apps.organizations.access_services import assign_platform_role
        from apps.organizations.models import Organization, PlatformRoleCode
        from apps.projects.models import Project
        from apps.projects.services import create_project

        with tempfile.TemporaryDirectory(
            prefix="c70_" if controls else "bonira_cep070_erp_",
            dir=controls.root if controls else None,
        ) as folder:
            private = Path(folder).resolve()
            if controls:
                assert private.is_relative_to(controls.root)
            roots = {
                key: private / key
                for key in (
                    "document_media",
                    "configuration_metadata",
                    "audit_operational",
                )
            }
            for root in roots.values():
                root.mkdir()
            fixture = DocumentServiceTests()
            fixture.setUp()
            with override_settings(
                DOCUMENT_PROTECTED_ROOT=str(roots["document_media"] / "protected"),
                MEDIA_ROOT=str(roots["document_media"] / "media"),
            ):
                Path(settings.MEDIA_ROOT).mkdir()
                (Path(settings.MEDIA_ROOT) / "synthetic-media.txt").write_text(
                    "fixture only"
                )
                first = fixture._create_document()
                add_document_version(
                    document=first,
                    actor=fixture.owner,
                    upload=fixture._pdf_upload("v2.pdf", b"-v2"),
                )
                second_project = create_project(
                    organization=fixture.other_organization,
                    actor=fixture.other_user,
                    code="RECOVERY-B",
                    name="Synthetic recovery project",
                    estimated_budget=Decimal("123456.78"),
                    actual_budget=Decimal("123.45"),
                )
                second = fixture._create_document(
                    organization=fixture.other_organization,
                    actor=fixture.other_user,
                    target=second_project,
                    upload=fixture._pdf_upload("other.pdf", b"-other"),
                )
                assigner = User.objects.create_superuser(
                    username="recovery-fixture-assigner"
                )
                approver = User.objects.create_superuser(
                    username="recovery-fixture-approver"
                )
                operator = User.objects.create_user(
                    username="recovery-fixture-operator"
                )
                assign_platform_role(
                    actor=assigner,
                    approver=approver,
                    target=operator,
                    role=PlatformRoleCode.PLATFORM_OPERATIONS,
                    reason="Synthetic recovery fixture processing duty",
                )
                for version in DocumentVersion.objects.all():
                    record_document_processing_assessment(
                        version=version,
                        actor=operator,
                        verdict="clean",
                        adapter_code="synthetic-recovery-fixture",
                    )
                identities = [
                    (fixture.owner.pk, fixture.organization.pk, first.pk),
                    (fixture.other_user.pk, fixture.other_organization.pk, second.pk),
                ]
                (roots["configuration_metadata"] / "reconstruction.json").write_text(
                    json.dumps(
                        {
                            "revision": result["head"],
                            "mode": "synthetic-development",
                            "secrets": "NOT_CAPTURED",
                        }
                    )
                )
                (roots["audit_operational"] / "operation.json").write_text(
                    json.dumps(
                        {
                            "event": "synthetic.quiescent_capture",
                            "source": "CEP070-preparation",
                        }
                    )
                )
                connections.close_all()
                source = fingerprint(options, names[0])
                service_file = private / "pg_service.conf"
                service_file.write_text(
                    "\n".join(
                        f"[cep070_erp_{index}]\nhost={options['host']}\nport={options['port']}\n"
                        f"user={options['user']}\ndbname={name}\n"
                        for index, name in enumerate(names)
                    ),
                    encoding="utf-8",
                )
                started = perf_counter()
                with patch.dict(
                    os.environ,
                    {
                        "PGSERVICEFILE": str(service_file),
                        "PGPASSWORD": options["password"],
                    },
                ):
                    plan = BackupPlan(
                        environment="non-production",
                        source_revision=result["head"],
                        operator_reference="Human-authorized-Codex-Development-preparation",
                        recovery_reference=(
                            controls.policy["authority"]
                            if controls
                            else "CEP070-current-ERP-fixture-only"
                        ),
                        consistency_reference="isolated-quiescent-no-other-writers",
                        database_service="cep070_erp_0",
                        pg_dump=PG_BIN / "pg_dump.exe",
                        roots=roots,
                        destination=private / "bundle",
                        command_timeout_seconds=180,
                    )
                    if controls:
                        bundle = controls.run_cycles(plan, cycles=2)
                        capture = json.loads(
                            (bundle / "capture.json").read_text(encoding="utf-8")
                        )
                        result["capture_schedule"] = sorted(
                            [
                                json.loads(p.read_text(encoding="utf-8"))
                                for p in (controls.root / "events").glob("*.json")
                                if json.loads(p.read_text(encoding="utf-8"))["event"]
                                == "CAPTURE_COMPLETED"
                            ],
                            key=lambda event: event["capture_started_at"],
                        )
                    else:
                        bundle = private / "bundle"
                        capture = create_bundle(plan)
                    if controls:
                        result["bounded_worker_elapsed_seconds"] = (
                            perf_counter() - started
                        )
                        result["capture_seconds_observed_no_objective"] = sum(
                            (
                                datetime.fromisoformat(e["completed_at"])
                                - datetime.fromisoformat(e["capture_started_at"])
                            ).total_seconds()
                            for e in result["capture_schedule"]
                        )
                    else:
                        result["capture_seconds_observed_no_objective"] = (
                            perf_counter() - started
                        )
                    started = perf_counter()
                    recovery_started = datetime.now(UTC)
                    restored = subprocess.run(
                        [
                            str(PG_BIN / "pg_restore.exe"),
                            "--no-password",
                            "--exit-on-error",
                            "--no-owner",
                            "--no-privileges",
                            "--dbname=service=cep070_erp_1",
                            str(bundle / "database.dump"),
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=180,
                        check=False,
                    )
                    result["restore_seconds_observed_no_objective"] = (
                        perf_counter() - started
                    )
                check("PostgreSQL restore exits successfully", restored.returncode == 0)
                target = fingerprint(options, names[1])
                result["fingerprint_differences"] = {
                    key: {"source": source[key], "restored": target[key]}
                    for key in source
                    if source[key] != target[key]
                }
                check(
                    "all complete table rows, constraints and sequences match",
                    source == target,
                )
                check(
                    "source remains unchanged after backup",
                    source == fingerprint(options, names[0]),
                )
                result["database_fingerprint"] = target
                result["capture"] = capture
                recovered = private / "recovered"
                recovered.mkdir()
                for key, root in roots.items():
                    destination = recovered / key
                    shutil.copytree(bundle / key, destination)
                    expected = {
                        p.relative_to(root).as_posix(): file_hash(p)
                        for p in root.rglob("*")
                        if p.is_file()
                    }
                    actual = {
                        p.relative_to(destination).as_posix(): file_hash(p)
                        for p in destination.rglob("*")
                        if p.is_file()
                    }
                    check("recovered file class matches: " + key, expected == actual)
                config["NAME"] = names[1]
                connections["default"].settings_dict["NAME"] = names[1]
                with override_settings(
                    DOCUMENT_PROTECTED_ROOT=str(
                        recovered / "document_media" / "protected"
                    ),
                    MEDIA_ROOT=str(recovered / "document_media" / "media"),
                ):
                    for user_id, org_id, doc_id in identities:
                        actor = User.objects.get(pk=user_id)
                        organization = Organization.objects.get(pk=org_id)
                        document = get_organization_document(
                            user=actor,
                            organization=organization,
                            document_id=str(doc_id),
                        )
                        check(
                            "restored tenant can resolve its authorized document",
                            document.pk == doc_id,
                        )
                        for version in document.versions.all():
                            authorized = get_document_version_for_download(
                                document=document,
                                version_id=str(version.pk),
                                actor=actor,
                            )
                            with authorized.file.open("rb") as handle:
                                digest = hashlib.sha256(handle.read()).hexdigest()
                            check(
                                "restored version bytes match retained DB digest",
                                digest == version.sha256,
                            )
                        other = next(pair for pair in identities if pair[1] != org_id)
                        for attempted_org, attempted_doc in (
                            (organization, other[2]),
                            (Organization.objects.get(pk=other[1]), other[2]),
                        ):
                            denied = False
                            try:
                                get_organization_document(
                                    user=actor,
                                    organization=attempted_org,
                                    document_id=str(attempted_doc),
                                )
                            except PermissionDenied:
                                denied = True
                            check(
                                "restored cross-tenant document access denied", denied
                            )
                    project = Project.objects.get(pk=second_project.pk)
                    check(
                        "Decimal project budgets retain exact cents",
                        project.estimated_budget == Decimal("123456.78")
                        and project.actual_budget == Decimal("123.45"),
                    )
                    check(
                        "all immutable versions retained",
                        DocumentVersion.objects.count() == 3
                        and Document.objects.count() == 2,
                    )
                connections.close_all()
                check(
                    "read-only recovery validation preserves all database rows",
                    target == fingerprint(options, names[1]),
                )
                if controls:
                    result["approved_objective_result"] = controls.record_restore(
                        bundle=bundle,
                        started=recovery_started,
                        rpo_seconds=0,
                        passed=True,
                    )
                    result["rpo_basis"] = (
                        "No acknowledged synthetic write lost: complete row/sequence/constraint and all file-class equality at a quiescent boundary. No changing-workload RPO claim."
                    )
                    result["rto_boundary"] = (
                        "Preprovisioned empty target; restore invocation through database/file reconciliation and authorized tenant service validation. No web/provider/region recovery claim."
                    )
                    result["retention"] = controls.retention_status(datetime.now(UTC))
                    result["storage_access"] = verify_private_tree(controls.root)
                    result["schedule_state"] = controls.state
                    result["objectives"] = (
                        "PASS_EXECUTED_BOUNDED_SYNTHETIC_RECOVERY_ONLY"
                    )
        result["status"] = "PASS_CURRENT_ERP_SYNTHETIC_DEVELOPMENT_PREPARATION"
        if controls:
            result["status"] = (
                "PASS_EXT0020_APPROVED_SYNTHETIC_DEVELOPMENT_QUALIFICATION"
            )
    except Exception as exc:  # noqa: BLE001 -- sanitized evidence only
        result["status"] = "FAILED"
        result["failure_type"] = type(exc).__name__
        result["failure_stack"] = [
            {
                "file": Path(frame.filename).name,
                "line": frame.lineno,
                "function": frame.name,
            }
            for frame in traceback.extract_tb(exc.__traceback__)[-6:]
        ]
        result["failure_errno"] = getattr(exc, "errno", None)
        failed_path = str(getattr(exc, "filename", "") or "")
        result["failure_path_length"] = len(failed_path)
        if failed_path:
            result["failure_logical_path"] = failed_path.replace(
                os.environ.get("USERPROFILE", "__NO_USER_PROFILE__"), "%USERPROFILE%"
            ).replace(str(ROOT), "%REPO%")
        raise RuntimeError(
            "ERP recovery proof failed; inspect sanitized evidence."
        ) from None
    finally:
        if fixture is not None:
            fixture.doCleanups()
        connections.close_all()
        config["NAME"] = original_name
        connections["default"].settings_dict["NAME"] = original_name
        with psycopg.connect(**options, dbname="postgres", autocommit=True) as admin:
            for name in reversed(created):
                assert (
                    name in names
                    and name.startswith("cep070_erp_")
                    and name != original_name
                )
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
            check(
                "both new disposable databases removed",
                all(
                    admin.execute(
                        "SELECT 1 FROM pg_database WHERE datname=%s", (name,)
                    ).fetchone()
                    is None
                    for name in names
                ),
            )
        result["finished_at"] = datetime.now(UTC).isoformat()
        OUT.mkdir(exist_ok=True)
        (OUT / "ERP_RECOVERY.json").write_text(
            json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8"
        )
    print(result["status"])


if __name__ == "__main__":
    run()
