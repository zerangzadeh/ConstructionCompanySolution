"""Static and bounded connectivity preflight for the frozen P10-S20 workload."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from uuid import UUID


PROFILE_ID = "P10-S20-WP1-20261007-E0E078C9-A"
ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def _environment_fingerprint(environment: dict[str, Any]) -> str:
    payload = dict(environment)
    payload.pop("fingerprint_sha256", None)
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_routes(journeys: dict[str, Any]) -> dict[str, Any]:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    import django

    django.setup()
    from django.urls import reverse

    placeholder = str(UUID(journeys["placeholder_uuid"]))
    resolved: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    for journey in journeys["journeys"]:
        service = journey.get("service")
        if service:
            module_name, attribute = service.rsplit(".", 1)
            module = importlib.import_module(module_name)
            if not callable(getattr(module, attribute)):
                failures.append({"journey": journey["id"], "service": service})
        for method, name, raw_kwargs in journey["routes"]:
            kwargs = {
                key: placeholder if value == "$UUID" else value
                for key, value in raw_kwargs.items()
            }
            try:
                path = reverse(name, kwargs=kwargs or None)
            except Exception as exc:  # noqa: BLE001 - evidence must retain exact failure
                failures.append(
                    {"journey": journey["id"], "route": name, "error": repr(exc)}
                )
            else:
                resolved.append(
                    {"journey": journey["id"], "method": method, "route": name, "path": path}
                )
    return {"status": "PASS" if not failures else "FAIL", "resolved": resolved, "failures": failures}


def _reachability(base_url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        base_url.rstrip("/") + "/accounts/login/",
        headers={"X-P10-Preflight-ID": "P10-S20-PREFLIGHT-ONLY"},
        method="GET",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response.read(1024)
            status = response.status
            headers = dict(response.headers.items())
    except (OSError, urllib.error.URLError) as exc:
        return {"status": "FAIL", "error": repr(exc)}
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    correlation_header = next(
        (value for key, value in headers.items() if key.lower() in {"x-request-id", "x-correlation-id"}),
        None,
    )
    return {
        "status": "PASS" if status < 500 else "FAIL",
        "http_status": status,
        "latency_ms": elapsed_ms,
        "server_correlation_id": correlation_header,
    }


def _database_metrics() -> dict[str, Any]:
    try:
        import psycopg

        connection = psycopg.connect(
            dbname=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            host=os.environ.get("DB_HOST", "localhost"),
            port=os.environ.get("DB_PORT", "5432"),
            connect_timeout=5,
        )
        with connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*), current_setting('max_connections')::int "
                "FROM pg_stat_activity"
            )
            active, maximum = cursor.fetchone()
        return {
            "status": "PASS",
            "active_connections": active,
            "max_connections": maximum,
            "utilization": active / maximum,
        }
    except Exception as exc:  # noqa: BLE001 - preflight evidence retains failure
        return {"status": "FAIL", "error": repr(exc)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    workload = _load("workload.json")
    journeys = _load("journeys.json")
    ramp = _load("ramp_think_time.json")
    volume = _load("dataset_volume.json")
    environment = _load("environment.json")
    ids_match = all(
        artifact["workload_profile_id"] == PROFILE_ID
        for artifact in (workload, journeys, ramp, volume, environment)
    )
    share_total = sum(item["share"] for item in journeys["journeys"])
    routes = _validate_routes(journeys)
    reachability = _reachability(environment["topology"]["edge"]["endpoint"])
    database = _database_metrics()
    observed_fingerprint = _environment_fingerprint(environment)
    observability = environment["topology"]["observability"]
    required_observability = all(
        observability[key]
        for key in (
            "runner_latency_and_status",
            "runner_error_classification",
            "server_correlation_id",
            "application_cpu",
            "application_memory",
            "postgresql_active_connections",
            "postgresql_connection_limit",
            "postgresql_waits",
            "database_cpu",
        )
    )
    report = {
        "workload_profile_id": PROFILE_ID,
        "environment_id": environment["environment_id"],
        "checks": {
            "profile_ids": {"status": "PASS" if ids_match else "FAIL"},
            "journey_share_total": {"status": "PASS" if share_total == 100 else "FAIL", "value": share_total},
            "routes_and_services": routes,
            "endpoint_reachability": reachability,
            "database_connection_metrics": database,
            "environment_fingerprint": {
                "status": "PASS" if observed_fingerprint == environment["fingerprint_sha256"] else "FAIL",
                "observed": observed_fingerprint,
                "recorded": environment["fingerprint_sha256"],
            },
            "required_observability": {"status": "PASS" if required_observability else "FAIL"},
            "isolated_environment": {"status": "FAIL"},
            "load_runner_headroom": {"status": "FAIL"},
        },
        "performance_run_executed": False,
    }
    report["ready_for_performance_execution"] = all(
        check["status"] == "PASS" for check in report["checks"].values()
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "PASS" if report["ready_for_performance_execution"] else "BLOCKED",
                "routes": routes["status"],
                "reachability": reachability["status"],
                "observability": report["checks"]["required_observability"]["status"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
