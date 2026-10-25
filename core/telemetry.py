"""Request outcome telemetry; never a business audit or readiness authority."""

from __future__ import annotations

import json
import logging
import re
import sys
from collections.abc import Callable
from contextvars import ContextVar
from datetime import UTC, datetime
from time import perf_counter_ns
from uuid import UUID, uuid4

from django.http import HttpRequest, HttpResponse

_request_id: ContextVar[str | None] = ContextVar("bonira_request_id", default=None)
_logger = logging.getLogger("bonira.request")
_ROUTE = re.compile(r"[A-Za-z0-9_.:-]{1,200}\Z")
_METHODS = frozenset(
    {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE"}
)


def current_request_id() -> str | None:
    return _request_id.get()


class RequestJsonFormatter(logging.Formatter):
    """Serialize only fixed fields, excluding messages, payloads and tracebacks."""

    def format(self, record: logging.LogRecord) -> str:
        correlation = getattr(record, "request_id", None)
        try:
            correlation = str(UUID(correlation))
        except (ValueError, TypeError, AttributeError):
            correlation = None
        route = getattr(record, "route", None)
        if not isinstance(route, str) or not _ROUTE.fullmatch(route):
            route = None
        method = getattr(record, "method", None)
        status = getattr(record, "status_code", None)
        duration = getattr(record, "duration_ms", None)
        return json.dumps(
            {
                "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
                "event": "http.response",
                "request_id": correlation,
                "method": method if method in _METHODS else None,
                "route": route,
                "status_code": status if type(status) is int else None,
                "duration_ms": duration if type(duration) is int else None,
            },
            separators=(",", ":"),
        )


class RequestTelemetryMiddleware:
    """Correlate all outcomes, including denials, without inspecting tenant data."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Client-supplied IDs never determine server correlation or authorization.
        correlation = str(uuid4())
        request.request_id = correlation
        token = _request_id.set(correlation)
        started = perf_counter_ns()
        status = 500
        try:
            response = self.get_response(request)
            status = response.status_code
            response["X-Request-ID"] = correlation
            return response
        finally:
            try:
                _logger.log(
                    logging.ERROR if status >= 500 else logging.INFO,
                    "http.response",
                    extra={
                        "request_id": correlation,
                        "method": request.method,
                        "route": getattr(
                            getattr(request, "resolver_match", None), "view_name", None
                        ),
                        "status_code": status,
                        "duration_ms": max(
                            0, (perf_counter_ns() - started) // 1_000_000
                        ),
                    },
                )
            except Exception:  # noqa: BLE001 -- isolate arbitrary logging handler failures
                # Logging must not turn a committed business action into a retry.
                # Retain an explicit sanitized delivery-failure signal if possible.
                request.telemetry_delivery_failed = True
                try:
                    sys.stderr.write(
                        json.dumps(
                            {
                                "event": "telemetry.delivery_failed",
                                "request_id": correlation,
                            }
                        )
                        + "\n"
                    )
                except (OSError, ValueError):
                    request.telemetry_fallback_failed = True
            finally:
                _request_id.reset(token)
