"""Run bounded remediation tests on a dedicated non-production test database."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

from django.conf import settings

settings.DATABASES["default"].setdefault("TEST", {})["NAME"] = (
    "test_cep006_imb0066_20261019"
)

import pytest


class QueryEvidence:
    """Retain executed query shapes without bound values or tenant identifiers."""

    def __init__(self):
        self.results = {}

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self, item):
        if item.name not in {
            "test_queries_limit_journals_and_first_debit_without_line_prefetch",
            "test_one_bounded_source_read_includes_actor_and_no_writes",
        }:
            yield
            return
        from django.db import connection

        queries = []

        def capture(execute, sql, params, many, context):
            result = execute(sql, params, many, context)
            if sql.lstrip().upper().startswith("SELECT") and any(
                f'FROM "{table}"' in sql and f'"{table}"."organization_id" =' in sql
                for table in ("accounting_journalentry", "audit_auditevent")
            ):
                queries.append(
                    {"sql_without_parameters": sql, "rows": context["cursor"].rowcount}
                )
            return result

        with connection.execute_wrapper(capture):
            yield
        self.results[item.nodeid] = queries

    def pytest_sessionfinish(self):
        if self.results:
            (ROOT / "output/cep-006/imb0066/query-evidence.json").write_text(
                json.dumps(self.results, indent=2) + "\n", encoding="utf-8"
            )


if __name__ == "__main__":
    regression = "--regression" in sys.argv
    targets = (
        [
            "apps/accounting/tests.py::AccountingTenantUiTests",
            "apps/audit/tests.py",
        ]
        if regression
        else ["apps/accounting/test_imb0066.py", "apps/audit/test_imb0066.py"]
    )
    name = "regression" if regression else "focused"
    raise SystemExit(
        pytest.main(
            [
                *targets,
                "-q",
                "--reuse-db",
                f"--junitxml=output/cep-006/imb0066/{name}.xml",
            ],
            plugins=[QueryEvidence()] if not regression else [],
        )
    )
