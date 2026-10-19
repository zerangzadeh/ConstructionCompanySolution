"""Offline, non-production backup preparation; never a readiness certificate.

Uses PostgreSQL's own dump format and copies explicitly selected quiescent local
trees. Production adapters, storage/encryption, scheduling, retention and
cross-store consistency policy require their separately approved contracts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import stat
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

FILE_CLASSES = frozenset(
    {"document_media", "configuration_metadata", "audit_operational"}
)


class BackupError(Exception):
    """Capture failed; a created bundle must not be used as a successful backup."""


@dataclass(frozen=True)
class BackupPlan:
    environment: str
    source_revision: str
    operator_reference: str
    recovery_reference: str
    consistency_reference: str
    database_service: str
    pg_dump: Path
    roots: dict[str, Path]
    destination: Path
    command_timeout_seconds: int


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_link(path: Path) -> None:
    metadata = path.lstat()
    if path.is_symlink() or getattr(metadata, "st_file_attributes", 0) & getattr(
        stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0
    ):
        raise BackupError("Links and reparse points are not capture sources.")


def _inventory(root: Path) -> dict[str, str | None]:
    result: dict[str, str | None] = {}

    def visit(directory: Path) -> None:
        _reject_link(directory)
        for path in sorted(directory.iterdir()):
            _reject_link(path)
            relative = path.relative_to(root).as_posix()
            if path.is_dir():
                result[relative] = None
                visit(path)
            elif path.is_file():
                result[relative] = file_hash(path)
            else:
                raise BackupError("Only regular files and directories are supported.")

    visit(root)
    return result


def _validate(plan: BackupPlan) -> None:
    if plan.environment != "non-production":
        raise BackupError("This preparation adapter permits non-production only.")
    if not re.fullmatch(r"[0-9a-f]{40}", plan.source_revision):
        raise BackupError("An exact source revision is required.")
    for reference in (
        plan.operator_reference,
        plan.recovery_reference,
        plan.consistency_reference,
    ):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}", reference):
            raise BackupError("Explicit non-secret evidence references are required.")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", plan.database_service):
        raise BackupError("Use a named libpq service, never inline credentials.")
    if (
        type(plan.command_timeout_seconds) is not int
        or plan.command_timeout_seconds <= 0
    ):
        raise BackupError("An explicit positive tool timeout is required.")
    if set(plan.roots) != FILE_CLASSES:
        raise BackupError("All three non-database data classes must be explicit.")
    if not plan.pg_dump.is_absolute() or not plan.pg_dump.is_file():
        raise BackupError("An explicit PostgreSQL pg_dump executable is required.")
    paths = [*plan.roots.values(), plan.destination]
    for path in paths:
        if not path.is_absolute():
            raise BackupError("Source and destination paths must be absolute.")
        for ancestor in (path, *path.parents):
            if ancestor.exists() or ancestor.is_symlink():
                _reject_link(ancestor)
    resolved = [p.resolve() for p in paths]
    for index, path in enumerate(resolved):
        for other in resolved[index + 1 :]:
            if path == other or path in other.parents or other in path.parents:
                raise BackupError("Source and destination trees must not overlap.")
    if plan.destination.exists() or not plan.destination.parent.is_dir():
        raise BackupError("Use a new destination beneath an existing protected parent.")
    if any(not p.is_dir() for p in plan.roots.values()):
        raise BackupError("Every file-class root must exist explicitly.")


def create_bundle(plan: BackupPlan) -> dict[str, object]:
    """Capture bytes only. References are provenance, never approval or coherence.

    libpq obtains connection credentials from the operator's environment/service
    files. Raw subprocess output is discarded to avoid credential/data leakage.
    The parent must already have suitable OS access controls; this adapter does
    not grant permissions, encrypt data or manage credentials.
    """
    _validate(plan)
    plan.destination.mkdir()  # Exclusive creation; never overwrite a prior run.
    evidence: dict[str, object] = {
        "schema": "bonira.backup-capture.v1",
        "environment": plan.environment,
        "source_revision": plan.source_revision,
        "operator_reference": plan.operator_reference,
        "recovery_reference": plan.recovery_reference,
        "consistency_reference": plan.consistency_reference,
        "started_at": datetime.now(UTC).isoformat(),
        "capture_status": "INCOMPLETE",
        "restore_status": "NOT_EXECUTED",
        "cross_store_consistency": "UNVERIFIED",
        "production_certification": "NOT_EXECUTED",
        "classes": {},
    }
    try:
        before = {key: _inventory(root) for key, root in plan.roots.items()}
        dump = plan.destination / "database.dump"
        result = subprocess.run(
            [
                str(plan.pg_dump),
                "--format=custom",
                "--no-password",
                f"--dbname=service={plan.database_service}",
                f"--file={dump}",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=plan.command_timeout_seconds,
            check=False,
        )
        evidence["database_tool_exit_code"] = result.returncode
        if result.returncode or not dump.is_file() or dump.stat().st_size == 0:
            raise BackupError("Database capture failed.")
        _reject_link(dump)
        evidence["classes"]["transactional_database"] = {"sha256": file_hash(dump)}
        for key, root in sorted(plan.roots.items()):
            target = plan.destination / key
            shutil.copytree(root, target, symlinks=True)
            captured = _inventory(target)
            if captured != before[key] or _inventory(root) != before[key]:
                raise BackupError("File tree changed during capture.")
            evidence["classes"][key] = {
                "files": sum(value is not None for value in captured.values()),
                "inventory_sha256": hashlib.sha256(
                    json.dumps(captured, sort_keys=True).encode()
                ).hexdigest(),
            }
            # Paths/hashes stay inside the confidential bundle, not public logs.
            (plan.destination / f"{key}.inventory.json").write_text(
                json.dumps(captured, sort_keys=True, indent=2) + "\n", encoding="utf-8"
            )
        evidence["capture_status"] = "CAPTURED_NOT_RESTORE_VERIFIED"
    except (BackupError, OSError, ValueError, subprocess.SubprocessError) as exc:
        evidence["capture_status"] = "FAILED"
        evidence["failure_type"] = type(exc).__name__
        raise BackupError(
            "Capture failed; retain restricted evidence and investigate."
        ) from None
    finally:
        evidence["completed_at"] = datetime.now(UTC).isoformat()
        (plan.destination / "capture.json").write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    args = parser.parse_args()
    try:
        values = json.loads(args.plan.read_text(encoding="utf-8"))
        values["roots"] = {key: Path(value) for key, value in values["roots"].items()}
        for key in ("pg_dump", "destination"):
            values[key] = Path(values[key])
        create_bundle(BackupPlan(**values))
    except (BackupError, OSError, ValueError, KeyError, TypeError):
        print("Capture rejected or failed. Inspect restricted run evidence if created.")
        return 1
    print(
        "Non-production bytes captured; restore/consistency/certification unverified."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
