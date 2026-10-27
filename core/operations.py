"""Local operational preparation, without production policy or business authority."""

from __future__ import annotations

import json
import logging
import os
import stat
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Self
from uuid import uuid4

SIGNALS = frozenset(
    {
        "database.reachable",
        "database.unreachable",
        "cache.reachable",
        "cache.unreachable",
        "http.server_error",
        "telemetry.delivery_failed",
    }
)
# Discrete failures only: no latency/error-rate threshold, SLA or escalation timer.
ALERT_SIGNALS = SIGNALS - {"database.reachable", "cache.reachable"}


def dependency_signals(
    *, database: Callable[[], None], cache: Callable[[], None]
) -> list[str]:
    """Probe both dependencies even if one fails; omit exception/connection details."""
    result = []
    for name, probe in (("database", database), ("cache", cache)):
        try:
            probe()
        except Exception:  # noqa: BLE001 -- sanitize arbitrary dependency failures
            result.append(f"{name}.unreachable")
        else:
            result.append(f"{name}.reachable")
    return result


def request_failure_signal(record: dict) -> str | None:
    """Project only established technical events; never copy arbitrary log fields."""
    if record.get("event") == "telemetry.delivery_failed":
        return "telemetry.delivery_failed"
    status = record.get("status_code")
    if (
        record.get("event") == "http.response"
        and type(status) is int
        and 500 <= status <= 599
    ):
        return "http.server_error"
    return None


class LocalOperationsAdapter:
    """Disposable local alert destination and diagnostic retention implementation.

    Owns only its freshly created temporary directory and files. No path, external
    destination, credentials, production activation or audit deletion is accepted.
    Caller supplies a timezone-aware retention cutoff; there is no default policy.
    """

    def __init__(self) -> None:
        self._temporary = tempfile.TemporaryDirectory(prefix="bonira-operations-test-")
        self.directory = Path(self._temporary.name).resolve()
        self._records: dict[Path, datetime] = {}

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self._temporary.cleanup()

    def emit(self, signal: str) -> dict:
        if signal not in SIGNALS:
            raise ValueError("Unregistered technical signal.")
        observed = datetime.now(UTC)
        record = {
            "event_id": str(uuid4()),
            "signal": signal,
            "observed_at": observed.isoformat(),
            "alert": signal in ALERT_SIGNALS,
            "environment": "disposable-local-test",
            "production_readiness": "NOT_VALIDATED",
        }
        path = self.directory / f"{record['event_id']}.json"
        with path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(record, separators=(",", ":")))
        self._records[path] = observed
        return record

    def retain(self, *, cutoff: datetime, execute: bool = False) -> list[str]:
        """Plan by default; execute only against files this adapter owns."""
        if cutoff.tzinfo is None or cutoff.utcoffset() is None:
            raise ValueError("Retention cutoff must be timezone-aware.")
        if cutoff > datetime.now(UTC):
            raise ValueError("Retention cutoff cannot be in the future.")
        selected = [
            path for path, observed in self._records.items() if observed < cutoff
        ]
        for path in selected:
            if path.is_symlink() or path.resolve().parent != self.directory:
                raise ValueError("Diagnostic path escaped local adapter ownership.")
        if execute:
            for path in selected:
                path.unlink()
                del self._records[path]
        return [path.name for path in selected]


class DevelopmentOperationsSink:
    """Explicitly activated local diagnostics with EXT-0022 minimum retention.

    The operator must provision and verify restricted filesystem access before
    construction. No external destination, business payload or purge is accepted.
    Restarting or closing the executor never removes retained evidence.
    """

    def __init__(self, directory: Path) -> None:
        if not directory.is_absolute() or not directory.is_dir():
            raise ValueError("An existing absolute restricted directory is required.")
        for path in (directory, *directory.parents):
            if path.is_symlink() or (
                getattr(path.lstat(), "st_file_attributes", 0)
                & stat.FILE_ATTRIBUTE_REPARSE_POINT
            ):
                raise ValueError("Linked diagnostic paths are forbidden.")
        self.directory = directory.resolve()

    def write(self, *, signal: str, request_id: str | None = None) -> dict:
        from uuid import UUID

        if signal not in SIGNALS:
            raise ValueError("Unregistered technical signal.")
        if request_id is not None:
            request_id = str(UUID(request_id))
        observed = datetime.now(UTC)
        record = {
            "event_id": str(uuid4()),
            "signal": signal,
            "request_id": request_id,
            "observed_at": observed.isoformat(),
            "retain_until": (observed + timedelta(days=30)).isoformat(),
            "alert": signal in ALERT_SIGNALS,
            "environment": "development-non-production",
            "authority": "EXT-0022-HUMAN-20261027",
            "production_readiness": "NOT_VALIDATED",
        }
        self._persist(record)
        return record

    def _persist(self, record: dict) -> Path:
        """Internal fixed-schema diagnostic writer; durable receipt after fsync."""
        # Callers are the registered signal writer and the fixed-field formatter.
        path = self.directory / f"{uuid4()}.json"
        with path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(record, separators=(",", ":")))
            stream.flush()
            os.fsync(stream.fileno())
        return path


class DevelopmentOperationsHandler(logging.Handler):
    """Capture existing HTTP telemetry and discrete alerts in a local sink."""

    def __init__(self, sink: DevelopmentOperationsSink) -> None:
        super().__init__()
        self.sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        from core.telemetry import RequestJsonFormatter

        data = json.loads(RequestJsonFormatter().format(record))
        observed = datetime.fromisoformat(data["timestamp"])
        data.update(
            environment="development-non-production",
            authority="EXT-0022-HUMAN-20261027",
            retain_until=(observed + timedelta(days=30)).isoformat(),
            production_readiness="NOT_VALIDATED",
        )
        self.sink._persist(data)
        signal = request_failure_signal(data)
        if signal is not None:
            self.sink.write(signal=signal, request_id=data["request_id"])
