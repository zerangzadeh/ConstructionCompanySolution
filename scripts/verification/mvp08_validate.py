"""Isolated PostgreSQL validation; never creates fixtures in Development."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault(
    "MVP08_OUTPUT_ROOT",
    str(ROOT / "output/mvp-08/continuation-20261103/regression"),
)
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

import pytest
from django.core.management import call_command
from django.db import connections
from django.test import TransactionTestCase
from psycopg import sql

TEST_DATABASE = (
    "test_bonira_mvp08_reg_20261103"
    if os.environ.get("MVP08_REGRESSION") == "1"
    else "test_bonira_mvp08_20261103"
)
connection = connections["default"]
with connection.cursor() as cursor:
    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", [TEST_DATABASE])
    if cursor.fetchone() is None:
        cursor.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                sql.Identifier(TEST_DATABASE),
                sql.Identifier("test_bonira_module_selector_clone_20261103"),
            )
        )
connection.settings_dict["TEST"]["NAME"] = TEST_DATABASE
original_setup = TransactionTestCase._fixture_setup.__func__


@classmethod
def isolated_setup(cls):
    for alias in cls._databases_names(include_mirrors=False):
        target = connections[alias]
        if cls.serialized_rollback and hasattr(target, "_test_serialized_contents"):
            if target.settings_dict["NAME"] != TEST_DATABASE:
                raise RuntimeError("Fixture reset requires MVP-08 isolated DB")
            call_command(
                "flush",
                database=alias,
                interactive=False,
                verbosity=0,
                allow_cascade=True,
                inhibit_post_migrate=True,
            )
    original_setup(cls)


TransactionTestCase._fixture_setup = isolated_setup


class FailureEvidence:
    def pytest_collection_modifyitems(self, items):
        # Reused tests must never overwrite historical package evidence.
        for item in items:
            if item.cls is not None and hasattr(item.cls, "evidence_root"):
                item.cls.evidence_root = (
                    ROOT / "output/mvp-08/regression" / item.cls.__name__
                )

    def pytest_runtest_logreport(self, report):
        if report.failed:
            directory = ROOT / "output/mvp-08/failures"
            directory.mkdir(parents=True, exist_ok=True)
            name = report.nodeid.replace("/", "_").replace(":", "_")
            (directory / f"{name}.txt").write_text(
                str(report.longrepr), encoding="utf8"
            )


raise SystemExit(
    pytest.main(
        sys.argv[1:] or ["tests/test_mvp08_demo.py", "--reuse-db", "-q"],
        plugins=[FailureEvidence()],
    )
)
