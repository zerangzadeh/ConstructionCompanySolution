"""Approved EXT-0022 technical diagnostics; no business or readiness authority."""

from __future__ import annotations

import json
import logging
import os
import stat
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from core.operations import SIGNALS, DevelopmentOperationsSink

PRODUCTION_SIGNALS = SIGNALS | {
    "authentication.failed",
    "authorization.denied",
    "document.delivery_failed",
    "migration.failed",
    "deployment.failed",
    "backup.failed",
    "recovery.failed",
    "operational.not_ready",
}
AUTHORITY = "docs/governance/production/PRODUCTION_SCOPED_DISPOSITIONS_20261028.md"


class ProductionOperationsSink(DevelopmentOperationsSink):
    def __init__(self, directory: Path, *, environment: str) -> None:
        super().__init__(directory)
        if environment not in {"production", "production-equivalent-qualification"}:
            raise ValueError("Explicit governed environment required.")
        if os.name != "posix" or stat.S_IMODE(directory.stat().st_mode) & 0o077:
            raise ValueError("Owner-only POSIX sink required.")
        self.environment = environment

    def write(self, *, signal: str, request_id: str | None = None) -> dict:
        if signal not in PRODUCTION_SIGNALS:
            raise ValueError("Unregistered technical signal.")
        observed = datetime.now(UTC)
        record = {
            "event_id": str(uuid4()),
            "signal": signal,
            "request_id": str(UUID(request_id)) if request_id else None,
            "observed_at": observed.isoformat(),
            "retain_until": (observed + timedelta(days=30)).isoformat(),
            "alert": signal not in {"database.reachable", "cache.reachable"},
            "environment": self.environment,
            "authority": AUTHORITY,
            "production_readiness": "NOT_VALIDATED",
        }
        self._persist(record)
        return record

    def _persist(self, record: dict) -> Path:
        if stat.S_IMODE(self.directory.stat().st_mode) & 0o077:
            raise ValueError("Sink permissions changed; delivery refused.")
        result = super()._persist(record)
        result.chmod(0o600)
        descriptor = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return result


class ProductionOperationsHandler(logging.Handler):
    def __init__(self, sink: ProductionOperationsSink) -> None:
        super().__init__()
        self.sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        from core.telemetry import RequestJsonFormatter

        data = json.loads(RequestJsonFormatter().format(record))
        observed = datetime.fromisoformat(data["timestamp"])
        data.update(
            environment=self.sink.environment,
            authority=AUTHORITY,
            retain_until=(observed + timedelta(days=30)).isoformat(),
            production_readiness="NOT_VALIDATED",
        )
        self.sink._persist(data)
        status = data.get("status_code")
        signal = (
            "telemetry.delivery_failed"
            if data.get("event") == "telemetry.delivery_failed"
            else "authentication.failed"
            if status == 401
            else "authorization.denied"
            if status == 403
            else "http.server_error"
            if type(status) is int and 500 <= status <= 599
            else None
        )
        if signal:
            self.sink.write(signal=signal, request_id=data["request_id"])
        if (
            data.get("route") == "documents:version-download"
            and type(status) is int
            and status >= 400
        ):
            self.sink.write(
                signal="document.delivery_failed", request_id=data["request_id"]
            )


def install_authentication_observer(sink: ProductionOperationsSink) -> None:
    """Observe Django's failed-login event; never inspect credentials or grant access."""
    from django.contrib.auth.signals import user_login_failed

    from core.telemetry import current_request_id

    def failed_login(sender: object, **kwargs: object) -> None:
        try:
            sink.write(signal="authentication.failed", request_id=current_request_id())
        except (OSError, ValueError):
            # Diagnostics must not change authentication behavior on sink failure.
            sys.stderr.write(
                json.dumps(
                    {
                        "event": "telemetry.delivery_failed",
                        "request_id": current_request_id(),
                    }
                )
                + "\n"
            )

    user_login_failed.connect(
        failed_login,
        weak=False,
        dispatch_uid="bonira.production.authentication-observer",
    )
