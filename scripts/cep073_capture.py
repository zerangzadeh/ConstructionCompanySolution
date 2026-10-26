"""Pytest observer for bounded CEP-073 runtime timing and read-only query plans.

EXPLAIN runs through the existing DB-API connection so Django query-budget
assertions continue to measure only application queries. Only whitelisted pure
source SELECTs are observed; locking queries and all mutations are excluded.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from django.db import connection

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/governance/cep/evidence/CEP-073_DEVELOPMENT_20261026"
RESULTS = {
    "started_at": datetime.now(timezone.utc).isoformat(),
    "tests": [],
    "plans": [],
}


def save():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "RUNTIME.json").write_text(json.dumps(RESULTS, indent=2), encoding="utf-8")


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    name = connection.settings_dict["NAME"]
    assert name.startswith("test_bonira_cep073_"), (
        "CEP073 must use its disposable test database"
    )
    captured = {}

    def observe(execute, query, params, many, context):
        started = time.perf_counter()
        result = execute(query, params, many, context)
        elapsed = time.perf_counter() - started
        upper = query.upper()
        if (
            many
            or not upper.lstrip().startswith("SELECT")
            or any(
                token in upper
                for token in ("FOR UPDATE", "PG_ADVISORY", "FOR SHARE", "NEXTVAL")
            )
        ):
            return result
        category = None
        if 'FROM "accounting_journalentry"' in query and "LIMIT 25" in upper:
            category = "GL_BOUNDED_LIST"
        elif 'FROM "audit_auditevent"' in query and "LIMIT 25" in upper:
            category = "AUDIT_BOUNDED_LIST"
        elif 'FROM "inventory_stocktransaction"' in query and "SUM(" in upper:
            category = "INVENTORY_SCOPED_AGGREGATE"
        elif 'FROM "inventory_inventoryvaluationpool"' in query and "SUM(" in upper:
            category = "REPORTING_SOURCE_AGGREGATE"
        limit = 2 if category == "REPORTING_SOURCE_AGGREGATE" else 1
        if (
            category
            and context["connection"].force_debug_cursor
            and captured.get(category, 0) < limit
        ):
            captured[category] = captured.get(category, 0) + 1
            with context["connection"].connection.cursor() as cursor:
                cursor.execute(
                    "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + query, params
                )
                plan = cursor.fetchone()[0]
            RESULTS["plans"].append(
                {
                    "scenario": item.nodeid,
                    "category": category,
                    "application_execute_seconds": elapsed,
                    "sql_template": query,
                    "postgresql_explain_analyze": plan,
                }
            )
            save()
        return result

    with connection.execute_wrapper(observe):
        yield


def pytest_runtest_logreport(report):
    if report.when == "call" or report.failed:
        RESULTS["tests"].append(
            {
                "scenario": report.nodeid,
                "phase": report.when,
                "outcome": report.outcome,
                "seconds": report.duration,
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )
        save()


def pytest_sessionfinish(session, exitstatus):
    RESULTS["exit_code"] = int(exitstatus)
    RESULTS["finished_at"] = datetime.now(timezone.utc).isoformat()
    RESULTS["configured_business_database_accessed"] = False
    RESULTS["database_base_name"] = os.environ["DB_NAME"]
    save()
