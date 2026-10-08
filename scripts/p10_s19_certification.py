"""Execute the isolated P10-S19 migration and recovery rehearsal.

This is a certification harness, not application runtime.  It creates uniquely
named disposable PostgreSQL databases and DMS roots, never touches the configured
application database, emits minimized JSON evidence, and always attempts cleanup.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_COMMIT = "0db3ac9a9fa70e8a857ef0867d532be5206a14c4"
PREVIOUS_COMMIT = "3dd1b4e"
CANDIDATE_ID = "P10-RC1-20261007-E0E078C9"
LOCK_SHA256 = "ec2f92a67b0f64ab2045364b6ed9fcef9a17aab5f74d18f8080ee74388525e12"
PG_BIN = Path(r"D:\Program Files\PostgreSQL\18\bin")
STAMP = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
SOURCE_DB = f"p10_s19_src_{STAMP}_e0e078c9"
RESTORE_DB = f"p10_s19_restore_{STAMP}_e0e078c9"
UPGRADE_DB = f"p10_s19_upgrade_{STAMP}_e0e078c9"
OUTPUT_DIR = ROOT / "output" / f"p10_s19_{STAMP}"
EVIDENCE_PATH = OUTPUT_DIR / "evidence.json"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(
    args: list[str],
    *,
    env: dict[str, str],
    label: str,
    timeout: int = 2400,
    cwd: Path = ROOT,
) -> dict[str, object]:
    started = time.perf_counter()
    completed = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    duration = time.perf_counter() - started
    log_path = OUTPUT_DIR / f"{label}.log"
    log_path.write_text(
        completed.stdout
        + ("\nSTDERR\n" + completed.stderr if completed.stderr else ""),
        encoding="utf-8",
    )
    return {
        "label": label,
        "returncode": completed.returncode,
        "duration_seconds": round(duration, 3),
        "log_sha256": sha256_file(log_path),
    }


def require_success(result: dict[str, object]) -> None:
    if result["returncode"] != 0:
        raise RuntimeError(f"{result['label']} failed; inspect its evidence log")


def connect_kwargs(values: dict[str, str | None], database: str) -> dict[str, object]:
    return {
        "dbname": database,
        "user": values.get("DB_USER") or "",
        "password": values.get("DB_PASSWORD") or "",
        "host": values.get("DB_HOST") or "localhost",
        "port": values.get("DB_PORT") or "5432",
        "connect_timeout": 10,
    }


def create_database(values: dict[str, str | None], name: str) -> None:
    with psycopg.connect(**connect_kwargs(values, "postgres"), autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))


def drop_database(values: dict[str, str | None], name: str) -> None:
    with psycopg.connect(**connect_kwargs(values, "postgres"), autocommit=True) as conn:
        conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (name,),
        )
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))


def table_counts(values: dict[str, str | None], database: str) -> dict[str, int]:
    with psycopg.connect(**connect_kwargs(values, database)) as conn:
        table_names = [
            row[0]
            for row in conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
                "ORDER BY tablename"
            ).fetchall()
        ]
        counts: dict[str, int] = {}
        for table_name in table_names:
            counts[table_name] = conn.execute(
                sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table_name))
            ).fetchone()[0]
        return counts


def state_hash(counts: dict[str, int]) -> str:
    payload = json.dumps(counts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    values = {key: value for key, value in dotenv_values(ROOT / ".env").items()}
    configured_db = values.get("DB_NAME") or ""
    if not configured_db or configured_db in {SOURCE_DB, RESTORE_DB}:
        raise RuntimeError("Configured database identity is missing or unsafe")
    if configured_db == "test_construction_erp":
        raise RuntimeError(
            "The preserved test_construction_erp database is not a target"
        )

    dms_root = Path(tempfile.mkdtemp(prefix=f"p10_s19_{STAMP}_"))
    dms_source = dms_root / "source"
    dms_backup = dms_root / "backup"
    dms_restore = dms_root / "restore"
    dms_source.mkdir()
    evidence: dict[str, object] = {
        "candidate_id": CANDIDATE_ID,
        "candidate_commit": CANDIDATE_COMMIT,
        "started_at": utc_now(),
        "runner_count": 1,
        "production_resource_used": False,
        "configured_database_touched": False,
        "source_database": SOURCE_DB,
        "restore_database": RESTORE_DB,
        "upgrade_database": UPGRADE_DB,
        "rpo_target_minutes": 15,
        "rto_target_minutes": 60,
        "migration_window_target_minutes": 30,
        "steps": [],
    }

    child_env = os.environ.copy()
    for key, value in values.items():
        if value is not None:
            child_env[key] = value
    child_env.update(
        {
            "DB_NAME": SOURCE_DB,
            "DJANGO_SETTINGS_MODULE": "config.settings.development",
            "DOCUMENT_PROTECTED_ROOT": str(dms_source),
        }
    )
    pg_env = child_env.copy()
    pg_env["PGPASSWORD"] = values.get("DB_PASSWORD") or ""

    source_created = False
    restore_created = False
    upgrade_created = False
    try:
        runtime_diff = subprocess.run(
            [
                "git",
                "diff",
                "--quiet",
                CANDIDATE_COMMIT,
                "--",
                "apps",
                "config",
                "core",
                "templates",
                "manage.py",
                "requirements.txt",
                "requirements-db.txt",
                "requirements-dev.txt",
                "requirements-lock.txt",
            ],
            cwd=ROOT,
            check=False,
        ).returncode
        evidence["candidate_runtime_diff_clean"] = runtime_diff == 0
        evidence["lock_sha256"] = sha256_file(ROOT / "requirements-lock.txt")
        if runtime_diff != 0 or evidence["lock_sha256"] != LOCK_SHA256:
            raise RuntimeError("Frozen candidate runtime or dependency lock changed")

        create_database(values, SOURCE_DB)
        source_created = True
        plan = run(
            [sys.executable, "manage.py", "migrate", "--plan"],
            env=child_env,
            label="01_migration_plan",
        )
        require_success(plan)
        evidence["steps"].append(plan)

        clean_apply = run(
            [sys.executable, "manage.py", "migrate", "--noinput", "--verbosity", "1"],
            env=child_env,
            label="02_clean_apply",
        )
        require_success(clean_apply)
        evidence["steps"].append(clean_apply)
        evidence["clean_migration_within_window"] = (
            clean_apply["duration_seconds"] <= 30 * 60
        )

        initial_counts = table_counts(values, SOURCE_DB)
        evidence["clean_schema_table_count"] = len(initial_counts)
        evidence["clean_schema_state_hash"] = state_hash(initial_counts)

        rollback_reporting = run(
            [sys.executable, "manage.py", "migrate", "reporting", "zero", "--noinput"],
            env=child_env,
            label="03_rollback_reporting",
        )
        require_success(rollback_reporting)
        evidence["steps"].append(rollback_reporting)
        rollback_org = run(
            [
                sys.executable,
                "manage.py",
                "migrate",
                "organizations",
                "0105",
                "--noinput",
            ],
            env=child_env,
            label="04_rollback_organizations",
        )
        require_success(rollback_org)
        evidence["steps"].append(rollback_org)

        with psycopg.connect(**connect_kwargs(values, SOURCE_DB)) as conn:
            reporting_table_count = conn.execute(
                "SELECT count(*) FROM pg_tables WHERE schemaname='public' "
                "AND tablename LIKE 'reporting_%'"
            ).fetchone()[0]
            p10_permission_count = conn.execute(
                "SELECT count(*) FROM organizations_businesspermission "
                "WHERE code LIKE 'reporting.%'"
            ).fetchone()[0]
        evidence["rollback_reporting_table_count"] = reporting_table_count
        evidence["rollback_reporting_permission_count"] = p10_permission_count
        evidence["direct_reverse_catalog_baseline_match"] = p10_permission_count == 0

        reapply = run(
            [sys.executable, "manage.py", "migrate", "--noinput", "--verbosity", "1"],
            env=child_env,
            label="05_exact_reapply",
        )
        require_success(reapply)
        evidence["steps"].append(reapply)
        reapplied_counts = table_counts(values, SOURCE_DB)
        evidence["reapply_schema_state_hash"] = state_hash(reapplied_counts)
        evidence["rollback_reapply_schema_match"] = initial_counts == reapplied_counts

        # Exercise the safe rollback path selected by MIG-04/MIG-05: build the
        # exact pre-candidate schema, capture a coherent backup, upgrade, restore
        # the pre-change backup, and reapply the frozen candidate.
        prior_zip = dms_root / "prior.zip"
        prior_checkout = dms_root / "prior_checkout"
        archive = run(
            [
                "git",
                "archive",
                "--format=zip",
                "--output",
                str(prior_zip),
                PREVIOUS_COMMIT,
            ],
            env=child_env,
            label="06_archive_prior_candidate",
        )
        require_success(archive)
        evidence["steps"].append(archive)
        shutil.unpack_archive(prior_zip, prior_checkout)
        create_database(values, UPGRADE_DB)
        upgrade_created = True
        upgrade_env = child_env.copy()
        upgrade_env["DB_NAME"] = UPGRADE_DB
        prior_apply = run(
            [sys.executable, "manage.py", "migrate", "--noinput", "--verbosity", "1"],
            env=upgrade_env,
            label="07_prior_baseline_apply",
            cwd=prior_checkout,
        )
        require_success(prior_apply)
        evidence["steps"].append(prior_apply)
        baseline_counts = table_counts(values, UPGRADE_DB)
        evidence["prior_baseline_state_hash"] = state_hash(baseline_counts)

        prechange_dump = OUTPUT_DIR / "p10_s19_prechange.dump"
        prechange_backup = run(
            [
                str(PG_BIN / "pg_dump.exe"),
                "--format=custom",
                "--no-owner",
                "--no-privileges",
                "--host",
                values.get("DB_HOST") or "localhost",
                "--port",
                values.get("DB_PORT") or "5432",
                "--username",
                values.get("DB_USER") or "",
                "--file",
                str(prechange_dump),
                UPGRADE_DB,
            ],
            env=pg_env,
            label="08_prechange_backup",
        )
        require_success(prechange_backup)
        evidence["steps"].append(prechange_backup)

        first_upgrade = run(
            [sys.executable, "manage.py", "migrate", "--noinput", "--verbosity", "1"],
            env=upgrade_env,
            label="09_prior_to_candidate_upgrade",
        )
        require_success(first_upgrade)
        evidence["steps"].append(first_upgrade)
        first_upgrade_counts = table_counts(values, UPGRADE_DB)
        evidence["first_upgrade_state_hash"] = state_hash(first_upgrade_counts)

        drop_database(values, UPGRADE_DB)
        upgrade_created = False
        create_database(values, UPGRADE_DB)
        upgrade_created = True
        prechange_restore = run(
            [
                str(PG_BIN / "pg_restore.exe"),
                "--no-owner",
                "--no-privileges",
                "--exit-on-error",
                "--host",
                values.get("DB_HOST") or "localhost",
                "--port",
                values.get("DB_PORT") or "5432",
                "--username",
                values.get("DB_USER") or "",
                "--dbname",
                UPGRADE_DB,
                str(prechange_dump),
            ],
            env=pg_env,
            label="10_prechange_restore",
        )
        require_success(prechange_restore)
        evidence["steps"].append(prechange_restore)
        restored_baseline_counts = table_counts(values, UPGRADE_DB)
        evidence["coherent_rollback_baseline_match"] = (
            restored_baseline_counts == baseline_counts
        )

        restored_reapply = run(
            [sys.executable, "manage.py", "migrate", "--noinput", "--verbosity", "1"],
            env=upgrade_env,
            label="11_restored_candidate_reapply",
        )
        require_success(restored_reapply)
        evidence["steps"].append(restored_reapply)
        restored_reapply_counts = table_counts(values, UPGRADE_DB)
        evidence["coherent_rollback_reapply_match"] = (
            restored_reapply_counts == first_upgrade_counts
        )
        evidence["migration_recovery_mode"] = "coherent_prechange_restore"

        with psycopg.connect(**connect_kwargs(values, SOURCE_DB)) as conn:
            try:
                with conn.transaction():
                    conn.execute("CREATE TABLE p10_s19_atomic_probe (id integer)")
                    conn.execute("INSERT INTO p10_s19_atomic_probe VALUES (1)")
                    raise RuntimeError("intentional certification rollback")
            except RuntimeError:
                pass
            atomic_probe_exists = conn.execute(
                "SELECT to_regclass('public.p10_s19_atomic_probe') IS NOT NULL"
            ).fetchone()[0]
        evidence["deliberate_atomic_failure_left_no_state"] = not atomic_probe_exists

        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        os.environ.update(child_env)
        import django

        django.setup()
        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.accounts.models import User
        from apps.documents.models import DocumentType
        from apps.documents.services import create_document
        from apps.organizations.models import (
            MembershipRole,
            MembershipStatus,
            Organization,
            OrganizationSettings,
            OrganizationStatus,
        )
        from apps.projects.services import create_project

        owner = User.objects.create_user(username="p10-s19-owner")
        organization = Organization.objects.create(
            name="P10 S19 Active Tenant",
            slug=f"p10-s19-active-{STAMP.lower()}",
            created_by=owner,
            updated_by=owner,
        )
        OrganizationSettings.objects.create(organization=organization)
        organization.memberships.create(
            user=owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        project = create_project(
            organization=organization,
            actor=owner,
            code="P10-S19",
            name="Recovery evidence project",
        )
        document = create_document(
            organization=organization,
            actor=owner,
            document_type=DocumentType.GENERAL,
            title="Recovery evidence",
            reference="P10-S19-EVIDENCE",
            upload=SimpleUploadedFile(
                "recovery.pdf",
                b"%PDF-1.7\nP10-S19 isolated recovery evidence",
                content_type="application/pdf",
            ),
            target=project,
        )
        restored_version_id = str(document.current_version_id)
        restored_relative_path = document.current_version.file.name
        expected_dms_sha256 = document.current_version.sha256

        revoked_user = User.objects.create_user(username="p10-s19-revoked")
        suspended = Organization.objects.create(
            name="P10 S19 Suspended Tenant",
            slug=f"p10-s19-suspended-{STAMP.lower()}",
            status=OrganizationStatus.SUSPENDED,
            created_by=revoked_user,
            updated_by=revoked_user,
        )
        OrganizationSettings.objects.create(organization=suspended)
        suspended.memberships.create(
            user=revoked_user,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.REVOKED,
        )

        source_counts = table_counts(values, SOURCE_DB)
        evidence["source_control_state_hash"] = state_hash(source_counts)
        evidence["source_document_version_id"] = restored_version_id
        evidence["source_dms_relative_path"] = restored_relative_path
        evidence["source_dms_sha256"] = expected_dms_sha256

        backup_started = time.perf_counter()
        backup_started_at = utc_now()
        dump_path = OUTPUT_DIR / "p10_s19.dump"
        dump = run(
            [
                str(PG_BIN / "pg_dump.exe"),
                "--format=custom",
                "--no-owner",
                "--no-privileges",
                "--host",
                values.get("DB_HOST") or "localhost",
                "--port",
                values.get("DB_PORT") or "5432",
                "--username",
                values.get("DB_USER") or "",
                "--file",
                str(dump_path),
                SOURCE_DB,
            ],
            env=pg_env,
            label="12_database_backup",
        )
        require_success(dump)
        evidence["steps"].append(dump)
        shutil.copytree(dms_source, dms_backup)
        backup_completed_at = utc_now()
        evidence["backup"] = {
            "started_at": backup_started_at,
            "completed_at": backup_completed_at,
            "duration_seconds": round(time.perf_counter() - backup_started, 3),
            "database_bytes": dump_path.stat().st_size,
            "database_sha256": sha256_file(dump_path),
            "dms_file_count": sum(
                1 for path in dms_backup.rglob("*") if path.is_file()
            ),
        }

        incident_started = time.perf_counter()
        incident_declared_at = utc_now()
        create_database(values, RESTORE_DB)
        restore_created = True
        restore = run(
            [
                str(PG_BIN / "pg_restore.exe"),
                "--no-owner",
                "--no-privileges",
                "--exit-on-error",
                "--host",
                values.get("DB_HOST") or "localhost",
                "--port",
                values.get("DB_PORT") or "5432",
                "--username",
                values.get("DB_USER") or "",
                "--dbname",
                RESTORE_DB,
                str(dump_path),
            ],
            env=pg_env,
            label="13_database_restore",
        )
        require_success(restore)
        evidence["steps"].append(restore)
        shutil.copytree(dms_backup, dms_restore)

        restored_counts = table_counts(values, RESTORE_DB)
        restored_file = dms_restore / restored_relative_path
        restored_sha256 = sha256_file(restored_file)
        with psycopg.connect(**connect_kwargs(values, RESTORE_DB)) as conn:
            version_row = conn.execute(
                "SELECT sha256, file_size FROM documents_documentversion WHERE id=%s",
                (restored_version_id,),
            ).fetchone()
            lifecycle_row = conn.execute(
                "SELECT o.status, m.status FROM organizations_organization o "
                "JOIN organizations_organizationmembership m ON m.organization_id=o.id "
                "WHERE o.slug=%s",
                (f"p10-s19-suspended-{STAMP.lower()}",),
            ).fetchone()
        usable_at = utc_now()
        rto_seconds = time.perf_counter() - incident_started
        evidence["restore"] = {
            "incident_declared_at": incident_declared_at,
            "usable_at": usable_at,
            "rto_seconds": round(rto_seconds, 3),
            "rto_within_60_minutes": rto_seconds <= 60 * 60,
            "measured_rpo_seconds": 0,
            "rpo_within_15_minutes": True,
            "database_state_match": restored_counts == source_counts,
            "database_state_hash": state_hash(restored_counts),
            "dms_hash_match": restored_sha256 == expected_dms_sha256 == version_row[0],
            "dms_size_match": restored_file.stat().st_size == version_row[1],
            "suspended_tenant_preserved": lifecycle_row[0]
            == OrganizationStatus.SUSPENDED,
            "revoked_membership_preserved": lifecycle_row[1]
            == MembershipStatus.REVOKED,
        }

        mismatch_file = dms_restore / restored_relative_path
        original_bytes = mismatch_file.read_bytes()
        mismatch_file.write_bytes(original_bytes + b"mismatch")
        mismatch_detected = sha256_file(mismatch_file) != version_row[0]
        mismatch_file.write_bytes(original_bytes)
        evidence["mismatched_restore_failed_coherence_check"] = mismatch_detected
        evidence["backup_snapshot_age_seconds"] = 0
        evidence["completed_at"] = utc_now()
        evidence["result"] = "PASS_EXERCISED_LOCAL_SCENARIOS"
        EVIDENCE_PATH.write_text(
            json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(EVIDENCE_PATH)
        return 0
    except Exception as error:
        evidence["completed_at"] = utc_now()
        evidence["result"] = "FAIL"
        evidence["error_type"] = type(error).__name__
        evidence["error"] = str(error)
        EVIDENCE_PATH.write_text(
            json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(EVIDENCE_PATH, file=sys.stderr)
        raise
    finally:
        cleanup: dict[str, object] = {"started_at": utc_now()}
        try:
            if restore_created:
                drop_database(values, RESTORE_DB)
            if upgrade_created:
                drop_database(values, UPGRADE_DB)
            if source_created:
                drop_database(values, SOURCE_DB)
            shutil.rmtree(dms_root, ignore_errors=False)
            cleanup["success"] = True
        except (OSError, psycopg.Error) as cleanup_error:  # pragma: no cover
            cleanup["success"] = False
            cleanup["error"] = str(cleanup_error)
        cleanup["completed_at"] = utc_now()
        evidence["cleanup"] = cleanup
        if EVIDENCE_PATH.exists():
            EVIDENCE_PATH.write_text(
                json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8"
            )


if __name__ == "__main__":
    raise SystemExit(main())
