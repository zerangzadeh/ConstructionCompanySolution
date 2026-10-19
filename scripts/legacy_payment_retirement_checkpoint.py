"""Capture and restore-verify the authorized local Development database.

Private dump/diagnostics stay ignored. This does not migrate or alter the source
database, delete a database, grant production authority, or issue certification.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

import psycopg
from django.conf import settings
from django.db import connection
from psycopg import sql


def inventory(conn) -> dict[str, dict[str, object]]:
    result = {}
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        )
        for (table,) in cursor.fetchall():
            cursor.execute(
                sql.SQL(
                    "SELECT count(*), md5(coalesce(string_agg(row_hash, '' ORDER BY row_hash), '')) "
                    "FROM (SELECT md5(to_jsonb(t)::text) row_hash FROM {} t) rows"
                ).format(sql.Identifier(table))
            )
            count, digest = cursor.fetchone()
            result[table] = {"count": count, "digest": digest}
    return result


def main() -> None:
    if settings.SETTINGS_MODULE != "config.settings.development":
        raise RuntimeError("Only explicit Development settings are permitted")
    config = connection.settings_dict
    if config["HOST"] not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("Only the local Development PostgreSQL host is permitted")
    native = Path("D:/Program Files/PostgreSQL/18/bin")
    if not all((native / name).is_file() for name in ("pg_dump.exe", "pg_restore.exe")):
        raise RuntimeError("Native PostgreSQL dump/restore tools unavailable")
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    private = ROOT / "output/legacy-payment-retirement-private" / stamp
    private.mkdir(parents=True, exist_ok=False)
    dump = private / "development.dump"
    env = os.environ.copy()
    env.update(
        PGHOST=config["HOST"],
        PGPORT=str(config["PORT"]),
        PGUSER=config["USER"],
        PGPASSWORD=config["PASSWORD"],
        PGDATABASE=config["NAME"],
        PGSSLMODE=config["OPTIONS"].get("sslmode", "prefer"),
    )

    def run(args: list[str], name: str):
        result = subprocess.run(
            args, env=env, capture_output=True, timeout=600, check=False
        )
        (private / f"{name}.diagnostic").write_bytes(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f"{name} failed; see ignored private diagnostic")

    connection.ensure_connection()
    before = inventory(connection)
    run(
        [str(native / "pg_dump.exe"), "--format=custom", "--file", str(dump)], "capture"
    )
    after = inventory(connection)
    if before != after:
        raise RuntimeError("Source changed during capture; checkpoint not verified")
    restore_name = f"bonira_payment_restore_{stamp}"
    kwargs = {
        "host": config["HOST"],
        "port": config["PORT"],
        "user": config["USER"],
        "password": config["PASSWORD"],
        "sslmode": env["PGSSLMODE"],
    }
    # Create a unique clone; deliberately never DROP or overwrite a database.
    with psycopg.connect(dbname="postgres", autocommit=True, **kwargs) as admin:
        admin.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                sql.Identifier(restore_name)
            )
        )
    env["PGDATABASE"] = restore_name
    run(
        [
            str(native / "pg_restore.exe"),
            "--exit-on-error",
            "--no-owner",
            "--no-privileges",
            "--dbname",
            restore_name,
            str(dump),
        ],
        "restore",
    )
    with psycopg.connect(dbname=restore_name, **kwargs) as restored:
        actual = inventory(restored)
    if before != actual:
        raise RuntimeError(
            "Restored table row counts/digests differ; recovery not verified"
        )
    manifest = {
        "environment": "local-development-postgresql",
        "source_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "capture_utc": stamp,
        "source_unchanged_during_capture": True,
        "restored_all_tables_match": True,
        "table_count": len(actual),
        "dump_sha256": hashlib.sha256(dump.read_bytes()).hexdigest(),
        "private_dump_path": str(dump),
        "restored_database": restore_name,
        "tables": actual,
    }
    (private / "recovery.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    public = {
        key: manifest[key]
        for key in (
            "environment",
            "source_revision",
            "capture_utc",
            "source_unchanged_during_capture",
            "restored_all_tables_match",
            "table_count",
            "dump_sha256",
        )
    }
    public.update(
        status="PASS",
        private_manifest_path=str(private / "recovery.json"),
        source_database_mutated=False,
    )
    (
        ROOT / "docs/governance/cep/evidence/CEP-064_DEVELOPMENT_RECOVERY.json"
    ).write_text(json.dumps(public, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(public))


if __name__ == "__main__":
    main()
