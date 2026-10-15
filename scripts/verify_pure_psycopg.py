"""Bounded CEP-013 pure-Psycopg verification; never rewrites the production lock."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import sys
from pathlib import Path

PURE_WHEEL = "psycopg-3.3.5-py3-none-any.whl"
PURE_SHA256 = "ce5aa5cdb4f9379f00f487590e5890bfa7df9a164648c969ffa628505e21af4e"
BINARY_LINE = "psycopg-binary==3.3.5 " + chr(92)
BINARY_SHA256 = "d8b66353b20e79bf7ac0a80f03ae97f522ccbbf909d687eec62f112e56c0276d"


def prepare_lock(source: Path, destination: Path) -> None:
    """Remove exactly one rejected artifact from an ephemeral lock copy."""
    raw = source.read_text(encoding="utf-8")
    lines = raw.splitlines(keepends=True)
    binary_indexes = [
        i for i, line in enumerate(lines) if line.startswith("psycopg-binary==")
    ]
    if len(binary_indexes) != 1:
        raise ValueError("Expected exactly one psycopg-binary lock entry")
    index = binary_indexes[0]
    if lines[index].strip() != BINARY_LINE.strip():
        raise ValueError("Unexpected psycopg-binary lock entry")
    if index + 1 >= len(lines) or lines[index + 1].strip() != (
        f"--hash=sha256:{BINARY_SHA256}"
    ):
        raise ValueError("Unexpected psycopg-binary wheel hash")
    if len(re.findall(r"^psycopg==3\.3\.5\s*\\$", raw, re.MULTILINE)) != 1:
        raise ValueError("Exact psycopg version missing or duplicated")
    if raw.count(f"--hash=sha256:{PURE_SHA256}") != 1:
        raise ValueError("Exact psycopg wheel hash missing or duplicated")
    del lines[index : index + 2]
    result = "".join(lines)
    if "psycopg-binary" in result.lower():
        raise ValueError("Rejected artifact remains in ephemeral lock")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(result, encoding="utf-8")


def runtime_check(wheelhouse: Path, output: Path) -> None:
    """Exercise the Django backend against a disposable PostgreSQL database."""
    output.parent.mkdir(parents=True, exist_ok=True)
    result: dict[str, object] = {
        "status": "FAIL",
        "python": sys.version,
        "architecture": platform.machine(),
        "psycopg_wheel": PURE_WHEEL,
        "checks": {},
    }
    checks: dict[str, str] = result["checks"]  # type: ignore[assignment]
    try:
        expected = wheelhouse / PURE_WHEEL
        if hashlib.sha256(expected.read_bytes()).hexdigest() != PURE_SHA256:
            raise RuntimeError("Pure Psycopg wheel hash mismatch")
        result["psycopg_wheel_sha256"] = PURE_SHA256
        checks["wheel_hash"] = "PASS"

        installed = {
            d.metadata["Name"].lower().replace("_", "-")
            for d in importlib.metadata.distributions()
        }
        if "psycopg-binary" in installed:
            raise RuntimeError("psycopg-binary is installed")
        import psycopg
        from psycopg import pq

        if psycopg.__version__ != "3.3.5":
            raise RuntimeError(f"Unexpected Psycopg version: {psycopg.__version__}")
        if pq.__impl__ != "python":
            raise RuntimeError(f"Unexpected Psycopg implementation: {pq.__impl__}")
        for root in map(Path, sys.path):
            if root.is_dir() and any(root.glob("psycopg_binary*")):
                raise RuntimeError(f"psycopg-binary files found under {root}")
        result["psycopg_version"] = psycopg.__version__
        result["psycopg_implementation"] = pq.__impl__
        result["libpq_version_number"] = pq.version()
        result["psycopg_binary_installed"] = False
        checks["pure_import_and_absence"] = "PASS"

        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
        import django

        django.setup()
        checks["django_setup"] = "PASS"
        from django.contrib.auth import get_user_model
        from django.db import connection, transaction

        connection.ensure_connection()
        checks["postgresql_connection"] = "PASS"
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            if cursor.fetchone() != (1,):
                raise RuntimeError("SELECT 1 returned unexpected value")
        checks["select_1"] = "PASS"

        user_model = get_user_model()
        result["orm_read_count"] = user_model.objects.count()
        checks["orm_read"] = "PASS"
        username = "cep013_pure_psycopg_rollback_probe"
        if user_model.objects.filter(username=username).exists():
            raise RuntimeError("Rollback probe username already exists")
        with transaction.atomic():
            user_model.objects.create(username=username)
            if not user_model.objects.filter(username=username).exists():
                raise RuntimeError("Transactional ORM write was not visible")
            checks["transactional_orm_write"] = "PASS"
            transaction.set_rollback(True)
        if user_model.objects.filter(username=username).exists():
            raise RuntimeError("Rollback probe row remained after rollback")
        checks["rollback_confirmed"] = "PASS"
        connection.close()
        if connection.connection is not None:
            raise RuntimeError("Django database connection did not close")
        checks["clean_close"] = "PASS"
        result["status"] = "PURE_PSYCO_PG_RUNTIME_VERIFIED"
    except Exception as exc:
        result["error_type"] = type(exc).__name__
        result["error"] = str(exc)
        raise
    finally:
        output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare-lock")
    prepare.add_argument("source", type=Path)
    prepare.add_argument("destination", type=Path)
    runtime = subparsers.add_parser("runtime-check")
    runtime.add_argument("wheelhouse", type=Path)
    runtime.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "prepare-lock":
        prepare_lock(args.source, args.destination)
    else:
        runtime_check(args.wheelhouse, args.output)


if __name__ == "__main__":
    main()
