"""CEP-070 synthetic loopback-only capture/restore. Never migrate an ERP DB."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import psycopg
from dotenv import dotenv_values
from psycopg import sql

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.backup_bundle import BackupPlan, create_bundle, file_hash

PG_BIN = Path(r"D:\Program Files\PostgreSQL\18\bin")


def main() -> None:
    values = dotenv_values(ROOT / ".env")
    host = values.get("DB_HOST") or "localhost"
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("Rehearsal requires the existing local loopback server.")
    stamp = uuid4().hex
    source, restored = (f"cep070_{kind}_{stamp}" for kind in ("source", "restore"))
    if values.get("DB_NAME") in {source, restored}:
        raise RuntimeError(
            "Disposable names must differ from the application database."
        )
    connection = {
        "host": host,
        "port": values.get("DB_PORT") or "5432",
        "user": values.get("DB_USER") or "",
        "password": values.get("DB_PASSWORD") or "",
        "connect_timeout": 10,
    }
    result = {
        "scope": "CEP070 synthetic non-production capture/restore only",
        "started_at": datetime.now(UTC).isoformat(),
        "baseline_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_hashes": {
            name: file_hash(ROOT / name)
            for name in ("scripts/backup_bundle.py", "output/cep-070/run_rehearsal.py")
        },
        "production_certification": "NOT_EXECUTED",
        "production_objectives": "UNSPECIFIED",
        "application_database_accessed": False,
        "erp_tenant_restore_validation": "NOT_EXECUTED",
        "cross_store_consistency": "QUIESCENT_SYNTHETIC_FIXTURE_ONLY",
        "migrations_executed": False,
        "scenario": "two synthetic relational rows and three file-class trees",
        "status": "INCOMPLETE",
    }
    created = []
    try:
        with psycopg.connect(**connection, dbname="postgres", autocommit=True) as admin:
            result["postgresql_version"] = admin.execute("SELECT version()").fetchone()[
                0
            ]
            for database in (source, restored):
                admin.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database))
                )
                created.append(database)
        with psycopg.connect(**connection, dbname=source) as conn:
            conn.execute("CREATE TABLE fixture (tenant text, amount numeric(12,2))")
            conn.execute(
                "INSERT INTO fixture VALUES ('synthetic-a', 12.34), ('synthetic-b', 56.78)"
            )
        with tempfile.TemporaryDirectory(prefix="bonira_cep070_") as folder:
            temporary = Path(folder).resolve()
            roots = {}
            for name in (
                "document_media",
                "configuration_metadata",
                "audit_operational",
            ):
                roots[name] = temporary / name
                roots[name].mkdir()
                (roots[name] / "fixture.txt").write_text("synthetic " + name)
            service_file = temporary / "pg_service.conf"
            service_file.write_text(
                "".join(
                    f"[{name}]\nhost={host}\nport={connection['port']}\n"
                    f"user={connection['user']}\ndbname={database}\n"
                    for name, database in (
                        ("cep070_source", source),
                        ("cep070_restore", restored),
                    )
                ),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "PGSERVICEFILE": str(service_file),
                    "PGPASSWORD": connection["password"],
                },
            ):
                capture = create_bundle(
                    BackupPlan(
                        environment="non-production",
                        source_revision=result["baseline_revision"],
                        operator_reference="authorized-Codex-nonproduction-rehearsal",
                        recovery_reference="CEP070-synthetic-rehearsal-only",
                        consistency_reference="CEP070-private-quiescent-fixtures",
                        database_service="cep070_source",
                        pg_dump=PG_BIN / "pg_dump.exe",
                        roots=roots,
                        destination=temporary / "bundle",
                        command_timeout_seconds=120,
                    )
                )
                result["capture"] = capture
                completed = subprocess.run(
                    [
                        str(PG_BIN / "pg_restore.exe"),
                        "--no-password",
                        "--exit-on-error",
                        "--no-owner",
                        "--no-privileges",
                        "--dbname=service=cep070_restore",
                        str(temporary / "bundle" / "database.dump"),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=120,
                    check=False,
                )
                result["restore_exit_code"] = completed.returncode
                if completed.returncode:
                    raise RuntimeError("Synthetic restore failed.")
            with psycopg.connect(**connection, dbname=source) as conn:
                source_rows = conn.execute(
                    "SELECT tenant, amount FROM fixture ORDER BY tenant"
                ).fetchall()
            with psycopg.connect(**connection, dbname=restored) as conn:
                restored_rows = conn.execute(
                    "SELECT tenant, amount FROM fixture ORDER BY tenant"
                ).fetchall()
            result["database_rows_match"] = (
                source_rows == restored_rows and len(source_rows) == 2
            )
            result["all_file_class_hashes_match"] = all(
                file_hash(root / "fixture.txt")
                == file_hash(temporary / "bundle" / name / "fixture.txt")
                for name, root in roots.items()
            )
            if (
                not result["database_rows_match"]
                or not result["all_file_class_hashes_match"]
            ):
                raise RuntimeError("Synthetic restored source mismatch.")
        result["status"] = "PASS_SYNTHETIC_REHEARSAL_ONLY"
    except Exception as exc:  # noqa: BLE001 -- restricted evidence, no raw error data
        result["status"] = "FAILED"
        result["failure_type"] = type(exc).__name__
        raise RuntimeError("Rehearsal failed; inspect minimized evidence.") from None
    finally:
        with psycopg.connect(**connection, dbname="postgres", autocommit=True) as admin:
            for database in reversed(created):
                admin.execute(
                    sql.SQL("DROP DATABASE {}").format(sql.Identifier(database))
                )
        result["disposable_databases_removed"] = len(created)
        result["completed_at"] = datetime.now(UTC).isoformat()
        (ROOT / "output/cep-070/rehearsal.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
    print(result["status"])


if __name__ == "__main__":
    main()
