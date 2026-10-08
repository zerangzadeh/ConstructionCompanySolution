"""Run a short, non-certification P10-S20 concurrent calibration.

This harness consumes the frozen workload artifacts without modifying them. It
uses existing active memberships, creates temporary authenticated sessions, and
removes those sessions after the run. Empty POST bodies and the frozen
placeholder UUID deliberately prevent the calibration from becoming a data-load
or business-workflow exercise.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import ctypes
import hashlib
import json
import math
import os
import random
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from ctypes import wintypes
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = ROOT / "certification" / "p10_s20"
PROFILE_ID = "P10-S20-WP1-20261007-E0E078C9-A"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")


def _load(name: str) -> dict[str, Any]:
    return json.loads((ARTIFACT_ROOT / name).read_text(encoding="utf-8"))


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(0, math.ceil(percentile * len(ordered)) - 1)
    return round(ordered[rank], 3)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _FileTime(ctypes.Structure):
    _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]

    def ticks(self) -> int:
        return (self.high << 32) | self.low


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("page_fault_count", wintypes.DWORD),
        ("peak_working_set_size", ctypes.c_size_t),
        ("working_set_size", ctypes.c_size_t),
        ("quota_peak_paged_pool_usage", ctypes.c_size_t),
        ("quota_paged_pool_usage", ctypes.c_size_t),
        ("quota_peak_non_paged_pool_usage", ctypes.c_size_t),
        ("quota_non_paged_pool_usage", ctypes.c_size_t),
        ("pagefile_usage", ctypes.c_size_t),
        ("peak_pagefile_usage", ctypes.c_size_t),
    ]


def _sample_process(pid: int) -> tuple[int, int] | None:
    if sys.platform != "win32":
        return None
    process_query_limited_information = 0x1000
    process_vm_read = 0x0010
    kernel32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
    handle = kernel32.OpenProcess(
        process_query_limited_information | process_vm_read, False, pid
    )
    if not handle:
        return None
    try:
        creation = _FileTime()
        exit_time = _FileTime()
        kernel = _FileTime()
        user = _FileTime()
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            return None
        memory = _ProcessMemoryCounters()
        memory.cb = ctypes.sizeof(memory)
        if not psapi.GetProcessMemoryInfo(
            handle, ctypes.byref(memory), ctypes.sizeof(memory)
        ):
            return None
        return kernel.ticks() + user.ticks(), memory.working_set_size
    finally:
        kernel32.CloseHandle(handle)


def _monitor(
    *,
    stop: threading.Event,
    server_pid: int | None,
    samples: dict[str, list[float]],
    defects: list[str],
) -> None:
    import psycopg
    from django.conf import settings

    process_ids = {"runner": os.getpid()}
    if server_pid:
        process_ids["application"] = server_pid
    previous: dict[str, tuple[int, float]] = {}
    logical_cpus = os.cpu_count() or 1
    database = settings.DATABASES["default"]
    try:
        connection = psycopg.connect(
            dbname=database["NAME"],
            user=database["USER"],
            password=database["PASSWORD"],
            host=database["HOST"],
            port=database["PORT"],
            connect_timeout=5,
        )
    except Exception as exc:  # noqa: BLE001
        defects.append(f"database monitor connect failed: {exc!r}")
        return
    try:
        while not stop.is_set():
            sample_time = time.perf_counter()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT count(*) FROM pg_stat_activity")
                    samples["database_connections"].append(float(cursor.fetchone()[0]))
            except Exception as exc:  # noqa: BLE001
                defects.append(f"database monitor sample failed: {exc!r}")
                break
            for label, pid in process_ids.items():
                current = _sample_process(pid)
                if current is None:
                    continue
                cpu_ticks, working_set = current
                samples[f"{label}_working_set_bytes"].append(float(working_set))
                if label in previous:
                    old_ticks, old_time = previous[label]
                    elapsed = sample_time - old_time
                    if elapsed > 0:
                        cpu = (cpu_ticks - old_ticks) / 10_000_000 / elapsed
                        samples[f"{label}_cpu_percent_one_core"].append(
                            round(cpu * 100, 3)
                        )
                        samples[f"{label}_cpu_percent_host"].append(
                            round(cpu * 100 / logical_cpus, 3)
                        )
                previous[label] = (cpu_ticks, sample_time)
            stop.wait(0.25)
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--virtual-users", type=int, default=50)
    parser.add_argument("--mix-cycles", type=int, default=5)
    parser.add_argument("--server-pid", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import django

    django.setup()
    from django.conf import settings
    from django.contrib.sessions.backends.db import SessionStore
    from django.contrib.sessions.models import Session
    from django.urls import reverse

    from apps.organizations.models import MembershipStatus, OrganizationMembership
    from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY

    workload = _load("workload.json")
    journeys = _load("journeys.json")
    ramp = _load("ramp_think_time.json")
    manifest = _load("artifact_hashes.json")
    if workload["workload_profile_id"] != PROFILE_ID:
        raise RuntimeError("Unexpected workload profile")
    if args.virtual_users != workload["users"]["baseline"]:
        raise RuntimeError("Calibration must use frozen baseline concurrency")

    artifact_hashes = {}
    for name, expected in manifest["artifacts"].items():
        actual = hashlib.sha256((ARTIFACT_ROOT / name).read_bytes()).hexdigest()
        artifact_hashes[name] = {"expected": expected, "actual": actual, "match": actual == expected}
    if not all(item["match"] for item in artifact_hashes.values()):
        raise RuntimeError("Frozen workload artifact hash mismatch")

    memberships = list(
        OrganizationMembership.objects.filter(
            status=MembershipStatus.ACTIVE,
            user__is_active=True,
            organization__status="active",
        )
        .select_related("user", "organization")
        .order_by("organization_id", "user_id")
    )
    if not memberships:
        raise RuntimeError("No active membership is available for calibration")

    placeholder = journeys["placeholder_uuid"]
    resolved = {}
    for journey in journeys["journeys"]:
        resolved[journey["id"]] = [
            (
                method,
                route,
                reverse(
                    route,
                    kwargs={
                        key: placeholder if value == "$UUID" else value
                        for key, value in raw_kwargs.items()
                    }
                    or None,
                ),
            )
            for method, route, raw_kwargs in journey["routes"]
        ]

    schedule = []
    journey_by_id = {item["id"]: item for item in journeys["journeys"]}
    for journey in journeys["journeys"]:
        schedule.extend([journey["id"]] * journey["share"] * args.mix_cycles)
    random.Random(20261007).shuffle(schedule)
    assignments = [schedule[index :: args.virtual_users] for index in range(args.virtual_users)]

    session_keys = []
    identities = []
    for index in range(args.virtual_users):
        membership = memberships[index % len(memberships)]
        session = SessionStore()
        session["_auth_user_id"] = str(membership.user_id)
        session["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
        session["_auth_user_hash"] = membership.user.get_session_auth_hash()
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(membership.organization_id)
        session.create()
        session_keys.append(session.session_key)
        identities.append(
            {
                "session_key": session.session_key,
                "organization_id": str(membership.organization_id),
            }
        )

    lock = threading.Lock()
    barrier = threading.Barrier(args.virtual_users)
    latencies: dict[str, list[float]] = defaultdict(list)
    journey_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    exact_errors: Counter[str] = Counter()
    harness_defects: list[str] = []
    active_workers = 0
    peak_active_workers = 0
    in_flight = 0
    peak_in_flight = 0
    request_count = 0
    samples: dict[str, list[float]] = defaultdict(list)
    stop_monitor = threading.Event()
    monitor = threading.Thread(
        target=_monitor,
        kwargs={
            "stop": stop_monitor,
            "server_pid": args.server_pid,
            "samples": samples,
            "defects": harness_defects,
        },
        daemon=True,
    )

    def worker(index: int) -> None:
        nonlocal active_workers, peak_active_workers, in_flight, peak_in_flight, request_count
        identity = identities[index]
        csrf_token = hashlib.sha256(f"p10-s20-{index}".encode()).hexdigest()[:32]
        cookie = (
            f"{settings.SESSION_COOKIE_NAME}={identity['session_key']}; "
            f"{settings.CSRF_COOKIE_NAME}={csrf_token}"
        )
        opener = urllib.request.build_opener(_NoRedirect())
        barrier.wait(timeout=15)
        with lock:
            active_workers += 1
            peak_active_workers = max(peak_active_workers, active_workers)
        try:
            for journey_id in assignments[index]:
                journey = journey_by_id[journey_id]
                with lock:
                    journey_counts[journey_id] += 1
                for method, route_name, path in resolved[journey_id]:
                    request = urllib.request.Request(
                        args.base_url.rstrip("/") + path,
                        data=b"" if method == "POST" else None,
                        method=method,
                        headers={
                            "Cookie": cookie,
                            "X-CSRFToken": csrf_token,
                            "Referer": args.base_url.rstrip("/") + "/",
                            "X-P10-Calibration-ID": "P10-S20-NON-CERTIFICATION",
                            "Content-Type": "application/x-www-form-urlencoded",
                        },
                    )
                    started = time.perf_counter()
                    with lock:
                        in_flight += 1
                        peak_in_flight = max(peak_in_flight, in_flight)
                    status = None
                    failure = None
                    try:
                        with opener.open(request, timeout=30) as response:
                            response.read(4096)
                            status = response.status
                    except urllib.error.HTTPError as exc:
                        status = exc.code
                        exc.read(4096)
                    except Exception as exc:  # noqa: BLE001
                        failure = f"{type(exc).__name__}: {exc}"
                    finally:
                        elapsed_ms = (time.perf_counter() - started) * 1000
                        with lock:
                            in_flight -= 1
                            request_count += 1
                            latencies[journey["class"]].append(elapsed_ms)
                            if status is not None:
                                status_counts[str(status)] += 1
                                if status >= 400:
                                    exact_errors[f"{method} {route_name}: HTTP {status}"] += 1
                            else:
                                status_counts["transport_error"] += 1
                                exact_errors[f"{method} {route_name}: {failure}"] += 1
                think = (
                    ramp["heavy_think_time_seconds"]
                    if journey["class"] in {"report", "bounded"}
                    else ramp["ordinary_think_time_seconds"]
                )
                time.sleep(random.Random(20261007 + index + journey_counts[journey_id]).uniform(think["minimum"], think["maximum"]))
        finally:
            with lock:
                active_workers -= 1

    started_at = time.time()
    started_perf = time.perf_counter()
    monitor.start()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.virtual_users) as executor:
            futures = [executor.submit(worker, index) for index in range(args.virtual_users)]
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as exc:  # noqa: BLE001
                    harness_defects.append(f"worker failed: {exc!r}")
    finally:
        stop_monitor.set()
        monitor.join(timeout=5)
        Session.objects.filter(session_key__in=session_keys).delete()
    duration_seconds = round(time.perf_counter() - started_perf, 3)

    total_journeys = sum(journey_counts.values())
    mix = []
    for journey in journeys["journeys"]:
        actual = journey_counts[journey["id"]]
        actual_percent = actual / total_journeys * 100 if total_journeys else 0
        mix.append(
            {
                "journey_id": journey["id"],
                "expected_percent": journey["share"],
                "actual_count": actual,
                "actual_percent": round(actual_percent, 3),
                "delta_percentage_points": round(actual_percent - journey["share"], 3),
            }
        )

    successful_requests = sum(
        count for status, count in status_counts.items() if status.isdigit() and int(status) < 400
    )
    error_requests = request_count - successful_requests
    runtime_errors = {
        key: value
        for key, value in exact_errors.items()
        if "HTTP 5" in key or "HTTP" not in key
    }
    report = {
        "classification": "non-certification performance calibration",
        "workload_profile_id": PROFILE_ID,
        "environment_id": _load("environment.json")["environment_id"],
        "capacity_classification": "environment-qualified / production capacity certification still gated",
        "started_at_unix": started_at,
        "duration_seconds": duration_seconds,
        "configuration": {
            "virtual_users": args.virtual_users,
            "mix_cycles": args.mix_cycles,
            "closed_loop": ramp["closed_loop"],
            "base_url": args.base_url,
            "existing_memberships_used": len(memberships),
            "existing_organizations_used": len({item["organization_id"] for item in identities}),
        },
        "artifact_hash_verification": artifact_hashes,
        "concurrency": {
            "virtual_users_reached": peak_active_workers,
            "peak_in_flight_requests": peak_in_flight,
        },
        "counts": {
            "journeys": total_journeys,
            "requests": request_count,
            "http_statuses": dict(sorted(status_counts.items())),
        },
        "journey_mix": mix,
        "latency_ms_by_major_class": {
            name: {
                "samples": len(values),
                "p50": _percentile(values, 0.50),
                "p95": _percentile(values, 0.95),
                "p99": _percentile(values, 0.99),
                "mean": round(statistics.fmean(values), 3) if values else None,
            }
            for name, values in sorted(latencies.items())
        },
        "errors": {
            "count": error_requests,
            "rate": round(error_requests / request_count, 6) if request_count else None,
            "exact": dict(sorted(exact_errors.items())),
        },
        "database_connections": {
            "samples": len(samples["database_connections"]),
            "minimum": min(samples["database_connections"], default=None),
            "peak": max(samples["database_connections"], default=None),
        },
        "resource_metrics": {
            name: {
                "samples": len(values),
                "minimum": round(min(values), 3) if values else None,
                "mean": round(statistics.fmean(values), 3) if values else None,
                "peak": round(max(values), 3) if values else None,
            }
            for name, values in sorted(samples.items())
            if name != "database_connections"
        },
        "harness_defects": harness_defects,
        "runtime_defects": runtime_errors,
        "full_environment_qualified_run_may_start": not harness_defects and not runtime_errors,
        "performance_run_executed": False,
        "overall_status": "P10-S19–S21 = BLOCKED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "duration_seconds": duration_seconds,
                "virtual_users": peak_active_workers,
                "journeys": total_journeys,
                "requests": request_count,
                "errors": error_requests,
                "runtime_defects": len(runtime_errors),
                "harness_defects": len(harness_defects),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
